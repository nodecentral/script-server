"""
Where a script came from, for the script header's one-tap "update from Gitea" button (admins).

Import from Gitea (scripts/import_from_gitea.py) records every import in
data/gitea_import_state.json, keyed "<url>|<owner>|<repo>", including the runner files it placed
(relative to conf/runners), the branch/commit it took them from and - since its 5.1.0 - the exact
parameters to send to re-run that import ("update_parameters"). This module only reads that file:
the import script owns its format and how it should be re-run, the server just looks a runner up.

Imports recorded by older versions of the import script have no branch/commit/update_parameters;
a minimal re-import (manual_repo + branch "main" + apply) is synthesised for them, and the first
update through the button records the full details.
"""

import json
import logging
import os

LOGGER = logging.getLogger('script_server.gitea_origin')

# The runner whose script does the importing - what the update button executes
UPDATER_SCRIPT_NAME = 'Import from Gitea'


def default_state_path():
    # The app's working dir is /app in the Docker image, so this is /app/data - the same file
    # the import script writes (STATE_PATH there).
    return os.path.join(os.getcwd(), 'data', 'gitea_import_state.json')


def _load_state(state_path):
    if not os.path.exists(state_path):
        return {}
    try:
        with open(state_path, encoding='utf-8') as f:
            state = json.load(f)
        return state if isinstance(state, dict) else {}
    except Exception:
        LOGGER.exception('Cannot read ' + state_path)
        return {}


def find_origin(runner_relpath, state_path=None):
    """The import that placed this runner file (path relative to conf/runners), or None."""
    if not runner_relpath:
        return None

    state = _load_state(state_path or default_state_path())
    runner_relpath = runner_relpath.replace(os.sep, '/')

    for source_key, entry in state.items():
        if not isinstance(entry, dict):
            continue
        runners = [str(r).replace(os.sep, '/') for r in (entry.get('runners') or [])]
        if runner_relpath not in runners:
            continue

        url, _, rest = source_key.partition('|')
        owner, _, repo = rest.partition('|')
        owner = entry.get('owner') or owner
        repo = entry.get('repo') or repo
        branch = entry.get('branch') or 'main'

        update_parameters = entry.get('update_parameters')
        if not isinstance(update_parameters, dict):
            update_parameters = {'manual_repo': f'{owner}/{repo}', 'branch': branch, 'apply': True}

        return {
            'type': 'gitea',
            'url': entry.get('url') or url,
            'owner': owner,
            'repo': repo,
            'branch': branch,
            'commit': entry.get('commit'),
            'commitTime': entry.get('commit_time'),
            'importedAt': entry.get('imported_at'),
            'updater': UPDATER_SCRIPT_NAME,
            'updateParameters': update_parameters,
        }

    return None
