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
#   api_key = get_secret('finnhub', 'API_KEY', 'used by Portfolio Prices')
#
# Consuming a secret from Lua/bash (or anything that can shell out):
#   python3 /app/scripts/shared/secrets_store.py get finnhub API_KEY "used by Portfolio Prices"
# prints just the raw value to stdout (nothing else), exit code 1 if unset (and
# registers a placeholder, same as get_secret() - the purpose argument is optional) -
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
#
# Every script that consumes a secret owns preparing for it itself - there is no
# centralized scanner that guesses what a script needs from its source. Two
# per-script layers, both built on get_secret():
# - get_secret(product, key, purpose) self-registers a placeholder on a miss
#   (DISCOVERED_PATH below), so the missing secret shows up in Secrets
#   Manager's dropdown and Secrets Viewer's "Not Yet Configured" list, ready
#   for a value - the script's own request is what puts it there, so it's
#   always tied to a real, installed script asking for it.
# - missing_secret_banner_html() in the script's preload shows a banner with a
#   one-click deep link into Secrets Manager (and registers the placeholder
#   too, since it goes through get_secret()) - before the script is even run.
#   Reference: scripts/preload/import_from_gitea.py.

import html
import json
import os
import sys
import time
from urllib.parse import urlencode

STORE_PATH = '/app/data/secrets.json'

# Script-Server's own SPA router (confirmed in web-src/src/main-app/store/scripts.js and
# store/index.js): the URL's query string is read once on page load as "predefinedParameters"
# and fed straight into the script form as initial parameter values, keyed by each query key
# matching a parameter's "name" - a real, native deep-link mechanism, not something built here.
# scriptNameToHash() (web-src/src/main-app/utils/model_helper.js) is just encodeURIComponent(name)
# - Secrets Manager's runner "name" is literally "Secrets Manager".
SECRETS_MANAGER_HASH = 'Secrets%20Manager'

# The "expected secrets" checklist - product/key/description entries this fork already has (or
# expects to have) a consuming script for, so Secrets Manager's dropdown and Secrets Viewer can
# surface them BEFORE a value is ever set. Shipped as checked-in DATA (this file, not code) so
# it's visible/diffable in git and editable without touching secrets_store.py - deliberately kept
# separate from /app/data/secrets.json (the real, gitignored, NAS-local values) so a fresh git
# pull can add new known integrations without ever touching or clobbering real stored values.
# Add an entry here whenever a script is wired to call get_secret() for a product/key that isn't
# in this list yet.
KNOWN_INTEGRATIONS_PATH = '/app/conf/secrets_defaults.json'

# Placeholders self-registered at runtime by get_secret() on a miss - {product: {key:
# {first_seen, requested_by: {script: purpose}}}}. NAS-local and gitignored, alongside
# secrets.json, rather than written into conf/secrets_defaults.json: that file is checked into
# git and hand-curated, so a later git pull/deploy of it would silently wipe any entry
# auto-written there. Holds no secret values at all (names + purpose text only) - the only thing
# that needs protecting is a value, and values only ever live in STORE_PATH.
DISCOVERED_PATH = '/app/data/secrets_discovered.json'

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


def get_secret(product, key, purpose='', register=True):
    """Returns the raw secret value, or None if the product/key doesn't exist.

    On a miss, also self-registers a placeholder (see register_placeholder()) so the secret shows
    up in Secrets Manager/Viewer ready to be filled in - pass a short purpose (what it's needed
    for) so whoever fills it in knows why. Pass register=False only for a lookup that isn't a real
    requirement, e.g. resolving a key the user just picked from a dropdown of existing keys (a miss
    there means a stale pick, not a secret any script needs)."""
    store = load_store()
    entry = store.get(product, {}).get(key)
    value = entry.get('value') if entry else None
    if value is None and register:
        register_placeholder(product, key, purpose)
    return value


def _requesting_script():
    """Best-effort name of the script asking for a secret - the running Python entry point,
    relative to /app/scripts when it lives there (e.g. "notify.py", "preload/import_from_gitea.py").
    A Lua/bash shell-out runs this module's own CLI, so the real caller isn't knowable here."""
    path = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ''
    if not path or os.path.basename(path) == 'secrets_store.py':
        return 'a Lua/bash script (via secrets_store.py get)'
    scripts_dir = '/app/scripts/'
    return path[len(scripts_dir):] if path.startswith(scripts_dir) else os.path.basename(path)


def load_discovered():
    if not os.path.exists(DISCOVERED_PATH):
        return {}
    with open(DISCOVERED_PATH) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_discovered(discovered):
    os.makedirs(os.path.dirname(DISCOVERED_PATH), exist_ok=True)
    # Per-process tmp name: preloads and dropdown scripts can call get_secret() concurrently.
    tmp_path = f'{DISCOVERED_PATH}.{os.getpid()}.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(discovered, f, indent=2, sort_keys=True)
    os.replace(tmp_path, DISCOVERED_PATH)


def register_placeholder(product, key, purpose='', requested_by=None):
    """Records that a script needs product.key, so it appears as a "not set yet" entry in
    Secrets Manager/Viewer. Only writes when something is actually new (a new product/key, a new
    requesting script, or a purpose where there was none), not on every miss. Never raises -
    this runs inside get_secret(), and failing to record a placeholder (e.g. run standalone with
    no /app/data) must never break the actual lookup."""
    try:
        requested_by = requested_by or _requesting_script()
        discovered = load_discovered()
        entry = discovered.setdefault(product, {}).setdefault(key, {})
        requesters = entry.setdefault('requested_by', {})
        if requested_by in requesters and (requesters[requested_by] or not purpose):
            return
        requesters[requested_by] = purpose or ''
        entry.setdefault('first_seen', time.strftime('%Y-%m-%d %H:%M:%S'))
        _save_discovered(discovered)
    except Exception:
        pass


def remove_placeholder(product, key):
    """Removes a self-registered placeholder. Returns True if one existed. A script that still
    calls get_secret() for it will simply register it again on its next run."""
    discovered = load_discovered()
    if product in discovered and key in discovered[product]:
        del discovered[product][key]
        if not discovered[product]:
            del discovered[product]
        _save_discovered(discovered)
        return True
    return False


def missing_secret_link(product, key):
    """A deep link straight into Secrets Manager with New Product/New Key pre-filled via
    Script-Server's own predefinedParameters mechanism (see the module docstring) - the "Add it"
    link a missing-secret banner should point at. Always includes target="_top": this is meant
    to be embedded inside a preload's own html/html_iframe output, and for html_iframe that's a
    same-origin <iframe> with no router of its own - without target="_top" the link would try
    (and fail) to navigate the iframe itself instead of the actual app."""
    query = urlencode({'entry': NEW_ENTRY_SENTINEL, 'new_product': product, 'new_key': key})
    return f'/#/{SECRETS_MANAGER_HASH}?{query}'


def missing_secret_banner_html(product, key, purpose=''):
    """Returns an HTML snippet warning that product.key isn't configured yet, with a deep link
    into Secrets Manager (New Product/New Key already filled in - just Value left to type) - or
    '' if it's already set, so a caller can just do `banner = missing_secret_banner_html(...);
    if banner: print(banner)`. Every script that needs a secret should check for it this way, in
    its own preload (see CLAUDE.md/SCRIPTING.md's Secrets Store section).

    Uses inline styles for a themed warning banner under html_iframe. Under plain "html" output
    format, Script-Server's own sanitizer strips both <style> blocks AND inline style=
    attributes (confirmed in CLAUDE.md's Output Formats section) - this degrades to plain,
    unstyled text there, but the link itself still works either way. Use html_iframe if the
    styling matters, matching this fork's existing "html can't do custom CSS" convention."""
    # Goes through get_secret() on purpose, so a preload showing this banner also registers the
    # placeholder - the secret is in Secrets Manager's dropdown before the script is ever run.
    if get_secret(product, key, purpose) is not None:
        return ''
    link = missing_secret_link(product, key)
    purpose_html = f' - {html.escape(purpose)}' if purpose else ''
    return (
        '<div style="background:#ffebee;border-left:4px solid #c62828;border-radius:2px;'
        'padding:12px 16px;font-size:0.9rem;font-family:\'Roboto\',\'Helvetica Neue\',Arial,'
        'sans-serif;">'
        f'Missing secret: <span style="font-family:\'Roboto Mono\',\'Courier New\',monospace;">'
        f'{html.escape(product)}.{html.escape(key)}</span>{purpose_html}. '
        f'<a href="{link}" target="_top" style="font-weight:500;">Add it in Secrets Manager</a>'
        '</div>'
    )


def missing_secrets_banner_html(requirements):
    """Convenience wrapper for a script needing more than one secret. requirements: an iterable
    of (product, key) or (product, key, purpose) tuples. Returns the concatenated HTML for every
    one NOT yet configured - '' if everything's already set."""
    parts = []
    for product, key, *rest in requirements:
        banner = missing_secret_banner_html(product, key, rest[0] if rest else '')
        if banner:
            parts.append(banner)
    return '\n'.join(parts)


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
    """Every secret expected but not set yet - (product, key, description, source) tuples, where
    source is 'defaults' (curated, conf/secrets_defaults.json) or 'requested' (self-registered by
    a script's get_secret() call, DISCOVERED_PATH). Curated entries win on a duplicate - their
    description is hand-written - but a script that registered itself is still named alongside."""
    store = load_store()
    discovered = load_discovered()

    def requested_by_text(product, key):
        requesters = discovered.get(product, {}).get(key, {}).get('requested_by', {})
        return '; '.join(f'{script}: {purpose}' if purpose else script
                         for script, purpose in sorted(requesters.items()))

    result, seen = [], set()
    for product, key, description in load_known_integrations():
        if (product, key) in seen:
            continue
        seen.add((product, key))
        result.append((product, key, description, 'defaults'))
    for product, keys in discovered.items():
        for key in keys:
            if (product, key) not in seen:
                seen.add((product, key))
                result.append((product, key, 'requested by ' + requested_by_text(product, key),
                               'requested'))
    return [entry for entry in result if entry[1] not in store.get(entry[0], {})]


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
    if len(args) not in (2, 3):
        print('Usage: secrets_store.py get <product> <key> [purpose]', file=sys.stderr)
        sys.exit(1)
    purpose = args[2] if len(args) == 3 else ''
    value = get_secret(args[0], args[1], purpose)
    if value is None:
        print(f'No secret set for {args[0]}.{args[1]} - a placeholder has been added; set its '
              f'value via Secrets Manager.', file=sys.stderr)
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
    for product, key, description, _source in list_known_placeholders():
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
