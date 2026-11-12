"""Read Windows joystick axes through WinMM; does not send input or change settings.

Use --test only while xiao_axis_test firmware is running. Standard library only.
API: https://learn.microsoft.com/en-us/windows/win32/api/joystickapi/
"""

import argparse
import ctypes as ct
import json
import sys
import time


class JoyCaps(ct.Structure):
    _fields_ = [
        ("wMid", ct.c_ushort), ("wPid", ct.c_ushort),
        ("szPname", ct.c_wchar * 32),
    ] + [(name, ct.c_uint) for name in (
        "wXmin wXmax wYmin wYmax wZmin wZmax wNumButtons wPeriodMin "
        "wPeriodMax wRmin wRmax wUmin wUmax wVmin wVmax wCaps wMaxAxes "
        "wNumAxes wMaxButtons"
    ).split()] + [
        ("szRegKey", ct.c_wchar * 32), ("szOEMVxD", ct.c_wchar * 260),
    ]


class JoyInfo(ct.Structure):
    _fields_ = [(name, ct.c_uint32) for name in (
        "dwSize dwFlags dwXpos dwYpos dwZpos dwRpos dwUpos dwVpos "
        "dwButtons dwButtonNumber dwPOV dwReserved1 dwReserved2"
    ).split()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=17)
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--buttons", action="store_true",
                        help="Require left, right, both pressed and released states.")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Run this on Windows.")

    winmm = ct.WinDLL("winmm")
    winmm.joyGetDevCapsW.argtypes = [ct.c_size_t, ct.POINTER(JoyCaps), ct.c_uint]
    winmm.joyGetDevCapsW.restype = ct.c_uint
    winmm.joyGetPosEx.argtypes = [ct.c_uint, ct.POINTER(JoyInfo)]
    winmm.joyGetPosEx.restype = ct.c_uint

    def position(identifier):
        state = JoyInfo()
        state.dwSize, state.dwFlags = ct.sizeof(state), 0xFF  # JOY_RETURNALL
        result = winmm.joyGetPosEx(identifier, ct.byref(state))
        if result:
            raise RuntimeError(f"joyGetPosEx({identifier}) returned {result}")
        return state

    devices = []
    for identifier in range(16):
        caps = JoyCaps()
        if winmm.joyGetDevCapsW(identifier, ct.byref(caps), ct.sizeof(caps)) == 0:
            try:
                position(identifier)
            except RuntimeError:
                continue
            devices.append((identifier, caps))
    print(json.dumps({"connected": [{"id": i, "name": c.szPname,
                                    "axes": c.wNumAxes, "buttons": c.wNumButtons}
                                   for i, c in devices]}), flush=True)
    if len(devices) != 1:
        raise RuntimeError("Disconnect other controllers; exactly one is required.")

    identifier, caps = devices[0]
    if caps.wNumAxes != 6:
        raise RuntimeError("Expected the six-axis XIAO descriptor; check device/access permissions.")
    labels = ("X", "Y", "Z", "R", "U", "V")
    fields = ("dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos", "dwVpos")
    minimum, maximum = [65535] * 6, [0] * 6
    active_seen, coupled_samples, samples = set(), 0, 0
    button_masks = set()
    button_changes = []
    start = time.monotonic()
    while time.monotonic() - start < args.seconds:
        state = position(identifier)
        mask = state.dwButtons
        button_masks.add(mask)
        if not button_changes or mask != button_changes[-1][1]:
            button_changes.append([round(time.monotonic() - start, 3), mask])
            if args.buttons:
                print(json.dumps({"button_mask": mask,
                                  "pressed": [i + 1 for i in range(32) if mask & (1 << i)]}),
                      flush=True)
        values = [getattr(state, field) for field in fields]
        for index, value in enumerate(values):
            minimum[index] = min(minimum[index], value)
            maximum[index] = max(maximum[index], value)
        active = [i for i, value in enumerate(values) if abs(value - 32767) > 4000]
        active_seen.update(active)
        coupled_samples += len(active) > 1
        samples += 1
        time.sleep(0.02)
    result = {"samples": samples, "ranges": dict(zip(labels, zip(minimum, maximum))),
              "active_axes": [labels[i] for i in sorted(active_seen)],
              "samples_with_multiple_displaced_axes": coupled_samples,
              "button_masks": sorted(button_masks), "button_changes": button_changes}
    print(json.dumps(result), flush=True)
    if args.test:
        moved = {i for i in range(6) if maximum[i] - minimum[i] > 50000}
        if moved != {0, 1, 2, 3} or coupled_samples or active_seen != moved:
            raise RuntimeError("Test sweep failed: expect only X/Y/Z/R moving one at a time.")
        print("PASS: four independent test axes; unused axes centered.")
    if args.buttons:
        if button_masks != {0, 1, 2, 3} or button_changes[-1][1] != 0:
            raise RuntimeError("Expect released, left-only, right-only, both, then released.")
        print("PASS: both USB buttons pressed independently/together and released.")


if __name__ == "__main__":
    main()
