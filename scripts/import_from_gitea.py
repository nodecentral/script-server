#!/usr/bin/env python3
# Name: import_from_gitea.py
# Version: 5.1.1
# Description: Clones a Gitea repo (expected to have its own top-level
#              scripts/ and runners/ folders) and mirrors scripts/ into
#              /app/scripts and runners/ into /app/conf/runners: existing
#              files are overwritten with the latest version, and files
#              that were imported from this same source before but no
#              longer exist upstream are removed - so a rename/delete in
#              Gitea is reflected here too. Only files this exact source
#              previously placed are ever candidates for removal (tracked
#              in /app/data/gitea_import_state.json) - nothing else under
#              scripts/ or conf/runners/ is touched. Dry-run by default -
#              pass --apply to actually write files. Run standalone
#              (./import_from_gitea.py --repo someowner/somerepo --apply)
#              or from Script-Server.
#
#              No "Gitea URL" field either: both the URL and its token(s)
#              live in the Secrets Store's "gitea" product (key URL, plus
#              one or more token keys), set via Secrets Manager - see
#              gitea_client.resolve_gitea_url()/resolve_gitea_token(). An
#              explicit manually entered "token" field still overrides the
#              stored token for a one-off run; if more than one token is
#              stored the "Gitea Token" dropdown must pick which one.
#
#              No separate "owner" field either: the Repo dropdown lists
#              live "owner/repo" values straight from Gitea's own
#              /user/repos API for whichever token is in play, so the owner
#              never needs typing - see gitea_client.list_user_repos().
#              Manual Repo (also owner/repo) is the fallback for a public
#              repo with no token, where the dropdown can't be populated
#              live.
#              5.1.0: the report lists every file with its installed and
#              Gitea version (runner "_version" / script "# Version:" header),
#              the time of the last commit that changed it, and a status
#              (NEW / UPDATE / CHANGED / SAME / OLDER / REMOVED) - OLDER flags
#              a stale branch before you apply it. Each import records the
#              commit, its time and how to repeat the import in the state
#              file, which is what the script header's one-tap "update from
#              Gitea" button (admins only) re-runs.

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from gitea_client import GiteaApiError, list_gitea_tokens, resolve_gitea_token, resolve_gitea_url  # noqa: E402
from secrets_store import AUTO_SENTINEL  # noqa: E402

try:
    from gitea_client import format_time  # noqa: E402
except ImportError:
    # An older scripts/shared/gitea_client.py (pre-v2.1) - e.g. a v1 instance sharing this
    # scripts folder put its own copy back on start. Everything still works, times included.
    def format_time(value):
        if not value:
            return ''
        try:
            parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone()
        except ValueError:
            return ''
        return parsed.strftime('%d %b %Y %H:%M')

STATE_PATH = '/app/data/gitea_import_state.json'

DEBUG = os.environ.get('DEBUG', 'false') == 'true'


def log_debug(msg):
    if DEBUG:
        print(f'DEBUG: {msg}', flush=True)


def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp_path = STATE_PATH + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp_path, STATE_PATH)


def list_files(root):
    if not os.path.isdir(root):
        return []
    result = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            result.append(os.path.relpath(full, root))
    return sorted(result)


VERSION_PATTERN = re.compile(r'Version:\s*v?([0-9]+(?:\.[0-9]+)*)')

STATUS_ORDER = ['OLDER', 'NEW', 'UPDATE', 'CHANGED', 'REMOVED', 'SAME']
SUMMARY_LABELS = {'OLDER': 'older', 'NEW': 'new', 'UPDATE': 'updated', 'CHANGED': 'changed',
                  'REMOVED': 'removed', 'SAME': 'unchanged'}


def read_version(path):
    """A runner's "_version", or a script's "Version: x.y.z" header line - None if neither."""
    if not os.path.isfile(path):
        return None
    try:
        if path.endswith('.json'):
            with open(path, encoding='utf-8') as f:
                value = json.load(f).get('_version')
            return str(value) if value else None
        with open(path, encoding='utf-8', errors='replace') as f:
            head = f.read(4096)
    except (OSError, ValueError, AttributeError):
        return None
    match = VERSION_PATTERN.search(head)
    return match.group(1) if match else None


def version_tuple(version):
    try:
        return tuple(int(part) for part in version.split('.'))
    except (AttributeError, ValueError):
        return None


def file_status(src_path, dest_path, gitea_version, installed_version):
    if not os.path.exists(dest_path):
        return 'NEW'
    if filecmp.cmp(src_path, dest_path, shallow=False):
        return 'SAME'
    new, old = version_tuple(gitea_version), version_tuple(installed_version)
    if new and old:
        if new > old:
            return 'UPDATE'
        if new < old:
            return 'OLDER'
    return 'CHANGED'


def last_commit_time(clone_dir, repo_relpath):
    result = subprocess.run(['git', '-C', clone_dir, 'log', '-1', '--format=%cI', '--', repo_relpath],
                            capture_output=True, text=True)
    return format_time(result.stdout.strip()) if result.returncode == 0 else ''


def sync_category(clone_dir, category, dest_root, label, apply_changes, previous_files):
    """Reports (and with apply_changes, mirrors) one top-level folder of the clone. Returns
    (current_files, status_counts)."""
    src_root = os.path.join(clone_dir, category)
    current_files = list_files(src_root)
    stale_files = sorted(set(previous_files) - set(current_files))
    counts = {}

    if not current_files and not stale_files:
        print(f'{label}: nothing found upstream')
        print()
        return current_files, counts

    rows = []
    for rel in current_files:
        src_path = os.path.join(src_root, rel)
        dest_path = os.path.join(dest_root, rel)
        gitea_version = read_version(src_path)
        installed_version = read_version(dest_path)
        status = file_status(src_path, dest_path, gitea_version, installed_version)
        rows.append((status, rel, installed_version, gitea_version,
                     last_commit_time(clone_dir, os.path.join(category, rel))))
    for rel in stale_files:
        rows.append(('REMOVED', rel, read_version(os.path.join(dest_root, rel)), None, ''))

    rows.sort(key=lambda r: (STATUS_ORDER.index(r[0]), r[1].lower()))
    for row in rows:
        counts[row[0]] = counts.get(row[0], 0) + 1

    name_width = max(len(r[1]) for r in rows)
    print(f'{label}: {len(current_files)} file(s) upstream')
    print(f'    {"STATUS":<8} {"FILE":<{name_width}}  {"INSTALLED -> GITEA":<22} LAST CHANGED IN GITEA')
    for status, rel, installed_version, gitea_version, changed in rows:
        versions = f'{installed_version or "-"} -> {gitea_version or "-"}'
        print(f'    {status:<8} {rel:<{name_width}}  {versions:<22} {changed}')
    if counts.get('OLDER'):
        print(f'    WARNING: {counts["OLDER"]} file(s) in Gitea have a LOWER version than what is '
              'installed - is this the right branch?')

    if apply_changes:
        for rel in current_files:
            src_path = os.path.join(src_root, rel)
            dest_path = os.path.join(dest_root, rel)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(src_path, dest_path)

        for rel in stale_files:
            dest_path = os.path.join(dest_root, rel)
            if os.path.exists(dest_path):
                os.remove(dest_path)
                log_debug(f'Removed stale file: {dest_path}')

        print(f'{label}: synced to {dest_root}')

    print()
    return current_files, counts


def head_commit(clone_dir):
    """(short sha, ISO commit time, subject) of the cloned branch's head."""
    result = subprocess.run(['git', '-C', clone_dir, 'log', '-1', '--format=%h%x09%cI%x09%s'],
                            capture_output=True, text=True)
    parts = result.stdout.strip().split('\t', 2) if result.returncode == 0 else []
    return tuple(parts) if len(parts) == 3 else ('', '', '')


def clone_repo(gitea_url, owner, repo, branch, token, clone_dir):
    if token:
        scheme, _, rest = gitea_url.partition('://')
        clone_url = f'{scheme}://{token}@{rest}/{owner}/{repo}.git'
    else:
        clone_url = f'{gitea_url}/{owner}/{repo}.git'

    print(f'Cloning {gitea_url}/{owner}/{repo}.git (branch: {branch}) ...')
    result = subprocess.run(
        # No --depth 1: the report's per-file "last changed" needs the branch history. These
        # repos are small; history for one branch is cheap.
        ['git', 'clone', '--branch', branch, '--single-branch', clone_url, clone_dir],
        capture_output=True, text=True,
    )
    log_debug(f'git clone stdout={result.stdout!r} stderr={result.stderr!r}')

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        if 'could not read Username' in result.stderr or 'Authentication failed' in result.stderr:
            print('This repo needs a Gitea access token - pick "gitea | TOKEN" from Secrets '
                  'Manager\'s Entry dropdown and set it, or fill in the manual "token" field directly '
                  '(Gitea > Settings > Applications > Generate New Token, needs read '
                  'access to the repo).', file=sys.stderr)
        else:
            print('Clone failed - check the URL, branch, credentials, and that this Gitea '
                  'instance is reachable from the container.', file=sys.stderr)
        sys.exit(1)


def resolve_owner_repo(repo_selection, manual_repo):
    """Repo dropdown values are real 'owner/repo' selections; sentinel/error lines from
    gitea_client's dropdown-repos all start with '--' (e.g. "-- could not fetch repos: ... --",
    which can itself contain '/' from a URL in the error text - so detect sentinels by that
    prefix, not by the presence of a slash). Falls back to Manual Repo (also owner/repo) when
    the dropdown couldn't be populated - the case a public, tokenless repo needs, since there's
    no token to list live repos with."""
    selection = (repo_selection or '').strip()
    if selection and not selection.startswith('--'):
        if '/' not in selection:
            print(f'Selected repo {selection!r} is not in owner/repo form - unexpected dropdown '
                  f'value.', file=sys.stderr)
            sys.exit(1)
        owner, _, repo = selection.partition('/')
        return owner.strip(), repo.strip()

    manual = (manual_repo or '').strip()
    if manual:
        if '/' not in manual:
            print('Manual Repo must be in the form owner/repo, e.g. someuser/somerepo.',
                  file=sys.stderr)
            sys.exit(1)
        owner, _, repo = manual.partition('/')
        return owner.strip(), repo.strip()

    print('No repo selected - pick one from the Repo dropdown above (needs a working Gitea '
          'token), or fill in Manual Repo (owner/repo) directly.', file=sys.stderr)
    sys.exit(1)


def fix_permissions():
    fixed_any = False
    failed = False
    for dirpath, _dirnames, filenames in os.walk('/app/scripts'):
        for name in filenames:
            if name.endswith(('.sh', '.py', '.lua')):
                path = os.path.join(dirpath, name)
                try:
                    os.chmod(path, 0o755)
                    fixed_any = True
                except OSError:
                    failed = True
    if failed:
        print('WARNING: chmod failed on some files. Some hosts (certain QNAP setups) reject', file=sys.stderr)
        print('chmod across a bind mount with "Bad address". If scripts show as greyed out,', file=sys.stderr)
        print('run this on the NAS shell directly (outside Docker):', file=sys.stderr)
        print('  chmod +x scripts/*.sh scripts/*.py scripts/*.lua scripts/shared/*', file=sys.stderr)
    return fixed_any


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default=os.environ.get('PARAM_REPO', ''))
    parser.add_argument('--manual_repo', default=os.environ.get('PARAM_MANUAL_REPO', ''))
    parser.add_argument('--branch', default=os.environ.get('PARAM_BRANCH', 'main'))
    parser.add_argument('--token-key', default=os.environ.get('PARAM_TOKEN_KEY', ''))
    parser.add_argument('--apply', action='store_true', default=os.environ.get('PARAM_APPLY') == 'true')
    args = parser.parse_args()

    explicit_token = os.environ.get('GITEA_TOKEN', '')
    owner, repo = resolve_owner_repo(args.repo, args.manual_repo)

    try:
        gitea_url = resolve_gitea_url()
    except GiteaApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    source_key = f'{gitea_url}|{owner}|{repo}'
    state = load_state()
    previous = state.get(source_key, {'scripts': [], 'runners': []})

    # A repeat import (the one-tap update button) asks for the "auto" token: reuse the stored
    # token this source was imported with last time, if it's still stored, rather than failing
    # when several tokens exist.
    token_key = args.token_key
    stored_keys = {key for key, _ in list_gitea_tokens()}
    if (not explicit_token) and (not token_key or token_key == AUTO_SENTINEL) \
            and previous.get('token_key') in stored_keys:
        token_key = previous['token_key']

    try:
        token, token_source = resolve_gitea_token(explicit_token, token_key)
    except GiteaApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    log_debug(f'url={gitea_url} owner={owner} repo={repo} branch={args.branch} apply={args.apply}')
    print(f'Gitea token: {token_source}')

    if args.apply:
        print('Mode: APPLY (files will be written/removed)')
    else:
        print('Mode: DRY RUN (no files will be written - pass --apply to actually import)')
    print()

    with tempfile.TemporaryDirectory() as clone_dir:
        clone_repo(gitea_url, owner, repo, args.branch, token, clone_dir)
        commit, commit_iso, subject = head_commit(clone_dir)
        print(f'Gitea:     {owner}/{repo} @ {args.branch}, commit {commit} ({format_time(commit_iso)}) '
              f'"{subject}"')
        if previous.get('commit'):
            same = ' - same commit, nothing new in Gitea' if previous['commit'] == commit else ''
            print(f'Installed: commit {previous["commit"]} ({format_time(previous.get("commit_time"))}), '
                  f'imported {format_time(previous.get("imported_at"))}{same}')
        print()

        scripts_files, script_counts = sync_category(
            clone_dir, 'scripts', '/app/scripts', 'scripts/',
            args.apply, previous.get('scripts', []))
        runners_files, runner_counts = sync_category(
            clone_dir, 'runners', '/app/conf/runners', 'runners/',
            args.apply, previous.get('runners', []))

    totals = {}
    for counts in (script_counts, runner_counts):
        for status, count in counts.items():
            totals[status] = totals.get(status, 0) + count
    summary = ', '.join(f'{totals[status]} {SUMMARY_LABELS[status]}' for status in STATUS_ORDER if totals.get(status))

    if args.apply:
        print('Fixing execute permissions on imported scripts...')
        fix_permissions()
        print()

        state[source_key] = {
            'scripts': scripts_files,
            'runners': runners_files,
            'url': gitea_url,
            'owner': owner,
            'repo': repo,
            'branch': args.branch,
            'commit': commit,
            'commit_time': commit_iso,
            'imported_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            # Key NAME only (never the token) - see the repeat-import note above
            'token_key': token_key.split('|')[0].strip()
            if token_key and token_key != AUTO_SENTINEL else previous.get('token_key'),
            # Exactly what to send to re-run this import (the script header's update button)
            'update_parameters': {
                'manual_repo': f'{owner}/{repo}',
                'branch': args.branch,
                'token_key': AUTO_SENTINEL,
                'apply': True,
            },
        }
        save_state(state)

        print('Done. Refresh the browser to see new/updated/removed scripts - Script-Server')
        print('rereads conf/runners on each page load, no restart needed.')
    else:
        print('Dry run complete - re-run with --apply to actually sync these files.')

    # Last line, read by the update button for its confirmation message
    print(f'SUMMARY: {owner}/{repo} @ {commit} ({format_time(commit_iso)}): {summary or "no files"}'
          + ('' if args.apply else ' (dry run)'))


if __name__ == '__main__':
    main()
