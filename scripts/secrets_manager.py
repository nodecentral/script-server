#!/usr/bin/env python3
# Name: secrets_manager.py
# Version: 1.0.0
# Description: Sets, updates, or deletes an entry in the categorized secrets
#              store (/app/data/secrets.json via scripts/shared/secrets_store.py)
#              - e.g. category "finance" holding FINNHUB_API_KEY, category
#              "paperless" holding TOKEN. Pick an existing entry from the
#              dropdown (populated live by secrets_store.py) or choose
#              "-- new entry --" and type a new category/key. Values are never
#              echoed back - only a character count confirms what was set.
#              Run standalone (./secrets_manager.py --entry "-- new entry --"
#              --new_category finance --new_key API_KEY --value secret123)
#              or from Script-Server.

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from secrets_store import NEW_ENTRY_SENTINEL, delete_secret, set_secret  # noqa: E402


def parse_entry(entry, new_category, new_key):
    if entry == NEW_ENTRY_SENTINEL:
        category = (new_category or '').strip()
        key = (new_key or '').strip()
        if not category or not key:
            print('Choose "-- new entry --" only together with both a new category and a new key.',
                  file=sys.stderr)
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
    parser.add_argument('--new_category', default=os.environ.get('PARAM_NEW_CATEGORY', ''))
    parser.add_argument('--new_key', default=os.environ.get('PARAM_NEW_KEY', ''))
    parser.add_argument('--action', default=os.environ.get('PARAM_ACTION', 'set'))
    parser.add_argument('--value', default=os.environ.get('PARAM_VALUE', ''))
    args = parser.parse_args()

    if not args.entry:
        print('No entry selected', file=sys.stderr)
        sys.exit(1)

    category, key = parse_entry(args.entry, args.new_category, args.new_key)

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
