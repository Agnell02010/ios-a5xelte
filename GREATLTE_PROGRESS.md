# GREATLTE (Galaxy Note 8 SM-N950F/DS, Exynos 8895): progress

Log device evidence, build results and open questions here. Keep source-derived
facts separate from measurements on the phone.

## 2026-10-30

### Device confirmed

- SM-N950F/DS (DUOS), `greatlte`, Exynos 8895, 6 GB DRAM, bought in Italy.
- TWRP/Omni 16.1.0, bootloader `N950FXXUGDVG5`, bootloader unlocked
  (`ro.boot.verifiedbootstate=orange`), 5,497,364 kB visible RAM.
- BOOT `/dev/block/sda7`; by-name root
  `/dev/block/platform/11120000.ufs/by-name`.
- Backed up BOOT, RECOVERY, EFS, RADIO, CPEFS and PERSISTENT to
  `backup/greatlte/` with `SHA256SUMS.txt`. Stock BOOT sha256
  `b277b673726a9ccc06cff48198b7e69603376bcf33c21668ca8df8a98eb3a671`.

### Phase 1 probe (device-verified)

`shim/greatlte/probe.Image` (10,832 bytes) packed as `probe-boot.img`
(1,828,880 bytes) and flashed to BOOT. It printed on the Note 8 panel:

```
GREATLTE XNU PROBE 1
EL 1
SCTLR 0x30C5183E
FDT 0x8A000000
IMAGE 0x800EC000
MIDR 0x410FD034
MPIDR 0x80000100
MMFR0 0x1122
PFR0 0x2222
ISAR0 0x11120
CNTFRQ 0
FB 0xCC000000
TRIG 0x1291
INITRD 0x89000000
INITRD END 0x8918067C
16K PAGES: NO
```

The boot CPU is a Cortex-A53 at MPIDR `0x100`; S-Boot loads the Image at
`0x800ec000`, not the BOOT header's `0x10008000`.

### Live FDT (read through TWRP)

- Memory: `0x80000000+0x3c800000`, `0xc0000000+0x40000000`,
  `0x880000000+0x80000000`, `0x900000000+0x80000000`.
- GIC-400: distributor `0x10201000`, CPU interface `0x10202000`.
- Timer: 26 MHz (`0x018cba80`), virtual PPI 11 -> INTID 27.
- UFS: `0x11120000+0x200`, vendor `+0x100`, UNIPRO `0x11110000+0x8000`,
  protector `0x11130000+0x100`.
- CPU MPIDRs: Mongoose `0x000`..`0x003`, A53 `0x100`..`0x103`.
- Reserved/occupied ranges near the chosen window: `ess_setup=0x91200000`
  (ends before `0x92200000`); Samsung secure logs at `0x92202000`,
  `0x92244000`, `0x92286000`, `0x92388000`; TIMA at `0xb1000000` size
  `0x200000`; framebuffer at `0xcc000000` size 17,049,600 bytes.
- XNU RAM window chosen: `0x92400000`..`0xb1000000` (492 MiB), clear of all
  the above. Do not grow it upward past TIMA.

### Phase 2 work

- `shim/greatlte/xnu_boot.c` and `xnu_boot.S` adapted: FB `0xcc000000`,
  height 2960, RAM window `0x92400000`..`0xb1000000`, Exynos 8895 PMU
  `0x16480000` for the TWRP fallback.
- `tools/mkadt_greatlte.py` writes a greatlte ADT: GIC `0x10201000`/
  `0x10202000`, timer INTID 27, one A53 at MPIDR `0x100`, UFS
  `0x11120000`, FB console `0xcc000000` 1440x2960, DRAM window above.
- `xnu/patches/0219-greatlte-board-target.patch` adds
  `MACHINE_CONFIG=GREATLTE`, `config/MASTER.arm64.greatlte`, the A5XELTE.h
  board constants (FB `0xcc000000`, 1440x2960, 9 x 2 MiB FB blocks) and
  enables the iPhone X canvas path on greatlte.
- No greatlte kernel artifact exists yet. The first herolte CI run was
  cancelled while queued on arm64 (`The job was not acquired by Runner of
  type hosted`); the workflow now uses `macos-15-intel`.

### Claims

- Device-verified: probe output and all live-FDT values above; stock
  partition backups exist.
- Build-verified: probe.Image and xnu_boot.Image compile; greatlte ADT
  serializes. The GREATLTE kernel patch has not been compiled yet.
- Not verified: XNU boot on greatlte, storage, display services, touch,
  keys, iOS userland.
