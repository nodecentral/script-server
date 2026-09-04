#!/bin/bash
# Name: disk_usage.sh
# Version: 1.1.0
# Description: Confirms the docker-compose bind mounts (conf/scripts/data/logs)
#              are actually connected, then shows a visual tree + df usage for
#              a path picked from a dropdown populated live by
#              scripts/shared/list_mounts.sh (which always lists /app and its
#              bind-mounted subfolders first, plus whatever real disk mounts
#              df finds). Run standalone (./disk_usage.sh --mount /app/data)
#              or from Script-Server.

set -euo pipefail

DEBUG="${DEBUG:-false}"
log_debug() {
  if [ "$DEBUG" = "true" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEBUG: $*"
  fi
}

mount_point="${PARAM_MOUNT:-/app}"
depth="${PARAM_DEPTH:-2}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mount) mount_point="$2"; shift 2 ;;
    --depth) depth="$2"; shift 2 ;;
    *) shift ;;
  esac
done

log_debug "Resolved mount_point='$mount_point' depth='$depth'"

# Each check looks for a file that only ever arrives via the bind mount (never
# baked into the image), so a pass here means the host folder is genuinely
# connected - not just an empty directory created inside the container.
check_mount() {
  local label="$1" path="$2" marker="$3"
  if [ ! -d "$path" ]; then
    printf '  [MISSING]        %-8s %s (directory does not exist)\n' "$label" "$path"
  elif [ -n "$marker" ] && [ ! -e "$marker" ]; then
    printf '  [NOT CONNECTED] %-8s %s (expected file not found - bind mount likely missing)\n' "$label" "$path"
  else
    printf '  [OK]             %-8s %s\n' "$label" "$path"
  fi
}

echo "== Bind mount check (from docker-compose.yml) =="
check_mount "conf"    "/app/conf"    "/app/conf/runners/hello_world.json"
check_mount "scripts" "/app/scripts" "/app/scripts/hello_world.sh"
check_mount "data"    "/app/data"    "/app/data/.gitkeep"
if [ -d /app/logs ] && [ -w /app/logs ]; then
  printf '  [OK]             %-8s %s\n' "logs" "/app/logs"
else
  printf '  [NOT WRITABLE]   %-8s %s\n' "logs" "/app/logs"
fi
echo

if [ ! -d "$mount_point" ]; then
  echo "Not a directory: $mount_point" >&2
  exit 1
fi

echo "== df -h $mount_point =="
df -h "$mount_point"

echo
echo "== tree -h -L $depth $mount_point =="
if command -v tree >/dev/null 2>&1; then
  tree -h --du -L "$depth" "$mount_point" 2>/dev/null || tree -h -L "$depth" "$mount_point"
else
  log_debug "tree not found, falling back to du"
  du -sh "$mount_point"/* 2>/dev/null | sort -rh | head -n 10 || echo "(nothing there yet)"
fi
