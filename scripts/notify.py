#!/usr/bin/env python3
# Name: notify.py
# Version: 1.1.0
# Description: Sends a push notification via Pushover or Prowl. Designed to
#              be run manually, or shelled out to from another script (e.g.
#              python3 /app/scripts/notify.py --service pushover --message
#              "New device found"). Run standalone or from Script-Server.
#
#              Token/user-key fall back to the Secrets Store
#              (pushover.TOKEN / pushover.USER_KEY / prowl.TOKEN via
#              scripts/shared/secrets_store.py - see Secrets Manager) when
#              left blank, so credentials don't need re-entering every run.
#              An explicit --token/--user-key still overrides the store.
#
#              NOTE: built from Pushover's and Prowl's long-stable public
#              API docs, but not verified against a live account - test
#              with your own credentials before relying on it.

import argparse
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from secrets_store import get_secret  # noqa: E402

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'
PROWL_URL = 'https://api.prowlapp.com/publicapi/add'

DEBUG = os.environ.get('DEBUG', 'false') == 'true'


def log_debug(msg):
    if DEBUG:
        print(f'DEBUG: {msg}', flush=True)


def send_pushover(token, user_key, title, message):
    if not token or not user_key:
        print('Pushover requires both --token (app token) and --user-key', file=sys.stderr)
        sys.exit(1)

    response = requests.post(PUSHOVER_URL, data={
        'token': token,
        'user': user_key,
        'title': title,
        'message': message,
    }, timeout=15)
    log_debug(f'Pushover response: {response.status_code} {response.text}')

    if response.status_code != 200:
        print(f'Pushover send failed: HTTP {response.status_code} {response.text}', file=sys.stderr)
        sys.exit(1)


def send_prowl(token, title, message):
    if not token:
        print('Prowl requires --token (apikey)', file=sys.stderr)
        sys.exit(1)

    response = requests.post(PROWL_URL, data={
        'apikey': token,
        'application': 'Script-Server',
        'event': title,
        'description': message,
    }, timeout=15)
    log_debug(f'Prowl response: {response.status_code} {response.text}')

    if response.status_code != 200:
        print(f'Prowl send failed: HTTP {response.status_code} {response.text}', file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--service', default=os.environ.get('PARAM_SERVICE', 'pushover'))
    parser.add_argument('--token', default=os.environ.get('PARAM_TOKEN', ''))
    parser.add_argument('--user-key', default=os.environ.get('PARAM_USER_KEY', ''))
    parser.add_argument('--title', default=os.environ.get('PARAM_TITLE', 'Script-Server'))
    parser.add_argument('--message', default=os.environ.get('PARAM_MESSAGE', ''))
    args = parser.parse_args()

    if not args.message:
        print('Missing required --message', file=sys.stderr)
        sys.exit(1)

    log_debug(f'service={args.service} title={args.title!r} message={args.message!r}')

    if args.service == 'pushover':
        token = args.token or get_secret('pushover', 'TOKEN') or ''
        user_key = args.user_key or get_secret('pushover', 'USER_KEY') or ''
        if not token or not user_key:
            print('Pushover requires both a token and a user key - pass --token/--user-key, or '
                  'set pushover.TOKEN / pushover.USER_KEY via Secrets Manager.', file=sys.stderr)
            sys.exit(1)
        send_pushover(token, user_key, args.title, args.message)
    elif args.service == 'prowl':
        token = args.token or get_secret('prowl', 'TOKEN') or ''
        if not token:
            print('Prowl requires a token - pass --token, or set prowl.TOKEN via '
                  'Secrets Manager.', file=sys.stderr)
            sys.exit(1)
        send_prowl(token, args.title, args.message)
    else:
        print(f'Unknown service: {args.service} (expected pushover or prowl)', file=sys.stderr)
        sys.exit(1)

    print(f'Notification sent via {args.service}')


if __name__ == '__main__':
    main()
