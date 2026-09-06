# -*- coding: utf-8 -*-
"""收尾：备份 SD 卡分区表、检查服务、生成恢复要点"""
import paramiko, os

HOST, USER, PWD = "192.168.9.101", "user", "1"

CMD = r"""
echo "=== 1. SD 卡分区表(sfdisk 可复现格式) ==="
sfdisk -d /dev/sda

echo
echo "=== 2. MBR 磁盘签名 ==="
sfdisk --disk-id /dev/sda

echo
echo "=== 3. SSH 服务状态 ==="
systemctl is-active ssh 2>/dev/null; systemctl is-active sshd 2>/dev/null
systemctl list-unit-files 2>/dev/null | grep -E '^ssh' | head -5

echo
echo "=== 4. 当前 rootfs 大小(便于以后制作恢复包) ==="
du -shx / 2>/dev/null

echo
echo "=== 5. 排除项(打包 rootfs 时应排除) ==="
echo '/proc/* /sys/* /dev/* /run/* /tmp/* /mnt/data/* /lost+found'

echo
echo "=== 6. eMMC rootfs 是否可挂载(fallback 可行性) ==="
mkdir -p /mnt/emmc_root
mount -o ro /dev/mmcblk0p14 /mnt/emmc_root 2>&1 && {
  echo "  eMMC rootfs 可挂载, 大小: $(du -shx /mnt/emmc_root 2>/dev/null | cut -f1)"
  umount /mnt/emmc_root
} || echo "  挂载失败(可能文件系统损坏)"
rmdir /mnt/emmc_root 2>/dev/null

echo
echo "=== 7. 开机挂载点确认 ==="
findmnt -o TARGET,SOURCE,FSTYPE --df 2>/dev/null | grep -E 'sda|mmcblk0p14|^TARGET'
"""

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=15)
stdin, stdout, stderr = cli.exec_command("sudo -S -p '' bash -s", timeout=240)
stdin.write(PWD + "\n")
stdin.write(CMD)
stdin.channel.shutdown_write()
out = stdout.read().decode("utf-8", "replace")
print(out)
e = stderr.read().decode("utf-8", "replace")
if e.strip():
    print("[stderr]", e[:1000])

# 保存分区表到本地
start = out.find("=== 1. SD 卡分区表")
end = out.find("=== 2. MBR")
if start > 0 and end > start:
    body = out[start:end]
    lines = [l for l in body.splitlines() if l.startswith("/dev/") or l.startswith("label") or l.startswith("device")]
    if lines:
        with open("sda_partition_table.txt", "w") as f:
            f.write("# SD 卡分区表备份 - 用于以后恢复/换卡\n")
            f.write("# 恢复命令: sudo sfdisk /dev/sda < sda_partition_table.txt\n")
            f.write("# 注意: 磁盘签名 id=0x8306c78f 必须与 boot.img 的 root=PARTUUID 匹配!\n\n")
            f.write("\n".join(lines) + "\n")
        print("\n[已保存] sda_partition_table.txt")
        print("\n".join(lines))
cli.close()
