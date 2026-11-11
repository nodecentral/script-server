"""
Sidebar categories - the top level of the user view's Category > Group > Script hierarchy.

A runner names its category with a plain `"category": "Finance"` field. Everything about how a
category LOOKS (its icon, its position in the rail) lives in one central file,
conf/categories.json, so scripts imported from different Gitea repos into the same category can
never disagree about its icon.

conf/categories.json is user content (seeded fill-if-missing by the Docker entrypoint, never
overwritten by an image upgrade), and this service also writes to it: whenever a runner uses a
category the file doesn't know yet - a script created through the admin form, a runner arriving
via Import from Gitea, a file copied in by hand - the category is appended with the default icon
the next time the script list is loaded. An admin can then change that icon in the file; nothing
here ever changes or removes an entry that already exists.

Category names match case-insensitively ("finance" in a runner lands in "Finance"), and the
spelling in categories.json is the one shown, so a casing slip in one repo doesn't split a
category in two.
"""

import json
import logging
import os
import threading
from typing import Iterable, List, Optional

LOGGER = logging.getLogger('script_server.category_service')

CATEGORIES_FILE = 'categories.json'

# Material Icons ligature names - checked against the bundled material-design-icons@3.0.1 font
# (see CLAUDE.md's note on invalid icon names). Any icon value that isn't a lowercase ligature
# name is rendered as plain text instead, which is how "£" works for Finance.
FALLBACK_DEFAULT_ICON = 'label'
FALLBACK_UNCATEGORISED = {'name': 'Uncategorised', 'icon': 'label_outline'}


def _normalize_name(name):
    if name is None:
        return None
    name = str(name).strip()
    return name if name else None


def _serialize(content):
    """json.dumps(indent=2), except each entry of the 'categories' list stays on one line - the
    hand-edited layout the file ships with, so an automatic append doesn't reflow the whole file
    and the git/NAS diff shows just the added line."""
    lines = ['{']
    items = list(content.items())
    for index, (key, value) in enumerate(items):
        comma = ',' if index < len(items) - 1 else ''
        key_json = json.dumps(key, ensure_ascii=False)
        if (key == 'categories') and isinstance(value, list) and value:
            entries = [json.dumps(entry, ensure_ascii=False) for entry in value]
            lines.append('  ' + key_json + ': [')
            lines.extend('    ' + entry + (',' if i < len(entries) - 1 else '') for i, entry in enumerate(entries))
            lines.append('  ]' + comma)
        else:
            value_json = json.dumps(value, ensure_ascii=False, indent=2).replace('\n', '\n  ')
            lines.append('  ' + key_json + ': ' + value_json + comma)
    lines.append('}')
    return '\n'.join(lines) + '\n'


class CategoryService:
    def __init__(self, conf_folder):
        self._path = os.path.join(conf_folder, CATEGORIES_FILE)
        self._lock = threading.Lock()

    def _read_file(self) -> Optional[dict]:
        if not os.path.exists(self._path):
            return None

        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                content = json.load(f)
            if not isinstance(content, dict):
                raise ValueError('top level must be a JSON object')
            return content
        except Exception:
            LOGGER.exception('Cannot read ' + self._path + ', using built-in category defaults')
            return None

    def _write_file(self, content):
        try:
            tmp_path = self._path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.write(_serialize(content))
            os.replace(tmp_path, self._path)
            return True
        except Exception:
            LOGGER.exception('Cannot update ' + self._path + ' with newly used categories')
            return False

    def resolve(self, used_categories: Iterable[Optional[str]]):
        """
        Makes sure every category in used_categories has an entry in categories.json (appending
        missing ones with the default icon) and returns everything the sidebar needs:

        {
          'categories': [{'name': 'Finance', 'icon': '£'}, ...],   # in file order
          'uncategorised': {'name': 'Uncategorised', 'icon': 'label_outline'},
          'aliases': {'finance': 'Finance', ...}                     # lowercased -> display name
        }
        """
        with self._lock:
            file_content = self._read_file()
            can_write = file_content is not None or not os.path.exists(self._path)
            content = file_content if file_content is not None else {}

            categories = content.get('categories')
            if not isinstance(categories, list):
                categories = []

            valid_categories = []
            for entry in categories:
                if not isinstance(entry, dict):
                    continue
                name = _normalize_name(entry.get('name'))
                if name is None:
                    continue
                valid_categories.append(entry)

            default_icon = _normalize_name(content.get('default_icon')) or FALLBACK_DEFAULT_ICON

            uncategorised = content.get('uncategorised')
            if not isinstance(uncategorised, dict):
                uncategorised = {}
            uncategorised = {
                'name': _normalize_name(uncategorised.get('name')) or FALLBACK_UNCATEGORISED['name'],
                'icon': _normalize_name(uncategorised.get('icon')) or FALLBACK_UNCATEGORISED['icon'],
            }

            aliases = {}
            for entry in valid_categories:
                name = _normalize_name(entry['name'])
                aliases.setdefault(name.lower(), name)

            added = []
            for used in used_categories:
                name = _normalize_name(used)
                if (name is None) or (name.lower() in aliases):
                    continue
                # A runner explicitly saying "Uncategorised" just means no category
                if name.lower() == uncategorised['name'].lower():
                    continue

                new_entry = {'name': name, 'icon': default_icon}
                valid_categories.append(new_entry)
                categories.append(new_entry)
                aliases[name.lower()] = name
                added.append(name)

            if added and can_write:
                content['categories'] = categories
                if self._write_file(content):
                    LOGGER.info('Added new categories to ' + self._path + ' with the default icon "'
                                + default_icon + '": ' + ', '.join(added))

            result_categories = []
            for entry in valid_categories:
                result_categories.append({
                    'name': _normalize_name(entry['name']),
                    'icon': _normalize_name(entry.get('icon')) or default_icon
                })

            return {
                'categories': result_categories,
                'uncategorised': uncategorised,
                'aliases': aliases
            }

    @staticmethod
    def canonical_name(category, resolved) -> Optional[str]:
        name = _normalize_name(category)
        if name is None:
            return None
        return resolved['aliases'].get(name.lower())


def to_external(resolved) -> dict:
    return {
        'categories': resolved['categories'],
        'uncategorised': resolved['uncategorised']
    }
