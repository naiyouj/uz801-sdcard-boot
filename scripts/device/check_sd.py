# -*- coding: utf-8 -*-
"""确认 SD 卡分区 / PARTUUID / rootfs 完整性"""
import paramiko

HOST, USER, PWD = "192.168.9.101", "user", "1"

CMD = r"""
echo "=== USB 设备树 ==="
lsusb 2>/dev/null || echo '(no lsusb)'
echo
echo "=== role ==="
cat /sys/kernel/debug/usb/ci_hdrc.0/role 2>/dev/null
echo
echo "=== 块设备 ==="
lsblk -o NAME,SIZE,TYPE,FSTYPE,LABEL,PARTUUID,MOUNTPOINT
echo
echo "=== blkid sd ==="
blkid | grep -E '^/dev/sd' || echo '!!! 仍然没有 /dev/sd* !!!'
echo
echo "=== dmesg 新出现的 usb/mass storage ==="
dmesg | tail -30 | grep -i -E 'usb|scsi|sd |mass' || dmesg | tail -15
echo
echo "=== 内核是否识别到 scsi disk ==="
ls -d /sys/block/sd* 2>/dev/null || echo 'no sd block'
"""

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=15)
stdin, stdout, stderr = cli.exec_command("sudo -S -p '' bash -s", timeout=120)
stdin.write(PWD + "\n")
stdin.write(CMD)
stdin.channel.shutdown_write()
print(stdout.read().decode("utf-8", "replace"))
e = stderr.read().decode("utf-8", "replace")
if e.strip():
    print("[stderr]", e[:1000])
cli.close()
