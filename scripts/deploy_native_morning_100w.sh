#!/usr/bin/env bash
set -euo pipefail

ROOT="${HA_CONFIG_ROOT:-/config}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$ROOT/.backup_native_morning_100w_$STAMP"
FILES=("configuration.yaml" "automations.yaml" "lovelace/energijos_valdymas.yaml")

cd "$ROOT"

echo "=== Deploy native precise >=100 W morning wake ==="
echo "Root: $ROOT"
echo "Backup: $BACKUP"

if [[ ! -d .git ]]; then
  echo "ERROR: $ROOT is not a git working tree." >&2
  exit 1
fi
if ! command -v ha >/dev/null 2>&1; then
  echo "ERROR: Home Assistant CLI 'ha' not found." >&2
  exit 1
fi

echo "[1/8] Fetching ha-config main"
git fetch origin main

echo "[2/8] Backing up live files"
mkdir -p "$BACKUP/lovelace"
for f in "${FILES[@]}"; do
  if [[ -f "$f" ]]; then
    cp -a "$f" "$BACKUP/$f"
  fi
done

restore() {
  echo "ROLLBACK: restoring live files"
  for f in "${FILES[@]}"; do
    if [[ -f "$BACKUP/$f" ]]; then
      cp -a "$BACKUP/$f" "$f"
    fi
  done
}

echo "[3/8] Installing precise-morning files from origin/main"
for f in "${FILES[@]}"; do
  git show "origin/main:$f" > "$f"
done

echo "[4/8] Checking required markers"
grep -q 'unique_id: inverter_morning_on_time_precise' configuration.yaml
grep -q 'native_ha_morning_100w_v1_20260909' configuration.yaml
grep -q 'at: sensor.inverter_morning_on_time_precise' automations.yaml
grep -q 'precise_morning_reached' automations.yaml
grep -q 'sensor.inverter_morning_on_time_precise' lovelace/energijos_valdymas.yaml

echo "[5/8] Home Assistant config check"
if ! ha core check; then
  restore
  echo "ERROR: HA config validation failed; original files restored." >&2
  exit 2
fi

echo "[6/8] Restarting Home Assistant Core"
ha core restart

echo "[7/8] Waiting for HA API and precise sensor"
ok=0
for i in $(seq 1 24); do
  sleep 5
  if ha api get /api/states/sensor.inverter_morning_on_time_precise        > /tmp/native_morning_precise.json 2>/dev/null; then
    ok=1
    break
  fi
done

if [[ "$ok" != "1" ]]; then
  echo "ERROR: precise sensor did not appear after restart." >&2
  echo "Backup remains at $BACKUP" >&2
  exit 3
fi

echo "[8/8] Live verification"
python3 - <<'PY'
import json
p="/tmp/native_morning_precise.json"
with open(p, encoding="utf-8") as f:
    d=json.load(f)
a=d.get("attributes", {})
print("entity: sensor.inverter_morning_on_time_precise")
print("state:", d.get("state"))
print("local display:", a.get("laikas"))
print("algorithm_version:", a.get("algorithm_version"))
print("calculation_method:", a.get("calculation_method"))
print("source:", a.get("source"))

if a.get("algorithm_version") != "native_ha_morning_100w_v1_20260909":
    raise SystemExit("ERROR: live precise sensor is not using the expected algorithm")
PY

echo
echo "SUCCESS: native precise morning wake is LIVE."
echo "Legacy sensor.inverter_morning_on_time may still show 08:00; it is no longer authoritative."
echo "Backup: $BACKUP"
