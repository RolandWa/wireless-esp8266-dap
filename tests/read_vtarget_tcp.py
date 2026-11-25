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

Vendor2 (0x82) — Set VTarget PWM:
    Request:  [0x82, voltage_low, voltage_high, <padding>]   (little-endian mV)
    Response: [0x82, status]
    Status:   0x00=OK  0x01=out of range for the active calibration table
              (default table CLUSTER: 1326-4200 mV)  0xFF=not supported

Vendor3 (0x83) — VTarget info (range, last request, settling, calibration table):
    Request:  [0x83]
    Response: [0x83, flags, min_lo, min_hi, max_lo, max_hi, req_lo, req_hi,
               settle_ms_lo, settle_ms_hi, name_len, name...]
    flags:    bit0 = output settled, bit7 = not supported on this target

Vendor4 (0x84) — Select the calibration table (stored in NVS):
    Request:  [0x84, name_len, name...]     e.g. "PCB-05" or "CLUSTER"
    Response: [0x84, status]   0x00=OK  0x01=unknown board  0xFF=error

USAGE
-----
    python read_vtarget_tcp.py [--ip <esp32-ip>] [--set <mV>] [--info] [--board <name>]

    Default IP: 192.168.137.123  (set in wifi_configuration.h)
    --set <mV>:    also send Vendor2 to set voltage (range of the active table);
                   waits for the output to settle (Vendor3) before reading back
    --info:        print the Vendor3 info (table, range, settling)
    --board NAME:  select the calibration table first (CLUSTER, PCB-01 ... PCB-10)

DEPENDENCIES
------------
    Only Python standard library (socket, struct, argparse).
"""

import argparse
import socket
import struct
import sys
import time

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_IP   = "192.168.137.123"
USBIP_PORT   = 3240
BUSID        = b"1-1\x00" + b"\x00" * 28      # 32 bytes, null-padded

CMD_DAP_VENDOR1 = 0x81   # Read VTarget voltage
CMD_DAP_VENDOR2 = 0x82   # Set VTarget voltage (PWM)
CMD_DAP_VENDOR3 = 0x83   # VTarget info (range, settling, calibration table)
CMD_DAP_VENDOR4 = 0x84   # Select calibration table
DAP_PACKET_SIZE = 512    # firmware compiled with USE_WINUSB=1
BOARD_NAME_MAX  = 15     # firmware accepts names up to 15 characters

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

SET_STATUS = {0x00: "OK", 0x01: "invalid range for the active calibration table",
              0xFF: "not supported on this target"}
BOARD_STATUS = {0x00: "OK", 0x01: "unknown board", 0xFF: "error / not supported"}


# ---------------------------------------------------------------------------
# Vendor3 / Vendor4 message helpers (pure functions, unit-tested)
# ---------------------------------------------------------------------------
def decode_vtarget_info(resp: bytes) -> dict:
    """Decode a Vendor3 response ``[0x83, flags, min, max, req, settle_ms, name_len, name...]``.

    Raises ValueError for a malformed response or a target without VTarget
    control (flags bit7).
    """
    if len(resp) < 2 or resp[0] != CMD_DAP_VENDOR3:
        raise ValueError(f"not a Vendor3 response: {list(resp[:4])}")
    flags = resp[1]
    if flags & 0x80:
        raise ValueError("VTarget control not supported on this target")
    if len(resp) < 11:
        raise ValueError(f"Vendor3 response too short ({len(resp)} bytes) - old firmware?")
    name_len = resp[10]
    if len(resp) < 11 + name_len:
        raise ValueError(f"Vendor3 name truncated ({len(resp) - 11} of {name_len} bytes)")
    return {
        "settled": bool(flags & 0x01),
        "min_mv": resp[2] | (resp[3] << 8),
        "max_mv": resp[4] | (resp[5] << 8),
        "requested_mv": resp[6] | (resp[7] << 8),
        "settle_ms": resp[8] | (resp[9] << 8),
        "board": resp[11:11 + name_len].decode("ascii", errors="replace"),
    }


def build_set_board_request(name: str) -> bytes:
    """Vendor4 request ``[0x84, name_len, name...]`` padded to a DAP packet."""
    raw = name.encode("ascii")
    if not 1 <= len(raw) <= BOARD_NAME_MAX:
        raise ValueError(f"board name must be 1-{BOARD_NAME_MAX} ASCII characters: {name!r}")
    pkt = bytearray(DAP_PACKET_SIZE)
    pkt[0] = CMD_DAP_VENDOR4
    pkt[1] = len(raw)
    pkt[2:2 + len(raw)] = raw
    return bytes(pkt)


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
                        help="Set VTarget voltage in mV (range of the active table, "
                             "default 1326-4200) via Vendor2 command")
    parser.add_argument("--info", action="store_true",
                        help="Print VTarget info (calibration table, range, settling) via Vendor3")
    parser.add_argument("--board", metavar="NAME",
                        help="Select the calibration table first via Vendor4 "
                             "(CLUSTER, PCB-01 ... PCB-10); stored in NVS")
    args = parser.parse_args()

    print(f"Connecting to {args.ip}:{USBIP_PORT} ...")
    with socket.create_connection((args.ip, USBIP_PORT), timeout=10) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        print("Attaching via USBIP stage-1 ...")
        attach(sock)

        seqnum = 1

        def vtarget_info():
            """Vendor3 round trip; returns the decoded dict or None (old firmware)."""
            nonlocal seqnum
            pkt = bytearray(DAP_PACKET_SIZE)
            pkt[0] = CMD_DAP_VENDOR3
            resp, seqnum = dap_exchange(sock, seqnum, bytes(pkt))
            try:
                return decode_vtarget_info(resp)
            except ValueError as exc:
                print(f"  (Vendor3 info unavailable: {exc})")
                return None

        def print_info(info):
            print(f"  Calibration table : {info['board']}")
            print(f"  Range             : {info['min_mv']}-{info['max_mv']} mV")
            print(f"  Last request      : {info['requested_mv'] or '-'} mV")
            print(f"  Settled           : {'yes' if info['settled'] else 'no'}"
                  f" ({info['settle_ms']} ms to wait)")

        # --- Vendor4: Select calibration table (optional) ---
        if args.board is not None:
            print(f"\nSending DAP_Vendor4 (0x{CMD_DAP_VENDOR4:02x}): calibration table = {args.board} ...")
            resp, seqnum = dap_exchange(sock, seqnum, build_set_board_request(args.board))
            if len(resp) >= 2 and resp[0] == CMD_DAP_VENDOR4:
                st = resp[1]
                print(f"  Status: 0x{st:02x} = {BOARD_STATUS.get(st, 'unknown')}")
                if st != 0x00:
                    return 1
            else:
                print(f"  ERROR: unexpected response {[hex(b) for b in resp[:4]]}")
                return 1

        if args.info:
            print(f"\nSending DAP_Vendor3 (0x{CMD_DAP_VENDOR3:02x}): VTarget info ...")
            info = vtarget_info()
            if info:
                print_info(info)

        # --- Vendor2: Set VTarget (optional) ---
        if args.set is not None:
            voltage_mv = args.set
            print(f"\nSending DAP_Vendor2 (0x{CMD_DAP_VENDOR2:02x}): set VTarget = {voltage_mv} mV ...")
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

            # The output needs ~1 s to settle (gate filter tau ~145 ms): ask the
            # firmware how long, fall back to a fixed wait on old firmware.
            info = vtarget_info()
            wait_s = (info["settle_ms"] / 1000.0 + 0.05) if info else 1.0
            if wait_s > 0.05:
                print(f"  Waiting {wait_s:.2f} s for VTarget to settle ...")
                time.sleep(wait_s)

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
