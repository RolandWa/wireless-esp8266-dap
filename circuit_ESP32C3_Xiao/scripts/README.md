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

### generate_vtarget_cal_boards.py
**Purpose:** Generate `main/vtarget_cal_boards.c`, the per-board VTarget calibration
tables of the firmware, from the DMM sweeps in
`tests/test_results/vtarget_PCB-xx_measurements.csv`. Each 101-point curve is reduced
to at most 32 points that stay within 6 mV of the measurements.

**Usage:**
```bash
python circuit_ESP32C3_Xiao/scripts/generate_vtarget_cal_boards.py          # write the file
python circuit_ESP32C3_Xiao/scripts/generate_vtarget_cal_boards.py --check  # exit 1 if stale
```

**Output:** `main/vtarget_cal_boards.c` (deterministic, no timestamps) and a per-board
summary (points, range, max fit error). Re-run after re-measuring a board with
`tests/pwm_vtarget_dmm.py`; the unit tests (`python -m pytest tests/unit`) fail if the
committed file is out of date.

**Requirements:** Python 3 standard library only.

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
- VTarget batch analysis (why per-board tables): [VTARGET_BATCH_ANALYSIS.md](../documentations/VTARGET_BATCH_ANALYSIS.md)
- VTarget firmware and interface documentation: [docs/vtarget.md](../../docs/vtarget.md)
