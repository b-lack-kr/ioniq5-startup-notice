#!/system/bin/sh
# Cold boot / QuickBoot / screen wake monitoring, adapted from Factory82 v4.2.
# Uses the verified method NAME on this firmware, never a numeric transaction.
SCRIPT_DIR=${0%/*}; [ "$SCRIPT_DIR" != "$0" ] || SCRIPT_DIR=.
BASE=$(cd "$SCRIPT_DIR/.." && pwd) || { echo "cannot locate package directory"; exit 1; }
. "$BASE/bin/common.sh"
target_ok || { log 'refused: wrong vehicle firmware'; exit 20; }
mkdir -p "$STATE" || exit 1
chmod 700 "$STATE" || exit 1
BOOT_ID=$(cat "$BOOT_ID_FILE" 2>/dev/null)
[ -n "$BOOT_ID" ] || { log 'missing kernel boot id'; exit 20; }
LAST_ATTEMPT=-1
LAST_DISPLAY=unknown
LAST_BOOT_PROP=unknown
LAST_UP=0
INITIAL=1
PENDING=
WAIT_STARTED=-1
WAKE_UPTIME=0
log 'NEEV startup notice v4.3.2 started; 1s readiness polling; no fixed startup delay'
[ -x "$SERVICE" ] || { log 'service registry tool missing; no call'; exit 20; }

write_marker() {
    printf '%s %s\n' "$NOW" "$BOOT_ID" > "$SESSION.new.$$" &&
        mv "$SESSION.new.$$" "$SESSION"
}
while :; do
    NOW=$(uptime_seconds) || { log 'cannot read uptime'; exit 20; }
    DISPLAY=$(display_state)
    BOOT_PROP=$("$GETPROP" sys.boot_completed)
    REASON=
    if [ "$INITIAL" = 1 ]; then
        MARK_UP=0; MARK_BOOT=
        if [ -f "$SESSION" ]; then read -r MARK_UP MARK_BOOT < "$SESSION"; fi
        if [ "$MARK_BOOT" = "$BOOT_ID" ]; then
            case "$MARK_UP" in ''|*[!0-9]*) REASON=invalid-marker ;; *) LAST_ATTEMPT=$MARK_UP ;; esac
        else
            REASON=cold-or-service-start
        fi
        INITIAL=0
    elif [ "$DISPLAY" = on ] && [ "$LAST_DISPLAY" = off ]; then
        REASON=display-wake
    elif [ "$BOOT_PROP" = 1 ] && [ "$LAST_BOOT_PROP" = 0 ]; then
        REASON=framework-ready
    elif [ ! -f "$SESSION" ] && [ -z "$PENDING" ]; then
        REASON=quickboot-marker-cleared
    elif [ "$LAST_UP" -gt 0 ] && [ $((NOW - LAST_UP)) -ge 45 ]; then
        REASON=resume-gap
    fi
    # A blocked/pending wake remains pending across boot/service initialization.
    case "$REASON" in
        display-wake|framework-ready)
            if [ -n "$PENDING" ]; then
                PENDING=$REASON; WAIT_STARTED=-1; WAKE_UPTIME=$NOW
            fi ;;
    esac
    if [ -n "$REASON" ] && [ -z "$PENDING" ]; then
        # Real display/framework transitions must not be discarded by the
        # cooldown used only to coalesce ambiguous duplicate wake signals.
        CONFIRMED=0
        case "$REASON" in display-wake|framework-ready) CONFIRMED=1 ;; esac
        if [ "$CONFIRMED" = 0 ] && [ "$LAST_ATTEMPT" -ge 0 ] && [ $((NOW - LAST_ATTEMPT)) -ge 0 ] && [ $((NOW - LAST_ATTEMPT)) -lt 15 ]; then
            write_marker || { log 'cannot save session marker'; exit 1; }
        else
            PENDING=$REASON; WAIT_STARTED=-1; WAKE_UPTIME=$NOW
            log "wake=$PENDING display=$DISPLAY uptime=$NOW"
        fi
    fi
    if [ -n "$PENDING" ] && [ "$DISPLAY" != off ] && [ "$BOOT_PROP" = 1 ]; then
        [ "$WAIT_STARTED" -ge 0 ] || WAIT_STARTED=$NOW
        if [ $((NOW - WAIT_STARTED)) -ge 120 ]; then
            log 'readiness timeout after 120 eligible seconds; waiting for next wake'
            write_marker || exit 1
            PENDING=
        else
            # Cheap readiness probe: do not start a Java VM once for --check
            # and a second VM for --dismiss. The latter validates everything.
            REGISTRY=$("$SERVICE" check com.hkmc.factory 2>&1); RC=$?
            REGISTERED=0
            if [ "$RC" = 0 ]; then
                case "$REGISTRY" in *'com.hkmc.factory: found'*) REGISTERED=1 ;; esac
            fi
            if [ "$REGISTERED" = 1 ]; then
                # No grace sleep: recheck the display, then let Java check boot
                # completion again immediately before invoking the OEM method.
                DISPLAY=$(display_state)
                if [ "$DISPLAY" != off ]; then
                    NOW=$(uptime_seconds) || exit 20
                    # Save before the call: a crash/restart must not repeat an uncertain call.
                    write_marker || { log 'cannot save session marker; no call'; exit 1; }
                    LAST_ATTEMPT=$NOW
                    RESULT=$(consent --dismiss 2>&1); RC=$?
                    log "request=$PENDING exit=$RC $RESULT"
                    {
                        echo "reason=$PENDING"; echo "uptime=$NOW"; echo "boot_id=$BOOT_ID"
                        echo "wake_uptime=$WAKE_UPTIME"
                        echo "wake_to_request_seconds=$((NOW - WAKE_UPTIME))"
                        echo "exit=$RC"; echo "$RESULT"
                        echo 'Visual screen dismissal requires on-vehicle confirmation.'
                    } > "$STATE/last_attempt.txt"
                    case "$RC" in
                        10|11) # Helper guarantees these occur BEFORE the mutating call.
                            # A restart may retry this proven no-call outcome.
                            rm -f "$SESSION" || exit 1
                            LAST_ATTEMPT=-1 ;;
                        20) log 'compatibility refused; no OEM call'; exit 20 ;;
                        *) PENDING= ;; # Includes unknown exceptions: no blind repeat.
                    esac
                else
                    WAIT_STARTED=-1
                fi
            fi
        fi
    else
        # Time spent booting or with the display off is not a readiness failure.
        WAIT_STARTED=-1
    fi
    LAST_DISPLAY=$DISPLAY
    LAST_BOOT_PROP=$BOOT_PROP
    LAST_UP=$(uptime_seconds) || exit 20
    sleep 1
done
