#!/system/bin/sh
# Start the home watcher detached in its own session so Magisk's cleanup
# of the module script does not kill it.
MODDIR=${0%/*}
W="$MODDIR/m3x-home-watch.sh"
[ -f "$W" ] || exit 0
setsid sh "$W" >>/data/local/tmp/m3x_home.log 2>&1 < /dev/null &
