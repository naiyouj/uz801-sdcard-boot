# -*- coding: utf-8 -*-
"""SD 卡启动后的健康检查"""
import paramiko

HOST, USER, PWD = "192.168.9.101", "user", "1"

CMD = r"""
echo "=== 1. 根文件系统 ==="
findmnt -no SOURCE,FSTYPE /
df -h | grep -E 'Filesystem|sda|mmcblk0p14'

echo
echo "=== 2. eMMC 使用情况(应只有 boot 分区被读, rootfs 未挂载) ==="
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT /dev/mmcblk0 | grep -E 'mmcblk0p12|mmcblk0p14|^NAME'
echo "  mmcblk0p14 挂载点: $(findmnt -no MOUNTPOINT /dev/mmcblk0p14 2>/dev/null || echo '(未挂载 - 正确)')"

echo
echo "=== 3. swap ==="
swapon --show

echo
echo "=== 4. 写入测试(应落在 SD 卡, 不碰 eMMC) ==="
dd if=/dev/zero of=/root/testfile bs=1M count=100 2>&1 | tail -1
sync
rm -f /root/testfile
echo "  已清理 testfile"

echo
echo "=== 5. USB 状态 ==="
cat /sys/kernel/debug/usb/ci_hdrc.0/role
lsusb

echo
echo "=== 6. 网络 ==="
nmcli -t -f NAME,DEVICE,STATE c show --active
echo "  --- 外网连通性 ---"
ping -c 2 -W 3 223.5.5.5 2>&1 | tail -2

echo
echo "=== 7. 启动阶段 USB 枚举时间 ==="
dmesg | grep -E 'new high-speed|Attached SCSI|EXT4-fs \(sda1\)' | head -8

echo
echo "=== 8. 关键服务 ==="
systemctl is-active systemd-journald NetworkManager sshd 2>/dev/null

echo
echo "=== 9. 系统日志错误(近50行中的 error/fail) ==="
journalctl -b -p err --no-pager -n 15 2>/dev/null || dmesg | grep -i -E 'error|fail' | tail -10

echo
echo "=== 10. 负载/内存 ==="
uptime; free -h
"""

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=15)
stdin, stdout, stderr = cli.exec_command("sudo -S -p '' bash -s", timeout=240)
stdin.write(PWD + "\n")
stdin.write(CMD)
stdin.channel.shutdown_write()
print(stdout.read().decode("utf-8", "replace"))
e = stderr.read().decode("utf-8", "replace")
if e.strip():
    print("[stderr]", e[:1200])
cli.close()
