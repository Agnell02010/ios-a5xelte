# greatlte (SM-N950F/FD, Exynos 8895): XNU / iOS 16 bring-up plan

Status: **Phase 1 complete; Phase 2 in progress.** The greatlte probe ran on
the phone and printed the S-Boot handoff. The XNU loader, ADT and `GREATLTE`
kernel target are written; the first XNU build/boot is next. The reference
implementation is the `herolte` branch (Galaxy S7, Exynos 8890), which reaches
the iOS 16.7.16 "Hello" setup screen with touch and buttons.

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

## Hardware map (measured on the phone unless noted)

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
| Boot CPU | Cortex-A53, MPIDR `0x100`, MIDR `0x410FD034` | Probe + live FDT |
| Other cluster | Mongoose M2, MPIDR `0x0`..`0x3` | Live FDT; leave unused initially |
| PSCI | `enable-method = "psci"`, SMC | Reuse herolte SMP approach |
| GIC | GIC-400: distributor `0x10201000`, CPU interface `0x10202000` | Live FDT |
| Timer | 26 MHz, virtual timer PPI 11 -> INTID 27 | Live FDT (`clock-frequency 0x18cba80`) |
| RAM (live FDT) | `0x80000000+0x3c800000`, `0xc0000000+0x40000000`, `0x880000000+0x80000000`, `0x900000000+0x80000000` | 6 GB |
| XNU window | `0x92400000`..`0xb1000000` (492 MiB) | Between Samsung secure logs and TIMA |
| Framebuffer | `0xcc000000`, 1440x2960, ARGB8888, stride 5760 | Probe `FB=0xCC000000`; bootargs `s3cfb.bootloaderfb` |
| DECON | `DECON_F` `0x12860000`; HW trigger register `+0x70` read as `0x1291` | Probe |
| DSIM | `0x12870000` | Live FDT |
| Storage | UFS 2.1 at `0x11120000` (HCI +0, vendor +0x100, UNIPRO `0x11110000`, protector `0x11130000`) | Live FDT |
| FDT / initrd | FDT `0x8a000000`; initrd `0x89000000`..`0x8918067c` | Probe |
| Image load | `0x800ec000` (not the BOOT header's `0x10008000`) | Probe |
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
- Loader copies XNU into the `0x92400000`..`0xb1000000` window, passes a
  minimal ADT and boot-args, jumps.
- Success criterion: XNU C console output on screen, VM bootstrap, scheduler.
  **Device-verified 2026-10-30:** BSD init completes, Skywalk self-tests pass,
  and the kernel waits on `IOMedia … Apple_HFS` (the Phase 2 end state).

Prepare the image on the host (the stock BOOT is only read):

```sh
gh run download <GREATLTE_RUN_ID> -R Agnell02010/ios-a5xelte \
    -n xnu-kernel -D xnu-kernel
tools/greatlte-make-xnu-boot.sh xnu-kernel/kernel.development.greatlte \
    xnu-boot.img
```

Flash only BOOT from TWRP and reboot:

```sh
adb push xnu-boot.img /tmp/xnu-boot.img
adb shell 'dd if=/tmp/xnu-boot.img of=/dev/block/sda7 bs=4096'
```

Restore the stock BOOT by flashing `backup/greatlte/BOOT.img` the same way.
The loader prints the failure reason on screen and requests TWRP after 30 s;
a hard hang is recovered with Vol- + Power ~7 s, then Vol+ + Bixby + Power.

### Phase 3 — storage and root

- Adapt the herolte Exynos UFS driver to the 8895 controller at
  `0x11120000` (UNIPRO `0x11110000`, protector `0x11130000`); add the
  `greatlte-ufs` ADT node and a read-only probe first.
- Then HFSX ramdisk root, then USERDATA read/write.
- Success criterion: `hfs: mounted ... on device`, launchd starts.

The UFS PHY/link initialization is implemented in patch `0225`. Build a
read-only diagnostic image from its kernel artifact with `ufsprobe=1` (do not
set `rd=ufsroot0` or `ufsrw=1` for this probe):

```sh
gh run download 41243017134 -R Agnell02010/ios-a5xelte \
    -n xnu-kernel -D xnu-kernel-ufs5
tools/greatlte-make-xnu-boot.sh \
    xnu-kernel-ufs5/kernel.development.greatlte xnu-boot-ufs5.img \
    'debug=0xc serial=3 cpus=1 keepsyms=1 startup_debug=1 ufsprobe=1 -enable_kprintf_spam -noprogress'
```

The image only probes UFS and reads the LUN 0 GPT; it does not mount or write
USERDATA. Flashing still replaces BOOT, so verify the stock BOOT backup and
confirm the target device before using the existing BOOT flash helper.

### Phase 4 — display, touch, keys

- iPhone X canvas 1125x2436 scaled/presented on 1440x2960.
- `sec_ts` touch and GPIO keys.
- Success criterion: Hello screen with working touch and buttons.

### Phase 5 — userland

- Build/flash the iPhone X iOS 16.7.16 root image.
- Apply greatlte-specific root tweaks.
- Success criterion: launchd, backboardd, SpringBoard, Hello screen.

## Reserved / occupied physical memory (from the live FDT and bootargs)

The low 3 GiB bank is not a flat RAM range. Keep the XNU window clear of:

| Range | Owner |
| --- | --- |
| `0x80000000`..`0x80004000` | S-Boot / DT |
| kernel image from `0x800ec000`, ~40 MiB | S-Boot |
| `0x89000000`..`0x8918067c` | initrd |
| `0x8a000000` | FDT |
| `0x91200000` | ESS setup (`ess_setup=0x91200000`), ends before `0x92200000` |
| `0x92202000`, `0x92244000`, `0x92286000`, `0x92388000` | Samsung `sec_avc_log`, `sec_tsp_log`, `sec_debug.base`, `auto_summary_log` |
| `0xb1000000`..`0xb1200000` | TIMA (`tima_region`, `tima_log`) |
| `0xc0000000`..`0xc0010000` | `seclog_mem` |
| `0xcc000000`..`0xcd043000` | S-Boot framebuffer (17,049,600 bytes) |
| `0xd0000000`..`0xd1400000` | secure camera |
| `0xe6c00000`..`0xea800000` | video stream |
| `0xea800000`..`0xeac00000` | ABOX |
| `0xf3400000`..`0xf4c00000` | crypto |
| `0xf4c00000`..`0xfdc00000` | modem |
| `0xfdc00000`..`0xffc00000` | CP RAM logging |
| `0xffc00000`..`0x100000000` | GNSS |

The window `0x92400000`..`0xb1000000` is clear in this map. It ends exactly
at TIMA; do not grow it upward.

## Open questions

1. Touch controller protocol/firmware differences from herolte.
2. S2MPS17 rail mapping for touch and display.
3. UFS host quirks after S-Boot handoff.
4. Panel scaling/letterboxing for the 18.5:9 display.
5. Real D22AP `/product` tree for iOS userland (missing until the IPSW is
   downloaded and extracted).

## Safety

- Writing BOOT replaces TWRP/LineageOS boot; keep a backup and Odin.
- Writing USERDATA erases Android data; back up first.
- The iOS root is not secure; do not sign in with an Apple ID or store
  personal data.
- Apple's userland must be built from an IPSW the owner provides; do not
  publish it.
