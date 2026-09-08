#!/usr/bin/env python3
# Shared module (not a standalone Script-Server script): a single categorized
# JSON store for API keys/tokens needed by other scripts - e.g. a "gitea"
# product holding a TOKEN, a "paperless" product holding a TOKEN - so
# unrelated scripts don't need to share one flat namespace of env vars.
#
# Terminology: a "product" is the service/product the secret belongs to
# (gitea, paperless, pushover, adobe...) and a "key" is the specific
# credential within it (TOKEN, URL, API_KEY...). Each product should be one
# real product/service - if you're tempted to create a grouping/topic
# product (e.g. an old "finance" product that held eight unrelated
# providers' keys), don't: give each provider its own product instead, one
# key each, so "product" always means exactly what it says. See ROADMAP.md's
# entry on this rename for why - a prior version of this store had a
# "finance" grouping and it caused real confusion.
#
# Consuming a secret from a Python script running under Script-Server:
#   import sys
#   sys.path.insert(0, '/app/scripts/shared')
#   from secrets_store import get_secret
#   api_key = get_secret('finnhub', 'API_KEY')
#
# Consuming a secret from Lua/bash (or anything that can shell out):
#   python3 /app/scripts/shared/secrets_store.py get finnhub API_KEY
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
# - `list-products` for Secrets Manager's "New Product" field (editable_list -
#   suggests existing products but still accepts a typed new one)
# - `dropdown-product <product>` for a runner that needs to let the user pick
#   among several stored keys for one product, e.g. Import from Gitea picking
#   which stored "gitea" token to use when more than one exists
#   (see conf/runners/import_from_gitea.json)

import json
import os
import sys
import time

STORE_PATH = '/app/data/secrets.json'

# The "expected secrets" checklist - product/key/description entries this fork already has (or
# expects to have) a consuming script for, so Secrets Manager's dropdown and Secrets Viewer can
# surface them BEFORE a value is ever set. Shipped as checked-in DATA (this file, not code) so
# it's visible/diffable in git and editable without touching secrets_store.py - deliberately kept
# separate from /app/data/secrets.json (the real, gitignored, NAS-local values) so a fresh git
# pull can add new known integrations without ever touching or clobbering real stored values.
# Add an entry here whenever a script is wired to call get_secret() for a product/key that isn't
# in this list yet.
KNOWN_INTEGRATIONS_PATH = '/app/conf/secrets_defaults.json'

# Deliberately loud and self-explanatory, not just "-- new entry --": Script-Server has no way to
# hide the New Product/New Key fields unless this exact sentinel is picked, so the dropdown option
# itself has to carry the instruction rather than relying on a field description the user may not
# read. New Product is an editable_list (see list-products below) so an existing product can be
# picked instead of retyped - this sentinel covers both "add a key to an existing product" and
# "create a brand new product", since either way the two fields below are just Product + Key now.
NEW_ENTRY_SENTINEL = '+ CREATE NEW ENTRY (fill in New Product + New Key below)'

# Sentinel for a dropdown scoped to one product (see list_product_keys/dropdown-product) - means
# "don't pick a specific stored key, let the caller decide" (e.g. Import from Gitea falls back to
# a manually entered token, or auto-selects if exactly one is stored under that product).
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


def load_known_integrations():
    """Returns (product, key, description) tuples from the checked-in defaults file
    (KNOWN_INTEGRATIONS_PATH) - the "expected secrets" checklist. Missing/unreadable file is
    treated as an empty checklist, not an error - this file is optional data, never required for
    the store itself to work."""
    if not os.path.exists(KNOWN_INTEGRATIONS_PATH):
        return []
    with open(KNOWN_INTEGRATIONS_PATH) as f:
        try:
            entries = json.load(f)
        except json.JSONDecodeError:
            return []
    return [
        (entry['product'], entry['key'], entry.get('description', ''))
        for entry in entries
        if 'product' in entry and 'key' in entry
    ]


def get_secret(product, key):
    """Returns the raw secret value, or None if the product/key doesn't exist."""
    store = load_store()
    entry = store.get(product, {}).get(key)
    return entry.get('value') if entry else None


def set_secret(product, key, value, description=''):
    """Sets/updates a secret's value. A non-empty description overwrites any existing one; an
    empty description leaves whatever was already stored untouched, so updating just the value
    never silently wipes out a description set on a previous run."""
    store = load_store()
    entry = store.setdefault(product, {}).setdefault(key, {})
    entry['value'] = value
    entry['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    if description:
        entry['description'] = description
    save_store(store)


def delete_secret(product, key):
    store = load_store()
    if product in store and key in store[product]:
        del store[product][key]
        if not store[product]:
            del store[product]
        save_store(store)
        return True
    return False


def list_products():
    return sorted(load_store().keys())


def list_product_keys(product):
    """Returns (key, updated_at) tuples for all keys currently set under one product."""
    entries = load_store().get(product, {})
    return sorted(
        [(key, entry.get('updated_at', '')) for key, entry in entries.items()],
        key=lambda e: e[0].lower(),
    )


def list_known_placeholders():
    """Known integrations (see load_known_integrations()) that don't have a value set yet -
    (product, key, description) tuples."""
    store = load_store()
    return [
        (product, key, description)
        for product, key, description in load_known_integrations()
        if key not in store.get(product, {})
    ]


def list_entries_metadata():
    """Returns (product, key, updated_at, value_length, description) tuples - never the raw
    value. description is whatever was entered via Secrets Manager, empty string if none."""
    store = load_store()
    result = []
    for product, keys in store.items():
        for key, entry in keys.items():
            value = entry.get('value', '')
            result.append((
                product, key, entry.get('updated_at', ''), len(value), entry.get('description', ''),
            ))
    return sorted(result, key=lambda e: (e[0].lower(), e[1].lower()))


def _cmd_get(args):
    if len(args) != 2:
        print('Usage: secrets_store.py get <product> <key>', file=sys.stderr)
        sys.exit(1)
    value = get_secret(args[0], args[1])
    if value is None:
        print(f'No secret set for {args[0]}.{args[1]}', file=sys.stderr)
        sys.exit(1)
    print(value, end='')


def _cmd_list_products(_args):
    for product in list_products():
        print(product)


def _cmd_dropdown_entries(_args):
    print(NEW_ENTRY_SENTINEL)
    for product, key, updated_at, _length, description in list_entries_metadata():
        suffix = f' - {description}' if description else ''
        print(f'{product} | {key} | ✓ set - last updated {updated_at}{suffix}')
    for product, key, description in list_known_placeholders():
        print(f'{product} | {key} | ○ not set yet - {description}')


def _cmd_dropdown_product(args):
    if len(args) != 1:
        print('Usage: secrets_store.py dropdown-product <product>', file=sys.stderr)
        sys.exit(1)
    product = args[0]
    print(AUTO_SENTINEL)
    for key, updated_at in list_product_keys(product):
        print(f'{key} | last set {updated_at}')


def main():
    if len(sys.argv) < 2:
        print('Usage: secrets_store.py <get|list-products|dropdown-entries|dropdown-product> [args...]',
              file=sys.stderr)
        sys.exit(1)

    command, rest = sys.argv[1], sys.argv[2:]
    commands = {
        'get': _cmd_get,
        'list-products': _cmd_list_products,
        'dropdown-entries': _cmd_dropdown_entries,
        'dropdown-product': _cmd_dropdown_product,
    }
    if command not in commands:
        print(f'Unknown command: {command}', file=sys.stderr)
        sys.exit(1)

    commands[command](rest)


if __name__ == '__main__':
    main()
