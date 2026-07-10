#!/usr/bin/env python3
"""
VTarget Linearity Test Suite for Wireless ESP8266/ESP32 DAP
Tests VTarget voltage output linearity and VTref measurement accuracy
Requires USB connection for proper VTarget power supply

Author: Test Suite
Date: 2025-12-29
"""

import os
import sys
import time
import csv
import argparse
from datetime import datetime
from typing import List, Tuple, Dict
import statistics

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import numpy as np
    from scipy import stats
    from scipy.optimize import curve_fit
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("Warning: scipy/numpy not available. Advanced statistics disabled.")
    print("Install with: pip install numpy scipy")

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available. Plotting disabled.")
    print("Install with: pip install matplotlib")

try:
    import pyocd
    from pyocd.core.helpers import ConnectHelper
    from pyocd.probe.pydapaccess import DAPAccess
except ImportError:
    print("Error: pyOCD not installed. Please install with: pip install pyocd")
    sys.exit(1)

try:
    import pyvisa
    HAS_PYVISA = True
except ImportError:
    HAS_PYVISA = False
    print("Warning: pyvisa not available. DMM integration disabled.")
    print("Install with: pip install pyvisa pyvisa-py")


class VTargetLinearityTest:
    """Test VTarget output linearity and VTref measurement accuracy"""
    
    # VTarget voltage range (mV)
    VTARGET_MIN = 1250
    VTARGET_MAX = 5000
    
    # Test parameters
    SETTLING_TIME = 0.5  # seconds to wait after setting voltage
    MEASUREMENT_SAMPLES = 10  # number of measurements per voltage point
    MEASUREMENT_DELAY = 0.05  # seconds between measurements
    
    # pyOCD vendor() API: vendor(index, data)
    # index = offset from DAP_VENDOR0 (0x80), NOT the full command ID.
    # ID_DAP_Vendor1 (0x81) → index=1, ID_DAP_Vendor2 (0x82) → index=2.
    # pyOCD strips the echoed command byte; response[0] is the first payload byte.
    CMD_READ_VTARGET = 1  # DAP Vendor index for read  (command ID 0x81)
    CMD_SET_VTARGET  = 2  # DAP Vendor index for set   (command ID 0x82)
    
    def __init__(self, serial_number: str = None, dmm_resource: str = None):
        """Initialize test suite
        
        Args:
            serial_number: Specific DAP probe serial number to use
            dmm_resource: VISA resource string for Keysight DMM (e.g., 'USB0::0x2A8D::0x1301::MY********::INSTR')
        """
        self.serial_number = serial_number
        self.probe = None
        self.session = None
        self.dmm = None
        self.dmm_resource = dmm_resource
        self.use_dmm = False
        self.results = []
        self.test_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def connect(self) -> bool:
        """Connect to DAP probe via USB
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Find all connected probes
            all_probes = ConnectHelper.get_all_connected_probes()
            
            if not all_probes:
                print("Error: No DAP probes found")
                return False
            
            # Filter by serial number if specified
            if self.serial_number:
                probes = [p for p in all_probes if p.serial_number == self.serial_number]
                if not probes:
                    print(f"Error: Probe with serial {self.serial_number} not found")
                    return False
            else:
                probes = all_probes
            
            # Use first matching probe
            self.probe = probes[0]
            print(f"Connecting to probe: {self.probe.description}")
            print(f"Serial number: {self.probe.serial_number}")
            
            # Open probe session
            self.session = ConnectHelper.session_with_chosen_probe(
                unique_id=self.probe.unique_id,
                options={'auto_unlock': False}
            )
            self.session.open()
            
            print("Connection successful")
            return True
            
        except Exception as e:
            print(f"Error connecting to probe: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from DAP probe and DMM"""
        try:
            if self.session:
                self.session.close()
                self.session = None
            self.probe = None
            
            if self.dmm:
                self.dmm.close()
                self.dmm = None
            
            print("Disconnected")
        except Exception as e:
            print(f"Error disconnecting: {e}")
    
    def connect_dmm(self) -> bool:
        """Connect to Keysight 34460A/34461A DMM via VISA
        
        Returns:
            True if connection successful, False otherwise
        """
        if not HAS_PYVISA:
            print("Warning: pyvisa not available, DMM integration disabled")
            return False
        
        if not self.dmm_resource:
            print("Warning: No DMM resource specified, DMM integration disabled")
            return False
        
        try:
            rm = pyvisa.ResourceManager()
            self.dmm = rm.open_resource(self.dmm_resource)
            
            # Configure DMM for DC voltage measurement
            self.dmm.write("*RST")  # Reset to known state
            time.sleep(0.5)
            
            # Query identification
            idn = self.dmm.query("*IDN?").strip()
            print(f"Connected to DMM: {idn}")
            
            # Configure for DC voltage measurement
            self.dmm.write("CONF:VOLT:DC 10,0.0001")  # 10V range, 100µV resolution
            self.dmm.write("VOLT:DC:NPLC 10")  # 10 PLCs for low noise (~167ms @ 60Hz)
            self.dmm.write("VOLT:DC:ZERO:AUTO OFF")  # Disable auto-zero for speed
            
            # Verify configuration
            if "34460" in idn or "34461" in idn or "34465" in idn or "34470" in idn:
                self.use_dmm = True
                print("DMM configured for precision DC voltage measurement")
                return True
            else:
                print(f"Warning: Unexpected DMM model: {idn}")
                self.use_dmm = True  # Try anyway
                return True
                
        except Exception as e:
            print(f"Error connecting to DMM: {e}")
            print("Continuing without DMM reference measurements")
            self.dmm = None
            self.use_dmm = False
            return False
    
    def read_dmm_voltage(self) -> float:
        """Read voltage from DMM
        
        Returns:
            Voltage in millivolts, or -1 on error
        """
        if not self.use_dmm or not self.dmm:
            return -1
        
        try:
            # Trigger measurement and read
            voltage_v = float(self.dmm.query("READ?"))
            voltage_mv = voltage_v * 1000.0
            return voltage_mv
            
        except Exception as e:
            print(f"Error reading DMM: {e}")
            return -1
    
    def read_vtarget(self) -> int:
        """Read VTarget voltage from DAP

        Returns:
            Voltage in millivolts, or -1 on error
        """
        try:
            # probe.vendor(int, list) strips the echoed command ID;
            # response[0]=LOW, response[1]=HIGH
            response = self.session.probe.vendor(self.CMD_READ_VTARGET, [])

            if len(response) >= 2:
                voltage_mv = response[0] | (response[1] << 8)
                return voltage_mv
            else:
                print(f"Invalid response length: {len(response)}")
                return -1

        except Exception as e:
            print(f"Error reading VTarget: {e}")
            return -1
    
    def set_vtarget(self, voltage_mv: int) -> bool:
        """Set VTarget voltage
        
        Args:
            voltage_mv: Desired voltage in millivolts (1250-5000)
            
        Returns:
            True if successful, False otherwise
        """
        if voltage_mv < self.VTARGET_MIN or voltage_mv > self.VTARGET_MAX:
            print(f"Error: Voltage {voltage_mv}mV out of range ({self.VTARGET_MIN}-{self.VTARGET_MAX}mV)")
            return False
        
        try:
            # probe.vendor(int, list) strips the echoed command ID;
            # response[0] is the status byte
            low_byte = voltage_mv & 0xFF
            high_byte = (voltage_mv >> 8) & 0xFF
            response = self.session.probe.vendor(self.CMD_SET_VTARGET, [low_byte, high_byte])

            if len(response) >= 1:
                status = response[0]
                if status == 0x00:
                    return True
                elif status == 0x01:
                    print(f"Error: Invalid voltage range")
                    return False
                else:
                    print(f"Error: Unknown status {status}")
                    return False
            else:
                print(f"Invalid response length: {len(response)}")
                return False
                
        except Exception as e:
            print(f"Error setting VTarget: {e}")
            return False
    
    def measure_voltage_point(self, set_voltage_mv: int) -> Dict:
        """Measure voltage at a specific setpoint with multiple samples
        
        Args:
            set_voltage_mv: Voltage to set in millivolts
            
        Returns:
            Dictionary with measurement statistics
        """
        print(f"\nTesting setpoint: {set_voltage_mv} mV")
        
        # Set voltage
        if not self.set_vtarget(set_voltage_mv):
            return None
        
        # Wait for settling
        time.sleep(self.SETTLING_TIME)
        
        # Take multiple measurements from DAP
        dap_measurements = []
        dmm_measurements = []
        
        for i in range(self.MEASUREMENT_SAMPLES):
            # Read from DAP
            voltage = self.read_vtarget()
            if voltage >= 0:
                dap_measurements.append(voltage)
            
            # Read from DMM if available
            if self.use_dmm:
                dmm_voltage = self.read_dmm_voltage()
                if dmm_voltage >= 0:
                    dmm_measurements.append(dmm_voltage)
            
            time.sleep(self.MEASUREMENT_DELAY)
        
        if not dap_measurements:
            print(f"  Error: No valid DAP measurements")
            return None
        
        # Calculate DAP statistics
        mean_dap_voltage = statistics.mean(dap_measurements)
        stdev_dap_voltage = statistics.stdev(dap_measurements) if len(dap_measurements) > 1 else 0
        min_dap_voltage = min(dap_measurements)
        max_dap_voltage = max(dap_measurements)
        error_dap_mv = mean_dap_voltage - set_voltage_mv
        error_dap_percent = (error_dap_mv / set_voltage_mv) * 100
        
        result = {
            'set_voltage_mv': set_voltage_mv,
            'dap_mean_voltage_mv': mean_dap_voltage,
            'dap_stdev_voltage_mv': stdev_dap_voltage,
            'dap_min_voltage_mv': min_dap_voltage,
            'dap_max_voltage_mv': max_dap_voltage,
            'dap_samples': len(dap_measurements),
            'dap_error_mv': error_dap_mv,
            'dap_error_percent': error_dap_percent,
            'dap_raw_measurements': dap_measurements,
        }
        
        # Calculate DMM statistics if available
        if dmm_measurements:
            mean_dmm_voltage = statistics.mean(dmm_measurements)
            stdev_dmm_voltage = statistics.stdev(dmm_measurements) if len(dmm_measurements) > 1 else 0
            min_dmm_voltage = min(dmm_measurements)
            max_dmm_voltage = max(dmm_measurements)
            
            # DMM error vs setpoint
            error_dmm_mv = mean_dmm_voltage - set_voltage_mv
            error_dmm_percent = (error_dmm_mv / set_voltage_mv) * 100
            
            # DAP error vs DMM reference
            dap_vs_dmm_error_mv = mean_dap_voltage - mean_dmm_voltage
            dap_vs_dmm_error_percent = (dap_vs_dmm_error_mv / mean_dmm_voltage) * 100
            
            result.update({
                'dmm_mean_voltage_mv': mean_dmm_voltage,
                'dmm_stdev_voltage_mv': stdev_dmm_voltage,
                'dmm_min_voltage_mv': min_dmm_voltage,
                'dmm_max_voltage_mv': max_dmm_voltage,
                'dmm_samples': len(dmm_measurements),
                'dmm_error_mv': error_dmm_mv,
                'dmm_error_percent': error_dmm_percent,
                'dap_vs_dmm_error_mv': dap_vs_dmm_error_mv,
                'dap_vs_dmm_error_percent': dap_vs_dmm_error_percent,
                'dmm_raw_measurements': dmm_measurements,
            })
            
            print(f"  DAP Mean: {mean_dap_voltage:.2f} mV, StdDev: {stdev_dap_voltage:.2f} mV")
            print(f"  DMM Mean: {mean_dmm_voltage:.2f} mV, StdDev: {stdev_dmm_voltage:.2f} mV")
            print(f"  DAP Error vs Setpoint: {error_dap_mv:.2f} mV ({error_dap_percent:.2f}%)")
            print(f"  DAP Error vs DMM: {dap_vs_dmm_error_mv:.2f} mV ({dap_vs_dmm_error_percent:.2f}%)")
        else:
            print(f"  DAP Mean: {mean_dap_voltage:.2f} mV, StdDev: {stdev_dap_voltage:.2f} mV")
            print(f"  DAP Error vs Setpoint: {error_dap_mv:.2f} mV ({error_dap_percent:.2f}%)")
        
        return result
    
    def test_full_range(self, num_points: int = 20, include_endpoints: bool = True) -> List[Dict]:
        """Test VTarget linearity across full voltage range
        
        Args:
            num_points: Number of test points
            include_endpoints: Always test min and max voltages
            
        Returns:
            List of measurement results
        """
        print(f"\n{'='*60}")
        print(f"VTarget Full Range Linearity Test")
        print(f"{'='*60}")
        print(f"Range: {self.VTARGET_MIN}-{self.VTARGET_MAX} mV")
        print(f"Test points: {num_points}")
        print(f"Samples per point: {self.MEASUREMENT_SAMPLES}")
        
        # Generate test voltages
        if include_endpoints:
            # Ensure min and max are always tested
            if num_points <= 2:
                voltages = [self.VTARGET_MIN, self.VTARGET_MAX]
            else:
                # Linspace between min and max
                step = (self.VTARGET_MAX - self.VTARGET_MIN) / (num_points - 1)
                voltages = [int(self.VTARGET_MIN + i * step) for i in range(num_points)]
        else:
            step = (self.VTARGET_MAX - self.VTARGET_MIN) / (num_points + 1)
            voltages = [int(self.VTARGET_MIN + (i + 1) * step) for i in range(num_points)]
        
        # Test each voltage point
        results = []
        for voltage in voltages:
            result = self.measure_voltage_point(voltage)
            if result:
                results.append(result)
        
        self.results = results
        return results
    
    def test_specific_points(self, voltages: List[int]) -> List[Dict]:
        """Test specific voltage points
        
        Args:
            voltages: List of voltages to test in millivolts
            
        Returns:
            List of measurement results
        """
        print(f"\n{'='*60}")
        print(f"VTarget Specific Points Test")
        print(f"{'='*60}")
        print(f"Test voltages: {voltages}")
        
        results = []
        for voltage in voltages:
            if self.VTARGET_MIN <= voltage <= self.VTARGET_MAX:
                result = self.measure_voltage_point(voltage)
                if result:
                    results.append(result)
            else:
                print(f"Warning: Skipping {voltage}mV (out of range)")
        
        self.results = results
        return results
    
    def calculate_linearity_statistics(self) -> Dict:
        """Calculate linearity statistics from test results
        
        Returns:
            Dictionary with linearity metrics
        """
        if not self.results:
            print("Error: No test results available")
            return None
        
        print(f"\n{'='*60}")
        print(f"Linearity Statistics")
        print(f"{'='*60}")
        
        # Extract DAP data
        set_voltages = [r['set_voltage_mv'] for r in self.results]
        dap_measured_voltages = [r['dap_mean_voltage_mv'] for r in self.results]
        dap_errors = [r['dap_error_mv'] for r in self.results]
        dap_errors_percent = [r['dap_error_percent'] for r in self.results]
        
        # Check if DMM data is available
        has_dmm = 'dmm_mean_voltage_mv' in self.results[0]
        
        # Basic DAP statistics
        stats_dict = {
            'num_points': len(self.results),
            'voltage_range_mv': (min(set_voltages), max(set_voltages)),
            'dap_mean_error_mv': statistics.mean(dap_errors),
            'dap_max_error_mv': max(dap_errors, key=abs),
            'dap_min_error_mv': min(dap_errors, key=abs),
            'dap_stdev_error_mv': statistics.stdev(dap_errors) if len(dap_errors) > 1 else 0,
            'dap_mean_error_percent': statistics.mean(dap_errors_percent),
            'dap_max_error_percent': max(dap_errors_percent, key=abs),
        }
        
        # DMM statistics if available
        if has_dmm:
            dmm_measured_voltages = [r['dmm_mean_voltage_mv'] for r in self.results]
            dmm_errors = [r['dmm_error_mv'] for r in self.results]
            dmm_errors_percent = [r['dmm_error_percent'] for r in self.results]
            dap_vs_dmm_errors = [r['dap_vs_dmm_error_mv'] for r in self.results]
            dap_vs_dmm_errors_percent = [r['dap_vs_dmm_error_percent'] for r in self.results]
            
            stats_dict.update({
                'dmm_mean_error_mv': statistics.mean(dmm_errors),
                'dmm_max_error_mv': max(dmm_errors, key=abs),
                'dmm_stdev_error_mv': statistics.stdev(dmm_errors) if len(dmm_errors) > 1 else 0,
                'dmm_mean_error_percent': statistics.mean(dmm_errors_percent),
                'dap_vs_dmm_mean_error_mv': statistics.mean(dap_vs_dmm_errors),
                'dap_vs_dmm_max_error_mv': max(dap_vs_dmm_errors, key=abs),
                'dap_vs_dmm_stdev_error_mv': statistics.stdev(dap_vs_dmm_errors) if len(dap_vs_dmm_errors) > 1 else 0,
                'dap_vs_dmm_mean_error_percent': statistics.mean(dap_vs_dmm_errors_percent),
                'dap_vs_dmm_max_error_percent': max(dap_vs_dmm_errors_percent, key=abs),
            })
        
        # Advanced statistics with scipy
        if HAS_SCIPY:
            # Linear regression for DAP vs Setpoint
            slope_dap, intercept_dap, r_value_dap, p_value_dap, std_err_dap = stats.linregress(set_voltages, dap_measured_voltages)
            r_squared_dap = r_value_dap ** 2
            
            # Calculate residuals
            predicted_dap = [slope_dap * x + intercept_dap for x in set_voltages]
            residuals_dap = [measured - pred for measured, pred in zip(dap_measured_voltages, predicted_dap)]
            
            # Non-linearity (max deviation from ideal line)
            max_residual_dap = max(residuals_dap, key=abs)
            
            # Integral non-linearity (INL) and Differential non-linearity (DNL)
            ideal_step = (max(set_voltages) - min(set_voltages)) / (len(set_voltages) - 1) if len(set_voltages) > 1 else 0
            actual_steps_dap = [dap_measured_voltages[i+1] - dap_measured_voltages[i] for i in range(len(dap_measured_voltages)-1)]
            dnl_values_dap = [(step - ideal_step) / ideal_step * 100 for step in actual_steps_dap] if ideal_step > 0 else []
            
            stats_dict.update({
                'dap_r_squared': r_squared_dap,
                'dap_slope': slope_dap,
                'dap_intercept_mv': intercept_dap,
                'dap_std_error': std_err_dap,
                'dap_p_value': p_value_dap,
                'dap_max_nonlinearity_mv': max_residual_dap,
                'dap_max_dnl_percent': max(dnl_values_dap, key=abs) if dnl_values_dap else 0,
                'dap_mean_dnl_percent': statistics.mean(dnl_values_dap) if dnl_values_dap else 0,
            })
            
            print(f"\nDAP vs Setpoint:")
            print(f"R² (coefficient of determination): {r_squared_dap:.6f}")
            print(f"Slope: {slope_dap:.6f}")
            print(f"Intercept: {intercept_dap:.2f} mV")
            print(f"Max non-linearity: {max_residual_dap:.2f} mV")
            print(f"Max DNL: {max(dnl_values_dap, key=abs):.2f}%" if dnl_values_dap else "Max DNL: N/A")
            
            # DMM linearity analysis if available
            if has_dmm:
                # DAP vs DMM regression (DMM as reference)
                slope_dmm_ref, intercept_dmm_ref, r_value_dmm_ref, p_value_dmm_ref, std_err_dmm_ref = stats.linregress(dmm_measured_voltages, dap_measured_voltages)
                r_squared_dmm_ref = r_value_dmm_ref ** 2
                
                # DMM vs Setpoint regression
                slope_dmm, intercept_dmm, r_value_dmm, p_value_dmm, std_err_dmm = stats.linregress(set_voltages, dmm_measured_voltages)
                r_squared_dmm = r_value_dmm ** 2
                
                stats_dict.update({
                    'dap_vs_dmm_r_squared': r_squared_dmm_ref,
                    'dap_vs_dmm_slope': slope_dmm_ref,
                    'dap_vs_dmm_intercept_mv': intercept_dmm_ref,
                    'dmm_r_squared': r_squared_dmm,
                    'dmm_slope': slope_dmm,
                    'dmm_intercept_mv': intercept_dmm,
                })
                
                print(f"\nDAP vs DMM Reference:")
                print(f"R²: {r_squared_dmm_ref:.6f}")
                print(f"Slope: {slope_dmm_ref:.6f} (ideal: 1.0)")
                print(f"Intercept: {intercept_dmm_ref:.2f} mV (ideal: 0.0)")
                
                print(f"\nDMM vs Setpoint:")
                print(f"R²: {r_squared_dmm:.6f}")
                print(f"Slope: {slope_dmm:.6f}")
                print(f"Intercept: {intercept_dmm:.2f} mV")
        else:
            # Simple correlation coefficient for DAP
            mean_set = statistics.mean(set_voltages)
            mean_meas = statistics.mean(dap_measured_voltages)
            
            numerator = sum((s - mean_set) * (m - mean_meas) for s, m in zip(set_voltages, dap_measured_voltages))
            denom_set = sum((s - mean_set) ** 2 for s in set_voltages)
            denom_meas = sum((m - mean_meas) ** 2 for m in dap_measured_voltages)
            
            if denom_set > 0 and denom_meas > 0:
                correlation = numerator / (denom_set * denom_meas) ** 0.5
                stats_dict['dap_correlation'] = correlation
                print(f"DAP correlation coefficient: {correlation:.6f}")
        
        # Print summary
        print(f"\nDAP Mean error vs Setpoint: {stats_dict['dap_mean_error_mv']:.2f} mV ({stats_dict['dap_mean_error_percent']:.2f}%)")
        print(f"DAP Max error vs Setpoint: {stats_dict['dap_max_error_mv']:.2f} mV ({stats_dict['dap_max_error_percent']:.2f}%)")
        print(f"DAP Error std dev: {stats_dict['dap_stdev_error_mv']:.2f} mV")
        
        if has_dmm:
            print(f"\nDAP Mean error vs DMM: {stats_dict['dap_vs_dmm_mean_error_mv']:.2f} mV ({stats_dict['dap_vs_dmm_mean_error_percent']:.2f}%)")
            print(f"DAP Max error vs DMM: {stats_dict['dap_vs_dmm_max_error_mv']:.2f} mV ({stats_dict['dap_vs_dmm_max_error_percent']:.2f}%)")
        
        return stats_dict
    
    def save_results_csv(self, filename: str = None):
        """Save test results to CSV file
        
        Args:
            filename: Output CSV filename (auto-generated if None)
        """
        if not self.results:
            print("Error: No results to save")
            return
        
        if filename is None:
            filename = f"vtarget_linearity_{self.test_timestamp}.csv"
        
        # Ensure tests directory exists
        os.makedirs('test_results', exist_ok=True)
        filepath = os.path.join('test_results', filename)
        
        # Check if DMM data is available
        has_dmm = 'dmm_mean_voltage_mv' in self.results[0]
        
        try:
            with open(filepath, 'w', newline='') as csvfile:
                # Define base fieldnames
                fieldnames = [
                    'set_voltage_mv',
                    'dap_mean_voltage_mv',
                    'dap_stdev_voltage_mv',
                    'dap_min_voltage_mv',
                    'dap_max_voltage_mv',
                    'dap_samples',
                    'dap_error_mv',
                    'dap_error_percent',
                ]
                
                # Add DMM fields if available
                if has_dmm:
                    fieldnames.extend([
                        'dmm_mean_voltage_mv',
                        'dmm_stdev_voltage_mv',
                        'dmm_min_voltage_mv',
                        'dmm_max_voltage_mv',
                        'dmm_samples',
                        'dmm_error_mv',
                        'dmm_error_percent',
                        'dap_vs_dmm_error_mv',
                        'dap_vs_dmm_error_percent',
                    ])
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in self.results:
                    row = {k: result[k] for k in fieldnames if k in result}
                    writer.writerow(row)
            
            print(f"\nResults saved to: {filepath}")
            
            # Also save raw measurements
            raw_filename = filename.replace('.csv', '_raw.csv')
            raw_filepath = os.path.join('test_results', raw_filename)
            
            with open(raw_filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header row
                header = ['set_voltage_mv']
                header.extend([f'dap_sample_{i+1}' for i in range(self.MEASUREMENT_SAMPLES)])
                if has_dmm:
                    header.extend([f'dmm_sample_{i+1}' for i in range(self.MEASUREMENT_SAMPLES)])
                writer.writerow(header)
                
                # Data rows
                for result in self.results:
                    row = [result['set_voltage_mv']] + result['dap_raw_measurements']
                    if has_dmm and 'dmm_raw_measurements' in result:
                        row.extend(result['dmm_raw_measurements'])
                    writer.writerow(row)
            
            print(f"Raw measurements saved to: {raw_filepath}")
            
        except Exception as e:
            print(f"Error saving results: {e}")
    
    def save_statistics_csv(self, stats: Dict, filename: str = None):
        """Save linearity statistics to CSV file
        
        Args:
            stats: Statistics dictionary
            filename: Output CSV filename (auto-generated if None)
        """
        if not stats:
            print("Error: No statistics to save")
            return
        
        if filename is None:
            filename = f"vtarget_statistics_{self.test_timestamp}.csv"
        
        os.makedirs('test_results', exist_ok=True)
        filepath = os.path.join('test_results', filename)
        
        try:
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Metric', 'Value'])
                
                for key, value in stats.items():
                    if isinstance(value, tuple):
                        writer.writerow([key, f"{value[0]}-{value[1]}"])
                    elif isinstance(value, float):
                        writer.writerow([key, f"{value:.6f}"])
                    else:
                        writer.writerow([key, value])
            
            print(f"Statistics saved to: {filepath}")
            
        except Exception as e:
            print(f"Error saving statistics: {e}")
    
    def plot_results(self, filename: str = None):
        """Plot linearity results
        
        Args:
            filename: Output plot filename (auto-generated if None)
        """
        if not HAS_MATPLOTLIB:
            print("Warning: matplotlib not available, skipping plot")
            return
        
        if not self.results:
            print("Error: No results to plot")
            return
        
        if filename is None:
            filename = f"vtarget_linearity_{self.test_timestamp}.png"
        
        os.makedirs('test_results', exist_ok=True)
        filepath = os.path.join('test_results', filename)
        
        # Check if DMM data is available
        has_dmm = 'dmm_mean_voltage_mv' in self.results[0]
        
        # Extract DAP data
        set_voltages = [r['set_voltage_mv'] for r in self.results]
        dap_measured_voltages = [r['dap_mean_voltage_mv'] for r in self.results]
        dap_errors = [r['dap_error_mv'] for r in self.results]
        dap_stdevs = [r['dap_stdev_voltage_mv'] for r in self.results]
        
        if has_dmm:
            # Create figure with 3 subplots for DMM comparison
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 14))
            
            dmm_measured_voltages = [r['dmm_mean_voltage_mv'] for r in self.results]
            dmm_stdevs = [r['dmm_stdev_voltage_mv'] for r in self.results]
            dap_vs_dmm_errors = [r['dap_vs_dmm_error_mv'] for r in self.results]
            
            # Plot 1: Measured vs Set voltage (DAP and DMM)
            ax1.errorbar(set_voltages, dap_measured_voltages, yerr=dap_stdevs, fmt='o-', 
                         capsize=5, label='DAP Measured', alpha=0.7)
            ax1.errorbar(set_voltages, dmm_measured_voltages, yerr=dmm_stdevs, fmt='s-', 
                         capsize=5, label='DMM Reference', alpha=0.7)
            ax1.plot([min(set_voltages), max(set_voltages)], 
                    [min(set_voltages), max(set_voltages)], 
                    'r--', label='Ideal', linewidth=2)
            ax1.set_xlabel('Set Voltage (mV)', fontsize=12)
            ax1.set_ylabel('Measured Voltage (mV)', fontsize=12)
            ax1.set_title('VTarget Linearity: DAP vs DMM Reference', fontsize=14, fontweight='bold')
            ax1.legend(fontsize=10)
            ax1.grid(True, alpha=0.3)
            
            # Plot 2: DAP Error vs Set voltage
            ax2.errorbar(set_voltages, dap_errors, yerr=dap_stdevs, fmt='o-', capsize=5, color='blue', label='DAP Error')
            ax2.axhline(y=0, color='r', linestyle='--', linewidth=2)
            ax2.set_xlabel('Set Voltage (mV)', fontsize=12)
            ax2.set_ylabel('DAP Error vs Setpoint (mV)', fontsize=12)
            ax2.set_title('DAP Measurement Error', fontsize=14, fontweight='bold')
            ax2.legend(fontsize=10)
            ax2.grid(True, alpha=0.3)
            
            # Plot 3: DAP vs DMM Error
            ax3.errorbar(set_voltages, dap_vs_dmm_errors, yerr=dap_stdevs, fmt='o-', capsize=5, color='green', label='DAP vs DMM')
            ax3.axhline(y=0, color='r', linestyle='--', linewidth=2)
            ax3.set_xlabel('Set Voltage (mV)', fontsize=12)
            ax3.set_ylabel('DAP Error vs DMM Reference (mV)', fontsize=12)
            ax3.set_title('DAP Accuracy vs DMM', fontsize=14, fontweight='bold')
            ax3.legend(fontsize=10)
            ax3.grid(True, alpha=0.3)
            
        else:
            # Create figure with 2 subplots for DAP only
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))
            
            # Plot 1: Measured vs Set voltage
            ax1.errorbar(set_voltages, dap_measured_voltages, yerr=dap_stdevs, fmt='o-', 
                         capsize=5, label='DAP Measured')
            ax1.plot([min(set_voltages), max(set_voltages)], 
                    [min(set_voltages), max(set_voltages)], 
                    'r--', label='Ideal')
            ax1.set_xlabel('Set Voltage (mV)')
            ax1.set_ylabel('Measured Voltage (mV)')
            ax1.set_title('VTarget Linearity')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Plot 2: Error vs Set voltage
            ax2.errorbar(set_voltages, dap_errors, yerr=dap_stdevs, fmt='o-', capsize=5)
            ax2.axhline(y=0, color='r', linestyle='--')
            ax2.set_xlabel('Set Voltage (mV)')
            ax2.set_ylabel('Error (mV)')
            ax2.set_title('VTarget Error')
            ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        print(f"Plot saved to: {filepath}")
        plt.close()


def main():
    """Main test execution"""
    parser = argparse.ArgumentParser(description='VTarget Linearity Test with Optional DMM Reference')
    parser.add_argument('-s', '--serial', help='DAP probe serial number')
    parser.add_argument('-d', '--dmm', help='DMM VISA resource string (e.g., USB0::0x2A8D::0x1301::MY********::INSTR)')
    parser.add_argument('-n', '--num-points', type=int, default=20, 
                       help='Number of test points (default: 20)')
    parser.add_argument('-m', '--samples', type=int, default=10,
                       help='Samples per point (default: 10)')
    parser.add_argument('--voltages', type=str,
                       help='Comma-separated list of specific voltages to test (e.g., "1250,2500,5000")')
    parser.add_argument('--no-plot', action='store_true',
                       help='Skip plotting results')
    
    args = parser.parse_args()
    
    # Create test instance
    test = VTargetLinearityTest(serial_number=args.serial, dmm_resource=args.dmm)
    test.MEASUREMENT_SAMPLES = args.samples
    
    # Connect to probe
    if not test.connect():
        print("Failed to connect to DAP probe")
        sys.exit(1)
    
    # Connect to DMM if specified
    if args.dmm:
        print("\nAttempting to connect to DMM...")
        test.connect_dmm()
    
    try:
        # Run tests
        if args.voltages:
            # Test specific voltages
            voltages = [int(v.strip()) for v in args.voltages.split(',')]
            test.test_specific_points(voltages)
        else:
            # Test full range
            test.test_full_range(num_points=args.num_points)
        
        # Calculate statistics
        if test.results:
            stats = test.calculate_linearity_statistics()
            
            # Save results
            test.save_results_csv()
            if stats:
                test.save_statistics_csv(stats)
            
            # Plot results
            if not args.no_plot:
                test.plot_results()
            
            # Print summary
            print(f"\n{'='*60}")
            print(f"Test Summary")
            print(f"{'='*60}")
            print(f"Total test points: {len(test.results)}")
            print(f"DMM reference: {'YES' if test.use_dmm else 'NO'}")
            print(f"Results saved to: test_results/")
            
            # Pass/Fail criteria
            if stats:
                dap_max_error = abs(stats['dap_max_error_percent'])
                r_squared_dap = stats.get('dap_r_squared', 0)
                
                print(f"\nDAP Pass/Fail Criteria (vs Setpoint):")
                print(f"  Max error < 2%: {'PASS' if dap_max_error < 2.0 else 'FAIL'} ({dap_max_error:.2f}%)")
                if 'dap_r_squared' in stats:
                    print(f"  R² > 0.99: {'PASS' if r_squared_dap > 0.99 else 'FAIL'} ({r_squared_dap:.6f})")
                
                # DMM comparison if available
                if 'dap_vs_dmm_max_error_percent' in stats:
                    dap_vs_dmm_max_error = abs(stats['dap_vs_dmm_max_error_percent'])
                    dap_vs_dmm_r2 = stats.get('dap_vs_dmm_r_squared', 0)
                    
                    print(f"\nDAP Accuracy (vs DMM Reference):")
                    print(f"  Max error < 1%: {'PASS' if dap_vs_dmm_max_error < 1.0 else 'FAIL'} ({dap_vs_dmm_max_error:.2f}%)")
                    if 'dap_vs_dmm_r_squared' in stats:
                        print(f"  R² > 0.995: {'PASS' if dap_vs_dmm_r2 > 0.995 else 'FAIL'} ({dap_vs_dmm_r2:.6f})")
        
    finally:
        # Disconnect
        test.disconnect()
    
    print("\nTest complete!")


if __name__ == '__main__':
    main()
