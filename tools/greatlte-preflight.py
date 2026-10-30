#!/usr/bin/env python3
"""Read-only greatlte (Galaxy Note 8, Exynos 8895) preflight collector.

Runs adb commands against a booted LineageOS or TWRP device and writes a
report. It never flashes, formats or writes to the phone.

Usage:
    python3 tools/greatlte-preflight.py
    python3 tools/greatlte-preflight.py -o my-report.txt
"""

import argparse
import datetime
import shutil
import subprocess
import sys
from pathlib import Path

PROPS = [
    "ro.product.model",
    "ro.product.device",
    "ro.product.name",
    "ro.board.platform",
    "ro.hardware",
    "ro.build.version.release",
    "ro.build.display.id",
    "ro.lineage.version",
    "ro.modversion",
    "ro.boot.bootloader",
    "ro.boot.hardware",
    "ro.boot.verifiedbootstate",
    "ro.boot.flash.locked",
    "ro.boot.kg.state",
]

SHELL_COMMANDS = [
    ("adb identity", "id"),
    ("kernel", "cat /proc/version"),
    ("kernel command line", "cat /proc/cmdline"),
    ("partitions", "cat /proc/partitions"),
    ("memory", "head -n 5 /proc/meminfo"),
    ("possible CPUs", "cat /sys/devices/system/cpu/possible"),
    ("present CPUs", "cat /sys/devices/system/cpu/present"),
    ("device-tree model", "tr -d '\\000' < /proc/device-tree/model 2>/dev/null"),
    ("device-tree compatible", "tr -d '\\000' < /proc/device-tree/compatible 2>/dev/null"),
    ("by-name dirs", "ls -d /dev/block/platform/*/by-name 2>/dev/null"),
    ("by-name entries", "ls -l /dev/block/platform/*/by-name/ 2>/dev/null"),
    ("block by-name symlink", "ls -l /dev/block/by-name/ 2>/dev/null"),
    ("data filesystem", "df -h /data 2>/dev/null"),
]


def run(cmd, timeout=30):
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s: {' '.join(cmd)}"


def adb(args, timeout=30):
    return run(["adb"] + args, timeout=timeout)


def adb_shell(command, timeout=30):
    return adb(["shell", command], timeout=timeout)


def section(title, body):
    return f"\n===== {title} =====\n{body.rstrip()}\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        default="greatlte-preflight.txt",
        help="report path (default: greatlte-preflight.txt)",
    )
    args = parser.parse_args()

    if shutil.which("adb") is None:
        print("adb not found in PATH. Install Android platform-tools first.")
        return 2

    rc, devices, err = adb(["devices", "-l"])
    if rc != 0:
        print(f"adb failed: {err}")
        return 2

    usable = []
    for line in devices.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2 and fields[1] in ("device", "recovery"):
            usable.append((fields[0], fields[1]))

    if not usable:
        print("No usable adb device attached.")
        print("Connect the phone and enable USB debugging (LineageOS), or boot")
        print("TWRP (adb state 'recovery'), then accept the authorization prompt.")
        print(devices)
        return 1

    lines = [
        "greatlte preflight report\n",
        f"generated: {datetime.datetime.now().isoformat(timespec='seconds')}\n",
        f"host: {sys.platform}\n",
        "",
        section("adb devices", devices),
    ]

    props = {}
    for prop in PROPS:
        rc, out, _ = adb_shell(f"getprop {prop}")
        props[prop] = out
        lines.append(section(prop, out or "(empty)"))

    lines.append(section("getprop ro.boot.*", "\n".join(
        f"{p}={props.get(p, '')}" for p in PROPS if p.startswith("ro.boot.")
    )))

    for title, command in SHELL_COMMANDS:
        rc, out, err = adb_shell(command)
        body = out if out else (err or "(no output)")
        lines.append(section(title, body))

    by_name = ""
    by_name_dir = ""
    for title, command in SHELL_COMMANDS:
        if title == "by-name dirs":
            _, by_name_dir, _ = adb_shell(command)
            by_name_dir = by_name_dir.splitlines()[0].strip() if by_name_dir else ""
        if title == "by-name entries":
            _, by_name, _ = adb_shell(command)

    report = "".join(lines)
    output = Path(args.output)
    output.write_text(report, encoding="utf-8")

    print(f"report written to {output}")
    print()
    print("summary:")
    for key in ("ro.product.model", "ro.product.device", "ro.board.platform",
                "ro.hardware", "ro.build.version.release", "ro.boot.flash.locked"):
        print(f"  {key}: {props.get(key) or '(empty)'}")

    warnings = []
    if props.get("ro.product.device") != "greatlte":
        warnings.append("ro.product.device is not greatlte; check the model.")

    platform = (props.get("ro.board.platform") or "").strip()
    hardware = (props.get("ro.hardware") or "").strip()
    if platform and platform != "exynos8895" and "exynos8895" not in hardware.lower():
        warnings.append("platform is not exynos8895; this is not the Exynos Note 8.")
    if not platform and "exynos8895" not in hardware.lower():
        warnings.append("could not confirm exynos8895 from ro.board.platform/ro.hardware.")
    if props.get("ro.boot.flash.locked") not in ("0", ""):
        warnings.append("bootloader may be locked (ro.boot.flash.locked is not 0).")

    boot_line = ""
    for line in by_name.splitlines():
        if " BOOT ->" in line or line.strip().startswith("BOOT "):
            boot_line = line
            break

    if warnings:
        print()
        print("warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    print()
    if boot_line:
        fields = boot_line.split()
        target = fields[-1] if fields else ""
        boot_path = f"{by_name_dir}/BOOT" if by_name_dir else target
        print("BOOT candidate from by-name:")
        print(f"  {boot_path}")
        if target:
            print(f"  target: {target}")
        print("Save it from TWRP (never overwrite it without a copy):")
        print(f"  adb shell dd if={boot_path} of=/sdcard/boot-stock.img")
        print("  adb pull /sdcard/boot-stock.img")
    else:
        print("No BOOT entry found. Run this again from TWRP and check the by-name listing.")

    print()
    print("This script does not flash or erase anything.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
