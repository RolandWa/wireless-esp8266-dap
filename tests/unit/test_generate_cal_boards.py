"""Tests for circuit_ESP32C3_Xiao/scripts/generate_vtarget_cal_boards.py."""
import csv
import os

import pytest

import generate_vtarget_cal_boards as gen
from conftest import REPO, parse_c_points, read_text

CSV_DIR = os.path.join(REPO, "tests", "test_results")
OUT_C = os.path.join(REPO, "main", "vtarget_cal_boards.c")


# ---------------------------------------------------------------- clean_curve

def test_clean_curve_drops_points_that_do_not_fall():
    pts = [(100, 4000.2), (200, 3000.0), (300, 3000.4), (400, 3100.0), (500, 2000.0)]
    assert gen.clean_curve(pts) == [(100, 4000), (200, 3000), (500, 2000)]


def test_clean_curve_result_is_strictly_decreasing():
    noisy = [(d, 4000 - d + (7 if d % 3 == 0 else 0)) for d in range(0, 300, 5)]
    out = gen.clean_curve(noisy)
    assert all(b[1] < a[1] for a, b in zip(out, out[1:]))
    assert all(b[0] > a[0] for a, b in zip(out, out[1:]))


# --------------------------------------------------------------- reduce_curve

def _linear(n=101):
    return [(358 + i * 6, 4200 - i * 28) for i in range(n)]


def test_reduce_keeps_end_points_and_sorts():
    pts = [(d, int(4200 - ((d - 358) / 624) ** 1.5 * 2800)) for d in range(358, 983, 6)]
    sel, _ = gen.reduce_curve(gen.clean_curve(pts), tol_mv=6, max_points=32)
    assert sel[0] == pts[0] and sel[-1][0] == pts[-1][0]
    assert sel == sorted(sel)


def test_reduce_linear_curve_needs_only_the_end_points():
    sel, err = gen.reduce_curve(_linear(), tol_mv=1, max_points=32)
    assert len(sel) == 2
    assert err <= 1


def test_reduce_respects_tolerance_and_max_points():
    pts = gen.clean_curve([(d, 4200 - (d - 358) ** 2 // 90) for d in range(358, 983, 3)])
    sel, err = gen.reduce_curve(pts, tol_mv=3, max_points=64)
    assert err <= 3
    capped, capped_err = gen.reduce_curve(pts, tol_mv=0.1, max_points=6)
    assert len(capped) == 6
    assert capped_err > 0.1                      # cap reached before the tolerance


def test_reduce_error_is_measured_against_the_selected_curve():
    pts = gen.clean_curve([(d, 4200 - (d - 358) ** 2 // 90) for d in range(358, 983, 3)])
    sel, err = gen.reduce_curve(pts, tol_mv=5, max_points=32)
    worst = max(abs(gen.interp(sel, d) - v) for d, v in pts)
    assert worst == pytest.approx(err)


# ------------------------------------------------------------- real CSV data

@pytest.fixture(scope="module")
def tables():
    return gen.build_tables(CSV_DIR)


def test_a_table_exists_for_every_measured_board(tables):
    boards = {gen.load_board_curve(os.path.join(CSV_DIR, f))[0]
              for f in os.listdir(CSV_DIR) if f.startswith("vtarget_PCB-") and f.endswith("_measurements.csv")}
    assert set(tables) == boards
    assert len(boards) >= 10


def test_every_generated_table_is_valid(tables):
    for board, (pts, err, _src) in tables.items():
        assert 2 <= len(pts) <= gen.DEFAULT_MAX_POINTS, board
        assert all(b[0] > a[0] for a, b in zip(pts, pts[1:])), board         # duty ascending
        assert all(b[1] < a[1] for a, b in zip(pts, pts[1:])), board         # voltage descending
        assert all(0 <= d <= 1023 for d, _ in pts), board
        assert err <= gen.DEFAULT_TOL_MV + 1e-9, board


def test_generated_tables_follow_the_measurements(tables):
    for board, (pts, _err, src) in tables.items():
        _b, raw = gen.load_board_curve(os.path.join(CSV_DIR, src))
        worst = max(abs(gen.interp(pts, d) - v) for d, v in raw)
        assert worst <= 10, f"{board}: {worst:.1f} mV"


def test_committed_c_file_is_up_to_date_with_the_csv_data():
    expected = gen.render(gen.build_tables(CSV_DIR), gen.DEFAULT_TOL_MV, gen.DEFAULT_MAX_POINTS)
    actual = read_text("main", "vtarget_cal_boards.c").replace("\r\n", "\n")
    assert actual == expected, "vtarget_cal_boards.c is stale - run generate_vtarget_cal_boards.py"


def test_committed_c_tables_equal_the_generated_points(tables):
    text = read_text("main", "vtarget_cal_boards.c")
    for board, (pts, _e, _s) in tables.items():
        assert parse_c_points(text, board.replace("-", "_") + "_POINTS") == pts


def test_generation_is_deterministic():
    a = gen.render(gen.build_tables(CSV_DIR), 6.0, 32)
    b = gen.render(gen.build_tables(CSV_DIR), 6.0, 32)
    assert a == b


def test_check_mode_reports_stale_file(tmp_path, capsys):
    stale = tmp_path / "boards.c"
    stale.write_text("// old\n")
    import sys
    argv = sys.argv
    try:
        sys.argv = ["gen", "--check", "--out", str(stale)]
        assert gen.main() == 1
        sys.argv = ["gen", "--check", "--out", OUT_C]
        assert gen.main() == 0
    finally:
        sys.argv = argv


def test_missing_csv_dir_is_an_error(tmp_path):
    import sys
    argv = sys.argv
    try:
        sys.argv = ["gen", "--csv-dir", str(tmp_path), "--out", str(tmp_path / "x.c")]
        assert gen.main() == 2
    finally:
        sys.argv = argv


def test_load_board_curve_averages_duplicate_duty_rows(tmp_path):
    p = tmp_path / "vtarget_PCB-77_measurements.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["board_id", "duty_percent", "commanded_mv", "duty_count", "adc_mv", "dmm_mv"])
        w.writerow(["PCB-77", 0, 4000, 358, 4000, 4000.0])
        w.writerow(["PCB-77", 1, 4000, 358, 4000, 4010.0])
        w.writerow(["PCB-77", 2, 3000, 500, 3000, 3000.0])
    board, pts = gen.load_board_curve(str(p))
    assert board == "PCB-77"
    assert pts == [(358, 4005.0), (500, 3000.0)]
