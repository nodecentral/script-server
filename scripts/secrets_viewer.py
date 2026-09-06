#!/usr/bin/env python3
# Name: secrets_viewer.py
# Version: 1.1.0
# Description: Renders the categorized secrets store (/app/data/secrets.json,
#              managed via Secrets Manager) as a styled HTML page - category,
#              key, and when it was last set. Never shows values, not even
#              partially - only a character-count hint. Colours/fonts match
#              Script-Server's own theme (web-src/src/assets/css/shared.css's
#              --primary-color, --surface-color etc.) since output_format
#              html_iframe renders in an isolated document that doesn't
#              inherit the app's stylesheet. Also lists known integrations
#              (see secrets_store.KNOWN_INTEGRATIONS) that don't have a value
#              set yet, so a missing secret is visible before a consuming
#              script fails on it. Run standalone (./secrets_viewer.py) or
#              from Script-Server.

import html
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from secrets_store import list_entries_metadata, list_known_placeholders  # noqa: E402

# Matches web-src/src/assets/css/shared.css's :root variables (light theme
# defaults) so this page looks like part of the app rather than a bare table.
STYLE = """
<style>
  :root {
    --primary-color: #26a69a;
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
  .intro {
    margin-bottom: 16px;
    font-size: 0.9rem;
    color: var(--font-color-medium);
  }
  details.group {
    background: var(--background-color);
    border-radius: 2px;
    box-shadow: var(--shadow-4dp);
    margin-bottom: 14px;
  }
  details.group summary {
    cursor: pointer;
    list-style: none;
    background: var(--primary-color);
    color: var(--font-on-primary-color-main);
    padding: 10px 20px;
    font-size: 1.1rem;
    font-weight: 400;
    border-radius: 2px;
  }
  details.group[open] summary {
    border-radius: 2px 2px 0 0;
  }
  details.group summary::-webkit-details-marker { display: none; }
  details.group summary::before {
    content: '\\25B6';
    display: inline-block;
    margin-right: 10px;
    transition: transform 0.15s;
  }
  details.group[open] summary::before {
    transform: rotate(90deg);
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
  tbody tr:nth-child(odd) { background: var(--background-color-slight-emphasis); }
  tbody tr:hover { background: var(--hover-color); }
  td {
    border-bottom: 1px solid var(--separator-color);
    font-size: 0.9rem;
  }
  .mono { font-family: "Roboto Mono", "Courier New", monospace; }
  .set-chip {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    background: var(--primary-color);
    color: var(--font-on-primary-color-main);
    font-size: 0.85rem;
  }
  .empty-state {
    padding: 40px 20px;
    text-align: center;
    color: var(--font-color-medium);
  }
  .missing { color: #c62828; font-weight: 500; }
  .unset-chip {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    background: #c62828;
    color: rgba(255, 255, 255, 0.87);
    font-size: 0.85rem;
  }
</style>
"""


def render_empty(message):
    print(STYLE)
    print('<div class="intro">Secrets Viewer</div>')
    print(f'<div class="empty-state">{html.escape(message)}</div>')


def render_placeholders_group(placeholders):
    print(f'<details class="group" open><summary>Not Yet Configured ({len(placeholders)})</summary>')
    print('<div class="table-scroll"><table><thead><tr>'
          '<th>Category</th><th>Key</th><th>Value</th><th>Needed For</th></tr></thead><tbody>')
    for category, key, description in placeholders:
        print(
            '<tr>'
            f'<td class="mono">{html.escape(category)}</td>'
            f'<td class="mono">{html.escape(key)}</td>'
            f'<td><span class="unset-chip">not set</span></td>'
            f'<td>{html.escape(description)}</td>'
            '</tr>'
        )
    print('</tbody></table></div></details>')


def main():
    entries = list_entries_metadata()
    placeholders = list_known_placeholders()

    if not entries and not placeholders:
        render_empty('No secrets set yet - use Secrets Manager to add one.')
        return

    groups = {}
    for category, key, updated_at, length in entries:
        groups.setdefault(category, []).append((key, updated_at, length))

    total = len(entries)
    print(STYLE)
    intro = (f'Secrets Viewer - {total} entr{"y" if total == 1 else "ies"} '
             f'across {len(groups)} categor{"y" if len(groups) == 1 else "ies"}.')
    if placeholders:
        intro += (f' <span class="missing">{len(placeholders)} known integration(s) '
                  'not yet configured.</span>')
    intro += ' Values are never shown here - use Secrets Manager to change one.'
    print(f'<div class="intro">{intro}</div>')

    if placeholders:
        render_placeholders_group(placeholders)

    for category in sorted(groups.keys()):
        rows = groups[category]
        print(f'<details class="group" open><summary>{html.escape(category)} ({len(rows)})</summary>')
        print('<div class="table-scroll"><table><thead><tr>'
              '<th>Key</th><th>Value</th><th>Last Set</th></tr></thead><tbody>')
        for key, updated_at, length in rows:
            print(
                '<tr>'
                f'<td class="mono">{html.escape(key)}</td>'
                f'<td><span class="set-chip">set &middot; {length} chars</span></td>'
                f'<td>{html.escape(updated_at)}</td>'
                '</tr>'
            )
        print('</tbody></table></div></details>')


if __name__ == '__main__':
    main()
