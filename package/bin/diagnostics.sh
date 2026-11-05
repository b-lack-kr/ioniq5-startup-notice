#!/system/bin/sh
SCRIPT_DIR=${0%/*}; [ "$SCRIPT_DIR" != "$0" ] || SCRIPT_DIR=.
BASE=$(cd "$SCRIPT_DIR/.." && pwd) || { echo "cannot locate package directory"; exit 1; }
. "$BASE/bin/common.sh"
report() {
    echo 'NEEV Startup Notice 4.3.2 — read-only diagnostics'
    for PROP in ro.build.product ro.board.platform ro.build.version.release ro.mobis.targetdir ro.mobis.onebindir sys.boot_completed; do
        printf '%s=' "$PROP"; "$GETPROP" "$PROP"
    done
    consent --check
    echo "helper_check_exit=$?"
    echo "display=$(display_state) uptime=$(uptime_seconds)"
    nemesis service status local.hkmc.factory82/apply 2>&1
    if [ -f "$STATE/last_attempt.txt" ]; then cat "$STATE/last_attempt.txt"; fi
    echo '--- monitor log ---'
    cat /data/nemesis/logs/local.hkmc.factory82/apply.log 2>/dev/null
}
OUT=
for ROOT in /storage/usb0 /storage/usb1 /storage/usb2 /mnt/media_rw/usb0 /mnt/media_rw/usb1; do
    [ -d "$ROOT" ] || continue
    if mkdir -p "$ROOT/NEEV-STARTUP-NOTICE" 2>/dev/null; then
        OUT="$ROOT/NEEV-STARTUP-NOTICE/diagnostics.txt"
        break
    fi
done
if [ -n "$OUT" ]; then report > "$OUT" 2>&1; cat "$OUT"; echo "Saved: $OUT"; else report; fi
