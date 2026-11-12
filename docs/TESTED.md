# What has been verified

The reference build uses a Seeed Studio XIAO ESP32-S3, two Robocraze PS2-style
analog joystick modules powered at 3.3 V, a Windows laptop, and FPV SkyDive
installed through Steam. Hardware checks were performed on 12–13 November 2026.

| Check | Result | Evidence boundary |
| --- | --- | --- |
| Normal and automatic axis-test environments | Both compile locally | A build does not validate physical wiring |
| Native USB flashing | Successful; written flash hashes verified | Application and ROM COM ports can differ |
| Windows enumeration | XIAO_FPV_Joystick, HID + CDC | Generic HID, not Xbox/XInput |
| Four independent USB axes | Passed a 17-second automatic sweep | X/Y/Z/R moved one at a time; U/V remained centered |
| Physical stick travel | All four raw inputs reached 0 and 4095 | Measured on the reference modules |
| Released centers after calibration | All four HID values remained zero | Confirmed in serial output and Windows joystick API |
| Push switches | User confirmed operation in joy.cpl | All simultaneous-press combinations were not separately instrumented |
| SkyDive 2.9.2(b) detection | TinyUSB HID selected in game | Detection alone does not validate flight controls |
| In-game action mapping and flight | Not verified | Complete the game's calibration and button binding |

The automatic USB sweep collected 834 Windows samples: the four active axes
each covered 258–65275 in WinMM's scaled range. There were no samples with more
than one displaced axis, and the two unused axes remained at 32767.

The reference center measurements were `1857, 1884, 1914, 1905` in yaw,
throttle, roll, pitch order. They are the values currently in `src/main.cpp`.
Calibrate other modules instead of treating these as universal constants.

The GitHub Actions workflow compiles both environments and packages their
images. It does not connect to hardware, flash a board, or run the simulator.
Use the PlatformIO upload instructions to flash a complete build; the single
application binary is not a combined factory image.

Local raw captures and workstation-specific validation logs stay outside Git.
The portable measurement tools are included in `tools/` so the checks can be
repeated on another controller.
