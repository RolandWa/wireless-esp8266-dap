#!/usr/bin/env python3
"""
build_WSL.py — Automated build environment setup and firmware builder.

Replicates the GitHub CI environment exactly:
  - Ubuntu 24.04 + ESP-IDF v4.4.2 (espressif/esp-idf-ci-action@v1)
  - Target: esp32c3
  - Merges bootloader + partition table + app into one flashable binary
  - esptool v4.6.2 (same as CI)

Usage — from Windows PowerShell / CMD (no WSL terminal needed):
    python build_WSL.py            # full setup + build
    python build_WSL.py --build    # build only (skip setup if already done)
    python build_WSL.py --clean    # clean build directory first

Usage — from inside a WSL Ubuntu terminal:
    python3 build_WSL.py --build
"""

import argparse
import os
import shutil
import subprocess
import sys

# ── Windows launcher ──────────────────────────────────────────────────────────
# When run from Windows, convert this script's path to a WSL /mnt/... path and
# re-exec inside WSL so the rest of the script runs natively on Linux.
# __file__ will then be the /mnt/c/... path, giving correct rsync source and
# copy-back destination for free.
def _relaunch_in_wsl():
    """If running on Windows, re-exec this script inside WSL and exit."""
    if sys.platform != "win32":
        return  # already in WSL or native Linux

    script = os.path.abspath(__file__)

    # Convert Windows path  C:\foo\bar  →  /mnt/c/foo/bar
    drive, rest = os.path.splitdrive(script)          # e.g. "C:", "\foo\bar"
    wsl_path = "/mnt/" + drive[0].lower() + rest.replace("\\", "/")

    print(f"Detected Windows — launching inside WSL: {wsl_path}")
    result = subprocess.run(
        ["wsl", "python3", wsl_path] + sys.argv[1:],
        check=False,
    )
    sys.exit(result.returncode)


_relaunch_in_wsl()  # no-op when already inside WSL

# ── Configuration (mirrors CI exactly) ────────────────────────────────────────
IDF_VERSION     = "v4.4.2"
IDF_TARGET      = "esp32c3"
ESPTOOL_TAG     = "v4.6.2"
IDF_DIR         = os.path.expanduser(f"~/esp/esp-idf-{IDF_VERSION}")
BUILD_DIR       = os.path.expanduser("~/build_wireless_dap")
ESPTOOL_DIR     = os.path.expanduser("~/esptool")

# IDF v4.4.2 requires Python ≤3.10. gevent 1.5.0 (pulled in by gdbgui in
# requirements.txt) uses Cython extensions that fail to compile on Python 3.11+.
PYTHON_FOR_IDF  = "python3.10"

# Detect repo root: script lives at the repo root on the Windows FS.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR   = SCRIPT_DIR

# IDF's kconfiglib splits paths at spaces — the Windows repo path contains
# "OneDrive - Rockwell Automation, Inc" with spaces and cmake cannot handle it.
# Mirror the repo to a clean Linux-native path before every build (rsync is
# fast after the first run). This matches CI which clones to a space-free path.
REPO_LINUX = os.path.expanduser("~/wireless_dap")

# APT packages matching the CI runner (ubuntu-24.04)
APT_PACKAGES = [
    "git", "wget", "flex", "bison", "gperf",
    "python3", "python3-pip", "python3-venv", "python3-full",
    "python3-virtualenv",
    "software-properties-common",          # needed for add-apt-repository
    "cmake", "ninja-build", "ccache",
    "libffi-dev", "libssl-dev", "dfu-util", "libusb-1.0-0",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def banner(msg):
    print(f"\n{'='*70}\n  {msg}\n{'='*70}")

def run(cmd, env=None, check=True, cwd=None):
    print(f"  $ {cmd if isinstance(cmd, str) else ' '.join(str(a) for a in cmd)}")
    return subprocess.run(
        cmd, shell=isinstance(cmd, str), env=env, check=check,
        cwd=cwd, text=True,
    )

def check_wsl():
    if not os.path.exists("/proc/version"):
        sys.exit("ERROR: This script must run inside WSL Ubuntu.")
    with open("/proc/version") as f:
        if "microsoft" not in f.read().lower():
            sys.exit("ERROR: This script must run inside WSL Ubuntu.")
    print("WSL detected OK")

def load_idf_env():
    """Source IDF export.sh using python3.10 venv and return the environment."""
    export_sh = os.path.join(IDF_DIR, "export.sh")
    if not os.path.exists(export_sh):
        sys.exit(f"ERROR: IDF not found at {IDF_DIR} — run without --build to set up first.")

    shim_dir = _python_shim_dir()

    # Write a temp script to avoid quoting issues with paths containing spaces.
    tmp_script = os.path.expanduser("~/idf_env_dump.sh")
    with open(tmp_script, "w") as f:
        f.write(f'export PATH="{shim_dir}:$PATH"\n')
        f.write(f'. "{export_sh}" > /dev/null 2>&1\n')
        f.write("env\n")
    os.chmod(tmp_script, 0o755)

    result = subprocess.run(["bash", tmp_script], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ERROR: Failed to source IDF export.sh:\n{result.stderr}")

    env = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            env[k] = v
    return env

def _python_shim_dir():
    """Return path to a directory where python3 -> python3.10 symlink lives."""
    shim_dir = os.path.expanduser("~/idf_python_shim")
    os.makedirs(shim_dir, exist_ok=True)

    py310 = shutil.which(PYTHON_FOR_IDF)
    if not py310:
        sys.exit(
            f"ERROR: {PYTHON_FOR_IDF} not found.\n"
            "Run the full setup (without --build) to install it first."
        )

    for name in ("python3", "python"):
        link = os.path.join(shim_dir, name)
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(py310, link)

    return shim_dir

# ── Setup steps ───────────────────────────────────────────────────────────────

def step_apt():
    banner("1/6  Installing system packages")
    run(["sudo", "apt-get", "update", "-qq"])
    run(["sudo", "apt-get", "install", "-y", "--no-install-recommends"] + APT_PACKAGES)

def step_install_python310():
    banner("2/6  Installing Python 3.10 (required by IDF v4.4.2)")
    result = subprocess.run([PYTHON_FOR_IDF, "--version"], capture_output=True)
    if result.returncode == 0:
        ver = (result.stdout or result.stderr).decode().strip()
        print(f"  {ver} already installed — skipping")
        return

    print(f"  {PYTHON_FOR_IDF} not found, installing via deadsnakes PPA...")
    run(["sudo", "add-apt-repository", "-y", "ppa:deadsnakes/ppa"])
    run(["sudo", "apt-get", "update", "-qq"])
    run([
        "sudo", "apt-get", "install", "-y",
        "python3.10", "python3.10-venv", "python3.10-dev", "python3.10-distutils",
    ])

def step_clone_idf():
    banner("3/6  Cloning ESP-IDF " + IDF_VERSION)
    if os.path.isdir(os.path.join(IDF_DIR, ".git")):
        print(f"  Already cloned at {IDF_DIR} — skipping")
        return
    os.makedirs(os.path.dirname(IDF_DIR), exist_ok=True)
    run([
        "git", "clone",
        "--branch", IDF_VERSION,
        "--depth", "1",
        "--recursive",
        "https://github.com/espressif/esp-idf.git",
        IDF_DIR,
    ])

def step_install_idf():
    banner("4/6  Installing IDF tools for " + IDF_TARGET)
    stamp = os.path.join(IDF_DIR, f".installed_{IDF_TARGET}")
    if os.path.exists(stamp):
        print("  Already installed — skipping")
        print(f"  (delete {stamp} to force reinstall)")
        return

    # Clean up any stale state from previous failed attempts
    idf_env_json = os.path.expanduser("~/.espressif/idf-env.json")
    if os.path.exists(idf_env_json):
        print(f"  Removing stale {idf_env_json}")
        os.remove(idf_env_json)

    stale_venv = os.path.expanduser("~/.espressif/python_env/idf4.4_py3.14_env")
    if os.path.isdir(stale_venv):
        print(f"  Removing stale Python 3.14 venv: {stale_venv}")
        shutil.rmtree(stale_venv)

    # Shim PATH: python3 / python -> python3.10 so IDF detect_python.sh
    # picks the compatible version instead of the system Python 3.14.
    shim_dir = _python_shim_dir()
    env = os.environ.copy()
    env["PATH"] = shim_dir + ":" + env.get("PATH", "")

    print(f"  Using {PYTHON_FOR_IDF} for IDF install (shim: {shim_dir})")
    subprocess.run(
        ["bash", os.path.join(IDF_DIR, "install.sh"), IDF_TARGET],
        check=True,
        env=env,
    )
    # Install cmake 3.28 into the IDF venv. Ubuntu 26+ ships cmake 4.x which
    # removed <3.5 compatibility required by IDF v4.4.2's mbedtls component.
    # The venv bin dir is first in PATH after export.sh, so this takes precedence.
    idf_pip = os.path.expanduser(
        "~/.espressif/python_env/idf4.4_py3.10_env/bin/pip"
    )
    if os.path.exists(idf_pip):
        subprocess.run([idf_pip, "install", "cmake==3.28.4"], check=True)

    open(stamp, "w").close()

def step_sync_repo():
    """Mirror repo to a space-free Linux path so cmake/kconfiglib can handle it."""
    banner("Syncing repo to Linux filesystem (space-free path)")
    os.makedirs(REPO_LINUX, exist_ok=True)
    # rsync everything including gitignored files (e.g. wifi_configuration.h).
    # Exclude large items not needed for esp32c3 build.
    run([
        "rsync", "-a", "--delete",
        "--exclude=ESP8266_RTOS_SDK/",
        "--exclude=.git/",
        "--exclude=__pycache__/",
        "--exclude=.venv/",
        "--exclude=.claude/",
        SCRIPT_DIR + "/",
        REPO_LINUX + "/",
    ])
    print(f"  Synced to: {REPO_LINUX}")

def step_clone_esptool():
    banner("5/6  Cloning esptool " + ESPTOOL_TAG)
    if os.path.isdir(os.path.join(ESPTOOL_DIR, ".git")):
        print(f"  Already cloned at {ESPTOOL_DIR} — skipping")
        return
    run(["git", "clone", "https://github.com/espressif/esptool.git", ESPTOOL_DIR])
    run(["git", "-C", ESPTOOL_DIR, "checkout", f"tags/{ESPTOOL_TAG}", "-b", "ci_build"])

# ── Build ──────────────────────────────────────────────────────────────────────

def step_build(clean=False):
    banner("6/6  Building firmware")

    # Always sync repo first — picks up latest changes and ensures the build
    # uses the space-free Linux path that cmake/kconfiglib require.
    step_sync_repo()

    env = load_idf_env()

    if clean and os.path.isdir(BUILD_DIR):
        print(f"  Removing build dir: {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR)

    os.makedirs(BUILD_DIR, exist_ok=True)

    print(f"\n  Source : {REPO_DIR}")
    print(f"  Build  : {REPO_LINUX} -> {BUILD_DIR}")
    print(f"  Target : {IDF_TARGET}")
    print(f"  IDF    : {env.get('IDF_PATH', '?')}")
    print(f"  Python : {env.get('IDF_PYTHON_ENV_PATH', PYTHON_FOR_IDF)}\n")

    run(["idf.py", "-C", REPO_LINUX, "-B", BUILD_DIR, "set-target", IDF_TARGET], env=env)
    run(["idf.py", "-C", REPO_LINUX, "-B", BUILD_DIR, "build"],                  env=env)

    # Merge binaries — offsets match CI merge step for esp32c3
    full_bin = os.path.join(BUILD_DIR, "wireless_esp_dap_full.bin")
    app_src  = os.path.join(BUILD_DIR, "wireless_esp_dap.bin")
    app_dst  = os.path.join(BUILD_DIR, "wireless_esp_dap_app.bin")
    boot_bin = os.path.join(BUILD_DIR, "bootloader", "bootloader.bin")
    ptbl_bin = os.path.join(BUILD_DIR, "partition_table", "partition-table.bin")

    run([
        PYTHON_FOR_IDF,
        os.path.join(ESPTOOL_DIR, "esptool.py"),
        "--chip", IDF_TARGET,
        "merge_bin", "-o", full_bin,
        "0x0",     boot_bin,
        "0x8000",  ptbl_bin,
        "0x10000", app_src,
    ])

    if os.path.exists(app_src):
        shutil.copy2(app_src, app_dst)

    banner("Firmware sizes")
    for f in [full_bin, app_dst]:
        if os.path.exists(f):
            sz = os.path.getsize(f)
            print(f"  {os.path.basename(f):40s}  {sz:>8,} bytes  ({sz/1024:.1f} kB)")

    # Copy the merged binary back to the Windows repo directory so flash_eps.bat works
    win_repo = os.path.dirname(os.path.abspath(__file__))
    win_bin  = os.path.join(win_repo, "wireless_esp_dap_full.bin")
    if os.path.exists(full_bin):
        shutil.copy2(full_bin, win_bin)
        print(f"  Copied to:   {win_bin}")

    print(f"\n  Flash with:  flash_eps.bat")
    print(f"  Full binary: {full_bin}")
    print(f"\n  Done.")

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--build", action="store_true", help="Skip setup steps, build only")
    ap.add_argument("--clean", action="store_true", help="Remove build directory before building")
    args = ap.parse_args()

    check_wsl()

    if not args.build:
        step_apt()
        step_install_python310()
        step_clone_idf()
        step_install_idf()
        step_clone_esptool()

    step_build(clean=args.clean)

if __name__ == "__main__":
    main()
