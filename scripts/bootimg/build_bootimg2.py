# -*- coding: utf-8 -*-
"""
重新构建 SD 卡启动的 boot.img
修正上一版的致命 bug: kernel_size 未随新 DTB 长度更新，导致 DTB 尾部被截断
"""
import struct, hashlib, os, sys

SRC = "boot_orig.img"
NEW_DTB = "boot_new.dtb"
OUT = "boot_v2.img"

CMDLINE = ("earlycon root=PARTUUID=8306c78f-01 rootwait rootdelay=20 "
           "rootfstype=ext4 console=ttyMSM0,115200 no_framebuffer=true rw")

d = bytearray(open(SRC, "rb").read())
assert bytes(d[0:8]) == b"ANDROID!", "不是 Android boot.img"

(kernel_size, kernel_addr, ramdisk_size, ramdisk_addr,
 second_size, second_addr, tags_addr, page_size) = struct.unpack("<8I", d[8:40])

hdr_ver = struct.unpack("<I", d[0x28:0x2C])[0]
old_cmdline = d[0x40:0x240].rstrip(b"\0").decode(errors="replace")
print("原 kernel_size :", kernel_size)
print("原 ramdisk_size:", ramdisk_size)
print("原 page_size   :", page_size, " header_ver:", hdr_ver)
print("原 cmdline     :", old_cmdline)

ps = page_size
def pages_up(n):
    return ((n + ps - 1) // ps) * ps

off_kernel = ps
off_ramdisk = off_kernel + pages_up(kernel_size)

# --- 定位 appended DTB ---
dtb_off = bytes(d).find(b"\xd0\x0d\xfe\xed", off_kernel, off_ramdisk)
assert dtb_off >= 0, "找不到 appended DTB"
old_dtb_total = struct.unpack(">I", d[dtb_off + 4:dtb_off + 8])[0]
print("\nDTB @0x%x  size=%d  end=0x%x" % (dtb_off, old_dtb_total, dtb_off + old_dtb_total))
print("ramdisk @0x%x" % off_ramdisk)

kernel_pure_len = dtb_off - off_kernel          # kernel 不含 DTB 的部分
print("kernel(纯)长度 :", kernel_pure_len)

# --- 读新 DTB ---
new_dtb = open(NEW_DTB, "rb").read()
assert new_dtb[:4] == b"\xd0\x0d\xfe\xed", "新 DTB magic 错误"
new_dtb_total = struct.unpack(">I", new_dtb[4:8])[0]
assert new_dtb_total == len(new_dtb), "DTB totalsize(%d) != 文件长度(%d)" % (new_dtb_total, len(new_dtb))
print("新 DTB 长度    :", len(new_dtb))

# 校验 dr_mode
i = new_dtb.find(b"dr_mode")
if i > 0:
    s = new_dtb[i:i + 40].split(b"\0")[0]
    print("新 DTB dr_mode :", s, " (前后文:", new_dtb[max(0, i - 8):i + 24], ")")
if new_dtb.find(b"host\0") > 0:
    print("新 DTB 含 'host' 字符串 OK")

# --- 新的 kernel_size ---
new_kernel_size = kernel_pure_len + len(new_dtb)
print("\n新 kernel_size :", new_kernel_size, " (原 %d, +%d)" % (kernel_size, new_kernel_size - kernel_size))

new_off_ramdisk = off_kernel + pages_up(new_kernel_size)
print("新 ramdisk off : 0x%x (原 0x%x) %s" % (
    new_off_ramdisk, off_ramdisk,
    "不变" if new_off_ramdisk == off_ramdisk else "!!! 需要移动 ramdisk !!!"))

# --- 组装 ---
out = bytearray(d)

# 1) 新 cmdline（先清零，且必须清干净，防止残留）
out[0x40:0x240] = b"\0" * 0x200
cb = CMDLINE.encode()
assert len(cb) < 512, "cmdline 太长"
out[0x40:0x40 + len(cb)] = cb

# 2) 写新 DTB（原位）
dtb_end_new = dtb_off + len(new_dtb)
assert dtb_end_new <= off_ramdisk, "新 DTB 越界到 ramdisk!"
out[dtb_off:dtb_end_new] = new_dtb
# 若新 DTB 比旧的短，残留部分清零（这里只会更长，保险起见仍处理）
if len(new_dtb) < old_dtb_total:
    out[dtb_end_new:dtb_off + old_dtb_total] = b"\0" * (old_dtb_total - len(new_dtb))
# kernel 尾部到 ramdisk 之间的空隙清零
out[dtb_end_new:off_ramdisk] = b"\0" * (off_ramdisk - dtb_end_new)

# 3) 更新 kernel_size（关键！）
struct.pack_into("<I", out, 0x08, new_kernel_size)

# 4) 若 ramdisk 需要移动（本例通常不需要）
if new_off_ramdisk != off_ramdisk:
    rd = bytes(d[off_ramdisk:off_ramdisk + ramdisk_size])
    out[new_off_ramdisk:new_off_ramdisk + ramdisk_size] = rd

open(OUT, "wb").write(bytes(out))
print("\n写出:", OUT, os.path.getsize(OUT), "bytes")
print("MD5 :", hashlib.md5(bytes(out)).hexdigest())

# --- 回读校验 ---
v = open(OUT, "rb").read()
vk = struct.unpack("<I", v[8:12])[0]
vdtb = v.find(b"\xd0\x0d\xfe\xed", off_kernel, len(v))
vtotal = struct.unpack(">I", v[vdtb + 4:vdtb + 8])[0]
vrd = v[off_kernel + pages_up(vk):off_kernel + pages_up(vk) + 6]
print("\n--- 回读校验 ---")
print("kernel_size :", vk, "OK" if vk == new_kernel_size else "FAIL")
print("DTB @0x%x total=%d  end=0x%x (需 <= 0x%x)" % (vdtb, vtotal, vdtb + vtotal, off_ramdisk))
print("DTB 完整    :", "OK" if vdtb + vtotal <= off_ramdisk else "FAIL")
print("ramdisk magic:", vrd, "OK" if vrd[:2] == b"\x1f\x8b" else "FAIL")
print("ramdisk md5 :", hashlib.md5(v[off_kernel + pages_up(vk):off_kernel + pages_up(vk) + ramdisk_size]).hexdigest())
print("cmdline     :", v[0x40:0x240].rstrip(b"\0").decode())
