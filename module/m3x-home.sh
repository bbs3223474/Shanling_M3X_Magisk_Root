#!/system/bin/sh
# m3x-home.sh  -  home switcher
#   m3x-home.sh list                  list activities handling HOME
#   m3x-home.sh set <pkg/activity>    set the "Android mode" launcher (persistent)
#   m3x-home.sh nova | music          switch the current home once
#   m3x-home.sh <pkg/activity>        switch the current home once (any component)
CFG=/data/adb/m3x_android_home
DEF=com.teslacoilsw.launcher/.NovaLauncher
MUSIC=com.shanling.MusicApp/.MainActivity

android_target() {
  c=$(cat "$CFG" 2>/dev/null)
  if [ -n "$c" ]; then echo "$c"; else echo "$DEF"; fi
}

case "$1" in
  list)
    cmd package query-activities -a android.intent.action.MAIN \
        -c android.intent.category.HOME 2>/dev/null \
      | grep -E "name=|packageName=" | sed 's/^[[:space:]]*//'
    exit 0
    ;;
  set)
    [ -z "$2" ] && { echo "usage: $0 set <pkg/activity>"; exit 2; }
    pkg=${2%%/*}
    if ! pm path "$pkg" >/dev/null 2>&1; then
      echo "not installed: $pkg"
      exit 1
    fi
    echo "$2" > "$CFG"
    chmod 644 "$CFG"
    T="$2"
    echo "android-mode launcher = $2"
    ;;
  nova)  T=$DEF ;;
  music) T=$MUSIC ;;
  "")    T=$(android_target) ;;
  */*)   T="$1" ;;
  *)     echo "usage: $0 list | set <pkg/activity> | nova | music | <pkg/activity>"; exit 2 ;;
esac

cmd package set-home-activity "$T" || { echo "set-home-activity failed"; exit 1; }
am start -n "$T" >/dev/null 2>&1
echo "home=$T"
