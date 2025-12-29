import re
import csv
import os
from collections import defaultdict

# Read the schematic file using relative paths
script_dir = os.path.dirname(os.path.abspath(__file__))
schematic_file = os.path.join(script_dir, "circuit_ESP32C3_Xiao", "ESP32C3_Xiao_wireless_DAP.kicad_sch")
mapping_file = os.path.join(script_dir, "circuit_ESP32C3_Xiao", "jlcpcb", "mapping.csv")

with open(schematic_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract components from schematic
symbol_pattern = r'\(symbol\s+\(lib_id[^\)]+\)[^\(]*\(at[^\(]*[\s\S]*?\(instances'
symbols = re.findall(symbol_pattern, content)

components = []
for symbol in symbols:
    ref_match = re.search(r'\(property "Reference" "([^"]+)"', symbol)
    val_match = re.search(r'\(property "Value" "([^"]+)"', symbol)
    lcsc_match = re.search(r'\(property "LCSC" "([^"]+)"', symbol)
    footprint_match = re.search(r'\(property "Footprint" "([^"]+)"', symbol)
    desc_match = re.search(r'\(property "Description" "([^"]+)"', symbol)
    
    if ref_match:
        ref = ref_match.group(1)
        # Only include actual components (R, C, D, Q, U, J, H)
        if re.match(r'^[RCDQUJH]\d+', ref):
            components.append({
                'Reference': ref,
                'Value': val_match.group(1) if val_match else '',
                'LCSC_Schematic': lcsc_match.group(1) if lcsc_match else 'Missing',
                'Footprint': footprint_match.group(1) if footprint_match else '',
                'Description': desc_match.group(1) if desc_match else ''
            })

# Sort components by reference
components.sort(key=lambda x: (x['Reference'][0], int(re.search(r'\d+', x['Reference']).group())))

# Read mapping.csv
mapping_dict = {}
with open(mapping_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        footprint = row['Footprint']
        value = row['Part Value']
        lcsc = row['LCSC Part']
        mapping_dict[(footprint, value)] = lcsc

# Compare and output results
print("=" * 150)
print(f"{'Ref':<8} {'Value':<15} {'LCSC (Schematic)':<18} {'LCSC (Mapping)':<18} {'Footprint (Schematic)':<50} {'Status':<15}")
print("=" * 150)

for comp in components:
    ref = comp['Reference']
    value = comp['Value']
    lcsc_sch = comp['LCSC_Schematic']
    footprint_full = comp['Footprint']
    footprint = comp['Footprint'].split(':')[-1] if ':' in comp['Footprint'] else comp['Footprint']
    
    # Look up in mapping
    lcsc_map = mapping_dict.get((footprint, value), 'Not in mapping')
    
    # Determine status
    if lcsc_sch == 'Missing' and lcsc_map == 'Not in mapping':
        status = 'Both Missing'
    elif lcsc_sch == 'Missing':
        status = 'Missing in Sch'
    elif lcsc_map == 'Not in mapping':
        status = 'Not in Mapping'
    elif lcsc_sch == lcsc_map:
        status = 'Match ✓'
    else:
        status = 'MISMATCH ⚠'
    
    # Truncate footprint for display
    fp_display = footprint[:48] + '..' if len(footprint) > 50 else footprint
    
    print(f"{ref:<8} {value:<15} {lcsc_sch:<18} {lcsc_map:<18} {fp_display:<50} {status:<15}")

print("=" * 150)

# Show mapping.csv contents
print("\n" + "=" * 80)
print("MAPPING.CSV CONTENTS:")
print("=" * 80)
print(f"{'Footprint':<55} {'Value':<20} {'LCSC':<15}")
print("-" * 80)
for (fp, val), lcsc in sorted(mapping_dict.items()):
    print(f"{fp:<55} {val:<20} {lcsc:<15}")
print("=" * 80)

# Summary statistics
total = len(components)
matches = sum(1 for c in components if mapping_dict.get((c['Footprint'].split(':')[-1], c['Value']), '') == c['LCSC_Schematic'] and c['LCSC_Schematic'] != 'Missing')
mismatches = sum(1 for c in components if mapping_dict.get((c['Footprint'].split(':')[-1], c['Value']), 'X') not in ['', c['LCSC_Schematic']] and c['LCSC_Schematic'] != 'Missing')
missing_sch = sum(1 for c in components if c['LCSC_Schematic'] == 'Missing')

print(f"\nSummary:")
print(f"Total components: {total}")
print(f"Matches: {matches}")
print(f"Mismatches: {mismatches}")
print(f"Missing in Schematic: {missing_sch}")
