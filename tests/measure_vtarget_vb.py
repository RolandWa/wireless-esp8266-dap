#!/usr/bin/env python3
"""
Measure the VTarget output versus PWM duty cycle with an NI VirtualBench.

Channel 1 (mso/1) is connected to the VTarget output. The script sets the
corresponding VTarget control value through USBIP, acquires the Channel 1
waveform with the internal niVB_MSO_ReadAnalog API, and calculates average,
RMS, and peak-to-peak voltage for each duty-cycle point.

Usage:
    python tests/measure_vtarget_vb.py
    python tests/measure_vtarget_vb.py --step 5 --settle 0.5
    python tests/measure_vtarget_vb.py --ip 192.168.137.123 --vb VB8034-314E194
"""

import argparse
import csv
import math
import socket
import struct
import sys
import time
from ctypes import byref, c_double, c_int32, c_size_t
from pathlib import Path

import pyvirtualbench as pvb
from pyvirtualbench.pyvirtualbench import Timestamp

DEFAULT_IP = "192.168.137.123"
DEFAULT_VB = "VB8034-314E194"
USBIP_PORT = 3240
BUSID = b"1-1\x00" + b"\x00" * 28
PACKET_SIZE = 512

USBIP_VERSION = 0x0111
OP_REQ_IMPORT = 0x8003
USBIP_DEVICE_SIZE = 312
SUBMIT_CMD = 0x00000001
RESPONSE_CMD = 0x00000003
URB_FMT = "!IIIIIIIIII8s"
DIR_OUT, DIR_IN = 0, 1

CMD_SET_VTARGET = 0x82
MAX_DUTY = 1023
MIN_VOLTAGE_MV = 1250
MAX_VOLTAGE_MV = 5000


def duty_percent_to_voltage_mv(duty_percent):
    duty_count = round(MAX_DUTY * duty_percent / 100.0)
    duty_count = max(0, min(MAX_DUTY, duty_count))
    if duty_count == 0:
        return MAX_VOLTAGE_MV
    if duty_count >= MAX_DUTY:
        return MIN_VOLTAGE_MV
    return round(
        MAX_VOLTAGE_MV
        - duty_count * (MAX_VOLTAGE_MV - MIN_VOLTAGE_MV) / MAX_DUTY
    )


def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError(f"Connection closed ({len(data)}/{size} bytes)")
        data += chunk
    return data


def attach(sock):
    request = struct.pack("!HHI", USBIP_VERSION, OP_REQ_IMPORT, 0) + BUSID
    sock.sendall(request)
    _, _, status = struct.unpack("!HHI", recv_exact(sock, 8))
    if status != 0:
        raise RuntimeError(f"USBIP import failed: status={status:#010x}")
    recv_exact(sock, USBIP_DEVICE_SIZE)


def submit_urb(sock, sequence, endpoint, direction, data=b""):
    buffer_length = len(data) if direction == DIR_OUT else PACKET_SIZE
    header = struct.pack(
        URB_FMT,
        SUBMIT_CMD,
        sequence,
        0,
        direction,
        endpoint & 0x0F,
        0,
        buffer_length,
        0,
        0xFFFFFFFF,
        0,
        b"\x00" * 8,
    )
    sock.sendall(header + data)

    response = recv_exact(sock, 48)
    command, _, _, _, _, status, actual_length, *_ = struct.unpack(URB_FMT, response)
    if command != RESPONSE_CMD:
        raise RuntimeError(f"Unexpected USBIP response: {command:#010x}")
    if status != 0:
        raise RuntimeError(f"USBIP URB failed: status={status:#010x}")

    if direction == DIR_IN and actual_length > 0:
        return recv_exact(sock, actual_length)
    return b""


def dap_exchange(sock, sequence, packet):
    submit_urb(sock, sequence, 0x01, DIR_OUT, packet)
    response = submit_urb(sock, sequence + 1, 0x81, DIR_IN)
    return response, sequence + 2


def set_vtarget(sock, sequence, voltage_mv):
    packet = bytearray(PACKET_SIZE)
    packet[0] = CMD_SET_VTARGET
    packet[1] = voltage_mv & 0xFF
    packet[2] = (voltage_mv >> 8) & 0xFF
    response, sequence = dap_exchange(sock, sequence, bytes(packet))

    if len(response) < 2 or response[0] != CMD_SET_VTARGET:
        raise RuntimeError(f"Invalid VTarget response: {list(response[:4])}")
    if response[1] == 0x01:
        raise ValueError(f"VTarget voltage out of range: {voltage_mv} mV")
    if response[1] == 0xFF:
        raise RuntimeError("VTarget control is not supported by this firmware")
    return sequence


def capture_vtarget(scope, probe_attenuation, sample_rate, acquisition_time):
    record_length = int(sample_rate * acquisition_time)
    scope.stop()
    scope.configure_timing(
        sample_rate,
        acquisition_time,
        1e-9,
        pvb.MsoSamplingMode.SAMPLE,
    )
    scope.configure_analog_channel(
        "mso/1",
        True,
        5.0,
        0.0,
        int(probe_attenuation),
        pvb.MsoCoupling.DC,
    )
    scope.configure_immediate_trigger()
    scope.run(True)

    raw = (c_double * (record_length * 2))()
    data_size = c_size_t(0)
    data_stride = c_size_t(0)
    timestamp_start = Timestamp(0, 0, 0, 0)
    timestamp_end = Timestamp(0, 0, 0, 0)
    trigger_reference = c_int32(0)

    status = scope.nilcicapi.niVB_MSO_ReadAnalog(
        scope.instrument_handle,
        byref(raw),
        c_size_t(record_length * 2),
        byref(data_size),
        byref(data_stride),
        byref(timestamp_start),
        byref(timestamp_end),
        byref(trigger_reference),
    )
    if status != 0:
        raise RuntimeError(f"niVB_MSO_ReadAnalog failed: {status}")

    data = list(raw[:data_size.value])
    if not data:
        raise RuntimeError("VirtualBench returned no Channel 1 samples")

    mean_voltage = sum(data) / len(data)
    rms_voltage = math.sqrt(sum(sample * sample for sample in data) / len(data))
    peak_to_peak = max(data) - min(data)
    stride_ns = data_stride.value

    return {
        "samples": len(data),
        "sample_interval_ns": stride_ns,
        "average_v": mean_voltage,
        "rms_v": rms_voltage,
        "min_v": min(data),
        "max_v": max(data),
        "peak_to_peak_v": peak_to_peak,
    }


def save_results_csv(results, output_path):
    fields = [
        "duty_percent",
        "duty_count",
        "commanded_mv",
        "samples",
        "sample_interval_ns",
        "average_v",
        "rms_v",
        "min_v",
        "max_v",
        "peak_to_peak_v",
    ]
    with output_path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)


def save_plot(results, output_path):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Plot skipped: matplotlib is not installed")
        return

    duty = [row["duty_percent"] for row in results]
    average = [row["average_v"] for row in results]
    rms = [row["rms_v"] for row in results]
    peak_to_peak = [row["peak_to_peak_v"] for row in results]

    figure, axes = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    axes[0].plot(duty, average, "o-", markersize=3, label="Average VTarget")
    axes[0].set_ylabel("Average (V)")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(duty, rms, "o-", markersize=3, color="tab:orange", label="VTarget RMS")
    axes[1].set_ylabel("RMS (V)")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    axes[2].plot(
        duty,
        peak_to_peak,
        "o-",
        markersize=3,
        color="tab:green",
        label="VTarget peak-to-peak",
    )
    axes[2].set_xlabel("PWM duty cycle (%)")
    axes[2].set_ylabel("Peak-to-peak (V)")
    axes[2].set_xlim(0, 100)
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()

    figure.suptitle("VTarget Output vs PWM Duty Cycle")
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description="Measure VTarget with VirtualBench Channel 1")
    parser.add_argument("--ip", default=DEFAULT_IP, help="DAP device IP address")
    parser.add_argument("--vb", default=DEFAULT_VB, help="VirtualBench device name")
    parser.add_argument("--probe", type=float, default=10.0, help="Probe attenuation factor")
    parser.add_argument("--step", type=float, default=1.0, help="PWM step in percent")
    parser.add_argument("--settle", type=float, default=0.4, help="Settling time in seconds")
    parser.add_argument("--sample-rate", type=float, default=5_000_000, help="Sample rate")
    parser.add_argument("--acquisition-time", type=float, default=0.002, help="Acquisition time")
    args = parser.parse_args()

    if not 0 < args.step <= 100:
        parser.error("--step must be greater than 0 and no greater than 100")

    steps = []
    duty = 0.0
    while duty < 100.0:
        steps.append(round(duty, 6))
        duty += args.step
    steps.append(100.0)

    output_dir = Path(__file__).resolve().parent / "test_results"
    output_dir.mkdir(exist_ok=True)
    csv_path = output_dir / "vtarget_pwm_vb_measurements.csv"
    png_path = output_dir / "vtarget_pwm_vb_curve.png"

    print("VTarget VirtualBench Channel 1 measurement")
    print(f"  DAP device     : {args.ip}:{USBIP_PORT}")
    print(f"  VirtualBench   : {args.vb}")
    print(f"  PWM points     : {len(steps)} ({steps[0]:g}% to {steps[-1]:g}%)")
    print(f"  Probe          : 1:{int(args.probe)}")
    print("  Measurements   : average, RMS, peak-to-peak")
    print()

    vb = pvb.PyVirtualBench(args.vb)
    scope = vb.acquire_mixed_signal_oscilloscope()
    scope.reset_instrument()
    results = []
    sequence = 1

    try:
        with socket.create_connection((args.ip, USBIP_PORT), timeout=10) as sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            attach(sock)

            print(f"  {'Duty%':>7}  {'Command':>9}  {'Average':>9}  {'RMS':>9}  {'Pk-Pk':>9}")
            print("  " + "-" * 51)
            for duty_percent in steps:
                commanded_mv = duty_percent_to_voltage_mv(duty_percent)
                duty_count = round(MAX_DUTY * duty_percent / 100.0)
                sequence = set_vtarget(sock, sequence, commanded_mv)
                time.sleep(args.settle)

                measurement = capture_vtarget(
                    scope,
                    args.probe,
                    args.sample_rate,
                    args.acquisition_time,
                )
                row = {
                    "duty_percent": duty_percent,
                    "duty_count": duty_count,
                    "commanded_mv": commanded_mv,
                    **measurement,
                }
                results.append(row)
                print(
                    f"  {duty_percent:>6.1f}%  {commanded_mv:>7} mV  "
                    f"{measurement['average_v']:>8.4f} V  "
                    f"{measurement['rms_v']:>8.4f} V  "
                    f"{measurement['peak_to_peak_v']:>8.4f} V"
                )

            sequence = set_vtarget(sock, sequence, 3300)
            print("\n  VTarget restored to 3300 mV")
    finally:
        scope.release()
        vb.release()

    save_results_csv(results, csv_path)
    save_plot(results, png_path)
    print(f"  CSV saved to: {csv_path}")
    print(f"  PNG saved to: {png_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
