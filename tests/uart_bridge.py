#!/usr/bin/env python3
"""
UART TCP bridge client for wireless-esp8266-dap.

The firmware on the ESP32-C3 bridges TCP port 1234 ↔ UART1 (GPIO21 TX / GPIO20 RX).
This script connects to that bridge and lets you interact with whatever serial device
is wired to those pins (e.g. the UART of a MAX32672, SWO trace output, etc.).

Usage:
    # Interactive terminal (reads keyboard, prints received bytes)
    python tests/uart_bridge.py

    # Loopback test at one baud rate (GPIO20 shorted to GPIO21)
    python tests/uart_bridge.py --loopback --baud 115200

    # Sweep all standard baud rates (9600 … 115200)
    python tests/uart_bridge.py --loopback --all-bauds

    # Non-interactive: send a string and print the response
    python tests/uart_bridge.py --send "AT" --timeout 1.0

    # Log all received bytes to a file
    python tests/uart_bridge.py --log uart_log.txt

Enable in firmware first:
    wifi_configuration.h:  USE_UART_BRIDGE  1
                            UART_BRIDGE_PORT 1234
"""

import argparse
import socket
import sys
import threading
import time

DEFAULT_IP   = "192.168.137.123"
DEFAULT_PORT = 1234
DEFAULT_BAUD = 115200

# Standard COM port baud rates supported by the DAP / Windows
SUPPORTED_BAUDS = [9600, 14400, 19200, 28800, 38400, 56000, 57600, 115200]


def _recv_thread(sock: socket.socket, log_file, stop_event: threading.Event):
    """Background thread: print bytes received from the bridge."""
    try:
        while not stop_event.is_set():
            sock.settimeout(0.2)
            try:
                data = sock.recv(512)
            except socket.timeout:
                continue
            if not data:
                print("\r[bridge] Connection closed by device.")
                stop_event.set()
                break
            text = data.decode(errors="replace")
            sys.stdout.write(text)
            sys.stdout.flush()
            if log_file:
                log_file.write(text)
                log_file.flush()
    except OSError:
        pass


def _set_baud(sock: socket.socket, baud: int):
    """Send the baud-rate string as the first packet (firmware protocol)."""
    sock.sendall(f"{baud}".encode())
    time.sleep(0.15)   # give firmware time to reconfigure UART


def connect(ip: str = DEFAULT_IP, port: int = DEFAULT_PORT,
            baud: int = DEFAULT_BAUD) -> socket.socket:
    """Open a TCP connection to the UART bridge and negotiate baud rate."""
    sock = socket.create_connection((ip, port), timeout=10)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    _set_baud(sock, baud)
    return sock


def send_and_receive(ip: str = DEFAULT_IP, port: int = DEFAULT_PORT,
                     baud: int = DEFAULT_BAUD, message: str = "",
                     timeout: float = 1.0) -> str:
    """Send a string, collect responses for `timeout` seconds, return them."""
    with connect(ip, port, baud) as sock:
        if message:
            sock.sendall(message.encode())
        deadline = time.monotonic() + timeout
        chunks = []
        sock.settimeout(0.1)
        while time.monotonic() < deadline:
            try:
                data = sock.recv(512)
                if data:
                    chunks.append(data.decode(errors="replace"))
            except socket.timeout:
                pass
        return "".join(chunks)


def interactive(ip: str, port: int, baud: int, log_path: str | None):
    """Run an interactive terminal session over the UART bridge."""
    print(f"Connecting to {ip}:{port} (baud {baud}) ...")
    sock = connect(ip, port, baud)
    print(f"Connected. Press Ctrl+C to quit.\n{'─'*50}")

    log_file = open(log_path, "a", encoding="utf-8") if log_path else None
    stop = threading.Event()

    rx = threading.Thread(target=_recv_thread, args=(sock, log_file, stop),
                          daemon=True)
    rx.start()

    try:
        while not stop.is_set():
            try:
                line = input()
                sock.sendall((line + "\r\n").encode())
            except EOFError:
                break
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        sock.close()
        if log_file:
            log_file.close()
        print("\n[bridge] Disconnected.")


def _loopback_one(ip: str, port: int, baud: int) -> tuple[int, int]:
    """
    Run loopback test at a single baud rate.
    Opens a fresh TCP connection (required — firmware sets baud from first packet).
    Returns (passed, failed) counts.
    """
    # Scale timeout inversely with baud rate so slow rates have time to transmit
    # 9600 baud: ~10 ms per byte → 32-byte payload ~= 33 ms + WiFi ~= 200 ms safe
    byte_time_ms = 10_000 / baud          # ms per byte at this rate
    PAYLOAD = b"DAP-UART-loopback-test!\r\n"
    timeout = max(2.0, (len(PAYLOAD) * byte_time_ms / 1000) * 4 + 0.5)

    TESTS = [
        PAYLOAD,
        b"0123456789\r\n",
        b"\xAA\x55\xAA\x55\r\n",
    ]

    sock = connect(ip, port, baud)
    sock.settimeout(timeout)

    passed = failed = 0
    for payload in TESTS:
        sock.sendall(payload)
        received = b""
        deadline = time.monotonic() + timeout
        try:
            while len(received) < len(payload) and time.monotonic() < deadline:
                chunk = sock.recv(len(payload) - len(received))
                if not chunk:
                    break
                received += chunk
        except socket.timeout:
            pass

        if received == payload:
            passed += 1
        else:
            failed += 1
            label = payload.rstrip().decode(errors="replace")
            print(f"      FAIL '{label}'")
            print(f"           sent:     {payload.hex(' ')}")
            print(f"           received: {received.hex(' ')}")

    sock.close()
    return passed, failed


def loopback_test(ip: str, port: int, baud: int, all_bauds: bool):
    """
    TX→RX loopback test.
    With --all-bauds: opens a fresh connection for each rate in SUPPORTED_BAUDS.
    Without: tests the single baud rate given by --baud.
    """
    bauds = SUPPORTED_BAUDS if all_bauds else [baud]

    print("UART loopback test")
    print(f"  Device : {ip}:{port}")
    print(f"  Wiring : GPIO20 (D7/RX) shorted to GPIO21 (D6/TX)")
    print(f"  Rates  : {bauds}\n")
    print(f"  {'Baud':>8}   {'Tests':>5}   Result")
    print(f"  {'─'*8}   {'─'*5}   {'─'*30}")

    total_pass = total_fail = 0
    results = []

    for b in bauds:
        try:
            p, f = _loopback_one(ip, port, b)
        except Exception as e:
            print(f"  {b:>8}     —    error: {e}")
            results.append((b, 0, 1))
            total_fail += 1
            continue

        status = "PASS" if f == 0 else f"FAIL ({f} errors)"
        print(f"  {b:>8}   {p+f:>5}   {status}")
        total_pass += p
        total_fail += f
        results.append((b, p, f))

        # Brief pause between connections so firmware TCP stack settles
        if all_bauds and b != bauds[-1]:
            time.sleep(0.3)

    print(f"\n{'─'*50}")
    print(f"Total: {total_pass} passed, {total_fail} failed")
    if total_fail == 0:
        print("All baud rates OK — UART bridge loopback verified")
    else:
        failed_bauds = [b for b, _, f in results if f > 0]
        print(f"Failed at: {failed_bauds}")
        print("Check: GPIO20 (D7/RX) shorted to GPIO21 (D6/TX) ?")


def stress_test(ip: str, port: int, baud: int, duration_s: int):
    """
    Continuous loopback stress test for `duration_s` seconds at a single baud rate.
    Sends sequential 32-byte packets and verifies every echo.
    Reports bytes transferred, packet count, error count, and throughput.
    """
    import os

    PACKET_SIZE = 32
    byte_time_ms = 10_000 / baud
    pkt_timeout = max(2.0, (PACKET_SIZE * byte_time_ms / 1000) * 6 + 0.5)

    print(f"UART bridge stress test")
    print(f"  Device   : {ip}:{port}")
    print(f"  Baud     : {baud}")
    print(f"  Duration : {duration_s} s")
    print(f"  Wiring   : GPIO20 (D7/RX) shorted to GPIO21 (D6/TX)")
    print(f"  Pkt size : {PACKET_SIZE} bytes\n")

    sock = connect(ip, port, baud)
    sock.settimeout(pkt_timeout)

    total_sent = 0
    total_recv = 0
    total_pkts = 0
    errors      = 0
    reconnects  = 0
    seq         = 0
    t_start     = time.monotonic()
    t_report    = t_start + 5.0
    t_end       = t_start + duration_s

    def _make_packet(n: int) -> bytes:
        # 4-byte little-endian sequence number + pseudorandom fill + \r\n
        header = n.to_bytes(4, "little")
        body   = bytes((n * 6364136223846793005 + i) & 0xFF for i in range(PACKET_SIZE - 6))
        return header + body + b"\r\n"

    print(f"  {'Elapsed':>8}  {'Pkts':>8}  {'Errors':>6}  {'KB sent':>8}  {'Kbps':>8}")
    print(f"  {'─'*8}  {'─'*8}  {'─'*6}  {'─'*8}  {'─'*8}")

    while time.monotonic() < t_end:
        payload = _make_packet(seq)
        seq += 1

        try:
            sock.sendall(payload)
            total_sent += len(payload)

            received = b""
            deadline = time.monotonic() + pkt_timeout
            while len(received) < len(payload) and time.monotonic() < deadline:
                chunk = sock.recv(len(payload) - len(received))
                if not chunk:
                    raise OSError("connection closed")
                received += chunk

            total_recv += len(received)
            total_pkts += 1

            if received != payload:
                errors += 1

        except (OSError, socket.timeout):
            errors += 1
            sock.close()
            time.sleep(0.5)
            try:
                sock = connect(ip, port, baud)
                sock.settimeout(pkt_timeout)
                reconnects += 1
            except OSError as e:
                print(f"\n  [!] Reconnect failed: {e}")
                break

        now = time.monotonic()
        if now >= t_report:
            elapsed = now - t_start
            kbps = (total_sent * 8) / elapsed / 1000
            print(f"  {elapsed:>7.1f}s  {total_pkts:>8}  {errors:>6}  {total_sent/1024:>7.1f}K  {kbps:>7.1f}")
            t_report = now + 5.0

    sock.close()
    elapsed = time.monotonic() - t_start
    kbps    = (total_sent * 8) / elapsed / 1000 if elapsed > 0 else 0

    print(f"\n{'─'*60}")
    print(f"Stress test complete")
    print(f"  Duration   : {elapsed:.1f} s")
    print(f"  Packets    : {total_pkts}")
    print(f"  Bytes sent : {total_sent:,}")
    print(f"  Bytes recv : {total_recv:,}")
    print(f"  Errors     : {errors}")
    print(f"  Reconnects : {reconnects}")
    print(f"  Throughput : {kbps:.1f} kbps")
    if errors == 0:
        print(f"\n  PASS — no errors in {elapsed:.0f} s")
    else:
        error_rate = errors / total_pkts * 100 if total_pkts else 0
        print(f"\n  FAIL — {errors} errors ({error_rate:.2f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="UART bridge client for wireless-esp8266-dap")
    parser.add_argument("--ip",   default=DEFAULT_IP)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD,
                        choices=SUPPORTED_BAUDS + [DEFAULT_BAUD],
                        metavar=f"{{{','.join(str(b) for b in SUPPORTED_BAUDS)}}}",
                        help="UART baud rate (default: 115200)")
    parser.add_argument("--loopback", action="store_true",
                        help="Run TX→RX loopback test (GPIO20 shorted to GPIO21)")
    parser.add_argument("--all-bauds", action="store_true",
                        help="Sweep all supported baud rates in loopback test")
    parser.add_argument("--stress", action="store_true",
                        help="Run continuous loopback stress test")
    parser.add_argument("--duration", type=int, default=600,
                        help="Stress test duration in seconds (default: 600 = 10 min)")
    parser.add_argument("--send", default=None,
                        help="Send this string then print received bytes (non-interactive)")
    parser.add_argument("--timeout", type=float, default=1.0,
                        help="Receive timeout for --send mode (default: 1.0 s)")
    parser.add_argument("--log", default=None,
                        help="Append all received text to this file")
    args = parser.parse_args()

    if args.stress:
        stress_test(args.ip, args.port, args.baud, args.duration)
    elif args.loopback:
        loopback_test(args.ip, args.port, args.baud, args.all_bauds)
    elif args.send is not None:
        response = send_and_receive(args.ip, args.port, args.baud,
                                    args.send, args.timeout)
        print(response, end="")
    else:
        interactive(args.ip, args.port, args.baud, args.log)


if __name__ == "__main__":
    main()
