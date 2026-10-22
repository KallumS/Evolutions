#!/bin/sh
# Runs every suite: the helper script's (Lua) and the JSFX's (through ysfx).
# Uses lua if there is one, and falls back to lupa otherwise.
set -e
cd "$(dirname "$0")/.."

if command -v lua5.4 >/dev/null 2>&1; then RUN="lua5.4"
elif command -v lua >/dev/null 2>&1;   then RUN="lua"
else RUN="python3 tools/run_lua.py"
fi

fail=0
LOG=$(mktemp -d)
for suite in tests/test_midi.lua tests/test_helper.lua; do
  printf '%-22s ' "$(basename "$suite")"
  if ! $RUN "$suite"; then fail=1; fi
done

if [ -x tools/build/host ]; then
  python3 tools/enginecheck.py > "$LOG/engine.log" 2>&1 && echo "enginecheck.py         ok  ($(grep -c '^PASS' "$LOG/engine.log") checks)" \
    || { grep '^FAIL' "$LOG/engine.log"; echo "enginecheck.py         FAILED"; fail=1; }
  python3 tools/uicheck.py > "$LOG/ui.log" 2>&1 && echo "uicheck.py             ok  ($(grep -c '^PASS' "$LOG/ui.log") checks)" \
    || { grep '^FAIL' "$LOG/ui.log"; echo "uicheck.py             FAILED"; fail=1; }
else
  echo "(no tools/build/host: run tools/build_host.sh for the JSFX's checks)"
  python3 tools/uicheck.py --static > "$LOG/ui.log" 2>&1 || { grep '^FAIL' "$LOG/ui.log"; fail=1; }
fi

rm -rf "$LOG"
exit $fail
