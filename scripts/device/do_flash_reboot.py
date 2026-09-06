# -*- coding: utf-8 -*-
"""dd 写入 boot_v2.img 到 mmcblk0p12，校验后重启"""
import paramiko, time

HOST, USER, PWD = "192.168.9.101", "user", "1"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=20)
print("connected")

CMD = r"""
echo "=== 卸载 SD 卡(让文件系统干净) ==="
umount /mnt/sdroot 2>/dev/null; umount /dev/sda2 2>/dev/null; swapoff /dev/sda3 2>/dev/null
mountpoint /mnt/sdroot || echo '  SD 已卸载'

echo
echo "=== dd 写入 ==="
dd if=/root/boot_v2.img of=/dev/mmcblk0p12 bs=1M 2>&1 | tail -3
sync

echo
echo "=== 写入后校验 ==="
dd if=/dev/mmcblk0p12 bs=1M count=64 2>/dev/null | md5sum
echo "期望: dd9cedffdb866aa6f8f3394e60251ebd"

echo
echo "=== 逐字节比对(cmp) ==="
cmp /root/boot_v2.img /dev/mmcblk0p12 && echo '  cmp: 完全一致 OK'

echo
echo "=== 重启 ==="
sync
"""

stdin, stdout, stderr = cli.exec_command("sudo -S -p '' bash -s", timeout=600)
stdin.write(PWD + "\n")
stdin.write(CMD)
stdin.channel.shutdown_write()
out = stdout.read().decode("utf-8", "replace")
print(out)
e = stderr.read().decode("utf-8", "replace")
if e.strip():
    print("[stderr]", e[:1200])

if "dd9cedffdb866aa6f8f3394e60251ebd" in out and "完全一致" in out:
    print("\n[写入校验通过] 准备重启...")
else:
    print("\n!!! 写入校验失败，不重启 !!!")
    cli.close()
    raise SystemExit(1)

# 单独发 reboot（避免被上面的输出混淆）
try:
    stdin, stdout, stderr = cli.exec_command("sudo -S -p '' reboot", timeout=10)
    stdin.write(PWD + "\n")
    stdin.channel.shutdown_write()
    time.sleep(2)
except Exception as ex:
    print("reboot 指令已下发:", ex)

print("REBOOT 已下发，等待 100 秒后重连...")
cli.close()
