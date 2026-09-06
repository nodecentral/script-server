#!/bin/bash
# Shared helper (not a standalone Script-Server script): used as this
# runner's preload_script - runs automatically when the page opens, before
# any parameters are set or Run is clicked. Purely informational: it
# cannot block the main script from running, so the main script re-checks
# for itself rather than trusting this banner alone. Usage:
# check_jq_preload.sh

if command -v jq >/dev/null 2>&1; then
  echo '<p style="color: #2e7d32;">&#10003; jq is installed - the demo below will use it to pretty-print JSON.</p>'
else
  echo '<p style="color: #c62828;">&#10007; jq is not installed. Run <b>Install Package</b> first and pick jq for the nicest output - the demo below still works without it.</p>'
fi
