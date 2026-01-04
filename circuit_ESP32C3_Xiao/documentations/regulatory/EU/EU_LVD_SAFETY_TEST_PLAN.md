# Safety Test Plan (EU) — Safety Objectives for USB-Powered Wi‑Fi Product (RED 2014/53/EU)

## 1. Document control
- Project: 
- Product name / model: 
- HW revision: 
- FW revision: 
- Test plan version: 
- Date: 
- Author: 

## 2. Purpose
Define a product safety test plan and required evidence to support electrical safety objectives for a **USB-powered Wi‑Fi product** assessed under the Radio Equipment Directive **RED 2014/53/EU**.

Notes:
- USB-powered products are typically **SELV** and may fall outside the voltage scope of LVD. Safety objectives are still applicable under RED for radio products.
- This plan is written for a **USB-only** product and can be extended later if a mains-powered variant is created.

## 3. Scope
### 3.1 DUT definition
- Variant(s): 
- Enclosure: 
- Power source(s): 
  - SELV input: USB 5 V (external USB power adapter not included)
  - Mains input: None
- User access: consumer / professional
- Environment: indoor / outdoor / industrial

### 3.2 Safety standard route (lock selection)
Record the exact edition and any national deviations:
- EN IEC 62368-1 (ICT/multimedia equipment) — recommended for a USB programmer/debugger with Wi‑Fi

Supporting references as needed:
- IEC 60664-1 (insulation coordination)
- EN 60529 (IP rating), if claimed

## 4. References
- LVD 2014/35/EU: https://eur-lex.europa.eu/eli/dir/2014/35/oj
- RED 2014/53/EU: https://eur-lex.europa.eu/eli/dir/2014/53/oj
- CE marking principles: https://eur-lex.europa.eu/eli/reg/2008/765/oj

## 5. Safety requirements overview (what we will verify)
The plan verifies that the DUT does not present unacceptable risks related to:
- electric shock / energy hazards
- overheating / fire
- mechanical hazards related to electrical equipment
- hazards under reasonably foreseeable misuse / fault conditions
- markings and instructions for safe installation/use

## 6. Test environment
- Lab / location: 
- Ambient: temperature ____ °C, humidity ____ %RH
- Ventilation condition: 
- Mounting (table / enclosure / installed): 

## 7. Equipment list (fill in)
- DMM, oscilloscope, current probes
- Power supplies (USB 5 V source, programmable DC supply)
- Thermal measurement (thermocouples, IR camera)
- Environmental chamber (if used)
- Hipot / insulation resistance tester (if applicable)
- Touch-current / leakage-current measurement equipment (if applicable)

## 8. Pre-compliance design review (evidence to capture)
Before lab testing, archive these artifacts:
- Schematics + PCB layout + BOM
- Critical component list (protective components, insulation materials)
- Creepage/clearance assessment worksheet (if applicable)
- Risk assessment / hazard analysis
- User manual draft + label/rating plate draft

External USB power adapter (not supplied) evidence:
- Manual/label specifies required supply: SELV, limited power (as applicable), voltage/current rating, and acceptable connector/cable constraints
- Keep a record of at least one representative compliant USB supply used during testing (manufacturer/model) and its safety approvals/DoC (if available)

## 9. Test matrix
### 9.1 Construction / accessibility checks
| Check | Applicability | Evidence |
|---|---:|---|
| Sharp edges / accessible hazards | Yes | Photos + notes |
| Accessibility of hazardous voltages/energies | Yes | Probe checks + rationale |
| Enclosure integrity / openings | As applicable | Measurements |
| Marking presence (model, ratings, warnings) | Yes | Photo of label artwork |

### 9.2 Electrical safety tests (SELV / low-voltage products)
| Test | Typical method | Applicability | Pass/Fail basis |
|---|---|---:|---|
| Input power stability | Apply min/max USB/DC input | Yes | DUT functions, no overheating |
| Overcurrent / short behavior (external ports) | Short external outputs/ports as relevant | As applicable | No fire, no unsafe temps, recovers safely |
| Reverse polarity / misconnection (if possible) | Apply foreseeable misuse | As applicable | No unsafe condition |
| Accessible energy / hot surface check | Worst-case operation | Yes | Per chosen safety standard limits |

### 9.3 Thermal / fire-related
| Test | Conditions | Applicability | Evidence |
|---|---|---:|---|
| Temperature rise (normal) | Worst-case mode, steady-state | Yes | Thermocouple table + photos |
| Temperature rise (abnormal) | Simulated fault(s) per standard | As applicable | Thermocouple table + notes |
| Component derating review | Compare stresses vs datasheets | Yes | Derating table |

### 9.4 Electrical safety tests (mains-rated variant — not applicable for this product)
Not applicable for the current USB-only product. If a future variant includes AC mains input or an internal AC/DC supply, add the following (exact levels come from the chosen safety standard tables):

| Test | Typical note | Applicability | Evidence |
|---|---|---:|---|
| Dielectric strength (hipot) | Example-only: ~1500 Vac basic / ~3000 Vac reinforced | Optional | Hipot report |
| Insulation resistance | Example-only: 500 Vdc with min resistance criterion | Optional | IR report |
| Touch/leakage current | Measurement network per standard | Optional | Touch current report |

## 10. Functional criteria
Define what constitutes acceptable behavior during safety tests:
- Acceptable resets/restarts: 
- Acceptable temporary loss of function: 
- No-go conditions (always fail): smoke, fire, melted insulation, accessible hazardous voltage, unsafe touch temperature

## 11. Test evidence package (deliverables)
Minimum archive set:
- Completed safety test report with pass/fail summary
- Temperature rise table (sensor locations, steady-state definition)
- Fault-condition records (what was shorted/blocked, duration)
- Photos of test setup and thermocouple placement
- Label artwork and user manual safety section
- Risk assessment with mitigations linked to test evidence

## 12. Deviations / waivers
Record any deviations from the selected safety standard and justify.
- Deviations:
- Rationale:
- Risk impact:

## 13. Sign-off
- Prepared by: __________________  Date: __________
- Reviewed by: __________________  Date: __________
- Approved by: __________________  Date: __________

## References
- RED 2014/53/EU: https://eur-lex.europa.eu/eli/dir/2014/53/oj
- LVD 2014/35/EU (safety objectives reference context): https://eur-lex.europa.eu/eli/dir/2014/35/oj
- CE marking principles (Reg. (EC) 765/2008): https://eur-lex.europa.eu/eli/reg/2008/765/oj
- IEC webstore (for EN/IEC 62368-1 and related safety standards catalogs): https://webstore.iec.ch/
