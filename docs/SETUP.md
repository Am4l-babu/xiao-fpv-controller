# XIAO ESP32-S3 USB joystick for FPV SkyDive

Four independent analog inputs become a native Windows USB HID gamepad.
Physical joystick mode is the default. No Bluetooth, vJoy, serial-to-joystick
bridge, or third-party HID library is needed.

## Wiring (disconnect USB while wiring)

Power **both 3.3 V analog joystick modules from 3V3**, never from 5V.
All grounds must be connected. Use a USB data cable from the XIAO to the laptop.

The reference build uses the [Robocraze PS2 joystick module](https://robocraze.com/products/joystick-module).
Its [product photo](https://robocraze.com/cdn/shop/products/2_2__2_9f905b50-596d-49f7-93bd-ee58c749ab38_1000x.jpg?v=1743775747) labels the five pins
`GND, +5V, VRx, VRy, SW`. Treat **+5V as the module supply input** and connect
it to XIAO **3V3**, not XIAO 5V. Robocraze specifies 5 V operation and describes
two approximately 10 kOhm potentiometers; the 3.3 V recommendation here is based
on that passive divider design, not an explicit 3.3 V rating in the listing.
Supplying the dividers with 3.3 V limits VRx/VRy to that supply voltage.

The [official Seeed front pinout](https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/img/XIAO_ESP32-S3_front_pinout.png) confirms:
with the component side facing you and USB-C at the top, the first four pads
down the left are D0/GPIO1, D1/GPIO2, D2/GPIO3, D3/GPIO4. The first three down
the right are 5V/VBUS, GND, 3V3. Follow pin labels if viewing the board underside.

| Module connection | XIAO pin label | ESP32-S3 GPIO | USB axis / flight control |
| --- | --- | --- | --- |
| Left VCC / + | 3V3 | power | Module power |
| Left GND / - | GND | ground | Common ground |
| Left VRx (horizontal) | D0 / A0 | 1 | X / yaw |
| Left VRy (vertical) | D1 / A1 | 2 | Y / throttle |
| Right VCC / + | 3V3 | power | Module power |
| Right GND / - | GND | ground | Common ground |
| Right VRx (horizontal) | D2 / A2 | 3 | Z / roll |
| Right VRy (vertical) | D3 / A3 | 4 | Rz (Z rotation) / pitch |
| Left SW (push switch) | D4 | 5 | USB Button 1 |
| Right SW (push switch) | D5 | 6 | USB Button 2 |

Module labeling/orientation can vary; swap VRx/VRy connections if necessary.
SW closes to the module's GND. The firmware enables internal pull-ups and
requires a stable input for 20 ms before changing either USB button. Both
momentary buttons work independently, including simultaneous presses. The
firmware sends button levels, not keyboard keys or an arm/disarm toggle.
Inputs must stay between GND and 3.3 V. GPIO19/20 are used internally by USB;
do not use them for joystick signals. Unwired analog pins float, so movement in
physical mode without wiring is not evidence of a working joystick.

## Verified configuration

- PlatformIO Core on this laptop: 6.2.0, installed by the VS Code extension.
- Pinned official platform: `platformio/espressif32@7.0.1`.
- Board ID: `seeed_xiao_esp32s3` (8 MB flash, `qio_opi` memory configuration).
- Pinned Arduino package: `3.20017.241212` (installed metadata includes
  `+sha.dcc1105b`); its `esp_arduino_version.h` confirms **Arduino-ESP32 2.0.17**.
- Pinned esptool package: `2.41100.0`, which runs **esptool 4.11.0**.
- Remove the board's `ARDUINO_USB_MODE=1`; define `ARDUINO_USB_MODE=0`
  for USB-OTG/TinyUSB and `ARDUINO_USB_CDC_ON_BOOT=1` for composite HID + CDC.
  The installed S3 SDK already enables TinyUSB, CDC and HID; no fake
  `CONFIG_TINYUSB_*` overrides or separate TinyUSB library are required.
- Espressif's built-in `USBHIDGamepad` supports
  `send(x, y, z, rz, rx, ry, hat, buttons)`. This project sends X/Y/Z/Rz
  together every 8 ms, each in -127..127. Rx/Ry remain centered, the hat is
  neutral. Buttons 1/2 follow the two SW inputs; buttons 3–32 remain released.
  Windows may show these extra unused
  controls because they are part of the official descriptor. This is generic
  HID, not an Xbox/XInput device.
- Upload is `esptool` over the native USB COM port, not UF2 or USB DFU.
  `board_upload.use_1200bps_touch = true` and
  `board_upload.wait_for_upload_port = true` let PlatformIO reset the
  application and find the new bootloader port automatically. This was
  verified on this laptop: COM16 (application) became COM3 (ROM uploader).
  The application uses the variant's Seeed USB identity, 2886:0056; ROM boot
  mode can appear as Espressif 303A:1001. A ROM USB ID alone does not prove the
  board model. Always identify the port by unplug/reconnect before flashing.

## Build and upload in VS Code

Open this folder, install/enable PlatformIO IDE, then use **PlatformIO: New
Terminal** from the Command Palette. Run:

```powershell
pio --version
pio device list
pio run -e xiao_joystick
pio run -e xiao_axis_test
# Replace COMx with the positively identified current XIAO port:
pio run -e xiao_joystick -t upload --upload-port COMx
```

If `pio` is missing in a normal PowerShell terminal, use the installed executable:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" device list
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run -e xiao_joystick -t upload --upload-port COMx
```

For the GUI: click the **PlatformIO alien icon → PROJECT TASKS →
xiao_joystick → General → Build**, then **Upload**. Alternatively select
`xiao_joystick` in the bottom environment selector and click the bottom status
bar **right-arrow Upload** button. Close Serial Monitor before uploading. If
several compatible boards are connected, specify the port with the command
above (or a local `upload_port` setting) instead of relying on autodetection.

Successful upload should identify ESP32-S3, write and verify the flash data,
reset, and finish with `[SUCCESS]`. The application COM number may change.

### If upload cannot connect or the port disappears

1. Close serial monitors and the simulator. Use a known data-capable cable.
2. Unplug USB. Hold the XIAO **BOOT** button, reconnect USB while holding it,
   then release BOOT. Alternatively, while connected, hold BOOT, press and
   release RESET, then release BOOT.
3. Run `pio device list` again. Use the **new bootloader COM port**, which
   may differ from the application port; do not assume it is still COM3.
4. Retry `pio run -e xiao_joystick -t upload --upload-port COMx`.
   If serial transfer is unstable, try `--upload-port COMx` with
   `upload_speed = 115200` in `platformio.ini`.
5. Press RESET once after a successful flash if it remains in boot mode.

## Calibration and direction

Edit only the `axes[]` table near the top of `src/main.cpp`. Each row contains
`{pin, minimum, center, maximum, deadzone, inverted}` in 12-bit ADC counts.
Change `inverted` to `true` for any reversed direction. Center is explicit;
the firmware does not silently recalibrate at startup with a displaced stick.

For measurements, open `pio device monitor -p COMx -b 115200`. Every 500 ms it
prints `J RAW=yaw,throttle,roll,pitch HID=... BTN=...` (`T` in test mode).
`BTN` is a bitmask: 0 = released, 1 = left, 2 = right, 3 = both.
Record each axis's stable lower endpoint, released center, and upper endpoint;
enter those as minimum/center/maximum, rebuild and re-upload. ADC saturation
near the supply rail is possible. Small center deadzones and smoothing reduce
jitter; throttle has no center deadzone by default. Diagnostics are skipped
if the serial host is not ready, so a paused monitor cannot stall USB axes.

Throttle uses its entire stick travel: minimum is one endpoint and maximum the
other. A spring-centered module rests near **half throttle**, not zero. Configure
the game accordingly and hold the low-throttle endpoint when arming. The
firmware does not turn throttle into a cumulative/integrating control.

## Windows check and optional wiring-free test

1. Press **Win+R**, enter `joy.cpl`, and press Enter.
2. Select **XIAO_FPV_Joystick** (Windows can instead show a generic gamepad
   name), then **Properties → Test**.
3. Move left horizontal only: X changes. Left vertical only: Y changes.
   Right horizontal only: Z changes. Right vertical only: Z rotation changes.
   X/Y often share a crosshair; Z and Z rotation appear as bars. Other reported
   axes should stay centered. Left stick push lights Button 1; right stick
   push lights Button 2; releasing each turns its indicator off. Both can light
   together. Other buttons and POV should stay inactive.
4. Check full travel, centers and independence. Optional **Settings →
   Calibrate** in this dialog can apply Windows calibration; it does not
   replace the simulator's mapping/calibration.

To check HID without wiring, explicitly flash the separate test environment:

```powershell
pio run -e xiao_axis_test -t upload --upload-port COMx
```

Watch Test for at least 16 seconds. X, Y, Z, then Z rotation each get one
4-second slot and move center → positive → negative → center, with the
other axes centered. This proves USB reports only, not physical wiring.
**Do not calibrate or fly using the automatic test movement.** Restore normal
firmware afterward (simply changing VS Code's selected environment is not enough):

```powershell
pio device list
pio run -e xiao_joystick -t upload --upload-port COMx
```

## FPV SkyDive through Steam

The installed **2.9.2(b)** was observed detecting the device as **TinyUSB HID**,
while Windows Game Controllers called it **XIAO_FPV_Joystick**. Open
**Settings (gear) → Controls → Choose Input → TinyUSB HID**, then
**Input Calibration → Configure**. This immediately starts a rotate-sticks
prompt; perform it only with normal firmware and the joysticks wired.
Connect the controller before starting the game. Depending on the game version,
the entry may instead be called
**Joystick Calibration → Start Joystick Calibration** in the main menu.
If asked for controller type, use **Gamepad** for this two-stick HID device.
Select a mode/profile with left yaw/throttle and right roll/pitch (Mode 2).

Follow each prompt using only the requested axis, move every axis through its
full travel, set centers/endpoints and invert any reversed channels. Check the
live channel bars: left horizontal = yaw, left vertical = throttle, right
horizontal = roll, right vertical = pitch. Select the XIAO explicitly if a
different input is active. Set arm/reset/flight-mode actions to keyboard keys
in the game, or bind USB Buttons 1/2 if the game accepts them. Suggested mapping:
left press = arm/disarm, right press = reset. Actual in-game button binding must
be checked; the firmware does not emulate keyboard keys. The older official FAQ lists
P = arm/disarm, R = reset, F = flight mode; check the current bindings. Arming
requires low throttle.

If Windows Test works but the game ignores it: exit the game, open **Steam
Library → right-click FPV SkyDive → Properties → Controller → Override for
FPV SkyDive → Disable Steam Input**, then relaunch and reselect/recalibrate the
XIAO. Disconnect other controllers and temporarily disable virtual gamepad
software if the wrong input remains selected. Menu wording can vary by build.
Success means both the calibration bars and the drone respond to the intended
four channels; a connected icon alone is not proof of correct mapping.

## Official references

- [Seeed pinout, power and ROM BOOT/reset instructions](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)
- [Exact joystick listing, description and product pin-label photo](https://robocraze.com/products/joystick-module)
- [PlatformIO board documentation and upload protocols](https://docs.platformio.org/en/stable/boards/espressif32/seeed_xiao_esp32s3.html)
- [Exact platform 7.0.1 manifest](https://github.com/platformio/platform-espressif32/blob/v7.0.1/platform.json)
- [Exact XIAO board definition at 7.0.1](https://github.com/platformio/platform-espressif32/blob/v7.0.1/boards/seeed_xiao_esp32s3.json)
- [Version-matched upload reset and new-port handling](https://github.com/platformio/platform-espressif32/blob/v7.0.1/builder/main.py)
- [PlatformIO Core 6.2.0 serial-port switching implementation](https://github.com/platformio/platformio-core/blob/v6.2.0/platformio/builder/tools/pioupload.py)
- [7.0.1 release: Arduino 2.0.17 support](https://github.com/platformio/platform-espressif32/releases/tag/v7.0.1)
- [Espressif Arduino 2.0.17 USB Gamepad example](https://github.com/espressif/arduino-esp32/blob/2.0.17/libraries/USB/examples/Gamepad/Gamepad.ino)
- [Version-matched HID API](https://github.com/espressif/arduino-esp32/blob/2.0.17/libraries/USB/src/USBHIDGamepad.h)
- [Version-matched XIAO pin constants](https://github.com/espressif/arduino-esp32/blob/2.0.17/variants/XIAO_ESP32S3/pins_arduino.h)
- [Orqa calibration instructions](https://orqafpv.freshdesk.com/support/solutions/articles/48001249756-calibration)
- [Orqa calibration FAQ, hosted by Steam (older menu screenshots)](https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1278060/manuals/FPV.SkyDive_Calibration_FAQ__4_2022_.pdf?t=1735561536)

See [TESTED.md](TESTED.md) for the hardware checks and their limits. Local raw
captures, workstation details and build/upload logs are excluded from Git.
