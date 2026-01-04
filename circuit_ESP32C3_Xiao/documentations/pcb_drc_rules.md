# PCB Design Rules Check (DRC) - PCB Layout Checklist (KiCad)

This checklist is meant to be run repeatedly during layout (online DRC) and again before generating fabrication/assembly outputs (full DRC + external DFM).

## 0. Workflow (when to run checks)
- [ ] **Define rules early:** Set manufacturer-driven constraints before routing (clearances, min track/via/drill, mask/silk limits, board edge clearances).
- [ ] **Keep DRC “online”:** Fix violations immediately while placing/routing.
- [ ] **Before final DRC:** Refill zones (or enable “refill zones before DRC”) so results match final copper.
- [ ] **Final DRC run:** Run a full DRC and export/save the report.
- [ ] **External DFM (recommended):** Upload generated Gerbers/Drill to your fab/assembler’s DFM tool as a second independent check.

## 1. Manufacturer / DFM Constraints (board can be fabricated)
- [ ] **Use fab’s published capabilities:** Minimum trace/space, minimum drill, minimum annular ring, solder mask rules, copper-to-edge, slot/cutout rules.
- [ ] **Copper clearances:** Trace-to-trace, trace-to-pad, pad-to-pad meet the chosen capability class.
- [ ] **Track widths vs. current:** Power rails sized for current and copper weight; internal layers (if any) usually need wider tracks for the same current.
- [ ] **Via/drill sizes:** Drill diameter and finished hole sizes meet fab limits; avoid “exotic” sizes unless required.
- [ ] **Annular ring:** Ensure adequate ring around plated holes/vias to prevent drill breakout.
- [ ] **Hole-to-copper / hole-to-hole:** Maintain clearance around drills and between adjacent drills.
- [ ] **Solder mask sliver / dam:** Ensure mask between adjacent pads is manufacturable; avoid tiny slivers that will wash out.
- [ ] **Solder mask expansion:** Pads have correct mask openings (avoid mask covering pads; avoid excessive exposure causing bridging).
- [ ] **Silkscreen constraints:** Minimum line width/text size; silk-to-mask clearance; no silk on pads.
- [ ] **Board outline validity:** Outline is closed/continuous; any internal cutouts/slots are correctly defined on the proper layer.
- [ ] **Copper-to-edge:** Traces/zones keep the required distance from routed edges/V-cuts.

## 2. Assembly / DFA Constraints (board can be assembled)
- [ ] **Footprints verified:** New/edited footprints match the component datasheet (pad sizes, courtyard, pin 1, polarity marks).
- [ ] **Component spacing:** Sufficient room for pick-and-place, rework access, and hand soldering where expected.
- [ ] **Orientation consistency:** Polarized parts oriented consistently where practical (reduces assembly errors).
- [ ] **Fiducials:** Provide board-level fiducials (and local ones for fine-pitch if required by assembler).
- [ ] **Test points (if required):** Accessible probe points for critical rails/signals; avoid placing them under tall parts.
- [ ] **Thermal reliefs / plane connections:** Pads on large pours have suitable thermal reliefs to avoid cold joints.

## 3. Electrical correctness (layout matches schematic intent)
- [ ] **Schematic/PCB parity:** Run DRC with “schematic parity”/connectivity checks enabled; resolve unconnected pads/incorrect net ties.
- [ ] **No unintended shorts:** Especially between power rails and GND and between adjacent fine-pitch pins.
- [ ] **No unintended “antennas”:** Remove dead-end stubs and stray copper islands not tied solidly to GND.

## 4. Signal integrity / EMI / power integrity (performance-focused checks)
- [ ] **Solid reference plane:** High-speed/fast-edge signals route over a continuous reference plane; avoid crossing plane splits.
- [ ] **Return path continuity:** Confirm return currents are not forced into large loops by breaks, voids, or stitching gaps.
- [ ] **Crosstalk control:** For long parallel runs, increase spacing (rule of thumb: keep-to-keep separation multiple of trace width when feasible).
- [ ] **Differential pairs:** Consistent spacing/coupling, symmetric routing, length matching/skew within requirement, avoid vias or use them symmetrically.
- [ ] **Vias used intentionally:** Minimize unnecessary layer changes (vias add inductance and manufacturing complexity).
- [ ] **Decoupling placement:** Bypass capacitors placed close to IC power pins with short, low-inductance connections to power and ground.
- [ ] **Planes and bottlenecks:** Check for narrow necks in power/ground pours that increase impedance and heat.
- [ ] **Stitching (when needed):** Stitch ground near connectors, around board edges (EMI), and near plane transitions.

## 5. Mechanical / 3D sanity
- [ ] **Connector fit:** Keepouts and mechanical alignment checked; mating connectors have clearance.
- [ ] **Mounting holes:** Copper keepouts where required; verify washer/screw head clearance.
- [ ] **3D check:** Verify component heights, collisions, and enclosure constraints.

## 6. Regulatory-driven layout checks (EMC + Safety Objectives + RED integration)

These are practical PCB-layout checks that support EU compliance evidence for a **USB-powered Wi‑Fi product** (radio equipment) under **RED 2014/53/EU**, including EMC performance and safety objectives.

### 6.1 EMC (emissions + immunity) layout checks
- [ ] **ESD/Surge entry control (connectors):** Place ESD parts (TVS arrays, spark gaps if used) physically close to the connector pins they protect.
- [ ] **Shortest ESD return path:** Ensure protected lines have a low-inductance return to the reference plane (short trace + nearby stitching vias). Avoid routing ESD current through sensitive ground islands.
- [ ] **Common-mode noise control:** If required, place common-mode chokes close to the connector (USB/high-speed I/O) with a continuous return plane under/near the choke.
- [ ] **Keep loop areas small:** Minimize high di/dt loops (DC/DC switch loop, input cap loop, return loops for fast edges).
- [ ] **Reference plane continuity:** Fast-edge nets (USB D+/D-, clocks, SPI at high edge rates) must not cross plane splits/voids.
- [ ] **Ground stitching near transitions:** Where return path continuity is threatened (layer changes, cutouts), add stitching vias to keep the return current local.
- [ ] **Edge stitching (when appropriate):** Consider ground stitching vias along the board edge and near connectors to reduce edge radiation (avoid violating antenna keepouts).
- [ ] **No accidental antennas:** Avoid long unterminated stubs, thin “whiskers” of copper, and isolated copper islands.

### 6.2 RED (radio module integration) layout checks
For products using a pre-certified module (e.g., Seeed XIAO ESP module), the final product must still respect the module’s RF integration constraints.

- [ ] **Antenna keepout enforced:** Respect the module vendor keepout (no copper, no components, no ground pour) under/around the antenna region as specified by the manufacturer.
- [ ] **Antenna-to-edge/enclosure clearance:** Ensure adequate clearance from metal, batteries, shields, and enclosure features that can detune or block the antenna.
- [ ] **Noisy nets kept away:** Keep DC/DC switching nodes, high-speed clocks, and long digital buses away from the antenna region.
- [ ] **Ground strategy near antenna:** Follow the module guidance (some modules require ground under certain regions; many require no ground under the antenna). Do not improvise pours under antenna without a datasheet-backed rule.
- [ ] **RF test access (if required):** If the module requires a test pad/jumper configuration, keep it accessible.

### 6.3 Safety objectives (USB SELV product) layout checks
Even for SELV products, capture layout evidence that reduces safety risk.

- [ ] **VBUS protection and trace sizing:** Verify USB 5 V (VBUS) routing, fusing/current limiting, and trace widths for worst-case current.
- [ ] **Thermal risk review:** Identify hot components (LDO/DC-DC/USB power path) and ensure copper heat spreading does not create hazardous touch temperatures at expected user-accessible surfaces.
- [ ] **Creepage/clearance sanity (SELV):** Ensure reasonable spacing between VBUS and sensitive low-level signals, and avoid tight spacing that increases short risk due to contamination/flux.
- [ ] **No exposed hazardous conductors:** If any conductive surfaces are user-accessible, confirm they are tied to the correct reference and not floating in a way that increases ESD susceptibility.

## References
- https://www.eevblog.com/forum/beginners/pcb-design-rules/?all
- https://www.protoexpress.com/blog/drc-pcb-manufacturing/
- https://www.bernini-design.ro/best-rules-for-a-good-electronic-board-design/
- https://resources.altium.com/p/master-your-pcb-design-workflow-with-online-design-rule-checking
- https://jlcpcb.com/blog/pcb-design-rules-best-practices
- https://www.youtube.com/@RobertFeranec
- https://www.youtube.com/@HansRosenberg74
- https://www.youtube.com/@easylogixpcb-investigator2804
- https://www.youtube.com/@ProtoexpressPCB