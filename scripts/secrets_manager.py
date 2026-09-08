#!/usr/bin/env python3
# Name: secrets_manager.py
# Version: 1.4.0
# Description: Sets, updates, or deletes an entry in the categorized secrets
#              store (/app/data/secrets.json via scripts/shared/secrets_store.py)
#              - e.g. product "gitea" holding TOKEN, product "finnhub" holding
#              API_KEY. Pick an existing or suggested entry from the dropdown
#              (populated live by secrets_store.py) - that alone is enough,
#              product/key come from the selection itself. To create a new
#              entry (a new key under an existing product, or a brand new
#              product), pick "+ CREATE NEW ENTRY" and fill in New Product
#              (an existing product from the list, or type a new one, e.g.
#              Adobe) and New Key (e.g. API_KEY) - both are needed together,
#              in the same run as the Value. Values are never echoed back -
#              only a character count confirms what was set. After every run
#              (success or error) this re-renders the current store (same
#              view as Secrets Viewer) so the result is immediately visible
#              and the next entry can be set right away without navigating
#              anywhere. Run standalone (./secrets_manager.py --entry
#              "+ CREATE NEW ENTRY (fill in New Product + New Key below)"
#              --new_product finnhub --new_key API_KEY --value secret123)
#              or from Script-Server.

import argparse
import html
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from secrets_store import NEW_ENTRY_SENTINEL, delete_secret, set_secret  # noqa: E402
import secrets_viewer  # noqa: E402


def parse_entry(entry, new_product, new_key):
    if entry == NEW_ENTRY_SENTINEL:
        product = (new_product or '').strip()
        key = (new_key or '').strip()
        if not product or not key:
            return None, None, ('New Product and New Key are both required to create a new '
                                 'entry (e.g. Product: finnhub, Key: API_KEY).')
        return product, key, None

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
    parser.add_argument('--new_product', default=os.environ.get('PARAM_NEW_PRODUCT', ''))
    parser.add_argument('--new_key', default=os.environ.get('PARAM_NEW_KEY', ''))
    parser.add_argument('--action', default=os.environ.get('PARAM_ACTION', 'set'))
    parser.add_argument('--value', default=os.environ.get('PARAM_VALUE', ''))
    args = parser.parse_args()

    if not args.entry:
        fail('No entry selected.')
        return

    product, key, error = parse_entry(args.entry, args.new_product, args.new_key)
    if error:
        fail(error)
        return

    if args.action == 'delete':
        if delete_secret(product, key):
            render_result(True, f'Deleted {product}.{key}')
        else:
            fail(f'No secret found for {product}.{key} - nothing to delete.')
        return

    if not args.value:
        fail('A value is required when action is "Set / Update value".')
        return

    set_secret(product, key, args.value)
    render_result(True, f'Set {product}.{key} ({len(args.value)} characters)')


if __name__ == '__main__':
    main()
