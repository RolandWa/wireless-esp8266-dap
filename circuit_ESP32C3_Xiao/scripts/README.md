# Scripts Directory

Python utility scripts for ESP32-C3 XIAO wireless DAP hardware verification and analysis.

## Scripts

### verify_lcsc.py
**Purpose:** Extract and verify LCSC part number assignments from KiCAD schematic file.

**Usage:**
```bash
python verify_lcsc.py
```

**Output:**
- Lists all components with their LCSC part numbers
- Identifies components without LCSC assignments
- Checks for duplicate LCSC part numbers
- Reports potential issues

**Requirements:**
- Python 3.x
- KiCAD schematic file: `ESP32C3_Xiao_wireless_DAP.kicad_sch`

### analyze_components.py
**Purpose:** Analyze component usage and generate BOM reports from KiCAD schematic.

**Usage:**
```bash
python analyze_components.py
```

**Output:**
- Component count summary
- Bill of Materials (BOM)
- Component groupings by type

## Running from Root Directory

If scripts need to be run from the project root:
```bash
python circuit_ESP32C3_Xiao/scripts/verify_lcsc.py
python circuit_ESP32C3_Xiao/scripts/analyze_components.py
```

## Notes
- Scripts expect to be run from the project root directory
- They automatically locate the schematic in the `circuit_ESP32C3_Xiao/` folder
- Output may include Unicode characters; redirect stderr to suppress encoding warnings on Windows

## References
- KiCad documentation: https://docs.kicad.org/
- KiCad file formats (developer docs): https://dev-docs.kicad.org/en/file-formats/
