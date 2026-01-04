#!/usr/bin/env python3
"""
Find TME equivalents for components with empty TME fields
Based on LCSC part numbers and component values
"""

import re

# Component mapping for common values
# Format: (Value, LCSC) -> TME
tme_mapping = {
    # Resistors 0603
    ('12k', 'C114659'): 'RC0603JR-0712KL',      # 12kΩ 5% 0603
    ('39k', 'C163424'): 'RC0603JR-0739KL',      # 39kΩ 5% 0603
    ('120R', 'C114640'): 'RC0603JR-07120RL',    # 120Ω 5% 0603
    ('39', 'C2907032'): 'RC0603JR-0739RL',      # 39Ω 5% 0603
    ('1k', 'C114664'): 'RC0603JR-071KL',        # 1kΩ 5% 0603
    ('100k', 'C25803'): 'RC0603JR-07100KL',     # 100kΩ 5% 0603
    ('10k', 'C114636'): 'RC0603JR-0710KL',      # 10kΩ 5% 0603
    ('100R', 'C114639'): 'RC0603JR-07100RL',    # 100Ω 5% 0603
    ('2.2k', 'C2907014'): 'RC0603JR-072K2L',    # 2.2kΩ 5% 0603
    
    # Capacitors
    ('10uF', 'C9900006346'): 'CS2012X7R106M100NR',  # 10µF 0805 X7R (already has TME)
    ('10nF', 'C2907007'): 'CL10B103KB8NNNC',     # 10nF 0603 X7R
    ('100nF', 'C131056'): 'CL10B104KB8NNNC',     # 100nF 0603 X7R
    ('1uF', 'C114639'): 'CL10A105KB8NNNC',       # 1µF 0603 X7R
}

def find_tme_equivalent(value, lcsc):
    """Find TME equivalent based on value and LCSC number"""
    key = (value, lcsc)
    if key in tme_mapping:
        return tme_mapping[key]
    
    # Try generic matching by value for common resistors
    if value in ['12k', '39k', '120R', '39', '1k', '100k', '10k', '100R', '2.2k']:
        # Return generic Yageo resistor series
        value_map = {
            '12k': 'RC0603JR-0712KL',
            '39k': 'RC0603JR-0739KL',
            '120R': 'RC0603JR-07120RL',
            '39': 'RC0603JR-0739RL',
            '1k': 'RC0603JR-071KL',
            '100k': 'RC0603JR-07100KL',
            '10k': 'RC0603JR-0710KL',
            '100R': 'RC0603JR-07100RL',
            '2.2k': 'RC0603JR-072K2L',
        }
        return value_map.get(value, '')
    
    return ''

if __name__ == '__main__':
    print("TME Mapping Database")
    print("=" * 60)
    for (val, lcsc), tme in sorted(tme_mapping.items()):
        print(f"{val:10s} {lcsc:12s} -> {tme}")
