#!/usr/bin/env python3
"""
VTarget PWM output linearity test.

Sets the PWM voltage via DAP Vendor2 (0x82), then reads back the actual
voltage via the VTref ADC (DAP Vendor1, 0x81).  VTref and VTarget must be
wired together for this test.

Uses the raw USBIP-over-TCP transport — no USB driver, no pyOCD required.

Usage:
    python tests/test_vtarget_pwm.py [--ip 192.168.137.123] [--settle 0.5]
"""

import argparse
import socket
import struct
import sys
import time

DEFAULT_IP   = "192.168.137.123"
USBIP_PORT   = 3240
BUSID        = b"1-1\x00" + b"\x00" * 28
DAP_PACKET_SIZE = 512

CMD_READ_VTARGET = 0x81
CMD_SET_VTARGET  = 0x82

USBIP_VERSION     = 0x0111
OP_REQ_IMPORT     = 0x8003
USBIP_DEVICE_SIZE = 312
SUBMIT_CMD        = 0x00000001
RESPONSE_CMD      = 0x00000003
URB_FMT           = "!IIIIIIIIII8s"
DIR_OUT, DIR_IN   = 0, 1

# Voltage sweep: 1.25 V to 5.0 V in steps; always include key embedded voltages
SWEEP_VOLTAGES_MV = [1250, 1800, 2500, 3000, 3300, 3600, 4096, 5000]

PASS_THRESHOLD_PCT = 5.0   # acceptable error vs set-point


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(f"Connection closed (got {len(buf)}/{n} bytes)")
        buf += chunk
    return buf


def attach(sock):
    req = struct.pack("!HHI", USBIP_VERSION, OP_REQ_IMPORT, 0) + BUSID
    sock.sendall(req)
    hdr = _recv_exact(sock, 8)
    version, code, status = struct.unpack("!HHI", hdr)
    if status != 0:
        raise RuntimeError(f"OP_REP_IMPORT status={status:#010x}")
    _recv_exact(sock, USBIP_DEVICE_SIZE)


def submit_urb(sock, seqnum, ep, direction, data=b""):
    buf_len = len(data) if direction == DIR_OUT else DAP_PACKET_SIZE
    hdr = struct.pack(URB_FMT, SUBMIT_CMD, seqnum, 0, direction,
                      ep & 0x0F, 0, buf_len, 0, 0xFFFFFFFF, 0, b"\x00" * 8)
    sock.sendall(hdr + data)
    resp = _recv_exact(sock, 48)
    cmd, rseq, devid, rdir, rep, status, actual_length, *_ = struct.unpack(URB_FMT, resp)
    if cmd != RESPONSE_CMD:
        raise RuntimeError(f"Unexpected URB response cmd={cmd:#010x}")
    if status != 0:
        raise RuntimeError(f"URB error status={status:#010x}")
    if direction == DIR_IN and actual_length > 0:
        return _recv_exact(sock, actual_length)
    return b""


def dap_exchange(sock, seqnum, pkt):
    submit_urb(sock, seqnum,     ep=0x01, direction=DIR_OUT, data=pkt)
    resp = submit_urb(sock, seqnum + 1, ep=0x81, direction=DIR_IN)
    return resp, seqnum + 2


def set_vtarget(sock, seqnum, voltage_mv):
    pkt = bytearray(DAP_PACKET_SIZE)
    pkt[0] = CMD_SET_VTARGET
    pkt[1] = voltage_mv & 0xFF
    pkt[2] = (voltage_mv >> 8) & 0xFF
    resp, seqnum = dap_exchange(sock, seqnum, bytes(pkt))
    if len(resp) < 2 or resp[0] != CMD_SET_VTARGET:
        raise RuntimeError(f"Bad set response: {[hex(b) for b in resp[:4]]}")
    status = resp[1]
    if status == 0x01:
        raise ValueError(f"Voltage {voltage_mv} mV out of range (1250-5000)")
    if status == 0xFF:
        raise RuntimeError("Set VTarget not supported on this firmware")
    return seqnum  # status 0x00 = OK


def read_vtarget(sock, seqnum, samples=5):
    readings = []
    for _ in range(samples):
        pkt = bytearray(DAP_PACKET_SIZE)
        pkt[0] = CMD_READ_VTARGET
        resp, seqnum = dap_exchange(sock, seqnum, bytes(pkt))
        if len(resp) < 3 or resp[0] != CMD_READ_VTARGET:
            raise RuntimeError(f"Bad read response: {[hex(b) for b in resp[:4]]}")
        mv = resp[1] | (resp[2] << 8)
        if mv == 0xFFFF:
            raise RuntimeError("ADC error (0xFFFF)")
        readings.append(mv)
        time.sleep(0.05)
    avg = sum(readings) / len(readings)
    return avg, seqnum


def main():
    parser = argparse.ArgumentParser(description="VTarget PWM sweep test")
    parser.add_argument("--ip",     default=DEFAULT_IP)
    parser.add_argument("--settle", type=float, default=0.5,
                        help="Settle time after PWM change (s, default 0.5)")
    parser.add_argument("--samples", type=int, default=5,
                        help="ADC reads per set-point (default 5)")
    args = parser.parse_args()

    print(f"VTarget PWM linearity test")
    print(f"  Device   : {args.ip}:{USBIP_PORT}")
    print(f"  Settle   : {args.settle} s per step")
    print(f"  Samples  : {args.samples} ADC reads per step")
    print(f"  Wiring   : VTref shorted to VTarget")
    print()

    with socket.create_connection((args.ip, USBIP_PORT), timeout=10) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        attach(sock)

        seqnum = 1
        results = []

        hdr = f"  {'Set (mV)':>9}  {'Actual (mV)':>11}  {'Error (mV)':>10}  {'Error (%)':>9}  Result"
        sep = "  " + "-" * (len(hdr) - 2)
        print(hdr)
        print(sep)

        for set_mv in SWEEP_VOLTAGES_MV:
            seqnum = set_vtarget(sock, seqnum, set_mv)
            time.sleep(args.settle)
            actual_mv, seqnum = read_vtarget(sock, seqnum, args.samples)
            error_mv  = actual_mv - set_mv
            error_pct = (error_mv / set_mv) * 100
            passed    = abs(error_pct) <= PASS_THRESHOLD_PCT
            results.append((set_mv, actual_mv, error_mv, error_pct, passed))
            flag = "PASS" if passed else "FAIL"
            print(f"  {set_mv:>9}  {actual_mv:>11.1f}  {error_mv:>+10.1f}  {error_pct:>+9.2f}%  {flag}")

        print(sep)

        passed_all = all(r[4] for r in results)
        n_pass = sum(1 for r in results if r[4])
        n_fail = len(results) - n_pass

        print(f"\n  {n_pass}/{len(results)} points passed (threshold ±{PASS_THRESHOLD_PCT}%)")

        # Return to 3.3 V default
        set_vtarget(sock, seqnum, 3300)
        print(f"  PWM restored to 3300 mV default")

    print()
    if passed_all:
        print("  PASS — PWM VTarget output is within spec across full range")
        return 0
    else:
        print(f"  FAIL — {n_fail} point(s) out of spec")
        return 1


if __name__ == "__main__":
    sys.exit(main())
