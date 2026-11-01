#!/usr/bin/env python3
"""Build the greatlte (SM-N950F/DS, Exynos 8895) ADT for the GREATLTE XNU config.

Derived from mkadt_herolte.py. Addresses come from the phone's own live FDT
(read through TWRP: /sys/firmware/devicetree/base) and the S-Boot probe:
  - RAM window 0x92400000..0xb1000000, between Samsung's ESS/security logs
    (ends 0x92398000) and TIMA (0xb1000000);
  - GIC-400 distributor 0x10201000, CPU interface 0x10202000;
  - timer 26 MHz, virtual PPI 11 -> INTID 27;
  - framebuffer 0xcc000000, 1440x2960 (S-Boot s3cfb.bootloaderfb);
  - UFS host 0x11120000 (Exynos 8895 UFSHCI).
Storage is exposed as /greatlte-ufs; no touch or GPU nodes yet. The driver
work for those comes after the first XNU boot.
"""
import argparse
import os
from pathlib import Path

import adt
import mkadt

DRAM_BASE = 0x92400000      # between Samsung secure logs and TIMA
DRAM_SIZE = 0x1ec00000      # 492 MiB, ends exactly at TIMA 0xb1000000
SOC_BASE = 0x10000000       # arm-io ranges base; child regs are relative
FB_BASE, FB_WIDTH, FB_HEIGHT = 0xcc000000, 1440, 2960
GIC_DIST, GIC_CPU = 0x10201000, 0x10202000
UFS_BASE, UFS_SIZE = 0x11120000, 0x3000


def set_prop(node, name, value):
    for i, (key, flags, _) in enumerate(node.props):
        if key == name:
            node.props[i] = (key, flags, value)
            return
    node.props.append((name, 0, value))


def child(node, name):
    for candidate in node.children:
        if candidate.prop('name') == mkadt.cstr(name):
            return candidate
    raise ValueError(f'missing donor ADT node {name}')


def build():
    # The userland is the iPhone X (iPhone10,3 / D22AP). When the owner has
    # supplied its IPSW, mkadt.d22ap_product() imports the real /product
    # properties from research/ipsw-x/d22ap.adt (kept out of git).
    root = mkadt.build(seed=os.urandom(64), qemu=True)
    set_prop(root, 'compatible', mkadt.cstr('D22AP') + mkadt.cstr('iPhone10,3') +
             mkadt.cstr('samsung,a5xelte') + mkadt.cstr('samsung,greatlte') +
             mkadt.cstr('samsung,exynos8895') + mkadt.cstr('AppleARM'))
    set_prop(root, 'model', mkadt.cstr('iPhone10,3'))
    set_prop(root, 'target-type', mkadt.cstr('D22'))
    set_prop(root, 'target-sub-type', mkadt.cstr('D22AP'))
    chosen = child(root, 'chosen')
    set_prop(chosen, 'dram-base', mkadt.u64(DRAM_BASE))
    set_prop(chosen, 'dram-size', mkadt.u64(DRAM_SIZE))
    set_prop(chosen, 'firmware-version', mkadt.cstr('greatlte-entry'))
    set_prop(chosen, 'system-firmware-version', mkadt.cstr('greatlte-entry'))

    product_props = mkadt.d22ap_product()
    if product_props:
        # mkadt.build() allocates its synthetic-node phandles below 1000.
        root.children.append(mkadt.node('product', [
            ('AAPL,phandle', mkadt.u32(1001)),
        ] + product_props))

    cpus = child(root, 'cpus')
    cpus.children = []
    # S-Boot starts on the Cortex-A53 "Apollo" cluster at MPIDR 0x100. The
    # Mongoose cluster (0x000..0x003) is left out; one A53 is enough for the
    # first bootstrap and the loader does not start secondaries yet.
    cpus.children.append(mkadt.node('cpu0', [
        ('device_type', mkadt.cstr('cpu')),
        ('compatible', mkadt.cstr('arm,cortex-a53') + mkadt.cstr('ARM,v8')),
        ('reg', mkadt.u32(0x100)),
        ('cpu-id', mkadt.u32(0)),
        ('cluster-id', mkadt.u32(0)),
        ('cluster-type', mkadt.u32(0)),
        ('die-cluster-id', mkadt.u32(0)),
        ('cluster-core-id', mkadt.u32(0)),
        ('l2-cache-id', mkadt.u32(0)),
        ('l3-cache-id', mkadt.u32(0)),
        ('state', mkadt.cstr('running')),
        ('timebase-frequency', mkadt.u32(26000000)),
        ('clock-frequency', mkadt.u32(1794000000)),
        ('bus-frequency', mkadt.u32(100000000)),
        ('memory-frequency', mkadt.u32(1794000000)),
        ('peripheral-frequency', mkadt.u32(26000000)),
        ('fixed-frequency', mkadt.u32(26000000)),
    ]))

    arm_io = child(root, 'arm-io')
    set_prop(arm_io, 'device_type', mkadt.cstr('greatlte-io'))
    set_prop(arm_io, 'compatible', mkadt.cstr('samsung,exynos8895-io') +
             mkadt.cstr('arm-io'))
    set_prop(arm_io, 'ranges', mkadt.u64(0, SOC_BASE, 0xf0000000))
    arm_io.children = [n for n in arm_io.children if n.prop('name') == mkadt.cstr('wdt')]
    # GIC-400: distributor 0x10201000, CPU interface 0x10202000.
    arm_io.children.append(mkadt.node('gic', [
        ('compatible', mkadt.cstr('arm,cortex-a15-gic')),
        ('interrupt-controller', mkadt.cstr('master')),
        ('virtual-timer-intid', mkadt.u32(27)),
        ('reg', mkadt.u64(GIC_DIST - SOC_BASE, 0x1000, GIC_CPU - SOC_BASE, 0x1000)),
    ]))
    arm_io.children.append(mkadt.node('disp0', [
        ('device_type', mkadt.cstr('display-subsystem')),
        # AppleCLCD (SweetFramebuffer.cpp) matches 'samsung,a5xelte-display'
        # in KernelConfigTables.cpp; without it SpringBoard sees no main display.
        ('compatible', mkadt.cstr('samsung,a5xelte-display') +
         mkadt.cstr('samsung,greatlte-display')),
        ('canvas-width', mkadt.u32(FB_WIDTH)),
        ('canvas-height', mkadt.u32(FB_HEIGHT)),
    ]))

    root.children = [n for n in root.children if n.prop('name') not in
                     (mkadt.cstr('sweet-fbcon'), mkadt.cstr('sweet-ufs'))]
    # Exynos 8895 UFSHCI (exynos8895.dtsi ufs@0x11120000): standard HCI at
    # +0, vendor HCI +0x100, UNIPRO +0x8000 below, UFS protector +0x10000
    # above. Absolute address; a greatlte driver will read this node later.
    root.children.append(mkadt.node('greatlte-ufs', [
        ('reg', mkadt.u64(UFS_BASE, UFS_SIZE)),
    ]))
    # pe_serial.c looks this node up by name for the kprintf console.
    root.children.append(mkadt.node('a5xelte-fbcon', [
        ('reg', mkadt.u64(FB_BASE, FB_WIDTH * FB_HEIGHT * 4)),
        ('width', mkadt.u32(FB_WIDTH)),
        ('height', mkadt.u32(FB_HEIGHT)),
        ('stride', mkadt.u32(FB_WIDTH * 4)),
    ]))
    return root


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    blob = adt.serialize(build())
    args.output.write_bytes(blob)
    print(f'{args.output}: {len(blob)} bytes')
