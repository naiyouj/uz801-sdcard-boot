# -*- coding: utf-8 -*-
"""构造 512 字节 MBR，磁盘签名 0x8306c78f，三分区 6G+4G+1G"""
import struct

DISK_ID = 0x8306c78f

PARTS = [
    # (bootable, type, start_lba, sectors)
    (True,  0x83,      8192,  6 * 1024 * 1024 * 1024 // 512),   # 6G  rootfs  sdroot
    (False, 0x83,  12591104,  4 * 1024 * 1024 * 1024 // 512),   # 4G  data    sddata
    (False, 0x82,  20979712,      1024 * 1024 * 1024 // 512),   # 1G  swap    sdswap
]

MAX_CHS_LBA = 1024 * 255 * 63  # 16450560


def chs(lba):
    """LBA -> (head, sector_cyl_hi, cyl_lo)"""
    if lba > MAX_CHS_LBA:
        return (0xFE, 0xFF, 0xFF)
    sector = (lba % 63) + 1
    head = (lba // 63) % 255
    cyl = (lba // 63) // 255
    if cyl > 1023:
        return (0xFE, 0xFF, 0xFF)
    return (head & 0xFF, (sector & 0x3F) | ((cyl >> 2) & 0xC0), cyl & 0xFF)


mbr = bytearray(512)

for i, (boot, ptype, start, count) in enumerate(PARTS):
    off = 0x1BE + i * 16
    h1, s1, c1 = chs(start)
    h2, s2, c2 = chs(start + count - 1)
    mbr[off + 0] = 0x80 if boot else 0x00
    mbr[off + 1] = h1
    mbr[off + 2] = s1
    mbr[off + 3] = c1
    mbr[off + 4] = ptype
    mbr[off + 5] = h2
    mbr[off + 6] = s2
    mbr[off + 7] = c2
    struct.pack_into("<I", mbr, off + 8, start)
    struct.pack_into("<I", mbr, off + 12, count)
    end_gb = (start + count) * 512 / 1024**3
    print("part%d type=0x%02x boot=%d start=%10d count=%10d  end=%.2fGB"
          % (i + 1, ptype, boot, start, count, end_gb))

# 磁盘签名 (决定 PARTUUID 前缀)
struct.pack_into("<I", mbr, 0x1B8, DISK_ID)
# 结束标志
mbr[0x1FE] = 0x55
mbr[0x1FF] = 0xAA

open("mbr.bin", "wb").write(bytes(mbr))
print("\n磁盘签名: 0x%08x  -> PARTUUID 前缀 %08x" % (DISK_ID, DISK_ID))
print("镜像最小大小: %d sectors = %.2f GB"
      % (PARTS[-1][2] + PARTS[-1][3], (PARTS[-1][2] + PARTS[-1][3]) * 512 / 1024**3))
print("已写出 mbr.bin (512 bytes)")

# 回读校验
v = open("mbr.bin", "rb").read()
assert v[0x1FE:0x200] == b"\x55\xaa", "结束标志错误"
assert struct.unpack("<I", v[0x1B8:0x1BC])[0] == DISK_ID
for i, (_, ptype, start, count) in enumerate(PARTS):
    off = 0x1BE + i * 16
    assert struct.unpack("<I", v[off + 8:off + 12])[0] == start
    assert struct.unpack("<I", v[off + 12:off + 16])[0] == count
    assert v[off + 4] == ptype
print("回读校验 OK")
