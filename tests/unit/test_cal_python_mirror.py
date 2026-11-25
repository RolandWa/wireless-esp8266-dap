"""The Python mirrors of the firmware calibration must stay in sync with the C table."""
import ast
import re

import pytest

import vtarget_cal as py_cal
from conftest import parse_c_points, read_text

C_SRC = read_text("main", "vtarget_cal.c")
C_CLUSTER = parse_c_points(C_SRC, "CLUSTER_POINTS")


def test_python_table_equals_firmware_cluster_table():
    assert py_cal.FW_CAL_TABLE == C_CLUSTER


def test_range_constants_match_firmware():
    assert py_cal.VTARGET_MAX_MV == C_CLUSTER[0][1] == 4200
    assert py_cal.VTARGET_MIN_MV == C_CLUSTER[-1][1] == 1326
    assert py_cal.DUTY_MIN == C_CLUSTER[0][0] == 358
    assert py_cal.DUTY_MAX == C_CLUSTER[-1][0] == 982


@pytest.mark.parametrize("script", ["pwm_vtarget_dmm.py"])
def test_script_mirror_tables_equal_firmware(script):
    """Scripts that carry their own FW_CAL_TABLE copy must match (parsed, not imported)."""
    tree = ast.parse(read_text("tests", script))
    tables = [
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "FW_CAL_TABLE" for t in node.targets)
    ]
    assert len(tables) == 1, f"{script}: expected exactly one FW_CAL_TABLE"
    assert [tuple(p) for p in tables[0]] == C_CLUSTER


def test_test_vtarget_pwm_range_constants_match_firmware():
    text = read_text("tests", "test_vtarget_pwm.py")
    lo = int(re.search(r"^_VTARGET_MIN_MV\s*=\s*(\d+)", text, flags=re.M).group(1))
    hi = int(re.search(r"^_VTARGET_MAX_MV\s*=\s*(\d+)", text, flags=re.M).group(1))
    assert (lo, hi) == (C_CLUSTER[-1][1], C_CLUSTER[0][1])


def test_no_script_still_uses_the_old_linear_range():
    """1250-5000 mV was the pre-calibration range; the firmware rejects it now."""
    for script in ("read_vtarget_tcp.py", "test_xiao_usb.py", "test_vtarget_linearity.py",
                   "measure_vtarget_vb.py", "sweep_pwm_vb.py", "measure_pwm_vb.py"):
        text = read_text("tests", script)
        assert not re.search(r"\b1250\b", text), f"{script} still mentions 1250 mV"


# ------------------------------------------------------------------ behaviour

@pytest.mark.parametrize("mv, duty", [(4200, 358), (3300, 726), (2500, 801), (1800, 859), (1326, 982)])
def test_mv_to_duty_matches_known_firmware_values(mv, duty):
    # same integer interpolation as vtarget_cal_mv_to_duty (values also asserted in the C tests)
    assert py_cal.mv_to_duty(mv) == duty


def test_mv_to_duty_clamps_outside_the_table():
    assert py_cal.mv_to_duty(5000) == 358
    assert py_cal.mv_to_duty(0) == 982


def test_table_points_are_exact():
    for duty, mv in py_cal.FW_CAL_TABLE:
        assert py_cal.mv_to_duty(mv) == duty
        assert py_cal.duty_to_mv(duty) == mv


def test_duty_to_mv_clamps_to_reachable_window():
    assert py_cal.duty_to_mv(0) == 4200
    assert py_cal.duty_to_mv(1023) == 1326


def test_roundtrip_within_one_duty_step():
    for mv in range(py_cal.VTARGET_MIN_MV, py_cal.VTARGET_MAX_MV + 1):
        assert abs(py_cal.duty_to_mv(py_cal.mv_to_duty(mv)) - mv) <= 15


def test_duty_pct_helpers_stay_inside_the_window():
    assert not py_cal.reachable_duty_pct(0)
    assert not py_cal.reachable_duty_pct(100)
    assert py_cal.reachable_duty_pct(50)
    assert py_cal.reachable_duty_pct(py_cal.DUTY_MIN_PCT)
    assert py_cal.reachable_duty_pct(py_cal.DUTY_MAX_PCT)
    assert py_cal.duty_pct_to_mv(0) == 4200      # clamped
    assert py_cal.duty_pct_to_mv(100) == 1326    # clamped
    mvs = [py_cal.duty_pct_to_mv(p) for p in range(35, 96, 5)]
    assert mvs == sorted(mvs, reverse=True)
