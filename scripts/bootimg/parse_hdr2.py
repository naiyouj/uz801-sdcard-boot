# -*- coding: utf-8 -*-
"""完整解析 Android boot.img header（含 v0~v4 的 dtb 字段）"""
import struct, sys, hashlib, os

def parse(path):
    d = open(path, "rb").read()
    magic = d[0:8]
    print("FILE      :", path)
    print("SIZE      :", len(d))
    print("magic     :", magic)
    if magic != b"ANDROID!":
        print("NOT an android boot.img")
        return

    kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr, \
        tags_addr, page_size = struct.unpack("<8I", d[8:40])

    header_version = struct.unpack("<I", d[0x28:0x2C])[0]
    name = d[0x30:0x40].rstrip(b"\0").decode(errors="replace")
    cmdline = d[0x40:0x240].rstrip(b"\0").decode(errors="replace")

    print("kernel    : size=%d (0x%x) addr=0x%08x" % (kernel_size, kernel_size, kernel_addr))
    print("ramdisk   : size=%d (0x%x) addr=0x%08x" % (ramdisk_size, ramdisk_size, ramdisk_addr))
    print("second    : size=%d addr=0x%08x" % (second_size, second_addr))
    print("tags_addr : 0x%08x" % tags_addr)
    print("page_size : %d (0x%x)" % (page_size, page_size))
    print("header_ver: %d" % header_version)
    print("name      : %r" % name)
    print("cmdline   : %r" % cmdline)

    ps = page_size
    def pages_up(n):
        return ((n + ps - 1) // ps) * ps

    off_kernel = ps
    off_ramdisk = off_kernel + pages_up(kernel_size)
    off_second = off_ramdisk + pages_up(ramdisk_size)
    print("\n--- 各段偏移（按页对齐推算）---")
    print("kernel  off : 0x%x  (end 0x%x)" % (off_kernel, off_kernel + kernel_size))
    print("ramdisk off : 0x%x  (end 0x%x)" % (off_ramdisk, off_ramdisk + ramdisk_size))
    print("second  off : 0x%x" % off_second)

    if header_version >= 1:
        recovery_dtbo_size, recovery_dtbo_offset, header_size = struct.unpack("<IQQ", d[0x244:0x258])
        print("recovery_dtbo: size=%d off=0x%x" % (recovery_dtbo_size, recovery_dtbo_offset))
        print("header_size  : %d" % header_size)
    if header_version >= 2:
        dtb_size, dtb_addr = struct.unpack("<IQ", d[0x24C:0x258])
        print("dtb_size     : %d (0x%x)" % (dtb_size, dtb_size))
        print("dtb_addr     : 0x%x" % dtb_addr)
    else:
        dtb_size = None
        print("dtb_size     : <header v%d 无此字段>" % header_version)

    # 在 kernel 尾部之后搜索 appended DTB (magic d00dfeed)
    print("\n--- appended DTB 搜索 ---")
    scan_from = off_kernel + pages_up(kernel_size)
    scan_to = min(off_ramdisk, len(d))
    pos = d.find(b"\xd0\x0d\xfe\xed", scan_from, scan_to)
    if pos < 0:
        pos = d.find(b"\xd0\x0d\xfe\xed", off_kernel, len(d))
    if pos >= 0:
        total = struct.unpack(">I", d[pos + 4:pos + 8])[0]
        print("DTB magic @ 0x%x  totalsize=%d  (end 0x%x)" % (pos, total, pos + total))
        print("gap after kernel(aligned): %d bytes" % (pos - (off_kernel + pages_up(kernel_size))))
        if dtb_size:
            print(">>> header.dtb_size=%d  实际 DTB=%d  %s" %
                  (dtb_size, total, "OK" if dtb_size == total else "!!! 不一致 !!!"))
        blob = d[pos:pos + total]
        print("DTB md5 :", hashlib.md5(blob).hexdigest())
        open(os.path.splitext(path)[0] + ".extracted.dtb", "wb").write(blob)
    else:
        print("未找到 appended DTB")

    # ramdisk 校验
    rd = d[off_ramdisk:off_ramdisk + ramdisk_size]
    print("\nramdisk magic:", rd[:6])
    print("ramdisk md5  :", hashlib.md5(rd).hexdigest())

if __name__ == "__main__":
    for p in sys.argv[1:]:
        parse(p)
        print("\n" + "=" * 60 + "\n")
