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

### Phase 3e: repair 0225 before another device test

- CI run `41249392008` reported success but skipped
  `0225-greatlte-ufs-phy-init.patch` as malformed. Its `xnu-boot-ufs6.img`
  artifact does not contain the PHY fix and must not be flashed.
- Rebuilt 0225 as a fresh diff against the post-0224 source extracted from
  run `41243017134`; `git apply --check` now succeeds against that exact base.
- The regenerated patch also maps the MPHY PMA (`0x11124000`) separately from
  the HCI block, and maps the isolation register through its aligned PMU page
  (`0x16480000` + `0x724`). UIC commands now wait for `HCS.UCRDY` and report a
  timeout rather than being issued while the controller is not ready.
- No new kernel has been built or flashed yet. Device storage remains
  untouched; the next image must be read-only (`ufsprobe=1`) and verified in
  CI to include 0225 before BOOT is written.
- Commit `45f1e4f` repaired the patch; CI run `41296783791` completed
  successfully. Its log explicitly says it applied
  `0225-greatlte-ufs-phy-init.patch`, and does not report that patch as
  skipped. The rebuilt kernel contains the PHY isolation marker and the
  UFS-PHY initialization diagnostics; kernel sha256 is
  `421080377ccb033db0c102665e35b0b3bd58fedb8b92cbd64fc66a45140e8ba2`.
- Packaged a new candidate `xnu-boot-ufs7.img` (18,317,328 bytes, sha256
  `efe44c907d8119d2511c8ca6bb00379188b8001477d30981e696a6f2ab3fd33b`).
  Its embedded command line includes `ufsprobe=1` and contains neither
  `rd=ufsroot0` nor `ufsrw=1`; the image has not been flashed.
- On 2026-11-01 the Note 8 was detected in TWRP as `greatlte`; the
  BOOT-by-name symlink resolved to `/dev/block/sda7` and its size was the
  expected 81920 sectors. Flashed `xnu-boot-ufs7.img` to BOOT only. Readback
  SHA-256 matched `efe44c907d8119d2511c8ca6bb00379188b8001477d30981e696a6f2ab3fd33b`.
  USERDATA and all other partitions were not touched.
- Rebooted the device to run the read-only UFS probe. ADB did not reconnect
  within 90 seconds after leaving TWRP; this is consistent with the boot
  handoff but does not establish whether XNU reached the UFS diagnostic.
- Photo `IMG_20261101_113713248.jpg` shows XNU past CPU startup, HID
  registration, platform expert startup and kernel post-boot initialization;
  it has no UFS result. The later photo
  `IMG_20261101_113943718.jpg` shows the UFS diagnostic and root wait.
- **2026-11-01 photo evidence, read-only UFS probe:** the PHY table reports
  `9 ok 0 err`; `DME_LINK_STARTUP` reports result 0 (the captured UIC status
  is `0x404`, with UIC error details also printed). The first SCSI TUR then
  times out with `HCE=1`, `HCS=0xf`, `IS=0`, and `UTRLDBR=1`. W-LUN TUR,
  START STOP UNIT, and the later LUN 0 TUR also time out; bring-up ends with
  error 60 and XNU reaches `Waiting on ... Apple_HFS`. This proves that the
  kernel/PHY diagnostic path runs and link startup returns success, but it
  does **not** prove that the UFS device accepts SCSI commands or that the
  link is fully operational. No GPT was read. USERDATA and all other
  partitions remain untouched.
- The `Archivio/Downloads` and `Space2/Downloads` copies of each photo are
  byte-identical; the SHA-256 for `IMG_20261101_113943718.jpg` is
  `ccc28e79…9d7c054`.
- Added `0226-greatlte-ufs-timeout-diagnostics.patch`. On a SCSI timeout it
  snapshots the slot-0 UTRD and UCD before clearing the wedged slot, and logs
  the command/response UPIU, UTRL base/run registers, Nexus register and UIC
  error registers. `git apply --check` succeeds after patches 0222–0225.
- Commit `a1f40f4` pushed to `greatlte`; CI run `41314001168` succeeded in
  17m39s. Its log explicitly applies 0226; the unrelated donor patches
  `iobuffermemd_monterey`, `skywalk_sonoma`, `syntax_checker_sonoma` and
  `TrustCache` are reported as skipped, as before. Kernel SHA-256:
  `568e039c7ff218154981e9a13345e80c55cbf8a609508b49f986ebafa23e01f3`.
- Built `xnu-boot-ufs8.img` from the verified stock BOOT backup and that
  kernel. Its payload command line is `debug=0xc serial=3 cpus=1 keepsyms=1
  startup_debug=1 ufsprobe=1 -enable_kprintf_spam -noprogress`; it contains
  neither `rd=ufsroot0` nor `ufsrw=1`. Image size 18,317,328 bytes; SHA-256
  `8920da5d957b9efe579edc5951f51b4a881b1f3625f43ab6c0865ff96193c098`.
- Flashed that image to BOOT `/dev/block/sda7` from TWRP only; device identity,
  by-name path and 81920-sector size were checked. Readback SHA-256 matched.
  Rebooted to run the probe. ADB is now disconnected, which is expected for
  this XNU path; physical screen result is pending. USERDATA and all other
  partitions remain untouched. Next: read the new screen output, then use the
  UTRD/UCD evidence to choose a driver fix. Do not mount UFS or enable
  `ufsrw=1` until TUR and GPT reads succeed.
- **2026-11-01 photos after 0226 (`IMG_20261101_153412521.jpg`,
  `IMG_20261101_153416835.jpg`):** the controller still does not consume slot
  0. At timeout, `HCE=1`, `HCS=0xf`, `IS=0`, `UTRLDBR=1`, `UTRLRSR=1`;
  UTRL base `0x9589a000`, UCD address `0x9589b000`, UCD response region
  offset/length `0x200/0x200`. OCS remains `0xf` and the response UPIU is all
  zero. The command header uses W-LUN `0xd0` and advancing tags; no GPT read
  succeeds. `DME_LINK_STARTUP` completes with result 0 but reports PA error
  `0x80000010` (generic PA/line-reset indication); later UIC error registers
  are zero. This narrows the failure to post-link transport/HCI setup or DMA
  request consumption; it does not show a SCSI response.
- Compared the source sequence with Samsung's Exynos UFS driver. Its
  `exynos_ufs_post_link()` establishes the UniPro CPort after link startup,
  then configures HCI data reorder and AXI DMA burst length. GreatLTE 0225
  had not reproduced that post-link sequence. Added `0227-greatlte-ufs-post-link-setup.patch`
  to set CPort idle, device/peer IDs, peer CPort, default CPort flags, traffic
  class, then connected state, and configure/read back those two HCI fields.
  Patches 0222–0227 apply in order locally. This is a source-based correction
  candidate; it still needs CI build and a read-only device trial. Continue
  using `ufsprobe=1`, with no root mount or USERDATA writes.
- CI run `41318162902` completed successfully for commit `13439af`
  (`0227-greatlte-ufs-post-link-setup.patch`), including the A53 compatibility
  check. Downloaded kernel SHA-256:
  `5ac226c529de4aa94aca0e22a861daeb928f859d1ae5a4a4c6db0cb8216bafb7`.
  Kernel strings contain the post-link CPort-connected and failure markers.
- Built `xnu-boot-ufs9.img` from that kernel and the preserved stock BOOT
  backup. The appended payload contains `ufsprobe=1`; it has no `rd=ufsroot0`
  or `ufsrw=1`. The packaged image is 18,317,328 bytes (below the 40 MiB BOOT
  size) and SHA-256 is
  `8dcc47fb2e40a76093f9ba8980137f9084b1c29b9ef5df1d58a333942bb8f267`.
- TWRP again identified the phone as `greatlte`, resolved BOOT to
  `/dev/block/sda7`, and reported 81920 sectors. Flashed `xnu-boot-ufs9.img`
  to BOOT only; the readback SHA-256 matched. Rebooted for the diagnostic
  trial. ADB is disconnected after leaving TWRP; no new screen result is
  available yet. All other partitions, including USERDATA, remain untouched.
- Next step: capture the screen after this boot and inspect the new post-link
  setup and SCSI timeout diagnostics. Until TUR and GPT reads succeed, do not
  mount UFS or enable `ufsrw=1`.
- **2026-11-01 photo `IMG_20261101_161437503.jpg` (SHA-256
  `b4921582aad8ca3e295cfe902b32ec434fcaeb2fdaeeb07a00c9baa9b499e4ea`):**
  the complete 0227 run logs `post-link CPort connected`, then the W-LUN and
  LUN 0 SCSI commands still time out (error 60); no response UPIU or GPT read
  is obtained. The lower part of the photo begins a second UFS initialization
  and cuts off at link startup, so it is incomplete evidence for that later
  attempt.
- Compared the failure with the public Galaxy S8 Exynos 8895 port. Its
  working UFS path sets UTRD command type CT=1, treats HCE=0/HCS=0xf as the
  running S-Boot host, and reuses that link instead of restarting HCE/PHY or
  DME link startup; it wakes the device through the W-LUN. GreatLTE patch 0224
  had changed CT to 0, and patches 0223–0227 restart and reconfigure the
  already-used link. Those differences explain why the generic CPort change
  did not resolve the timeout. Reference code: `Floppikrob/ios-galaxy-s8`,
  `tools/dreamlte/apply-dreamlte.py` and `shim/dreamlte/ufs_probe.c`.
- Added `0228-greatlte-ufs-reuse-sboot-link.patch`: restore Exynos storage
  CT=1, accept HCE=0 when HCS reports all ready bits, and default to S-Boot's
  existing link before waking the W-LUN and probing LUN 0. The previous HCE/
  PHY/DME restart path is retained only behind explicit `ufslinkrestart=1`;
  the read-only probe does not set it. Timeout cleanup no longer writes the
  Exynos-broken UTRLCLR register. This is based on the successful same-SoC S8
  implementation; it still needs a CI build and another device result.
- CI run `41321503094` for commit `496f914` applied
  `0228-greatlte-ufs-reuse-sboot-link.patch` and passed in 12m42s, including
  the Cortex-A53 compatibility check. Kernel SHA-256:
  `888e9b59e400a3898917092beec5dcd8085f2ebb7ca1b7f0977c0e7bda1f5e19`.
- Built read-only probe `xnu-boot-ufs10.img` from that kernel and the preserved
  stock BOOT backup. Payload command line includes `ufsprobe=1`, with no
  `ufslinkrestart=1`, `rd=ufsroot0`, or `ufsrw=1`. Image size is 18,317,328
  bytes; SHA-256:
  `a222c80ea1848e037fb3087e901af3d074b41d3c24dc067150aeb9f0dcd69fc4`.
- TWRP identified `greatlte`, BOOT resolved to `/dev/block/sda7`, size 81920
  sectors. Flashed `xnu-boot-ufs10.img` to BOOT only and verified matching
  readback SHA-256. Rebooted to run the probe; ADB is disconnected after
  leaving TWRP. The screen result is pending. USERDATA and other partitions
  remain untouched.
- **2026-11-01 photo `IMG_20261101_164606420.jpg` (SHA-256
  `7accb977d46d26fa2cada1420e8a0b7914cb9617f27894439fb97c74f9875bd9`):**
  the 0228 read-only probe now succeeds. UFS returns a real CHECK CONDITION
  on the device W-LUN (`sense key 2`, ASC/ASCQ `04/02`, initialization
  required); START STOP UNIT (ACTIVE) returns 0, LUN 0 TEST UNIT READY returns
  0, READ(10) LBA 1 returns `EFI PART`, and the kernel reads the 128-entry GPT
  and lists all 23 partitions, including USERDATA (52,744 MiB). `probe done
  (0)` confirms the diagnostic path's read-only storage test. The kernel then
  continues through BSD/Skywalk startup and waits for an Apple_HFS root, as
  expected because this boot has no iOS root image or `rd=ufsroot0`. The photo
  also shows a second UFS initialization starting later; it is cut off before
  its result, so that path still needs confirmation. No UFS writes have been
  made and USERDATA remains untouched.
- The S8 code was the right Exynos 8895 reference for the UFS transport: its
  storage path uses CT=1, reuses the S-Boot host/link and wakes the device W-LUN.
  This first Note 8 GPT read verifies those adapted transport changes on this
  device. Next: confirm the regular root-device initialization, prepare an
  iPhone X iOS 16.7.16 HFSX root from an owner-provided IPSW, and only then
  request explicit confirmation before any write to USERDATA. Touch, buttons,
  and iOS userland remain separate unverified milestones.
- Owner-provided IPSW located at `/home/agnell0/Archivio/Downloads/` and
  inspected read-only with `tools/a5xelte-inspect-ipsw.py`: iPhone10,3 and
  iPhone10,6, iOS 16.7.16 build 20H392, D22AP. Extracted the 182 KiB D22AP
  device tree to ignored local file `research/ipsw-x/d22ap.adt`; it is not
  committed. `tools/mkadt_greatlte.py` now imports its real `/product` node.
  Generated ADT is 9,596 bytes and includes the iPhone X product name and 63
  product properties.
- The user has since made `/run/media/agnell0/Space1` available with 27.2 GiB
  free. Linux's available APFS FUSE driver explicitly lacks LZFSE decoding,
  so it is not suitable for producing this root. Added a dedicated private-
  repository macOS workflow (`greatlte-ios-root.yml`) using Apple's `hdiutil`
  path; it builds a 20 GiB HFSX root, applies a GreatLTE-named system-tuning
  script derived from the herolte reference, and publishes the split image
  only as a private release.
- Private build repository created with only the workflow and its four
  required files; donor notes, private addresses, dumps, and local IPSW are
  excluded. Initial run `41337418395` was cancelled before any job steps
  because its `macos-14` runner was retiring on 2026-11-02. Updated the
  workflow to `macos-15` and run `41337486410` completed successfully.
- The private release `greatlte-ios-root-16.7.16-41337486410` contains the
  D22AP tree, SHA-256 manifest, and three compressed root-image segments.
  All four release assets match the manifest. Reassembled
  `/run/media/agnell0/Space1/greatlte-ios-root-20g/root.img`: 21,474,836,480
  bytes, HFSX `HX` signature, SHA-256
  `f9dd05225e8b082d71765bb3f5d47361bffb5b90ebb62a3ffcff4d1a7fb16410`.
- Built the candidate BOOT image with `rd=ufsroot0 ufsroot=USERDATA ufsrw=1`
  at `/run/media/agnell0/Space1/greatlte-ios-root-20g/xnu-boot-greatlte-iosroot.img`,
  SHA-256 `c5a4163a7c35a693ea0623975f2a06f834385e699160097cf0bd81c161941bdb`.
  TWRP identified `greatlte` / Galaxy Note8; USERDATA resolved to
  `/dev/block/sda23`, 55,307,120,640 bytes. Following the owner's explicit
  install authorization, wrote the 20 GiB HFSX image to p23 (leaving other
  partitions unchanged) and read back its first 20 GiB; SHA-256 matched the
  host image. Saved the current 40 MiB BOOT partition as
  `/run/media/agnell0/Space1/greatlte-ios-root-20g/boot-before-root.img`
  (SHA-256 `085fea713a8312f0bb2b269e370858db94270d0545f4150d0495b3d46ad8ca12`);
  stock BOOT and EFS backups remain intact and their hashes match.
- Wrote the XNU root boot image to BOOT p7 (`/dev/block/sda7`) and read back
  20 MiB; the candidate's 18,321,424-byte prefix matched SHA-256
  `c5a4163a7c35a693ea0623975f2a06f834385e699160097cf0bd81c161941bdb`.
  Rebooted from TWRP. At the last check the phone no longer enumerated on USB
  and ADB was unavailable. Since this port has no iOS USB driver, that alone
  does not distinguish a successful boot from a kernel hang. Screen result,
  root mount, launchd, and UI behavior remain unverified; next evidence needed
  is the phone display or a return to TWRP with a persistent panic log.
- **2026-11-01 first root-boot photo** (`IMG_20261101_202912065.jpg`): the
  Note 8 successfully reuses the S-Boot UFS link, starts the device, reads
  USERDATA as read-write, and mounts `IOSROOT` as `ufsroot0`. BSD and kernel
  startup continue. Userland then fails at `load_init_program`: the
  development launchd path is absent and `/sbin/launchd` is killed with
  `CS_KILLED` (`namespace 9 code 0xe`). This is evidence of a kernel code
  signing enforcement mismatch, not a UFS/root mount failure. The screen also
  contains later kernel output, but the photo does not establish that
  launchd or SpringBoard recovered. The boot command line omitted
  `cs_enforcement_disable=1` (and the unsigned-userland boot settings used by
  the reference port).
- Prepared, but have **not yet flashed**, a corrected BOOT candidate using the
  verified UFS10 kernel and the same USERDATA root, adding
  `rootrw=1 cs_enforcement_disable=1 unentitled_ios_sim_launch=1
  ignition_level=1 launchd_unsecure_cache=1 wdt=-1 -wdt_no_pmu
  wdt_test=no_user_checkin`. Image:
  `/run/media/agnell0/Space1/greatlte-ios-root-20g/xnu-boot-greatlte-iosroot-csfix.img`,
  18,321,424 bytes, SHA-256
  `deca1dfae54678377b63166176f766aeb1caa2e4810a620b08b7c7ce8042390e`;
  packer confirms it fits the 40 MiB BOOT partition. At this check `adb
  devices -l` shows no attached device, so no BOOT write or reboot was
  attempted. USERDATA and all protected partitions remain unchanged.
- The corrected BOOT candidate was subsequently flashed from TWRP after ADB
  identified `greatlte`, BOOT resolved to `/dev/block/sda7`, and p7 reported
  81920 sectors. The 18,321,424-byte write completed and readback SHA-256
  matched `deca1dfae54678377b63166176f766aeb1caa2e4810a620b08b7c7ce8042390e`.
  Rebooted to retry iOS startup. ADB disconnected as expected on leaving TWRP;
  the post-fix launchd/UI result is pending a screen photo. No partition other
  than BOOT was written in this step.
- **2026-11-01 post-fix userland photos** (`IMG_20261101_203654834.jpg`,
  `IMG_20261101_203710208.jpg`, `IMG_20261101_203720859.jpg`,
  `IMG_20261101_203749176.jpg`, `IMG_20261101_203755184.jpg`,
  `IMG_20261101_203838573.jpg`): after the BOOT fix, the screen advances past
  the previous `CS_KILLED` launchd failure and prints a changing stream of
  daemon/XPC launches, including `xpcproxy`, `bluetoothd`, `fairplayd.H2`,
  `homed`, `ManagedSettingsAgent`, `pfd`, and Siri embedded speech. Repeated
  `exec xpcproxy` entries are process-launch diagnostics and are consistent
  with launchd starting XPC services; they are not by themselves a crash
  message. SWEET AKS stub calls mostly return `0x0`; one `rapportd` sandbox
  privilege denial and a flowswitch/utun notice are visible. The photographed
  log has not yet shown `backboardd`/`SpringBoard` or the iOS UI, so userland
  startup is progressing but the Hello screen remains unverified. The Android
  boot logo is still the framebuffer background. No new partition writes.
- **2026-11-01 later startup photo** (`IMG_20261101_204211946.jpg`): the
  visible launch log has advanced beyond the previous six frames and now
  includes `com.apple.datamigrator`, `mobiletimerd`, `nfcd`, `followupd`,
  `navspushd`, `nehelper`, and `routined`. No fresh kernel banner, panic, or
  return to the first launch lines is visible, so this frame does not support
  a reboot loop; repeated `xpcproxy` exec messages continue amid new jobs.
  `backboardd`, `SpringBoard`, and an iOS display are still not visible.
- **2026-11-01 user report (~40 minutes after the 20:42 photo):** the display
  continues showing repeated exec/service strings and has not reached the iOS
  UI. No newer photo is present in Downloads and ADB currently lists no
  device. Treat this as a userland startup stall or service respawn loop rather
  than an acceptably slow first boot; the available photo does not identify
  the exact process or prove that the kernel is rebooting. Next recovery is to
  return to TWRP without wiping/formatting USERDATA, then collect any available
  boot logs and inspect the root filesystem. No further writes have been made.
- **TWRP read-only diagnostics after the reported long startup:** ADB sees
  `greatlte` in recovery. TWRP reports no `hfsplus` filesystem support and
  cannot mount `/data`; `/sys/fs/pstore` is empty (no persistent previous
  kernel panic). Read the final 4,198,400 bytes of p23 (offset 55,302,922,240)
  without writing; the region is all zero and has no `SWEETLOG` header. The
  GreatLTE kernel path does not call the SWEET UFS log/sampler startup, so
  those generic facilities did not record this run. Added
  `0229-greatlte-process-sampler.patch` to start the existing sampler from the
  GreatLTE UFS root init; it should print SpringBoard/backboardd thread
  backtraces after 90 seconds and every 120 seconds. Patch applies to the
  locally reconstructed 0222–0228 GreatLTE UFS source; CI build/device trial
  still pending. USERDATA was read only during these diagnostics.
- CI run `41346553548` for 0229 failed at link: the sampler source patch
  `0088` intentionally wrapped `sweet_sample.c` in a SWEET-only guard, and
  0207 extended that guard only to HEROLTE. `greatlte_ufs.o` therefore had an
  unresolved `sweet_sample_start` reference. Updated 0229 to extend the guard
  to GREATLTE as well; the patch applies after 0207 in a local source
  reconstruction. No device image was produced or flashed from the failed run.
- CI run `41347832800` built successfully on commit `30bd1db`; kernel
  `kernel.development.greatlte` SHA-256
  `93f5f8ac53a0778e4ae9fbcc3e545728788bf9be83db029f3cee6f3b67ad92c9`.
  The built kernel contains `_sweet_sample_start`; the artifact manifest
  matches its hash. Prepared BOOT image
  `/run/media/agnell0/Space1/greatlte-ios-root-20g/xnu-boot-greatlte-native-sampler.img`
  (18,321,424 bytes, SHA-256
  `cbd28a97d7e546c224e940c024f82c6a27a085c1e5da7520d562f53ddd84120a`)
  with the existing iOS root/signing flags plus `sweetfb_native=1` and
  `cpus=1`. This follows the S8 port's workaround for its failed first frame
  in iPhone X logical resolution; it is a hypothesis to test on GreatLTE.
- Flashed this image from TWRP after confirming device `greatlte`, BOOT
  `/dev/block/sda7`, and 81920 sectors. Readback SHA-256 matched exactly.
  Rebooted to the iOS trial. Photos received at 22:02–22:03 local
  (`IMG_20261101_220234814 (1).jpg`,
  `IMG_20261101_220300999 (1).jpg`, `IMG_20261101_220347419.jpg`) show the
  iOS lock screen on the Note8, with `SWEET SURF: SpringBoard` in the nearby
  console output. This is the first device evidence of the iOS UI appearing;
  it strongly supports the S8 native-framebuffer workaround, though the image
  alone does not isolate it as the only cause. One framebuffer report shows
  only 1 frame in 5268 ms (~0.1 fps), so rendering is still extremely slow.
  Another photo shows `assetsd` crashing (namespace 2, code 0x6); the UI is
  still visible. Touch input and lock-screen interaction have not been tested,
  and the GreatLTE touch driver is not implemented. The photos do not show a
  process-sampler backtrace yet. No partition other than BOOT was written;
  USERDATA was not changed.
- Touch source comparison for the next step: GreatLTE's Samsung DTS describes
  `hsi2c_23` at `0x108e0000`, touchscreen address `0x48`, GPA1-0 interrupt,
  4095x4095 coordinates, `tsp_io`/`tsp_avdd` boot-on rails, and firmware
  `y661_great.fw`. Its Y661 driver uses coordinate/status/gesture event IDs
  0/1/2 and the same 8-byte coordinate record layout and `0x60`/`0x61` event
  commands as the S8 touch path. The S8 controller is S6SY761, so the bus
  transfer and coordinate decoding are reusable, but its ID command is not:
  GreatLTE reads the Y661 ID with `0x22`. Patch `0230` adds a polled GreatLTE
  touch path that reads the Y661 ID, preserves existing touch-function bits,
  enables sensing, and forwards touch events to SweetHID; it does not update
  controller firmware or NVM. The patch applies to the source tree from the
  successful sampler build. CI compilation and physical touch interaction are
  still pending.
