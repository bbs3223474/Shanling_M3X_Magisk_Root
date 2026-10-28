import gzip, io, struct, sys

class Entry:
    __slots__ = ("name", "mode", "uid", "gid", "nlink", "mtime", "data", "devmajor",
                 "devminor", "rdevmajor", "rdevminor", "ino")


def read_cpio(data):
    entries = []
    off = 0
    while True:
        if data[off:off + 6] != b"070701":
            raise ValueError(f"bad cpio magic at {off}: {data[off:off+8]!r}")
        f = [int(data[off + 6 + i * 8: off + 14 + i * 8], 16) for i in range(13)]
        ino, mode, uid, gid, nlink, mtime, fsize, dmaj, dmin, rmaj, rmin, namesize, chk = f
        name_start = off + 110
        name = data[name_start:name_start + namesize - 1].decode("utf-8", "replace")
        p = name_start + namesize
        p += (-p) % 4
        payload = data[p:p + fsize]
        p += fsize
        p += (-p) % 4
        if name == "TRAILER!!!":
            break
        e = Entry()
        e.name, e.mode, e.uid, e.gid, e.nlink, e.mtime = name, mode, uid, gid, nlink, mtime
        e.data = payload
        e.devmajor, e.devminor, e.rdevmajor, e.rdevminor = dmaj, dmin, rmaj, rmin
        e.ino = ino
        entries.append(e)
        off = p
    return entries


def write_cpio(entries):
    out = io.BytesIO()
    ino = 1
    for e in entries:
        name = e.name.encode()
        hdr = b"070701" + b"".join(f"{v:08x}".encode() for v in (
            e.ino, e.mode, e.uid, e.gid, e.nlink, e.mtime, len(e.data),
            e.devmajor, e.devminor, e.rdevmajor, e.rdevminor, len(name) + 1, 0))
        out.write(hdr)
        out.write(name + b"\x00")
        pad = (-(110 + len(name) + 1)) % 4
        out.write(b"\x00" * pad)
        out.write(e.data)
        out.write(b"\x00" * ((-len(e.data)) % 4))
        ino += 1
    name = b"TRAILER!!!"
    hdr = b"070701" + b"".join(f"{v:08x}".encode() for v in (
        0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, len(name) + 1, 0))
    out.write(hdr)
    out.write(name + b"\x00")
    out.write(b"\x00" * ((-(110 + len(name) + 1)) % 4))
    return out.getvalue()


def load_boot(path):
    b = open(path, "rb").read()
    ks, ka, rs, ra, ss, sa, tags, page, hv, osv = struct.unpack_from("<10I", b, 8)
    ko = page
    ro = ko + ((ks + page - 1) // page) * page
    header = bytearray(b[:page])
    kernel = b[ko:ko + ks]
    ramdisk = b[ro:ro + rs]
    return b, header, kernel, ramdisk, dict(ks=ks, ka=ka, rs=rs, ra=ra, ss=ss, sa=sa,
                                            tags=tags, page=page, hv=hv, osv=osv)


def build_boot(header, kernel, ramdisk, meta, total_size=None):
    page = meta["page"]
    ks = len(kernel)
    rs = len(ramdisk)
    struct.pack_into("<I", header, 8, ks)
    struct.pack_into("<I", header, 16, rs)
    out = bytearray()
    out += header
    out += kernel + b"\x00" * ((-ks) % page)
    out += ramdisk + b"\x00" * ((-rs) % page)
    if total_size:
        if len(out) < total_size:
            out += b"\x00" * (total_size - len(out))
    return bytes(out)


if __name__ == "__main__":
    b, header, kernel, ramdisk, meta = load_boot(sys.argv[1])
    print("meta:", meta)
    cpio = gzip.decompress(ramdisk)
    print("cpio size:", len(cpio))
    ents = read_cpio(cpio)
    print(f"{len(ents)} entries")
    for e in ents:
        print(f"  {oct(e.mode)} {e.uid}:{e.gid} {len(e.data):8d} {e.name}")
