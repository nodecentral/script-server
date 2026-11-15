#!/usr/bin/env python3
# Name: notify.py
# Version: 1.6.0
# Description: Send Notification - sends (or tests) a push notification via Pushover, Prowl or
#              both, with each provider's own options: priority and a link for both; sound,
#              device, link title, formatting and auto-delete time for Pushover; sender name
#              for Prowl. The preload banner (preload/notify.py) shows which services are set
#              up and your Pushover devices. Prints what each service said, e.g. Prowl's API
#              calls left this hour. Run standalone or from Script-Server, or shell out to it.
#
#              The sending itself is shared/notify_send.py (a platform file), which other
#              scripts import to send their own alerts.
#
#              Credentials come from the Secrets Store (pushover.TOKEN / pushover.USER_KEY /
#              prowl.TOKEN - see Secrets Manager); --token/--user-key override them for one
#              run, e.g. to test a new key before saving it. A miss registers a placeholder in
#              Secrets Manager.

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from notify_send import NotifyError, send_detailed, send_prowl, send_pushover  # noqa: E402
from secrets_store import get_secret  # noqa: E402

DEBUG = os.environ.get('DEBUG', 'false') == 'true'

# Terminal colours readable on Script-Server's light grey panel (see SCRIPTING.md)
OK = '\033[1;32m'
ERR = '\033[1;31m'
DIM = '\033[90m'
RESET = '\033[0m'


def log_debug(msg):
    if DEBUG:
        print(f'{DIM}DEBUG: {msg}{RESET}', flush=True)


def env(name, default=''):
    return os.environ.get('PARAM_' + name.upper(), default)


def parse_args():
    parser = argparse.ArgumentParser(description='Send a push notification via Pushover or Prowl.')
    parser.add_argument('--service', default=env('service', 'auto'),
                        help='auto (first set up), pushover, prowl or all')
    parser.add_argument('--title', default=env('title', 'Script-Server'))
    parser.add_argument('--message', default=env('message'))
    parser.add_argument('--priority', default=env('priority', '0'), help='-2 .. 2')
    parser.add_argument('--url', default=env('url'))
    parser.add_argument('--url-title', default=env('pushover_url_title'))
    parser.add_argument('--sound', default=env('pushover_sound'))
    parser.add_argument('--device', default=env('pushover_device'))
    parser.add_argument('--format', default=env('pushover_format'))
    parser.add_argument('--ttl', default=env('pushover_ttl'))
    parser.add_argument('--application', default=env('prowl_application'))
    parser.add_argument('--token', default=env('token'),
                        help='override the stored Pushover app token / Prowl API key for this run')
    parser.add_argument('--user-key', default=env('user_key'),
                        help='override the stored Pushover user key for this run')
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.message:
        print(f'{ERR}ERROR{RESET} Missing the message to send.', file=sys.stderr)
        sys.exit(1)

    pushover_options = {'url_title': args.url_title, 'sound': args.sound, 'device': args.device,
                        'format': args.format, 'ttl': args.ttl}
    prowl_options = {'application': args.application}
    log_debug(f'service={args.service} priority={args.priority} pushover={pushover_options} '
              f'prowl={prowl_options}')

    sent, failed = [], []
    try:
        if args.token:
            # A key typed into the form is for one service, so send through that one directly
            service = args.service if args.service in ('pushover', 'prowl') else 'pushover'
            if service == 'pushover':
                user_key = args.user_key or get_secret('pushover', 'USER_KEY',
                                                       'Send Notification via Pushover')
                if not user_key:
                    raise NotifyError('Pushover needs a user key too - type it in, or pick '
                                      '"pushover | USER_KEY" in Secrets Manager')
                result = send_pushover(args.token, user_key, args.title, args.message,
                                       args.priority, args.url, **pushover_options)
            else:
                result = send_prowl(args.token, args.title, args.message, args.priority, args.url,
                                    **prowl_options)
            sent = [(service + ', with the key typed in', result)]
        else:
            sent, failed = send_detailed(args.title, args.message, args.priority, args.url,
                                         args.service, 'used by Send Notification',
                                         pushover=pushover_options, prowl=prowl_options)
    except NotifyError as e:
        print(f'{ERR}ERROR{RESET} Not sent: {e}', file=sys.stderr, flush=True)
        sys.exit(1)

    for service, result in sent:
        print(f'{OK}OK{RESET}    Sent via {service}: {result}', flush=True)
    for service, error in failed:
        print(f'{ERR}ERROR{RESET} Not sent via {service}: {error}', flush=True)
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
