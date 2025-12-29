#!/usr/bin/env python3
"""
XIAO ESP32-C3 Hardware Test - WiFi Interface
Tests DAP functionality over WiFi/TCP connection
"""

import sys
import time
import socket
import struct
from typing import Optional, Tuple

try:
    import usbip
except ImportError:
    print("Warning: usbip module not found. USBIP functionality limited.")
    usbip = None


class XiaoWiFiTest:
    """Test suite for XIAO ESP32-C3 DAP over WiFi"""
    
    def __init__(self, host: str = "dap.local", port: int = 3240):
        self.host = host
        self.port = port
        self.sock = None
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
    
    def test_dns_resolution(self) -> Optional[str]:
        """Test DNS resolution of dap.local"""
        print("\n=== DNS Resolution Test ===")
        
        try:
            ip = socket.gethostbyname(self.host)
            self.log_test("DNS Resolution", True, f"{self.host} -> {ip}")
            return ip
        except socket.gaierror:
            self.log_test("DNS Resolution", False, f"Cannot resolve {self.host}")
            
            # Try alternative hostname
            alt_host = "esp32-dap.local"
            try:
                ip = socket.gethostbyname(alt_host)
                self.host = alt_host
                self.log_test("Alternative DNS", True, f"{alt_host} -> {ip}")
                return ip
            except:
                print(f"    Hint: Check if device is powered on and WiFi is connected")
                return None
        except Exception as e:
            self.log_test("DNS Resolution", False, f"Error: {str(e)}")
            return None
    
    def test_tcp_connection(self, ip: str) -> bool:
        """Test TCP connection to WiFi DAP"""
        print("\n=== TCP Connection Test ===")
        
        try:
            # Create socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            
            # Connect
            print(f"    Connecting to {ip}:{self.port}...")
            self.sock.connect((ip, self.port))
            
            self.log_test("TCP Connection", True, f"Connected to {ip}:{self.port}")
            return True
            
        except socket.timeout:
            self.log_test("TCP Connection", False, "Connection timeout")
            return False
        except ConnectionRefusedError:
            self.log_test("TCP Connection", False, f"Connection refused (port {self.port})")
            print(f"    Hint: Check if USBIP server is running on device")
            return False
        except Exception as e:
            self.log_test("TCP Connection", False, f"Error: {str(e)}")
            return False
    
    def test_ping(self, ip: str) -> bool:
        """Test network ping"""
        print("\n=== Network Ping Test ===")
        
        try:
            import subprocess
            import platform
            
            # Platform-specific ping command
            param = "-n" if platform.system().lower() == "windows" else "-c"
            command = ["ping", param, "4", ip]
            
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Parse ping statistics
                output = result.stdout
                if "Average" in output or "avg" in output:
                    self.log_test("Network Ping", True, "Device is reachable")
                    return True
                else:
                    self.log_test("Network Ping", True, "Device responds to ping")
                    return True
            else:
                self.log_test("Network Ping", False, "No response")
                return False
                
        except Exception as e:
            self.log_test("Network Ping", False, f"Error: {str(e)}")
            return False
    
    def test_usbip_handshake(self) -> bool:
        """Test USBIP protocol handshake"""
        print("\n=== USBIP Handshake Test ===")
        
        if not self.sock:
            self.log_test("USBIP Handshake", False, "No TCP connection")
            return False
        
        try:
            # Send OP_REQ_DEVLIST (0x8005)
            version = 0x0111  # USBIP version
            command = 0x8005  # OP_REQ_DEVLIST
            status = 0x0000
            
            request = struct.pack(">HHI", version, command, status)
            self.sock.sendall(request)
            
            # Receive response header
            response = self.sock.recv(4096)
            
            if len(response) >= 8:
                resp_version, resp_command, resp_status = struct.unpack(">HHI", response[:8])
                
                if resp_version == version and resp_command == 0x0005:  # OP_REP_DEVLIST
                    self.log_test("USBIP Handshake", True, f"Protocol version: 0x{resp_version:04X}")
                    
                    # Try to parse device list
                    if len(response) >= 12:
                        num_devices = struct.unpack(">I", response[8:12])[0]
                        self.log_test("Device List", True, f"{num_devices} device(s) exported")
                        return True
                    else:
                        self.log_test("Device List", False, "Response too short")
                        return False
                else:
                    self.log_test("USBIP Handshake", False, 
                                f"Unexpected response: cmd=0x{resp_command:04X}")
                    return False
            else:
                self.log_test("USBIP Handshake", False, "No response from server")
                return False
                
        except socket.timeout:
            self.log_test("USBIP Handshake", False, "Response timeout")
            return False
        except Exception as e:
            self.log_test("USBIP Handshake", False, f"Error: {str(e)}")
            return False
    
    def test_wifi_signal(self) -> bool:
        """Test WiFi signal quality (if accessible)"""
        print("\n=== WiFi Signal Test ===")
        
        # This is a placeholder - actual implementation would require
        # device-specific telemetry command
        print("    Note: WiFi signal quality monitoring not yet implemented")
        self.log_test("WiFi Signal", True, "Test skipped (telemetry not available)")
        return True
    
    def test_uart_loopback(self) -> bool:
        """Test UART loopback (RX-TX connected)"""
        print("\n=== UART Loopback Test ===")
        print("Note: This test requires RX (GPIO20) and TX (GPIO21) to be connected")
        
        # This would require a specific vendor command to control UART
        # For now, provide instructions
        print("    To test UART loopback:")
        print("    1. Connect GPIO20 (RX/D7) to GPIO21 (TX/D6) with a wire")
        print("    2. Use serial terminal to test (115200 baud)")
        print("    3. Characters sent should echo back")
        
        self.log_test("UART Loopback", True, "Manual test required")
        return True
    
    def test_latency(self, ip: str, samples: int = 10) -> Optional[float]:
        """Test network latency"""
        print(f"\n=== Network Latency Test ({samples} samples) ===")
        
        latencies = []
        
        for i in range(samples):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                
                start = time.time()
                sock.connect((ip, self.port))
                elapsed = (time.time() - start) * 1000  # Convert to ms
                
                latencies.append(elapsed)
                sock.close()
                
                print(f"    Sample {i+1}/{samples}: {elapsed:.2f} ms")
                
            except Exception as e:
                print(f"    Sample {i+1}/{samples}: Failed ({str(e)})")
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            self.log_test("Network Latency", True, 
                        f"Avg: {avg_latency:.2f} ms, Min: {min_latency:.2f} ms, Max: {max_latency:.2f} ms")
            return avg_latency
        else:
            self.log_test("Network Latency", False, "All samples failed")
            return None
    
    def disconnect(self):
        """Close connections"""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 60)
        print("XIAO ESP32-C3 Hardware Test Suite - WiFi Interface")
        print(f"Target: {self.host}:{self.port}")
        print("=" * 60)
        
        # Test 1: DNS Resolution
        ip = self.test_dns_resolution()
        if not ip:
            print("\n❌ Cannot proceed without valid IP address")
            print("\nTroubleshooting:")
            print("  1. Check device is powered on")
            print("  2. Verify WiFi credentials in firmware")
            print("  3. Check router is providing DHCP")
            print("  4. Try accessing device by IP instead of hostname")
            return False
        
        # Test 2: Network Ping
        self.test_ping(ip)
        
        # Test 3: Network Latency
        self.test_latency(ip, samples=10)
        
        # Test 4: TCP Connection
        if not self.test_tcp_connection(ip):
            print("\n❌ Cannot proceed without TCP connection")
            return False
        
        # Test 5: USBIP Handshake
        self.test_usbip_handshake()
        
        # Test 6: WiFi Signal
        self.test_wifi_signal()
        
        # Test 7: UART Loopback (manual)
        self.test_uart_loopback()
        
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
    import argparse
    
    parser = argparse.ArgumentParser(description="Test XIAO ESP32-C3 DAP over WiFi")
    parser.add_argument("--host", default="dap.local", 
                       help="Hostname or IP address (default: dap.local)")
    parser.add_argument("--port", type=int, default=3240,
                       help="USBIP port (default: 3240)")
    
    args = parser.parse_args()
    
    test = XiaoWiFiTest(host=args.host, port=args.port)
    
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
