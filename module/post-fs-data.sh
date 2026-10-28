#!/system/bin/sh
# Runs before zygote: seed a valid Nova HOME preference.
MODDIR=${0%/*}
sh "$MODDIR/m3x-home-xml.sh" >/dev/null 2>&1
