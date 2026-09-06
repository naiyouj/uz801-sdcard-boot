# UZ801 (OpenStick) USB 口改 Host 模式 —— 已搞定 ✅

> 2026-09-06 · 设备：`4G-wifi` · 内核 `5.15.0-jsbsbxjxh66+`
> **结论：不用 OTG 线，纯软件改一行即可，重启后自动生效，SD 卡已能正常读写。**

---

## 一、正确做法（就这一行）

```bash
echo host > /sys/kernel/debug/usb/ci_hdrc.0/role
```

注意路径是 **`/sys/kernel/debug/usb/ci_hdrc.0/role`**，不是 `/sys/kernel/debug/ci_hdrc.0/role`。
chipidea 的 debugfs 挂在 `usb_debug_root` 下，**中间多一层 `usb/`**（我第一遍就是漏了这层才以为没有 role 接口）。

- 当前值读法：`cat /sys/kernel/debug/usb/ci_hdrc.0/role` → `host` / `gadget`
- 切回 device 模式：`echo gadget > /sys/kernel/debug/usb/ci_hdrc.0/role`

---

## 二、已做的改动

### 1. 启动脚本持久化的补丁

文件：`/usr/sbin/mobian-usb-gadget`

```diff
 setup() {
+    # ---- 强制 USB host 模式 (板上 ID 脚浮空，无需 OTG 线) ----
+    # 想恢复 device(adb/rndis) 模式: 把下面的 host 改成 gadget，或直接注释掉
+    echo host > /sys/kernel/debug/usb/ci_hdrc.0/role
+
     # Remove All Gadgets If Gadget Exist
     [ -d $CONFIGFS ] && gc -c
     ...
```

- 原文件已备份两份：
  - 设备上：`/usr/sbin/mobian-usb-gadget.bak`
  - 本地：`mobian-usb-gadget.orig`
- 补丁后版本本地留存：`mobian-usb-gadget.patched`
- 已通过 `sh -n` 语法检查

### 2. SD 卡开机自动挂载

`/etc/fstab` 追加（原文件已备份为 `/etc/fstab.bak`）：

```
UUID=1b1e2556-13d1-47a0-b366-ee3971ff2558 /mnt/sd ext4 defaults,nofail,noatime 0 2
```

`nofail` 保证 SD 卡不在时不会卡住启动。`findmnt --verify` 校验通过。

---

## 三、验证结果（重启后实测）

```
role = host                        ← 开机自动切换，无需人工干预
mobian-usb-gadget.service = active

USB 枚举:
  1-1:   USB2.0 HUB        [1a40:0101]
  1-1.1: USB 10/100 LAN    [0bda:8152]   → 网卡 enx00e04c360028 (已 UP)
  1-1.2: MXT USB Device    [aaaa:8816]   → 读卡器
  usb1:  EHCI Host Controller

SD 卡:
  /dev/sda1  30G  已用 2.2G  可用 26G  → 已挂载 /mnt/sd  ✅
```

SD 卡里原有内容：`ostk/`、`swapfile`(2G)、`var-cache-apt/`、`var-log/`、`var-tmp/`、`lost+found/`

---

## 四、之前的错误结论（已作废，别再照做）

我早前判断"软件走不通、必须买 OTG 线"，**这是错的**，原因是 debugfs 路径查错。
下面这些弯路记录在此，避免重复踩：

| 走过的弯路 | 结果 |
|---|---|
| 拉低 ID 脚 GPIO 500（pinctrl pin110） | gadget 掉线但 host 起不来，卡在中间态 |
| unbind `extcon-usb-gpio` 拉低 GPIO 后重新 bind `msm_hsusb` | ci_hdrc probe 找不到 extcon → `-EPROBE_DEFER` → bind 失败 |
| 在 UDC 已解绑时跑 `mobian-usb-gadget reset` | **内核 Oops** `usb_put_function_instance+0x24/0x40`，USB 子系统崩溃，systemd 半死（22 端口连得上但发不出 banner），只能拔电重启 |
| 改 DT `dr_mode=host` + 重刷 boot | 完全没必要（也没做） |

**root cause：ID 脚那条路根本不用走，`role` debugfs 接口才是正解。**

---

## 五、注意事项

1. **usb0 (RNDIS) 不能用了**
   进 host 后 gadget 停掉，usb0 会 DOWN 且无 IP，电脑不能再通过 USB 网卡连设备。
   现在走 WiFi 热点 `4G-WIFI`（密码 `12345678`）连，地址通常是 `10.42.0.1` 或 `10.42.1.1`，两个都试。

2. **启动时日志里会有报错，属正常**
   ```
   install_listener('tcp:5037','*smartsocket*')
   cannot bind 'tcp:5037'
   failed to enable gadget!
   ```
   host 模式下 adbd / rndis 本来就无用，`gc -e` 绑定 UDC 必然失败。**不影响 host 功能。**
   想消掉的话，在 `echo host > ...` 那行后面加一句 return 提前退出：
   ```sh
   USB_ROLE=host
   echo $USB_ROLE > /sys/kernel/debug/usb/ci_hdrc.0/role
   [ "$USB_ROLE" = host ] && return 0
   ```
   这样改成 `USB_ROLE=gadget` 时还能正常走回 device 模式。

3. **供电**：hub 上的 RTL8152 网卡 + 读卡器都能正常枚举，说明你这套供电是够的。
   若以后插更大功耗设备（移动硬盘）出现 `device descriptor read/64, error -71` 或反复断连，
   就是板上无 5V boost 输出导致的，需换**自供电** hub。

4. **要恢复 device 模式**：
   ```bash
   sudo cp /usr/sbin/mobian-usb-gadget.bak /usr/sbin/mobian-usb-gadget
   sudo reboot
   ```

---

## 六、常用命令速查

```bash
# 查看/切换 USB 角色
cat /sys/kernel/debug/usb/ci_hdrc.0/role
echo host   > /sys/kernel/debug/usb/ci_hdrc.0/role
echo gadget > /sys/kernel/debug/usb/ci_hdrc.0/role

# 看枚举到的 USB 设备
for d in /sys/bus/usb/devices/*; do
  [ -f "$d/idVendor" ] && echo "$(basename $d): $(cat $d/product 2>/dev/null)"
done

# SD 卡
lsblk
mount /dev/sda1 /mnt/sd      # 手动挂载（正常情况下 fstab 已自动挂好）
umount /mnt/sd               # 卸载后再拔卡，避免数据损坏
```

> ⚠️ 拔 SD 卡前务必 `umount /mnt/sd`，否则 ext4 可能损坏。
