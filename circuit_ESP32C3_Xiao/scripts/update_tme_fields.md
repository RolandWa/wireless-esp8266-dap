# TME Field Update Process
**Script companion documentation for TME field population**

## Purpose
This document explains the process used to populate TME (Transfer Multisort Elektronik) part number equivalents for all LCSC components in the ESP32-C3 XIAO Wireless DAP schematic.

## Process Overview

### 1. Initial Analysis
```bash
# Find all empty TME fields
grep -n 'property "TME" ""' circuit_ESP32C3_Xiao/ESP32C3_Xiao_wireless_DAP.kicad_sch | wc -l
# Result: 27 empty fields (excluding previously updated active components)
```

### 2. Component Extraction
For each component with empty TME field:
- Read component block from `.kicad_sch` file
- Extract: Reference designator, Value, LCSC part number
- Categorize: Resistor, Capacitor, IC, LED, Connector, etc.

### 3. LCSC → TME Mapping
Using online resources (TME catalog, datasheet cross-references):

**Resistors:** Standardized on Yageo RC0603JR-07 series
```python
resistor_map = {
    "C114640": "RC0603JR-07120RL",   # 120Ω, 8 instances
    "C114659": "RC0603JR-0712KL",    # 12kΩ, 3 instances
    "C163424": "RC0603JR-0739KL",    # 39kΩ
    "C22356636": "RC0603JR-07100KL", # 100kΩ, 2 instances
    "C98220": "RC0603JR-0710KL",     # 10kΩ
    "C9900170064": "RC0603JR-071KL", # 1kΩ
    "C2907032": "RC0603JR-0739RL",   # 39Ω
    "C114614": "RC0603JR-0727KL",    # 27kΩ
    "C9900083237": "RC0603JR-07220KL" # 220kΩ
}
```

**Capacitors:** X7R dielectric for temperature stability
```python
capacitor_map = {
    "C9900224280": "0603B103K500CG",    # 10nF, 50V, 0603
    "C9900006346": "CS2012X7R106M100NR" # 10µF, 10V, 0805
}
```

**Active Components:**
- ICs: Match manufacturer/specs (e.g., AP1117-ADJ → AP1117E33G-13)
- LEDs: Match color/package (e.g., Red 0805 → LTST-C191KRKT)
- Transistors: Industry standard equivalents (e.g., YJL2304A → 2N7002K)
- Diodes: Exact match (e.g., 1N4148W C2099 → 1N4148W-TP)

### 4. Schematic Update
Used KiCAD text format manipulation:
```python
# Pattern for TME property update
old_pattern = '''
    (property "LCSC" "CXXXXXX"
        ...
    )
    (property "TME" ""
        ...
    )
'''

new_pattern = '''
    (property "LCSC" "CXXXXXX"
        ...
    )
    (property "TME" "TME_PART_NUMBER"
        ...
    )
'''
```

Batch updates via `multi_replace_string_in_file` tool:
- First batch: 5 resistors (R16, R4, R11, R17, R15)
- Second batch: 7 resistors (R10, R6, R13, R7, R5, R18, R12)
- Third batch: 7 resistors (R19, R8, R14, R1, R9, R2, R3)
- Final: D4 diode (1N4148W)

### 5. Verification
```bash
# Check remaining empty TME fields
grep 'property "TME" ""' circuit_ESP32C3_Xiao/ESP32C3_Xiao_wireless_DAP.kicad_sch

# Expected results: H1-H4 (mounting holes), V1-V3 (sim sources) - 7 items
# All orderable components should have TME values
```

## Excluded Components

### Mounting Holes (4 items)
- **H1, H2, H3, H4:** Mechanical features, no part to order
- **Footprint:** MountingHole_2.2mm_M2_Pad_Via
- **TME field:** Correctly left empty

### Simulation Components (3 items)
- **V1, V2, V3:** SPICE voltage sources for circuit simulation
- **Status:** Not physical parts, excluded from BOM
- **TME field:** Correctly left empty

## Tools Created

### tme_mapper.py
Python module created during this process (optional, for reference):
```python
#!/usr/bin/env python3
"""
LCSC to TME part number mapping database
For ESP32-C3 XIAO Wireless DAP project
"""

# Resistor mappings (Yageo RC0603JR-07 series)
RESISTOR_MAP = {
    "C114640": "RC0603JR-07120RL",   # 120Ω
    "C114659": "RC0603JR-0712KL",    # 12kΩ
    # ... (see full map in file)
}

# Capacitor mappings (X7R ceramic)
CAPACITOR_MAP = {
    "C9900224280": "0603B103K500CG",    # 10nF
    "C9900006346": "CS2012X7R106M100NR" # 10µF
}

def get_tme_equivalent(lcsc_part):
    """Look up TME equivalent for LCSC part number"""
    if lcsc_part in RESISTOR_MAP:
        return RESISTOR_MAP[lcsc_part]
    elif lcsc_part in CAPACITOR_MAP:
        return CAPACITOR_MAP[lcsc_part]
    else:
        return None
```

## Results Summary

**Total components in schematic:** 44 (including mounting holes and sim sources)  
**Orderable components:** 37  
**Components with TME values:** 37 ✅  
**Update success rate:** 100%

### Component Breakdown
- **Resistors:** 19 (all Yageo RC0603JR-07 series)
- **Capacitors:** 6 (all X7R dielectric)
- **ICs:** 2 (AP1117-ADJ, XIAO ESP32-C3)
- **LEDs:** 3 (Red, Yellow, Green)
- **Diodes:** 1 (1N4148W)
- **Transistors:** 1 (N-channel FET)
- **Connectors:** 5 (USB-C, debug headers)

## Quality Assurance

### Verification Checklist
- ✅ All resistor values use same series (Yageo RC0603JR-07)
- ✅ All capacitors have X7R dielectric specified
- ✅ All package sizes match LCSC equivalents
- ✅ All voltage ratings meet or exceed LCSC specs
- ✅ All tolerance ratings documented
- ✅ No accidental updates to mounting holes or sim sources

### Testing Procedure
1. Run `verify_lcsc.py` to extract LCSC assignments
2. Cross-reference TME catalog for each LCSC part
3. Verify electrical specs match (±10% acceptable)
4. Verify footprint/package compatibility
5. Update schematic TME field
6. Re-verify with grep search

## Maintenance

### Adding New Components
When adding new components to the schematic:

1. **Assign LCSC part** during design
2. **Find TME equivalent:**
   - Search TME catalog by specifications
   - Match package size exactly
   - Match or exceed voltage/current ratings
   - Prefer same manufacturer when possible
3. **Update TME field** in KiCAD properties
4. **Document exceptions** in TME_FIELD_COMPLETION_SUMMARY.md
5. **Re-run analyze_components.py** to update BOM

### Component Substitution Guidelines
- **Resistors:** Yageo RC0603JR-07 series preferred (5% tolerance acceptable)
- **Capacitors:** X7R dielectric required for stability, match voltage rating
- **Active components:** Verify pinout compatibility, not just electrical specs
- **Connectors:** Check mechanical dimensions and mounting style

## References

- **Full documentation:** [TME_FIELD_COMPLETION_SUMMARY.md](../documentations/TME_FIELD_COMPLETION_SUMMARY.md)
- **Component analysis:** Use `analyze_components.py` script
- **LCSC verification:** Use `verify_lcsc.py` script
- **TME catalog:** https://www.tme.eu/
- **JLCPCB parts:** https://jlcpcb.com/parts

## Troubleshooting

### Empty TME Fields After Update
Check if component is:
1. Mounting hole (H1-H4) → Correct to leave empty
2. Simulation source (V1-V3) → Correct to leave empty
3. New component not yet mapped → Find TME equivalent and update

### TME Part Not Available
1. Search for alternative manufacturer (e.g., KOA, Samsung, Vishay)
2. Ensure specifications match within ±10%
3. Document substitution in summary file
4. Consider ordering LCSC part directly if no TME equivalent exists

### Package Mismatch
- Verify metric vs imperial designation (0603 = 1608 metric)
- Check pad layout compatibility with footprint
- Measure footprint dimensions if uncertain
- Update footprint if necessary (not recommended post-PCB design)

---

*Process documented 2024*  
*Last updated: TME field completion project*
