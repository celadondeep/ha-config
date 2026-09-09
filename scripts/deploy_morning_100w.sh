#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/config/appdaemon/apps}"
ADDON_SLUG="${APPDAEMON_ADDON_SLUG:-a0d7b954_appdaemon}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$APP_DIR/.backup_morning100w_$STAMP"
FILES=(energy_manager.py energy_manager_eimo.py solar_timing.py)

echo "=== Deploy minute-resolution 100 W morning logic ==="
echo "App dir: $APP_DIR"
echo "AppDaemon: $ADDON_SLUG"

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "ERROR: $APP_DIR is not a git working tree." >&2
  exit 1
fi

cd "$APP_DIR"

echo "[1/7] Fetching celadondeep/Solis main"
git fetch origin main

echo "[2/7] Backing up live files -> $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
for f in "${FILES[@]}"; do
  if [[ -f "$f" ]]; then
    cp -a "$f" "$BACKUP_DIR/$f"
  fi
done

echo "[3/7] Installing all required files"
for f in "${FILES[@]}"; do
  git show "origin/main:$f" > "$f"
done

echo "[4/7] Verifying algorithm markers"
grep -q 'morning_100w_v2_20260909' energy_manager.py
grep -q 'morning_100w_v2_20260909' energy_manager_eimo.py
grep -q 'forecast_threshold_time' solar_timing.py

echo "[5/7] Python compile"
python3 -m py_compile "${FILES[@]}"

echo "[6/7] Restarting AppDaemon"
if command -v ha >/dev/null 2>&1; then
  ha addons restart "$ADDON_SLUG"
else
  echo "ERROR: Home Assistant CLI 'ha' not available." >&2
  echo "Files were installed successfully, but AppDaemon was not restarted." >&2
  exit 2
fi

sleep 20

echo "[7/7] Live sensor verification"
if ha api get /api/states/sensor.inverter_morning_on_time > /tmp/morning100w_state.json 2>/dev/null; then
  python3 - <<'PY'
import json
p="/tmp/morning100w_state.json"
with open(p, encoding="utf-8") as f:
    d=json.load(f)
a=d.get("attributes", {})
print("state:", d.get("state"))
print("laikas:", a.get("laikas"))
print("algorithm_version:", a.get("algorithm_version"))
print("calculation_method:", a.get("calculation_method"))
print("calculated_at:", a.get("calculated_at"))
if a.get("algorithm_version") != "morning_100w_v2_20260909":
    raise SystemExit("ERROR: live sensor still does not expose the new algorithm marker")
PY
else
  echo "WARNING: could not read live sensor through HA CLI."
  echo "Check AppDaemon logs and sensor.inverter_morning_on_time manually."
fi

echo
echo "SUCCESS: minute-resolution 100 W morning logic deployed."
echo "Backup: $BACKUP_DIR"
