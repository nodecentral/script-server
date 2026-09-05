#!/usr/bin/env python3
# Name: label_device.py
# Version: 1.0.0
# Description: Sets a custom label (e.g. "Chris' iPhone") on a device in
#              the persistent /app/data/network_inventory.json, picked from
#              a dropdown populated live by scripts/shared/list_inventory.py.
#              Run standalone (./label_device.py --device "aa:bb:cc:dd:ee:01 | ..."
#              --label "Chris' iPhone") or from Script-Server.

import argparse
import json
import os
import sys

INVENTORY_PATH = '/app/data/network_inventory.json'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', default=os.environ.get('PARAM_DEVICE', ''))
    parser.add_argument('--label', default=os.environ.get('PARAM_LABEL', ''))
    args = parser.parse_args()

    if not args.device:
        print('No device selected', file=sys.stderr)
        sys.exit(1)

    mac = args.device.split('|')[0].strip().lower()

    if not os.path.exists(INVENTORY_PATH):
        print(f'No inventory found at {INVENTORY_PATH} - run Network Scanner first.', file=sys.stderr)
        sys.exit(1)

    with open(INVENTORY_PATH) as f:
        inventory = json.load(f)

    if mac not in inventory:
        print(f'Device {mac} not found in inventory', file=sys.stderr)
        sys.exit(1)

    inventory[mac]['label'] = args.label

    tmp_path = INVENTORY_PATH + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(inventory, f, indent=2, sort_keys=True)
    os.replace(tmp_path, INVENTORY_PATH)

    print(f'Labeled {mac} as "{args.label}"')


if __name__ == '__main__':
    main()
