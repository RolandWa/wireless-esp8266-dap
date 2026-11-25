# VTarget Batch Analysis

**Date:** 2026-09-08  
**Measurement:** 101-point DMM sweep per board, +/-5% requested-voltage criterion  
**Assumption:** PCB-01, PCB-04, PCB-05, PCB-06, PCB-08, PCB-09, and PCB-10 use the same reworked VTarget component population.  
**Excluded from this qualified-population analysis:** PCB-02, PCB-03, and PCB-07 because their hardware or test setup is outstanding.

## Scope

This analysis asks whether one VTarget PWM-to-voltage function can be used for the qualified population. The shared curve is the median DMM voltage at each PWM duty point, followed by piecewise-linear interpolation.

The source measurements are the board-specific files in `tests/test_results/`:

- `vtarget_PCB-01_measurements.csv`
- `vtarget_PCB-04_measurements.csv`
- `vtarget_PCB-05_measurements.csv`
- `vtarget_PCB-06_measurements.csv`
- `vtarget_PCB-08_measurements.csv`
- `vtarget_PCB-09_measurements.csv`
- `vtarget_PCB-10_measurements.csv`

The full-batch visualization, including the excluded boards, is available at:

- [vtarget_batch_common_curve.png](../../tests/test_results/vtarget_batch_common_curve.png)
- [vtarget_batch_common_curve.csv](../../tests/test_results/vtarget_batch_common_curve.csv)

## Results

| Board | DMM range | Points within +/-5% | Result |
|---|---:|---:|---|
| PCB-01 | 1338-4197 mV | 101/101 | PASS |
| PCB-04 | 1330-4206 mV | 32/101 | FAIL |
| PCB-05 | 1367-4200 mV | 40/101 | FAIL |
| PCB-06 | 1321-4173 mV | 60/101 | FAIL |
| PCB-08 | 1327-4200 mV | 40/101 | FAIL |
| PCB-09 | 1326-4199 mV | 40/101 | FAIL |
| PCB-10 | 1324-4190 mV | 40/101 | FAIL |

For the seven-board qualified population, the median shared curve produces:

```text
Mean absolute error: 3.731%
Worst absolute error: 31.953%
Points within +/-5%: 551/707 (77.93%)
```

The average curve is monotonic and covers approximately `1.32-4.20 V`, so it is useful as a general approximation. It is not accurate enough to replace per-board calibration when the acceptance requirement is +/-5%.

## Common-Curve Decision

A single shared firmware table is **not recommended** for all seven qualified boards. It would give reasonable typical behavior, but 156 of 707 measured points would still exceed the +/-5% requirement.

The closest subgroup is PCB-04, PCB-08, PCB-09, and PCB-10. Its median curve achieved:

```text
Mean absolute error: 0.662%
Worst absolute error: 1.885%
Points within +/-5%: 404/404 (100%)
```

That subgroup supports one shared table, but PCB-01, PCB-05, and PCB-06 do not follow it closely enough. The practical software choices are:

1. Keep the current PCB-01 table for the reference board only.
2. Use a board-specific calibration table selected by board MAC/serial number.
3. Use the four-board subgroup table only after confirming those boards share the same resistor, capacitor, MOSFET, and regulator population.
4. Use the seven-board median only as a coarse approximation with a wider tolerance, not as a +/-5% production control.

No firmware table was changed from this analysis because selecting the seven-board median would reduce accuracy for PCB-01 and other boards that currently have a better fit.

## Hardware Interpretation

The qualified boards respond over the full VTarget range, so Q1 is switching and the VTarget feedback path is active. Their remaining differences are consistent with variation in the analog control path:

- R1/R3 AP1117 feedback-divider values and tolerance
- R4 gate-series resistance
- R5 gate pull-down resistance
- C2 PWM-filter value and effective settling behavior
- Q1 threshold and $R_{DS(on)}$ variation
- AP1117 reference/dropout behavior
- Board load and supply conditions

The original fabrication BOM used the pre-rework values `R1=12k`, `R3=27k`, `R4=39k`, `R5=10k`, and `C2=10nF`. The reworked design, taken from the KiCad schematic and confirmed (2026-11-25) as fitted on **all** PCBs, is `R1=1.2k`, `R3=2.7k`, `R4=22k`, `R5=43k`, and `C2=10uF/25V`. The earlier `R4=100R` in the bench documentation and header was a documentation error and has been corrected.

**Consequence for this analysis:** because all boards share the same nominal component population, the board-to-board differences below cannot be explained by different rework states. See [Update 2026-11-25](#update-2026-11-25-all-boards-share-the-same-nominal-values).

The VTref jumper must be installed during every test. Without it, the DAP ADC can read near zero even when the external DMM measures the correct VTarget voltage.

## Recommended Next Step

Before changing firmware again, standardize the physical component population and verify the VTref jumper on every board. Then generate a calibration curve for each qualified board. Store one table per board identity and select it at runtime or during production programming.

A single common table should be accepted only when every board in the intended population achieves at least `95/101` points within +/-5%.

## Update 2026-09-08: Cluster Table Implemented for PCB-04/08/09/10

`main/vtarget_pwm.c` `VTARGET_CAL_TABLE` now holds a 25-point median curve built
from `vtarget_PCB-04_measurements.csv`, `vtarget_PCB-08_measurements.csv`,
`vtarget_PCB-09_measurements.csv`, and `vtarget_PCB-10_measurements.csv`
(duty and DMM voltage columns, median per duty index, 25 points evenly
selected while keeping the first/last duty). Re-checking the reduced table
against the full 4-board/101-point dataset (predicted duty from the table's
inverse interpolation, looked up against each board's own measured response)
gives:

```text
Mean absolute error: 0.489%
Worst absolute error: 1.927%
Points within +/-5%: 404/404 (100%)
```

New table range: `1326-4200 mV` (was `1343-4197 mV` from the PCB-01-only
table). `main/vtarget_pwm.h`, `components/DAP/source/DAP_vendor.c`, and the
`FW_CAL_TABLE` mirrors in `tests/pwm_vtarget_dmm.py` and
`tests/test_vtarget_pwm.py` were updated to match.

**This replaces the PCB-01 table as the firmware default.** PCB-01 itself is
no longer expected to pass its own +/-5% check with this table — see the
root-cause section below for why. Re-flash and re-run
`tests/pwm_vtarget_dmm.py --board-id PCB-XX` on a cluster board (04/08/09/10)
to confirm on real hardware before relying on retrospective analysis alone.

## Update 2026-11-25: All Boards Share the Same Nominal Values

Confirmed by the project owner: the component values in the KiCad schematic
(`R1=1.2k`, `R3=2.7k`, `R4=22k`, `R5=43k`, `C2=10uF/25V`) are fitted on **all**
PCBs, and the AP1117-ADJ is fitted everywhere. The `R4=100R` state described below
never existed on the boards; it was a documentation error.

This **rejects the "different/partial rework state" hypothesis** in the next section
(PCB-01 reworked at an intermediate state, PCB-03/07 partially or not reworked). The
remaining explanations for the board-to-board spread are:

- **Settling time:** with `R4=22k`, `R5=43k`, `C2=10uF` the gate filter has
  tau ≈ (R4‖R5)·C2 ≈ 145 ms (220 ms unloaded). The sweep scripts' default settle times
  for VTarget are 0.4 s (`pwm_vtarget_dmm.py`, `measure_vtarget_vb.py`) and 0.5 s
  (`test_vtarget_pwm.py`), i.e. only ~2.7–3.5 tau. Measured values then depend on
  the previous setpoint (hysteresis) and on how each board was swept.
  Re-measure with ≥ 1 s settle per point before drawing conclusions about individual boards.
- **Physical C2:** a 10uF/25V part does not fit the 0603 footprint in many cases; how it
  was fitted (package, flying leads, X5R/X7R DC-bias derating) can differ per board and
  changes the filter and the effective gate voltage (max ≈ 2.18 V with Q1 threshold at
  0.4–0.8 V, so Q1 operates in a steep region).
- **Component tolerance:** 0603 R1/R3/R4/R5 at 1–5 % and Q1 V_th spread move the transfer
  function, especially with the low gate drive.
- **VTref jumper / test setup** (e.g. PCB-02's ADC wiring defect) and possible
  hardware defects on PCB-03 and PCB-07 (restricted range 1878–4196 mV on PCB-07, 53–63 %
  worst error on PCB-03/07), which should be inspected directly.

Recommended next step: measure R1/R3/R4/R5 and C2 on PCB-03 and PCB-07 (the outliers),
then repeat the 101-point sweep on all boards with `--settle 1.0` and re-derive the
common table. Accept a shared table only if every board reaches ≥ 95/101 points.

## Root Cause (superseded hypothesis, kept for history): Why PCB-01/02/03/05/06/07 Don't Fit the Cluster Table

> **Superseded by the 2026-11-25 update above.** The component-population hypothesis
> in this section assumed boards differed in R1/R3/R4 values; all boards actually share
> the schematic values. The commit history table below remains accurate as a record of
> schematic changes.

Git history of `circuit_ESP32C3_Xiao/ESP32C3_Xiao_wireless_DAP.kicad_sch`
shows the VTarget analog values were changed **three times**, and the R4 gate
resistor value was accidentally reverted on the last pass:

| Commit | Date | R1 | R3 | R4 | R5 | C2 |
|---|---|---|---|---|---|---|
| `ce3967a` (original fabrication) | - | 12k | 27k | 39k | 10k | 10nF |
| `2ef4e5b` "Update ESP32-C3 VTarget hardware design" | - | 12k | 27k | 22k | 43k | 10uF/16V |
| `b58231a` "Calibrate VTarget PWM control range" | Aug 27 | 12k | 27k | **100R** | 43k | 10uF/25V |
| `de4efaf` "Update KiCad schematic, PCB, and iBOM" | Aug 31 | **1.2k** | **2.7k** | **22k** (reverted from 100R) | 43k | 10uF/25V |

`b58231a` is also the exact commit that produced the original PCB-01
calibration table (it touched `main/vtarget_pwm.c/.h`, `DAP_vendor.c`, and the
test scripts at the same time as changing R4 to 100R). This means **PCB-01
was measured and calibrated while the design called for R4=100R and R1/R3
still at their un-reworked 12k/27k values** — a different, incomplete rework
state than any other board. That explains why PCB-01's curve sits closest to
PCB-06 (1.278% pairwise) rather than the 04/08/09/10 cluster (6.029% pairwise
from PCB-04): PCB-01 was never rebuilt to the final R1=1.2k/R3=2.7k/R5=43k
state that the other boards received.

`de4efaf` (Aug 31) then reverted R4 from 100R back to 22k in the schematic
while adding the R1/R3 rework values — most likely an artifact of syncing the
KiCad files from an older working copy rather than an intentional design
decision, since `main/vtarget_pwm.h` and `docs/vtarget.md` were never updated
to match and still describe 100R. This left the repository in a
self-contradictory state (KiCad = 22k, docs = 100R) that has persisted since
Aug 31 and is the documented "open item" in
[VTARGET_REWORK_INSTRUCTIONS.txt](VTARGET_REWORK_INSTRUCTIONS.txt).

Because rework was performed on physical boards across several bench
sessions spanning this schematic churn, and because the schematic itself
doesn't tell you what was physically soldered onto any given unit, the most
likely explanation per board is:

- **PCB-01**: Reference/prototype unit, reworked and calibrated first at the
	`b58231a` (R4=100R, R1=12k, R3=27k) state — an intermediate rework that
	the rest of the batch did not receive. Root cause: incomplete rework,
	predates the R1/R3 change.
- **PCB-04, PCB-08, PCB-09, PCB-10**: Reworked together after `de4efaf`, most
	likely with a consistent R4 value (either physically 100R or 22k — bench
	measurement on one unit is needed to confirm which, since the schematic and
	docs disagree) plus R1=1.2k/R3=2.7k/R5=43k/C2=10uF. This is the only
	self-consistent group and is why they support one shared table.
- **PCB-06**: Fully reworked (responds across the full range) but pairs most
	closely with PCB-01 (1.278%), not the cluster. Likely reworked in the same
	early session as PCB-01, before the final R1/R3 values were settled, or
	built with R4 still at an intermediate value.
- **PCB-02, PCB-05**: Pair closely with each other (2.690%) but not with the
	cluster. Consistent with a separate rework batch/component reel, or with
	ordinary ±1-5% tolerance on 0603 R1/R3/R4/R5 parts pushing the transfer
	function shape away from the cluster's. PCB-02 additionally has a VTref
	sense-jumper/ADC wiring defect (see production summary) that is independent
	of the regulation root cause.
- **PCB-03, PCB-07**: Extreme outliers (53-63% worst error, restricted output
	range) that pair distantly with every other board. These are consistent
	with a **partial or missing rework** (e.g., R4/R5 changed but R1/R3 left at
	the original 12k/27k, or vice versa) rather than component tolerance —
	tolerance alone does not produce a 50%+ deviation or a truncated voltage
	range like PCB-07's 1878-4196 mV span.

This is a hypothesis built from the schematic history and the measured
curves; it has not been confirmed by physically measuring R1/R3/R4/R5 on
each board. That measurement is the recommended next step before reworking
or re-testing PCB-01, PCB-02, PCB-03, PCB-05, PCB-06, or PCB-07 again.

## References

- [VTarget rework instructions](VTARGET_REWORK_INSTRUCTIONS.txt)
- [VTarget firmware and interface documentation](../../docs/vtarget.md)
- [VTarget production results](../../tests/test_results/vtarget_production_summary.csv)
- [Batch common curve data](../../tests/test_results/vtarget_batch_common_curve.csv)
- [AP1117 adjustable regulator datasheet](https://www.diodes.com/assets/Datasheets/AP1117.pdf)
- [ESP-IDF v4.4.2 LEDC API reference](https://docs.espressif.com/projects/esp-idf/en/v4.4.2/esp32/api-reference/peripherals/ledc.html)
