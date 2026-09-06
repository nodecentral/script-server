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
# This module is also used directly as a dynamic dropdown's values.script
# (see conf/runners/secrets_manager.json) via the `dropdown-entries`
# subcommand.

import json
import os
import sys
import time

STORE_PATH = '/app/data/secrets.json'

NEW_ENTRY_SENTINEL = '-- new entry --'


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
        print(f'{category} | {key} | last set {updated_at}')


def main():
    if len(sys.argv) < 2:
        print('Usage: secrets_store.py <get|list-categories|dropdown-entries> [args...]', file=sys.stderr)
        sys.exit(1)

    command, rest = sys.argv[1], sys.argv[2:]
    commands = {
        'get': _cmd_get,
        'list-categories': _cmd_list_categories,
        'dropdown-entries': _cmd_dropdown_entries,
    }
    if command not in commands:
        print(f'Unknown command: {command}', file=sys.stderr)
        sys.exit(1)

    commands[command](rest)


if __name__ == '__main__':
    main()
