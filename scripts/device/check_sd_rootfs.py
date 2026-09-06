# -*- coding: utf-8 -*-
"""挂载 SD 卡并检查 rootfs 完整性"""
import paramiko

HOST, USER, PWD = "192.168.9.101", "user", "1"

CMD = r"""
set -e
mkdir -p /mnt/sdroot
if mountpoint -q /mnt/sdroot; then echo '(已挂载)'; else mount /dev/sda1 /mnt/sdroot; fi
echo "=== 挂载状态 ==="
findmnt -no SOURCE,FSTYPE,SIZE,USED /mnt/sdroot
echo
echo "=== 顶层目录 ==="
ls -la /mnt/sdroot
echo
echo "=== 关键文件存在性 ==="
for f in sbin/init bin/bash bin/sh etc/fstab etc/passwd etc/hostname etc/network/interfaces lib/systemd/systemd usr/bin/sudo bin/busybox; do
  if [ -e "/mnt/sdroot/$f" ]; then echo "  OK      $f"; else echo "  MISSING $f"; fi
done
echo
echo "=== 空目录(必须有) ==="
for d in dev proc sys run tmp media mnt; do
  if [ -d "/mnt/sdroot/$d" ]; then echo "  OK      $d"; else echo "  MISSING $d"; fi
done
echo
echo "=== SD 卡 /etc/fstab ==="
cat /mnt/sdroot/etc/fstab
echo
echo "=== 占用空间 ==="
du -sh /mnt/sdroot 2>/dev/null
df -h /mnt/sdroot
echo
echo "=== /etc/hostname ==="
cat /mnt/sdroot/etc/hostname 2>/dev/null
echo
echo "=== 是否有残留的 eMMC 专属配置(需留意) ==="
grep -rn 'mmcblk0p14' /mnt/sdroot/etc/ 2>/dev/null | head -5 || echo '  (无)'
echo "=== NetworkManager 连接配置数量 ==="
ls /mnt/sdroot/etc/NetworkManager/system-connections/ 2>/dev/null | head -10 || echo '  (无)'
echo
echo "=== 是否含 mobian-usb-gadget host 补丁 ==="
grep -n 'ci_hdrc' /mnt/sdroot/usr/sbin/mobian-usb-gadget 2>/dev/null || echo '  (无/文件不存在)'
"""

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=20)
stdin, stdout, stderr = cli.exec_command("sudo -S -p '' bash -s", timeout=180)
stdin.write(PWD + "\n")
stdin.write(CMD)
stdin.channel.shutdown_write()
print(stdout.read().decode("utf-8", "replace"))
e = stderr.read().decode("utf-8", "replace")
if e.strip():
    print("[stderr]", e[:1200])
cli.close()
