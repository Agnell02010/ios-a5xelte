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
- Run `41083355147` (GREATLTE, macos-15-intel) reached the compile phase and
  failed because `0019-stage-libpthread.sh`, `0020-stage-bearssl.sh` and
  `0026-stage-hfs.sh` only accepted `SWEET|A5XELTE|HEROLTE`, so the vendor
  sources were never staged. Fixed by adding `GREATLTE` to all three. The
  compiler errors were exactly the missing `sweet_bearssl/`,
  `sweet_libpthread/` and `sweet_hfs/` trees.
- Workflow now uploads `build.log` as the `xnu-buildlog` artifact on failure
  and reports real compile errors (not only skipped patches) as annotations.
- Run `41085604027` built `kernel.development.greatlte` (sha256
  `74d35dffa2450690335d39e176bf4249f1c68bbc85e1a03bb08f604b23dc7b8e`).
  The one-command host pipeline wraps it in a SWEETXNU payload and packs
  `xnu-boot.img` (18,282,512 bytes) into the 40 MiB BOOT slot.

### Phase 2 XNU boot (device-verified)

The first flash reused a stale loader (`HEROLTE XNU LOADER`, old 512 MiB
window) and failed with `LOADER FAIL: PAYLOAD RAM OUTSIDE WINDOW`; rebuilding
`shim/greatlte` with `CROSS=aarch64-none-elf-` produced `GREATLTE XNU
LOADER` with the `0x92400000`..`0xb1000000` window. The corrected image
(`sha256 00aa9eb6…f398a9`, then `b239c32f…4969a` with `startup_debug=1`)
booted XNU on the phone. Console evidence:

- `Darwin Kernel Version 22.6.0: … root:xnu-8796.141.3~6/RELEASE_ARM64_T8010`;
- platform expert, AppleKeyStore, watchdog, SURF, HID (buttons and touch);
- `SWEET CPU: requested=1 selected=1`, `cpu=0 … came alive: SGI OK`,
  `1/1 CPUs initialized, SGI verified`;
- `SWEET FB: AppleCLCD 1440x2960 stride 5760 at 0xcc000000 … presented as
  1125x2436`, `requested 30 Hz, effective 30 Hz`;
- AMFI, Sandbox, HFS registered; `vminit: done [64 MB total pool size,
  (42/21) split]`; Skywalk SUN16 self-tests `PASSED`; all created kernel
  threads scheduled; `vm_region_init …`; `running self-tests`.

This reaches the Phase 2 success criterion (XNU C console, VM bootstrap,
scheduler, one core). The expected next stop is the root-device wait
(`Waiting on <dict>IOProviderClass IOMedia, Content Apple_HFS</dict>`), which
is normal until a storage driver exists. The Note 8 panel is physically
damaged at the bottom, so the last console lines are hard to read; patch
`0220-greatlte-fbcon-top.patch` clamps the fbcon to the top 2400 of 2960
pixels (75 rows at `FBCON_SCALE 2`) to keep the newest output readable.
Run `41092209216` rebuilt the kernel with that patch (sha256
`b684186c3dadc7e8bea2288a130b6619fa9bacb0fb251bbb74034f48a3aa7d58`) and
produced the next diagnostic image (`xnu-boot.img`, sha256
`55e1f73217b9bee64d7c3ff16f1c728f24b16c2474510f09b0a5caae5e5ecb5c`).

### Claims

- Device-verified: probe output and all live-FDT values above; stock
  partition backups exist; XNU boots to the Phase 2 milestone and drives the
  panel through its fbcon.
- Build-verified: probe.Image and xnu_boot.Image compile; greatlte ADT
  serializes; `kernel.development.greatlte` builds in CI; payload and ADT
  survive packing byte-identically.
- Not verified: the final root-wait line (hidden by the damaged panel until
  the 0220 console build), storage, display services, touch, keys, iOS
  userland.
