#!/bin/bash
# Name: hello_world.sh
# Version: 1.0.0
# Description: Minimal starter example. Demonstrates the runner/script
#              matched-pair convention, a text parameter, a "list" dropdown
#              with display labels, and the DEBUG toggle convention.
#              Run standalone (./hello_world.sh --name Chris --greeting hi)
#              or from Script-Server.

set -euo pipefail

DEBUG="${DEBUG:-false}"
log_debug() {
  if [ "$DEBUG" = "true" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEBUG: $*"
  fi
}

name="${PARAM_NAME:-World}"
greeting="${PARAM_GREETING:-hello}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) name="$2"; shift 2 ;;
    --greeting) greeting="$2"; shift 2 ;;
    *) shift ;;
  esac
done

log_debug "Resolved name='$name' greeting='$greeting'"

case "$greeting" in
  hi) echo "Hi, $name!" ;;
  hey) echo "Hey, $name!" ;;
  *) echo "Hello, $name!" ;;
esac
