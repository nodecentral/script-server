#!/bin/bash
# Shared helper (not a standalone Script-Server script): prints one path per
# line, for use as a dynamic "list" parameter's values.script. Always lists
# the app's own bind-mount targets first - regardless of whether df reports
# them as distinct mounts on this particular host/storage driver - then
# whatever real disk mounts df finds. Usage: list_mounts.sh

set -euo pipefail

{
  echo "/app"
  echo "/app/conf"
  echo "/app/scripts"
  echo "/app/data"
  echo "/app/logs"
  df -P -x tmpfs -x devtmpfs -x proc -x sysfs -x cgroup -x cgroup2 -x squashfs 2>/dev/null \
    | tail -n +2 \
    | awk '{print $6}'
} | awk '!seen[$0]++'
