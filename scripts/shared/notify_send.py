#!/usr/bin/env python3
# Name: shared/notify_send.py
# Version: 1.0.0
# Description: Send a push notification from any script, through Pushover or Prowl, whichever
#              is set up in the Secrets Store. Platform file (tools/PLATFORM_FILES): shipped by
#              Script-Server and refreshed on every start, so don't copy it into a sibling repo.
#              Standard library only.
#
# Python:
#   sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
#   from notify_send import send, NotifyError
#   try:
#       send('Tariff Watch', 'Agile price below 5p', priority=1, url='https://...',
#            purpose='used by Tariff Watch')
#   except NotifyError as e:
#       print(f'WARN could not send alert: {e}', flush=True)
#
# Lua / bash (exit code 0 sent, 1 not sent; the reason goes to stderr):
#   python3 /app/scripts/shared/notify_send.py --title 'Tariff Watch' --message 'Price low' \
#       --priority 1 --purpose 'used by Tariff Watch'
#
# Which service: service=None (default) uses the first one fully set up, Pushover then Prowl;
# 'all' sends to every one set up; 'pushover' / 'prowl' forces one. When none is set up, the
# secrets of both are registered as "not set yet" placeholders in Secrets Manager (with the
# purpose given), and NotifyError says which entries to pick there.
#
# priority: -2 (lowest) .. 2 (emergency), the scale both services use. Pushover's 2 needs
# retry/expire, so it's sent with retry=60s, expire=1h. url: a link shown with the alert.

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from secrets_store import dropdown_entry_label, get_secret  # noqa: E402

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'
PROWL_URL = 'https://api.prowlapp.com/publicapi/add'
TIMEOUT_SECONDS = 15

# service -> the secrets it needs, in the order send() tries them
SERVICES = {
    'pushover': [('pushover', 'TOKEN'), ('pushover', 'USER_KEY')],
    'prowl': [('prowl', 'TOKEN')],
}


class NotifyError(Exception):
    pass


def _post(url, fields):
    data = urllib.parse.urlencode(fields).encode('utf-8')
    request = urllib.request.Request(url, data=data, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, OSError) as e:
        raise NotifyError(f'could not reach {urllib.parse.urlparse(url).hostname}: {e}')


def _clamp_priority(priority):
    try:
        return max(-2, min(2, int(priority)))
    except (TypeError, ValueError):
        return 0


def send_pushover(token, user_key, title, message, priority=0, url=''):
    """Sends one Pushover message with the credentials given. Raises NotifyError on failure."""
    priority = _clamp_priority(priority)
    fields = {'token': token, 'user': user_key, 'title': title, 'message': message,
              'priority': priority}
    if priority == 2:
        fields.update({'retry': 60, 'expire': 3600})
    if url:
        fields['url'] = url
    status, body = _post(PUSHOVER_URL, fields)
    if status != 200:
        raise NotifyError(f'Pushover refused it: HTTP {status} {body[:200]}')


def send_prowl(token, title, message, priority=0, url=''):
    """Sends one Prowl message with the API key given. Raises NotifyError on failure."""
    fields = {'apikey': token, 'application': 'Script-Server', 'event': title,
              'description': message, 'priority': _clamp_priority(priority)}
    if url:
        fields['url'] = url
    status, body = _post(PROWL_URL, fields)
    if status != 200:
        raise NotifyError(f'Prowl refused it: HTTP {status} {body[:200]}')


def _credentials(service):
    """The service's secret values, or None if any is missing. Doesn't register placeholders."""
    values = [get_secret(product, key, register=False) for product, key in SERVICES[service]]
    return None if any(not v for v in values) else values


def configured_services():
    """Services whose secrets are all set, in the order send() tries them."""
    return [service for service in SERVICES if _credentials(service)]


def _send_one(service, credentials, title, message, priority, url):
    if service == 'pushover':
        send_pushover(credentials[0], credentials[1], title, message, priority, url)
    else:
        send_prowl(credentials[0], title, message, priority, url)


def send(title, message, priority=0, url='', service=None, purpose=''):
    """Sends a notification and returns the list of services it went through.

    service: None = first set up (Pushover, then Prowl); 'all' = every one set up;
    'pushover' / 'prowl' = that one only. Raises NotifyError when nothing could be sent."""
    if not message:
        raise NotifyError('no message to send')
    title = title or 'Script-Server'

    if service in (None, '', 'all'):
        candidates = list(SERVICES)
    elif service in SERVICES:
        candidates = [service]
    else:
        raise NotifyError(f'unknown service "{service}" (expected pushover, prowl or all)')

    ready = [(s, _credentials(s)) for s in candidates]
    ready = [(s, creds) for s, creds in ready if creds]

    if not ready:
        # Make the missing secrets visible in Secrets Manager, with why they're wanted
        purpose = purpose or 'push notifications'
        missing = []
        for s in candidates:
            for product, key in SERVICES[s]:
                if get_secret(product, key, purpose) is None:
                    missing.append(f'"{dropdown_entry_label(product, key)}"')
        raise NotifyError('no notification service is set up - in Secrets Manager, pick '
                          + ' / '.join(missing) + ' from the Entry dropdown and set the value')

    if service in (None, ''):
        ready = ready[:1]

    sent, errors = [], []
    for s, creds in ready:
        try:
            _send_one(s, creds, title, message, priority, url)
            sent.append(s)
        except NotifyError as e:
            errors.append(str(e))
    if not sent:
        raise NotifyError('; '.join(errors))
    return sent


def main():
    parser = argparse.ArgumentParser(description='Send a push notification via Pushover or Prowl.')
    parser.add_argument('--title', default='Script-Server')
    parser.add_argument('--message', required=True)
    parser.add_argument('--priority', type=int, default=0, help='-2 .. 2')
    parser.add_argument('--url', default='')
    parser.add_argument('--service', default='', help='pushover, prowl or all (default: first set up)')
    parser.add_argument('--purpose', default='', help='why the alert is needed, shown in Secrets Manager')
    parser.add_argument('--json', action='store_true', help='print the result as JSON')
    args = parser.parse_args()

    try:
        sent = send(args.title, args.message, args.priority, args.url, args.service or None,
                    args.purpose)
    except NotifyError as e:
        print(f'Not sent: {e}', file=sys.stderr, flush=True)
        if args.json:
            print(json.dumps({'sent': [], 'error': str(e)}))
        sys.exit(1)

    print(json.dumps({'sent': sent}) if args.json else 'Sent via ' + ' and '.join(sent), flush=True)


if __name__ == '__main__':
    main()
