#!/usr/bin/env python3
# Name: view_inventory.py
# Version: 1.2.0
# Description: Renders the persistent /app/data/network_inventory.json as a
#              styled HTML page (label, vendor, last-seen IP, first/last
#              seen). Colours/fonts match Script-Server's own theme
#              (web-src/src/assets/css/shared.css's --primary-color,
#              --surface-color etc.) since output_format html_iframe
#              renders in an isolated document that doesn't inherit the
#              app's stylesheet. Run standalone (./view_inventory.py) or
#              from Script-Server.

import html
import json
import os

INVENTORY_PATH = '/app/data/network_inventory.json'

# Matches web-src/src/assets/css/shared.css's :root variables (light theme
# defaults) so this page looks like part of the app rather than a bare table.
STYLE = """
<style>
  :root {
    --primary-color: #26a69a;
    --primary-color-dark: #00796b;
    --font-on-primary-color-main: rgba(255, 255, 255, 0.87);
    --surface-color: #eeeeee;
    --background-color: #ffffff;
    --background-color-slight-emphasis: rgba(0, 0, 0, 0.025);
    --hover-color: rgba(0, 0, 0, 0.04);
    --separator-color: #dddddd;
    --font-color-main: rgba(0, 0, 0, 0.87);
    --font-color-medium: rgba(0, 0, 0, 0.56);
    --shadow-4dp: 0 4px 5px 0 rgba(0, 0, 0, 0.14), 0 1px 10px 0 rgba(0, 0, 0, 0.12),
      0 2px 4px -1px rgba(0, 0, 0, 0.20);
  }
  body {
    margin: 0;
    padding: 24px;
    background: var(--surface-color);
    color: var(--font-color-main);
    font-family: "Roboto", "Helvetica Neue", Arial, sans-serif;
  }
  .card {
    background: var(--background-color);
    border-radius: 2px;
    box-shadow: var(--shadow-4dp);
    max-width: 100%;
  }
  .card h2 {
    margin: 0;
    padding: 16px 20px;
    background: var(--primary-color);
    color: var(--font-on-primary-color-main);
    font-size: 1.3rem;
    font-weight: 400;
    border-radius: 2px 2px 0 0;
  }
  .table-scroll {
    overflow-x: auto;
    border-radius: 0 0 2px 2px;
  }
  table {
    border-collapse: collapse;
    width: 100%;
  }
  th, td {
    text-align: left;
    padding: 10px 20px;
    white-space: nowrap;
  }
  th {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--font-color-medium);
    border-bottom: 1px solid var(--separator-color);
  }
  tbody tr:nth-child(odd) {
    background: var(--background-color-slight-emphasis);
  }
  tbody tr:hover {
    background: var(--hover-color);
  }
  td {
    border-bottom: 1px solid var(--separator-color);
    font-size: 0.9rem;
  }
  .label-chip {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    background: var(--primary-color);
    color: var(--font-on-primary-color-main);
    font-size: 0.85rem;
  }
  .label-unset {
    color: var(--font-color-medium);
    font-style: italic;
  }
  .mac {
    font-family: "Roboto Mono", "Courier New", monospace;
    color: var(--font-color-medium);
  }
  .empty-state {
    padding: 40px 20px;
    text-align: center;
    color: var(--font-color-medium);
  }
</style>
"""


def render_empty(message):
    print(STYLE)
    print('<div class="card"><h2>Network Device Inventory</h2>')
    print(f'<div class="empty-state">{html.escape(message)}</div></div>')


def main():
    if not os.path.exists(INVENTORY_PATH):
        render_empty('No inventory yet - run Network Scanner first.')
        return

    with open(INVENTORY_PATH) as f:
        inventory = json.load(f)

    if not inventory:
        render_empty('Inventory is empty.')
        return

    rows = sorted(inventory.values(), key=lambda e: (e.get('label') or '~zzz', e.get('mac', '')))

    print(STYLE)
    print('<div class="card">')
    print(f'<h2>Network Device Inventory ({len(rows)} device{"s" if len(rows) != 1 else ""})</h2>')
    print('<div class="table-scroll">')
    print('<table><thead><tr>' + ''.join(
        f'<th>{h}</th>' for h in ['Label', 'MAC', 'Vendor', 'Last IP', 'Hostname', 'First Seen', 'Last Seen']
    ) + '</tr></thead><tbody>')

    for entry in rows:
        raw_label = entry.get('label') or ''
        if raw_label:
            label_html = f'<span class="label-chip">{html.escape(raw_label)}</span>'
        else:
            label_html = '<span class="label-unset">(unlabeled)</span>'

        mac_html = f'<span class="mac">{html.escape(entry.get("mac", ""))}</span>'

        other_cells = [
            entry.get('vendor', 'Unknown'),
            entry.get('last_ip', ''),
            entry.get('hostname', ''),
            entry.get('first_seen', ''),
            entry.get('last_seen', ''),
        ]
        cells_html = [label_html, mac_html] + [html.escape(str(c)) for c in other_cells]
        print('<tr>' + ''.join(f'<td>{c}</td>' for c in cells_html) + '</tr>')

    print('</tbody></table></div></div>')


if __name__ == '__main__':
    main()
