# GREATLTE (Galaxy Note 8 SM-N950F/DS, Exynos 8895): progress

Log device evidence, build results and open questions here. Keep source-derived
facts separate from measurements on the phone.

## 2026-10-30

- Target device: SM-N950F/DS (DUOS), `greatlte`, Exynos 8895, bought in Italy.
  Bootloader unlocked; TWRP available; currently LineageOS. Exact model still
  to be confirmed with `ro.product.device` and `ro.board.platform`.
- Created the `greatlte` branch from `herolte` (commit `b649c85`) and added:
  - `docs/greatlte-bringup.md`: scope, hardware map, phases, open questions;
  - `tools/greatlte-preflight.py`: read-only adb inventory and BOOT backup
    helper.
- Hardware map extracted from `exynos-linux-stable/greatlte` (`tw90-android`)
  and `ivoszbg/uniLoader` `board-dreamlte.c`:
  - boot CPU: Cortex-A53, MPIDR `0x100`; Mongoose M2 at `0x0`..`0x3`;
  - GIC-400 distributor `0x10201000`, CPU interface `0x10202000`;
  - timer 26 MHz, virtual PPI 11 -> INTID 27;
  - UFS at `0x11120000` (UNIPRO `0x11110000`, protector `0x11130000`);
  - DECON_F `0x12860000`, DSIM `0x12870000`;
  - touch `sec_ts` at HSI2C `0x108e0000`, address `0x48`, IRQ `gpa1-0`;
  - keys: power `gpa2-4`, vol- `gpa0-4`, vol+ `gpa0-3`, Bixby `gpa0-6`;
  - PMIC S2MPS17 on SPEEDY `0x15b50000`;
  - candidate XNU window `0x90000000`..`0xb0000000`;
  - framebuffer hypothesis `0xcc000000`, 1440x2960 (from dreamlte, not yet
    measured on greatlte).
- No code has run on the phone yet. `adb devices` showed no attached device.
- Next: run the preflight from LineageOS/TWRP, save BOOT and EFS/modem/persist,
  then build the Phase 1 probe (no XNU, no USERDATA writes).

## Claims

- Source-derived: all addresses above from the public DTS and uniLoader.
- Device-verified: none yet.
- Build-verified: none yet.
