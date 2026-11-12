"""Capture raw ADC diagnostics from a connected XIAO USB joystick."""

import argparse
import json
import re
import statistics
import time
from pathlib import Path

import serial
from serial.tools import list_ports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("centers", "travel", "verify"), required=True)
    parser.add_argument("--seconds", type=float, default=6)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", help="Select a port if several XIAO boards are connected.")
    parser.add_argument("--serial", help="Optionally restrict selection to a USB serial number.")
    args = parser.parse_args()
    requested_serial = (args.serial or "").replace(":", "").upper()
    ports = [p for p in list_ports.comports()
             if p.vid == 0x2886 and p.pid == 0x0056
             and (not args.port or p.device.casefold() == args.port.casefold())
             and (not requested_serial or
                  (p.serial_number or "").replace(":", "").upper() == requested_serial)]
    if len(ports) != 1:
        raise RuntimeError("Expected one XIAO application port; use --port or --serial to select it.")

    pattern = re.compile(r"J RAW=(\d+),(\d+),(\d+),(\d+) HID=(-?\d+),(-?\d+),(-?\d+),(-?\d+)(?: BTN=(\d+))?")
    raw_rows, hid_rows, button_rows = [], [], []
    with serial.Serial(ports[0].device, 115200, timeout=1) as port:
        # Re-establish CDC readiness without the ESP32 reboot line sequence.
        port.dtr = False
        port.rts = False
        time.sleep(0.1)
        port.dtr = True
        port.rts = True
        port.reset_input_buffer()
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            match = pattern.fullmatch(port.readline().decode(errors="replace").strip())
            if match:
                values = list(map(int, match.groups()[:8]))
                raw_rows.append(values[:4])
                hid_rows.append(values[4:])
                button_rows.append(int(match.group(9) or 0))
    if len(raw_rows) < max(4, int(args.seconds)):
        raise RuntimeError(f"Insufficient samples: {len(raw_rows)}. Close other serial monitors.")

    columns = list(zip(*raw_rows))
    hid_columns = list(zip(*hid_rows))
    result = {
        "phase": args.phase,
        "port": ports[0].device,
        "samples": len(raw_rows),
        "center": [round(statistics.median(c)) for c in columns],
        "minimum": [min(c) for c in columns],
        "maximum": [max(c) for c in columns],
        "hid_minimum": [min(c) for c in hid_columns],
        "hid_maximum": [max(c) for c in hid_columns],
        "button_masks": sorted(set(button_rows)),
        "raw": raw_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "raw"}, indent=2))


if __name__ == "__main__":
    main()
