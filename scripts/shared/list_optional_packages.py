#!/usr/bin/env python3
# Shared helper (not a standalone Script-Server script): prints one optional
# package per line, "name | description | type", for use as a dynamic
# "multiselect" parameter's values.script. Name/description lead since
# they're what matters when picking a package; type (apt/pip) trails since
# it's just install-mechanism detail. Usage: list_optional_packages.py

import json

MANIFEST_PATH = '/app/conf/capabilities.json'


def main():
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    optional = manifest.get('optional', {})

    for pkg in optional.get('apt', []):
        print(f"{pkg['name']} | {pkg.get('description', '')} | apt")

    for pkg in optional.get('pip', []):
        print(f"{pkg['name']} | {pkg.get('description', '')} | pip")


if __name__ == '__main__':
    main()
