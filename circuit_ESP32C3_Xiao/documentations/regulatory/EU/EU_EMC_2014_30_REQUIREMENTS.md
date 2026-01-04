# EU EMC Directive 2014/30/EU — Requirements (Engineering Checklist)

## Purpose
Capture practical requirements and documentation artifacts typically needed when the **EMC Directive 2014/30/EU** applies to a product placed on the EU market.

This is an engineering aid, not legal advice. Always verify the latest consolidated text and applicable harmonised standards.

## When EMC Directive applies (typical)
The EMC Directive applies to many types of **apparatus** and **fixed installations** that may generate electromagnetic disturbance or be affected by it.

Important interactions:
- If the product is **radio equipment**, **RED 2014/53/EU** typically applies and includes EMC requirements; EMC Directive may not be the primary route.
- EMC Directive addresses **electromagnetic compatibility**, not general electrical shock/fire safety.

## Core EMC requirements (plain language)
A compliant product should:
- not generate electromagnetic disturbance above a level that prevents radio/telecom equipment and other apparatus from operating as intended, and
- have adequate immunity so it continues to operate as intended in the presence of expected electromagnetic disturbances.

## What to do (engineering checklist)
### 1) Define the product configuration
- Identify all variants that can affect emissions/immunity: enclosure, cable lengths, ports, antennas, PSU, clock frequencies.
- Define operating modes to test: Wi‑Fi on/off (if applicable), max throughput, worst-case switching activity.

### 2) Identify applicable harmonised EMC standards
- Select harmonised standards appropriate to the product type and environment (residential/light-industrial/industrial).
- Record the chosen standards + editions and any deviations.

## Harmonised standards commonly used for EMC (pick the right family)
The EMC Directive does not mandate one specific standard. In practice, many electronics products use one of these harmonised standard “families” (verify the current harmonised list in the EU Official Journal and confirm applicability to your product type):

### A) Multimedia / ICT equipment (common for USB/network devices)
- **EN 55032** — Electromagnetic compatibility of multimedia equipment (emissions)
- **EN 55035** — Electromagnetic compatibility of multimedia equipment (immunity)

### B) Generic EMC standards (when no product-family standard fits)
- **EN IEC 61000-6-1** — Immunity for residential, commercial and light-industrial environments
- **EN IEC 61000-6-2** — Immunity for industrial environments
- **EN IEC 61000-6-3** — Emission for residential, commercial and light-industrial environments
- **EN IEC 61000-6-4** — Emission for industrial environments

### C) Mains-related power quality (only if applicable)
If the product is powered from AC mains (directly or via an internal AC/DC), these may apply:
- **EN IEC 61000-3-2** — Harmonic current emissions (≤16 A/phase)
- **EN IEC 61000-3-3** — Voltage fluctuations / flicker (≤16 A/phase)

### 3) Design controls (common)
- grounding strategy and return paths
- shielding and enclosure seams (if applicable)
- input/output filtering and ESD protection
- clock routing, impedance control, reference planes
- cable/connector strategy

### 4) Verification and test evidence
Typical evidence to capture (product-dependent):
- conducted and radiated emissions
- radiated and conducted immunity
- ESD immunity
- EFT/burst, surge (as applicable)
- voltage dips/interruptions (for AC-mains equipment)

## Test evidence package (what to store) + typical test levels
Below is a practical checklist with **typical** levels used by common EMC standards. Exact levels depend on:
- environment class (residential/light-industrial vs industrial),
- port type (DC power vs signal I/O),
- whether the product is mains-powered,
- the chosen harmonised standard edition.

### Emissions (evidence)
- **Radiated emissions** report (typically 30 MHz–1 GHz; sometimes above 1 GHz if product clocks/radios require)
- **Conducted emissions** report for mains ports (typically 150 kHz–30 MHz) if applicable
- Test setup photos, cable lists/lengths, operating modes definition, firmware version

### Immunity (evidence)
- **ESD (IEC 61000-4-2)**
  - Typical: **±8 kV contact**, **±15 kV air** (common “consumer-ish” severity)
- **Radiated RF immunity (IEC 61000-4-3)**
  - Typical: **3 V/m** (residential/light-industrial) or **10 V/m** (industrial), 80 MHz–1 GHz (range depends on standard)
- **EFT/Burst (IEC 61000-4-4)**
  - Typical: **±1 kV** on DC power / I/O lines, **±2 kV** on AC mains (if applicable)
- **Surge (IEC 61000-4-5)** (mains-powered or long external cables)
  - Typical: **±0.5 kV to ±1 kV** line-to-line and/or line-to-earth (depends heavily on installation class)
- **Conducted RF immunity (IEC 61000-4-6)**
  - Typical: **3 Vrms** (residential/light-industrial) or **10 Vrms** (industrial), 150 kHz–80 MHz
- **Voltage dips/interruptions (IEC 61000-4-11)**
  - Applicable to **AC-mains powered** equipment (test points and percentages depend on standard)

### Pass/fail criteria (record explicitly)
For each test, document the acceptance criteria you used (typical IEC criteria A/B/C) and any product-specific functional performance criteria.

### 5) Documentation artifacts to keep
- product description and intended environment
- schematics, PCB layout, BOM
- test plan and test reports (including test setup photos)
- risk assessment / engineering rationale for worst-case modes
- user manual / installation instructions (especially cabling and grounding)
- EU Declaration of Conformity (EU DoC)

## EU Declaration of Conformity (DoC) — minimum expectations
The DoC is typically expected to include:
- product identification (model, type, batch/serial as applicable)
- manufacturer identity and address
- the directive(s) declared (here: 2014/30/EU)
- referenced standards/specifications
- authorized signatory, date/place

## References (primary sources)
- EMC Directive 2014/30/EU (EUR-Lex):
  - https://eur-lex.europa.eu/eli/dir/2014/30/oj
- CE marking principles (general):
  - https://eur-lex.europa.eu/eli/reg/2008/765/oj
- Market surveillance / compliance of products:
  - https://eur-lex.europa.eu/eli/reg/2019/1020/oj
