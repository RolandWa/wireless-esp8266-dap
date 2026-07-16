#!/usr/bin/env python3
"""
PWM signal characterization on GPIO3 (VTarget_PWM) using NI VB-8034 oscilloscope.

Sets PWM duty cycle via DAP Vendor2 command, captures waveform via VirtualBench
oscilloscope channel 1 (1:10 probe), measures frequency and duty cycle.

Usage:
    python tests/measure_pwm_vb.py [--ip 192.168.137.123] [--vb VB8034-314E194]
"""

import argparse
import socket
import struct
import sys
import time

import pyvirtualbench

DEFAULT_IP   = "192.168.137.123"
DEFAULT_VB   = "VB8034-314E194"
USBIP_PORT   = 3240
BUSID        = b"1-1\x00" + b"\x00" * 28
DAP_PACKET_SIZE = 512

CMD_SET_VTARGET = 0x82

USBIP_VERSION     = 0x0111
OP_REQ_IMPORT     = 0x8003
USBIP_DEVICE_SIZE = 312
SUBMIT_CMD        = 0x00000001
RESPONSE_CMD      = 0x00000003
URB_FMT           = "!IIIIIIIIII8s"
DIR_OUT, DIR_IN   = 0, 1

# Test points: (set_mv, expected_duty_pct, label)
# duty = 1023 * (5000 - mv) / (5000 - 1250)
TEST_POINTS = [
    (5000, 0.0,   "0% duty (max V)"),
    (3300, 45.3,  "~45% duty (3.3V)"),
    (2500, 66.7,  "~67% duty (2.5V)"),
    (1250, 100.0, "100% duty (min V)"),
]


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(f"Connection closed ({len(buf)}/{n} bytes)")
        buf += chunk
    return buf


def attach(sock):
    req = struct.pack("!HHI", USBIP_VERSION, OP_REQ_IMPORT, 0) + BUSID
    sock.sendall(req)
    hdr = _recv_exact(sock, 8)
    _, _, status = struct.unpack("!HHI", hdr)
    if status != 0:
        raise RuntimeError(f"OP_REP_IMPORT status={status:#010x}")
    _recv_exact(sock, USBIP_DEVICE_SIZE)


def submit_urb(sock, seqnum, ep, direction, data=b""):
    buf_len = len(data) if direction == DIR_OUT else DAP_PACKET_SIZE
    hdr = struct.pack(URB_FMT, SUBMIT_CMD, seqnum, 0, direction,
                      ep & 0x0F, 0, buf_len, 0, 0xFFFFFFFF, 0, b"\x00" * 8)
    sock.sendall(hdr + data)
    resp = _recv_exact(sock, 48)
    cmd, _, _, _, _, status, actual_length, *_ = struct.unpack(URB_FMT, resp)
    if cmd != RESPONSE_CMD:
        raise RuntimeError(f"Unexpected URB cmd={cmd:#010x}")
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
    if resp[1] == 0x01:
        raise ValueError(f"Voltage {voltage_mv} mV out of range")
    if resp[1] == 0xFF:
        raise RuntimeError("Vendor2 not supported on this firmware")
    return seqnum


def measure_pwm(scope, probe_attenuation=10):
    """Capture one acquisition and measure frequency + duty cycle."""
    import pyvirtualbench

    # 2 ms acquisition window → enough for 2+ periods at 1 kHz
    # configure_timing(sample_rate, acquisition_time, pretrigger_time, sampling_mode)
    sample_rate    = 5_000_000   # 5 MS/s → dt = 200 ns
    acq_time       = 0.002       # 2 ms → 10 000 samples
    record_length  = int(sample_rate * acq_time)

    scope.configure_timing(
        sample_rate, acq_time, 1e-9,
        pyvirtualbench.MsoSamplingMode.SAMPLE,
    )
    # vertical_range = full-scale volts (not an enum — raw float)
    # probe_attenuation = integer ratio (10 for 1:10 probe)
    scope.configure_analog_channel(
        "mso/1", True,
        5.0,           # 5 V full-scale (×probe = 50 V)
        0.0,           # offset
        int(probe_attenuation),
        pyvirtualbench.MsoCoupling.DC,
    )
    scope.configure_analog_edge_trigger(
        "mso/1", pyvirtualbench.Edge.RISING, 1.5, 0.1,
        pyvirtualbench.MsoTriggerInstance.A,
    )
    scope.run(True)  # autoTrigger=True

    # pyvirtualbench wrapper has a bug (data.value on c_double array).
    # Call the underlying C function directly.
    from ctypes import c_double, c_size_t, c_int32, byref
    from pyvirtualbench.pyvirtualbench import Timestamp

    # VB-8034 has 4 analog channels; data is interleaved when multiple are enabled.
    # We enable only mso/1, so buf_size = record_length.
    buf_size = record_length * 4  # extra headroom
    raw = (c_double * buf_size)()
    data_size_out = c_size_t(0)
    data_stride   = c_size_t(0)
    t0  = Timestamp(0, 0, 0, 0)
    t1  = Timestamp(0, 0, 0, 0)
    tr  = c_int32(0)

    status = scope.nilcicapi.niVB_MSO_ReadAnalog(
        scope.instrument_handle,
        byref(raw), c_size_t(buf_size),
        byref(data_size_out), byref(data_stride),
        byref(t0), byref(t1), byref(tr),
    )
    if status != 0:
        raise RuntimeError(f"niVB_MSO_ReadAnalog failed: {status}")

    n   = data_size_out.value
    dt  = data_stride.value * 1e-9  # stride is in nanoseconds for VB8034
    data = list(raw[:n])

    # Simple threshold crossing analysis
    threshold = 1.5  # volts (midpoint for 3.3V logic)
    high_count = sum(1 for v in data if v > threshold)
    low_count  = len(data) - high_count

    duty_pct = (high_count / len(data)) * 100.0

    # Find rising edges to measure period
    was_high = data[0] > threshold
    rising_edges = []
    for i in range(1, len(data)):
        is_high = data[i] > threshold
        if is_high and not was_high:
            rising_edges.append(i * dt)
        was_high = is_high

    if len(rising_edges) >= 2:
        periods = [rising_edges[i+1] - rising_edges[i] for i in range(len(rising_edges)-1)]
        avg_period = sum(periods) / len(periods)
        freq_hz = 1.0 / avg_period
    else:
        freq_hz = None

    v_max = max(data)
    v_min = min(data)

    return duty_pct, freq_hz, v_max, v_min, len(data)


def main():
    parser = argparse.ArgumentParser(description="PWM signal characterization via VB-8034")
    parser.add_argument("--ip",    default=DEFAULT_IP)
    parser.add_argument("--vb",    default=DEFAULT_VB, help="VirtualBench device name")
    parser.add_argument("--probe", type=float, default=10.0, help="Probe attenuation (default 10 for 1:10)")
    args = parser.parse_args()

    print(f"PWM characterization — GPIO3 (VTarget_PWM)")
    print(f"  DAP device : {args.ip}:{USBIP_PORT}")
    print(f"  VirtualBench: {args.vb}")
    print(f"  Probe       : 1:{int(args.probe)}")
    print(f"  Ch1 range   : 5V × {int(args.probe)} = {5*int(args.probe)}V full-scale")
    print()

    vb = pyvirtualbench.PyVirtualBench(args.vb)
    scope = vb.acquire_mixed_signal_oscilloscope()
    scope.reset_instrument()

    with socket.create_connection((args.ip, USBIP_PORT), timeout=10) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        attach(sock)
        seqnum = 1

        hdr = f"  {'Set (mV)':>9}  {'Exp duty%':>9}  {'Meas duty%':>10}  {'Freq (Hz)':>10}  {'Vmax':>6}  {'Vmin':>6}  Status"
        sep = "  " + "-" * (len(hdr) - 2)
        print(hdr)
        print(sep)

        results = []
        for mv, exp_duty, label in TEST_POINTS:
            seqnum = set_vtarget(sock, seqnum, mv)
            time.sleep(0.3)  # let PWM settle

            duty, freq, vmax, vmin, npts = measure_pwm(scope, args.probe)
            freq_str = f"{freq:.1f}" if freq is not None else "  N/A "

            duty_ok = abs(duty - exp_duty) < 5.0
            flag = "OK" if duty_ok else "!!"

            results.append((mv, exp_duty, duty, freq, vmax, vmin, duty_ok))
            print(f"  {mv:>9}  {exp_duty:>9.1f}  {duty:>10.1f}  {freq_str:>10}  {vmax:>6.3f}  {vmin:>6.3f}  {flag}  ({label})")

        print(sep)

        # Restore 3.3V
        seqnum = set_vtarget(sock, seqnum, 3300)
        print(f"\n  PWM restored to 3300 mV")

    scope.release()
    vb.release()

    passed = sum(1 for r in results if r[6])
    print(f"\n  {passed}/{len(results)} duty-cycle checks passed (±5%)")
    print()

    # Summary
    r0 = results[0]  # 0% duty
    r3 = results[-1]  # 100% duty
    if r0[2] < 5.0 and r3[2] > 95.0:
        print("  PASS — PWM signal confirmed on GPIO3, full duty range verified")
    elif any(r[3] is not None and 990 < r[3] < 1010 for r in results):
        print("  INFO — Frequency confirmed ~1 kHz; duty range may be limited by hardware")
    else:
        print("  WARN — Check probe connection to GPIO3")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
