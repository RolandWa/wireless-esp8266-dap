#!/usr/bin/env python3
"""
build_WSL.py — Automated build environment setup and firmware builder.

Replicates the GitHub CI environment exactly:
  - Ubuntu 24.04 + ESP-IDF v4.4.2 (espressif/esp-idf-ci-action@v1)
  - Target: esp32c3
  - Merges bootloader + partition table + app into one flashable binary
  - esptool v4.6.2 (same as CI)

Usage (inside WSL Ubuntu terminal):
    python3 build_WSL.py            # full setup + build
    python3 build_WSL.py --build    # build only (skip setup if already done)
    python3 build_WSL.py --clean    # clean build directory first
"""

import argparse
import os
import shutil
import subprocess
import sys

# ── Configuration (mirrors CI exactly) ────────────────────────────────────────
IDF_VERSION     = "v4.4.2"
IDF_TARGET      = "esp32c3"
ESPTOOL_TAG     = "v4.6.2"
IDF_DIR         = os.path.expanduser(f"~/esp/esp-idf-{IDF_VERSION}")
BUILD_DIR       = os.path.expanduser("~/build_wireless_dap")
ESPTOOL_DIR     = os.path.expanduser("~/esptool")

# Detect repo root: script lives at the repo root on the Windows FS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# If running from the Windows path (/mnt/c/...) use it directly
REPO_DIR = SCRIPT_DIR

# APT packages installed by CI for esp32/esp32c3/esp32s3 targets
APT_PACKAGES = [
    "git", "wget", "flex", "bison", "gperf",
    "python3", "python3-pip", "python3-venv",
    "cmake", "ninja-build", "ccache",
    "libffi-dev", "libssl-dev", "dfu-util", "libusb-1.0-0",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def banner(msg):
    print(f"\n{'='*70}\n  {msg}\n{'='*70}")

def run(cmd, env=None, check=True, cwd=None):
    print(f"  $ {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
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
    """Source IDF export.sh and return the resulting environment dict."""
    export_sh = os.path.join(IDF_DIR, "export.sh")
    if not os.path.exists(export_sh):
        sys.exit(f"ERROR: IDF not found at {IDF_DIR} — run without --build to set up first.")
    result = subprocess.run(
        f'bash -c ". {export_sh} > /dev/null 2>&1 && env"',
        shell=True, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"ERROR: Failed to source IDF export.sh:\n{result.stderr}")
    env = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            env[k] = v
    return env

# ── Setup steps ───────────────────────────────────────────────────────────────

def step_apt():
    banner("1/5  Installing system packages")
    run(["sudo", "apt-get", "update", "-qq"])
    run(["sudo", "apt-get", "install", "-y", "--no-install-recommends"] + APT_PACKAGES)

def step_clone_idf():
    banner("2/5  Cloning ESP-IDF " + IDF_VERSION)
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
    banner("3/5  Installing IDF tools for " + IDF_TARGET)
    stamp = os.path.join(IDF_DIR, f".installed_{IDF_TARGET}")
    if os.path.exists(stamp):
        print("  Already installed — skipping (delete stamp to force reinstall):")
        print(f"    {stamp}")
        return

    # IDF v4.4.2 idf_tools.py crashes with KeyError:'idfSelectedId' if a previous
    # failed run left a partial idf-env.json. Remove it so install starts clean.
    idf_env_json = os.path.expanduser("~/.espressif/idf-env.json")
    if os.path.exists(idf_env_json):
        print(f"  Removing stale {idf_env_json}")
        os.remove(idf_env_json)

    # Execute install.sh as a child process (not sourced) so BASH_SOURCE[0]
    # resolves correctly and IDF can find its own tools/ directory.
    subprocess.run(
        ["bash", os.path.join(IDF_DIR, "install.sh"), IDF_TARGET],
        check=True,
    )
    open(stamp, "w").close()

def step_clone_esptool():
    banner("4/5  Cloning esptool " + ESPTOOL_TAG)
    if os.path.isdir(os.path.join(ESPTOOL_DIR, ".git")):
        print(f"  Already cloned at {ESPTOOL_DIR} — skipping")
        return
    run([
        "git", "clone", "https://github.com/espressif/esptool.git", ESPTOOL_DIR,
    ])
    run(["git", "-C", ESPTOOL_DIR, "checkout", f"tags/{ESPTOOL_TAG}", "-b", "ci_build"])

# ── Build ──────────────────────────────────────────────────────────────────────

def step_build(clean=False):
    banner("5/5  Building firmware")
    env = load_idf_env()

    if clean and os.path.isdir(BUILD_DIR):
        print(f"  Removing build dir: {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR)

    os.makedirs(BUILD_DIR, exist_ok=True)

    print(f"\n  Repo   : {REPO_DIR}")
    print(f"  Build  : {BUILD_DIR}")
    print(f"  Target : {IDF_TARGET}")
    print(f"  IDF    : {env.get('IDF_PATH', '?')}\n")

    # Set target
    run(
        ["idf.py", "-C", REPO_DIR, "-B", BUILD_DIR, "set-target", IDF_TARGET],
        env=env,
    )

    # Build
    run(
        ["idf.py", "-C", REPO_DIR, "-B", BUILD_DIR, "build"],
        env=env,
    )

    # Merge binaries — same offsets as CI merge step for esp32c3
    full_bin  = os.path.join(BUILD_DIR, "wireless_esp_dap_full.bin")
    app_src   = os.path.join(BUILD_DIR, "wireless_esp_dap.bin")
    app_dst   = os.path.join(BUILD_DIR, "wireless_esp_dap_app.bin")
    boot_bin  = os.path.join(BUILD_DIR, "bootloader", "bootloader.bin")
    ptbl_bin  = os.path.join(BUILD_DIR, "partition_table", "partition-table.bin")

    run([
        "python3",
        os.path.join(ESPTOOL_DIR, "esptool.py"),
        "--chip", IDF_TARGET,
        "merge_bin",
        "-o", full_bin,
        "0x0",    boot_bin,
        "0x8000", ptbl_bin,
        "0x10000", app_src,
    ])

    if os.path.exists(app_src):
        shutil.copy2(app_src, app_dst)

    # Report sizes
    banner("Firmware sizes")
    for f in [full_bin, app_dst]:
        if os.path.exists(f):
            sz = os.path.getsize(f)
            print(f"  {os.path.basename(f):40s}  {sz:>8,} bytes  ({sz/1024:.1f} kB)")

    print(f"\n  Flash command (Windows):")
    win_build = BUILD_DIR.replace(
        os.path.expanduser("~"),
        r"\\wsl$\Ubuntu" + os.path.expanduser("~").replace("/home/", "/home/")
    )
    print(f"    flash_esp.bat  (uses {full_bin})")
    print(f"\n  Done.")

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true", help="Skip setup steps, build only")
    ap.add_argument("--clean", action="store_true", help="Remove build directory before building")
    args = ap.parse_args()

    check_wsl()

    if not args.build:
        step_apt()
        step_clone_idf()
        step_install_idf()
        step_clone_esptool()

    step_build(clean=args.clean)

if __name__ == "__main__":
    main()
