# Regulatory / Compliance Documentation

This folder stores product requirements and checklists derived from regulations/standards (EU/CE, LVD, RED, RoHS; US/FCC; other regions later).

## Folder layout
- `EU/` — European Union regulatory requirements and CE-marking related documentation.
- `US/` — United States regulatory requirements (e.g., FCC).
- `ASIA/` — Placeholder for region-specific requirements (e.g., JP, CN, KR).
- `GLOBAL/` — Cross-region notes: definitions, common engineering controls, shared test methods.

## How to add a new requirement document
Use these conventions to keep documents searchable and consistent:

- **One document = one topic** (e.g., `EU_RED_RADIO_REQUIREMENTS.md`).
- **Start with scope** (what product types it applies to, what it does not apply to).
- **State inputs/assumptions** (power source, radio present, mains vs SELV, intended user).
- **Add a practical checklist** engineers can execute.
- **Add references** (prefer primary sources: EUR-Lex, FCC CFR, official guidance).

## Naming
- Use `REGION_TOPIC_DESCRIPTION.md`.
- Prefer uppercase region prefixes for fast filtering (`EU_`, `US_`).

## Important note
This repository documentation is intended to help engineering work and recordkeeping.
It is not legal advice. For products entering a regulated market, confirm obligations with the latest official texts and, when needed, compliance professionals.

## References
- EUR-Lex (EU law database): https://eur-lex.europa.eu/
- EU Blue Guide (implementation guidance for EU product rules): https://single-market-economy.ec.europa.eu/single-market/ce-marking/blue-guide_en
- FCC Equipment Authorization (USA): https://www.fcc.gov/oet/ea
