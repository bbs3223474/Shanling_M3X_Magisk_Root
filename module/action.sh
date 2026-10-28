#!/system/bin/sh
# Magisk action button: toggle the Shanling Android/Pure mode, exactly like
# the quick-settings tile, so the watcher applies the matching launcher.
KEY=system.audio.shanling.AndroidPureMode
cur=$(settings get system "$KEY" 2>/dev/null)
[ -z "$cur" ] && cur=0
if [ "$cur" = "1" ]; then nxt=0; else nxt=1; fi
settings put system "$KEY" "$nxt"
if [ "$nxt" = "1" ]; then
  echo "pure mode (Shanling Music)"
else
  echo "android mode ($(cat /data/adb/m3x_android_home 2>/dev/null || echo com.teslacoilsw.launcher/.NovaLauncher))"
fi
