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
LAST_ATTEMPT=0
LAST_DISPLAY=unknown
LAST_BOOT_PROP=unknown
LAST_UP=0
INITIAL=1
PENDING=
TRIES=0
NEXT_CHECK=0
log 'NEEV startup notice v4.3.1 started; named OEM method; strict boot readiness'

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
    if [ -n "$REASON" ] && [ -z "$PENDING" ]; then
        if [ "$LAST_ATTEMPT" -gt 0 ] && [ $((NOW - LAST_ATTEMPT)) -ge 0 ] && [ $((NOW - LAST_ATTEMPT)) -lt 15 ]; then
            write_marker || { log 'cannot save session marker'; exit 1; }
        else
            PENDING=$REASON; TRIES=0; NEXT_CHECK=0
            log "wake=$PENDING display=$DISPLAY uptime=$NOW"
        fi
    fi
    if [ -n "$PENDING" ] && [ "$DISPLAY" != off ] && [ "$NOW" -ge 15 ] &&
        [ "$NOW" -ge "$NEXT_CHECK" ] && [ "$BOOT_PROP" = 1 ]; then
        CHECK=$(consent --check 2>&1); RC=$?
        if [ "$RC" = 0 ]; then
            sleep 2
            # Recheck display and Java-side boot state immediately before sending.
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
                    echo "exit=$RC"; echo "$RESULT"
                    echo 'Visual screen dismissal requires on-vehicle confirmation.'
                } > "$STATE/last_attempt.txt"
                case "$RC" in
                    10|11) # Helper guarantees these occur BEFORE the mutating call.
                        LAST_ATTEMPT=0; NEXT_CHECK=$((NOW + 15))
                        TRIES=$((TRIES + 1))
                        if [ "$TRIES" -ge 8 ]; then
                            log 'readiness changed repeatedly; waiting for next wake'
                            PENDING=
                        fi ;;
                    *) PENDING= ;; # Includes unknown exceptions: no blind repeat.
                esac
            fi
        elif [ "$RC" = 10 ] || [ "$RC" = 11 ]; then
            TRIES=$((TRIES + 1)); NEXT_CHECK=$((NOW + 15))
            if [ "$TRIES" -ge 8 ]; then
                log "readiness timeout: $CHECK; waiting for next wake"
                # Record this skipped wake to avoid a hot loop on missing marker.
                write_marker || exit 1
                PENDING=
            fi
        else
            log "preflight refused: $CHECK; no call"
            exit "$RC"
        fi
    fi
    LAST_DISPLAY=$DISPLAY
    LAST_BOOT_PROP=$BOOT_PROP
    LAST_UP=$(uptime_seconds) || exit 20
    sleep 3
done
