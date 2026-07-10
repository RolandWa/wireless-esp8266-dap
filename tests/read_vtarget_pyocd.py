#!/usr/bin/env python3
"""
Read VTarget voltage via pyOCD vendor command over USBIP WiFi connection.

This script monkey-patches pyOCD to handle empty USB responses that occur
during the CMSIS-DAP initialization phase over USBIP (the firmware returns
a zero-length packet before the device warms up, causing IndexError in
unpatched pyOCD 0.44.1).

The actual vendor command for reading VTarget works correctly once the
device is open; only the initialization phase DAP_INFO queries are affected.

Usage:
    python read_vtarget_pyocd.py

Requirements:
    - ESP32-C3 XIAO running wireless-esp8266-dap firmware
    - USBIP device attached: usbip.exe attach -r 192.168.137.123 -b 1-1
    - WinUSB driver installed via Zadig for VID=0xC251 / PID=0xF00A
    - pyOCD 0.35+: pip install pyocd
"""

import sys
import time
import logging

# Optional: enable pyOCD debug logging
# logging.basicConfig(level=logging.DEBUG)

# --------------------------------------------------------------------------- #
#  Patch 1: cmsis_dap_core.dap_info — tolerate empty USB read responses       #
# --------------------------------------------------------------------------- #
def _patch_cmsis_dap_core():
    from pyocd.probe.pydapaccess.cmsis_dap_core import CMSISDAPProtocol, Command, INTEGER_INFOS
    from pyocd.probe.pydapaccess.dap_access_api import DAPAccessIntf

    original = CMSISDAPProtocol.dap_info

    def safe_dap_info(self, id_):
        """Patched dap_info: returns None on empty response instead of crashing."""
        cmd = [Command.DAP_INFO, id_.value]
        self.interface.write(cmd)
        resp = self.interface.read()
        if not resp:
            # Zero-length response from device (USBIP warm-up artefact); return None.
            return None
        if resp[0] != Command.DAP_INFO:
            raise DAPAccessIntf.DeviceError("expected DAP_INFO")
        resp_len = resp[1] if len(resp) > 1 else 0
        if id_ in INTEGER_INFOS:
            if resp_len == 1 and len(resp) > 2:
                return resp[2]
            elif resp_len == 2 and len(resp) > 3:
                return (resp[3] << 8) | resp[2]
            elif resp_len == 4 and len(resp) > 5:
                return (resp[5] << 24) | (resp[4] << 16) | (resp[3] << 8) | resp[2]
            else:
                return None  # malformed — caller will use default
        # String value
        if resp_len == 0:
            return None
        return resp[2:2 + resp_len].rstrip(b'\x00').decode('utf-8', errors='replace')

    CMSISDAPProtocol.dap_info = safe_dap_info
    return original


# --------------------------------------------------------------------------- #
#  Patch 2: dap_access_cmsis_dap.open — handle None from identify()           #
# --------------------------------------------------------------------------- #
def _patch_dap_access_open():
    import pyocd.probe.pydapaccess.dap_access_cmsis_dap as dac_mod

    original_open = dac_mod.DAPAccessCMSISDAP.open

    def safe_open(self):
        """Patched open: use safe defaults when DAP_INFO returns None."""
        if self._is_open:
            return

        self._interface.open()

        if self._has_opened_once:
            self._init_deferred_buffers()
            if self._has_swo_uart:
                self._swo_disable()
                self._swo_status = dac_mod.SWOStatus.DISABLED
            self._is_open = True
            return

        import pyocd.core.session as session_mod
        # Packet count
        try:
            limit = session_mod.Session.get_current().options['cmsis_dap.limit_packets']
        except Exception:
            limit = False
        if limit or dac_mod.DAPSettings.limit_packets:
            self._packet_count = 1
        else:
            pc = self.identify(self.ID.MAX_PACKET_COUNT)
            self._packet_count = pc if isinstance(pc, int) else 1
        print(f"  [patch] packet_count = {self._packet_count}")

        # Protocol version (already safe on None in _read_protocol_version)
        self._read_protocol_version()
        print(f"  [patch] cmsis_dap_version = {self._cmsis_dap_version}")

        # Packet size
        ps = self.identify(self.ID.MAX_PACKET_SIZE)
        self._packet_size = ps if isinstance(ps, int) else 64
        print(f"  [patch] packet_size = {self._packet_size}")

        self._interface.set_packet_count(self._packet_count)
        self._interface.set_packet_size(self._packet_size)

        # Capabilities
        from pyocd.probe.pydapaccess.cmsis_dap_core import Capabilities
        caps = self.identify(self.ID.CAPABILITIES)
        self._capabilities = caps if isinstance(caps, int) else 0
        print(f"  [patch] capabilities = {self._capabilities:#04x}")

        self._has_swo_uart = (self._capabilities & Capabilities.SWO_UART) != 0
        self._swo_status = dac_mod.SWOStatus.DISABLED

        self._init_deferred_buffers()
        self._has_opened_once = True
        self._is_open = True

    dac_mod.DAPAccessCMSISDAP.open = safe_open
    return original_open


# --------------------------------------------------------------------------- #
#  Main test                                                                   #
# --------------------------------------------------------------------------- #
def main():
    print("=" * 60)
    print("VTarget read via pyOCD vendor command")
    print("=" * 60)

    # Apply patches
    print("\n[*] Patching pyOCD to handle empty DAP_INFO responses...")
    _patch_cmsis_dap_core()
    _patch_dap_access_open()
    print("    Done.")

    # Import after patching
    from pyocd.probe.pydapaccess import DAPAccess
    import pyocd.core.session as session_mod

    # Find probe
    print("\n[*] Discovering probes...")
    try:
        with session_mod.Session(None) as sess:
            sess.open()
            probes = DAPAccess.get_connected_devices()
    except Exception as e:
        # get_connected_devices() needs a session context; try minimal approach
        try:
            probes = DAPAccess.get_connected_devices()
        except Exception as e2:
            print(f"    Error: {e2}")
            probes = []

    if not probes:
        print("    No probes found. Is USBIP attached?")
        print("    Run: usbip.exe attach -r 192.168.137.123 -b 1-1")
        return False

    for p in probes:
        print(f"    Probe: {p.product_name} | {p.vendor_name} | {p.get_unique_id()}")

    probe = probes[0]

    # Open probe — DAPAccess.get_connected_devices() returns DAPAccessCMSISDAP directly
    print(f"\n[*] Opening probe {probe.product_name}...")
    try:
        probe.open()
    except Exception as e:
        print(f"    Error opening: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("    Opened successfully!")

    # Read VTarget via vendor command
    # pyOCD vendor(index, data): index = offset from 0x80
    # vendor(1, []) → sends 0x81 → firmware Read VTarget
    # response: [LOW_BYTE, HIGH_BYTE, ...] (echo byte 0x81 stripped by pyOCD)
    print("\n[*] Reading VTarget (DAP_Vendor1 = 0x81)...")
    try:
        response = probe.vendor(1, [])
        print(f"    Raw response: {list(response)}")

        if len(response) >= 2:
            voltage_mv = response[0] | (response[1] << 8)
            voltage_v  = voltage_mv / 1000.0
            print(f"\n{'='*40}")
            print(f"  VTarget = {voltage_mv} mV  ({voltage_v:.3f} V)")
            print(f"{'='*40}")
            return True
        else:
            print(f"    Response too short ({len(response)} bytes)")
            return False

    except Exception as e:
        print(f"    vendor() error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        try:
            probe.close()
        except Exception:
            pass


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
