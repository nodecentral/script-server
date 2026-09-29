#!/bin/sh
# Container entrypoint: makes a fresh install with EMPTY bind mounts work straight away.
#
# Docker bind mounts don't inherit image content, so /app/conf, /app/conf/runners, /app/scripts
# and /app/data start out empty on a new install - no conf.json/logging.json, no runners, no
# scripts (secrets_store.py, the preload scripts...). The image therefore ships its own copies
# under /app/defaults (a path no mount covers) and this script copies them in before starting the
# app. Two rules, by file ownership:
#
#  * USER content (conf.json, runners, every script that isn't listed in PLATFORM_FILES, data/):
#    FILL-IF-MISSING. A file that already exists is never touched, so edits survive restarts and
#    image upgrades. Corollary: an upgrade won't deliver an updated runner/script to an existing
#    install, and a shipped file you deleted comes back on the next start (a missing file can't
#    be told apart from a never-seeded one).
#  * PLATFORM files (the names listed in /app/defaults/PLATFORM_FILES: scripts/shared/*,
#    scripts/preload/*, conf/logging.json): overwritten per individual file on every start, but
#    only when their content differs from the image's copy, and each one is logged. The
#    containing folder is never deleted or replaced, and files the image doesn't ship (your own
#    scripts/shared/foo.py, an imported repo's preload) are never touched.
#
# Nothing is ever deleted.
#
# Environment (all optional):
#   PUID / PGID              run the app as this uid/gid instead of root, and own everything this
#                            script creates as them (PGID defaults to PUID). Unset = root, the
#                            historical behaviour, which the Network Scanner needs (raw sockets).
#   SEED_DEFAULTS=false      skip the fill-if-missing user-content seeding.
#   PLATFORM_REFRESH=false   skip the per-file platform-file refresh.
#   CHMOD_SCRIPTS=false      skip `chmod -R +x` on /app/scripts (see the note near the end).
#   APP_ROOT / DEFAULTS_DIR  relocate /app and /app/defaults (a test hook, not for normal use).

set -e

APP_ROOT="${APP_ROOT:-/app}"
DEFAULTS="${DEFAULTS_DIR:-$APP_ROOT/defaults}"
MANIFEST="$DEFAULTS/PLATFORM_FILES"

SEEDED=0        # user-content files newly copied in
KEPT=0          # user-content files that already existed (left alone)
INSTALLED=0     # platform files that were missing and have been put in place
UPDATED=0       # platform files overwritten because their content differed from the image's
CURRENT=0       # platform files already identical to the image's copy
FAILED=0        # things we could not do (logged as WARN, never fatal)

log() { printf '[entrypoint] %s\n' "$*"; }
warn() { printf '[entrypoint] WARN: %s\n' "$*" >&2; FAILED=$((FAILED + 1)); }

is_number() {
    case "$1" in
        '' | *[!0-9]*) return 1 ;;
    esac
    return 0
}

# ---------------------------------------------------------------------------------------------
# Who does the app run as?
# ---------------------------------------------------------------------------------------------
CUR_UID="$(id -u)"

if [ "$CUR_UID" -eq 0 ]; then
    RUN_UID="${PUID:-0}"
    RUN_GID="${PGID:-${PUID:-0}}"
    is_number "$RUN_UID" || { echo "[entrypoint] ERROR: PUID must be a number, got '$RUN_UID'" >&2; exit 1; }
    is_number "$RUN_GID" || { echo "[entrypoint] ERROR: PGID must be a number, got '$RUN_GID'" >&2; exit 1; }
else
    # Started as a non-root user (compose `user:`): nothing to chown or drop to; files we create
    # are already owned by whoever we are.
    RUN_UID="$CUR_UID"
    RUN_GID="$(id -g)"
    if [ -n "${PUID:-}" ] || [ -n "${PGID:-}" ]; then
        log "started as uid $CUR_UID, not root - ignoring PUID/PGID"
    fi
fi

# True when files must be re-owned to somebody other than the current user.
NEED_CHOWN=false
if [ "$CUR_UID" -eq 0 ] && { [ "$RUN_UID" -ne 0 ] || [ "$RUN_GID" -ne 0 ]; }; then
    NEED_CHOWN=true
fi

own() {
    if [ "$NEED_CHOWN" = true ]; then
        chown "$RUN_UID:$RUN_GID" "$1" 2>/dev/null || warn "could not chown $1 to $RUN_UID:$RUN_GID"
    fi
}

# mkdir -p for a directory whose parent already exists; owns it only if we created it.
make_dir() {
    [ -d "$1" ] && return 0
    if mkdir -p "$1" 2>/dev/null; then
        own "$1"
        log "created directory $1"
    else
        warn "could not create directory $1 (read-only mount or permissions?)"
        return 1
    fi
}

# Can the app user write to this directory? (root can write anywhere except read-only mounts.)
writable_by_app() {
    if [ "$NEED_CHOWN" = true ]; then
        setpriv --reuid="$RUN_UID" --regid="$RUN_GID" --clear-groups test -w "$1" 2>/dev/null
    else
        [ -w "$1" ]
    fi
}

# ---------------------------------------------------------------------------------------------
# Target folders. Created in order so each mkdir is a single level (and so is owned correctly).
# ---------------------------------------------------------------------------------------------
make_dir "$APP_ROOT/conf" || true
make_dir "$APP_ROOT/conf/runners" || true
make_dir "$APP_ROOT/scripts" || true
make_dir "$APP_ROOT/data" || true
# Not seeded, but the app writes to both (execution logs, temp files) relative to its cwd.
make_dir "$APP_ROOT/logs" || true
make_dir "$APP_ROOT/temp" || true

# ---------------------------------------------------------------------------------------------
# Platform files: overwrite ONLY the individual files the image ships, per file, when different.
# ---------------------------------------------------------------------------------------------

# Where a path from the defaults tree lands. The defaults use the layout {conf,runners,scripts,
# data}; runners live at conf/runners on the target.
target_for() {
    case "$1" in
        runners/*) printf '%s/conf/%s' "$APP_ROOT" "$1" ;;
        conf/* | scripts/* | data/*) printf '%s/%s' "$APP_ROOT" "$1" ;;
        *) return 1 ;;
    esac
}

# A manifest line must be a plain relative path inside the defaults tree.
safe_relpath() {
    case "$1" in
        /* | *..*) return 1 ;;
    esac
    return 0
}

refresh_platform_files() {
    if [ ! -f "$MANIFEST" ]; then
        warn "no platform manifest at $MANIFEST - skipping platform refresh"
        return 0
    fi

    while IFS= read -r rel || [ -n "$rel" ]; do
        case "$rel" in '' | '#'*) continue ;; esac

        if ! safe_relpath "$rel" || ! dst="$(target_for "$rel")"; then
            warn "ignoring unusable manifest entry '$rel'"
            continue
        fi
        src="$DEFAULTS/$rel"
        if [ ! -f "$src" ]; then
            warn "manifest lists $rel but the image doesn't ship it - skipping"
            continue
        fi

        dst_dir="$(dirname "$dst")"
        if [ ! -d "$dst_dir" ]; then
            # A shipped subfolder that doesn't exist yet on the mount (e.g. scripts/shared on a
            # brand-new install): create it, owned by the app user.
            make_dir "$dst_dir" || continue
        fi

        if [ -L "$dst" ] || [ -d "$dst" ]; then
            warn "$dst is a symlink or directory, not a file - leaving it alone"
            continue
        fi

        if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
            CURRENT=$((CURRENT + 1))
            continue
        fi

        verb="updated"
        [ -e "$dst" ] || verb="installed"

        # Copy beside the target and rename over it, so the file is never seen half-written.
        tmp="$dst_dir/.$(basename "$dst").entrypoint.$$"
        if cp -p "$src" "$tmp" 2>/dev/null && own "$tmp" && mv -f "$tmp" "$dst" 2>/dev/null; then
            log "platform file $verb: $rel"
            if [ "$verb" = installed ]; then INSTALLED=$((INSTALLED + 1)); else UPDATED=$((UPDATED + 1)); fi
        else
            rm -f "$tmp" 2>/dev/null || true
            warn "could not update platform file $dst (read-only mount or permissions?)"
        fi
    done < "$MANIFEST"
}

# ---------------------------------------------------------------------------------------------
# User content: fill-if-missing, per file, no clobbering. (Equivalent to `cp -rn`, but done per
# file so each seeded file can be logged and so a future coreutils change to how `cp -n` reports
# a skipped file can't trip `set -e`.)
# ---------------------------------------------------------------------------------------------
seed_tree() {
    src_root="$1"
    dst_root="$2"
    prefix="$3"     # this tree's name in the defaults layout (conf, runners, scripts, data)
    [ -d "$src_root" ] || return 0
    make_dir "$dst_root" || return 0

    list="$(mktemp)"

    # Directories first (find prints a parent before its children), then files.
    (cd "$src_root" && find . -mindepth 1 -type d | sort) > "$list"
    while IFS= read -r rel; do
        [ -n "$rel" ] || continue
        make_dir "$dst_root/${rel#./}" || true
    done < "$list"

    (cd "$src_root" && find . -mindepth 1 -type f | sort) > "$list"
    while IFS= read -r rel; do
        [ -n "$rel" ] || continue
        rel="${rel#./}"
        dst="$dst_root/$rel"
        # Platform files were dealt with by refresh_platform_files above. (With PLATFORM_REFRESH=false
        # they fall through and are treated like any other user content: filled in if missing, so a
        # fresh install still gets them, but never overwritten.)
        if [ "${PLATFORM_REFRESH:-true}" = true ] && [ -f "$MANIFEST" ] && grep -qxF "$prefix/$rel" "$MANIFEST"; then
            continue
        fi
        if [ -e "$dst" ] || [ -L "$dst" ]; then
            KEPT=$((KEPT + 1))
            continue
        fi
        if [ -d "$(dirname "$dst")" ] && cp -p "$src_root/$rel" "$dst" 2>/dev/null; then
            own "$dst"
            log "seeded ${dst#"$APP_ROOT"/}"
            SEEDED=$((SEEDED + 1))
        else
            warn "could not seed $dst (read-only mount or permissions?)"
        fi
    done < "$list"

    rm -f "$list"
}

if [ "${PLATFORM_REFRESH:-true}" = true ]; then
    refresh_platform_files
else
    log "PLATFORM_REFRESH=false - platform files left as they are"
fi

if [ "${SEED_DEFAULTS:-true}" = true ]; then
    seed_tree "$DEFAULTS/conf" "$APP_ROOT/conf" conf
    seed_tree "$DEFAULTS/runners" "$APP_ROOT/conf/runners" runners
    seed_tree "$DEFAULTS/scripts" "$APP_ROOT/scripts" scripts
    seed_tree "$DEFAULTS/data" "$APP_ROOT/data" data
else
    log "SEED_DEFAULTS=false - user content not seeded"
fi

log "summary: seeded $SEEDED new file(s), left $KEPT existing file(s) alone; platform files: $INSTALLED installed, $UPDATED updated, $CURRENT already current"

# ---------------------------------------------------------------------------------------------
# Execute bit on scripts. A ZIP download doesn't preserve it and Script-Server silently greys
# out / fails anything that isn't executable, so this used to be done by docker-compose.yml's
# `entrypoint:` override on every start. That override would bypass this script, so it lives
# here now. Unlike the rest of this script it does touch existing files (mode only).
# ---------------------------------------------------------------------------------------------
if [ "${CHMOD_SCRIPTS:-true}" = true ]; then
    chmod -R +x "$APP_ROOT/scripts" 2>/dev/null || true
fi

# ---------------------------------------------------------------------------------------------
# The app has to be able to write to what it owns. Fix only the top of each folder, and only if
# it isn't already writable - files inside keep their owner (chown -R yourself if you want).
# ---------------------------------------------------------------------------------------------
if [ "$NEED_CHOWN" = true ]; then
    for d in conf conf/runners scripts data logs temp; do
        dir="$APP_ROOT/$d"
        [ -d "$dir" ] || continue
        if ! writable_by_app "$dir"; then
            if chown "$RUN_UID:$RUN_GID" "$dir" 2>/dev/null; then
                log "$dir wasn't writable by $RUN_UID:$RUN_GID - changed its owner (existing files inside unchanged)"
            else
                warn "$dir isn't writable by $RUN_UID:$RUN_GID and couldn't be fixed"
            fi
        fi
    done
    # Anything already inside that the app user can't write is worth a heads-up, not a fix.
    for d in conf scripts data; do
        if [ -n "$(find "$APP_ROOT/$d/" -maxdepth 1 -mindepth 1 ! -user "$RUN_UID" -print -quit 2>/dev/null)" ]; then
            log "note: $APP_ROOT/$d has files not owned by $RUN_UID - run 'chown -R $RUN_UID:$RUN_GID' on the host folder if the app needs to edit them"
        fi
    done
fi

if [ "$NEED_CHOWN" = true ]; then
    log "starting as uid $RUN_UID gid $RUN_GID"
    export HOME=/tmp
    exec setpriv --reuid="$RUN_UID" --regid="$RUN_GID" --clear-groups "$@"
fi

log "starting as uid $CUR_UID"
exec "$@"
