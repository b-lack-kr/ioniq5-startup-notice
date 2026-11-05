#!/system/bin/sh
# NEEV 260902 local adaptation. See LICENSE and NOTICE.txt.
export PATH=/sbin:/vendor/bin:/system/sbin:/system/bin:/system/xbin:/data/nemesis/bin:$PATH
export LD_LIBRARY_PATH=/vendor/lib:/system/lib
export ANDROID_ROOT=/system ANDROID_DATA=/data
umask 077
GETPROP=${NEEV_GETPROP:-/system/bin/getprop}
APP_PROCESS=${NEEV_APP_PROCESS:-/system/bin/app_process}
DUMPSYS=${NEEV_DUMPSYS:-/system/bin/dumpsys}
SERVICE=${NEEV_SERVICE:-/system/bin/service}
STATE=${NEEV_STATE:-/data/nemesis/state/local.hkmc.factory82}
SESSION=${NEEV_SESSION:-/data/local/tmp/neev-consent.session}
UPTIME_FILE=${NEEV_UPTIME_FILE:-/proc/uptime}
BOOT_ID_FILE=${NEEV_BOOT_ID_FILE:-/proc/sys/kernel/random/boot_id}
FB_BLANK=${NEEV_FB_BLANK:-/sys/class/graphics/fb0/blank}
log() { echo "neev-consent: $*"; }
target_ok() {
    [ "$("$GETPROP" ro.build.product)" = NEEV.KOR.0000.V039.001.260902 ] &&
    [ "$("$GETPROP" ro.board.platform)" = tcc803x ] &&
    [ "$("$GETPROP" ro.build.version.release)" = 4.4.2 ]
}
consent() {
    CLASSPATH="$BASE/lib/neev-consent.jar:/system/framework/automotive.jar" \
        "$APP_PROCESS" /system/bin NeevConsent "$@"
}
uptime_seconds() {
    UP=0
    read -r UP UNUSED < "$UPTIME_FILE" || return 1
    UP=${UP%%.*}
    case "$UP" in ''|*[!0-9]*) return 1 ;; esac
    echo "$UP"
}
# Display policy decoding adapted from upstream Factory82 v4.2.
display_state() {
    POWER=$("$DUMPSYS" power 2>/dev/null)
    case "$POWER" in
        *'mDisplayPowerRequest=policy=OFF'*|*'mDisplayPowerRequest=policy=0'*) echo off; return ;;
        *'mDisplayPowerRequest=policy=BRIGHT'*|*'mDisplayPowerRequest=policy=DIM'*) echo on; return ;;
        *'mScreenOn=false'*|*'mInteractive=false'*|*'mWakefulness=Asleep'*|*'mWakefulness=Dozing'*) echo off; return ;;
        *'mScreenOn=true'*|*'mInteractive=true'*|*'mWakefulness=Awake'*) echo on; return ;;
    esac
    if [ -r "$FB_BLANK" ]; then
        BLANK=$(cat "$FB_BLANK" 2>/dev/null)
        case "$BLANK" in 0) echo on; return ;; 1|2|3|4) echo off; return ;; esac
    fi
    echo unknown
}
