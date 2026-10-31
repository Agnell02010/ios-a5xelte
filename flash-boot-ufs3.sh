#!/bin/bash
# Flash ONLY the greatlte BOOT partition (/dev/block/sda7) with the UFS
# takeover probe. Run this with the phone booted into TWRP and USB attached.
set -euo pipefail

cd "$(dirname "$0")"
img=${1:-xnu-boot-ufs3.img}
part=/dev/block/sda7
offsetsize=$(stat -c %s "$img")
want=$(sha256sum "$img" | cut -d' ' -f1)

echo "== image: $img"
echo "   bytes: $offsetsize"
echo "   sha256: $want"

if [ "$(adb devices | grep -c 'recovery$')" -lt 1 ]; then
    echo "!! No device in recovery. Boot TWRP first (adb devices must show 'recovery')."
    exit 1
fi

device=$(adb shell getprop ro.product.device | tr -d '\r')
echo "== device: $device"
case "$device" in
    greatlte*|*greatlte*) ;;
    *) echo "!! This does not look like a greatlte ($device). Refusing."; exit 1 ;;
esac

byname=$(adb shell 'readlink -f /dev/block/platform/11120000.ufs/by-name/BOOT 2>/dev/null' | tr -d '\r')
echo "== by-name BOOT -> ${byname:-not found}"
sectors=$(adb shell 'cat /sys/class/block/sda7/size 2>/dev/null' | tr -d '\r')
echo "== sda7 sectors: ${sectors:-unknown} (BOOT must be 81920 = 40 MiB)"
if [ "$sectors" != "81920" ]; then
    echo "!! sda7 is not the 40 MiB BOOT partition. Refusing."
    exit 1
fi
if [ -n "$byname" ] && [ "$byname" != "$part" ]; then
    echo "!! by-name BOOT is not $part. Refusing to guess."
    exit 1
fi

echo "== pushing"
adb push "$img" /tmp/boot-ufs3.img >/dev/null

echo "== writing $part (this takes a few seconds)"
adb shell "dd if=/tmp/boot-ufs3.img of=$part bs=1M conv=fsync 2>&1" | tail -2
adb shell sync

echo "== reading back $offsetsize bytes"
adb exec-out "dd if=$part bs=1M count=18 2>/dev/null" > /tmp/boot-ufs3-readback.bin
got=$(head -c "$offsetsize" /tmp/boot-ufs3-readback.bin | sha256sum | cut -d' ' -f1)
echo "   readback sha256: $got"
if [ "$got" != "$want" ]; then
    echo "!! READBACK MISMATCH. Do not reboot; reflash or restore the backup."
    exit 1
fi

echo "== OK: BOOT verified. Reboot to system and photograph the bottom of the screen."
