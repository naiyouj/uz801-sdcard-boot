# UZ801 / MSM8916 随身 WiFi 棒子 · SD 卡启动方案

> 把系统从 eMMC 搬到 SD 卡。**棒子上只保留 boot 分区，系统全部跑在 SD 卡上** —— 系统玩坏了换张烧好的卡就行，eMMC 再也不用被反复擦写。

[English](README_EN.md) | 简体中文

---

## 🏷 项目类型

| 项目 | 说明 |
|---|---|
| **类型** | 嵌入式 Linux 启动改造 / 系统迁移 / 可烧录镜像制作 / 救砖工具集 |
| **适用硬件** | UZ801 随身 WiFi 棒（OpenStick 方案） |
| **SoC** | Qualcomm MSM8916 / Snapdragon 410，Cortex-A53 ×4 |
| **内存 / 存储** | 461 MB RAM / 3.6 GB eMMC |
| **系统** | Debian 11 bullseye，内核 `5.15.0-jsbsbxjxh66+` |
| **额外需要** | USB hub ×1、SD 卡（≥16G，推荐 32G）、SD 读卡器 |
| **难度** | ⭐⭐⭐⭐ 需要 Linux 命令行基础，会进 fastboot |

---

## ✨ 能解决什么

| 痛点 | 解决后 |
|---|---|
| eMMC 只有 3.6G，装点东西就满 | 系统搬到 SD 卡，16G/32G 随便用 |
| 系统玩坏了要重刷整个固件 | 烧一张新卡插上就好，eMMC 完全不用动 |
| eMMC 反复擦写会坏 | eMMC 只剩 boot 分区被读，**几乎不再写入** |
| 折腾有风险，怕变砖 | 每一步都有回退路径，附完整救砖方案 |

**最终效果实测：**

```
root       /dev/sda1   16G ext4  sdroot      ← 系统在 SD 卡
/mnt/data  /dev/sda2   12G ext4  sddata
swap       /dev/sda3   1.7G      sdswap
eMMC       mmcblk0p14  未挂载                ← 完全不写入
USB role   host
网络        lan + wan-wifi 均 activated
写入速度    30.4 MB/s
```

---

## 📦 两种使用路线

| 路线 | 适合谁 | 工作量 |
|---|---|---|
| **A. 用现成 boot 镜像** | 想最快跑起来 | 10 分钟 |
| **B. 从自己的 boot.img 改造** | 想理解原理 / 内核不是 5.15 / 想自定义 | 30 分钟 |

两条路线最终效果完全一样。区别只是 boot.img 从哪来。

---

## 🚀 快速开始

### 前置清单

- [ ] 棒子能正常启动，SSH 能连（默认 `user` / 密码 `1`）
- [ ] USB hub 插在棒子上，SD 卡插在 hub 上
- [ ] 电脑上有 fastboot（用于救砖）
- [ ] 备份了原版 boot 分区：`dd if=/dev/mmcblk0p12 of=boot_orig.img bs=1M count=64`

### 路线 A：用现成的 boot 镜像

```bash
# 1. 上传 boot 镜像到棒子（在你的电脑上执行）
scp boot_sdcard_v2.img user@192.168.9.101:/home/user/

# 2. 在棒子上：确认当前 boot 是原版 + 建立备份 + 写入
sudo -i
md5sum /dev/mmcblk0p12            # 先确认分区大小是 64M
dd if=/dev/mmcblk0p12 of=/root/boot_backup.img bs=1M count=64
dd if=/home/user/boot_sdcard_v2.img of=/dev/mmcblk0p12 bs=1M
sync
cmp /home/user/boot_sdcard_v2.img /dev/mmcblk0p12   # 必须输出"一致"
reboot
```

⚠️ 镜像文件（67MB）不在这个仓库里，见「[关于大文件](#关于大文件)」。

### 路线 B：从自己的 boot.img 改造

```bash
# 1. 从棒子上取出原版 boot.img
dd if=/dev/mmcblk0p12 of=/tmp/boot_orig.img bs=1M count=64

# 2. 在棒子上改 DTB（需要 dtc）
dtc -I dtb -O dts -o /tmp/orig.dts /tmp/boot_orig.dtb
sed -i 's/dr_mode = "otg"/dr_mode = "host"/' /tmp/orig.dts
dtc -I dts -O dtb -o /tmp/boot_new.dtb /tmp/orig.dts

# 3. 在电脑上重新打包（⚠️ 必须用本仓库的脚本，会自动同步 kernel_size）
python3 scripts/bootimg/build_bootimg2.py
```

**为什么不直接用 mkbootimg？** 因为这里有个致命的坑，见下一节。

---

## 🔍 原理：为什么会变砖，又是怎么修好的

这是本项目最有价值的部分。第一次尝试时设备直接起不来，排查后发现了三个坑。

### 坑 1️⃣：`kernel_size` 字段包含 appended DTB（致命）

这个 boot.img 的 header 是 **v0 版本**，结构如下：

| 字段 | 值 |
|---|---|
| `kernel_size` | **9500581** |
| kernel 起始偏移 | 0x800 |
| kernel + appended DTB 结束 | 0x90ffa5 |
| ramdisk 偏移 | 0x910000 |

**关键点：`kernel_size` 里包含了尾部 appended 的 DTB**（DTB magic 在 0x903f5c，正好落在 kernel_size 范围内）。

改 `dr_mode` 时 `"otg"` → `"host"` 多一个字符，dtc 按 4 字节对齐后 DTB 从 **49225 → 49229 字节（+4）**。

打包时只做了「DTB 原位替换」，忘了同步 `kernel_size`：

```
header 说 kernel 只有 9500581 字节，实际需要 9500585
  → LK(aboot) 只加载 9500581 字节
  → appended DTB 尾部 4 字节被截断
  → DTB 的 totalsize 说 49229，实际数据只有 49225
  → 设备树校验失败 → 内核根本没跑起来
```

**现象**：完全起不来，连内核日志都没有，看起来像"刷砖了"。

**修复**：`kernel_size = 9451356（kernel 纯数据）+ 49229 = 9500585`。
ramdisk 偏移页对齐后仍是 0x910000，不用移动。

> 💡 `scripts/bootimg/build_bootimg2.py` 会自动算这个值，并做回读校验。
> 用 `scripts/bootimg/parse_hdr2.py` 可以随时检查任意 boot.img 的 header。

### 坑 2️⃣：USB 枚举需要时间（rootdelay）

实测启动时序：

```
[  2.864s] usb 1-1    hub 出现
[  3.812s] usb 1-1.2  SD 读卡器
[  5.097s] sda attached (SCSI)
[ 23.753s] sda1 挂载为 root      ← rootdelay=20 生效
```

sd 设备在 **5.1 秒**就就绪了，但 initramfs 需要显式等待才会去挂载。
网友方案常用 `rootdelay=3`，对 USB 存储太紧。本项目用 **`rootdelay=20`**，`rootwait` 兜底。

想要更快可以把 20 降到 10（省约 15 秒启动时间），冷启动还有 2 倍余量。

### 坑 3️⃣：不要动 `extcon` 属性

DT 里 `usb@78d9000` 有 `extcon = <0x87 0x87>`，指向 `usb-id` 节点（ID 脚 GPIO 500）。

按 chipidea 驱动逻辑，`dr_mode = "host"` 时初始 role 就是 `CI_ROLE_HOST`，
extcon notifier 只在 OTG 模式下才决定 role。**所以不需要删 extcon。**

而且删了更糟：之前在运行时 unbind 过 extcon-usb-gpio，导致 ci_hdrc probe 找不到
extcon 直接 `-EPROBE_DEFER`，USB 完全不工作。

实测验证：启动后 `cat /sys/kernel/debug/usb/ci_hdrc.0/role` 返回 `host` ✓

### 已排除的猜测（省得你再查一遍）

内核配置里这些**全是 builtin**，「initramfs 缺 USB 模块」的猜测不成立：

```
CONFIG_USB_CHIPIDEA=y       CONFIG_USB_CHIPIDEA_HOST=y
CONFIG_USB_CHIPIDEA_MSM=y   CONFIG_PHY_QCOM_USB_HS=y
CONFIG_USB_STORAGE=y        CONFIG_BLK_DEV_SD=y
CONFIG_MMC_BLOCK=y
```

---

## 📖 完整步骤

<details>
<summary><b>第 0 步：前置准备</b>（点击展开）</summary>

```bash
# 确认当前系统状态
ssh user@192.168.9.101
cat /proc/cmdline
findmnt -no SOURCE /          # 应该显示 /dev/mmcblk0p14
lsblk                          # 确认 mmcblk0p12 是 64M 的 boot 分区

# 备份原版 boot（重要！）
sudo dd if=/dev/mmcblk0p12 of=$HOME/boot_orig.img bs=1M count=64
md5sum $HOME/boot_orig.img
```

记住这个 MD5，救砖时会用到。
</details>

<details>
<summary><b>第 1 步：让 USB 口进入 host 模式</b></summary>

```bash
sudo nano /usr/sbin/mobian-usb-gadget
```

在 `setup() {` 的下一行加：

```sh
echo host > /sys/kernel/debug/usb/ci_hdrc.0/role
```

验证：

```bash
cat /sys/kernel/debug/usb/ci_hdrc.0/role   # 应该输出 host
lsusb                                       # 应该能看到 hub 和读卡器
```

详见 `config/mobian-usb-gadget.host.patch`。
</details>

<details>
<summary><b>第 2 步：给 SD 卡分区</b></summary>

```bash
sudo sfdisk /dev/sda < config/partition-tables.txt     # 方案 A: 6G+4G+1G
sudo sfdisk --disk-id /dev/sda                          # 必须输出 0x8306c78f

sudo mkfs.ext4 -F -L sdroot /dev/sda1
sudo mkfs.ext4 -F -L sddata /dev/sda2
sudo mkswap    -L sdswap /dev/sda3
```

⚠️ **磁盘签名必须是 `0x8306c78f`**，否则 PARTUUID 对不上，起不来。
</details>

<details>
<summary><b>第 3 步：复制 rootfs 到 SD 卡</b></summary>

```bash
sudo mkdir -p /mnt/sdroot
sudo mount /dev/sda1 /mnt/sdroot

sudo cp -arf /{bin,boot,etc,home,lib,opt,root,sbin,srv,usr,var} /mnt/sdroot/
sudo mkdir -p /mnt/sdroot/{dev,proc,sys,run,tmp,media,mnt,mnt/data}
sudo chmod 1777 /mnt/sdroot/tmp

# 写入 SD 卡专属 fstab
sudo cp config/fstab.sdcard /mnt/sdroot/etc/fstab
```

`cp -arf` 的三个参数都不能少：`-a` 保权限和链接，`-r` 递归，`-f` 强制覆盖。
</details>

<details>
<summary><b>第 4 步：改造 boot.img</b></summary>

改两处：**DTB 的 `dr_mode`** 和 **cmdline 的 `root=`**。

最终 cmdline：

```
earlycon root=PARTUUID=8306c78f-01 rootwait rootdelay=20 rootfstype=ext4 \
console=ttyMSM0,115200 no_framebuffer=true rw
```

| 参数 | 为什么 |
|---|---|
| `root=PARTUUID=8306c78f-01` | SD 卡第一分区。换卡只要签名一致就不用改 |
| `rootdelay=20` | 等 USB 枚举，实测 5s 就绪，20s 留足余量 |
| `rootfstype=ext4` | 显式指定，避免 initramfs 猜错 |
| `rootwait` | 内核原生，无限等 root 出现 |
| `console=ttyMSM0,115200` | 必须和设备树串口节点一致，不匹配会卡在 kernel |

用脚本打包（会同步 `kernel_size`）：

```bash
python3 scripts/bootimg/build_bootimg2.py
```
</details>

<details>
<summary><b>第 5 步：写入 boot 分区并启动</b></summary>

因为棒子只有一个 USB 口，插着 hub 就没法连电脑进 fastboot，
所以**直接在系统里用 dd 写**，比 fastboot 更省事而且可校验：

```bash
# 预检：确认当前 boot 分区确实是原版（保证救砖链路有效）
sudo dd if=/dev/mmcblk0p12 bs=1M count=64 2>/dev/null | md5sum

# 写入
sudo dd if=boot_v2.img of=/dev/mmcblk0p12 bs=1M
sync

# 校验（必须完全一致）
sudo cmp boot_v2.img /dev/mmcblk0p12 && echo "OK"
sudo reboot
```

自动化脚本：`scripts/device/flash_v2_dd.py` + `scripts/device/do_flash_reboot.py`
</details>

<details>
<summary><b>第 6 步：验证</b></summary>

```bash
ssh user@192.168.9.101
findmnt -no SOURCE /      # 必须是 /dev/sda1
cat /proc/cmdline         # 必须含 root=PARTUUID=8306c78f-01
lsblk                     # mmcblk0p14 应该没有挂载点
swapon --show             # sda3 应该在列表里
```

一键体检：`python3 scripts/device/health_sd.py`
</details>

<details>
<summary><b>第 7 步：制作可烧录镜像（可选，推荐）</b></summary>

做成一个 `.img`，以后换卡直接烧，像树莓派一样：

```bash
# 在棒子上执行
python3 scripts/bootimg/gen_mbr.py      # 生成 MBR（含 0x8306c78f 签名）
sudo bash scripts/image/make_img.sh     # 约 17 分钟，产出 271MB 的 .img.gz
```

关键技巧：

```bash
# mkfs.ext4 的 -d 参数：不用 loop 挂载、不用 kpartx，直接把目录树烤成 ext4
truncate -s 6G p1.img
mkfs.ext4 -F -q -L sdroot -d newroot p1.img

# 稀疏文件 + conv=sparse，12G 镜像实际只占 ~850M
truncate -s 12G sdcard.img
dd if=mbr.bin of=sdcard.img bs=512 count=1 conv=notrunc
dd if=p1.img  of=sdcard.img bs=512 seek=8192 conv=notrunc,sparse
```

验证镜像内容（不用 loop 挂载）：

```bash
e2fsck -fn 'sdcard.img?offset=4194304'
debugfs -R 'cat /etc/fstab' 'sdcard.img?offset=4194304'
```

详见 `docs/04-镜像烧录说明.md`。
</details>

---

## 📁 文件说明

```
uz801-sdcard-boot/
├── README.md                     ← 你在这里
├── README_EN.md                  English version
├── LICENSE                       MIT
│
├── docs/
│   ├── 01-SD卡启动方案.md         完整方案 + 根因分析 + 运维手册
│   ├── 02-USB-Host模式.md         USB host 模式改造
│   ├── 03-LAN-WAN路由配置.md       网口做 LAN / WiFi 做 WAN
│   └── 04-镜像烧录说明.md          镜像烧录与换卡指南
│
├── scripts/
│   ├── bootimg/
│   │   ├── parse_hdr2.py         解析 boot.img header（v0~v4，含 DTB 越界检查）
│   │   ├── build_bootimg2.py     重新打包（自动同步 kernel_size + 回读校验）
│   │   └── gen_mbr.py            生成 MBR（512 字节，含磁盘签名）
│   ├── device/
│   │   ├── diag_rootcause.py     诊断：内核模块 / DT / initramfs / USB
│   │   ├── verify_dtb.py         上传 DTB 用 dtc 反编译验证
│   │   ├── flash_v2_dd.py        上传 boot 镜像 + 写入前预检
│   │   ├── do_flash_reboot.py    dd 写入 + cmp 校验 + 重启
│   │   ├── wait_boot.py          轮询等待重启，判断 root 是不是 sda1
│   │   ├── health_sd.py          启动后健康检查
│   │   ├── check_sd.py           检查 SD 卡是否被识别
│   │   └── finalize.py           备份分区表 + 收尾检查
│   └── image/
│       ├── make_img.sh           在设备上制作可烧录镜像
│       └── sd-expand.sh          烧到大卡后，把剩余空间建成 sda4
│
└── config/
    ├── partition-tables.txt      分区表（sfdisk 格式，两种方案）
    ├── fstab.sdcard              SD 卡系统的 /etc/fstab
    └── mobian-usb-gadget.host.patch   USB host 模式补丁
```

> 所有脚本里设备 IP 默认是 `192.168.9.101`，用户 `user`，密码 `1`。
> 改成你自己的：搜索替换即可。

---

## 🆘 救砖

| 症状 | 原因 | 解决 |
|---|---|---|
| 完全起不来，连内核日志都没有 | boot.img 打包错误（DTB 截断） | 进 fastboot 刷回原版 boot.img |
| 卡在 initramfs，`/dev/sda1` 不存在 | SD 卡没插好 / USB 没进 host | 检查 `lsusb` 和 role |
| 能起来但 root 是 `mmcblk0p14` | boot 还是原版 | 刷 SD 卡版 boot 镜像 |
| `/mnt/data` 没挂载 | sda2 没格式化 | `mkfs.ext4 -L sddata /dev/sda2 && mount -a` |

**标准救砖流程：**

```bash
# 1. 拔掉 hub，用 USB 线连电脑，进 fastboot 模式
# 2. 电脑上执行
fastboot devices
fastboot erase boot
fastboot flash boot boot_orig.img      # 原版 boot，root 指向 eMMC
fastboot reboot
```

原版 boot 的 MD5：`85f9c9fceacc4736ed45bcc657190305`

> ⚠️ **eMMC 上的 rootfs（mmcblk0p14）务必保留，不要格式化。**
> 这是唯一能在 SD 卡挂掉时让设备起死回生的东西。已验证可正常挂载（1.1G）。

---

## ❓ FAQ

**Q: 为什么不用 `fastboot boot` 先测试？**
A: 试不了。棒子只有一个 USB 口，插着 hub 就没法连电脑进 fastboot，而拔了 hub 就没有 SD 卡了 —— 两者互斥。所以改成在系统里 dd 写入，写入前确认当前分区 == 原版备份，写完 cmp 逐字节比对，一样安全。

**Q: 换卡需要重新打包 boot 吗？**
A: 不需要。PARTUUID = MBR 磁盘签名 + 分区号，镜像签名固定 `0x8306c78f`，任何卡烧出来 sda1 都是 `8306c78f-01`。**但自己分区时必须手动写回签名**：
```bash
sfdisk --disk-id /dev/sda 0x8306c78f
```

**Q: 可以把 boot 也放进 SD 卡吗？**
A: 不行。MSM8916 的 LK(aboot) 只从 eMMC 的 boot 分区加载内核，没有 SD 卡启动的 boot ROM 支持。所以 boot 必须留在 eMMC（好在它只有 64M，且只读）。

**Q: 镜像烧到 32G 卡，剩下的 19G 怎么用？**
A: 跑 `sudo bash /usr/local/bin/sd-expand.sh`，会建 sda4 挂到 `/mnt/data2`。
（MBR 只剩一个分区槽位，且 sda2 被 sda3 挡住不能直扩，建 sda4 最安全。）

**Q: eMMC 里的旧 rootfs 要删掉吗？**
A: **不要删。** 留着当 fallback。它现在完全不挂载、不写入，占的是死空间。

**Q: 启动要多久？**
A: 约 40 秒（其中 20 秒是 `rootdelay` 的固定等待）。改 `rootdelay=10` 能缩到约 28 秒。

---

## 关于大文件

GitHub 单文件限制 100MB，这些文件放不进仓库：

| 文件 | 大小 | 说明 |
|---|---|---|
| `boot_sdcard_v2.img` | 67 MB | SD 卡启动的 boot 镜像 |
| `boot_orig.img` | 67 MB | 原版 boot（救砖用）|
| `uz801-sdcard-*.img.gz` | 271 MB | 可烧录系统镜像 |

**获取方式：**

1. **从 Release 下载**（最快）—— [v1.0 Release](https://github.com/naiyouj/uz801-sdcard-boot/releases/tag/v1.0) 里三个文件都有：

   | 文件 | MD5 |
   |---|---|
   | `boot_sdcard_v2.img` | `dd9cedffdb866aa6f8f3394e60251ebd` |
   | `boot_orig.img` | `85f9c9fceacc4736ed45bcc657190305` |
   | `uz801-sdcard-20260906.img.gz` | `0de8e837d2d11d0ee66ee3e3b856d175` |

2. **用脚本生成** —— 从你自己的 `boot.img` 出发，跑 `scripts/bootimg/build_bootimg2.py`。
   **固件批次不同（内核不是 5.15）时必须走这条**，Release 里的镜像只适配 `5.15.0-jsbsbxjxh66+`
3. **开个 Issue** —— 说明你的内核版本，我帮你生成

---

## ⚠️ 免责声明

- 本方案涉及修改 boot 分区，**操作不当可能让设备无法启动**
- 动手前**务必备份原版 boot 分区**并记住 MD5
- 不同批次的 UZ801 固件可能不同，DTB 偏移、`kernel_size`、cmdline 都不一样，
  **不要直接照抄数字**，用 `scripts/bootimg/parse_hdr2.py` 解析你自己的镜像
- 作者不对任何设备损坏负责，请自行评估风险

---

## 🙏 参考

- 网友提供的 ARM Linux SD 卡启动资料（root= 主次设备号写法、rootdelay、console 节点匹配）
- OpenStick 社区
- Linux kernel chipidea / extcon 子系统源码

---

## 📄 License

MIT — 随便用，出问题不负责。
