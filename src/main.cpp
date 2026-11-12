#include <Arduino.h>
#include "USB.h"
#include "USBHIDGamepad.h"

#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "This project requires an ESP32-S3."
#endif
#if ARDUINO_USB_MODE != 0
#error "Select USB-OTG/TinyUSB with ARDUINO_USB_MODE=0."
#endif
#if ARDUINO_USB_CDC_ON_BOOT != 1
#error "Keep USB CDC enabled so serial diagnostics and upload reset are available."
#endif
#if !CONFIG_TINYUSB_ENABLED || !CONFIG_TINYUSB_HID_ENABLED
#error "The installed framework must include TinyUSB HID support."
#endif
#ifndef JOYSTICK_TEST_MODE
#define JOYSTICK_TEST_MODE 0
#endif

namespace {
USBHIDGamepad gamepad;

struct AxisConfig {
  uint8_t pin;
  int minimum;
  int center;
  int maximum;
  int deadzone;
  bool inverted;
};

// ADC counts, not millivolts. Adjust each row using the serial RAW readings.
// Order: yaw (USB X), throttle (USB Y), roll (USB Z), pitch (USB Rz).
// Released centers and full-travel limits measured on 2026-11-13.
constexpr AxisConfig axes[] = {
    {D0, 0, 1857, 4095, 40, false},
    {D1, 0, 1884, 4095,  0, false},
    {D2, 0, 1914, 4095, 40, false},
    {D3, 0, 1905, 4095, 40, false},
};
constexpr size_t axisCount = sizeof(axes) / sizeof(axes[0]);
static_assert(axisCount == 4, "Four independent inputs are required.");
static_assert(D0 == 1 && D1 == 2 && D2 == 3 && D3 == 4,
              "Unexpected XIAO ESP32-S3 variant pin mapping.");

constexpr bool validCalibration(const AxisConfig &axis) {
  return axis.minimum >= 0 && axis.maximum <= 4095 && axis.deadzone >= 0 &&
         axis.minimum < axis.center - axis.deadzone &&
         axis.center + axis.deadzone < axis.maximum;
}
static_assert(validCalibration(axes[0]) && validCalibration(axes[1]) &&
                  validCalibration(axes[2]) && validCalibration(axes[3]),
              "Each calibration needs min < center-deadzone <= center+deadzone < max.");

constexpr uint32_t reportIntervalMs = 8;  // 125 Hz; keep sending after reconnect.
int raw[axisCount] = {};
int32_t filteredQ8[axisCount] = {};
int8_t reports[axisCount] = {};
uint32_t failedReports = 0;

struct DebouncedButton {
  uint8_t pin;
  bool sampledPressed;
  bool stablePressed;
  uint32_t changedAt;
};

// USB bits 0/1 appear as Buttons 1/2 in Windows. SW closes to GND.
DebouncedButton buttons[] = {{D4, false, false, 0}, {D5, false, false, 0}};
constexpr uint32_t buttonDebounceMs = 20;
static_assert(D4 == 5 && D5 == 6, "Unexpected XIAO switch pin mapping.");

uint32_t readButtons(uint32_t now) {
  uint32_t mask = 0;
  for (size_t index = 0; index < sizeof(buttons) / sizeof(buttons[0]); ++index) {
    auto &button = buttons[index];
    const bool pressed = digitalRead(button.pin) == LOW;
    if (pressed != button.sampledPressed) {
      button.sampledPressed = pressed;
      button.changedAt = now;
    }
    if (now - button.changedAt >= buttonDebounceMs) {
      button.stablePressed = button.sampledPressed;
    }
    if (button.stablePressed) {
      mask |= uint32_t{1} << index;
    }
  }
  return mask;
}

int readAveraged(uint8_t pin) {
  int total = 0;
  for (int sample = 0; sample < 4; ++sample) {
    total += analogRead(pin);
  }
  return (total + 2) / 4;
}

int8_t mapAxis(int reading, const AxisConfig &axis) {
  const int value = constrain(reading, axis.minimum, axis.maximum);
  const int lowCenter = axis.center - axis.deadzone;
  const int highCenter = axis.center + axis.deadzone;
  int result = 0;
  if (value < lowCenter) {
    result = -((lowCenter - value) * 127L / (lowCenter - axis.minimum));
  } else if (value > highCenter) {
    result = (value - highCenter) * 127L / (axis.maximum - highCenter);
  }
  return static_cast<int8_t>(axis.inverted ? -result : result);
}

void physicalReports() {
  for (size_t index = 0; index < axisCount; ++index) {
    raw[index] = readAveraged(axes[index].pin);
    // Fixed-point EMA avoids losing small changes to integer rounding.
    filteredQ8[index] += ((raw[index] << 8) - filteredQ8[index]) / 4;
    reports[index] = mapAxis((filteredQ8[index] + 128) >> 8, axes[index]);
  }
}

void testReports(uint32_t now) {
  for (auto &value : reports) {
    value = 0;
  }
  // Each 4 s slot: neutral, positive, negative, neutral. Other axes stay zero.
  const size_t active = (now / 4000U) % axisCount;
  const uint32_t phase = now % 4000U;
  int value = 0;
  if (phase >= 500 && phase < 1500) {
    value = (phase - 500) * 127L / 1000;
  } else if (phase >= 1500 && phase < 2500) {
    value = 127 - (phase - 1500) * 254L / 1000;
  } else if (phase >= 2500 && phase < 3500) {
    value = -127 + (phase - 2500) * 127L / 1000;
  }
  reports[active] = static_cast<int8_t>(value);
}
}  // namespace

void setup() {
  for (const auto &button : buttons) {
    pinMode(button.pin, INPUT_PULLUP);
  }
#if !JOYSTICK_TEST_MODE
  analogReadResolution(12);
  for (size_t index = 0; index < axisCount; ++index) {
    pinMode(axes[index].pin, INPUT);
    analogSetPinAttenuation(axes[index].pin, ADC_11db);
    raw[index] = readAveraged(axes[index].pin);
    filteredQ8[index] = raw[index] << 8;
  }
#endif
  // Global gamepad registers its HID descriptor before Arduino's CDC startup.
  // USB_PRODUCT is defined at compile time because CDC can start before setup.
  gamepad.begin();
  USB.begin();
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);
  // Never wait for Serial: the joystick works with no serial monitor open.
}

void loop() {
  static uint32_t lastReport = 0;
  static uint32_t lastDiagnostic = 0;
  const uint32_t now = millis();
  if (now - lastReport < reportIntervalMs) {
    delay(1);
    return;
  }
  lastReport = now;
#if JOYSTICK_TEST_MODE
  testReports(now);
#else
  physicalReports();
#endif
  const uint32_t buttonMask = readButtons(now);
  // Axes and both momentary switches share one coherent USB report.
  // Rx/Ry and the hat stay neutral. No firmware toggle or keyboard emulation.
  if (!gamepad.send(reports[0], reports[1], reports[2], reports[3],
                    0, 0, HAT_CENTER, buttonMask)) {
    ++failedReports;
  }
  if (now - lastDiagnostic >= 500) {
    lastDiagnostic = now;
    // A complete short line fits the CDC FIFO. Skip diagnostics if the host
    // isn't reading, so a paused monitor cannot stall joystick reports.
    char line[64];
    const int length = snprintf(line, sizeof(line),
                                "%c RAW=%d,%d,%d,%d HID=%d,%d,%d,%d BTN=%lu\n",
                                JOYSTICK_TEST_MODE ? 'T' : 'J',
                                raw[0], raw[1], raw[2], raw[3],
                                reports[0], reports[1], reports[2], reports[3],
                                static_cast<unsigned long>(buttonMask));
    if (length > 0 && length < static_cast<int>(sizeof(line)) &&
        Serial.availableForWrite() >= length) {
      Serial.write(reinterpret_cast<const uint8_t *>(line), length);
    }
  }
}
