#!/usr/bin/env python3
# Name: install_package.py
# Version: 1.0.0
# Description: Installs one or more optional packages (from
#              conf/capabilities.json) into the running container via apt
#              or pip. This is EPHEMERAL - lost when the container is
#              rebuilt/recreated - unless you also add the package to
#              tools/Dockerfile. Records what was installed to
#              /app/data/installed_extras.json (see View Capabilities).
#              Run standalone (./install_package.py --packages
#              "apt:jq | jq | ...;pip:psutil | psutil | ...") or from
#              Script-Server.

import argparse
import json
import os
import subprocess
import sys
import time

INSTALLED_PATH = '/app/data/installed_extras.json'

DEBUG = os.environ.get('DEBUG', 'false') == 'true'


def log_debug(msg):
    if DEBUG:
        print(f'DEBUG: {msg}', flush=True)


def load_installed():
    if not os.path.exists(INSTALLED_PATH):
        return {}
    with open(INSTALLED_PATH) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_installed(installed):
    os.makedirs(os.path.dirname(INSTALLED_PATH), exist_ok=True)
    tmp_path = INSTALLED_PATH + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(installed, f, indent=2, sort_keys=True)
    os.replace(tmp_path, INSTALLED_PATH)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packages', default=os.environ.get('PARAM_PACKAGES', ''))
    args = parser.parse_args()

    if not args.packages:
        print('No packages selected', file=sys.stderr)
        sys.exit(1)

    selections = [s.strip() for s in args.packages.split(';') if s.strip()]
    log_debug(f'selections={selections}')

    apt_names = []
    pip_names = []
    for selection in selections:
        type_and_name = selection.split('|')[0].strip()
        if ':' not in type_and_name:
            print(f'Skipping unrecognized selection: {selection}', file=sys.stderr)
            continue
        pkg_type, name = type_and_name.split(':', 1)
        if pkg_type == 'apt':
            apt_names.append(name)
        elif pkg_type == 'pip':
            pip_names.append(name)
        else:
            print(f'Skipping unknown package type: {selection}', file=sys.stderr)

    installed = load_installed()
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    if apt_names:
        print(f"Installing apt packages: {', '.join(apt_names)}")
        subprocess.run(['apt-get', 'update'], check=True)
        subprocess.run(['apt-get', 'install', '-y'] + apt_names, check=True)
        for name in apt_names:
            installed[f'apt:{name}'] = {'type': 'apt', 'name': name, 'installed_at': now}

    if pip_names:
        print(f"Installing pip packages: {', '.join(pip_names)}")
        subprocess.run([sys.executable, '-m', 'pip', 'install'] + pip_names, check=True)
        for name in pip_names:
            installed[f'pip:{name}'] = {'type': 'pip', 'name': name, 'installed_at': now}

    save_installed(installed)
    print('Done. Note: this is ephemeral - add to tools/Dockerfile to make it permanent.')


if __name__ == '__main__':
    main()
