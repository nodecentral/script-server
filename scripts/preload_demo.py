#!/usr/bin/env python3
# Name: preload_demo.py
# Version: 1.0.0
# Description: Demonstrates the preload_script runner feature - see
#              scripts/shared/check_jq_preload.sh, which runs automatically
#              when this page opens (before Run is clicked) and shows
#              whether jq is installed. This script re-checks for itself
#              rather than trusting that banner alone, since preload_script
#              is informational only and can't block execution. Pretty-
#              prints conf/capabilities.json's optional packages via jq if
#              installed, plain JSON otherwise. Run standalone
#              (./preload_demo.py) or from Script-Server.

import json
import os
import shutil
import subprocess
import sys

CAPABILITIES_PATH = '/app/conf/capabilities.json'


def main():
    if not os.path.exists(CAPABILITIES_PATH):
        print(f'{CAPABILITIES_PATH} not found.', file=sys.stderr)
        sys.exit(1)

    if shutil.which('jq'):
        print('jq is installed - using it to pretty-print the optional packages:\n')
        subprocess.run(['jq', '.optional'], stdin=open(CAPABILITIES_PATH), check=True)
    else:
        print('jq is not installed - showing the same data as plain JSON instead:\n')
        with open(CAPABILITIES_PATH) as f:
            manifest = json.load(f)
        print(json.dumps(manifest.get('optional', {}), indent=2))


if __name__ == '__main__':
    main()
