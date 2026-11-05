#!/system/bin/sh
# Logged installer: preflight completes before NEMESIS can replace an old package.
if [ "${NEEV_TEST_MODE:-0}" != 1 ]; then
    export PATH=/system/bin:/system/xbin:/data/nemesis/bin:/sbin:/vendor/bin
fi
export LD_LIBRARY_PATH=/vendor/lib:/system/lib
export ANDROID_ROOT=/system ANDROID_DATA=/data
umask 077
USB=${0%/*}; [ "$USB" != "$0" ] || USB=$PWD
if [ "${NEEV_TEST_MODE:-0}" = 1 ]; then USB=$NEEV_INSTALL_USB; fi
USB=$(cd "$USB" && pwd) || exit 2
PACKAGE=local.hkmc.factory82-4.3.1-neev.zip
OUT="$USB/NEEV_STARTUP_NOTICE_RESULT_$(date +%Y%m%d_%H%M%S)_$$"
mkdir "$OUT" || exit 2
echo "$OUT" > "$USB/NEEV_STARTUP_NOTICE_LAST_RESULT.txt" || exit 2
exec > "$OUT/INSTALL.log" 2>&1
status() { echo "$*"; echo "$*" > "$OUT/STATUS.txt"; sync; }
collect_logs() {
    for F in /data/nemesis/nemesis.log /data/nemesis/logs/usb-session.log /data/nemesis/logs/local.hkmc.factory82/apply.log; do
        [ -f "$F" ] || continue
        cp "$F" "$OUT/${F##*/}" 2>/dev/null || :
    done
}
notice() {
    am broadcast -a com.hkmc.intent.action.TOAST -e com.hkmc.intent.extra.TOAST_MESSAGE "$1" \
        --ez com.hkmc.intent.extra.TOAST_POPUPSHOWING true >/dev/null 2>&1 || :
}
fail() {
    status "$1"
    collect_logs
    notice '시작 안내창 설치 중단: USB의 INSTALL.log를 확인하세요'
    exit 1
}
status PREFLIGHT
echo 'NEEV startup notice installer 4.3.1'
for PROP in ro.build.product ro.board.platform ro.build.version.release ro.mobis.targetdir ro.mobis.onebindir sys.boot_completed; do
    printf '%s=' "$PROP"; getprop "$PROP"
done
[ "$(getprop ro.build.product)" = NEEV.KOR.0000.V039.001.260902 ] || fail WRONG_PRODUCT
[ "$(getprop ro.board.platform)" = tcc803x ] || fail WRONG_PLATFORM
[ "$(getprop ro.build.version.release)" = 4.4.2 ] || fail WRONG_ANDROID
case "$(id)" in 'uid=0('*|'uid=0 '*|'uid=0') ;; *) fail ROOT_REQUIRED ;; esac
command -v nemesis >/dev/null 2>&1 || fail NEMESIS_MISSING
nemesis version
[ -f "$USB/NEEV_STARTUP_NOTICE/payload.md5" ] || fail PAYLOAD_MANIFEST_MISSING
PACKAGE_SEEN=0; HELPER_SEEN=0
while read -r EXPECTED REL; do
    case "$REL" in
        "$PACKAGE") [ "$PACKAGE_SEEN" = 0 ] || fail DUPLICATE_MANIFEST; PACKAGE_SEEN=1 ;;
        NEEV_STARTUP_NOTICE/neev-consent.jar) [ "$HELPER_SEEN" = 0 ] || fail DUPLICATE_MANIFEST; HELPER_SEEN=1 ;;
        *) fail INVALID_MANIFEST ;;
    esac
    SUM=$(md5 "$USB/$REL") || fail PAYLOAD_READ_FAILED
    [ "${SUM%% *}" = "$EXPECTED" ] || fail PAYLOAD_HASH_MISMATCH
done < "$USB/NEEV_STARTUP_NOTICE/payload.md5"
[ "$PACKAGE_SEEN$HELPER_SEEN" = 11 ] || fail INCOMPLETE_MANIFEST
STAGE=/data/nemesis/tmp/neev-startup-notice-431-$$
if [ "${NEEV_TEST_MODE:-0}" = 1 ]; then STAGE=$NEEV_INSTALL_STAGE; fi
[ ! -e "$STAGE" ] && [ ! -L "$STAGE" ] || fail STAGING_PATH_EXISTS
mkdir -p "$STAGE" || fail STAGING_CREATE_FAILED
trap 'rm -f "$STAGE/neev-consent.jar"; rmdir "$STAGE" 2>/dev/null' EXIT
cp "$USB/NEEV_STARTUP_NOTICE/neev-consent.jar" "$STAGE/neev-consent.jar" || fail HELPER_COPY_FAILED
CLASSPATH="$STAGE/neev-consent.jar:/system/framework/automotive.jar" \
    app_process /system/bin NeevConsent --check > "$OUT/PREFLIGHT.txt" 2>&1
RC=$?
cat "$OUT/PREFLIGHT.txt"
case "$RC" in 0|11) ;; *) fail "PREFLIGHT_FAILED_RC_$RC" ;; esac
status INSTALLING
nemesis install --update "$USB/$PACKAGE"
RC=$?
echo "nemesis_install_exit=$RC"
collect_logs
[ "$RC" = 0 ] || fail "INSTALL_FAILED_RC_$RC"
nemesis service status local.hkmc.factory82/apply > "$OUT/SERVICE.txt" 2>&1 || :
status INSTALLED_TEST_NEXT_START
notice '시작 안내창 4.3.1 설치 완료: 다음 시동에서 확인하세요'
exit 0
