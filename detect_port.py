"""Print the COM port of the first connected ESP32-C3 device (VID 0x303A)."""
import serial.tools.list_ports
import sys

ports = [p for p in serial.tools.list_ports.comports() if p.vid == 0x303A]
if not ports:
    sys.exit(1)
ports.sort(key=lambda p: p.device)
print(ports[-1].device)
