# -*- coding: utf-8 -*-
"""上传新 DTB 到设备，用 dtc 反编译验证 dr_mode 是否已改为 host"""
import paramiko

HOST, USER, PWD = "192.168.9.101", "user", "1"
LOCAL_DTB = "boot_new.dtb"
REMOTE = "/tmp/boot_new.dtb"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=15)
sftp = cli.open_sftp()
sftp.put(LOCAL_DTB, REMOTE)
sftp.close()
print("uploaded", LOCAL_DTB, "->", REMOTE)

cmd = r"""
cd /tmp
dtc -I dtb -O dts -o /tmp/new.dts /tmp/boot_new.dtb 2>/tmp/dtc.err
echo "=== dtc rc=$? ==="
cat /tmp/dtc.err
echo "=== usb@78d9000 节点 ==="
awk '/usb@78d9000/,/^		};/' /tmp/new.dts | head -40
echo "=== grep dr_mode ==="
grep -n 'dr_mode' /tmp/new.dts
echo "=== 总行数 ==="
wc -l /tmp/new.dts
"""

stdin, stdout, stderr = cli.exec_command("sudo -S -p '' bash -s", timeout=120)
stdin.write(PWD + "\n")
stdin.write(cmd)
stdin.channel.shutdown_write()
print(stdout.read().decode("utf-8", "replace"))
e = stderr.read().decode("utf-8", "replace")
if e.strip():
    print("[stderr]", e[:1500])
cli.close()
