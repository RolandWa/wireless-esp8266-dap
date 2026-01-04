# EU Low Voltage Directive (LVD) 2014/35/EU — Requirements (Engineering Checklist)

## Purpose
Capture the practical requirements and documentation artifacts typically needed when the **Low Voltage Directive (LVD) 2014/35/EU** applies to a product placed on the EU market.

This is an engineering aid, not legal advice. Always verify the latest consolidated text and applicable harmonised standards.

## When LVD applies (scope trigger)
LVD applies to **electrical equipment designed for use with a voltage rating** within:
- **50–1000 V AC**, or
- **75–1500 V DC**

If your product is below these voltage ratings (e.g., USB-powered SELV), LVD may not be the primary directive by voltage. However:
- If the product contains intentional radio, **RED 2014/53/EU** typically applies and includes safety objectives aligned with LVD safety objectives (without LVD voltage limits).

## What LVD is trying to achieve
LVD focuses on **electrical safety** and requires that electrical equipment is designed and manufactured so it does not endanger the safety of persons, domestic animals, or property when properly installed and maintained and used as intended.

Practically, this means controlling hazards such as:
- electric shock and energy hazards
- excessive temperatures / fire hazards
- mechanical hazards caused by electrical equipment
- risks under reasonably foreseeable fault conditions

## What to do (engineering checklist)
### 1) Define the product as placed on the market
- Exact model/variants, enclosure, connectors, PSU type, maximum ratings.
- Intended environment (home/industrial), user type, installation method.

### 2) Identify applicable harmonised standards
- Choose standards appropriate to the product category (examples often include IEC/EN 62368-1 or IEC/EN 61010-1 depending on product type, but verify what is harmonised and applicable for your product).
- Record the chosen standards + editions and any deviations.

## Harmonised standards commonly used for LVD (pick the right product family)
LVD compliance is typically demonstrated by applying an appropriate **product safety standard**. Common examples (verify what is harmonised and applicable to your product category):

### A) Audio/Video + ICT equipment (common for USB/networked devices)
- **EN IEC 62368-1** — Audio/video, information and communication technology equipment — Safety requirements

### B) Measurement / control / laboratory equipment
- **EN 61010-1** — Safety requirements for electrical equipment for measurement, control, and laboratory use

### C) Household / consumer appliances (when applicable)
- **EN 60335-1** — Household and similar electrical appliances — Safety (general requirements)

### Supporting / frequently referenced safety standards
Depending on the product, you may also need (or your chosen product standard will reference):
- **IEC 60664-1** (often adopted as EN) — Insulation coordination (creepage/clearance rules)
- **EN 60529** — IP code (ingress protection), if you claim an IP rating

For this project’s typical form factor (USB-powered, ICT-style device), **EN IEC 62368-1** is often the first standard to evaluate, but confirm the intended use category.

### 3) Design controls to address key hazards
Typical controls/evidence areas:
- insulation system, creepage/clearance, spacing, material ratings
- protective earth / protective bonding (if applicable)
- thermal design and temperature rise limits
- component derating and selection of protective parts
- abnormal operation / single fault conditions
- markings and instructions (ratings, installation, warnings)

### 4) Verification and test evidence
Store evidence appropriate to your standard and product:
- dielectric strength / hipot (if applicable)
- leakage current / touch current (if applicable)
- temperature rise measurements (normal and abnormal)
- overload/short-circuit behavior and protective device operation
- mechanical and enclosure checks relevant to safety

## Test evidence package (what to store) + typical test levels
Safety “levels” depend strongly on:
- rated voltage and insulation type (basic / reinforced),
- pollution degree, material group, overvoltage category,
- whether the product is mains-powered or SELV-only,
- the specific product safety standard (e.g., EN IEC 62368-1 vs EN 61010-1).

Use the levels defined by the chosen standard. The items below are a practical checklist; where numbers are shown they are **typical examples** seen for mains-rated equipment and must be verified against the standard tables.

### Safety construction evidence
- Schematics + PCB layout showing insulation barriers, spacing, protective parts
- Creepage/clearance calculation worksheet (with assumptions: PD, OVC, material group)
- Critical components list (fuses, optos, Y-caps, transformers, insulation materials)
- Mechanical drawings for enclosure and accessibility checks

### Electrical safety tests (examples)
- **Dielectric strength / hipot** (if required)
  - Typical examples for mains equipment: ~**1500 Vac** (basic insulation) / ~**3000 Vac** (reinforced) for 60 s (example only)
- **Insulation resistance** (if required)
  - Typical example: test at **500 Vdc** with a minimum resistance criterion (varies by standard)
- **Touch current / leakage current** (if required)
  - Limits and measurement networks are defined by the product safety standard

### Thermal / fire-related evidence
- Temperature rise test report (worst-case modes, ambient conditions)
- Abnormal operation / single fault condition evaluation (shorts, overloads, blocked vents if applicable)
- Materials/flammability evidence where required by the standard (often via component datasheets/certifications)

### Instructions / markings evidence
- Ratings label artwork (voltage/current, model, warnings)
- User manual safety section (installation, environmental limits, PSU requirements)

### If the product is SELV-only (e.g., USB-powered)
- Document the SELV input source assumptions (external PSU certification/ratings)
- Focus evidence on overheating/fire risks, accessible energy, and safe operation under faults
- Some hipot/leakage tests may become “not applicable”; record the rationale and the standard clause basis

### 5) Documentation artifacts to keep
- Product description (including ratings)
- schematics, PCB layout, BOM
- critical component list (safety-relevant components and their specs)
- risk assessment / hazard analysis
- test plan and test reports
- user manual and safety instructions
- labeling artwork (ratings, warnings)
- EU Declaration of Conformity (EU DoC)

## EU Declaration of Conformity (DoC) — minimum expectations
The DoC is typically expected to include:
- product identification (model, type, batch/serial as applicable)
- manufacturer identity and address
- the directive(s) declared (here: 2014/35/EU)
- referenced standards/specifications
- authorized signatory, date/place

## Marking
- Follow CE-marking rules from applicable EU legislation (see Regulation (EC) 765/2008 for general principles).
- Ensure product identification and traceability markings are consistent with the technical file.

## References (primary sources)
- LVD 2014/35/EU (EUR-Lex):
  - https://eur-lex.europa.eu/eli/dir/2014/35/oj
- CE marking principles (general):
  - https://eur-lex.europa.eu/eli/reg/2008/765/oj
- Market surveillance / EU economic operator concepts (often relevant for making documents available):
  - https://eur-lex.europa.eu/eli/reg/2019/1020/oj
