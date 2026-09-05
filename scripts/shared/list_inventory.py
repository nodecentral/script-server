#!/usr/bin/env python3
# Shared helper (not a standalone Script-Server script): prints one
# inventory entry per line, "MAC | label | vendor | last_ip", for use as a
# dynamic "list" parameter's values.script. Usage: list_inventory.py

import json
import os

INVENTORY_PATH = '/app/data/network_inventory.json'


def main():
    if not os.path.exists(INVENTORY_PATH):
        return

    with open(INVENTORY_PATH) as f:
        try:
            inventory = json.load(f)
        except json.JSONDecodeError:
            return

    for mac, entry in sorted(inventory.items()):
        label = entry.get('label') or '(unlabeled)'
        vendor = entry.get('vendor', 'Unknown')
        last_ip = entry.get('last_ip', '')
        print(f"{mac} | {label} | {vendor} | {last_ip}")


if __name__ == '__main__':
    main()
