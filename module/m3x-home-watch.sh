#!/system/bin/sh
# Keeps the home activity in sync with the Shanling mode switch.
#   AndroidPureMode=0 (安卓模式) -> Nova
#   AndroidPureMode=1 (纯净模式) -> Shanling Music (factory behaviour)
# com.android.launcher3 is removed, so the ROM's forced default fails;
# we take over and keep retrying until the home really is on screen.
LOG=/data/local/tmp/m3x_home.log
KEY=system.audio.shanling.AndroidPureMode
SET=/system/bin/settings
CMD=/system/bin/cmd
AM=/system/bin/am
LOCK=/data/local/tmp/m3x_home.lock

if [ -d "$LOCK" ]; then
  old=$(cat "$LOCK/pid" 2>/dev/null)
  if [ -n "$old" ] && kill -0 "$old" 2>/dev/null; then exit 0; fi
  rm -rf "$LOCK"
fi
mkdir -p "$LOCK" || exit 0
echo $$ > "$LOCK/pid"

target_for() {
  if [ "$1" = "1" ]; then
    echo com.shanling.MusicApp/.MainActivity
  else
    c=$(cat /data/adb/m3x_android_home 2>/dev/null)
    [ -z "$c" ] && c=com.teslacoilsw.launcher/.NovaLauncher
    # fall back if the configured launcher was uninstalled
    if pm path "${c%%/*}" >/dev/null 2>&1; then
      echo "$c"
    else
      echo com.teslacoilsw.launcher/.NovaLauncher
    fi
  fi
}

apply() {
  T=$(target_for "$1")
  echo "$(date +%H:%M:%S) apply mode=$1 -> $T" >> "$LOG"
  $CMD package set-home-activity "$T" >/dev/null 2>&1
  $AM start -n "$T" >>"$LOG" 2>&1
}

up() {
  pkg=$(target_for "$1"); pkg=${pkg%%/*}
  dumpsys activity activities 2>/dev/null | grep -m1 -E "mResumedActivity|mFocusedActivity" | grep -q "$pkg"
}

# wait until PackageManager answers
i=0
while [ $i -lt 120 ]; do
  if $CMD package path android >/dev/null 2>&1; then break; fi
  sleep 1
  i=$((i+1))
done

last=$($SET get system "$KEY" 2>/dev/null)
[ -z "$last" ] && last=0
apply "$last"

booted=0
n=0
while true; do
  m=$($SET get system "$KEY" 2>/dev/null)
  [ -z "$m" ] && m=0
  if [ "$m" != "$last" ]; then
    sleep 1
    last=$m
    apply "$m"
  fi
  if [ "$booted" = "0" ]; then
    if up "$last"; then
      booted=1
      echo "$(date +%H:%M:%S) home is up" >> "$LOG"
    else
      apply "$last"
      n=$((n+1))
      [ "$n" -ge 40 ] && booted=1
    fi
  fi
  sleep 2
done
