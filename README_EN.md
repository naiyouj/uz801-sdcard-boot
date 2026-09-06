# UZ801 / MSM8916 Pocket WiFi Stick · Boot from SD Card

> Move the system off the eMMC and onto an SD card. **The stick keeps only its boot partition — the whole OS runs from SD.** Brick the system? Flash a new card and plug it in. The eMMC never gets written to again.

English | [简体中文](README.md)

---

## 🏷 Project Type

| Field | Value |
|---|---|
| **Type** | Embedded Linux boot modification / rootfs migration / flashable image builder / unbrick toolkit |
| **Hardware** | UZ801 pocket WiFi stick (OpenStick-style) |
| **SoC** | Qualcomm MSM8916 / Snapdragon 410, quad Cortex-A53 |
| **RAM / Storage** | 461 MB RAM / 3.6 GB eMMC |
| **OS** | Debian 11 bullseye, kernel `5.15.0-jsbsbxjxh66+` |
| **Also needed** | USB hub ×1, SD card (≥16 GB, 32 GB recommended), SD reader |
| **Difficulty** | ⭐⭐⭐⭐ Needs Linux CLI skills and fastboot |

---

## ✨ What It Solves

| Problem | After |
|---|---|
| 3.6 GB eMMC fills up instantly | Rootfs on SD — 16/32 GB to play with |
| Bricking means reflashing the whole firmware | Flash a new card, plug it in, done. eMMC untouched |
| eMMC wears out from constant writes | Only the boot partition is ever read, **no more writes** |
| Tinkering is risky | Every step has a rollback path, plus a full unbrick guide |

**Measured result:**

```
root       /dev/sda1   16G ext4  sdroot      ← system on SD card
/mnt/data  /dev/sda2   12G ext4  sddata
swap       /dev/sda3   1.7G      sdswap
eMMC       mmcblk0p14  not mounted            ← never written
USB role   host
Network    lan + wan-wifi both activated
Write      30.4 MB/s
```

---

## 📦 Two Approaches

| Path | For | Time |
|---|---|---|
| **A. Use a prebuilt boot image** | Fastest way to get running | ~10 min |
| **B. Patch your own boot.img** | Want to understand it / different kernel / customization | ~30 min |

Both end up identical. The only difference is where the boot image comes from.

---

## 🚀 Quick Start

### Checklist

- [ ] Stick boots and SSH works (default `user` / password `1`)
- [ ] USB hub plugged into the stick, SD card in the hub
- [ ] fastboot available on your PC (for unbricking)
- [ ] Backed up the stock boot partition: `dd if=/dev/mmcblk0p12 of=boot_orig.img bs=1M count=64`

### Path A: prebuilt boot image

```bash
# 1. Push the boot image to the stick (from your PC)
scp boot_sdcard_v2.img user@192.168.9.101:/home/user/

# 2. On the stick: verify stock boot, back it up, flash
sudo -i
dd if=/dev/mmcblk0p12 of=/root/boot_backup.img bs=1M count=64
dd if=/home/user/boot_sdcard_v2.img of=/dev/mmcblk0p12 bs=1M
sync
cmp /home/user/boot_sdcard_v2.img /dev/mmcblk0p12   # must report identical
reboot
```

⚠️ The binary (67 MB) is not in this repo — see [Large Files](#large-files).

### Path B: patch your own boot.img

```bash
# 1. Extract the stock boot image from the stick
dd if=/dev/mmcblk0p12 of=/tmp/boot_orig.img bs=1M count=64

# 2. Patch the DTB (needs dtc)
dtc -I dtb -O dts -o /tmp/orig.dts /tmp/boot_orig.dtb
sed -i 's/dr_mode = "otg"/dr_mode = "host"/' /tmp/orig.dts
dtc -I dts -O dtb -o /tmp/boot_new.dtb /tmp/orig.dts

# 3. Repack on your PC (use the repo script — it syncs kernel_size!)
python3 scripts/bootimg/build_bootimg2.py
```

**Why not plain mkbootimg?** Because of the trap described below.

---

## 🔍 Why It Bricks, and How It Was Fixed

This is the most valuable part of the project. The first attempt left the device completely dead. Three traps were found.

### Trap 1️⃣: `kernel_size` includes the appended DTB (fatal)

The header of this boot.img is **version 0**:

| Field | Value |
|---|---|
| `kernel_size` | **9500581** |
| kernel offset | 0x800 |
| kernel + appended DTB end | 0x90ffa5 |
| ramdisk offset | 0x910000 |

**Key point: `kernel_size` includes the appended DTB** (DTB magic sits at 0x903f5c, inside the kernel_size range).

Changing `dr_mode` from `"otg"` to `"host"` adds one character; after dtc's 4-byte alignment the DTB grows from **49225 → 49229 bytes (+4)**.

The packer only replaced the DTB in place and forgot to update `kernel_size`:

```
header says kernel is 9500581 bytes, but 9500585 are needed
  → LK (aboot) loads only 9500581 bytes
  → last 4 bytes of the appended DTB are truncated
  → DTB totalsize says 49229, only 49225 bytes of data exist
  → device tree validation fails → kernel never runs
```

**Symptom:** completely dead, not even kernel logs. Looks like a hard brick.

**Fix:** `kernel_size = 9451356 (kernel only) + 49229 = 9500585`.
Page-aligned ramdisk offset stays 0x910000, so nothing has to move.

> 💡 `scripts/bootimg/build_bootimg2.py` computes this automatically and verifies on read-back.
> Use `scripts/bootimg/parse_hdr2.py` to inspect any boot.img header.

### Trap 2️⃣: USB enumeration takes time (rootdelay)

Measured boot timeline:

```
[  2.864s] usb 1-1    hub detected
[  3.812s] usb 1-1.2  SD card reader
[  5.097s] sda attached (SCSI)
[ 23.753s] sda1 mounted as root    ← rootdelay=20 kicked in
```

The sd device is ready at **5.1 s**, but initramfs waits only if you tell it to.
Common guides suggest `rootdelay=3`, way too tight for USB storage. This project uses **`rootdelay=20`** with `rootwait` as a backstop.

Drop it to 10 to save ~15 s of boot time — still 2× margin.

### Trap 3️⃣: leave the `extcon` property alone

The DT node `usb@78d9000` carries `extcon = <0x87 0x87>`, pointing at the `usb-id` node (ID-pin GPIO 500).

Per the chipidea driver, when `dr_mode = "host"` the initial role is already `CI_ROLE_HOST`;
the extcon notifier only decides the role in OTG mode. **So extcon does not need to be removed.**

Removing it is actively worse: unbinding extcon-usb-gpio at runtime made ci_hdrc probe fail
with `-EPROBE_DEFER` because it could no longer find its extcon — USB stopped working entirely.

Verified: after boot, `cat /sys/kernel/debug/usb/ci_hdrc.0/role` returns `host` ✓

### Ruled out (so you don't have to)

All of these are **builtin**, so the "initramfs is missing USB modules" theory is wrong:

```
CONFIG_USB_CHIPIDEA=y       CONFIG_USB_CHIPIDEA_HOST=y
CONFIG_USB_CHIPIDEA_MSM=y   CONFIG_PHY_QCOM_USB_HS=y
CONFIG_USB_STORAGE=y        CONFIG_BLK_DEV_SD=y
CONFIG_MMC_BLOCK=y
```

---

## 📖 Full Walkthrough

<details>
<summary><b>Step 0: Preparation</b></summary>

```bash
ssh user@192.168.9.101
cat /proc/cmdline
findmnt -no SOURCE /          # should show /dev/mmcblk0p14
lsblk                          # confirm mmcblk0p12 is the 64M boot partition

# Back up the stock boot (important!)
sudo dd if=/dev/mmcblk0p12 of=$HOME/boot_orig.img bs=1M count=64
md5sum $HOME/boot_orig.img
```

Note the MD5 — you will need it when unbricking.
</details>

<details>
<summary><b>Step 1: Force USB host mode</b></summary>

```bash
sudo nano /usr/sbin/mobian-usb-gadget
```

Right after `setup() {`, add:

```sh
echo host > /sys/kernel/debug/usb/ci_hdrc.0/role
```

Verify:

```bash
cat /sys/kernel/debug/usb/ci_hdrc.0/role   # should print host
lsusb                                       # should list the hub and card reader
```

See `config/mobian-usb-gadget.host.patch`.
</details>

<details>
<summary><b>Step 2: Partition the SD card</b></summary>

```bash
sudo sfdisk /dev/sda < config/partition-tables.txt     # plan A: 6G+4G+1G
sudo sfdisk --disk-id /dev/sda                          # must print 0x8306c78f

sudo mkfs.ext4 -F -L sdroot /dev/sda1
sudo mkfs.ext4 -F -L sddata /dev/sda2
sudo mkswap    -L sdswap /dev/sda3
```

⚠️ **The disk signature must be `0x8306c78f`**, otherwise the PARTUUID will not match and the device will not boot.
</details>

<details>
<summary><b>Step 3: Copy the rootfs</b></summary>

```bash
sudo mkdir -p /mnt/sdroot
sudo mount /dev/sda1 /mnt/sdroot

sudo cp -arf /{bin,boot,etc,home,lib,opt,root,sbin,srv,usr,var} /mnt/sdroot/
sudo mkdir -p /mnt/sdroot/{dev,proc,sys,run,tmp,media,mnt,mnt/data}
sudo chmod 1777 /mnt/sdroot/tmp

sudo cp config/fstab.sdcard /mnt/sdroot/etc/fstab
```

All three `cp` flags matter: `-a` preserves permissions and links, `-r` recurses, `-f` overwrites.
</details>

<details>
<summary><b>Step 4: Patch the boot image</b></summary>

Two things change: **the DTB's `dr_mode`** and **the cmdline's `root=`**.

Final cmdline:

```
earlycon root=PARTUUID=8306c78f-01 rootwait rootdelay=20 rootfstype=ext4 \
console=ttyMSM0,115200 no_framebuffer=true rw
```

| Parameter | Why |
|---|---|
| `root=PARTUUID=8306c78f-01` | First SD partition. Swapping cards needs no change as long as the signature matches |
| `rootdelay=20` | Wait for USB enumeration; ready at 5 s, 20 s leaves margin |
| `rootfstype=ext4` | Explicit, so initramfs does not have to guess |
| `rootwait` | Kernel-native, waits for the root device indefinitely |
| `console=ttyMSM0,115200` | Must match the DT serial node; a mismatch hangs the kernel |

Pack with the script (it keeps `kernel_size` in sync):

```bash
python3 scripts/bootimg/build_bootimg2.py
```
</details>

<details>
<summary><b>Step 5: Write the boot partition and reboot</b></summary>

The stick has a single USB port, so with the hub attached you cannot reach fastboot.
**Use dd from inside the running system instead** — simpler than fastboot and verifiable:

```bash
# Pre-check: confirm the current boot partition really is stock (keeps the unbrick path valid)
sudo dd if=/dev/mmcblk0p12 bs=1M count=64 2>/dev/null | md5sum

sudo dd if=boot_v2.img of=/dev/mmcblk0p12 bs=1M
sync

# Verify (must be identical)
sudo cmp boot_v2.img /dev/mmcblk0p12 && echo "OK"
sudo reboot
```

Automation: `scripts/device/flash_v2_dd.py` + `scripts/device/do_flash_reboot.py`
</details>

<details>
<summary><b>Step 6: Verify</b></summary>

```bash
ssh user@192.168.9.101
findmnt -no SOURCE /      # must be /dev/sda1
cat /proc/cmdline         # must contain root=PARTUUID=8306c78f-01
lsblk                     # mmcblk0p14 should have no mountpoint
swapon --show             # sda3 should be listed
```

One-shot health check: `python3 scripts/device/health_sd.py`
</details>

<details>
<summary><b>Step 7: Build a flashable image (optional, recommended)</b></summary>

Produce a `.img` so future card swaps are just a flash away, Raspberry-Pi style:

```bash
# Run on the stick
python3 scripts/bootimg/gen_mbr.py      # generate MBR (with 0x8306c78f signature)
sudo bash scripts/image/make_img.sh     # ~17 min, produces a 271 MB .img.gz
```

Key techniques:

```bash
# mkfs.ext4 -d: bake a directory tree into an ext4 image — no loop mount, no kpartx
truncate -s 6G p1.img
mkfs.ext4 -F -q -L sdroot -d newroot p1.img

# Sparse files + conv=sparse: a 12G image occupies only ~850M
truncate -s 12G sdcard.img
dd if=mbr.bin of=sdcard.img bs=512 count=1 conv=notrunc
dd if=p1.img  of=sdcard.img bs=512 seek=8192 conv=notrunc,sparse
```

Inspect the image without loop-mounting:

```bash
e2fsck -fn 'sdcard.img?offset=4194304'
debugfs -R 'cat /etc/fstab' 'sdcard.img?offset=4194304'
```

See `docs/04-镜像烧录说明.md` (Chinese).
</details>

---

## 📁 Repository Layout

```
uz801-sdcard-boot/
├── README.md                     ← you are here
├── README_EN.md
├── LICENSE                       MIT
│
├── docs/                         (Chinese) full write-up, root-cause analysis, ops manual
│   ├── 01-SD卡启动方案.md
│   ├── 02-USB-Host模式.md
│   ├── 03-LAN-WAN路由配置.md
│   └── 04-镜像烧录说明.md
│
├── scripts/
│   ├── bootimg/
│   │   ├── parse_hdr2.py         Parse boot.img header (v0~v4, DTB overrun check)
│   │   ├── build_bootimg2.py     Repack (syncs kernel_size + read-back verify)
│   │   └── gen_mbr.py            Generate a 512-byte MBR with disk signature
│   ├── device/
│   │   ├── diag_rootcause.py     Diagnose: modules / DT / initramfs / USB
│   │   ├── verify_dtb.py         Upload DTB and decompile with dtc to verify
│   │   ├── flash_v2_dd.py        Upload boot image + pre-write checks
│   │   ├── do_flash_reboot.py    dd write + cmp verify + reboot
│   │   ├── wait_boot.py          Poll for reboot, check root is sda1
│   │   ├── health_sd.py          Post-boot health check
│   │   ├── check_sd.py           Check whether the SD card is detected
│   │   └── finalize.py           Back up partition table + wrap-up checks
│   └── image/
│       ├── make_img.sh           Build a flashable image on the device
│       └── sd-expand.sh          Claim leftover space as sda4 on bigger cards
│
└── config/
    ├── partition-tables.txt      Partition tables (sfdisk format, two plans)
    ├── fstab.sdcard              /etc/fstab for the SD system
    └── mobian-usb-gadget.host.patch   USB host mode patch
```

> Scripts default to IP `192.168.9.101`, user `user`, password `1`.
> Search and replace to match your setup.

---

## 🆘 Unbricking

| Symptom | Cause | Fix |
|---|---|---|
| Totally dead, no kernel output | Badly packed boot.img (truncated DTB) | fastboot flash the stock boot image |
| Stuck in initramfs, no `/dev/sda1` | SD card not seated / USB not in host mode | Check `lsusb` and the role file |
| Boots but root is `mmcblk0p14` | Boot image is still stock | Flash the SD-card boot image |
| `/mnt/data` not mounted | sda2 not formatted | `mkfs.ext4 -L sddata /dev/sda2 && mount -a` |

**Standard recovery:**

```bash
# 1. Unplug the hub, connect the stick to your PC, enter fastboot
# 2. On the PC
fastboot devices
fastboot erase boot
fastboot flash boot boot_orig.img      # stock boot, root points at eMMC
fastboot reboot
```

Stock boot MD5: `85f9c9fceacc4736ed45bcc657190305`

> ⚠️ **Keep the old rootfs on eMMC (mmcblk0p14). Do not format it.**
> It is the only thing that can revive the device if the SD card dies.
> Verified mountable (1.1 GB).

---

## ❓ FAQ

**Q: Why not test with `fastboot boot` first?**
A: Not possible. One USB port — with the hub attached you cannot reach fastboot, and with the hub removed there is no SD card. Mutually exclusive. So we dd from inside the running system instead: verify the current partition matches the stock backup first, then `cmp` byte-for-byte after writing. Equally safe.

**Q: Do I need to repack boot when swapping cards?**
A: No. PARTUUID = MBR disk signature + partition number. The image signature is fixed at `0x8306c78f`, so sda1 on any flashed card is `8306c78f-01`. **But if you partition manually you must write the signature back:**
```bash
sfdisk --disk-id /dev/sda 0x8306c78f
```

**Q: Can boot live on the SD card too?**
A: No. The MSM8916 LK (aboot) only loads the kernel from the eMMC boot partition; there is no SD-boot ROM support. Boot must stay on eMMC — which is fine, it is only 64 MB and read-only.

**Q: Flashed to a 32 GB card — how do I use the remaining 19 GB?**
A: Run `sudo bash /usr/local/bin/sd-expand.sh`; it creates sda4 mounted at `/mnt/data2`.
(MBR has only one slot left and sda2 is blocked by sda3, so sda4 is the safe option.)

**Q: Should I delete the old eMMC rootfs?**
A: **No.** Keep it as a fallback. It is never mounted or written now — it is dead space otherwise.

**Q: How long is boot?**
A: ~40 s, of which 20 s is the fixed `rootdelay` wait. Set `rootdelay=10` to get it down to ~28 s.

---

## Large Files

GitHub caps individual files at 100 MB, so these are not in the repo:

| File | Size | Notes |
|---|---|---|
| `boot_sdcard_v2.img` | 67 MB | Boot image that boots from SD |
| `boot_orig.img` | 67 MB | Stock boot (for unbricking) |
| `uz801-sdcard-*.img.gz` | 271 MB | Flashable system image |

**How to get them:**

1. **Download from Releases** (fastest) — all three are in [v1.0](https://github.com/naiyouj/uz801-sdcard-boot/releases/tag/v1.0):

   | File | MD5 |
   |---|---|
   | `boot_sdcard_v2.img` | `dd9cedffdb866aa6f8f3394e60251ebd` |
   | `boot_orig.img` | `85f9c9fceacc4736ed45bcc657190305` |
   | `uz801-sdcard-20260906.img.gz` | `0de8e837d2d11d0ee66ee3e3b856d175` |

2. **Generate with the scripts** — start from your own `boot.img` and run `scripts/bootimg/build_bootimg2.py`.
   **Required if your firmware batch differs** (kernel other than 5.15) — the Release images only match `5.15.0-jsbsbxjxh66+`
3. **Open an issue** — tell me your kernel version and I will build one

---

## ⚠️ Disclaimer

- This modifies the boot partition; **careless operation can leave the device unbootable**
- **Always back up the stock boot partition** and note its MD5 before starting
- Firmware differs between UZ801 batches — DTB offset, `kernel_size` and cmdline vary.
  **Do not copy the numbers blindly**; run `scripts/bootimg/parse_hdr2.py` on your own image
- The author takes no responsibility for damaged devices. Assess the risk yourself

---

## 🙏 Credits

- Community write-ups on ARM Linux SD boot (root= major:minor syntax, rootdelay, console node matching)
- The OpenStick community
- Linux kernel chipidea / extcon subsystem source

---

## 📄 License

MIT — use freely, no warranty.
