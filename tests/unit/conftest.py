"""pytest setup for the VTarget unit tests (no hardware needed).

Run from the repository root:   python -m pytest tests/unit -v
(Do not run `pytest tests/` - the other scripts there need hardware.)
"""
import os
import re
import sys

UNIT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(UNIT_DIR)
REPO = os.path.dirname(TESTS_DIR)
SCRIPTS_DIR = os.path.join(REPO, "circuit_ESP32C3_Xiao", "scripts")

for path in (TESTS_DIR, SCRIPTS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)


def parse_c_points(c_source_text, array_name):
    """Return [(duty, mv), ...] of ``static const vtarget_cal_point_t <array_name>[] = {...};``."""
    m = re.search(
        r"vtarget_cal_point_t\s+" + re.escape(array_name) + r"\[\]\s*=\s*\{(.*?)\};",
        c_source_text,
        flags=re.S,
    )
    assert m, f"array {array_name} not found"
    return [(int(d), int(v)) for d, v in re.findall(r"\{\s*(\d+)\s*,\s*(\d+)\s*\}", m.group(1))]


def read_text(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as f:
        return f.read()
