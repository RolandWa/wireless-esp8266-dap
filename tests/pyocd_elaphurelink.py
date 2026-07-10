#!/usr/bin/env python3
"""
pyOCD probe plugin for wireless-esp8266-dap via elaphureLink TCP.

Implements the same interface as PyUSBv2 so it plugs directly into
pyOCD's DAPAccessCMSISDAP without any USB driver or USBIP.

Usage (standalone test):
    python tests/pyocd_elaphurelink.py [--ip 192.168.137.123] [--target max32672]

Usage (pyOCD API):
    from tests.pyocd_elaphurelink import make_probe
    probe = make_probe("192.168.137.123")
    probe.open()
    probe.connect(DebugProbe.Protocol.SWD)
    idcode = probe.read_dp(0)
    probe.disconnect()
    probe.close()
"""

import argparse
import logging
import queue
import socket
import struct
import threading

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("el-probe")

DEVICE_PORT = 3240
EL_MAGIC   = 0x8A656C70
EL_VERSION  = 0x00010000   # v1.0.0

DAP_PACKET_SIZE = 512


# ---------------------------------------------------------------------------
# elaphureLink TCP interface — drops in as a PyUSBv2 replacement
# ---------------------------------------------------------------------------

class _ElaphureLinkInterface:
    """CMSIS-DAP v2 (bulk) transport over elaphureLink TCP."""

    is_bulk      = True
    vid          = 0xC251
    pid          = 0xF00A
    vendor_name  = "windowsair"
    product_name = "CMSIS-DAP v2 (elaphureLink)"

    def __init__(self, host: str, port: int = DEVICE_PORT):
        self.host = host
        self.port = port
        self.serial_number = host          # unique ID = IP address
        self.packet_size   = DAP_PACKET_SIZE
        self.packet_count  = 1
        self.closed        = True
        self._sock: socket.socket | None = None
        # Internal read queue — keeps pyOCD's read() unblocking
        self._rx_queue: queue.SimpleQueue[bytes] = queue.SimpleQueue()
        self._rx_thread: threading.Thread | None = None
        self._rx_stop = threading.Event()

    # ---- lifecycle --------------------------------------------------------

    def open(self):
        sock = socket.create_connection((self.host, self.port), timeout=10)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # elaphureLink handshake
        sock.sendall(struct.pack("!III", EL_MAGIC, 0, EL_VERSION))
        resp = self._recv_exact(sock, 12)
        ident, _, ver = struct.unpack("!III", resp)
        if ident != EL_MAGIC:
            sock.close()
            raise RuntimeError(f"elaphureLink handshake bad magic {ident:#010x}")
        ver_str = f"{ver >> 16}.{(ver >> 8) & 0xFF}.{ver & 0xFF}"
        log.info("elaphureLink connected — device DAP %s @ %s:%d", ver_str, self.host, self.port)

        self._sock = sock
        self._rx_stop.clear()
        self._rx_thread = threading.Thread(target=self._rx_task, daemon=True,
                                           name="el-rx")
        self._rx_thread.start()
        self.closed = False

    def close(self):
        self.closed = True
        self._rx_stop.set()
        if self._sock:
            try: self._sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            self._sock.close()
            self._sock = None

    # ---- transport --------------------------------------------------------

    def write(self, data):
        """Send one CMSIS-DAP packet (OUT)."""
        raw = bytes(data)
        if log.isEnabledFor(logging.DEBUG):
            log.debug("TX> %s", raw[:16].hex(' '))
        self._sock.sendall(raw)

    def read(self, timeout: int = 1000) -> bytes:
        """Receive one CMSIS-DAP packet (IN). Blocks up to timeout ms."""
        try:
            data = self._rx_queue.get(timeout=timeout / 1000.0)
            if log.isEnabledFor(logging.DEBUG):
                log.debug("RX< %s", data[:16].hex(' '))
            return data
        except queue.Empty:
            return b""

    # ---- background receive thread ----------------------------------------

    def _rx_task(self):
        try:
            while not self._rx_stop.is_set():
                # Read up to packet_size bytes
                chunk = self._sock.recv(self.packet_size)
                if not chunk:
                    break
                self._rx_queue.put(chunk)
        except OSError:
            pass

    # ---- optional methods expected by some pyOCD paths --------------------

    def set_packet_count(self, count: int):
        self.packet_count = count

    def set_packet_size(self, size: int):
        self.packet_size = size

    def has_swo_ep(self) -> bool:
        return False

    def get_serial_number(self) -> str:
        return self.serial_number

    def get_packet_count(self) -> int:
        return self.packet_count

    def get_packet_size(self) -> int:
        return self.packet_size

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError(f"closed after {len(buf)}/{n} bytes")
            buf += chunk
        return buf


# ---------------------------------------------------------------------------
# Public helper: build a pyOCD probe from an elaphureLink TCP connection
# ---------------------------------------------------------------------------

def make_probe(host: str, port: int = DEVICE_PORT):
    """Return a CMSISDAPProbe connected over elaphureLink TCP.

    The probe is NOT yet open — call probe.open() then probe.connect().
    """
    from pyocd.probe.pydapaccess.dap_access_cmsis_dap import DAPAccessCMSISDAP
    from pyocd.probe.cmsis_dap_probe import CMSISDAPProbe

    iface = _ElaphureLinkInterface(host, port)
    dap   = DAPAccessCMSISDAP(unique_id=None, interface=iface)
    probe = CMSISDAPProbe(dap)
    return probe


# ---------------------------------------------------------------------------
# Standalone test / demo
# ---------------------------------------------------------------------------

def _run_test(host: str, target: str | None):
    from pyocd.probe.debug_probe import DebugProbe
    from pyocd.core.session import Session
    from pyocd.probe.pydapaccess.dap_access_cmsis_dap import DAPAccessCMSISDAP
    from pyocd.probe.pydapaccess.dap_access_api import DAPAccessIntf

    log.info("=== pyOCD elaphureLink probe test ===")
    log.info("Device: %s:%d", host, DEVICE_PORT)

    iface = _ElaphureLinkInterface(host)
    dap   = DAPAccessCMSISDAP(unique_id=None, interface=iface)

    try:
        # --- low-level DAP test (no Session needed) -----------------------
        dap.open()
        log.info("DAP opened  vendor='%s'  product='%s'", dap.vendor_name, dap.product_name)

        dap.connect(DAPAccessIntf.PORT.SWD)
        log.info("SWD port selected")

        # Read DPIDR (DP register at index 0)
        try:
            result = dap.read_reg(DAPAccessIntf.REG.DP_0x0)
            dap.flush()
            idcode = result()
            log.info("DPIDR = 0x%08X", idcode)
            designer = (idcode >> 1) & 0x7FF
            partno   = (idcode >> 12) & 0xFFFF
            version  = (idcode >> 28) & 0xF
            log.info("  Designer JEP106=0x%03X  Part=0x%04X  Version=%d", designer, partno, version)
        except DAPAccessIntf.TransferError:
            log.warning("DPIDR read: No ACK — no target MCU connected to DAP pins (normal if no target wired)")
            log.info("DAP probe itself is WORKING — connect SWD wires to your target to read IDCODE")

        # --- Session / target test (optional) -----------------------------
        if target:
            log.info("--- opening pyOCD session for target '%s' ---", target)
            dap.disconnect()
            dap.close()

            probe = make_probe(host)
            with Session(probe, target_override=target, auto_unlock=False) as session:
                session.open()
                t = session.target
                t.halt()
                pc = t.read_core_register("pc")
                log.info("Target halted  PC=0x%08X", pc)
        else:
            log.info("(pass --target <name> for full session, e.g. --target max32672)")

    finally:
        try: dap.disconnect()
        except Exception: pass
        try: dap.close()
        except Exception: pass
        log.info("=== done ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="pyOCD elaphureLink probe test")
    parser.add_argument("--ip", default="192.168.137.123")
    parser.add_argument("--target", default=None,
                        help="pyOCD target name, e.g. max32672 (optional)")
    args = parser.parse_args()
    _run_test(args.ip, args.target)
