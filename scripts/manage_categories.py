#!/usr/bin/env python3
# Name: manage_categories.py
# Version: 1.0.0
# Description: Categories (Settings tab) - review the sidebar's categories and change them: add
#              one, change its icon, move it, remove an unused one, or give categories still on
#              the generic icon the image's own icon. Edits conf/categories.json, the one place
#              category icons live; keeps a .bak of the previous file on every change.
#
# Standalone: python3 manage_categories.py [--html | --choices | --icons]
#             PARAM_ACTION=icon PARAM_CATEGORY=Energy PARAM_ICON=flash_on python3 manage_categories.py

import argparse
import difflib
import glob
import html
import json
import os
import re
import shutil
import sys

CONF_DIR = os.environ.get('SS_CONF_DIR', '/app/conf')
CATEGORIES = os.path.join(CONF_DIR, 'categories.json')
RUNNERS_DIR = os.path.join(CONF_DIR, 'runners')
DEFAULTS_DIR = os.environ.get('DEFAULTS_DIR', '/app/defaults')
IMAGE_CATEGORIES = os.path.join(DEFAULTS_DIR, 'conf', 'categories.json')
CODEPOINTS = os.path.join(DEFAULTS_DIR, 'material-icons-codepoints')
STATE = os.environ.get('SS_IMPORT_STATE', '/app/data/gitea_import_state.json')
WEB_DIR = os.environ.get('SS_WEB_DIR', '/app/web')

PICK = '-- pick a category --'
LIGATURE = re.compile(r'^[a-z0-9_]+$')   # the sidebar's rule (isLigatureIcon in categories.js)

ACTIONS = {
    'view': 'List categories (read-only)',
    'icon': "Change a category's icon (changes categories.json)",
    'add': 'Add a category (changes categories.json)',
    'move': 'Move a category (changes categories.json)',
    'remove': 'Remove an unused category (changes categories.json)',
    'defaults': "Give generic-icon categories the image's icon (changes categories.json)",
}


class Refused(Exception):
    pass


def load_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def serialize(content):
    """The layout CategoryService writes (src/config/category_service.py): json with indent 2,
    each category on one line, so a change shows as a one-line diff."""
    lines, items = ['{'], list(content.items())
    for index, (key, value) in enumerate(items):
        comma = ',' if index < len(items) - 1 else ''
        key_json = json.dumps(key, ensure_ascii=False)
        if key == 'categories' and isinstance(value, list) and value:
            entries = [json.dumps(e, ensure_ascii=False) for e in value]
            lines.append('  ' + key_json + ': [')
            lines += ['    ' + e + (',' if i < len(entries) - 1 else '') for i, e in enumerate(entries)]
            lines.append('  ]' + comma)
        else:
            lines.append('  ' + key_json + ': ' + json.dumps(value, ensure_ascii=False, indent=2).replace('\n', '\n  ') + comma)
    return '\n'.join(lines + ['}']) + '\n'


def read_categories():
    content = load_json(CATEGORIES)
    if not isinstance(content, dict):
        raise Refused(f'{CATEGORIES} is missing or not valid JSON - fix or delete it (the image re-creates it on restart).')
    content.setdefault('categories', [])
    return content


def write_categories(content):
    if os.path.exists(CATEGORIES):
        shutil.copy2(CATEGORIES, CATEGORIES + '.bak')
    tmp = CATEGORIES + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(serialize(content))
    os.replace(tmp, CATEGORIES)


def find(content, name):
    for index, entry in enumerate(content['categories']):
        if isinstance(entry, dict) and str(entry.get('name', '')).strip().lower() == name.strip().lower():
            return index, entry
    return None, None


def known_ligatures():
    try:
        with open(CODEPOINTS, encoding='utf-8') as f:
            return {line.split()[0] for line in f if line.strip()}
    except OSError:
        return None


def image_icons():
    content = load_json(IMAGE_CATEGORIES, {}) or {}
    return {str(e.get('name', '')).lower(): e.get('icon') for e in content.get('categories', []) if isinstance(e, dict)}


def usage():
    """{lowercased category: [(runner name, repo or '')]} from conf/runners and the import state."""
    repos = {}
    for key, entry in (load_json(STATE, {}) or {}).items():
        if isinstance(entry, dict):
            for rel in entry.get('runners') or []:
                repos.setdefault(os.path.basename(rel), key.partition('|')[2].replace('|', '/'))
    used = {}
    for path in sorted(glob.glob(os.path.join(RUNNERS_DIR, '*.json'))):
        runner = load_json(path)
        if isinstance(runner, dict) and str(runner.get('category') or '').strip():
            used.setdefault(runner['category'].strip().lower(), []).append(
                (runner.get('name') or os.path.basename(path)[:-5], repos.get(os.path.basename(path), '')))
    return used


def check_icon(icon):
    icon = (icon or '').strip()
    if not icon:
        raise Refused('Icon is empty: type a Material Icons name (e.g. flash_on) or one character (e.g. £).')
    if LIGATURE.match(icon):
        names = known_ligatures()
        if names is not None and icon not in names:
            close = difflib.get_close_matches(icon, sorted(names), n=5, cutoff=0.6)
            hint = f' Close matches: {", ".join(close)}.' if close else ''
            raise Refused(f'"{icon}" isn\'t in the bundled icon font, so it would show as a blank square.{hint}')
    elif len(icon) > 2:
        raise Refused(f'"{icon}" is text, and only one character fits the 24-pixel icon box. '
                      'Use one character (e.g. £ or an emoji) or a Material Icons name.')
    return icon


def position_index(text, length):
    text = (text or '').strip()
    if not text:
        return None
    if not text.isdigit() or not 1 <= int(text) <= length:
        raise Refused(f'Position must be a number from 1 to {length}.')
    return int(text) - 1


def apply(action, category, new_name, icon, position):
    if action == 'view':
        return None
    content = read_categories()
    cats = content['categories']
    if action == 'defaults':
        generic = str(content.get('default_icon') or 'label')
        suggestions, changed = image_icons(), []
        for entry in cats:
            suggested = suggestions.get(str(entry.get('name', '')).lower())
            if entry.get('icon') in (None, '', generic) and suggested and suggested != generic:
                entry['icon'] = suggested
                changed.append(f'{entry["name"]} → {suggested}')
        if not changed:
            return 'Nothing to change: every category the image knows already has an icon other than the generic one.'
        write_categories(content)
        return 'Updated ' + ', '.join(changed) + '.'

    if action == 'add':
        name = (new_name or '').strip()
        if not name:
            raise Refused('Type the new category\'s name in New category.')
        if find(content, name)[1]:
            raise Refused(f'"{name}" already exists.')
        entry = {'name': name, 'icon': check_icon(icon or image_icons().get(name.lower()) or content.get('default_icon') or 'label')}
        index = position_index(position, len(cats) + 1)
        cats.insert(len(cats) if index is None else index, entry)
        write_categories(content)
        return f'Added {name} (icon {entry["icon"]}) at position {cats.index(entry) + 1}. Scripts join it with "category": "{name}" in their runner.'

    if not category or category == PICK:
        raise Refused('Pick a category first.')
    index, entry = find(content, category)
    if entry is None:
        raise Refused(f'"{category}" isn\'t in categories.json any more - reload the page.')

    if action == 'icon':
        old, entry['icon'] = entry.get('icon'), check_icon(icon)
        write_categories(content)
        return f'{entry["name"]}: icon {old} → {entry["icon"]}.'
    if action == 'move':
        target = position_index(position, len(cats))
        if target is None:
            raise Refused('Type the new position (1 = top of the rail).')
        cats.insert(target, cats.pop(index))
        write_categories(content)
        return f'Moved {entry["name"]} to position {target + 1}.'
    if action == 'remove':
        users = usage().get(entry['name'].lower(), [])
        if users:
            names = ', '.join(n for n, _ in users[:5]) + (' and more' if len(users) > 5 else '')
            raise Refused(f'{len(users)} script(s) use {entry["name"]} ({names}), so it would come straight back. '
                          'Change or remove those scripts first.')
        cats.pop(index)
        write_categories(content)
        return f'Removed {entry["name"]}.'
    raise Refused(f'Unknown action "{action}".')


def font_face():
    fonts = sorted(glob.glob(os.path.join(WEB_DIR, 'fonts', 'MaterialIcons-Regular*.woff2')))
    if not fonts:
        return ''
    return (f"@font-face{{font-family:'Material Icons';src:url('/fonts/{os.path.basename(fonts[0])}') format('woff2')}}"
            ".mi{font-family:'Material Icons';font-size:24px;line-height:24px;font-feature-settings:'liga'}")


def table_html():
    e = html.escape
    content = load_json(CATEGORIES, {}) or {}
    cats = [c for c in content.get('categories', []) if isinstance(c, dict)]
    generic = str(content.get('default_icon') or 'label')
    names, suggestions, used = known_ligatures(), image_icons(), usage()
    rows = []
    for number, entry in enumerate(cats, 1):
        icon = str(entry.get('icon') or generic)
        users = used.get(str(entry.get('name', '')).lower(), [])
        notes = []
        suggested = suggestions.get(str(entry.get('name', '')).lower())
        if icon == generic and suggested and suggested != generic:
            notes.append(f'generic icon - the image uses <b>{e(suggested)}</b>')
        if LIGATURE.match(icon) and names is not None and icon not in names:
            notes.append('<span class="bad">not in the icon font: shows blank</span>')
        if not users:
            notes.append('no scripts use it')
        repos = sorted({r for _, r in users if r})
        shown = f'<span class="box mi">{e(icon)}</span>' if LIGATURE.match(icon) else f'<span class="box tx">{e(icon)}</span>'
        rows.append(f'<tr><td>{number}</td><td>{shown}</td><td><b>{e(str(entry.get("name")))}</b></td>'
                    f'<td><code>{e(icon)}</code></td><td>{len(users)}</td><td>{e(", ".join(repos)) or "-"}</td>'
                    f'<td>{"; ".join(notes)}</td></tr>')
    return f"""<style>{font_face()}
body{{font-family:Roboto,-apple-system,'Segoe UI',sans-serif;font-size:13px;color:rgba(0,0,0,.87);margin:0}}
table{{border-collapse:collapse;margin-top:6px}}td,th{{padding:3px 10px 3px 0;text-align:left;vertical-align:middle}}
th{{color:rgba(0,0,0,.56);font-weight:500;border-bottom:1px solid #ddd}}
.box{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;overflow:hidden;
background:#3949ab;color:#fff;border-radius:4px}}.tx{{font-size:20px;font-weight:500}}
.bad{{color:#c62828}}code{{color:#0097a7}}</style>
<div>{len(cats)} categories, in sidebar order. Icons are drawn as the sidebar draws them. A script joins one with
<code>"category": "Name"</code> in its runner; a name nobody listed is added automatically.</div>
<table><tr><th>#</th><th>Icon</th><th>Category</th><th>Icon value</th><th>Scripts</th><th>From</th><th>Notes</th></tr>
{''.join(rows)}</table>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--html', action='store_true', help='print the table only (the banner)')
    parser.add_argument('--choices', action='store_true', help='Category dropdown lines')
    parser.add_argument('--icons', action='store_true', help='every icon name in the bundled font')
    args, _unknown = parser.parse_known_args()

    if args.choices:   # a values script: always exit 0
        content = load_json(CATEGORIES, {}) or {}
        print(PICK)
        for entry in content.get('categories', []):
            if isinstance(entry, dict) and entry.get('name'):
                print(entry['name'])
        return 0
    if args.icons:
        print('\n'.join(sorted(known_ligatures() or [])))
        return 0
    if args.html:
        print(table_html(), flush=True)
        return 0

    action = os.environ.get('PARAM_ACTION', 'view')
    try:
        message = apply(action, os.environ.get('PARAM_CATEGORY', ''), os.environ.get('PARAM_NEW_CATEGORY', ''),
                        os.environ.get('PARAM_ICON', ''), os.environ.get('PARAM_POSITION', ''))
        status = '' if message is None else f'<div class="ok">OK {html.escape(message)} Reload the page to see the sidebar change.</div>'
        code = 0
    except Refused as error:
        status, code = f'<div class="err">Nothing changed: {html.escape(str(error))}</div>', 1
    print('<style>.ok{background:#e8f5e9;border-left:4px solid #2e7d32;padding:8px;margin-bottom:8px}'
          '.err{background:#ffebee;border-left:4px solid #c62828;padding:8px;margin-bottom:8px}</style>'
          + status + table_html(), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
