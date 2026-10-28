import os, sys, zipfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import otasign

SRC = r"D:\Desktop\M3X_OTA_V1.75_20231027"
UPDATE_BINARY = os.path.join(SRC, r"META-INF\com\google\android\update-binary")
OTACERT = os.path.join(SRC, r"META-INF\com\android\otacert")
PK8 = r"D:\Desktop\m3x_root\keys\testkey.pk8"
TEMPLATE = r"D:\Desktop\m3x_root\keys\pkcs7_template.der"
OUTDIR = r"D:\Desktop\m3x_root\out"

METADATA = """ota-required-cache=0
ota-type=BLOCK
post-build=Android/msm8937_64/msm8937_64:7.1.1/NMF26F/ShanLi10241856:user/release-keys
post-timestamp={ts}
pre-device=Shanling_M3X
"""


def build(out_zip, boot_img, script_text, ts=None):
    ts = ts or int(time.time())
    os.makedirs(OUTDIR, exist_ok=True)
    tmp = os.path.join(OUTDIR, os.path.basename(out_zip))
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("META-INF/com/google/android/update-binary", open(UPDATE_BINARY, "rb").read())
        z.writestr("META-INF/com/google/android/updater-script", script_text.encode())
        if boot_img:
            z.writestr("boot.img", open(boot_img, "rb").read())
        z.writestr("META-INF/com/android/metadata", METADATA.format(ts=ts).encode())
        z.writestr("META-INF/com/android/otacert", open(OTACERT, "rb").read())
    n, e, d = otasign.parse_pk8(PK8)
    tpl = open(TEMPLATE, "rb").read()
    otasign.sign_zip(tmp, tpl, n, d)
    ok, sig, dig = otasign.check_zip(tmp, n, e)
    print(f"[{os.path.basename(tmp)}] size={os.path.getsize(tmp)} sig_ok={ok} sha1={dig.hex()}")
    return tmp, ok


if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)

    script_magisk = """getprop("ro.product.device") == "Shanling_M3X" || abort("E3004: wrong device");
ui_print("M3X-ROOT: writing magisk-patched boot image");
show_progress(0.300000, 3);
package_extract_file("boot.img", "/dev/block/bootdevice/by-name/boot");
show_progress(1.000000, 2);
ui_print("M3X-ROOT: boot partition updated, rebooting is safe");
"""

    script_stock = """getprop("ro.product.device") == "Shanling_M3X" || abort("E3004: wrong device");
ui_print("M3X-ROOT: restoring STOCK boot image");
show_progress(0.300000, 3);
package_extract_file("boot.img", "/dev/block/bootdevice/by-name/boot");
show_progress(1.000000, 2);
ui_print("M3X-ROOT: stock boot restored");
"""

    script_probe = """getprop("ro.product.device") == "Shanling_M3X" || abort("E3004: wrong device");
ui_print("M3X-ROOT: signature probe OK, nothing was written");
"""

    build("m3x_magisk_boot.zip", r"D:\Desktop\m3x_root\magisk_patched.img", script_magisk)
    build("m3x_stock_boot.zip", r"D:\Desktop\m3x_root\boot_stock.img", script_stock)
    build("m3x_probe.zip", None, script_probe)
