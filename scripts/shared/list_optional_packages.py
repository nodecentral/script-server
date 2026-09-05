#!/usr/bin/env python3
# Shared helper (not a standalone Script-Server script): prints one optional
# package per line, "type:name | name | description", for use as a dynamic
# "multiselect" parameter's values.script. Usage: list_optional_packages.py

import json

MANIFEST_PATH = '/app/conf/capabilities.json'


def main():
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    optional = manifest.get('optional', {})

    for pkg in optional.get('apt', []):
        print(f"apt:{pkg['name']} | {pkg['name']} | {pkg.get('description', '')}")

    for pkg in optional.get('pip', []):
        print(f"pip:{pkg['name']} | {pkg['name']} | {pkg.get('description', '')}")


if __name__ == '__main__':
    main()
