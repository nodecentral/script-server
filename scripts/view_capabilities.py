#!/usr/bin/env python3
# Name: view_capabilities.py
# Version: 1.0.0
# Description: Shows what's baked into the image (conf/capabilities.json),
#              what's available to install, and what's been installed at
#              runtime this session (/app/data/installed_extras.json).
#              Rendered with output_format html (sanitised). Run standalone
#              (./view_capabilities.py) or from Script-Server.

import html
import json
import os

MANIFEST_PATH = '/app/conf/capabilities.json'
INSTALLED_PATH = '/app/data/installed_extras.json'


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default


def render_table(title, rows, columns):
    print(f'<h3>{html.escape(title)}</h3>')
    if not rows:
        print('<p><em>None</em></p>')
        return
    print('<table style="border-collapse: collapse; width: 100%; margin-bottom: 1.5em;">')
    print('<tr>' + ''.join(
        f'<th style="text-align:left; border-bottom: 2px solid #ccc; padding: 4px 8px;">{html.escape(c)}</th>'
        for c in columns
    ) + '</tr>')
    for row in rows:
        print('<tr>' + ''.join(
            f'<td style="padding: 4px 8px; border-bottom: 1px solid #eee;">{html.escape(str(cell))}</td>'
            for cell in row
        ) + '</tr>')
    print('</table>')


def main():
    manifest = load_json(MANIFEST_PATH, {})
    installed_extras = load_json(INSTALLED_PATH, {})

    preinstalled = manifest.get('preinstalled', {})
    optional = manifest.get('optional', {})

    render_table(
        'Preinstalled (apt)',
        [(p['name'], p.get('description', '')) for p in preinstalled.get('apt', [])],
        ['Package', 'Description'],
    )
    render_table(
        'Preinstalled (pip)',
        [(p['name'], p.get('description', '')) for p in preinstalled.get('pip', [])],
        ['Package', 'Description'],
    )
    render_table(
        'Preinstalled (other)',
        [(p['name'], p.get('description', '')) for p in preinstalled.get('other', [])],
        ['Package', 'Description'],
    )

    installed_names = set(installed_extras.keys())
    optional_rows = []
    for p in optional.get('apt', []):
        key = f"apt:{p['name']}"
        status = 'Installed (runtime)' if key in installed_names else 'Available'
        optional_rows.append(('apt', p['name'], p.get('description', ''), status))
    for p in optional.get('pip', []):
        key = f"pip:{p['name']}"
        status = 'Installed (runtime)' if key in installed_names else 'Available'
        optional_rows.append(('pip', p['name'], p.get('description', ''), status))

    render_table('Optional', optional_rows, ['Type', 'Package', 'Description', 'Status'])


if __name__ == '__main__':
    main()
