"""AOSP whole-file OTA signer (SignApk -w equivalent) in pure Python.

Recovery's verifier (bootable/recovery/verifier.cpp) checks:
  SHA1 of  file[0 : EOF-comment_len-2]  signed RSA PKCS#1 v1.5,
  signature blob = PKCS#7 DER stored in the zip comment.
Layout at EOF:
  u16 comment_len | "signed by SignApk\0" | PKCS#7 DER | u16(len(DER)+6) | 0xffff | u16(comment_len)
"""
import hashlib
import os
import struct
import sys

SHA1_PREFIX = bytes.fromhex("3021300906052b0e03021a05000414")
MAGIC = b"signed by SignApk\x00"


def tlv(b, off):
    tag = b[off]; off += 1
    l = b[off]; off += 1
    if l & 0x80:
        n = l & 0x7f
        l = int.from_bytes(b[off:off + n], "big"); off += n
    return tag, off, l


def children(b, off, end):
    out = []
    while off < end:
        tag, cstart, l = tlv(b, off)
        out.append((tag, cstart, l, off))
        off = cstart + l
    return out


def parse_pk8(path):
    b = open(path, "rb").read()
    tag, o, L = tlv(b, 0)
    ch = children(b, o, o + L)
    priv = b[ch[2][1]:ch[2][1] + ch[2][2]]
    tag, o2, L2 = tlv(priv, 0)
    vals = [int.from_bytes(priv[c[1]:c[1] + c[2]], "big") for c in children(priv, o2, o2 + L2)]
    version, n, e, d = vals[0], vals[1], vals[2], vals[3]
    return n, e, d


def cert_pubkey(pem_path):
    import base64
    txt = open(pem_path, "r", encoding="utf-8").read()
    der = base64.b64decode("".join(txt.split("-----")[2].split()))
    tag, o, L = tlv(der, 0)
    tbs = children(der, o, o + L)[0]
    fields = children(der, tbs[1], tbs[1] + tbs[2])
    spki = [x for x in fields if x[0] == 0x30
            and len(children(der, x[1], x[1] + x[2])) == 2
            and children(der, x[1], x[1] + x[2])[1][0] == 0x03][0]
    c = children(der, spki[1], spki[1] + spki[2])
    bs = der[c[1][1]:c[1][1] + c[1][2]][1:]
    _, o2, l2 = tlv(bs, 0)
    v = children(bs, o2, o2 + l2)
    return (int.from_bytes(bs[v[0][1]:v[0][1] + v[0][2]], "big"),
            int.from_bytes(bs[v[1][1]:v[1][1] + v[1][2]], "big")), der


def rsassa_pkcs1_sha1(digest, n, d):
    k = (n.bit_length() + 7) // 8
    di = SHA1_PREFIX + digest
    em = b"\x00\x01" + b"\xff" * (k - 3 - len(di)) + b"\x00" + di
    return pow(int.from_bytes(em, "big"), d, n).to_bytes(k, "big")


def rsa_verify(digest, sig, n, e):
    k = (n.bit_length() + 7) // 8
    em = pow(int.from_bytes(sig, "big"), e, n).to_bytes(k, "big")
    di = SHA1_PREFIX + digest
    return em == b"\x00\x01" + b"\xff" * (k - 3 - len(di)) + b"\x00" + di


def make_der(template, sig):
    """Patch the 256-byte encryptedDigest inside a known-good PKCS#7 structure."""
    marker = b"\x04\x82\x01\x00"
    pos = template.rfind(marker)
    assert pos >= 0 and len(sig) == 256
    out = bytearray(template)
    out[pos + 4:pos + 4 + 256] = sig
    return bytes(out)


def sign_zip(zip_path, der_template, n, d, verbose=True):
    data = open(zip_path, "rb").read()
    assert data[-2:] == b"\x00\x00", "zip must end with EOCD comment length 0"
    assert data[-22:-18] == b"PK\x05\x06", "EOCD not at end"
    P = len(data) - 2
    digest = hashlib.sha1(data[:P]).digest()
    sig = rsassa_pkcs1_sha1(digest, n, d)
    der = make_der(der_template, sig)
    comment_len = len(MAGIC) + len(der) + 6
    footer = struct.pack("<H", len(der) + 6) + b"\xff\xff" + struct.pack("<H", comment_len)
    out = data[:P] + struct.pack("<H", comment_len) + MAGIC + der + footer
    if verbose:
        print(f"  zip={len(data)} P={P} digest={digest.hex()}")
        print(f"  der={len(der)} comment_len={comment_len} total={len(out)}")
    with open(zip_path, "wb") as f:
        f.write(out)
    return digest


def check_zip(zip_path, n, e):
    """Independent re-verification of a signed package."""
    data = open(zip_path, "rb").read()
    footer = data[-6:]
    comment_len = struct.unpack("<H", footer[4:6])[0]
    sig_start = struct.unpack("<H", footer[0:2])[0]
    assert footer[2:4] == b"\xff\xff"
    P = len(data) - comment_len - 2
    assert struct.unpack("<H", data[P:P + 2])[0] == comment_len
    assert data[P + 2:P + 2 + len(MAGIC)] == MAGIC
    assert data[-sig_start:-6][:2] == b"\x30\x82"
    der = data[-sig_start:-6]
    pos = der.rfind(b"\x04\x82\x01\x00")
    sig = der[pos + 4:pos + 4 + 256]
    P = len(data) - comment_len - 2
    digest = hashlib.sha1(data[:P]).digest()
    return rsa_verify(digest, sig, n, e), sig, digest
