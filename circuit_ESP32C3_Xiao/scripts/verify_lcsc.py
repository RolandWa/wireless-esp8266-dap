import os
import re

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(script_dir, ".."))
schematic_file = os.path.join(project_dir, "ESP32C3_Xiao_wireless_DAP.kicad_sch")

with open(schematic_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Split into symbol blocks
symbol_blocks = content.split('(symbol')

components = []

for block in symbol_blocks[1:]:  # Skip first empty split
    ref_match = re.search(r'\(property "Reference" "([^"]+)"', block)
    if not ref_match:
        continue
    
    ref = ref_match.group(1)
    
    # Only process R, C, D, Q, U, J components
    if not re.match(r'^[RCDQUJ]\d+', ref):
        continue
    
    val_match = re.search(r'\(property "Value" "([^"]+)"', block)
    fp_match = re.search(r'\(property "Footprint" "([^"]+)"', block)
    lcsc_match = re.search(r'\(property "LCSC" "([^"]+)"', block)
    
    value = val_match.group(1) if val_match else ''
    footprint = fp_match.group(1).split(':')[-1] if fp_match else ''
    lcsc = lcsc_match.group(1) if lcsc_match else 'NONE'
    
    components.append({
        'ref': ref,
        'value': value,
        'lcsc': lcsc,
        'footprint': footprint
    })

# Sort components
components.sort(key=lambda x: (x['ref'][0], int(''.join(filter(str.isdigit, x['ref'])) or '0')))

# Display results
print('=' * 140)
print(f"{'Ref':<6} {'Value':<25} {'LCSC':<15} {'Footprint':<90}")
print('=' * 140)

for c in components:
    fp = c['footprint'][:85] + '...' if len(c['footprint']) > 88 else c['footprint']
    print(f"{c['ref']:<6} {c['value']:<25} {c['lcsc']:<15} {fp:<90}")

print('=' * 140)

# Group by LCSC to check for duplicates or issues
lcsc_groups = {}
for c in components:
    if c['lcsc'] != 'NONE':
        if c['lcsc'] not in lcsc_groups:
            lcsc_groups[c['lcsc']] = []
        lcsc_groups[c['lcsc']].append((c['ref'], c['value'], c['footprint']))

print('\n' + '=' * 140)
print('LCSC Part Number Usage Summary:')
print('=' * 140)
print(f"{'LCSC Part':<15} {'Count':<7} {'Used By':<120}")
print('=' * 140)

for lcsc in sorted(lcsc_groups.keys()):
    refs = lcsc_groups[lcsc]
    count = len(refs)
    ref_list = ', '.join([f"{r[0]}({r[1]})" for r in refs[:5]])
    if len(refs) > 5:
        ref_list += f' ...and {len(refs)-5} more'
    print(f"{lcsc:<15} {count:<7} {ref_list:<120}")

print('=' * 140)

# Check for potential issues
print('\nPotential Issues:')
print('=' * 140)

# Check resistors with different values but might have same LCSC
resistor_lcsc = {}
for c in components:
    if c['ref'].startswith('R') and c['lcsc'] != 'NONE':
        key = (c['lcsc'], c['value'])
        if key not in resistor_lcsc:
            resistor_lcsc[key] = []
        resistor_lcsc[key].append(c['ref'])

# Find LCSC parts used for multiple values (error!)
lcsc_to_values = {}
for c in components:
    if c['lcsc'] != 'NONE':
        if c['lcsc'] not in lcsc_to_values:
            lcsc_to_values[c['lcsc']] = set()
        lcsc_to_values[c['lcsc']].add(c['value'])

errors_found = False
for lcsc, values in lcsc_to_values.items():
    if len(values) > 1:
        print(f"ERROR: LCSC {lcsc} assigned to multiple different values: {', '.join(values)}")
        errors_found = True

if not errors_found:
    print("OK: No LCSC assignment errors found - each LCSC part number maps to only one component value")

print('=' * 140)
