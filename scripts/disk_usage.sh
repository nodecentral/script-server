#!/bin/bash
# Name: disk_usage.sh
# Version: 1.0.0
# Description: Reports free/used space and the largest top-level items for a
#              mount point, picked from a dropdown populated live by
#              scripts/shared/list_mounts.sh. Run standalone
#              (./disk_usage.sh --mount /app/data) or from Script-Server.

set -euo pipefail

DEBUG="${DEBUG:-false}"
log_debug() {
  if [ "$DEBUG" = "true" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEBUG: $*"
  fi
}

mount_point="${PARAM_MOUNT:-/app/data}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mount) mount_point="$2"; shift 2 ;;
    *) shift ;;
  esac
done

log_debug "Resolved mount_point='$mount_point'"

if [ ! -d "$mount_point" ]; then
  echo "Not a directory: $mount_point" >&2
  exit 1
fi

echo "== df -h $mount_point =="
df -h "$mount_point"

echo
echo "== Largest items directly under $mount_point =="
du -sh "$mount_point"/* 2>/dev/null | sort -rh | head -n 10 || echo "(nothing there yet)"
