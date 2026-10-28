import struct, sys

def parse(path):
    b = open(path, "rb").read()
    assert b[:8] == b"ANDROID!"
    (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr,
     tags_addr, page_size, header_version, os_version) = struct.unpack_from("<10I", b, 8)
    name = b[48:48 + 16].split(b"\x00")[0]
    cmdline = b[64:64 + 512].split(b"\x00")[0]
    hdr_id = b[576:576 + 8]
    extra = b[584:584 + 1024].split(b"\x00")[0]
    return dict(size=len(b), kernel_size=kernel_size, kernel_addr=hex(kernel_addr),
                ramdisk_size=ramdisk_size, ramdisk_addr=hex(ramdisk_addr),
                second_size=second_size, second_addr=hex(second_addr), tags_addr=hex(tags_addr),
                page_size=page_size, header_version=header_version, os_version=hex(os_version),
                name=name, cmdline=cmdline, extra_cmdline=extra)

if __name__ == "__main__":
    for p in sys.argv[1:]:
        print("==", p)
        for k, v in parse(p).items():
            print(f"  {k}: {v}")
