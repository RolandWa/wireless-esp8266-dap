#!/usr/bin/env python3
"""
XIAO ESP32-C3 Hardware Test - USB Interface
Tests DAP functionality over USB connection
"""

import sys
import time
import struct
from typing import Optional, Tuple

try:
    from pyocd.core.helpers import ConnectHelper
    from pyocd.core.target import Target
    from pyocd.probe.pydapaccess import DAPAccess
except ImportError:
    print("Error: pyOCD not installed. Install with: pip install pyocd")
    sys.exit(1)


class XiaoUSBTest:
    """Test suite for XIAO ESP32-C3 DAP over USB"""
    
    def __init__(self):
        self.probe = None
        self.session = None
        self.passed_tests = 0
        self.failed_tests = 0
        
    def log_test(self, name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"[{status}] {name}")
        if message:
            print(f"    {message}")
        
        if passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1
    
    def connect_usb(self) -> bool:
        """Test USB connection to XIAO module"""
        print("\n=== USB Connection Test ===")
        
        try:
            # Get all connected probes
            probes = ConnectHelper.get_all_connected_probes()
            
            if not probes:
                self.log_test("USB Device Detection", False, "No USB DAP probes found")
                return False
            
            self.log_test("USB Device Detection", True, f"Found {len(probes)} probe(s)")
            
            # Display probe information
            for i, probe in enumerate(probes):
                print(f"    Probe {i}: {probe.product_name} - {probe.unique_id}")
            
            # Connect to first probe
            self.probe = probes[0]
            self.probe.open()
            
            self.log_test("USB Probe Open", True, f"Connected to {self.probe.product_name}")
            
            return True
            
        except Exception as e:
            self.log_test("USB Connection", False, f"Error: {str(e)}")
            return False
    
    def test_dap_info(self) -> bool:
        """Test DAP information retrieval"""
        print("\n=== DAP Information Test ===")
        
        if not self.probe:
            self.log_test("DAP Info", False, "No probe connected")
            return False
        
        try:
            # Get vendor name
            vendor = self.probe.vendor_name
            product = self.probe.product_name
            serial = self.probe.unique_id
            
            self.log_test("Vendor Name", True, vendor)
            self.log_test("Product Name", True, product)
            self.log_test("Serial Number", True, serial)
            
            return True
            
        except Exception as e:
            self.log_test("DAP Info", False, f"Error: {str(e)}")
            return False
    
    def test_vtarget_read(self) -> Optional[float]:
        """Test VTarget voltage reading (Command 0x81)"""
        print("\n=== VTarget Reading Test ===")
        
        if not self.probe:
            self.log_test("VTarget Read", False, "No probe connected")
            return None
        
        try:
            # Send vendor command 0x81 (Read VTarget)
            response = self.probe.vendor(0x81, [])
            
            if len(response) >= 2:
                # Parse voltage (little-endian, mV)
                voltage_mv = response[0] | (response[1] << 8)
                voltage_v = voltage_mv / 1000.0
                
                # Check if voltage is in reasonable range (0.5V - 6.0V)
                if 0.5 <= voltage_v <= 6.0:
                    self.log_test("VTarget Read", True, f"{voltage_mv} mV ({voltage_v:.3f} V)")
                    return voltage_v
                else:
                    self.log_test("VTarget Read", False, f"Out of range: {voltage_v:.3f} V")
                    return None
            else:
                self.log_test("VTarget Read", False, "Invalid response length")
                return None
                
        except AttributeError:
            self.log_test("VTarget Read", False, "Vendor command not supported by pyOCD version")
            print("    Note: Try using pyOCD 0.35.0 or newer")
            return None
        except Exception as e:
            self.log_test("VTarget Read", False, f"Error: {str(e)}")
            return None
    
    def test_vtarget_set(self, voltage_mv: int) -> bool:
        """Test VTarget voltage setting (Command 0x82)"""
        print(f"\n=== VTarget Set Test ({voltage_mv} mV) ===")
        
        if not self.probe:
            self.log_test("VTarget Set", False, "No probe connected")
            return False
        
        try:
            # Validate range
            if not (1250 <= voltage_mv <= 5000):
                self.log_test("VTarget Set", False, f"Invalid range: {voltage_mv} mV (must be 1250-5000)")
                return False
            
            # Send vendor command 0x82 (Set VTarget)
            low_byte = voltage_mv & 0xFF
            high_byte = (voltage_mv >> 8) & 0xFF
            
            response = self.probe.vendor(0x82, [low_byte, high_byte])
            
            if len(response) >= 1:
                status = response[0]
                
                if status == 0x00:
                    self.log_test("VTarget Set", True, f"Voltage set to {voltage_mv} mV")
                    
                    # Wait for settling
                    time.sleep(0.1)
                    
                    # Read back voltage
                    actual_v = self.test_vtarget_read()
                    if actual_v:
                        expected_v = voltage_mv / 1000.0
                        error_percent = abs(actual_v - expected_v) / expected_v * 100
                        
                        if error_percent < 5.0:  # Within 5%
                            self.log_test("VTarget Readback", True, 
                                        f"Error: {error_percent:.2f}% (within spec)")
                        else:
                            self.log_test("VTarget Readback", False,
                                        f"Error: {error_percent:.2f}% (expected <5%)")
                    
                    return True
                elif status == 0x01:
                    self.log_test("VTarget Set", False, "Invalid voltage range")
                    return False
                else:
                    self.log_test("VTarget Set", False, f"Command failed (status: 0x{status:02X})")
                    return False
            else:
                self.log_test("VTarget Set", False, "Invalid response length")
                return False
                
        except AttributeError:
            self.log_test("VTarget Set", False, "Vendor command not supported")
            return False
        except Exception as e:
            self.log_test("VTarget Set", False, f"Error: {str(e)}")
            return False
    
    def test_swd_connection(self) -> bool:
        """Test SWD connection (requires target connected)"""
        print("\n=== SWD Connection Test ===")
        print("Note: This test requires a target MCU connected to the debug port")
        print("      Connect VTarget to VTref for loopback test")
        
        if not self.probe:
            self.log_test("SWD Connection", False, "No probe connected")
            return False
        
        try:
            # Try to create a session (will fail if no target)
            self.session = ConnectHelper.session_with_chosen_probe(
                blocking=False,
                return_first=True,
                unique_id=self.probe.unique_id
            )
            
            if self.session:
                self.session.open()
                target = self.session.target
                
                if target:
                    self.log_test("SWD Connection", True, f"Target: {target.part_number}")
                    
                    # Try to read IDCODE
                    try:
                        idcode = target.read_dp_register(0)  # DP IDCODE
                        self.log_test("IDCODE Read", True, f"0x{idcode:08X}")
                    except:
                        self.log_test("IDCODE Read", False, "Could not read IDCODE")
                    
                    self.session.close()
                    return True
                else:
                    self.log_test("SWD Connection", False, "No target detected")
                    return False
            else:
                self.log_test("SWD Connection", False, "Could not create session")
                return False
                
        except Exception as e:
            self.log_test("SWD Connection", False, f"Error: {str(e)}")
            return False
    
    def disconnect(self):
        """Close connections"""
        if self.session:
            self.session.close()
        if self.probe:
            self.probe.close()
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 60)
        print("XIAO ESP32-C3 Hardware Test Suite - USB Interface")
        print("=" * 60)
        
        # Test 1: USB Connection
        if not self.connect_usb():
            print("\n❌ Cannot proceed without USB connection")
            return False
        
        # Test 2: DAP Info
        self.test_dap_info()
        
        # Test 3: VTarget Read
        self.test_vtarget_read()
        
        # Test 4: VTarget Set (3.3V)
        self.test_vtarget_set(3300)
        
        # Test 5: VTarget Set (1.8V)
        self.test_vtarget_set(1800)
        
        # Test 6: VTarget Set (5.0V)
        self.test_vtarget_set(5000)
        
        # Test 7: SWD Connection (optional)
        input("\nPress Enter to test SWD connection (ensure target connected)...")
        self.test_swd_connection()
        
        # Summary
        print("\n" + "=" * 60)
        print("Test Summary:")
        print(f"  Passed: {self.passed_tests}")
        print(f"  Failed: {self.failed_tests}")
        print(f"  Total:  {self.passed_tests + self.failed_tests}")
        print("=" * 60)
        
        return self.failed_tests == 0


def main():
    """Main test execution"""
    test = XiaoUSBTest()
    
    try:
        success = test.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    finally:
        test.disconnect()


if __name__ == "__main__":
    main()
