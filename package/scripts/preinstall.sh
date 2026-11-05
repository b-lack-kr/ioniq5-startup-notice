#!/system/bin/sh
SCRIPT_DIR=${0%/*}; [ "$SCRIPT_DIR" != "$0" ] || SCRIPT_DIR=.
BASE=$(cd "$SCRIPT_DIR/.." && pwd) || { echo "cannot locate package directory"; exit 1; }
. "$BASE/bin/common.sh"
target_ok || { log 'refused: requires NEEV.KOR.0000.V039.001.260902 / tcc803x / Android 4.4.2'; exit 20; }
[ -r "$BASE/lib/neev-consent.jar" ] || exit 20
# Read-only check: do not dismiss a screen from an install hook.
consent --check
RC=$?
# NEMESIS removes the previous package before this hook. A late Binder service
# must not turn a valid firmware/API update into a missing installation.
# Exit 11 is emitted only after class/signature/service-name validation succeeds.
if [ "$RC" = 11 ]; then
    log 'factory service not registered yet; monitor will wait and recheck'
    exit 0
fi
exit "$RC"
