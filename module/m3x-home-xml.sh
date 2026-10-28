#!/system/bin/sh
# Seeds a valid HOME preference into package-restrictions.xml before
# PackageManagerService starts. The launcher comes from
# /data/adb/m3x_android_home (default Nova), so any third-party launcher works.
# HOME preferred activities all carry match="100000", which lets us drop every
# existing one generically instead of hardcoding package names.
F=/data/system/users/0/package-restrictions.xml
T=/data/local/tmp/m3x_item.xml
ANDROID=$(cat /data/adb/m3x_android_home 2>/dev/null)
[ -z "$ANDROID" ] && ANDROID=com.teslacoilsw.launcher/.NovaLauncher
[ -f "$F" ] || exit 0
grep -q '</package-restrictions>' "$F" || exit 0

cat > "$T" <<EOF
        <item name="$ANDROID" match="100000" always="true" set="3">
            <set name="com.shanling.MusicApp/.MainActivity" />
            <set name="$ANDROID" />
            <set name="com.android.settings/.FallbackHome" />
            <filter>
                <action name="android.intent.action.MAIN" />
                <cat name="android.intent.category.HOME" />
                <cat name="android.intent.category.DEFAULT" />
            </filter>
        </item>
EOF

sed -e '/<item name="[^"]*" match="100000"/,/<\/item>/d' \
    -e "/<preferred-activities>/r $T" "$F" > "$F.new"

if [ -s "$F.new" ] && grep -q '</package-restrictions>' "$F.new"; then
  chown system:system "$F.new" 2>/dev/null
  chmod 600 "$F.new" 2>/dev/null
  mv "$F.new" "$F"
  chown system:system "$F" 2>/dev/null
  chmod 600 "$F" 2>/dev/null
else
  rm -f "$F.new"
fi
