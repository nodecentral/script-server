#!/usr/bin/env python3
# Name: secrets_manager.py
# Version: 1.2.0
# Description: Sets, updates, or deletes an entry in the categorized secrets
#              store (/app/data/secrets.json via scripts/shared/secrets_store.py)
#              - e.g. category "finance" holding FINNHUB_API_KEY, category
#              "paperless" holding TOKEN. Pick an existing or suggested entry
#              from the dropdown (populated live by secrets_store.py) - that
#              alone is enough, category/key come from the selection itself.
#              Only pick "+ CREATE NEW ENTRY" and fill in New Entry
#              (category/KEY) when neither an existing nor a suggested entry
#              fits. Values are never echoed back - only a character count
#              confirms what was set. After every run (success or error) this
#              re-renders the current store (same view as Secrets Viewer) so
#              the result is immediately visible and the next entry can be
#              set right away without navigating anywhere. Run standalone
#              (./secrets_manager.py --entry "+ CREATE NEW ENTRY ..."
#              --new_entry finance/API_KEY --value secret123) or from
#              Script-Server.

import argparse
import html
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from secrets_store import NEW_ENTRY_SENTINEL, delete_secret, set_secret  # noqa: E402
import secrets_viewer  # noqa: E402


def parse_entry(entry, new_entry):
    if entry == NEW_ENTRY_SENTINEL:
        raw = (new_entry or '').strip()
        if '/' not in raw:
            return None, None, (f'New Entry must be in the form category/KEY '
                                 f'(e.g. finance/FINNHUB_API_KEY) - got {raw!r}')
        category, _, key = raw.partition('/')
        category, key = category.strip(), key.strip()
        if not category or not key:
            return None, None, ('New Entry must include both a category and a key, '
                                 'e.g. finance/FINNHUB_API_KEY.')
        return category, key, None

    parts = [p.strip() for p in entry.split('|')]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None, None, f'Could not parse selected entry: {entry!r}'
    return parts[0], parts[1], None


def render_result(success, message):
    print(secrets_viewer.STYLE)
    banner_class = 'action-banner' if success else 'action-banner error'
    print(f'<div class="{banner_class}">{html.escape(message)}</div>')
    secrets_viewer.render_body()


def fail(message):
    render_result(False, message)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--entry', default=os.environ.get('PARAM_ENTRY', ''))
    parser.add_argument('--new_entry', default=os.environ.get('PARAM_NEW_ENTRY', ''))
    parser.add_argument('--action', default=os.environ.get('PARAM_ACTION', 'set'))
    parser.add_argument('--value', default=os.environ.get('PARAM_VALUE', ''))
    args = parser.parse_args()

    if not args.entry:
        fail('No entry selected.')
        return

    category, key, error = parse_entry(args.entry, args.new_entry)
    if error:
        fail(error)
        return

    if args.action == 'delete':
        if delete_secret(category, key):
            render_result(True, f'Deleted {category}.{key}')
        else:
            fail(f'No secret found for {category}.{key} - nothing to delete.')
        return

    if not args.value:
        fail('A value is required when action is "Set / Update value".')
        return

    set_secret(category, key, args.value)
    render_result(True, f'Set {category}.{key} ({len(args.value)} characters)')


if __name__ == '__main__':
    main()
