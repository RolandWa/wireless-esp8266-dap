#!/usr/bin/env python3
"""
PWM duty cycle sweep: 1% to 100% in 5% steps.
Sets duty via DAP Vendor2, measures actual waveform with VB-8034 mso/1.

Usage:
    python tests/sweep_pwm_vb.py [--ip 192.168.137.123] [--vb VB8034-314E194] [--probe 10]
"""

import argparse
import socket
import struct
import sys
import time
from ctypes import c_double, c_size_t, c_int32, byref

import pyvirtualbench as pvb
from pyvirtualbench.pyvirtualbench import Timestamp

DEFAULT_IP  = "192.168.137.123"
DEFAULT_VB  = "VB8034-314E194"
USBIP_PORT  = 3240
BUSID       = b"1-1\x00" + b"\x00" * 28
PKT_SIZE    = 512

USBIP_VER        = 0x0111
OP_REQ_IMPORT    = 0x8003
USBIP_DEV_SIZE   = 312
SUBMIT_CMD       = 0x00000001
RESPONSE_CMD     = 0x00000003
URB_FMT          = "!IIIIIIIIII8s"
DIR_OUT, DIR_IN  = 0, 1

# Firmware constants (must match vtarget_pwm.c)
MAX_DUTY = 1023
MIN_V_MV = 1250
MAX_V_MV = 5000

def duty_pct_to_mv(duty_pct):
    """Convert desired duty % to the mV setpoint Vendor2 expects."""
    duty_count = round(MAX_DUTY * duty_pct / 100.0)
    duty_count = max(0, min(MAX_DUTY, duty_count))
    if duty_count == 0:
        return MAX_V_MV
    if duty_count >= MAX_DUTY:
        return MIN_V_MV
    mv = round(MAX_V_MV - duty_count * (MAX_V_MV - MIN_V_MV) / MAX_DUTY)
    return int(mv)


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(f"closed {len(buf)}/{n}")
        buf += chunk
    return buf


def attach(sock):
    sock.sendall(struct.pack("!HHI", USBIP_VER, OP_REQ_IMPORT, 0) + BUSID)
    _, _, status = struct.unpack("!HHI", recv_exact(sock, 8))
    if status != 0:
        raise RuntimeError(f"USBIP import status={status}")
    recv_exact(sock, USBIP_DEV_SIZE)


def urb(sock, seq, ep, direction, data=b""):
    buf_len = len(data) if direction == DIR_OUT else PKT_SIZE
    sock.sendall(struct.pack(URB_FMT, SUBMIT_CMD, seq, 0, direction,
                             ep & 0x0F, 0, buf_len, 0, 0xFFFFFFFF, 0, b"\x00" * 8) + data)
    resp = recv_exact(sock, 48)
    cmd, _, _, _, _, st, actual, *_ = struct.unpack(URB_FMT, resp)
    if cmd != RESPONSE_CMD:
        raise RuntimeError(f"bad URB cmd={cmd:#010x}")
    if st != 0:
        raise RuntimeError(f"URB error status={st:#010x}")
    if direction == DIR_IN and actual > 0:
        return recv_exact(sock, actual)
    return b""


def dap_set_duty(sock, seq, mv):
    pkt = bytearray(PKT_SIZE)
    pkt[0] = 0x82; pkt[1] = mv & 0xFF; pkt[2] = (mv >> 8) & 0xFF
    urb(sock, seq,     0x01, DIR_OUT, bytes(pkt))
    r = urb(sock, seq+1, 0x81, DIR_IN)
    status = r[1] if len(r) > 1 else 0xFF
    return status, seq + 2


def capture(scope, probe_att, sample_rate=5_000_000, acq_time=0.004):
    """Stop, reconfigure, run, read. Returns (duty_pct, freq_hz, vmax, vmin)."""
    scope.stop()
    record = int(sample_rate * acq_time)

    scope.configure_timing(sample_rate, acq_time, 1e-9, pvb.MsoSamplingMode.SAMPLE)
    scope.configure_analog_channel(
        "mso/1", True, 5.0, 0.0, int(probe_att), pvb.MsoCoupling.DC,
    )
    scope.configure_immediate_trigger()
    scope.run(True)

    buf_size = record * 2
    raw = (c_double * buf_size)()
    ds_out = c_size_t(0); stride = c_size_t(0)
    t0 = Timestamp(0, 0, 0, 0); t1 = Timestamp(0, 0, 0, 0); tr = c_int32(0)

    st = scope.nilcicapi.niVB_MSO_ReadAnalog(
        scope.instrument_handle,
        byref(raw), c_size_t(buf_size),
        byref(ds_out), byref(stride),
        byref(t0), byref(t1), byref(tr),
    )
    if st != 0:
        raise RuntimeError(f"ReadAnalog failed: {st}")

    n    = ds_out.value
    data = list(raw[:n])

    vmax = max(data)
    vmin = min(data)
    pp   = vmax - vmin

    if pp < 0.05:
        # flat signal — determine if high or low
        mean = sum(data) / n
        return (100.0 if mean > 0.5 else 0.0), None, vmax, vmin

    threshold = vmin + pp * 0.5

    high_count = sum(1 for v in data if v > threshold)
    duty_pct   = high_count / n * 100.0

    # Period measurement: rising edges
    was_hi = data[0] > threshold
    rising = []
    dt_s   = acq_time / n  # approximate sample interval
    for i in range(1, n):
        is_hi = data[i] > threshold
        if is_hi and not was_hi:
            rising.append(i * dt_s)
        was_hi = is_hi

    if len(rising) >= 2:
        periods = [rising[i+1] - rising[i] for i in range(len(rising) - 1)]
        freq_hz = 1.0 / (sum(periods) / len(periods))
    else:
        freq_hz = None

    return duty_pct, freq_hz, vmax, vmin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip",    default=DEFAULT_IP)
    ap.add_argument("--vb",    default=DEFAULT_VB)
    ap.add_argument("--probe", type=float, default=10.0,
                    help="Probe attenuation factor (10 for 1:10 probe, 1 for direct)")
    ap.add_argument("--settle", type=float, default=0.15,
                    help="Settle time after PWM change (s)")
    args = ap.parse_args()

    steps = [1] + list(range(5, 101, 5))   # 1, 5, 10, 15, … 100

    print(f"GPIO3 (A1) PWM sweep: {steps[0]}% to {steps[-1]}% in 5% steps")
    print(f"  Device      : {args.ip}:{USBIP_PORT}")
    print(f"  VirtualBench: {args.vb}")
    print(f"  Probe       : 1:{int(args.probe)}")
    print()

    vb_dev = pvb.PyVirtualBench(args.vb)
    scope  = vb_dev.acquire_mixed_signal_oscilloscope()
    scope.reset_instrument()

    with socket.create_connection((args.ip, USBIP_PORT), timeout=10) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        attach(sock)
        seq = 1

        hdr = (f"  {'Target%':>8}  {'Set mV':>7}  {'Duty cnt':>8}  "
               f"{'Meas%':>6}  {'Freq Hz':>8}  {'Vmax':>6}  {'Vmin':>6}  {'pp':>5}")
        sep = "  " + "-" * (len(hdr) - 2)
        print(hdr)
        print(sep)

        results = []
        for target_pct in steps:
            mv         = duty_pct_to_mv(target_pct)
            duty_count = round(MAX_DUTY * target_pct / 100.0)

            st, seq = dap_set_duty(sock, seq, mv)
            if st not in (0x00,):
                print(f"  {target_pct:>8}  set failed (status={st:#04x})")
                continue

            time.sleep(args.settle)
            meas_duty, freq, vmax, vmin = capture(scope, args.probe)

            freq_s = f"{freq:8.1f}" if freq is not None else "    N/A "
            err    = meas_duty - target_pct

            results.append((target_pct, mv, duty_count, meas_duty, freq, vmax, vmin))
            print(f"  {target_pct:>8}  {mv:>7}  {duty_count:>8}  "
                  f"{meas_duty:>6.1f}  {freq_s}  {vmax:>6.3f}  {vmin:>6.3f}  "
                  f"{vmax-vmin:>5.3f}  (err {err:+.1f}%)")

        print(sep)

        # Restore 3300 mV default
        dap_set_duty(sock, seq, 3300)
        print(f"\n  Restored to 3300 mV (≈45% duty)")

    scope.release()
    vb_dev.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
