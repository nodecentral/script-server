#!/usr/bin/env python3
# Name: motd.py
# Version: 2.0.1
# Description: Script Ingredients Check - audits every runner under
#              conf/runners/, grouped by their "group" field, confirming
#              each one's script_path and preload_script (if any) actually
#              exist on disk. Rendered as a themed, collapsible-by-group
#              HTML table (output_format html_iframe). The preload banner
#              for this runner lives separately at scripts/preload/motd.py
#              (system stats - a genuinely different job from this audit,
#              per CLAUDE.md's preload_script guidance). Run standalone
#              (./motd.py) or from Script-Server.

import html
import json
import os

RUNNERS_DIR = '/app/conf/runners'

# Script-Server's own root inside this image - a relative working_directory (e.g. "scripts",
# as opposed to this repo's own convention of always using "/app/scripts") is resolved by
# Script-Server against this directory, not against whatever cwd this audit script happens to
# be running from - so the same base must be used here to get an accurate existence check.
SERVER_ROOT = '/app'

STYLE = """
<style>
  body {
    margin: 0;
    padding: 20px;
    background: #eeeeee;
    color: rgba(0,0,0,0.87);
    font-family: "Roboto", "Helvetica Neue", Arial, sans-serif;
  }
  .intro {
    margin-bottom: 16px;
    font-size: 0.9rem;
    color: #555;
  }
  details.group {
    background: #ffffff;
    border-radius: 4px;
    box-shadow: 0 4px 5px 0 rgba(0,0,0,0.14), 0 1px 10px 0 rgba(0,0,0,0.12), 0 2px 4px -1px rgba(0,0,0,0.20);
    margin-bottom: 14px;
  }
  details.group summary {
    cursor: pointer;
    list-style: none;
    background: #26a69a;
    color: white;
    padding: 10px 16px;
    font-size: 1rem;
    font-weight: 500;
    border-radius: 4px;
  }
  details.group[open] summary {
    border-radius: 4px 4px 0 0;
  }
  details.group summary::-webkit-details-marker { display: none; }
  .table-scroll {
    overflow-x: auto;
    border-radius: 0 0 4px 4px;
  }
  details.group summary::before {
    content: '\\25B6';
    display: inline-block;
    margin-right: 8px;
    transition: transform 0.15s;
  }
  details.group[open] summary::before {
    transform: rotate(90deg);
  }
  table {
    border-collapse: collapse;
    width: 100%;
  }
  th, td {
    text-align: left;
    padding: 8px 16px;
    font-size: 0.85rem;
  }
  th {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #757575;
    border-bottom: 1px solid #ddd;
  }
  tbody tr:nth-child(odd) { background: rgba(0,0,0,0.025); }
  tbody tr:hover { background: rgba(0,0,0,0.04); }
  td { border-bottom: 1px solid #eee; }
  .mono { font-family: "Roboto Mono", "Courier New", monospace; font-size: 0.82rem; }
  .missing { color: #c62828; font-weight: 500; }
  .na { color: #9e9e9e; }
  .desc {
    display: block;
    max-width: 320px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #555;
  }
  .name-col { white-space: nowrap; }
</style>
"""


def load_runners():
    runners = []
    if not os.path.isdir(RUNNERS_DIR):
        return runners
    for filename in sorted(os.listdir(RUNNERS_DIR)):
        if not filename.endswith('.json'):
            continue
        path = os.path.join(RUNNERS_DIR, filename)
        try:
            with open(path) as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            config = None
        runners.append((filename, config))
    return runners


def resolve_main_script(config):
    script_path = config.get('script_path', '')
    if not script_path:
        return '', False

    working_directory = config.get('working_directory', '')
    if os.path.isabs(script_path):
        full_path = script_path
    else:
        base_dir = working_directory or SERVER_ROOT
        if not os.path.isabs(base_dir):
            base_dir = os.path.join(SERVER_ROOT, base_dir)
        full_path = os.path.join(base_dir, script_path)

    return script_path, os.path.isfile(full_path)


def resolve_preload(config):
    preload = config.get('preload_script')
    if not preload or not preload.get('script'):
        return None, None

    raw = preload['script'].strip()
    first_token = raw.split()[0] if raw else ''

    looks_like_file = first_token.startswith('/') or first_token.endswith(('.sh', '.py', '.lua'))
    if not looks_like_file:
        return '(inline command)', None

    full_path = first_token if os.path.isabs(first_token) else os.path.join(SERVER_ROOT, first_token)
    return os.path.basename(first_token), os.path.isfile(full_path)


def build_report():
    groups = {}
    for filename, config in load_runners():
        if config is None:
            groups.setdefault('(invalid JSON)', []).append({
                'name': filename, 'description': 'Failed to parse this runner file',
                'runner_file': filename, 'script_file': '', 'script_exists': False,
                'preload_file': None, 'preload_exists': None,
            })
            continue

        group = config.get('group') or 'Ungrouped'
        script_file, script_exists = resolve_main_script(config)
        preload_file, preload_exists = resolve_preload(config)

        groups.setdefault(group, []).append({
            'name': config.get('name', filename),
            'description': config.get('description', ''),
            'runner_file': filename,
            'script_file': script_file,
            'script_exists': script_exists,
            'preload_file': preload_file,
            'preload_exists': preload_exists,
        })

    return groups


def file_cell(filename, exists):
    if not filename:
        return '<span class="na">&mdash;</span>'
    escaped = html.escape(filename)
    if exists is None:
        return f'<span class="mono na">{escaped}</span>'
    if exists:
        return f'<span class="mono">{escaped}</span>'
    return f'<span class="mono missing">{escaped} (missing!)</span>'


def render_group_table(entries):
    rows = []
    for entry in sorted(entries, key=lambda e: e['name'].lower()):
        description = entry['description']
        rows.append(
            '<tr>'
            f'<td class="name-col">{html.escape(entry["name"])}</td>'
            f'<td><span class="desc" title="{html.escape(description)}">{html.escape(description)}</span></td>'
            f'<td class="mono">{html.escape(entry["runner_file"])}</td>'
            f'<td>{file_cell(entry["script_file"], entry["script_exists"])}</td>'
            f'<td>{file_cell(entry["preload_file"], entry["preload_exists"])}</td>'
            '</tr>'
        )

    headers = ['Runner', 'Description', 'Runner File', 'Script File', 'Preload File']
    header_html = ''.join(f'<th>{h}</th>' for h in headers)
    return (
        '<div class="table-scroll"><table><thead><tr>'
        f'{header_html}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def render_html(groups):
    total_runners = sum(len(entries) for entries in groups.values())
    total_missing = sum(
        1 for entries in groups.values() for e in entries
        if e['script_exists'] is False or e['preload_exists'] is False
    )

    parts = [STYLE]
    summary_line = f'{total_runners} runner(s) across {len(groups)} group(s).'
    if total_missing:
        summary_line += f' <span class="missing">{total_missing} missing file(s) found.</span>'
    else:
        summary_line += ' All script/preload files present.'
    parts.append(f'<div class="intro">Script Ingredients Check - {summary_line}</div>')

    for group_name in sorted(groups.keys()):
        entries = groups[group_name]
        parts.append(
            f'<details class="group" open>'
            f'<summary>{html.escape(group_name)} ({len(entries)})</summary>'
            f'{render_group_table(entries)}'
            f'</details>'
        )

    return '\n'.join(parts)


def main():
    groups = build_report()
    print(render_html(groups))


if __name__ == '__main__':
    main()
