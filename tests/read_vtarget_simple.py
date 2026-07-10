#!/usr/bin/env python3
"""
DEPRECATED — use read_vtarget_tcp.py instead.

Root cause: the Windows USBIP kernel driver forwards OUT (write) URBs correctly
but does NOT forward IN (read) URBs to the firmware.  pyusb dev.read() returns
stale enumeration data (UTF-16-LE string descriptor cache) and then zeros.

read_vtarget_tcp.py bypasses the kernel driver entirely and speaks USBIP over
TCP directly, so both the command and response URBs actually reach the ESP32.

See docs/vtarget.md for the full analysis.
"""
import sys
import os

script = os.path.join(os.path.dirname(__file__), "read_vtarget_tcp.py")
print(f"This script is deprecated.  Running {script} instead.\n")
os.execv(sys.executable, [sys.executable, script] + sys.argv[1:])
