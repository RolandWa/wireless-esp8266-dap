#!/usr/bin/env python3
"""
Read/set VTarget voltage on the wireless-esp8266-dap firmware via raw USBIP-over-TCP.

WHY TCP AND NOT pyusb / the Windows USBIP kernel driver
--------------------------------------------------------
The Windows USBIP kernel driver (usbip.exe) correctly forwards OUT (write) URBs
to the firmware but does NOT forward IN (read) URBs.  Instead it returns stale
data from its enumeration-phase buffer (UTF-16-LE string descriptors) and then
zeros.  This means dev.read() via pyusb never actually reaches the ESP32.

This script speaks the USBIP stage-2 protocol directly over TCP port 3240,
so both the OUT (DAP command) and IN (DAP response) URBs are handled by the
firmware — no kernel driver involved.

COMMANDS
--------
Vendor1 (0x81) — Read VTarget:
    Request:  [0x81, <512-byte padding>]
    Response: [0x81, voltage_low, voltage_high]   (little-endian mV)
    Error:    response[1:3] == 0xFFFF → ADC not initialised

Vendor2 (0x82) — Set VTarget PWM (hardware TODO — circuit not yet complete):
    Request:  [0x82, voltage_low, voltage_high, <padding>]   (little-endian mV)
    Response: [0x82, status]
    Status:   0x00=OK  0x01=out of range (valid: 1250-5000 mV)  0xFF=not supported

USAGE
-----
    python read_vtarget_tcp.py [--ip <esp32-ip>] [--set <mV>]

    Default IP: 192.168.137.123  (set in wifi_configuration.h)
    --set <mV>: also send Vendor2 to set voltage (1250-5000)

DEPENDENCIES
------------
    Only Python standard library (socket, struct, argparse).
"""

import argparse
import socket
import struct
import sys

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_IP   = "192.168.137.123"
USBIP_PORT   = 3240
BUSID        = b"1-1\x00" + b"\x00" * 28      # 32 bytes, null-padded

CMD_DAP_VENDOR1 = 0x81   # Read VTarget voltage
CMD_DAP_VENDOR2 = 0x82   # Set VTarget voltage (PWM, hardware TODO)
DAP_PACKET_SIZE = 512    # firmware compiled with USE_WINUSB=1

# ---------------------------------------------------------------------------
# USBIP constants
# ---------------------------------------------------------------------------
USBIP_VERSION     = 0x0111
OP_REQ_IMPORT     = 0x8003
USBIP_DEVICE_SIZE = 312   # sizeof(usbip_usb_device) — consumed after attach

SUBMIT_CMD   = 0x00000001
RESPONSE_CMD = 0x00000003

# Header: cmd seqnum devid direction ep flags buf_len start_frame npackets interval setup(8)
URB_FMT = "!IIIIIIIIII8s"   # 48 bytes

DIR_OUT = 0
DIR_IN  = 1

SET_STATUS = {0x00: "OK", 0x01: "invalid range (1250-5000 mV)", 0xFF: "not supported on this target"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(f"Connection closed (wanted {n} bytes, received {len(buf)})")
        buf += chunk
    return buf


def attach(sock: socket.socket) -> None:
    """USBIP stage-1: send OP_REQ_IMPORT, receive OP_REP_IMPORT."""
    req = struct.pack("!HHI", USBIP_VERSION, OP_REQ_IMPORT, 0) + BUSID
    sock.sendall(req)
    hdr = _recv_exact(sock, 8)
    version, code, status = struct.unpack("!HHI", hdr)
    if status != 0:
        raise RuntimeError(f"OP_REP_IMPORT failed with status={status:#010x}")
    print(f"  Attached (version={version:#06x}, status=OK)")
    _recv_exact(sock, USBIP_DEVICE_SIZE)   # consume device info blob


def submit_urb(sock: socket.socket, seqnum: int, ep: int,
               direction: int, data: bytes = b"") -> bytes:
    """Send one USBIP CMD_SUBMIT and return the IN payload (empty for OUT)."""
    buf_len = len(data) if direction == DIR_OUT else DAP_PACKET_SIZE
    hdr = struct.pack(URB_FMT,
        SUBMIT_CMD, seqnum, 0, direction,
        ep & 0x0F,       # strip direction bit — separate field in USBIP
        0, buf_len, 0,
        0xFFFFFFFF,      # number_of_packets = -1 (bulk)
        0, b"\x00" * 8,
    )
    sock.sendall(hdr + data)

    resp = _recv_exact(sock, 48)
    (cmd, rseq, devid, rdir, rep, status,
     actual_length, *_rest) = struct.unpack(URB_FMT, resp)

    if cmd != RESPONSE_CMD:
        raise RuntimeError(f"Unexpected response cmd={cmd:#010x}")
    if status != 0:
        raise RuntimeError(f"URB status error={status:#010x}")

    if direction == DIR_IN and actual_length > 0:
        return _recv_exact(sock, actual_length)
    return b""


def dap_exchange(sock: socket.socket, seqnum_start: int, pkt: bytes) -> tuple:
    """Send one DAP command (OUT) and receive one DAP response (IN). Returns (response, next_seqnum)."""
    submit_urb(sock, seqnum_start, ep=0x01, direction=DIR_OUT, data=pkt)
    resp = submit_urb(sock, seqnum_start + 1, ep=0x81, direction=DIR_IN)
    return resp, seqnum_start + 2


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read/set VTarget on wireless-esp8266-dap over USBIP/TCP"
    )
    parser.add_argument("--ip", default=DEFAULT_IP,
                        help=f"ESP32 IP address (default: {DEFAULT_IP})")
    parser.add_argument("--set", type=int, metavar="MV",
                        help="Set VTarget voltage in mV (1250-5000) via Vendor2 command")
    args = parser.parse_args()

    print(f"Connecting to {args.ip}:{USBIP_PORT} ...")
    with socket.create_connection((args.ip, USBIP_PORT), timeout=10) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        print("Attaching via USBIP stage-1 ...")
        attach(sock)

        seqnum = 1

        # --- Vendor2: Set VTarget (optional) ---
        if args.set is not None:
            voltage_mv = args.set
            print(f"\nSending DAP_Vendor2 (0x{CMD_DAP_VENDOR2:02x}): set VTarget = {voltage_mv} mV ...")
            print("  NOTE: hardware circuit is TODO — software path only")
            pkt = bytearray(DAP_PACKET_SIZE)
            pkt[0] = CMD_DAP_VENDOR2
            pkt[1] = voltage_mv & 0xFF
            pkt[2] = (voltage_mv >> 8) & 0xFF
            resp, seqnum = dap_exchange(sock, seqnum, bytes(pkt))

            if len(resp) >= 2 and resp[0] == CMD_DAP_VENDOR2:
                st = resp[1]
                label = SET_STATUS.get(st, f"unknown (0x{st:02x})")
                print(f"  Status: 0x{st:02x} = {label}")
                if st not in (0x00, 0xFF):
                    return 1
            else:
                print(f"  ERROR: unexpected response {[hex(b) for b in resp[:4]]}")
                return 1

        # --- Vendor1: Read VTarget ---
        print(f"\nSending DAP_Vendor1 (0x{CMD_DAP_VENDOR1:02x}): read VTarget ...")
        pkt = bytearray(DAP_PACKET_SIZE)
        pkt[0] = CMD_DAP_VENDOR1
        resp, seqnum = dap_exchange(sock, seqnum, bytes(pkt))

        print(f"  Received {len(resp)} bytes: {[hex(b) for b in resp[:6]]}")

        if len(resp) < 3 or resp[0] != CMD_DAP_VENDOR1:
            print(f"  ERROR: unexpected response — first byte=0x{resp[0]:02x}, expected 0x{CMD_DAP_VENDOR1:02x}")
            return 1

        voltage_mv = resp[1] | (resp[2] << 8)
        if voltage_mv == 0xFFFF:
            print("  ERROR: firmware returned 0xFFFF — ADC not initialised")
            return 1

        print(f"\n=== VTarget = {voltage_mv} mV  ({voltage_mv / 1000:.3f} V) ===")
        return 0


if __name__ == "__main__":
    sys.exit(main())
