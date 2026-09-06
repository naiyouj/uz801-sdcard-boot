# -*- coding: utf-8 -*-
"""
1) 上传 boot_v2.img 到设备
2) 校验当前 boot 分区 == 原版备份(确认备份有效)
3) dd 写入 mmcblk0p12
4) 比对写入结果
5) 重启
"""
import paramiko, hashlib, sys

HOST, USER, PWD = "192.168.9.101", "user", "1"
LOCAL = "boot_v2.img"
REMOTE = "/root/boot_v2.img"
LOCAL_MD5 = hashlib.md5(open(LOCAL, "rb").read()).hexdigest()

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=20)
print("connected")

# ---- 上传 ----
sftp = cli.open_sftp()
sftp.put(LOCAL, "/home/user/boot_v2.img")
sftp.close()
print("uploaded -> /home/user/boot_v2.img (local md5 %s)" % LOCAL_MD5)

CMD = r"""
echo "=== 1. 上传文件 MD5 ==="
md5sum /home/user/boot_v2.img

echo
echo "=== 2. 备份 boot 分区到 /root/boot_bak_before_v2.img ==="
dd if=/dev/mmcblk0p12 of=/root/boot_bak_before_v2.img bs=1M count=64 2>/dev/null
md5sum /root/boot_bak_before_v2.img

echo
echo "=== 3. 当前 boot 分区 MD5(应与原版 85f9c9fc... 一致) ==="
dd if=/dev/mmcblk0p12 bs=1M count=64 2>/dev/null | md5sum

echo
echo "=== 4. 目标分区确认 ==="
lsblk -o NAME,SIZE,TYPE,LABEL,PARTUUID /dev/mmcblk0p12
ls -la /dev/mmcblk0p12

echo
echo "=== 5. 移动到 /root 并校验 ==="
mv /home/user/boot_v2.img /root/boot_v2.img
md5sum /root/boot_v2.img
ls -la /root/boot_v2.img
"""

stdin, stdout, stderr = cli.exec_command("sudo -S -p '' bash -s", timeout=600)
stdin.write(PWD + "\n")
stdin.write(CMD)
stdin.channel.shutdown_write()
out = stdout.read().decode("utf-8", "replace")
print(out)
e = stderr.read().decode("utf-8", "replace")
if e.strip():
    print("[stderr]", e[:1500])

if LOCAL_MD5 not in out:
    print("\n!!! 上传后 MD5 不一致，中止 !!!")
    cli.close()
    sys.exit(1)

if "85f9c9fceacc4736ed45bcc657190305" not in out:
    print("\n!!! 当前 boot 分区不是已知的原版镜像，中止 !!!")
    cli.close()
    sys.exit(1)

print("\n[预检通过] 上传一致 + 当前 boot 分区=原版 + 备份已建立")
cli.close()
