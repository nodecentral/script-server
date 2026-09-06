#!/usr/bin/env python3
# Shared module (not a standalone Script-Server script): a single categorized
# JSON store for API keys/tokens needed by other scripts - e.g. a "finance"
# category holding FINNHUB_API_KEY, a "paperless" category holding TOKEN -
# so unrelated scripts don't need to share one flat namespace of env vars.
#
# Consuming a secret from a Python script running under Script-Server:
#   import sys
#   sys.path.insert(0, '/app/scripts/shared')
#   from secrets_store import get_secret
#   api_key = get_secret('finance', 'FINNHUB_API_KEY')
#
# Consuming a secret from Lua/bash (or anything that can shell out):
#   python3 /app/scripts/shared/secrets_store.py get finance FINNHUB_API_KEY
# prints just the raw value to stdout (nothing else), exit code 1 if unset -
# same "shell out to a Python helper" pattern used for JSON in Lua elsewhere
# in this repo (see CLAUDE.md's "Lua has no JSON library" note).
#
# Storage: /app/data/secrets.json, plaintext, chmod 600 best-effort after
# every write. This is the same risk tier as a Docker environment block or a
# plain .env file already sitting on the NAS filesystem - not encrypted at
# rest. See CLAUDE.md's Secrets Store section before treating this as a
# vault for anything more sensitive than a home-lab API key/token.
#
# This module is also used directly as a dynamic dropdown's values.script:
# - `dropdown-entries` for Secrets Manager (conf/runners/secrets_manager.json)
# - `dropdown-category <category>` for a runner that needs to let the user
#   pick among several stored tokens in one category, e.g. Import from Gitea
#   picking which stored "gitea" token to use when more than one exists
#   (see conf/runners/import_from_gitea.json)

import json
import os
import sys
import time

STORE_PATH = '/app/data/secrets.json'

# Deliberately loud and self-explanatory, not just "-- new entry --": Script-Server has no way to
# hide the New Entry field unless this exact sentinel is picked, so the dropdown option itself has
# to carry the instruction ("fill in New Entry below") rather than relying on a field description
# the user may not read.
NEW_ENTRY_SENTINEL = '+ CREATE NEW ENTRY (fill in New Entry field below: category/KEY)'

# Integrations this fork already has (or expects to have) a consuming script for, so Secrets
# Manager's dropdown and Secrets Viewer can surface them BEFORE a value is ever set - catching a
# missing secret before a script fails on it, rather than after. Add an entry here whenever a
# script is wired to call get_secret() for a category/key that isn't in this list yet.
KNOWN_INTEGRATIONS = [
    ('pushover', 'TOKEN', 'Pushover application token - used by Send Notification'),
    ('pushover', 'USER_KEY', 'Pushover user key - used by Send Notification'),
    ('prowl', 'TOKEN', 'Prowl API key - used by Send Notification'),
    ('paperless', 'URL', 'Paperless-ngx base URL, e.g. http://192.168.1.x:8010 - placeholder, no consuming script yet'),
    ('paperless', 'TOKEN', 'Paperless-ngx API token (Settings > API Tokens) - placeholder, no consuming script yet'),
    ('gitea', 'TOKEN', 'Default Gitea access token - used by Import from Gitea (Gitea > Settings > '
                        'Applications > Generate New Token). Add more named keys under the gitea '
                        'category via Secrets Manager if different repos need different tokens.'),
]

# Sentinel for a dropdown scoped to one category (see list_category_keys/dropdown-category) -
# means "don't pick a specific stored token, let the caller decide" (e.g. Import from Gitea falls
# back to a manually entered token, or auto-selects if exactly one is stored under that category).
AUTO_SENTINEL = '-- auto (manual token field, or the only stored one) --'


def load_store():
    if not os.path.exists(STORE_PATH):
        return {}
    with open(STORE_PATH) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_store(store):
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    tmp_path = STORE_PATH + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(store, f, indent=2, sort_keys=True)
    os.replace(tmp_path, STORE_PATH)
    try:
        os.chmod(STORE_PATH, 0o600)
    except OSError:
        pass  # best-effort - same QNAP bind-mount chmod caveat as elsewhere in this repo


def get_secret(category, key):
    """Returns the raw secret value, or None if the category/key doesn't exist."""
    store = load_store()
    entry = store.get(category, {}).get(key)
    return entry.get('value') if entry else None


def set_secret(category, key, value):
    store = load_store()
    store.setdefault(category, {})[key] = {
        'value': value,
        'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    save_store(store)


def delete_secret(category, key):
    store = load_store()
    if category in store and key in store[category]:
        del store[category][key]
        if not store[category]:
            del store[category]
        save_store(store)
        return True
    return False


def list_categories():
    return sorted(load_store().keys())


def list_category_keys(category):
    """Returns (key, updated_at) tuples for all keys currently set under one category."""
    entries = load_store().get(category, {})
    return sorted(
        [(key, entry.get('updated_at', '')) for key, entry in entries.items()],
        key=lambda e: e[0].lower(),
    )


def list_known_placeholders():
    """Known integrations (see KNOWN_INTEGRATIONS) that don't have a value set yet -
    (category, key, description) tuples."""
    store = load_store()
    return [
        (category, key, description)
        for category, key, description in KNOWN_INTEGRATIONS
        if key not in store.get(category, {})
    ]


def list_entries_metadata():
    """Returns (category, key, updated_at, value_length) tuples - never the raw value."""
    store = load_store()
    result = []
    for category, keys in store.items():
        for key, entry in keys.items():
            value = entry.get('value', '')
            result.append((category, key, entry.get('updated_at', ''), len(value)))
    return sorted(result, key=lambda e: (e[0].lower(), e[1].lower()))


def _cmd_get(args):
    if len(args) != 2:
        print('Usage: secrets_store.py get <category> <key>', file=sys.stderr)
        sys.exit(1)
    value = get_secret(args[0], args[1])
    if value is None:
        print(f'No secret set for {args[0]}.{args[1]}', file=sys.stderr)
        sys.exit(1)
    print(value, end='')


def _cmd_list_categories(_args):
    for category in list_categories():
        print(category)


def _cmd_dropdown_entries(_args):
    print(NEW_ENTRY_SENTINEL)
    for category, key, updated_at, _length in list_entries_metadata():
        print(f'{category} | {key} | ✓ set - last updated {updated_at}')
    for category, key, description in list_known_placeholders():
        print(f'{category} | {key} | ○ not set yet - {description}')


def _cmd_dropdown_category(args):
    if len(args) != 1:
        print('Usage: secrets_store.py dropdown-category <category>', file=sys.stderr)
        sys.exit(1)
    category = args[0]
    print(AUTO_SENTINEL)
    for key, updated_at in list_category_keys(category):
        print(f'{key} | last set {updated_at}')


def main():
    if len(sys.argv) < 2:
        print('Usage: secrets_store.py <get|list-categories|dropdown-entries> [args...]', file=sys.stderr)
        sys.exit(1)

    command, rest = sys.argv[1], sys.argv[2:]
    commands = {
        'get': _cmd_get,
        'list-categories': _cmd_list_categories,
        'dropdown-entries': _cmd_dropdown_entries,
        'dropdown-category': _cmd_dropdown_category,
    }
    if command not in commands:
        print(f'Unknown command: {command}', file=sys.stderr)
        sys.exit(1)

    commands[command](rest)


if __name__ == '__main__':
    main()
