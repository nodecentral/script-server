#!/bin/bash
# Name: backup.sh
# Version: 1.0.0
# Description: Backs up conf/ and scripts/ (and optionally data/) into a
#              timestamped tarball under /app/data/backups, offered as a
#              download. Run standalone (./backup.sh) or from
#              Script-Server.

set -euo pipefail

DEBUG="${DEBUG:-false}"
log_debug() {
  if [ "$DEBUG" = "true" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEBUG: $*"
  fi
}

include_data="${PARAM_INCLUDE_DATA:-false}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --include-data) include_data=true; shift ;;
    *) shift ;;
  esac
done

log_debug "include_data=$include_data"

backup_dir="/app/data/backups"
mkdir -p "$backup_dir"

timestamp="$(date '+%Y%m%d_%H%M%S')"
backup_path="$backup_dir/script-server-backup_${timestamp}.tar.gz"

members=(conf scripts)
if [ "$include_data" = "true" ]; then
  members+=(data)
fi

tar -czf "$backup_path" -C /app --exclude='data/backups' "${members[@]}"

size="$(du -h "$backup_path" | cut -f1)"
echo "Backed up: ${members[*]}"
echo "Size: $size"
echo "$backup_path"
