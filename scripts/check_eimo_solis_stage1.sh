#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${CONFIG_DIR:-/config}"
if [[ ! -d "$CONFIG_DIR/custom_components/solis_cloud_control" && -d "/homeassistant/custom_components/solis_cloud_control" ]]; then
  CONFIG_DIR="/homeassistant"
fi

BASE="$CONFIG_DIR/custom_components/solis_cloud_control"
SN="1033300254190112"

echo "=== EIMO SOLISCLOUD STAGE-1 DIAGNOSTIC ==="
echo "Config dir: $CONFIG_DIR"
echo "Inverter SN: $SN"
echo

if [[ ! -d "$BASE" ]]; then
  echo "ERROR: $BASE not found" >&2
  exit 1
fi

echo "[1] Stage-1 markers"
grep -nF "$SN" "$BASE/inverters/inverter_factory.py" "$BASE/coordinator.py" "$BASE/__init__.py" || true
grep -nF 'tou_v2_mode="43605"' "$BASE/inverters/inverter_factory.py" || true
grep -nF 'self.coordinator.data is None' "$BASE/entity.py" || true
echo

echo "[2] Python syntax"
python3 -m py_compile   "$BASE/__init__.py"   "$BASE/coordinator.py"   "$BASE/entity.py"   "$BASE/inverters/inverter_factory.py"
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
  tail -n 5000 "$CONFIG_DIR/home-assistant.log" > "$LOG_TMP"
else
  echo "No Home Assistant log source available."
  exit 0
fi

grep -Ei   'solis_cloud_control|atReadBatch|atRead|inverterDetail|B0072|setup_error|1033300254190112|SolisCloudControlApiError|UpdateFailed'   "$LOG_TMP" | tail -n 160 || true

echo
echo "[5] Interpretation hints"
echo "- SUCCESS target: Eimo setup loads and /v2/api/atReadBatch returns usable data."
echo "- B0072: SolisCloud reports device offline; keep recovery polling active."
echo "- Timeout on atReadBatch: direct path is still cloud-unreachable; do not blame discovery."
echo "- Timeout on inverterDetail for Eimo: Stage-1 code is not active in the live HA instance."
echo "- Import/Syntax error: run scripts/deploy_eimo_solis_stage1.sh rollback."
