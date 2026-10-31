#!/bin/bash
# Build the greatlte XNU boot image from a CI kernel artifact.
#
#   tools/greatlte-make-xnu-boot.sh kernel.development.greatlte OUT.img [CMDLINE]
#
# Steps: regenerate greatlte.adt, wrap the Mach-O kernel + ADT in a
# SWEETXNU payload (mkpayload resolves the chained fixups), append it to the
# loader Image and repack the stock BOOT (DTBH preserved). The stock BOOT is
# read from backup/greatlte/BOOT.img and is never modified.
set -euo pipefail
[[ $# -ge 2 && $# -le 3 ]] || { sed -n '2,8p' "$0"; exit 2; }
kernel=$(realpath "$1")
out=$2
cmdline=${3:-'debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress'}
cd "$(dirname "$0")/.."
[[ -f backup/greatlte/BOOT.img ]] || { echo "missing stock BOOT backup" >&2; exit 1; }
[[ -f shim/greatlte/out/xnu_boot.Image ]] || { echo "missing loader; run shim/greatlte/build.sh" >&2; exit 1; }

python3 tools/mkadt_greatlte.py greatlte.adt
python3 tools/mkpayload.py "$kernel" greatlte.adt payload.bin --cmdline "$cmdline"
python3 tools/greatlte-pack-boot.py pack backup/greatlte/BOOT.img \
    shim/greatlte/out/xnu_boot.Image "$out" --append payload.bin \
    --partition-size 41943040
