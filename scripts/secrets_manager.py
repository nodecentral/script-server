#!/usr/bin/env python3
# Name: secrets_manager.py
# Version: 1.1.0
# Description: Sets, updates, or deletes an entry in the categorized secrets
#              store (/app/data/secrets.json via scripts/shared/secrets_store.py)
#              - e.g. category "finance" holding FINNHUB_API_KEY, category
#              "paperless" holding TOKEN. Pick an existing or suggested entry
#              from the dropdown (populated live by secrets_store.py) - that
#              alone is enough, category/key come from the selection itself.
#              Only pick "+ CREATE NEW ENTRY" and fill in New Entry
#              (category/KEY) when neither an existing nor a suggested entry
#              fits. Values are never echoed back - only a character count
#              confirms what was set. Run standalone
#              (./secrets_manager.py --entry "+ CREATE NEW ENTRY ..."
#              --new_entry finance/API_KEY --value secret123) or from
#              Script-Server.

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from secrets_store import NEW_ENTRY_SENTINEL, delete_secret, set_secret  # noqa: E402


def parse_entry(entry, new_entry):
    if entry == NEW_ENTRY_SENTINEL:
        raw = (new_entry or '').strip()
        if '/' not in raw:
            print(f'New Entry must be in the form category/KEY (e.g. finance/FINNHUB_API_KEY) - '
                  f'got {raw!r}', file=sys.stderr)
            sys.exit(1)
        category, _, key = raw.partition('/')
        category, key = category.strip(), key.strip()
        if not category or not key:
            print('New Entry must include both a category and a key, '
                  'e.g. finance/FINNHUB_API_KEY.', file=sys.stderr)
            sys.exit(1)
        return category, key

    parts = [p.strip() for p in entry.split('|')]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        print(f'Could not parse selected entry: {entry!r}', file=sys.stderr)
        sys.exit(1)
    return parts[0], parts[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--entry', default=os.environ.get('PARAM_ENTRY', ''))
    parser.add_argument('--new_entry', default=os.environ.get('PARAM_NEW_ENTRY', ''))
    parser.add_argument('--action', default=os.environ.get('PARAM_ACTION', 'set'))
    parser.add_argument('--value', default=os.environ.get('PARAM_VALUE', ''))
    args = parser.parse_args()

    if not args.entry:
        print('No entry selected', file=sys.stderr)
        sys.exit(1)

    category, key = parse_entry(args.entry, args.new_entry)

    if args.action == 'delete':
        if delete_secret(category, key):
            print(f'Deleted {category}.{key}')
        else:
            print(f'No secret found for {category}.{key} - nothing to delete.', file=sys.stderr)
            sys.exit(1)
        return

    if not args.value:
        print('A value is required when action is "Set / Update value".', file=sys.stderr)
        sys.exit(1)

    set_secret(category, key, args.value)
    print(f'Set {category}.{key} ({len(args.value)} characters)')


if __name__ == '__main__':
    main()
