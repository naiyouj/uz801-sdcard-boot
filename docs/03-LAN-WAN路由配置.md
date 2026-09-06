# UZ801 变身无线路由器：网口=LAN，WiFi=WAN

> 2026-09-06 · 设备 `4G-wifi` · 与 USB host 模式配置共存（SD 卡已挂 `/mnt/sd`）

---

## 一、当前拓扑（已生效）

```
                       ┌─────────────────────────┐
   iKuai2G-982e  ))))) │ wlan0   192.168.9.101   │   WAN 上行
   (上级路由)          │                         │
                       │      NAT + DHCP         │
                       │                         │
   电脑/下游设备 ──────│ enx00e04c360028         │   LAN 下行
   192.168.100.18      │ 192.168.100.1/24        │
                       └─────────────────────────┘
```

| 角色 | 接口 | 地址 | 说明 |
|---|---|---|---|
| **WAN** | `wlan0` | `192.168.9.101/24` | 连 `iKuai2G-982e`（WPA2-PSK），网关 `192.168.9.1` |
| **LAN** | `enx00e04c360028` | `192.168.100.1/24` | RTL8152 有线网卡，DHCP 池 `192.168.100.10-254` |

DNS：`114.114.114.114`、`223.5.5.5`（从 iKuai 下发）
IP 转发：`net.ipv4.ip_forward = 1`
NAT：`MASQUERADE`，源 `192.168.100.0/24` → 出接口 wlan0

---

## 二、验证结果（全部通过）

```
ping 192.168.9.1        3/3 通   平均 15ms      ← 上级网关
ping 223.5.5.5          3/3 通   平均 21ms      ← 棒子自身上网
curl baidu.com          HTTP 200  61ms
ping -I 192.168.100.1   2/2 通   平均 17ms      ← LAN 侧源地址出网(NAT 生效)

本机(192.168.100.18) ping 223.5.5.5  通, TTL=48  ← 经过 NAT
DHCP 租约: 192.168.100.18 -> WIN-NCJSN6QDKTV      ← 电脑已拿到 LAN 地址
```

---

## 三、做了哪些改动

### NetworkManager 连接

| 连接名 | 类型 | 设备 | 状态 |
|---|---|---|---|
| `wan-wifi` | wifi (station) | wlan0 | **新建并激活** — 连 `iKuai2G-982e` |
| `lan` | ethernet (shared) | enx00e04c360028 | **新建并激活** — `192.168.100.1/24`，自带 dnsmasq + NAT |
| `wifi` | wifi (AP) | — | 保留但 `autoconnect=no`，已停用（原 `4G-WIFI` 热点） |
| `有线连接 1` | ethernet | — | 已删除（原来的自动获取，拿不到 IP） |

`lan` 用 NM 的 `ipv4.method shared`，所以 DHCP / NAT / IP 转发全部由 NM 自动管理，不用手写 iptables。

### 一键切换脚本

```bash
sudo /usr/local/bin/net-wifi-wan.sh     # 切到: WiFi=WAN + 网口=LAN（当前模式）
sudo /usr/local/bin/net-ap-hotspot.sh   # 切回: WiFi=AP 热点 4G-WIFI
```

两个脚本已通过 `sh -n` 语法检查。

---

## 四、怎么连设备（三种方式，按当前拓扑）

```bash
ssh user@192.168.100.1    # 走有线 LAN 口（最稳，不受 WiFi 切换影响）
ssh user@192.168.9.101    # 走 iKuai 网络直连（wlan0 的地址）
ssh user@10.42.0.1        # 仅在执行 net-ap-hotspot.sh 恢复热点后可用
# 密码统一是 1
```

---

## 五、⚠️ 注意事项

1. **热点没了**
   `4G-WIFI` 已停用，电脑不能再通过 WiFi 连设备。想恢复就跑 `net-ap-hotspot.sh`。

2. **你这台电脑现在有两条路出网**
   - `192.168.9.103` → 直连 iKuai（metric 25，**默认走这条**）
   - `192.168.100.18` → 经棒子 NAT（metric 35）
   想强制走棒子，把有线网卡的 metric 调低，或临时加路由：
   `route add 0.0.0.0 mask 0.0.0.0 192.168.100.1 metric 10`

3. **有一条过宽的 NAT 规则**
   ```
   MASQUERADE  all  --  *  *  192.168.0.0/16  0.0.0.0/0
   ```
   这是固件自带的残留规则，覆盖整个 192.168 段（含 WAN 侧的 192.168.9.0/24）。
   后果：LAN 侧访问 iKuai 网络内其他设备时，源地址会被伪装成 `192.168.9.101`。
   普通上网无影响；若需要 LAN 侧直接访问上级网络设备（NAS、打印机等），得把这条删掉：
   ```bash
   sudo iptables -t nat -D POSTROUTING -s 192.168.0.0/16 -j MASQUERADE
   ```

4. **网口速率**：RTL8152 是 USB 2.0 百兆卡，实际吞吐受棒子 CPU（1.4GHz A53×4）限制，大概 60-90 Mbps 上下。

5. **SD 卡还在**：`/mnt/sd` 正常挂载，配置没受影响。

---

## 六、恢复原状

```bash
# 方式一：只恢复热点（网口仍为 LAN）
sudo /usr/local/bin/net-ap-hotspot.sh

# 方式二：完全恢复出厂网络（删除本次所有连接）
sudo nmcli connection delete wan-wifi
sudo nmcli connection delete lan
sudo nmcli connection modify wifi connection.autoconnect yes
sudo nmcli connection up wifi
sudo reboot
```
