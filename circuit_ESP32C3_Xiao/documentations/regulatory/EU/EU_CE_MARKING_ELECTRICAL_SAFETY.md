# EU CE Marking & Electrical Safety (LVD / RED / EMC / RoHS)

## Purpose
This document is a practical engineering-facing summary of:
- what CE marking means in the EU framework,
- which common EU acts apply to electronic products,
- what “electrical safety” typically means for design + evidence,
- what to keep in the technical documentation file.

This is not legal advice. Always verify the latest consolidated texts and the latest list of harmonised standards.

## What CE marking is (and is not)
- **CE marking** is the manufacturer’s declaration that the product conforms to **applicable EU Union harmonisation legislation**.
- CE marking is **not** a “certificate” issued by the EU or by customs.

General rules and principles for CE marking are set in **Regulation (EC) 765/2008**.

## Quick applicability guide (common for electronics)
Use the product that is actually placed on the market (final enclosure, PSU, radios enabled, accessories).

### 1) Does the product contain intentional radio?
Examples: Wi‑Fi / BLE / 802.15.4 / LoRa.
- If **yes**: **RED 2014/53/EU** normally applies.
  - RED includes safety objectives aligned with the LVD safety objectives **without being limited by the LVD voltage ranges**.
  - RED also includes EMC and radio spectrum requirements.

### 2) If it is not radio equipment
- **EMC 2014/30/EU** often applies (EMC performance only; not “shock/fire safety”).
- **LVD 2014/35/EU** applies when the equipment is **rated** within:
  - **50–1000 VAC** or
  - **75–1500 VDC**

### 3) Hazardous substances
- **RoHS 2011/65/EU** typically applies to electrical and electronic equipment (EEE) placed on the EU market.

## “Electrical safety” — what it usually covers (design intent)
Electrical safety evidence commonly addresses (product-dependent):
- **Shock protection**: insulation system, protective earth (if used), accessible part limits.
- **Fire / overheating / energy hazards**: component temperature rise, fault conditions, fusing/limiting.
- **Mechanical safety interacting with electrical**: sharp edges, enclosure integrity, creepage/clearance.
- **Abnormal operation**: short circuits, stalled loads, overvoltage, misconnection scenarios.
- **Instructions and markings**: safe installation, intended PSU, environmental limits.

For low-voltage, USB-powered devices (SELV), LVD may not be in scope by voltage, but safety obligations can still exist under RED (if radio) and under general product safety expectations.

## Conformity workflow (practical)
Typical high-level steps:
1. Identify **applicable EU legislation** (RED vs EMC/LVD; RoHS, etc.).
2. Choose **harmonised standards** (or other technical specifications) appropriate for the product.
3. Perform evaluation/testing and keep evidence.
4. Compile **technical documentation**.
5. Draft and sign the **EU Declaration of Conformity (EU DoC)**.
6. Apply CE marking per applicable rules.

## Technical documentation (what to keep)
A typical technical file set (varies by directive/product) includes:
- Product description, variants, intended use, pictures.
- Schematics, PCB layout, BOM, assembly drawings.
- Risk assessment / hazard analysis.
- Test plans and test reports (safety, EMC, radio where applicable).
- Labeling and user instructions.
- Traceability: part specs for critical safety components.
- Copy of EU DoC and version history.

## Market surveillance & EU-based economic operator
EU market surveillance rules are strengthened by **Regulation (EU) 2019/1020**.
In particular, it introduces requirements (for many product families) that there is an **economic operator established in the EU** responsible for certain compliance tasks (e.g., keeping the DoC and making technical documentation available to authorities upon request).

## References (primary sources)
- CE marking principles: Regulation (EC) 765/2008
  - https://eur-lex.europa.eu/eli/reg/2008/765/oj
- Market surveillance / compliance of products: Regulation (EU) 2019/1020
  - https://eur-lex.europa.eu/eli/reg/2019/1020/oj
- Low Voltage Directive (LVD): Directive 2014/35/EU
  - https://eur-lex.europa.eu/eli/dir/2014/35/oj
- EMC Directive: Directive 2014/30/EU
  - https://eur-lex.europa.eu/eli/dir/2014/30/oj
- Radio Equipment Directive (RED): Directive 2014/53/EU
  - https://eur-lex.europa.eu/eli/dir/2014/53/oj
- RoHS: Directive 2011/65/EU
  - https://eur-lex.europa.eu/eli/dir/2011/65/oj

## Optional guidance (non-binding, but helpful)
- European Commission “Blue Guide” (implementation guidance for EU product rules)
  - https://single-market-economy.ec.europa.eu/single-market/ce-marking/blue-guide_en
