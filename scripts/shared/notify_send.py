#!/usr/bin/env python3
# Name: shared/notify_send.py
# Version: 1.1.0
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
#   Provider-only options go in a dict per provider and are ignored by the other one:
#       send(..., pushover={'sound': 'cashregister', 'device': 'iphone', 'url_title': 'Open',
#                           'format': 'html', 'ttl': 3600},
#                 prowl={'application': 'Tariff Watch'})
#
# Lua / bash (exit code 0 sent, 1 not sent; the reason goes to stderr):
#   python3 /app/scripts/shared/notify_send.py --title 'Tariff Watch' --message 'Price low' \
#       --priority 1 --purpose 'used by Tariff Watch' [--sound cashregister] [--application X]
#
# Which service: service=None (default) uses the first one fully set up, Pushover then Prowl;
# 'all' sends to every one set up; 'pushover' / 'prowl' forces one. When none is set up, the
# secrets of both are registered as "not set yet" placeholders in Secrets Manager (with the
# purpose given), and NotifyError says which entries to pick there.
#
# Common options (both providers): title, message, priority -2 (lowest) .. 2 (emergency), url.
# Pushover only (https://pushover.net/api): url_title, sound, device (comma-separated names),
#   format 'plain' | 'html' | 'monospace', ttl (seconds until deleted), timestamp (unix),
#   retry / expire for priority 2 (default 60 s / 3600 s; Pushover's limits: >= 30, <= 10800).
# Prowl only (https://www.prowlapp.com/api.php): application (shown as the sender, default
#   "Script-Server"). Prowl's event = title, description = message.
# Over-long values are trimmed to each provider's limits rather than refused.
#
# Dropdown helpers for runners (one value per line, first line "(default)"):
#   notify_send.py dropdown-sounds    Pushover sounds (live list, or the built-in names)
#   notify_send.py dropdown-devices   your Pushover devices

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from secrets_store import dropdown_entry_label, get_secret  # noqa: E402

PUSHOVER_URL = 'https://api.pushover.net/1/messages.json'
PUSHOVER_SOUNDS_URL = 'https://api.pushover.net/1/sounds.json'
PUSHOVER_VALIDATE_URL = 'https://api.pushover.net/1/users/validate.json'
PROWL_URL = 'https://api.prowlapp.com/publicapi/add'
TIMEOUT_SECONDS = 15

DEFAULT_CHOICE = '(default)'
PUSHOVER_BUILTIN_SOUNDS = [
    'pushover', 'bike', 'bugle', 'cashregister', 'classical', 'cosmic', 'falling', 'gamelan',
    'incoming', 'intermission', 'magic', 'mechanical', 'pianobar', 'siren', 'spacealarm',
    'tugboat', 'alien', 'climb', 'persistent', 'echo', 'updown', 'vibrate', 'none']

# service -> the secrets it needs, in the order send() tries them
SERVICES = {
    'pushover': [('pushover', 'TOKEN'), ('pushover', 'USER_KEY')],
    'prowl': [('prowl', 'TOKEN')],
}


class NotifyError(Exception):
    pass


def _request(url, fields=None, method='POST'):
    data = urllib.parse.urlencode(fields or {}).encode('utf-8')
    if method == 'GET' and fields:
        url, data = url + '?' + data.decode('ascii'), None
    request = urllib.request.Request(url, data=data if method == 'POST' else None, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')
    except (urllib.error.URLError, OSError) as e:
        raise NotifyError(f'could not reach {urllib.parse.urlparse(url).hostname}: {e}')


def _post(url, fields):
    return _request(url, fields, 'POST')


def _clamp_priority(priority):
    try:
        return max(-2, min(2, int(priority)))
    except (TypeError, ValueError):
        return 0


def _int_option(value, low=None, high=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if low is not None:
        number = max(low, number)
    if high is not None:
        number = min(high, number)
    return number


def _chosen(value):
    """A dropdown/option value, or '' for the "use the default" choices."""
    value = (value or '').strip()
    return '' if value in ('', DEFAULT_CHOICE) or value.startswith('--') else value


def send_pushover(token, user_key, title, message, priority=0, url='', **options):
    """Sends one Pushover message. Returns a short result text (the receipt for priority 2).
    options: url_title, sound, device, format ('plain'|'html'|'monospace'), ttl, timestamp,
    retry, expire. Raises NotifyError on failure."""
    priority = _clamp_priority(priority)
    fields = {'token': token, 'user': user_key, 'title': (title or '')[:250],
              'message': message[:1024], 'priority': priority}
    if url:
        fields['url'] = url[:512]
        if _chosen(options.get('url_title')):
            fields['url_title'] = options['url_title'][:100]
    sound, device = _chosen(options.get('sound')), _chosen(options.get('device'))
    if sound:
        fields['sound'] = sound
    if device:
        fields['device'] = device
    text_format = _chosen(options.get('format'))
    if text_format == 'html':
        fields['html'] = 1
    elif text_format == 'monospace':
        fields['monospace'] = 1
    ttl = _int_option(options.get('ttl'), low=1)
    if ttl and priority != 2:
        fields['ttl'] = ttl
    timestamp = _int_option(options.get('timestamp'), low=1)
    if timestamp:
        fields['timestamp'] = timestamp
    if priority == 2:
        fields['retry'] = _int_option(options.get('retry'), 30) or 60
        fields['expire'] = _int_option(options.get('expire'), 30, 10800) or 3600

    status, body = _post(PUSHOVER_URL, fields)
    if status != 200:
        raise NotifyError(f'Pushover refused it: HTTP {status} {_pushover_errors(body)}')
    try:
        receipt = json.loads(body).get('receipt')
    except ValueError:
        receipt = None
    return f'emergency receipt {receipt}' if receipt else 'accepted'


def _pushover_errors(body):
    try:
        return '; '.join(json.loads(body).get('errors') or []) or body[:200]
    except ValueError:
        return body[:200]


def send_prowl(token, title, message, priority=0, url='', **options):
    """Sends one Prowl message. Returns a short result text (API calls left this hour).
    options: application. Raises NotifyError on failure."""
    fields = {'apikey': token,
              'application': (_chosen(options.get('application')) or 'Script-Server')[:256],
              'event': (title or 'Script-Server')[:1024], 'description': message[:10000],
              'priority': _clamp_priority(priority)}
    if url:
        fields['url'] = url[:512]
    status, body = _post(PROWL_URL, fields)
    if status != 200:
        error = re.search(r'<error[^>]*>(.*?)</error>', body, re.S)
        raise NotifyError(f'Prowl refused it: HTTP {status} '
                          + (error.group(1).strip() if error else body[:200]))
    remaining = re.search(r'remaining="(\d+)"', body)
    return f'{remaining.group(1)} API calls left this hour' if remaining else 'accepted'


def _credentials(service):
    """The service's secret values, or None if any is missing. Doesn't register placeholders."""
    values = [get_secret(product, key, register=False) for product, key in SERVICES[service]]
    return None if any(not v for v in values) else values


def configured_services():
    """Services whose secrets are all set, in the order send() tries them."""
    return [service for service in SERVICES if _credentials(service)]


def pushover_sounds():
    """Sound names for the configured Pushover app (custom ones included), or the built-in list."""
    credentials = _credentials('pushover')
    if credentials:
        try:
            status, body = _request(PUSHOVER_SOUNDS_URL, {'token': credentials[0]}, 'GET')
            if status == 200:
                sounds = sorted((json.loads(body).get('sounds') or {}).keys())
                if sounds:
                    return sounds
        except (NotifyError, ValueError):
            pass
    return list(PUSHOVER_BUILTIN_SOUNDS)


def pushover_devices():
    """(device names, problem text). Names are the active devices on the configured user key."""
    credentials = _credentials('pushover')
    if not credentials:
        return [], 'Pushover is not set up'
    try:
        status, body = _post(PUSHOVER_VALIDATE_URL, {'token': credentials[0], 'user': credentials[1]})
        data = json.loads(body)
    except NotifyError as e:
        return [], str(e)
    except ValueError:
        return [], f'unexpected reply from Pushover (HTTP {status})'
    if status != 200 or data.get('status') != 1:
        return [], 'Pushover says: ' + ('; '.join(data.get('errors') or []) or f'HTTP {status}')
    return list(data.get('devices') or []), ''


def _send_one(service, credentials, title, message, priority, url, options):
    if service == 'pushover':
        return send_pushover(credentials[0], credentials[1], title, message, priority, url,
                             **options)
    return send_prowl(credentials[0], title, message, priority, url, **options)


def send_detailed(title, message, priority=0, url='', service=None, purpose='',
                  pushover=None, prowl=None):
    """Like send(), but returns [(service, result text)] and, when 'all' partly fails,
    also [(service, error)] as the second item: (sent, failed)."""
    if not message:
        raise NotifyError('no message to send')
    title = title or 'Script-Server'
    options = {'pushover': dict(pushover or {}), 'prowl': dict(prowl or {})}

    if service in (None, '', 'all', 'auto'):
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

    if service in (None, '', 'auto'):
        ready = ready[:1]

    sent, failed = [], []
    for s, creds in ready:
        try:
            sent.append((s, _send_one(s, creds, title, message, priority, url, options[s])))
        except NotifyError as e:
            failed.append((s, str(e)))
    if not sent:
        raise NotifyError('; '.join(error for _s, error in failed))
    return sent, failed


def send(title, message, priority=0, url='', service=None, purpose='', pushover=None, prowl=None):
    """Sends a notification and returns the list of services it went through.

    service: None = first set up (Pushover, then Prowl); 'all' = every one set up;
    'pushover' / 'prowl' = that one only. pushover / prowl: provider-only options (see the
    header). Raises NotifyError when nothing could be sent."""
    sent, _failed = send_detailed(title, message, priority, url, service, purpose, pushover, prowl)
    return [s for s, _result in sent]


def _dropdown(values):
    print(DEFAULT_CHOICE)
    for value in values:
        print(value)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'dropdown-sounds':
        _dropdown(pushover_sounds())
        return
    if len(sys.argv) > 1 and sys.argv[1] == 'dropdown-devices':
        devices, problem = pushover_devices()
        _dropdown(devices)
        if problem and not devices:
            print(f'-- {problem}')
        return

    parser = argparse.ArgumentParser(description='Send a push notification via Pushover or Prowl.')
    parser.add_argument('--title', default='Script-Server')
    parser.add_argument('--message', required=True)
    parser.add_argument('--priority', type=int, default=0, help='-2 .. 2')
    parser.add_argument('--url', default='')
    parser.add_argument('--service', default='', help='pushover, prowl or all (default: first set up)')
    parser.add_argument('--purpose', default='', help='why the alert is needed, shown in Secrets Manager')
    parser.add_argument('--url-title', default='', help='Pushover: text for the link')
    parser.add_argument('--sound', default='', help='Pushover: sound name')
    parser.add_argument('--device', default='', help='Pushover: device name(s), comma-separated')
    parser.add_argument('--format', default='', choices=['', 'plain', 'html', 'monospace'],
                        help='Pushover: message formatting')
    parser.add_argument('--ttl', default='', help='Pushover: seconds until the message is deleted')
    parser.add_argument('--application', default='', help='Prowl: sender name')
    parser.add_argument('--json', action='store_true', help='print the result as JSON')
    args = parser.parse_args()

    try:
        sent, failed = send_detailed(
            args.title, args.message, args.priority, args.url, args.service or None, args.purpose,
            pushover={'url_title': args.url_title, 'sound': args.sound, 'device': args.device,
                      'format': args.format, 'ttl': args.ttl},
            prowl={'application': args.application})
    except NotifyError as e:
        print(f'Not sent: {e}', file=sys.stderr, flush=True)
        if args.json:
            print(json.dumps({'sent': [], 'error': str(e)}))
        sys.exit(1)

    for service, error in failed:
        print(f'Not sent via {service}: {error}', file=sys.stderr, flush=True)
    if args.json:
        print(json.dumps({'sent': [s for s, _r in sent], 'results': dict(sent),
                          'failed': dict(failed)}))
    else:
        print('Sent via ' + ' and '.join(f'{s} ({r})' for s, r in sent), flush=True)


if __name__ == '__main__':
    main()
