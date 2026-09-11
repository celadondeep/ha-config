#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="${CONFIG_DIR:-/config}"
if [[ ! -d "$CONFIG_DIR/.git" && -d "/homeassistant/.git" ]]; then
  CONFIG_DIR="/homeassistant"
fi

if [[ ! -d "$CONFIG_DIR/.git" ]]; then
  echo "ERROR: HA config git repository not found in /config or /homeassistant" >&2
  exit 1
fi

# Stage-1 recovery + 2026-09-11 daytime cloud stability layer.
FILES=(
  "custom_components/solis_cloud_control/__init__.py"
  "custom_components/solis_cloud_control/api/solis_api.py"
  "custom_components/solis_cloud_control/coordinator.py"
  "custom_components/solis_cloud_control/entity.py"
  "custom_components/solis_cloud_control/inverters/inverter_factory.py"
  "custom_components/solis_cloud_control/utils/retry_policy.py"
)

ACTION="${1:-apply}"
BACKUP_ROOT="$CONFIG_DIR/.eimo_stage1_backup"

compile_files() {
  local root="$1"
  python3 -m py_compile \
    "$root/custom_components/solis_cloud_control/__init__.py" \
    "$root/custom_components/solis_cloud_control/api/solis_api.py" \
    "$root/custom_components/solis_cloud_control/coordinator.py" \
    "$root/custom_components/solis_cloud_control/entity.py" \
    "$root/custom_components/solis_cloud_control/inverters/inverter_factory.py" \
    "$root/custom_components/solis_cloud_control/utils/retry_policy.py"
}

apply_stage1() {
  local ts backup_dir stage_dir
  ts="$(date +%Y%m%d-%H%M%S)"
  backup_dir="$BACKUP_ROOT/$ts"
  stage_dir="$(mktemp -d)"
  trap 'rm -rf "$stage_dir"' RETURN

  echo "[1/7] Fetching origin/main..."
  git -C "$CONFIG_DIR" fetch origin main

  echo "[2/7] Staging exact Eimo recovery/stability files from origin/main..."
  for rel in "${FILES[@]}"; do
    mkdir -p "$stage_dir/$(dirname "$rel")"
    git -C "$CONFIG_DIR" show "origin/main:$rel" > "$stage_dir/$rel"
  done

  echo "[3/7] Python syntax validation..."
  compile_files "$stage_dir"

  echo "[4/7] Verifying stability markers..."
  grep -q '_EIMO_UPDATE_INTERVAL = timedelta(minutes=5)' "$stage_dir/custom_components/solis_cloud_control/coordinator.py"
  grep -q '_EIMO_REQUEST_REFRESH_COOLDOWN_SECONDS = 30' "$stage_dir/custom_components/solis_cloud_control/coordinator.py"
  grep -q '_MIN_DEVICE_REQUEST_INTERVAL_SECONDS = 0.75' "$stage_dir/custom_components/solis_cloud_control/api/solis_api.py"
  grep -q '_CONTROL_SETTLE_SECONDS = 2.5' "$stage_dir/custom_components/solis_cloud_control/api/solis_api.py"
  grep -q 'non_retryable_response_codes={"B0072"}' "$stage_dir/custom_components/solis_cloud_control/api/solis_api.py"
  grep -q 'control skipped (already confirmed)' "$stage_dir/custom_components/solis_cloud_control/coordinator.py"

  echo "[5/7] Backing up current live files to $backup_dir ..."
  for rel in "${FILES[@]}"; do
    mkdir -p "$backup_dir/$(dirname "$rel")"
    cp -a "$CONFIG_DIR/$rel" "$backup_dir/$rel"
  done
  printf '%s\n' "$ts" > "$BACKUP_ROOT/LATEST"

  echo "[6/7] Installing Eimo recovery/stability files..."
  for rel in "${FILES[@]}"; do
    cp -a "$stage_dir/$rel" "$CONFIG_DIR/$rel"
  done
  find "$CONFIG_DIR/custom_components/solis_cloud_control" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

  echo "[7/7] Verifying installed files..."
  compile_files "$CONFIG_DIR"

  echo "Eimo recovery/stability layer installed successfully."
  echo "Backup: $backup_dir"

  if command -v ha >/dev/null 2>&1; then
    echo "Restarting Home Assistant Core..."
    ha core restart
  else
    echo "WARNING: 'ha' CLI not found. Restart Home Assistant manually before testing." >&2
  fi
}

rollback_stage1() {
  local backup_dir latest
  if [[ -f "$BACKUP_ROOT/LATEST" ]]; then
    latest="$(cat "$BACKUP_ROOT/LATEST")"
  else
    latest="$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort | tail -n1)"
  fi

  if [[ -z "${latest:-}" || ! -d "$BACKUP_ROOT/$latest" ]]; then
    echo "ERROR: no Stage-1 backup found" >&2
    exit 1
  fi

  backup_dir="$BACKUP_ROOT/$latest"
  echo "Restoring backup: $backup_dir"

  for rel in "${FILES[@]}"; do
    if [[ ! -f "$backup_dir/$rel" ]]; then
      echo "ERROR: backup missing $rel" >&2
      exit 1
    fi
    cp -a "$backup_dir/$rel" "$CONFIG_DIR/$rel"
  done

  compile_files "$CONFIG_DIR"

  find "$CONFIG_DIR/custom_components/solis_cloud_control" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

  echo "Rollback completed."
  if command -v ha >/dev/null 2>&1; then
    ha core restart
  fi
}

case "$ACTION" in
  apply)
    apply_stage1
    ;;
  rollback)
    rollback_stage1
    ;;
  *)
    echo "Usage: $0 [apply|rollback]" >&2
    exit 2
    ;;
esac
