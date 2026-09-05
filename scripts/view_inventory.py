#!/usr/bin/env python3
# Name: view_inventory.py
# Version: 1.0.0
# Description: Renders the persistent /app/data/network_inventory.json as
#              an HTML table (label, vendor, last-seen IP, first/last
#              seen). Rendered with output_format html (sanitised). Run
#              standalone (./view_inventory.py) or from Script-Server.

import html
import json
import os

INVENTORY_PATH = '/app/data/network_inventory.json'


def main():
    if not os.path.exists(INVENTORY_PATH):
        print('<p>No inventory yet - run the Network Scanner first.</p>')
        return

    with open(INVENTORY_PATH) as f:
        inventory = json.load(f)

    if not inventory:
        print('<p>Inventory is empty.</p>')
        return

    rows = sorted(inventory.values(), key=lambda e: (e.get('label') or '~zzz', e.get('mac', '')))

    print('<table style="border-collapse: collapse; width: 100%;">')
    headers = ['Label', 'MAC', 'Vendor', 'Last IP', 'Hostname', 'First Seen', 'Last Seen']
    print('<tr>' + ''.join(
        f'<th style="text-align:left; border-bottom: 2px solid #ccc; padding: 4px 8px;">{h}</th>'
        for h in headers
    ) + '</tr>')

    for entry in rows:
        raw_label = entry.get('label') or ''
        label_html = html.escape(raw_label) if raw_label else '<em>(unlabeled)</em>'
        other_cells = [
            entry.get('mac', ''),
            entry.get('vendor', 'Unknown'),
            entry.get('last_ip', ''),
            entry.get('hostname', ''),
            entry.get('first_seen', ''),
            entry.get('last_seen', ''),
        ]
        cells_html = [label_html] + [html.escape(str(c)) for c in other_cells]
        print('<tr>' + ''.join(
            f'<td style="padding: 4px 8px; border-bottom: 1px solid #eee;">{c}</td>' for c in cells_html
        ) + '</tr>')

    print('</table>')


if __name__ == '__main__':
    main()
