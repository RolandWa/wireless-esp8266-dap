"""Build and run the C unit tests (tests/unit/test_vtarget_cal.c) from pytest.

Uses a native gcc when available (Linux/CI), otherwise gcc inside WSL (Windows).
Skipped if neither exists. Output of the C runner is shown on failure.
"""
import os
import re
import shutil
import subprocess

import pytest

from conftest import UNIT_DIR


def _wsl_path(path):
    drive, rest = os.path.splitdrive(os.path.abspath(path))
    return "/mnt/" + drive[0].lower() + rest.replace("\\", "/")


def _command():
    if shutil.which("gcc") and shutil.which("make"):
        return ["make", "-C", UNIT_DIR, "test"]
    if shutil.which("wsl"):
        return ["wsl", "--", "make", "-C", _wsl_path(UNIT_DIR), "test"]
    return None


@pytest.fixture(scope="module")
def c_result():
    cmd = _command()
    if cmd is None:
        pytest.skip("no gcc/make (native or WSL) available")
    proc = subprocess.run(cmd, capture_output=True, timeout=300)
    out = proc.stdout.decode("utf-8", errors="replace").replace("\x00", "")
    err = proc.stderr.decode("utf-8", errors="replace").replace("\x00", "")
    if proc.returncode != 0 and "gcc" in err + out and "not found" in err + out:
        pytest.skip("gcc not usable in this environment")
    return proc.returncode, out + err


def test_c_unit_tests_pass(c_result):
    code, out = c_result
    assert code == 0, out
    assert re.search(r"\d+ checks, 0 failures", out), out


def test_c_unit_tests_ran_every_test_function(c_result):
    _code, out = c_result
    ok = re.findall(r"^ok\s+(test_\w+)", out, flags=re.M)
    with open(os.path.join(UNIT_DIR, "test_vtarget_cal.c"), encoding="utf-8") as f:
        declared = re.findall(r"^\s*RUN\((test_\w+)\);", f.read(), flags=re.M)
    assert declared, "no RUN() entries found"
    assert ok == declared, out


def test_c_tests_compared_boards_with_measurements(c_result):
    _code, out = c_result
    assert "no sweep CSVs found" not in out, "board tables were not compared with the DMM sweeps"
