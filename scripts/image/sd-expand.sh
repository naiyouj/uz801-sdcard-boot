#!/bin/bash
# 把 SD 卡剩余空间建成第 4 个分区，挂载到 /mnt/data2
# 场景: 把 11G 的镜像烧到 32G/64G 卡后，卡尾剩下一大块未使用空间
# 用法: sudo bash /usr/local/bin/sd-expand.sh
set -e

DEV=/dev/sda

if [ "$(id -u)" != "0" ]; then
    echo "需要 root: sudo bash $0"
    exit 1
fi

if [ -e "${DEV}4" ]; then
    echo "sda4 已存在，无需再建。"
    df -h | grep sda4 || true
    exit 1
fi

echo "=== 当前分区表 ==="
sfdisk -d $DEV
echo
echo "卡总容量: $(( $(sfdisk -s $DEV) / 1024 )) MB"
echo
read -p "在剩余空间创建 sda4 并挂载到 /mnt/data2 ? [y/N] " ans
case "$ans" in
    y|Y) ;;
    *) echo "已取消"; exit 0;;
esac

echo
echo "=== 创建分区 ==="
printf ',\n' | sfdisk --append $DEV
partprobe $DEV 2>/dev/null || true
sleep 3

if [ ! -e "${DEV}4" ]; then
    echo "分区创建失败"
    exit 1
fi

echo "=== 格式化 ext4 (label sddata2) ==="
mkfs.ext4 -F -q -L sddata2 ${DEV}4

echo "=== 挂载到 /mnt/data2 ==="
mkdir -p /mnt/data2
PU=$(blkid -o value -s PARTUUID ${DEV}4)
if ! grep -q '/mnt/data2' /etc/fstab; then
    echo "PARTUUID=$PU  /mnt/data2  ext4  defaults,nofail,noatime  0  2" >> /etc/fstab
fi
mount -a

echo
echo "=== 完成 ==="
df -h /mnt/data2
echo
echo "提示: 想让 sda4 当主数据盘，可手动改 /etc/fstab 把 /mnt/data 指向它。"
