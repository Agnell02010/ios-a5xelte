# greatlte (SM-N950F/FD, Exynos 8895): XNU / iOS 16 bring-up plan

Status: **planning + hardware inventory only.** No greatlte code has run on a
phone yet. The reference implementation is the `herolte` branch (Galaxy S7,
Exynos 8890), which reaches the iOS 16.7.16 "Hello" setup screen with touch and
buttons.

## Scope and non-goals

- Target: the same milestone as `herolte` — XNU boots, CPU-rendered iOS 16
  userland reaches the Hello screen, touch and hardware keys work.
- The iOS userland is the **iPhone X (iPhone10,3) iOS 16.7.16** root, built
  from an IPSW the device owner provides. Apple's software is not in this
  repository.
- **Not** iOS 18 or iOS 26. Those userlands target newer Apple SoCs (PAC,
  Secure Enclave, different drivers); moving this port to them is a separate
  kernel project, not a configuration change.
- **Not** a secure phone. The port disables AMFI, sandbox and data protection,
  and uses a stub AppleKeyStore. Do not use an Apple ID or personal data.
- **Not** a daily driver. No GPU, Wi-Fi, Bluetooth, modem, audio, camera,
  sensors, real battery reporting or sleep. Rendering is on the CPU.

## Hardware map (from public sources, not yet device-verified)

Sources:

- `exynos-linux-stable/greatlte`, branch `tw90-android`:
  `arch/arm64/boot/dts/exynos/exynos8895.dtsi`,
  `exynos8895-greatlte_common.dtsi`,
  `exynos8895-greatlte-rmem.dtsi`.
- `ivoszbg/uniLoader`, `board/samsung/board-dreamlte.c` (Galaxy S8, same
  Exynos 8895 SoC and same 1440x2960 panel resolution).
- `herolte` docs and patches in this repository.

| Item | greatlte | Confidence / action |
| --- | --- | --- |
| SoC | Exynos 8895: 4x Cortex-A53 + 4x Mongoose M2 | From DTS |
| Boot CPU | Cortex-A53, MPIDR `0x100`..`0x103` | DTS `cpu@100`; verify with probe |
| Other cluster | Mongoose M2, MPIDR `0x0`..`0x3` | Leave unused initially, like herolte |
| PSCI | `enable-method = "psci"`, SMC | Reuse herolte SMP approach |
| GIC | GIC-400: distributor `0x10201000`, CPU interface `0x10202000` | DTS |
| Timer | 26 MHz, virtual timer PPI 11 -> INTID 27 | DTS; verify CNTFRQ in probe |
| RAM (DTS) | `0x80000000+0x3c800000`, `0xc0000000+0x40000000`, `0x880000000+0x80000000` | 6 GB variant needs boot-DTB verification |
| Candidate XNU window | `0x90000000`..`0xb0000000` (512 MiB), below TIMA `0xb1000000` | Same window as herolte; verify against boot DTB |
| Framebuffer (hypothesis) | `0xcc000000`, 1440x2960, ARGB8888, stride 5760 | From dreamlte; **must** be confirmed by probe |
| DECON | `DECON_F` `0x12860000`; HW trigger `+0x70` | DTS + dreamlte |
| DSIM | `0x12870000` | DTS |
| Storage | UFS 2.1 at `0x11120000`; UNIPRO `0x11110000`; protector `0x11130000` | DTS; adapt herolte UFS patch |
| Touch | `sec,sec_ts` at HSI2C `0x108e0000`, address `0x48`, IRQ `gpa1-0` | DTS; protocol needs device test |
| Touch rails | `tsp_io`, `tsp_avdd` | DTS; PMIC mapping to verify |
| Touch firmware | `tsp_sec/y661_great.fw` | DTS |
| Keys | Power `gpa2-4`, Vol- `gpa0-4`, Vol+ `gpa0-3`, Bixby/Wink `gpa0-6` | DTS; no Home key |
| PMIC | S2MPS17 on SPEEDY `0x15b50000`; S2MPB02 `0x59`; S2DOS03 `0x60` | DTS; dreamlte uses S2MPS17 LDO34/35 for touch |
| Boot | Samsung S-Boot, BOOT partition, boot.img with DTBH | Same family as herolte |
| Initrd (DTS) | `0x82000000`..`0x820fffff` | DTS placeholder; probe must find the real range |
| FDT | To be measured | Probe |
| Partition path | Likely `/dev/block/platform/11120000.ufs/by-name/` | Verify in TWRP |

The DTS is a 4 GB configuration in places; the SM-N950F/DS is a 6 GB device.
The boot DTB and the probe are authoritative.

## Reused from herolte

- XNU 8796, 4 KiB pages, non-PAC, Cortex-A53, GICv2, 39-bit VA.
- HFSX root in USERDATA, read/write, AMFI/sandbox bring-up stubs.
- IOSurface / IOMobileFramebuffer services and the CPU framebuffer copy.
- HID event services, persistent console log, crash diagnostics.
- Loader/payload format, BOOT packer, root flasher, log puller.
- iPhone X identity and the iOS 16.7.16 root image.

## New for greatlte

- `MACHINE_CONFIG=GREATLTE` board header and board target patch.
- `tools/mkadt_greatlte.py`: GIC, UFS, display, touch, keys, PMIC nodes.
- `shim/greatlte/`: probe and XNU loader with greatlte addresses.
- Exynos 8895 UFS host adaptation (base `0x11120000`).
- DECON/DSIM framebuffer handoff and iPhone X canvas scaling.
- `sec_ts` touch over HSI2C `0x108e0000` and S2MPS17 rail setup.
- GPIO keys (no Home button; use the iPhone X gesture identity).

## Phases

### Phase 0 — preflight and backups

- Run `tools/greatlte-preflight.py` with the phone in LineageOS or TWRP.
- Back up EFS, modem, persist, BOOT and the current LineageOS boot image.
- Keep Odin and a known-good boot image; Samsung recovery lives in BOOT.

### Phase 1 — probe (no XNU)

A small image in BOOT prints on the bootloader framebuffer:

- EL, SCTLR, FDT address, Image load address;
- MIDR/MPIDR, MMFR0/PFR0/ISAR0, CNTFRQ;
- framebuffer address/size, DECON trigger value;
- initrd range and payload range.

Success criterion: readable text on the phone, then reboot to TWRP. No
USERDATA writes.

### Phase 2 — XNU, one core

- Build `kernel.development.greatlte` with `MACHINE_CONFIG=GREATLTE`.
- Loader copies XNU into the `0x90000000` window, passes a minimal ADT and
  boot-args, jumps.
- Success criterion: XNU C console output on screen, VM bootstrap, scheduler.

### Phase 3 — storage and root

- UFS read-only probe, then HFSX ramdisk root, then USERDATA read/write.
- Success criterion: `hfs: mounted ... on device`, launchd starts.

### Phase 4 — display, touch, keys

- iPhone X canvas 1125x2436 scaled/presented on 1440x2960.
- `sec_ts` touch and GPIO keys.
- Success criterion: Hello screen with working touch and buttons.

### Phase 5 — userland

- Build/flash the iPhone X iOS 16.7.16 root image.
- Apply greatlte-specific root tweaks.
- Success criterion: launchd, backboardd, SpringBoard, Hello screen.

## Open questions

1. Actual framebuffer address and DECON state left by S-Boot.
2. Actual FDT and initrd addresses/ranges.
3. 6 GB RAM layout and a safe XNU window.
4. Touch controller protocol/firmware differences from herolte.
5. S2MPS17 rail mapping for touch and display.
6. UFS host quirks after S-Boot handoff.
7. Panel scaling/letterboxing for the 18.5:9 display.
8. Whether the bootloader starts on A53 `0x100` or on a Mongoose core.

## Safety

- Writing BOOT replaces TWRP/LineageOS boot; keep a backup and Odin.
- Writing USERDATA erases Android data; back up first.
- The iOS root is not secure; do not sign in with an Apple ID or store
  personal data.
- Apple's userland must be built from an IPSW the owner provides; do not
  publish it.
