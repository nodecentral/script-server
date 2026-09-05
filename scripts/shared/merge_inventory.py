#!/usr/bin/env python3
# Shared helper (not a standalone Script-Server script): merges a scan-results
# CSV (IP,MAC,Hostname,Vendor,Services) into the persistent
# /app/data/network_inventory.json, keyed by MAC address. Preserves any
# existing custom label. Usage: merge_inventory.py <scan_csv_path>

import csv
import json
import os
import sys
import time

INVENTORY_PATH = '/app/data/network_inventory.json'


def load_inventory():
    if not os.path.exists(INVENTORY_PATH):
        return {}
    with open(INVENTORY_PATH) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_inventory(inventory):
    os.makedirs(os.path.dirname(INVENTORY_PATH), exist_ok=True)
    tmp_path = INVENTORY_PATH + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(inventory, f, indent=2, sort_keys=True)
    os.replace(tmp_path, INVENTORY_PATH)


def main():
    if len(sys.argv) < 2:
        print('Usage: merge_inventory.py <scan_csv_path>', file=sys.stderr)
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f'No scan CSV found at {csv_path}, nothing to merge.')
        return

    inventory = load_inventory()
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    new_count = 0
    updated_count = 0

    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mac = (row.get('MAC') or '').strip().lower()
            if not mac:
                continue

            ip = row.get('IP', '')
            hostname = row.get('Hostname', '')
            vendor = row.get('Vendor', '')

            if mac not in inventory:
                inventory[mac] = {
                    'mac': mac,
                    'label': '',
                    'first_seen': now,
                }
                new_count += 1
            else:
                updated_count += 1

            inventory[mac]['last_seen'] = now
            inventory[mac]['last_ip'] = ip
            if hostname:
                inventory[mac]['hostname'] = hostname
            if vendor and vendor != 'Unknown':
                inventory[mac]['vendor'] = vendor

    save_inventory(inventory)
    print(f'Inventory updated: {new_count} new device(s), {updated_count} seen again.')


if __name__ == '__main__':
    main()
