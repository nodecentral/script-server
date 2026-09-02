#!/bin/bash
# Name: file_info.sh
# Version: 1.0.0
# Description: Reports size, type and checksum for a file picked via
#              Script-Server's native file browser (server_file type) under
#              /app/data. Run standalone (./file_info.sh --file /app/data/x)
#              or from Script-Server.

set -euo pipefail

DEBUG="${DEBUG:-false}"
log_debug() {
  if [ "$DEBUG" = "true" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEBUG: $*"
  fi
}

file_path="${PARAM_FILE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file) file_path="$2"; shift 2 ;;
    *) shift ;;
  esac
done

log_debug "Resolved file_path='$file_path'"

if [ -z "$file_path" ]; then
  echo "No file selected (--file is required)" >&2
  exit 1
fi

if [ ! -f "$file_path" ]; then
  echo "File not found: $file_path" >&2
  exit 1
fi

echo "File:   $file_path"
echo "Size:   $(du -h "$file_path" | cut -f1)"
echo "Type:   $(file -b "$file_path")"
echo "SHA256: $(sha256sum "$file_path" | cut -d' ' -f1)"
