# EMC Test Plan (EU) — Radio Product EMC Evidence (RED 2014/53/EU)

## 1. Document control
- Project: 
- Product name / model: 
- HW revision: 
- FW revision: 
- Test plan version: 
- Date: 
- Author: 

## 2. Purpose
Define the EMC test plan and required evidence to support conformity for a **radio product** under the Radio Equipment Directive **RED 2014/53/EU**.

This plan focuses on the EMC evidence typically needed for a Wi‑Fi enabled product that uses a pre-certified module (for example, a XIAO ESP module) integrated into a final product.

## 3. Scope
This plan is intended for an electronics product similar to this project (USB-powered embedded device with digital clocks and optional Wi‑Fi/BLE).

### 3.1 DUT configurations covered
- Variant(s): 
- Enclosure: (open PCB / enclosure type) 
- Powering: (USB 5 V, external PSU model) 
- I/O cables: (lengths, shielded/unshielded) 
- Peripherals: (debug probe, cables, target board) 

### 3.2 Operating modes (worst-case)
Define modes that maximize emissions and stress immunity:
- Mode A (worst-case digital activity): 
- Mode B (wireless active, max throughput): 
- Mode C (idle/low power): 

## 4. References
- RED 2014/53/EU: https://eur-lex.europa.eu/eli/dir/2014/53/oj
- CE marking principles: https://eur-lex.europa.eu/eli/reg/2008/765/oj

### 4.1 Target EMC standards (lock selection for Wi‑Fi radio product)
Record the exact editions used:

Primary EMC standards for 2.4 GHz WLAN/Bluetooth products:
- EN 301 489-1 (EMC standard for radio equipment and services; common requirements)
- EN 301 489-17 (EMC standard for 2.4 GHz WLAN / Bluetooth and similar)

Immunity methods referenced by the above (commonly used):
- IEC 61000-4-2 (ESD)
- IEC 61000-4-3 (Radiated RF immunity)
- IEC 61000-4-4 (EFT/Burst)
- IEC 61000-4-6 (Conducted RF immunity)

Optional/conditional standards:
- If the final product also needs non-radio ICT emission/immunity classification for a specific market/customer requirement: EN 55032 / EN 55035.
- EN IEC 61000-3-2 / EN IEC 61000-3-3 apply only if the product includes an AC mains port or internal AC/DC (not expected for USB-only devices).

## 5. Test environment
- Test lab / location: 
- Ambient: temperature ____ °C, humidity ____ %RH
- Ground reference plane: Yes/No
- Test site: semi-anechoic / OATS / chamber

## 6. Equipment list (fill in)
- EMI receiver / spectrum analyzer: 
- LISN(s): 
- Current probe / clamp: 
- Antennas: 
- Immunity generator(s): ESD gun, EFT/burst generator, surge generator (if used), RF generator + amplifier
- Field probes and calibration: 

## 7. Functional performance criteria (Pass/Fail)
Define what “operates as intended” means during immunity tests.
- Essential functions: 
- Allowed degradations (IEC criteria):
  - Criteria A: 
  - Criteria B: 
  - Criteria C: 
- Data integrity requirements (logs, sessions): 

## 8. Test matrix
Record results in a separate test report; this plan defines the required tests.

### 8.1 Emissions
| Test | Standard method | Applicability | Notes |
|---|---|---:|---|
| Radiated emissions (30 MHz–1 GHz) | EN 301 489 / referenced methods | Yes | Consider >1 GHz where required by standard/product |
| Conducted emissions on AC mains (150 kHz–30 MHz) | CISPR/EN method | N/A | N/A for USB-only products (no AC mains port) |
| Conducted emissions on DC power port (if applicable) | CISPR/EN method | Optional | Depends on standard and port classification |

### 8.2 Immunity (basic set; residential/light-industrial intent)
| Test | Reference | Typical level (confirm by chosen standard) | Applicability | Notes |
|---|---|---:|---:|---|
| ESD | IEC 61000-4-2 | ±8 kV contact, ±15 kV air | Yes | Test accessible metal, I/O, enclosure seams |
| Radiated RF immunity | IEC 61000-4-3 | 3 V/m (res/light-industrial) | Yes | 80 MHz–1 GHz typical; verify required range |
| EFT/Burst | IEC 61000-4-4 | ±1 kV on DC power / I/O | Yes | Clamp to cables; direct coupling if required |
| Conducted RF immunity | IEC 61000-4-6 | 3 Vrms (res/light-industrial) | Optional | Mainly for products with long external cables |

### 8.3 Immunity (conditional)
| Test | Reference | Typical level (confirm by chosen standard) | Applicability | Notes |
|---|---|---:|---:|---|
| Surge | IEC 61000-4-5 | ±0.5–±1 kV (very installation-dependent) | Optional | Usually for AC mains or long external cables |
| Voltage dips/interruptions | IEC 61000-4-11 | Per standard table | N/A | AC mains only |

## 9. Test setup requirements
- Cable types and lengths shall be recorded and kept consistent.
- Worst-case mode definition shall be documented (firmware version + configuration).
- For radiated tests: define DUT orientation, table height, antenna polarization.
- For immunity: document injection points, contact points, and monitoring instrumentation.

## 10. Test evidence to archive (deliverables)
Minimum evidence package:
- Completed test report(s) with pass/fail summary
- Raw plots (emissions) and immunity test logs
- Calibration certificates (or lab statement)
- Setup photographs for each test
- DUT configuration record (photos, BOM variant, firmware hash)
- Written functional performance criteria and observed behavior

Module integration evidence (attach if available from module supplier):
- Module Declaration of Conformity (DoC) and/or RED test report summary
- Module integration guide (layout, antenna keep-out, grounding, shielding requirements)
- Evidence that the final product integration matches the module constraints (photos, PCB layout notes)

## 11. Deviations / waivers
Record any deviations from the selected standards and the technical rationale.
- Deviations:
- Risk assessment impact:

## 12. Sign-off
- Prepared by: __________________  Date: __________
- Reviewed by: __________________  Date: __________
- Approved by: __________________  Date: __________

## References
- RED 2014/53/EU: https://eur-lex.europa.eu/eli/dir/2014/53/oj
- CE marking principles (Reg. (EC) 765/2008): https://eur-lex.europa.eu/eli/reg/2008/765/oj
- ETSI standards search (for EN 301 489-1 / EN 301 489-17): https://www.etsi.org/standards
- IEC webstore (for IEC 61000-4-x methods): https://webstore.iec.ch/
