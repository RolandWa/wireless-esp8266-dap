#!/usr/bin/env python3
"""
CMSIS-DAP TCP bridge for wireless-esp8266-dap.

Allows the standard xPack OpenOCD (cmsis-dap backend tcp) to connect to this
device without the elaphureLink OpenOCD fork.

HOW IT WORKS
------------
The device speaks the elaphureLink protocol on TCP port 3240:
  - 12-byte binary handshake (magic + version exchange)
  - Then raw CMSIS-DAP commands/responses, no additional framing

OpenOCD's cmsis-dap-tcp backend expects:
  - A TCP server (default port 4441)
  - Raw CMSIS-DAP commands/responses, no framing

After the elaphureLink handshake the wire format is identical.
This bridge does the handshake once, then proxies bytes bidirectionally.

USAGE
-----
1. Start this bridge:
       python openocd/cmsis_dap_tcp_bridge.py [--device-ip 192.168.137.123]

2. In another terminal, run the main xPack OpenOCD:
       c:\\openocd\\bin\\openocd.exe -f openocd/cmsis-dap-tcp.cfg -f target/stm32f4x.cfg

   Where cmsis-dap-tcp.cfg contains:
       adapter driver cmsis-dap
       cmsis-dap backend tcp
       cmsis-dap tcp host 127.0.0.1
       cmsis-dap tcp port 4441

ALTERNATIVE (no bridge needed)
-------------------------------
Use the elaphureLink-patched OpenOCD directly:
    c:\\openocd\\elaphurelink\\bin\\openocd.exe -f openocd/elaphurelink.cfg -f target/stm32f4x.cfg
"""

import argparse
import select
import socket
import struct
import threading
import sys

DEVICE_PORT  = 3240
BRIDGE_PORT  = 4441
BRIDGE_HOST  = "127.0.0.1"

EL_LINK_IDENTIFIER   = 0x8a656c70
EL_COMMAND_HANDSHAKE = 0x00000000


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError(f"Connection closed (wanted {n} bytes, got {len(buf)})")
        buf += chunk
    return buf


def el_connect(device_ip):
    """Open TCP connection to device and complete elaphureLink handshake."""
    s = socket.create_connection((device_ip, DEVICE_PORT), timeout=10)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    # Send handshake: identifier(4BE) + command(4BE) + client_version(4BE)
    handshake = struct.pack("!III", EL_LINK_IDENTIFIER, EL_COMMAND_HANDSHAKE, 0x10000)
    s.sendall(handshake)

    # Receive response: identifier(4BE) + command(4BE) + dap_version(4BE)
    resp = recv_exact(s, 12)
    ident, cmd, ver = struct.unpack("!III", resp)
    if ident != EL_LINK_IDENTIFIER:
        raise RuntimeError(f"elaphureLink handshake failed: bad identifier {ident:#010x}")

    ver_str = f"{ver >> 16}.{(ver >> 8) & 0xFF}.{ver & 0xFF}"
    print(f"  [bridge] elaphureLink connected — device DAP version {ver_str}")
    return s


def proxy(a, b, label):
    """Forward data from socket a to socket b until one closes."""
    try:
        while True:
            data = a.recv(4096)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        try: a.shutdown(socket.SHUT_RD)
        except OSError: pass
        try: b.shutdown(socket.SHUT_WR)
        except OSError: pass


def handle_client(ocd_sock, device_ip):
    """Bridge one OpenOCD connection to the device."""
    peer = ocd_sock.getpeername()
    print(f"  [bridge] OpenOCD connected from {peer}")
    try:
        dev_sock = el_connect(device_ip)
    except Exception as e:
        print(f"  [bridge] Failed to connect to device: {e}")
        ocd_sock.close()
        return

    # Bidirectional proxy in two threads
    t1 = threading.Thread(target=proxy, args=(ocd_sock, dev_sock, "ocd→dev"), daemon=True)
    t2 = threading.Thread(target=proxy, args=(dev_sock, ocd_sock, "dev→ocd"), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    ocd_sock.close()
    dev_sock.close()
    print(f"  [bridge] Session ended ({peer})")


def main():
    parser = argparse.ArgumentParser(description="CMSIS-DAP TCP bridge for wireless-esp8266-dap")
    parser.add_argument("--device-ip", default="192.168.137.123",
                        help="ESP32 IP address (default: 192.168.137.123)")
    parser.add_argument("--port", type=int, default=BRIDGE_PORT,
                        help=f"Local port for OpenOCD to connect to (default: {BRIDGE_PORT})")
    args = parser.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((BRIDGE_HOST, args.port))
    server.listen(1)

    print(f"CMSIS-DAP TCP bridge")
    print(f"  Listening on {BRIDGE_HOST}:{args.port} (for OpenOCD cmsis-dap-tcp)")
    print(f"  Forwarding to {args.device_ip}:{DEVICE_PORT} (via elaphureLink)")
    print(f"")
    print(f"  OpenOCD config: adapter driver cmsis-dap")
    print(f"                  cmsis-dap backend tcp")
    print(f"                  cmsis-dap tcp host 127.0.0.1")
    print(f"                  cmsis-dap tcp port {args.port}")
    print(f"")
    print(f"  Press Ctrl+C to stop.")

    try:
        while True:
            ocd_sock, _ = server.accept()
            ocd_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            threading.Thread(
                target=handle_client,
                args=(ocd_sock, args.device_ip),
                daemon=True,
            ).start()
    except KeyboardInterrupt:
        print("\nBridge stopped.")
    finally:
        server.close()


if __name__ == "__main__":
    main()
