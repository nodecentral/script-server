#!/usr/bin/env python3
# Name: migrate_runners_v2.py
# Version: 1.0.0
# Description: One-off migration of EXISTING runner files to the v2 layout, for an install whose
#              conf/runners pre-date v2 (the Docker image never overwrites runners - they're user
#              content, seeded only if missing). Edits files in place, minimally (only the lines
#              it changes - no reformatting), and only when they're valid JSON afterwards:
#                - Import from Gitea, Install Package, Secrets Manager -> "placement": "settings"
#                  (admin-only Settings tabs). Their "group" is left alone, so a v1 instance
#                  sharing these files still shows them where it always did.
#                - every other runner in the "Admin" group -> "category": "Script Server" and
#                  "group": "Demo" (examples) or "Tools" (real utilities). Admin-group runners this
#                  script doesn't recognise (e.g. ones imported from another repo) go to "Tools".
#              v1 ignores "placement"/"category", but DOES show the new group names (Demo/Tools
#              instead of Admin) if it shares the same runner files.
#              Runner "_version"s are not changed - this edits where a script shows up, not what
#              it does. Dry run by default; pass --apply to write.
#
# Usage on the NAS (from a checkout of this repo, against the running v2 container):
#   docker exec -i script-server-v2 python3 - < tools/migrate_runners_v2.py            # dry run
#   docker exec -i script-server-v2 python3 - --apply < tools/migrate_runners_v2.py    # apply
# Or directly: python3 tools/migrate_runners_v2.py [--apply] [--runners-dir /app/conf/runners]

import argparse
import json
import os
import re
import sys

SETTINGS_RUNNERS = {'import_from_gitea', 'install_package', 'secrets_manager'}
DEMO_RUNNERS = {'hello_world', 'progress_demo', 'terminal_colors', 'confirm_gate', 'download_image',
                'file_info', 'disk_usage_chart'}
TOOLS_RUNNERS = {'secrets_viewer', 'secret_ingredients_check', 'motd', 'disk_usage', 'backup',
                 'notify', 'view_capabilities'}

CATEGORY = 'Script Server'
OLD_GROUP = 'admin'

NAME_LINE = re.compile(r'(\n([ \t]*)"name"\s*:[^\n]*\n)')


def insert_after_name(text, key, value):
    """Adds `"key": "value",` on its own line right after the top-level "name" line."""
    match = NAME_LINE.search(text)
    if not match:
        return None
    indent = match.group(2)
    line = f'{indent}{json.dumps(key)}: {json.dumps(value)},\n'
    return text[:match.end()] + line + text[match.end():]


def set_string_field(text, key, value):
    """Replaces the first `"key": "..."` string value, or inserts the field if missing."""
    pattern = re.compile(r'("' + re.escape(key) + r'"\s*:\s*)"(?:[^"\\]|\\.)*"')
    if pattern.search(text):
        return pattern.sub(lambda m: m.group(1) + json.dumps(value), text, count=1)
    return insert_after_name(text, key, value)


def plan(base_name, config):
    """Changes as an ordered list of (field, new value)."""
    group = str(config.get('group') or '').strip().lower()

    if base_name in SETTINGS_RUNNERS:
        if str(config.get('placement') or '').lower() == 'settings':
            return []
        return [('placement', 'settings')]

    if group != OLD_GROUP:
        return []

    new_group = 'Demo' if base_name in DEMO_RUNNERS else 'Tools'
    changes = []
    if config.get('category') != CATEGORY:
        changes.append(('category', CATEGORY))
    changes.append(('group', new_group))
    return changes


def main():
    parser = argparse.ArgumentParser(description='Move pre-v2 runners into the v2 layout.')
    parser.add_argument('--apply', action='store_true', help='write the changes (default: dry run)')
    parser.add_argument('--runners-dir', default='/app/conf/runners')
    args = parser.parse_args()

    if not os.path.isdir(args.runners_dir):
        sys.exit(f'No runners folder at {args.runners_dir}')

    print(('APPLYING' if args.apply else 'DRY RUN - nothing written, pass --apply to write')
          + f' - {args.runners_dir}\n', flush=True)

    changed = skipped = 0
    for filename in sorted(os.listdir(args.runners_dir)):
        if not filename.endswith('.json'):
            continue
        path = os.path.join(args.runners_dir, filename)
        base_name = os.path.splitext(filename)[0]

        try:
            with open(path, encoding='utf-8') as f:
                text = f.read()
            config = json.loads(text)
        except (OSError, ValueError) as e:
            print(f'  SKIP    {filename}: unreadable ({e})')
            skipped += 1
            continue
        if not isinstance(config, dict):
            continue

        changes = plan(base_name, config)
        if not changes:
            continue

        new_text = text
        for key, value in changes:
            new_text = (insert_after_name(new_text, key, value) if key == 'placement'
                        else set_string_field(new_text, key, value)) or None
            if new_text is None:
                break

        description = ', '.join(f'{key}={value!r}' for key, value in changes)
        try:
            if new_text is None:
                raise ValueError('no top-level "name" line to anchor the edit')
            json.loads(new_text)
        except ValueError as e:
            print(f'  SKIP    {filename}: would not be valid JSON after the edit ({e}) - edit by hand: {description}')
            skipped += 1
            continue

        print(f'  {"CHANGED" if args.apply else "CHANGE "} {filename}: {description}')
        if args.apply:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_text)
        changed += 1

    print(f'\n{changed} runner(s) {"changed" if args.apply else "to change"}, {skipped} skipped.')
    if changed and not args.apply:
        print('Re-run with --apply to write these changes.')
    elif changed:
        print('Reload the page - runners are re-read on every page load, no restart needed.')


if __name__ == '__main__':
    main()
