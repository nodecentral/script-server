#!/bin/bash
# Name: import_from_gitea.sh
# Version: 1.0.0
# Description: Clones a Gitea repo (expected to use the same scripts/ +
#              conf/runners/ layout as this instance) and copies its
#              scripts/ and conf/runners/ contents into /app/scripts and
#              /app/conf/runners. Dry-run by default - pass --apply to
#              actually write files. Run standalone
#              (./import_from_gitea.sh --url http://gitea.local:3000
#              --owner me --repo my-scripts --apply) or from Script-Server.

set -euo pipefail

DEBUG="${DEBUG:-false}"
log_debug() {
  if [ "$DEBUG" = "true" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] DEBUG: $*"
  fi
}

gitea_url="${PARAM_GITEA_URL:-}"
owner="${PARAM_OWNER:-}"
repo="${PARAM_REPO:-}"
branch="${PARAM_BRANCH:-main}"
apply=false
token="${GITEA_TOKEN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) gitea_url="$2"; shift 2 ;;
    --owner) owner="$2"; shift 2 ;;
    --repo) repo="$2"; shift 2 ;;
    --branch) branch="$2"; shift 2 ;;
    --apply) apply=true; shift ;;
    *) shift ;;
  esac
done

gitea_url="${gitea_url%/}"

if [ -z "$gitea_url" ] || [ -z "$owner" ] || [ -z "$repo" ]; then
  echo "Missing required parameter(s): --url, --owner and --repo are all required" >&2
  exit 1
fi

log_debug "gitea_url=$gitea_url owner=$owner repo=$repo branch=$branch apply=$apply"

if $apply; then
  echo "Mode: APPLY (files will be written)"
else
  echo "Mode: DRY RUN (no files will be written - pass --apply to actually import)"
fi
echo

clone_dir="$(mktemp -d)"
cleanup() { rm -rf "$clone_dir"; }
trap cleanup EXIT

if [ -n "$token" ]; then
  scheme="${gitea_url%%://*}"
  rest="${gitea_url#*://}"
  clone_url="${scheme}://${token}@${rest}/${owner}/${repo}.git"
else
  clone_url="${gitea_url}/${owner}/${repo}.git"
fi

echo "Cloning ${gitea_url}/${owner}/${repo}.git (branch: $branch) ..."
if ! git clone --depth 1 --branch "$branch" --single-branch "$clone_url" "$clone_dir" 2>&1; then
  echo "Clone failed - check the URL, branch, credentials, and that this Gitea instance is reachable from the container." >&2
  exit 1
fi
echo

sync_dir() {
  local src="$1" dest="$2" label="$3"
  if [ ! -d "$src" ]; then
    echo "$label: nothing to import (no $src in repo)"
    echo
    return
  fi

  local files
  files="$(find "$src" -type f || true)"

  if [ -z "$files" ]; then
    echo "$label: 0 files found"
    echo
    return
  fi

  echo "$label: files found:"
  echo "$files" | sed "s#^$src/##" | sed 's/^/    /'

  if $apply; then
    mkdir -p "$dest"
    cp -a "$src"/. "$dest"/
    echo "  -> copied to $dest"
  fi
  echo
}

sync_dir "$clone_dir/scripts" "/app/scripts" "scripts/"
sync_dir "$clone_dir/conf/runners" "/app/conf/runners" "conf/runners/"

if $apply; then
  echo "Fixing execute permissions on imported scripts..."
  if ! find /app/scripts -type f \( -name '*.sh' -o -name '*.py' -o -name '*.lua' \) -exec chmod +x {} + 2>/dev/null; then
    echo "  WARNING: chmod failed. Some hosts (certain QNAP setups) reject chmod" >&2
    echo "  across a bind mount with 'Bad address'. If your scripts show as" >&2
    echo "  greyed out, run this on the NAS shell directly (outside Docker):" >&2
    echo "    chmod +x scripts/*.sh scripts/**/*.sh" >&2
  fi
  echo
  echo "Done. Refresh the browser to see new/updated scripts - Script-Server"
  echo "rereads conf/runners on each page load, no restart needed."
else
  echo "Dry run complete - re-run with --apply to actually copy these files."
fi
