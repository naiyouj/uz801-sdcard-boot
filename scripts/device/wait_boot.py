# -*- coding: utf-8 -*-
"""轮询等待设备重启，并检查是否成功从 SD 卡启动"""
import paramiko, time, sys

HOST, USER, PWD = "192.168.9.101", "user", "1"
DEADLINE = time.time() + 300

CHECK = r"""
echo "--- cmdline ---"; cat /proc/cmdline
echo "--- root ---";    findmnt -no SOURCE /
echo "--- uptime ---";  uptime
echo "--- lsblk ---";   lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT | grep -E 'sda|mmcblk0p14|^NAME'
echo "--- role ---";    cat /sys/kernel/debug/usb/ci_hdrc.0/role 2>/dev/null
echo "--- df ---";      df -h / | tail -1
echo "--- NM ---";      nmcli -t -f NAME,TYPE,DEVICE,STATE c show --active 2>/dev/null
"""

print("等待设备重启（最多 300 秒）...")
time.sleep(45)

last_err = None
while time.time() < DEADLINE:
    try:
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cli.connect(HOST, username=USER, password=PWD, timeout=8)
        print("\n[SSH 已连上]")
        stdin, stdout, stderr = cli.exec_command("sudo -S -p '' bash -s", timeout=60)
        stdin.write(PWD + "\n")
        stdin.write(CHECK)
        stdin.channel.shutdown_write()
        out = stdout.read().decode("utf-8", "replace")
        print(out)
        cli.close()
        if "/dev/sda1" in out:
            print(">>> 成功：已从 SD 卡启动！")
            sys.exit(0)
        else:
            print(">>> 起来了，但 root 仍不是 /dev/sda1（可能回退到 eMMC，或还没切）")
            sys.exit(2)
    except Exception as e:
        last_err = e
        print("  未就绪: %s" % str(e)[:80])
        time.sleep(10)

print("\n[超时] 300 秒内没能连上。最后错误:", last_err)
print("可能仍在启动，或启动失败。请用电脑连棒子进 fastboot 检查。")
sys.exit(1)
