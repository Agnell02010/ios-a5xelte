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
On one boot that image appeared frozen at `reached phase 5` for two
minutes; a later boot with the instrumented kernel (run `41095907038`, patch
`0221-greatlte-vm-bootstrap-markers.patch`) went through and reached the
Phase 2 end state, so the early stop is a timing-sensitive flake to watch,
not a deterministic blocker.

### Phase 2 complete (device-verified)

The instrumented image (`xnu-boot-diag.img`, sha256
`b5db1aa5ad2c0daf17ec0c008686845fd01edcc840a1992e7c81983d9927a4ce`)
printed the full BSD init sequence on the Note 8 panel, including:

- `pmap_init: done [64 MB total pool size, (42/21) split]`;
- `DLIL: running SUN16 self-tests ... PASSED`;
- `Skywalk: ... PASSED` for all sk_copy/sk_zero/moncap tests;
- `ifnet_attach: ... lo0/gif0/stf0 ... scheduled`;
- `Waiting on IOProviderClass IOMedia ... Apple_HFS`;
- `Failed to write boot-picker-bringup-reason to NVRAM` (expected).

This is the Phase 2 success criterion: XNU boots, the scheduler runs, BSD
initializes, and the kernel waits for an HFS root device. The next work is
storage (Exynos 8895 UFS) and then the iOS root image.

### Phase 3 work: Exynos 8895 UFS

- The herolte driver relies on the fact that S-Boot leaves the UFSHCI host
  enabled with the link up, then issues polled SCSI commands on LUN 0. The
  8895 uses the same UFSHCI 2.0 interface and the same Samsung quirks
  (`BROKEN_DWORD_UTRD`, `BROKEN_REQ_LIST_CLR`).
- One difference found in `exynos8895.dtsi`: the vendor-specific HCI block
  is at **`0x11121100` (+0x1100)**, not `+0x100` as on the 8890. The
  greatlte driver therefore uses `VS_TXPRDT_ENTRY_SIZE 0x1100`,
  `VS_RXPRDT_ENTRY_SIZE 0x1104`, `VS_UTRL_NEXUS_TYPE 0x1140` and maps at
  least `0x2000` bytes.
- `xnu/patches/0222-greatlte-exynos-ufs.patch` adds
  `bsd/dev/greatlte_ufs.c` (derived from the device-verified herolte
  driver), the `/greatlte-ufs` ADT node lookup (`reg = 0x11120000+0x3000`,
  already written by `mkadt_greatlte.py`), the `bsd/conf/files` entry and
  the `IOFindBSDRoot` hook (`ufsprobe=1`, `rd=ufsroot0`).
- First step is a read-only probe: host registers, TEST UNIT READY on
  LUN 0..3, then READ(10) of GPT LBA 1 and the partition list. No storage
  writes.

### Phase 3a: UFS probe image built

- CI run `41109326291` (branch `greatlte`, commit `212c910`) completed
  successfully and produced `kernel.development.greatlte` (sha256
  `f4e44374a85afdbe418005fb438e3d8a6749d782bcc5275ca369a6c6eaf5ac9a`).
  The binary contains the `GREATLTE UFS:` probe strings (24 occurrences),
  so the new driver is compiled in.
- Host pipeline produced `xnu-boot-ufs.img` (18,284,560 bytes, sha256
  `dc0a8afff9f3d110057d68f3f1255590eaac23dd8a0ff85e85759b394edd1d29`)
  with cmdline `debug=0xc serial=3 cpus=1 keepsyms=1 startup_debug=1
  ufsprobe=1 -enable_kprintf_spam -noprogress`.
- The image is ready to flash to BOOT (`/dev/block/sda7`) for the first
  greatlte UFS access. Nothing else is written by the probe.

### Phase 3b: first UFS probe on the device

- The probe booted and printed, after the full BSD init:
  `cap 0x1383ff0f ver 0x210 hcs 0xf hce 0x8 is 0x8 utrlba 0xef002000
  dbr 0x9 rsr 0x1`, `txprdt 0xc rxprdt 0xc nexus 0xffff`, then
  `host not ready (hce 0x8 hcs 0xf)` and `probe done (6)`.
- Unlike the 8890, the 8895 S-Boot leaves HCE bit 0 clear (controller
  disabled) although the UTP registers still show its list, run bit and
  two doorbells. The driver therefore refused to touch the list.
- The kernel then continued to the normal `Waiting on IOProviderClass
  IOMedia ... Apple_HFS` root wait: the phone was not hung.
- Patch `0223-greatlte-ufs-host-enable.patch` makes the driver stop the
  old list, clear the bootloader doorbells, write HCE=1 and wait for the
  controller readiness bits. If the first TEST UNIT READY set still
  fails, the probe issues a UniPro `DME_LINK_STARTUP` (UIC 0x16) and
  retries LUN 0. Register and UIC results are printed.

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

### Phase 3c: HCE accepted, but the first commands timed out

- Probe v2 (`0223`) got past the HCE write but every SCSI command timed
  out: the W-LUN START STOP UNIT, the per-LUN TEST UNIT READY set and
  `READ(10) LBA1`. The UIC retry branch never ran: its result was stored
  in a local and the compiler removed the whole branch as dead code.
- Two defects were found by reading the 8895 vendor driver:
  - the HCE write happened immediately and the 500 us wait could return
    while the controller was still running its 1 -> 0 -> 1 initialization;
    the vendor waits 1 ms after setting HCE and then up to ~50 ms for the
    controller;
  - UTRD DW0 used `1 << 28` (UTP command type "native UFS"), while the
    vendor uses `UTP_CMD_TYPE_SCSI = 0` for SCSI commands.
- Patch `0224-greatlte-ufs-takeover.patch` (build run `41185180237`,
  kernel sha256 `41d7d14ec9149d91720a8f43a24f3fac5e2f1b1aae565fd2f8413871e15c480a`)
  adds: A) reuse of S-Boot's controller when HCE is on; B) the vendor HCE
  start sequence (write 0, 5 ms, write 1, 1 ms, wait for HCE=1, wait for
  HCS=0xf); 1 s UIC polling; a shared `ufs_bring_up_link()` used by both
  the probe and the root device, which wakes the device and retries
  `DME_LINK_STARTUP`; and HCE/HCS/IS/DBR values on timeout.
- `xnu-boot-ufs3.img` (18,300,944 bytes, sha256
  `e1969f3083dd3e366087dde909744e8b1744d0af76cc6ab28e1f9ffd1a3ea773`)
  carries the same `ufsprobe=1` cmdline and the new strings.

### Phase 3d: UFS PHY initialization probe (device tested, link still down)

- Patch `0225-greatlte-ufs-phy-init.patch` adds the Exynos 8895 PHY/UniPro
  setup based on the board DTS and reports per-table DME results. CI run
  `41199104693` completed successfully for commit `6aa9e4e`. Its kernel was
  packed as `xnu-boot-ufs4.img` (18,300,944 bytes, sha256
  `a5a05a250fb2f71b9252a0e771ccd09d0126a12051d8e5fc22e2e36b1cf567a9`)
  with `ufsprobe=1` and without `rd=ufsroot0` or `ufsrw=1`.
- Updated `tools/greatlte-make-xnu-boot.sh` to accept an optional boot
  command line, preserving its original default. The probe command is
  documented in `docs/greatlte-bringup.md` and must include `ufsprobe=1`.
- The `xnu-boot-ufs4.img` probe was flashed to BOOT only; the flash helper
  read the image back and verified the same SHA-256. USERDATA was not touched.
- Device photo after boot (`IMG_20261031_220158514`): UIC
  `DME_LINK_STARTUP` returned `IS=0x4`, `ARG2=0`, `ARG3=0`; the driver
  reported `B link startup 5` (EIO). Subsequent SCSI commands timed out with
  `HCE=1`, `HCS=0xf`, `IS=0x404`, and `UTRLDBR=1`. Device W-LUN TEST UNIT
  READY and START STOP UNIT both returned 60 (ETIMEDOUT); LUN 0 TUR also
  timed out, and the read-only probe ended with error 60. XNU continued to
  the expected Apple_HFS root wait.
- This confirms XNU and the diagnostic path still boot, but the PHY patch
  did not bring the UFS link up. No GPT contents or partitions were read
  successfully. The follow-up photo shows another boot at the takeover
  sequence but does not include the PHY-table summary or fresh UIC error
  details. Do not enable `rd=ufsroot0` or `ufsrw=1` yet.
- Source review found that patch 0225 omitted the Exynos 8895 PHY isolation
  bypass (`0x16480724`) that the Samsung driver enables before controller
  and link startup. The follow-up also verifies the DME_SET argument order
  against the vendor kernel: ARG2 is attribute-set type 0; ARG3 carries the
  PHY attribute value.
- CI run `41243017134` succeeded for commit `acf4400`; kernel sha256
  `5f174392331039f46e5a453d5d97e40969d4f61ede23c17e05e22d88a551ff21`.
  Repacked as `xnu-boot-ufs5.img` (18,300,944 bytes, sha256
  `2c97e4f1d166f043c215b20f4554a6ab36bca3539fac1a7fbe9939b105a42c51`)
  with read-only `ufsprobe=1` arguments.
- On 2026-10-31 the corrected image was flashed to BOOT only from TWRP;
  readback SHA-256 matched. USERDATA and other partitions were not touched.
- Follow-up device photos (`IMG_20261031_233349214`,
  `IMG_20261031_233623115`) show the corrected image still reaches the same
  UFS failure: UIC command `0x16` reports `IS=0x4`, then
  `B link startup 5`; SCSI `0x00` and `0x1b` commands time out and the probe
  ends with 60. XNU itself continues to `Waiting on ... Apple_HFS`.
- The prior ARG2 change was incorrect and insufficient; it placed PHY values
  in the attribute-set field. Restored the vendor ABI order and added the
  missing PHY isolation bypass before host takeover. The new kernel still
  needs a CI build and a device test. Do not mount the UFS root or enable
  `ufsrw=1`.
