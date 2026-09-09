#!/usr/bin/env python3
"""
PWM sweep with simultaneous DAP ADC + VB-8034 DMM voltage measurement.
Sweeps GPIO3 PWM from 0% to 100% in 1% increments, reads VTarget via
Vendor1 and the VirtualBench DMM.

Usage:
    python tests/pwm_vtarget_dmm.py [--ip 192.168.137.123] [--vb VB8034-314E194]
"""

import argparse
import csv
from datetime import datetime
import socket
import struct
import sys
import time
from pathlib import Path

import pyvirtualbench as pvb

DEFAULT_IP = "192.168.137.123"
DEFAULT_VB = "VB8034-314E194"
USBIP_PORT = 3240
BUSID      = b"1-1\x00" + b"\x00" * 28
PKT_SIZE   = 512

USBIP_VER      = 0x0111
OP_REQ_IMPORT  = 0x8003
USBIP_DEV_SIZE = 312
SUBMIT_CMD     = 0x00000001
RESPONSE_CMD   = 0x00000003
URB_FMT        = "!IIIIIIIIII8s"
DIR_OUT, DIR_IN = 0, 1

MAX_DUTY = 1023

# Must mirror VTARGET_CAL_TABLE in main/vtarget_pwm.c so the recorded
# duty_count matches what the firmware actually drove for each mv.
FW_CAL_TABLE = [
    (358, 4200), (559, 4072), (612, 3943), (647, 3811), (678, 3650),
    (699, 3514), (716, 3385), (732, 3250), (747, 3110), (763, 2945),
    (775, 2813), (787, 2674), (797, 2552), (808, 2418), (819, 2281),
    (831, 2132), (841, 2010), (851, 1892), (862, 1772), (872, 1673),
    (883, 1575), (898, 1465), (912, 1397), (929, 1361), (982, 1326),
]

MIN_V_MV = FW_CAL_TABLE[-1][1]
MAX_V_MV = FW_CAL_TABLE[0][1]


def duty_pct_to_mv(pct):
    return int(round(MAX_V_MV - pct * (MAX_V_MV - MIN_V_MV) / 100.0))


def mv_to_fw_duty_count(voltage_mv):
    """Reproduce the firmware's mv -> PWM duty_cycle mapping (vtarget_set_voltage)."""
    if voltage_mv >= MAX_V_MV:
        return FW_CAL_TABLE[0][0]
    if voltage_mv <= MIN_V_MV:
        return FW_CAL_TABLE[-1][0]
    for (duty_lo, v_hi), (duty_hi, v_lo) in zip(FW_CAL_TABLE, FW_CAL_TABLE[1:]):
        if v_lo <= voltage_mv <= v_hi:
            return duty_lo + (duty_hi - duty_lo) * (v_hi - voltage_mv) // (v_hi - v_lo)
    return FW_CAL_TABLE[-1][0]


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c:
            raise ConnectionError(f"closed {len(buf)}/{n}")
        buf += c
    return buf


def attach(sock):
    sock.sendall(struct.pack("!HHI", USBIP_VER, OP_REQ_IMPORT, 0) + BUSID)
    _, _, status = struct.unpack("!HHI", recv_exact(sock, 8))
    if status != 0:
        raise RuntimeError(f"USBIP import failed: {status}")
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
        raise RuntimeError(f"URB error={st:#010x}")
    if direction == DIR_IN and actual > 0:
        return recv_exact(sock, actual)
    return b""


def dap_set(sock, seq, mv):
    pkt = bytearray(PKT_SIZE)
    pkt[0] = 0x82; pkt[1] = mv & 0xFF; pkt[2] = (mv >> 8) & 0xFF
    urb(sock, seq, 0x01, DIR_OUT, bytes(pkt))
    r = urb(sock, seq + 1, 0x81, DIR_IN)
    return (r[1] if len(r) > 1 else 0xFF), seq + 2


def dap_read_vtarget(sock, seq):
    pkt = bytearray(PKT_SIZE); pkt[0] = 0x81
    urb(sock, seq, 0x01, DIR_OUT, bytes(pkt))
    r = urb(sock, seq + 1, 0x81, DIR_IN)
    mv = (r[1] | (r[2] << 8)) if len(r) >= 3 else 0xFFFF
    return mv, seq + 2


def output_stem(board_id):
    return "vtarget_" + "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in board_id
    )


def save_plot(results, board_id):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("  Plot skipped: matplotlib is not installed")
        return

    output_dir = Path(__file__).resolve().parent / "test_results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{output_stem(board_id)}_curve.png"

    duty_percent = [result[0] for result in results]
    adc_voltage = [result[2] / 1000 for result in results]
    dmm_voltage = [result[3] / 1000 for result in results]

    plt.figure(figsize=(10, 6))
    plt.plot(duty_percent, dmm_voltage, "o-", markersize=3, label="VirtualBench DMM")
    plt.plot(duty_percent, adc_voltage, "o-", markersize=3, label="DAP ADC")
    plt.xlabel("Calibrated VTarget control (%)")
    plt.ylabel("VTarget voltage (V)")
    plt.title(f"VTarget Voltage vs Calibrated Control - {board_id}")
    plt.xlim(0, 100)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"  Graph saved to: {output_path}")


def save_csv(results, board_id, tolerance_pct):
    output_dir = Path(__file__).resolve().parent / "test_results"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{output_stem(board_id)}_measurements.csv"

    with output_path.open("w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([
            "board_id", "duty_percent", "commanded_mv", "duty_count", "adc_mv",
            "dmm_mv", "diff_mv", "error_pct", "result",
        ])
        for pct, mv, adc_mv, dmm_mv, diff in results:
            error_pct = (dmm_mv - mv) / mv * 100
            passed = abs(error_pct) <= tolerance_pct
            writer.writerow([
                board_id, pct, mv, mv_to_fw_duty_count(mv), adc_mv,
                f"{dmm_mv:.1f}", f"{diff:.1f}", f"{error_pct:.3f}",
                "PASS" if passed else "FAIL",
            ])
    print(f"  CSV saved to: {output_path}")
    return output_path


def append_summary(board_id, results, tolerance_pct):
    output_dir = Path(__file__).resolve().parent / "test_results"
    output_path = output_dir / "vtarget_production_summary.csv"
    error_percentages = [(result[3] - result[1]) / result[1] * 100 for result in results]
    failed_points = sum(abs(error_pct) > tolerance_pct for error_pct in error_percentages)
    dmm_values = [result[3] for result in results]
    adc_dmm_diffs = [abs(result[4]) for result in results]
    fieldnames = [
        "timestamp", "board_id", "points", "tolerance_pct", "failed_points",
        "worst_error_pct", "min_dmm_mv", "max_dmm_mv", "max_adc_dmm_diff_mv",
        "average_adc_dmm_diff_mv", "result",
    ]
    existing_rows = []
    if output_path.exists():
        with output_path.open(newline="") as csv_file:
            existing_rows = [row for row in csv.DictReader(csv_file) if row["board_id"] != board_id]

    summary_row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "board_id": board_id,
        "points": len(results),
        "tolerance_pct": f"{tolerance_pct:.2f}",
        "failed_points": failed_points,
        "worst_error_pct": f"{max(abs(error_pct) for error_pct in error_percentages):.3f}",
        "min_dmm_mv": f"{min(dmm_values):.1f}",
        "max_dmm_mv": f"{max(dmm_values):.1f}",
        "max_adc_dmm_diff_mv": f"{max(adc_dmm_diffs):.1f}",
        "average_adc_dmm_diff_mv": f"{sum(adc_dmm_diffs) / len(adc_dmm_diffs):.1f}",
        "result": "PASS" if failed_points == 0 else "FAIL",
    }
    existing_rows.append(summary_row)

    with output_path.open("w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(fieldnames)
        writer.writerows([[row[field] for field in fieldnames] for row in existing_rows])
    print(f"  Production summary saved to: {output_path}")
    return failed_points


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip",    default=DEFAULT_IP)
    ap.add_argument("--vb",    default=DEFAULT_VB)
    ap.add_argument("--settle", type=float, default=0.4,
                    help="Settle time after PWM change (s)")
    ap.add_argument("--board-id", required=True,
                    help="Unique identifier printed on the PCB under test")
    ap.add_argument("--tolerance-pct", type=float, default=5.0,
                    help="Maximum allowed DMM error percentage (default: 5.0)")
    args = ap.parse_args()

    steps = list(range(0, 101))

    print("PWM sweep + simultaneous DAP ADC & DMM measurement")
    print(f"  Device      : {args.ip}:{USBIP_PORT}")
    print(f"  VirtualBench: {args.vb}")
    print(f"  Board ID    : {args.board_id}")
    print(f"  Tolerance   : +/-{args.tolerance_pct:.1f}% DMM error")
    print(f"  Wiring      : VTarget output shorted to VTref (GPIO2 ADC)")
    print(f"  DMM probes  : V terminal on VTarget pad, COM on GND")
    print("  Sweep       : 0% to 100% calibrated VTarget range in 1% increments")
    print()

    vb_dev = pvb.PyVirtualBench(args.vb)
    dmm    = vb_dev.acquire_digital_multimeter()
    dmm.reset_instrument()
    dmm.configure_dc_voltage(pvb.DmmInputResistance.TEN_MEGA_OHM)

    with socket.create_connection((args.ip, USBIP_PORT), timeout=10) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        attach(sock)
        seq = 1

        hdr = (f"  {'Duty%':>6}  {'Set mV':>7}  {'ADC mV':>8}  {'DMM mV':>8}  {'Diff mV':>8}")
        sep = "  " + "-" * (len(hdr) - 2)
        print(hdr)
        print(sep)

        results = []
        for pct in steps:
            mv = duty_pct_to_mv(pct)

            st, seq = dap_set(sock, seq, mv)
            if st != 0x00:
                print(f"  {pct:>6}%  set failed ({st:#04x})")
                continue

            time.sleep(args.settle)

            adc_mv, seq = dap_read_vtarget(sock, seq)

            dmm_readings = [dmm.read() * 1000 for _ in range(5)]
            dmm_mv = sum(dmm_readings) / len(dmm_readings)

            diff = dmm_mv - adc_mv
            results.append((pct, mv, adc_mv, dmm_mv, diff))
            print(f"  {pct:>6}%  {mv:>7}  {adc_mv:>8.0f}  {dmm_mv:>8.1f}  {diff:>+8.1f}")

        print(sep)

        # Restore default
        dap_set(sock, seq, 3300)
        print(f"\n  Restored to 3300 mV default")

    dmm.release()
    vb_dev.release()

    # Summary
    if results:
        diffs = [abs(r[4]) for r in results]
        error_percentages = [(r[3] - r[1]) / r[1] * 100 for r in results]
        failed_points = sum(abs(error_pct) > args.tolerance_pct for error_pct in error_percentages)
        print(f"\n  ADC vs DMM: max diff {max(diffs):.0f} mV, avg diff {sum(diffs)/len(diffs):.0f} mV")
        dmm_vals = [r[3] for r in results]
        print(f"  DMM range : {min(dmm_vals):.0f} mV .. {max(dmm_vals):.0f} mV")
        print(f"  DMM tolerance: {len(results) - failed_points}/{len(results)} points passed")
        if max(dmm_vals) - min(dmm_vals) < 50:
            print("  NOTE: VTarget not responding to PWM - LDO fixed output or dropout")
        else:
            print("  PWM voltage control is working!")
        save_plot(results, args.board_id)
        save_csv(results, args.board_id, args.tolerance_pct)
        append_summary(args.board_id, results, args.tolerance_pct)
        return 0 if failed_points == 0 else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
