#!/usr/bin/env bash
set -euo pipefail

ADDON_SLUG="${APPDAEMON_ADDON_SLUG:-a0d7b954_appdaemon}"

echo "=== CONTROL PLAN RECOVERY ==="
echo "AppDaemon add-on: $ADDON_SLUG"
echo

if ! command -v ha >/dev/null 2>&1; then
  echo "ERROR: Home Assistant CLI 'ha' not found." >&2
  exit 1
fi

echo "[1/5] Current AppDaemon status"
ha addons info "$ADDON_SLUG" || true
echo

echo "[2/5] Restarting AppDaemon only"
ha addons restart "$ADDON_SLUG"
echo

echo "[3/5] Waiting for planners to initialize"
sleep 20
ha addons info "$ADDON_SLUG" || true
echo

echo "[4/5] Recent AppDaemon logs"
ha addons logs "$ADDON_SLUG" 2>&1 | tail -n 180 || true
echo

echo "[5/5] Planner/forecast state check"

TOKEN="${SUPERVISOR_TOKEN:-${HASSIO_TOKEN:-}}"
API_BASE="http://supervisor/core/api"

print_state() {
  local entity="$1"
  if [[ -z "$TOKEN" ]]; then
    echo "$entity: API token unavailable in this shell"
    return
  fi

  python3 - "$API_BASE" "$TOKEN" "$entity" <<'PY'
import json, sys, urllib.request
base, token, entity = sys.argv[1:]
req = urllib.request.Request(
    f"{base}/states/{entity}",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.load(r)
    attrs = d.get("attributes", {})
    heartbeat = attrs.get("planner_heartbeat", "-")
    interval = attrs.get("planner_interval_s", "-")
    source = attrs.get("saltinis", attrs.get("source", "-"))
    print(
        f"{entity}: state={d.get('state')} "
        f"last_changed={d.get('last_changed')} "
        f"last_updated={d.get('last_updated')} "
        f"last_reported={d.get('last_reported', '-')} "
        f"planner_heartbeat={heartbeat} planner_interval_s={interval} source={source}"
    )
except Exception as exc:
    print(f"{entity}: ERROR {exc}")
PY
}

for entity in   sensor.energy_manager_status   sensor.energy_manager_decision   sensor.energy_manager_target_soc   sensor.energy_manager_room_shortfall   sensor.energy_manager_eimo_status   sensor.energy_manager_eimo_decision   sensor.energy_manager_eimo_target_soc   sensor.energy_manager_eimo_room_shortfall   sensor.solcast_pv_forecast_forecast_remaining_today   sensor.solcast_pv_forecast_forecast_tomorrow
do
  print_state "$entity"
done

echo
echo "Interpretation:"
echo "- Both energy_manager planners should publish again shortly after AppDaemon restart."
echo "- If both planners remain stale but Solcast is healthy, inspect the new control-core plan freshness/TTL gate."
echo "- If Solcast is unavailable/stale for both, HOLD is a shared forecast-data problem."
echo "- If only Eimo is stale, inspect SolisCloud/Eimo telemetry separately."
