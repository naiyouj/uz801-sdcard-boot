#!/bin/bash
# 在设备上制作可烧录的 SD 卡镜像
# 布局: sda1 6G rootfs + sda2 4G data + sda3 1G swap, label-id 0x8306c78f
set -o pipefail

W=/mnt/data/work
LOG=$W/make.log
mkdir -p $W

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a $LOG; }

log "===== 开始 ====="
log "磁盘: $(df -h /mnt/data | tail -1)"

cd $W || exit 1

# ---------- 1. 备份 rootfs ----------
log "1/7 tar 备份 rootfs ..."
tar -czpf $W/rootfs.tar.gz \
  --exclude=./proc/* --exclude=./sys/* --exclude=./dev/* \
  --exclude=./run/* --exclude=./tmp/* \
  --exclude=./mnt/data/* --exclude=./lost+found/* \
  --exclude=./root/boot_v2.img --exclude=./root/boot_bak_before_v2.img \
  --exclude=./root/boot_orig_backup.img --exclude=./root/*.img \
  --exclude=./swapfile \
  --one-file-system -C / . 2>&1 | tail -3
log "tar 完成: $(ls -lh $W/rootfs.tar.gz | awk '{print $5}')"

# ---------- 2. 解压 ----------
log "2/7 解压到 newroot ..."
rm -rf $W/newroot
mkdir -p $W/newroot
tar -xzpf $W/rootfs.tar.gz -C $W/newroot 2>&1 | tail -3
log "解压完成"

# ---------- 3. 清理运行时内容 ----------
log "3/7 清理 ..."
rm -rf $W/newroot/var/log/journal/* 2>/dev/null
rm -f  $W/newroot/var/log/*.log 2>/dev/null
rm -f  $W/newroot/var/cache/apt/archives/*.deb 2>/dev/null
rm -f  $W/newroot/var/lib/apt/lists/* 2>/dev/null
rm -rf $W/newroot/tmp/* $W/newroot/run/* 2>/dev/null
rm -rf $W/newroot/root/.cache/* 2>/dev/null
rm -f  $W/newroot/swapfile 2>/dev/null
rm -f  $W/newroot/root/*.img 2>/dev/null
: > $W/newroot/etc/machine-id
for d in proc sys dev run tmp media mnt mnt/data; do mkdir -p $W/newroot/$d; done
chmod 1777 $W/newroot/tmp
log "newroot 大小: $(du -sh $W/newroot | cut -f1)"

# ---------- 4. 分区镜像 ----------
log "4/7 mkfs p1 (6G rootfs) ..."
truncate -s 6G $W/p1.img
mkfs.ext4 -F -q -L sdroot -d $W/newroot $W/p1.img 2>&1 | tail -3
e2fsck -fy $W/p1.img 2>&1 | tail -3
log "p1 完成, 实际占用 $(du -sh --apparent-size $W/p1.img | cut -f1) / 磁盘占用 $(du -sh $W/p1.img | cut -f1)"

log "4/7 mkfs p2 (4G data) ..."
truncate -s 4G $W/p2.img
mkfs.ext4 -F -q -L sddata $W/p2.img 2>&1 | tail -2

log "4/7 mkswap p3 (1G) ..."
truncate -s 1G $W/p3.img
mkswap -L sdswap $W/p3.img 2>&1 | tail -2

# ---------- 5. 组装 ----------
log "5/7 组装 sdcard.img (12G 稀疏) ..."
rm -f $W/sdcard.img
truncate -s 12G $W/sdcard.img

# 先写 MBR(由本地生成, 含 label-id 0x8306c78f)
dd if=$W/mbr.bin of=$W/sdcard.img bs=512 count=1 conv=notrunc 2>&1 | tail -1

log "  dd p1 -> seek 8192"
dd if=$W/p1.img of=$W/sdcard.img bs=512 seek=8192 conv=notrunc,sparse 2>&1 | tail -1
log "  dd p2 -> seek 12591104"
dd if=$W/p2.img of=$W/sdcard.img bs=512 seek=12591104 conv=notrunc,sparse 2>&1 | tail -1
log "  dd p3 -> seek 20979712"
dd if=$W/p3.img of=$W/sdcard.img bs=512 seek=20979712 conv=notrunc,sparse 2>&1 | tail -1

sync
log "分区表:"
sfdisk -d $W/sdcard.img 2>&1 | tee -a $LOG
fdisk -l $W/sdcard.img 2>&1 | tee -a $LOG

# ---------- 6. 清理中间文件 ----------
log "6/7 清理中间文件 ..."
rm -rf $W/newroot $W/p1.img $W/p2.img $W/p3.img $W/rootfs.tar.gz
df -h /mnt/data | tail -1 | tee -a $LOG

# ---------- 7. 压缩 ----------
log "7/7 gzip (这一步最慢, 约 10-15 分钟) ..."
gzip -1 -c $W/sdcard.img > $W/sdcard.img.gz
sync
log "完成!"
ls -lh $W/ | tee -a $LOG
md5sum $W/sdcard.img.gz | tee -a $LOG
echo "MAKE_IMG_DONE" | tee -a $LOG
