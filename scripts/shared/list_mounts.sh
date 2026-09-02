#!/bin/bash
# Shared helper (not a standalone Script-Server script): prints one mounted
# path per line, for use as a dynamic "list" parameter's values.script.
# Excludes pseudo/virtual filesystems that aren't useful to inspect.
# Usage: list_mounts.sh

set -euo pipefail

df -P -x tmpfs -x devtmpfs -x proc -x sysfs -x cgroup -x cgroup2 -x squashfs 2>/dev/null \
  | tail -n +2 \
  | awk '{print $6}' \
  | sort -u
