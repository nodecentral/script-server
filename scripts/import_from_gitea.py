#!/usr/bin/env python3
# Name: import_from_gitea.py
# Version: 2.3.0
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
#              (./import_from_gitea.py --apply) or from Script-Server.
#
#              Gitea token resolution: an explicit "token" field always wins.
#              Otherwise this looks at the "gitea" category in the Secrets
#              Store (scripts/shared/secrets_store.py) - if exactly one token
#              is stored there it's used automatically, if there's more than
#              one the "Gitea Token" dropdown must pick which one (different
#              repos can need different tokens), and if none are stored the
#              repo is assumed to be public.

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from secrets_store import AUTO_SENTINEL, get_secret, list_category_keys  # noqa: E402

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


def sync_category(src_root, dest_root, label, apply_changes, previous_files):
    current_files = list_files(src_root)

    if not current_files:
        print(f'{label}: nothing found upstream')
    else:
        print(f'{label}: {len(current_files)} file(s) upstream:')
        for rel in current_files:
            print(f'    {rel}')

    stale_files = sorted(set(previous_files) - set(current_files))
    if stale_files:
        print(f'{label}: {len(stale_files)} file(s) removed upstream since last import:')
        for rel in stale_files:
            print(f'    {rel}')

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

        if current_files or stale_files:
            print(f'{label}: synced to {dest_root}')

    print()
    return current_files


def clone_repo(gitea_url, owner, repo, branch, token, clone_dir):
    if token:
        scheme, _, rest = gitea_url.partition('://')
        clone_url = f'{scheme}://{token}@{rest}/{owner}/{repo}.git'
    else:
        clone_url = f'{gitea_url}/{owner}/{repo}.git'

    print(f'Cloning {gitea_url}/{owner}/{repo}.git (branch: {branch}) ...')
    result = subprocess.run(
        ['git', 'clone', '--depth', '1', '--branch', branch, '--single-branch', clone_url, clone_dir],
        capture_output=True, text=True,
    )
    log_debug(f'git clone stdout={result.stdout!r} stderr={result.stderr!r}')

    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        if 'could not read Username' in result.stderr or 'Authentication failed' in result.stderr:
            print('This repo needs a Gitea access token - fill in the "token" field '
                  '(Gitea > Settings > Applications > Generate New Token, needs read '
                  'access to the repo).', file=sys.stderr)
        else:
            print('Clone failed - check the URL, branch, credentials, and that this Gitea '
                  'instance is reachable from the container.', file=sys.stderr)
        sys.exit(1)


def resolve_gitea_token(explicit_token, token_key):
    """Returns (token, source_description) - source_description is for logging only,
    never the token value itself."""
    if explicit_token:
        return explicit_token, 'the manually entered token field'

    stored = list_category_keys('gitea')

    if token_key and token_key != AUTO_SENTINEL:
        value = get_secret('gitea', token_key)
        if value is None:
            print(f'No stored Gitea token found for gitea.{token_key} - check Secrets Manager.',
                  file=sys.stderr)
            sys.exit(1)
        return value, f'gitea.{token_key} (Secrets Store)'

    if len(stored) == 1:
        key = stored[0][0]
        return get_secret('gitea', key), f'gitea.{key} (Secrets Store, auto-selected - only one stored)'

    if len(stored) > 1:
        stored_names = ', '.join(f'gitea.{key}' for key, _ in stored)
        print(f'Multiple Gitea tokens are stored ({stored_names}) - pick one from the '
              '"Gitea Token" dropdown, or fill in the manual token field directly.', file=sys.stderr)
        sys.exit(1)

    return '', 'none (public repo assumed)'


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
    parser.add_argument('--url', default=os.environ.get('PARAM_GITEA_URL', 'http://192.168.102.148:3011'))
    parser.add_argument('--owner', default=os.environ.get('PARAM_OWNER', 'claude'))
    parser.add_argument('--repo', default=os.environ.get('PARAM_REPO', 'ss_music_file_management'))
    parser.add_argument('--branch', default=os.environ.get('PARAM_BRANCH', 'main'))
    parser.add_argument('--token-key', default=os.environ.get('PARAM_TOKEN_KEY', ''))
    parser.add_argument('--apply', action='store_true', default=os.environ.get('PARAM_APPLY') == 'true')
    args = parser.parse_args()

    gitea_url = args.url.rstrip('/')
    explicit_token = os.environ.get('GITEA_TOKEN', '')
    token, token_source = resolve_gitea_token(explicit_token, args.token_key)

    if not gitea_url or not args.owner or not args.repo:
        print('Missing required parameter(s): url, owner and repo are all required', file=sys.stderr)
        sys.exit(1)

    log_debug(f'url={gitea_url} owner={args.owner} repo={args.repo} branch={args.branch} apply={args.apply}')
    print(f'Gitea token: {token_source}')

    if args.apply:
        print('Mode: APPLY (files will be written/removed)')
    else:
        print('Mode: DRY RUN (no files will be written - pass --apply to actually import)')
    print()

    source_key = f'{gitea_url}|{args.owner}|{args.repo}'
    state = load_state()
    previous = state.get(source_key, {'scripts': [], 'runners': []})

    with tempfile.TemporaryDirectory() as clone_dir:
        clone_repo(gitea_url, args.owner, args.repo, args.branch, token, clone_dir)
        print()

        scripts_files = sync_category(
            os.path.join(clone_dir, 'scripts'), '/app/scripts', 'scripts/',
            args.apply, previous.get('scripts', []))
        runners_files = sync_category(
            os.path.join(clone_dir, 'runners'), '/app/conf/runners', 'runners/',
            args.apply, previous.get('runners', []))

    if args.apply:
        print('Fixing execute permissions on imported scripts...')
        fix_permissions()
        print()

        state[source_key] = {'scripts': scripts_files, 'runners': runners_files}
        save_state(state)

        print('Done. Refresh the browser to see new/updated/removed scripts - Script-Server')
        print('rereads conf/runners on each page load, no restart needed.')
    else:
        print('Dry run complete - re-run with --apply to actually sync these files.')


if __name__ == '__main__':
    main()
