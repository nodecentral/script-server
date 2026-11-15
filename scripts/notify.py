#!/usr/bin/env python3
# Name: notify.py
# Version: 1.5.0
# Description: Sends a push notification via Pushover or Prowl. Designed to
#              be run manually, or shelled out to from another script (e.g.
#              python3 /app/scripts/notify.py --service pushover --message
#              "New device found"). Run standalone or from Script-Server.
#
#              Token/user-key fall back to the Secrets Store
#              (pushover.TOKEN / pushover.USER_KEY / prowl.TOKEN via
#              scripts/shared/secrets_store.py - see Secrets Manager) when
#              left blank, so credentials don't need re-entering every run.
#              An explicit --token/--user-key still overrides the store. A
#              miss registers a placeholder in Secrets Manager (get_secret()
#              with a purpose), and preload/notify.py shows which services
#              are ready before the form is even submitted.
#
#              The sending itself is shared/notify_send.py (a platform file), which other
#              scripts import to send their own alerts.
#
#              NOTE: built from Pushover's and Prowl's long-stable public
#              API docs, but not verified against a live account - test
#              with your own credentials before relying on it.

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from notify_send import NotifyError, send_prowl, send_pushover  # noqa: E402
from secrets_store import get_secret  # noqa: E402

DEBUG = os.environ.get('DEBUG', 'false') == 'true'


def log_debug(msg):
    if DEBUG:
        print(f'DEBUG: {msg}', flush=True)


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
        token = args.token or get_secret('pushover', 'TOKEN', 'Send Notification via Pushover') or ''
        user_key = args.user_key or get_secret('pushover', 'USER_KEY', 'Send Notification via Pushover') or ''
        if not token or not user_key:
            print('Pushover requires both a token and a user key - pass --token/--user-key, or '
                  'pick "pushover | TOKEN" / "pushover | USER_KEY" from Secrets Manager\'s Entry '
                  'dropdown and set their values.', file=sys.stderr)
            sys.exit(1)
        try:
            send_pushover(token, user_key, args.title, args.message)
        except NotifyError as e:
            print(f'Pushover send failed: {e}', file=sys.stderr)
            sys.exit(1)
    elif args.service == 'prowl':
        token = args.token or get_secret('prowl', 'TOKEN', 'Send Notification via Prowl') or ''
        if not token:
            print('Prowl requires a token - pass --token, or pick "prowl | TOKEN" from Secrets '
                  'Manager\'s Entry dropdown and set its value.', file=sys.stderr)
            sys.exit(1)
        try:
            send_prowl(token, args.title, args.message)
        except NotifyError as e:
            print(f'Prowl send failed: {e}', file=sys.stderr)
            sys.exit(1)
    else:
        print(f'Unknown service: {args.service} (expected pushover or prowl)', file=sys.stderr)
        sys.exit(1)

    print(f'Notification sent via {args.service}')


if __name__ == '__main__':
    main()
