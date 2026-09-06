# -*- coding: utf-8 -*-
"""诊断 SD 卡启动失败的根因"""
import paramiko, sys

HOST = "192.168.9.101"
USER = "user"
PWD = "1"

CMDS = [
    ("== 基本信息 ==", "uname -a; echo '--- cmdline ---'; cat /proc/cmdline; echo '--- root ---'; findmnt -no SOURCE /; echo '--- uptime ---'; uptime"),

    ("== 块设备 ==", "lsblk -o NAME,SIZE,TYPE,FSTYPE,PARTUUID,MOUNTPOINT 2>/dev/null"),

    ("== USB 状态 ==", "lsusb 2>/dev/null; echo '--- role ---'; cat /sys/kernel/debug/usb/ci_hdrc.0/role 2>/dev/null || echo 'NO_ROLE_FILE'; echo '--- usb bus ---'; ls /sys/bus/usb/devices/ 2>/dev/null | head -20"),

    ("== DT usb节点 ==", "cd /sys/firmware/devicetree/base 2>/dev/null || cd /proc/device-tree; "
                         "for n in $(find . -maxdepth 4 -name 'usb@78d9000' 2>/dev/null); do "
                         "echo \"NODE=$n\"; ls $n; echo '--- dr_mode ---'; cat $n/dr_mode 2>/dev/null; echo; "
                         "echo '--- extensible-connector(extcon props) ---'; ls $n | grep -i -E 'extcon|connector'; "
                         "for p in $(ls $n | grep -i -E 'extcon|connector'); do echo \"prop=$p len=$(stat -c%s $n/$p 2>/dev/null)\"; "
                         "xxd $n/$p 2>/dev/null | head -3; done; done"),

    ("== usb_id extcon 节点 ==", "cd /sys/firmware/devicetree/base 2>/dev/null || cd /proc/device-tree; "
                                  "for n in $(find . -maxdepth 5 -name 'usb-id' -o -maxdepth 5 -name 'extcon*' -o -maxdepth 5 -name 'usb_id' 2>/dev/null); do "
                                  "echo \"NODE=$n\"; ls $n 2>/dev/null; "
                                  "for p in compatible gpios status; do echo \"  $p: $(cat $n/$p 2>/dev/null | tr '\\0' ' ')\"; done; done"),

    ("== 关键内核模块 (M还是y) ==", "K=$(uname -r); echo \"kernel=$K\"; "
                                     "for m in ci_hdrc ci_hdrc_msm msm_hsusb phy_qcom_usb_hs phy_qcom_usb_hsic "
                                     "ehci_hcd ehci_msm ohci_hcd usb_storage uas sd_mod mmc_block extcon_usb_gpio gpio_keys; do "
                                     "f=$(find /lib/modules/$K -name \"$m.ko*\" 2>/dev/null | head -1); "
                                     "if [ -n \"$f\" ]; then echo \"$m : MODULE  $f\"; "
                                     "elif [ -f /proc/kallsyms ] && grep -q \" $m\" /proc/kallsyms 2>/dev/null; then echo \"$m : maybe-builtin\"; "
                                     "else echo \"$m : NOT-FOUND\"; fi; done; "
                                     "echo '--- config ---'; zcat /proc/config.gz 2>/dev/null | grep -E 'CONFIG_USB_CHIPIDEA|CONFIG_USB_MSM_OTG|CONFIG_PHY_QCOM_USB|CONFIG_USB_EHCI_MSM|CONFIG_USB_STORAGE|CONFIG_BLK_DEV_SD|CONFIG_MMC_BLOCK' || "
                                     "grep -rE 'CONFIG_USB_CHIPIDEA|CONFIG_PHY_QCOM_USB|CONFIG_USB_EHCI_MSM|CONFIG_USB_STORAGE|CONFIG_BLK_DEV_SD' /boot/config-* 2>/dev/null | head -20"),

    ("== 当前已加载 USB 模块 ==", "lsmod | grep -i -E 'ci_hdrc|usb|ehci|phy|sd_mod|mmc' | head -30"),

    ("== initramfs 模块清单 ==", "ls -la /boot/initrd.img-* /boot/initramfs-* 2>/dev/null; echo '--- modules file ---'; cat /etc/initramfs-tools/modules 2>/dev/null; echo '--- 现有 initrd 内含 usb/sd 模块 ---'; "
                                  "for f in $(ls /boot/initrd.img-* 2>/dev/null | head -1); do echo \"FILE=$f\"; "
                                  "unmkinitramfs /tmp/irdx $f 2>/dev/null || (mkdir -p /tmp/irdx && cd /tmp/irdx && zcat $f | cpio -idm 2>/dev/null); "
                                  "find /tmp/irdx -name '*.ko*' 2>/dev/null | grep -i -E 'ci_hdrc|ehci|usb|phy|sd_mod|mmc|extcon' | head -30; "
                                  "echo '--- total ko ---'; find /tmp/irdx -name '*.ko*' 2>/dev/null | wc -l; done"),

    ("== SD 卡现状 ==", "blkid | grep -E '^/dev/sd' || echo 'NO_SD_BLOCK_DEV'; echo '--- dmesg usb ---'; dmesg | tail -40"),
]


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        cli.connect(HOST, username=USER, password=PWD, timeout=15)
    except Exception as e:
        print("CONNECT_FAIL:", e)
        return 1
    print("CONNECTED to", HOST)

    for title, cmd in CMDS:
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)
        try:
            stdin, stdout, stderr = cli.exec_command("sudo -S -p '' bash -s", timeout=180)
            stdin.write(PWD + "\n")
            stdin.write(cmd)
            stdin.channel.shutdown_write()
            out = stdout.read().decode("utf-8", "replace")
            err = stderr.read().decode("utf-8", "replace")
            print(out)
            if err.strip():
                print("[stderr]", err[:2000])
        except Exception as e:
            print("CMD_ERR:", e)
    cli.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
