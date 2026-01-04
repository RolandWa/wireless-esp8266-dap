# Schematic Design Rules Check (ERC) - Schematic Checklist (KiCad)

Goal: catch logical/electrical issues early, and produce a clean handoff to PCB layout with explicit constraints.

## 0. Workflow (when to run checks)
- [ ] **ERC early/often:** Run ERC during capture, not just at the end.
- [ ] **Annotate deliberately:** Re-annotate when adding blocks; avoid leaving duplicates.
- [ ] **Handoff readiness:** Before layout export, run ERC again and resolve (or formally waive) all issues.

## 1. Connectivity & ERC correctness
- [ ] **No unconnected pins:** Every intentionally-unused pin has an explicit No-Connect marker.
- [ ] **No single-node nets:** Investigate nets with only one pin; usually indicates a missed wire or wrong label.
- [ ] **No hidden net merges:** Confirm that global labels/power symbols aren’t unintentionally tying nodes together.
- [ ] **No power rail shorts:** Ensure different voltage rails are not shorted together (including through net-ties unless intended).
- [ ] **Pin-type mismatches:** Fix output-output conflicts, passive vs. power pin mistakes, etc.
- [ ] **Connector pin mapping sanity:** Verify pin numbers/orientation (pin 1 marking) matches the physical connector.

## 2. Clarity and maintainability (layout and review friendly)
- [ ] **Functional grouping:** Organize sheets/areas by function (power, MCU, I/O, debug, etc.).
- [ ] **Readable signal flow:** Prefer left-to-right flow for main paths; avoid spaghetti wiring.
- [ ] **Net naming:** Use descriptive net labels (not only “VCC”); this makes layout rule assignment easier later.
- [ ] **Notes for layout constraints:** Add explicit notes for placement/routing requirements (examples: “place Cx close to Ux VDD”, “diff pair”, “controlled impedance”, “keepout under antenna”).

## 3. Robustness / “what happens if?” checks
- [ ] **Floating inputs avoided:** Provide pull-ups/pull-downs on reset/boot straps and any externally-driven digital inputs that can float.
- [ ] **Power sequencing assumptions stated:** If mixed-voltage domains exist (3V3/5V), ensure interfaces are protected and assumptions are documented.
- [ ] **Protection where needed:** Consider ESD/TVS, series resistors, and current-limiting where connectors expose signals.
- [ ] **Fault behavior considered:** Identify what happens if a connector is unplugged, a line opens, or supply ramps slowly; avoid undefined states.

## 4. Component correctness
- [ ] **Values and units:** Verify resistor/capacitor values and units (k vs. ohm, uF vs. nF).
- [ ] **Voltage/current ratings:** Caps/regs/diodes/LED resistors meet expected operating conditions with margin.
- [ ] **Polarity/orientation:** Diodes, electrolytics, LEDs, IC pin 1 indicators are correct.
- [ ] **Decoupling completeness:** Every IC has local bypassing; bulk capacitance exists near power entry/regulators.
- [ ] **Footprint linkage:** Every symbol has the intended footprint assigned; new library parts checked against datasheets.

## 5. Metadata / release readiness
- [ ] **Title block updated:** Project name, revision, date.
- [ ] **BOM fields present:** Manufacturer/MPN (and your sourcing fields like LCSC/TME) filled for orderable items.

## 6. Regulatory-driven schematic checks (EMC + Safety Objectives + RED integration)

These schematic checks help ensure the design contains the right features/notes to support compliance evidence for a **USB-powered Wi‑Fi product** (radio equipment) under **RED 2014/53/EU**.

### 6.1 EMC (emissions + immunity) schematic checks
- [ ] **External connector protection defined:** For each connector pin that can be touched or connected by a user cable, define protection as applicable (TVS/ESD array, series resistors, common-mode choke).
- [ ] **USB interface network defined:** If USB is present, define the full network: ESD protection, any series resistors, common-mode choke (if used), shield strategy (if shielded connector).
- [ ] **Cable assumptions stated:** Add a note identifying typical cable type/length (unshielded consumer cable vs shielded) so test setup reflects reality.
- [ ] **No “mystery grounds”:** Document whether connector shield is tied to GND directly, via RC/ESD path, or left floating (and why).
- [ ] **Power entry filtering defined:** Define input bulk/decoupling at USB power entry and any ferrites/filters used for conducted noise control.

### 6.2 RED (radio module integration) schematic checks
- [ ] **Module identity recorded:** Record exact module variant/ordering code and hardware revision in the schematic notes/title block.
- [ ] **Module compliance evidence tracked:** Add fields or a note to attach module DoC/test summary and the vendor integration guide.
- [ ] **Integration constraints captured:** Add explicit schematic notes such as “antenna keepout mandatory per module integration guide” so PCB layout treats it as a requirement.
- [ ] **Firmware regulatory behavior noted:** Add a note to verify region/channel constraints and transmit power configuration is controlled by the module/SDK and not user-bypassable.

### 6.3 Safety objectives (USB SELV product) schematic checks
- [ ] **USB supply requirement documented:** Since the external USB adapter is not supplied, add a note for the manual/label: use a compliant SELV USB supply with the required voltage/current rating.
- [ ] **Overcurrent protection strategy defined:** Define fuse/polyfuse/current-limit behavior on USB VBUS as applicable.
- [ ] **Abnormal/fault conditions considered:** Document foreseeable faults (short on external pins, reverse connection where possible) and the intended safe behavior.
- [ ] **Thermal protection features used:** If regulators/DC-DC include thermal shutdown or current limit, document expected behavior under overload.

## References
- https://jlcpcb.com/blog/pcb-design-rules-best-practices
- https://www.bernini-design.ro/best-rules-for-a-good-electronic-board-design/
- https://www.protoexpress.com/blog/drc-pcb-manufacturing/
- https://www.youtube.com/@RobertFeranec
- https://www.youtube.com/@HansRosenberg74
- https://www.youtube.com/@easylogixpcb-investigator2804
- https://www.youtube.com/@ProtoexpressPCB