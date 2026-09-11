#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${CONFIG_DIR:-/config}"
if [[ ! -d "$CONFIG_DIR/custom_components/solis_cloud_control" && -d "/homeassistant/custom_components/solis_cloud_control" ]]; then
  CONFIG_DIR="/homeassistant"
fi

BASE="$CONFIG_DIR/custom_components/solis_cloud_control"
SN="1033300254190112"

echo "=== EIMO SOLISCLOUD RECOVERY / STABILITY DIAGNOSTIC ==="
echo "Config dir: $CONFIG_DIR"
echo "Inverter SN: $SN"
echo

if [[ ! -d "$BASE" ]]; then
  echo "ERROR: $BASE not found" >&2
  exit 1
fi

echo "[1] Recovery/stability markers"
grep -nF "$SN" "$BASE/inverters/inverter_factory.py" "$BASE/coordinator.py" "$BASE/__init__.py" || true
grep -nF 'tou_v2_mode="43605"' "$BASE/inverters/inverter_factory.py" || true
grep -nF 'self.coordinator.data is None' "$BASE/entity.py" || true
grep -nF '_EIMO_UPDATE_INTERVAL = timedelta(minutes=5)' "$BASE/coordinator.py" || true
grep -nF '_EIMO_REQUEST_REFRESH_COOLDOWN_SECONDS = 30' "$BASE/coordinator.py" || true
grep -nF '_MIN_DEVICE_REQUEST_INTERVAL_SECONDS = 0.75' "$BASE/api/solis_api.py" || true
grep -nF '_CONTROL_SETTLE_SECONDS = 2.5' "$BASE/api/solis_api.py" || true
grep -nF 'non_retryable_response_codes={"B0072"}' "$BASE/api/solis_api.py" || true
grep -nF 'control skipped (already confirmed)' "$BASE/coordinator.py" || true
echo

echo "[2] Python syntax"
python3 -m py_compile \
  "$BASE/__init__.py" \
  "$BASE/api/solis_api.py" \
  "$BASE/coordinator.py" \
  "$BASE/entity.py" \
  "$BASE/inverters/inverter_factory.py" \
  "$BASE/utils/retry_policy.py"
echo "Python syntax: OK"
echo

echo "[3] Home Assistant Core status"
if command -v ha >/dev/null 2>&1; then
  ha core info || true
else
  echo "'ha' CLI not available in this shell."
fi
echo

echo "[4] Recent Solis Cloud Control logs"
LOG_TMP="$(mktemp)"
trap 'rm -f "$LOG_TMP"' EXIT

if command -v ha >/dev/null 2>&1; then
  ha core logs > "$LOG_TMP" 2>&1 || true
elif [[ -f "$CONFIG_DIR/home-assistant.log" ]]; then
  tail -n 10000 "$CONFIG_DIR/home-assistant.log" > "$LOG_TMP"
else
  echo "No Home Assistant log source available."
  exit 0
fi

grep -Ei \
  'solis_cloud_control|SolisCloud control|control skipped|atReadBatch|atRead|inverterDetail|B0072|setup_error|1033300254190112|SolisCloudControlApiError|UpdateFailed|Timeout accessing' \
  "$LOG_TMP" | tail -n 240 || true

echo
if [[ -f "$CONFIG_DIR/scripts/analyze_eimo_cloud_log.py" ]]; then
  echo "[5] Forensic traffic/failure correlation"
  python3 "$CONFIG_DIR/scripts/analyze_eimo_cloud_log.py" "$LOG_TMP" || true
  echo
fi

echo "[6] Interpretation hints"
echo "- Healthy: periodic atReadBatch around 5 min cadence, controls only when values actually change."
echo "- 'control skipped (already confirmed)' is expected and means a redundant cloud write was suppressed."
echo "- B0072 is NOT immediately retried; recovery is left to the next scheduled/confirmation cycle."
echo "- Timeout/B0072 shortly after many distinct control CIDs suggests device-control channel saturation."
echo "- Timeout on inverterDetail for Eimo means the cached-profile Stage-1 code is not active live."
echo "- Import/Syntax error: run scripts/deploy_eimo_solis_stage1.sh rollback."
