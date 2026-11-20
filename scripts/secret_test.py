#!/usr/bin/env python3
# Name: secret_test.py
# Version: 1.0.0
# Description: Test a Secret - tries a secret from the Secrets Store against its real service and
#              shows what came back: a reply from an AI model, a live share price, the latest
#              inflation figure, your Paperless library, your Gitea repos, or a notification on
#              your phone. Covers every secret listed in conf/secrets_defaults.json (a test in
#              src/tests/secret_test_test.py fails if one is missing), so a new default always
#              arrives with a way to try it.
#
#              Pick one secret, or "all" to test every one that's set. Each test is one cheap
#              call: AI providers cost a fraction of a penny each. Values are never printed, and
#              any key a provider echoes back in an error is removed before it's shown.
#
#              Run from Script-Server (html_iframe) or standalone:
#                  python3 secret_test.py --secret finnhub --symbol MSFT

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shared'))
from secrets_store import get_secret, secrets_manager_link, dropdown_entry_label  # noqa: E402

TIMEOUT = 20
DEFAULT_SYMBOL = 'AAPL'
DEFAULT_PROMPT = 'Write a two-line poem about a home server.'
CLAUDE_MODEL = 'claude-opus-5-5'


def own_version():
    with open(__file__, encoding='utf-8') as f:
        m = re.search(r'Version\s*:\s*([0-9][^\s]*)', f.read(16384))
    return m.group(1) if m else 'unknown'


class CheckFailed(Exception):
    """A check that reached a verdict: the message is shown to the user as the reason."""


class Result:
    def __init__(self, ok, headline, facts=None, quote=None, warning=None, verified=True):
        self.ok = ok                # True / False
        self.verified = verified    # False: the service answered, but that doesn't prove the key
        self.headline = headline    # one line, the "cool" bit
        self.facts = facts or []    # [(label, value)]
        self.quote = quote          # longer text shown in a speech bubble (AI replies)
        self.warning = warning      # shown even when ok


# --- HTTP ------------------------------------------------------------------------------------

def http_json(url, headers=None, data=None, method=None):
    """Request url and return (status, parsed JSON or raw text). Never raises for an HTTP status:
    the caller decides what a 401 means for its provider."""
    body = None
    headers = dict(headers or {})
    if data is not None:
        if isinstance(data, dict) and headers.get('Content-Type') == 'application/json':
            body = json.dumps(data).encode()
        elif isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode()
        else:
            body = data
    headers.setdefault('User-Agent', 'script-server-secret-test')
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except urllib.error.URLError as e:
        raise CheckFailed(f'could not reach {urllib.parse.urlsplit(url).netloc}: {e.reason}')
    except TimeoutError:
        raise CheckFailed(f'{urllib.parse.urlsplit(url).netloc} did not answer within {TIMEOUT}s')
    text = raw.decode('utf-8', errors='replace')
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text


def error_text(payload):
    """The provider's own error message, from the usual JSON shapes."""
    if isinstance(payload, dict):
        for key in ('error', 'message', 'detail', 'Error Message', 'error_message', 'errors'):
            value = payload.get(key)
            if isinstance(value, dict):
                value = value.get('message') or value.get('code') or json.dumps(value)
            if isinstance(value, list):
                value = '; '.join(str(v) for v in value)
            if value:
                return str(value)
    return str(payload)[:200]


def expect_ok(status, payload, what):
    if status in (401, 403):
        raise CheckFailed(f'{what} rejected the key ({status}): {error_text(payload)}')
    if status >= 400:
        raise CheckFailed(f'{what} answered {status}: {error_text(payload)}')
    return payload


def money(value):
    try:
        return f'{float(value):,.2f}'
    except (TypeError, ValueError):
        return str(value)


def change_text(change, percent):
    try:
        change, percent = float(change), float(percent)
    except (TypeError, ValueError):
        return None
    arrow = '▲' if change >= 0 else '▼'
    return f'{arrow} {change:+,.2f} ({percent:+.2f}%)'


# --- AI providers ------------------------------------------------------------------------------

def check_anthropic(s, opts):
    try:
        import anthropic
    except ImportError:
        # Same self-install pattern as other scripts (see SCRIPTING.md): kept across restarts.
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet',
                        '--break-system-packages', 'anthropic'],
                       check=False, capture_output=True)
        try:
            import anthropic
        except ImportError:
            raise CheckFailed('the anthropic package is not installed and could not be installed')

    client = anthropic.Anthropic(api_key=s['API_KEY'], timeout=60.0, max_retries=1)
    try:
        models = [m.id for m in client.models.list()]
        if not opts.ask_ai:
            return Result(True, f'Key works: {len(models)} models available',
                          [('Models', ', '.join(models[:4]) + (' …' if len(models) > 4 else ''))])
        request = dict(model=CLAUDE_MODEL, max_tokens=1024, output_config={'effort': 'low'},
                       messages=[{'role': 'user', 'content': opts.prompt}])
        try:
            # Server-side refusal fallback, on by default for this model.
            response = client.beta.messages.create(
                betas=['server-side-fallback-2026-07-01'], fallbacks='default', **request)
        except TypeError:
            # An older SDK already installed without the fallbacks parameter.
            response = client.messages.create(**request)
    except anthropic.AuthenticationError:
        raise CheckFailed('Anthropic rejected the key (401)')
    except anthropic.PermissionDeniedError as e:
        raise CheckFailed(f'the key is not allowed to do this (403): {e.message}')
    except anthropic.RateLimitError:
        raise CheckFailed('rate limited (429) - the key works, try again in a minute')
    except anthropic.APIStatusError as e:
        raise CheckFailed(f'Anthropic answered {e.status_code}: {e.message}')
    except anthropic.APIConnectionError:
        raise CheckFailed('could not reach api.anthropic.com')

    if response.stop_reason == 'refusal':
        return Result(True, 'Key works (the model declined this prompt)',
                      [('Model', response.model)])
    text = ''.join(b.text for b in response.content if b.type == 'text').strip()
    return Result(True, f'Claude answered ({len(models)} models available on this key)',
                  [('Model', response.model),
                   ('Tokens', f'{response.usage.input_tokens} in, {response.usage.output_tokens} out')],
                  quote=text)


def _pick_model(ids, prefer, avoid=('audio', 'realtime', 'image', 'tts', 'embed', 'transcribe',
                                     'search', 'vision', 'moderation', 'whisper', 'dall', 'imagine')):
    usable = [i for i in ids if not any(word in i.lower() for word in avoid)]
    for wanted in prefer:
        for model in usable:
            if wanted in model.lower():
                return model
    return usable[0] if usable else None


def _openai_style(name, base, s, opts, prefer, models_path='/v1/models', chat_path='/v1/chat/completions'):
    headers = {'Authorization': f'Bearer {s["API_KEY"]}'}
    payload = expect_ok(*http_json(base + models_path, headers), name)
    ids = sorted(m.get('id', '') for m in payload.get('data', []) if isinstance(m, dict))
    if not opts.ask_ai:
        return Result(True, f'Key works: {len(ids)} models available',
                      [('Models', ', '.join(ids[:4]) + (' …' if len(ids) > 4 else ''))])
    model = _pick_model(ids, prefer)
    if not model:
        return Result(True, f'Key works: {len(ids)} models, none suitable for a chat test')
    headers['Content-Type'] = 'application/json'
    reply = expect_ok(*http_json(base + chat_path, headers, {
        'model': model, 'max_tokens': 200,
        'messages': [{'role': 'user', 'content': opts.prompt}]}), name)
    text = ((reply.get('choices') or [{}])[0].get('message') or {}).get('content', '').strip()
    usage = reply.get('usage') or {}
    return Result(True, f'{name} answered ({len(ids)} models available on this key)',
                  [('Model', reply.get('model', model)),
                   ('Tokens', f'{usage.get("prompt_tokens", "?")} in, '
                              f'{usage.get("completion_tokens", "?")} out')],
                  quote=text)


def check_openai(s, opts):
    return _openai_style('OpenAI', 'https://api.openai.com', s, opts, ['mini', 'gpt'])


def check_xai(s, opts):
    return _openai_style('xAI', 'https://api.x.ai', s, opts, ['mini', 'fast', 'grok'])


def check_deepseek(s, opts):
    return _openai_style('DeepSeek', 'https://api.deepseek.com', s, opts, ['deepseek-chat', 'chat'],
                         models_path='/models', chat_path='/chat/completions')


def check_gemini(s, opts):
    base = 'https://generativelanguage.googleapis.com/v1beta'
    headers = {'x-goog-api-key': s['API_KEY']}
    payload = expect_ok(*http_json(base + '/models?pageSize=200', headers), 'Gemini')
    models = [m for m in payload.get('models', [])
              if 'generateContent' in (m.get('supportedGenerationMethods') or [])]
    names = sorted(m.get('name', '') for m in models)
    if not opts.ask_ai:
        return Result(True, f'Key works: {len(names)} models available')
    model = _pick_model(names, ['flash-lite', 'flash'])
    if not model:
        return Result(True, f'Key works: {len(names)} models, none suitable for a chat test')
    headers['Content-Type'] = 'application/json'
    reply = expect_ok(*http_json(f'{base}/{model}:generateContent', headers, {
        'contents': [{'parts': [{'text': opts.prompt}]}],
        'generationConfig': {'maxOutputTokens': 200}}), 'Gemini')
    parts = (((reply.get('candidates') or [{}])[0].get('content') or {}).get('parts') or [])
    text = ''.join(p.get('text', '') for p in parts).strip()
    usage = reply.get('usageMetadata') or {}
    return Result(True, f'Gemini answered ({len(names)} models available on this key)',
                  [('Model', model.split('/')[-1]),
                   ('Tokens', f'{usage.get("promptTokenCount", "?")} in, '
                              f'{usage.get("candidatesTokenCount", "?")} out')],
                  quote=text or '(no text in the reply)')


# --- Finance ------------------------------------------------------------------------------------

def _quote(symbol, price, change=None, percent=None, extra=None):
    facts = [('Price', money(price))]
    moved = change_text(change, percent)
    if moved:
        facts.append(('Today', moved))
    facts.extend(extra or [])
    return Result(True, f'{symbol}: {money(price)}', facts)


def check_eod(s, opts):
    symbol = opts.symbol if '.' in opts.symbol else opts.symbol + '.US'
    q = expect_ok(*http_json(f'https://eodhd.com/api/real-time/{urllib.parse.quote(symbol)}?'
                             + urllib.parse.urlencode({'api_token': s['API_KEY'], 'fmt': 'json'})),
                  'EOD Historical Data')
    if not isinstance(q, dict) or q.get('close') in (None, 'NA'):
        raise CheckFailed(f'no quote for {symbol}: {error_text(q)}')
    return _quote(symbol, q['close'], q.get('change'), q.get('change_p'))


def check_fmp(s, opts):
    q = expect_ok(*http_json('https://financialmodelingprep.com/stable/quote?'
                             + urllib.parse.urlencode({'symbol': opts.symbol, 'apikey': s['API_KEY']})),
                  'Financial Modeling Prep')
    if not isinstance(q, list) or not q:
        raise CheckFailed(f'no quote for {opts.symbol}: {error_text(q)}')
    q = q[0]
    percent = q.get('changePercentage', q.get('changesPercentage'))
    return _quote(q.get('name') or opts.symbol, q.get('price'), q.get('change'), percent)


def check_fred(s, opts):
    q = expect_ok(*http_json('https://api.stlouisfed.org/fred/series/observations?' + urllib.parse.urlencode({
        'series_id': 'CPIAUCSL', 'api_key': s['API_KEY'], 'file_type': 'json',
        'sort_order': 'desc', 'limit': 13})), 'FRED')
    obs = [o for o in q.get('observations', []) if o.get('value') not in (None, '.')]
    if not obs:
        raise CheckFailed(f'no data: {error_text(q)}')
    latest = obs[0]
    facts = [('Index', latest['value']), ('Month', latest['date'][:7])]
    if len(obs) >= 13:
        rate = (float(latest['value']) / float(obs[12]['value']) - 1) * 100
        facts.insert(0, ('Inflation, last 12 months', f'{rate:.1f}%'))
        headline = f'US inflation: {rate:.1f}% a year (CPI, {latest["date"][:7]})'
    else:
        headline = f'US consumer price index: {latest["value"]} ({latest["date"][:7]})'
    return Result(True, headline, facts)


def check_alphavantage(s, opts):
    q = expect_ok(*http_json('https://www.alphavantage.co/query?' + urllib.parse.urlencode(
        {'function': 'GLOBAL_QUOTE', 'symbol': opts.symbol, 'apikey': s['API_KEY']})), 'Alpha Vantage')
    if not isinstance(q, dict) or not q.get('Global Quote'):
        # 200 with a note: rate limit, premium-only, or an unknown symbol
        raise CheckFailed(q.get('Information') or q.get('Note') or error_text(q)
                          if isinstance(q, dict) else str(q)[:200])
    g = q['Global Quote']
    result = _quote(g.get('01. symbol', opts.symbol), g.get('05. price'), g.get('09. change'),
                    str(g.get('10. change percent', '')).rstrip('%'))
    result.verified = False
    result.warning = ('Alpha Vantage answers this call even for keys it doesn\'t know, so a quote '
                      'here doesn\'t prove the key is yours. A wrong key fails on its premium calls.')
    return result


def check_marketstack(s, opts):
    q = expect_ok(*http_json('https://api.marketstack.com/v2/eod/latest?' + urllib.parse.urlencode(
        {'access_key': s['API_KEY'], 'symbols': opts.symbol})), 'Marketstack')
    data = (q.get('data') or []) if isinstance(q, dict) else []
    if not data:
        raise CheckFailed(f'no quote for {opts.symbol}: {error_text(q)}')
    d = data[0]
    return _quote(d.get('symbol', opts.symbol), d.get('close'),
                  extra=[('Trading day', str(d.get('date', ''))[:10])])


def check_finnhub(s, opts):
    q = expect_ok(*http_json('https://finnhub.io/api/v1/quote?' + urllib.parse.urlencode(
        {'symbol': opts.symbol, 'token': s['API_KEY']})), 'Finnhub')
    if not isinstance(q, dict) or not q.get('c'):
        raise CheckFailed(f'no quote for {opts.symbol} (an unknown symbol gives a price of 0)')
    return _quote(opts.symbol, q['c'], q.get('d'), q.get('dp'))


def check_coinapi(s, opts):
    q = expect_ok(*http_json('https://rest.coinapi.io/v1/exchangerate/BTC/USD',
                             {'X-CoinAPI-Key': s['API_KEY']}), 'CoinAPI')
    if not isinstance(q, dict) or 'rate' not in q:
        raise CheckFailed(error_text(q))
    return Result(True, f'1 BTC = {money(q["rate"])} USD',
                  [('Rate', money(q['rate'])), ('As of', str(q.get('time', ''))[:19].replace('T', ' '))])


def check_tiingo(s, opts):
    q = expect_ok(*http_json(f'https://api.tiingo.com/tiingo/daily/{urllib.parse.quote(opts.symbol.lower())}/prices',
                             {'Authorization': f'Token {s["API_KEY"]}'}), 'Tiingo')
    if not isinstance(q, list) or not q:
        raise CheckFailed(f'no prices for {opts.symbol}: {error_text(q)}')
    d = q[-1]
    return _quote(opts.symbol.upper(), d.get('close'), extra=[('Trading day', str(d.get('date', ''))[:10])])


# --- Services and notifications -------------------------------------------------------------

def check_paperless(s, opts):
    base = s['URL'].rstrip('/')
    headers = {'Authorization': f'Token {s["TOKEN"]}', 'Accept': 'application/json'}
    stats = expect_ok(*http_json(base + '/api/statistics/', headers), 'Paperless')
    if not isinstance(stats, dict):
        raise CheckFailed(f'{base} doesn\'t look like Paperless-ngx (no JSON from /api/statistics/)')
    total = stats.get('documents_total', '?')
    facts = [('Documents', f'{total:,}' if isinstance(total, int) else total),
             ('In the inbox', stats.get('documents_inbox', '?'))]
    for label, key in (('Correspondents', 'correspondent_count'), ('Tags', 'tag_count')):
        if key in stats:
            facts.append((label, stats[key]))
    status, latest = http_json(base + '/api/documents/?page_size=1&ordering=-added&fields=title,added', headers)
    if status == 200 and isinstance(latest, dict) and latest.get('results'):
        doc = latest['results'][0]
        facts.append(('Newest document', f'{doc.get("title", "")} ({str(doc.get("added", ""))[:10]})'))
    return Result(True, f'Paperless: {facts[0][1]} documents, '
                        f'{stats.get("documents_inbox", "?")} in the inbox', facts)


def check_gitea(s, opts):
    try:
        import gitea_client
        user = gitea_client.get_authenticated_user(s['URL'].rstrip('/'), s['TOKEN'])
        repos = gitea_client.list_user_repo_details(s['URL'].rstrip('/'), s['TOKEN'])
    except Exception as e:  # GiteaApiError carries a user-facing message
        raise CheckFailed(str(e))
    recent = ', '.join(r['full_name'] for r in repos[:3]) or '(none)'
    return Result(True, f'Signed in to Gitea as {user}: {len(repos)} repos',
                  [('User', user), ('Repos', len(repos)), ('Most recently updated', recent)])


def check_pushover(s, opts):
    if not opts.notify:
        payload = expect_ok(*http_json('https://api.pushover.net/1/users/validate.json', data={
            'token': s['TOKEN'], 'user': s['USER_KEY']}), 'Pushover')
        devices = ', '.join(payload.get('devices') or []) or '(none)'
        return Result(True, 'Pushover accepts both keys', [('Devices', devices)])
    from notify_send import NotifyError, send_pushover
    try:
        outcome = send_pushover(s['TOKEN'], s['USER_KEY'], 'Test a Secret',
                                'Your Pushover keys work. 🎉', priority=0)
    except NotifyError as e:
        raise CheckFailed(str(e))
    return Result(True, '📱 Sent: check your phone', [('Pushover said', outcome)])


def check_prowl(s, opts):
    if not opts.notify:
        status, text = http_json('https://api.prowlapp.com/publicapi/verify?'
                                 + urllib.parse.urlencode({'apikey': s['TOKEN']}))
        if status != 200:
            raise CheckFailed(f'Prowl rejected the key ({status})')
        left = re.search(r'remaining="(\d+)"', str(text))
        return Result(True, 'Prowl accepts the key',
                      [('API calls left this hour', left.group(1) if left else '?')])
    from notify_send import NotifyError, send_prowl
    try:
        outcome = send_prowl(s['TOKEN'], 'Test a Secret', 'Your Prowl key works. 🎉', priority=0,
                             application='Script-Server')
    except NotifyError as e:
        raise CheckFailed(str(e))
    return Result(True, '📱 Sent: check your phone', [('Prowl said', outcome)])


# --- Registry -------------------------------------------------------------------------------
# product -> (label, group, keys it needs, check). Every product in conf/secrets_defaults.json
# must be here (src/tests/secret_test_test.py checks it), with the same keys.

CHECKS = {
    'anthropic': ('Anthropic (Claude)', 'AI', ['API_KEY'], check_anthropic),
    'openai': ('OpenAI', 'AI', ['API_KEY'], check_openai),
    'gemini': ('Google Gemini', 'AI', ['API_KEY'], check_gemini),
    'xai': ('xAI (Grok)', 'AI', ['API_KEY'], check_xai),
    'deepseek': ('DeepSeek', 'AI', ['API_KEY'], check_deepseek),
    'eod': ('EOD Historical Data', 'Finance', ['API_KEY'], check_eod),
    'fmp': ('Financial Modeling Prep', 'Finance', ['API_KEY'], check_fmp),
    'fred': ('FRED (US economic data)', 'Finance', ['API_KEY'], check_fred),
    'alphavantage': ('Alpha Vantage', 'Finance', ['API_KEY'], check_alphavantage),
    'marketstack': ('Marketstack', 'Finance', ['API_KEY'], check_marketstack),
    'finnhub': ('Finnhub', 'Finance', ['API_KEY'], check_finnhub),
    'coinapi': ('CoinAPI', 'Finance', ['API_KEY'], check_coinapi),
    'tiingo': ('Tiingo', 'Finance', ['API_KEY'], check_tiingo),
    'paperless': ('Paperless-ngx', 'Services', ['URL', 'TOKEN'], check_paperless),
    'gitea': ('Gitea', 'Services', ['URL', 'TOKEN'], check_gitea),
    'pushover': ('Pushover', 'Notifications', ['TOKEN', 'USER_KEY'], check_pushover),
    'prowl': ('Prowl', 'Notifications', ['TOKEN'], check_prowl),
}
ICONS = {'AI': '🤖', 'Finance': '📈', 'Services': '🗂️', 'Notifications': '🔔'}
ALL_CHOICE = 'all | All secrets that are set'


def choices():
    """The Secret dropdown's lines, '<product> | <group>: <label>'. The runner fills its list
    from here (--choices), so a provider added to CHECKS appears without changing the runner,
    which an existing install never gets refreshed."""
    return [ALL_CHOICE] + [f'{p} | {group}: {label}' for p, (label, group, _k, _c) in CHECKS.items()]


def run_check(product, opts):
    """(product, Result or None if not set, missing keys, seconds)."""
    label, _group, keys, check = CHECKS[product]
    # register=False: this only tests what's configured. The defaults file already lists every
    # placeholder, so a miss here isn't a new requirement (see CLAUDE.md, Secrets Store).
    values = {k: get_secret(product, k, register=False) for k in keys}
    missing = [k for k, v in values.items() if not v]
    if missing:
        return product, None, missing, 0.0
    started = time.time()
    try:
        result = check(values, opts)
    except CheckFailed as e:
        result = Result(False, str(e))
    except Exception as e:  # a bug or an unexpected reply: say so, don't crash the page
        result = Result(False, f'unexpected {type(e).__name__}: {e}')
    secrets = [v for k, v in values.items() if k != 'URL' and v and len(v) >= 6]
    for field in ('headline', 'quote', 'warning'):
        text = getattr(result, field)
        if text:
            setattr(result, field, redact(text, secrets))
    result.facts = [(k, redact(str(v), secrets)) for k, v in result.facts]
    return product, result, [], time.time() - started


MASKED = re.compile(r'[\w.-]*?\*{3,}[\w-]*')


def redact(text, secrets):
    """Never show a key, even inside a provider's error text: the key itself, and the masked
    fragments some providers echo back (OpenAI 'sk-proj-****abcd', DeepSeek '****abcd').
    A URL isn't a secret and stays readable."""
    for value in secrets:
        text = text.replace(value, '•••')
    return MASKED.sub('•••', text)


# --- Output -----------------------------------------------------------------------------------

STYLE = """
<style>
  body { font-family: Roboto, -apple-system, 'Segoe UI', sans-serif; margin: 0; padding: 4px;
         color: rgba(0,0,0,.87); background: #fff; }
  h2 { font-size: 15px; font-weight: 500; margin: 14px 0 8px; color: #3949ab; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
  .card { border: 1px solid #e0e0e0; border-left: 4px solid #9e9e9e; border-radius: 6px;
          padding: 10px 12px; background: #fafafa; }
  .card.ok { border-left-color: #43a047; } .card.fail { border-left-color: #e53935; }
  .card.unset { border-left-color: #bdbdbd; color: rgba(0,0,0,.56); }
  .name { font-weight: 500; } .badge { float: right; font-size: 12px; font-weight: 500; }
  .card.unverified { border-left-color: #f9a825; } .unverified .badge { color: #e65100; }
  .ok .badge { color: #2e7d32; } .fail .badge { color: #c62828; } .unset .badge { color: #757575; }
  .headline { margin: 6px 0; font-size: 15px; }
  .fail .headline { font-size: 13px; color: #b71c1c; }
  table { border-collapse: collapse; font-size: 13px; width: 100%; }
  td { padding: 2px 0; vertical-align: top; } td:first-child { color: rgba(0,0,0,.56); width: 40%; }
  td.up { color: #2e7d32; } td.down { color: #c62828; }
  .quote { margin: 8px 0 4px; padding: 8px 10px; background: #e8eaf6; border-radius: 10px;
           white-space: pre-wrap; font-size: 14px; }
  .warn { margin-top: 6px; font-size: 12px; color: #ad1457; }
  .meta { font-size: 12px; color: rgba(0,0,0,.56); margin-top: 6px; }
  a { color: #3949ab; }
</style>
"""


def card_html(product, result, missing, seconds):
    label, group, keys, _check = CHECKS[product]
    e = html.escape
    if result is None:
        picks = ', '.join(f'<b>{e(dropdown_entry_label(product, k))}</b>' for k in missing)
        return (f'<div class="card unset"><span class="badge">NOT SET</span>'
                f'<div class="name">{ICONS[group]} {e(label)}</div>'
                f'<div class="meta">In <a href="{e(secrets_manager_link())}" target="_top">Secrets '
                f'Manager</a>, pick {picks} from the Entry dropdown and set it.</div></div>')
    state, badge = (('ok', 'OK') if result.ok and result.verified
                    else ('unverified', 'UNVERIFIED') if result.ok else ('fail', 'FAILED'))
    parts = [f'<div class="card {state}"><span class="badge">{badge}</span>',
             f'<div class="name">{ICONS[group]} {e(label)}</div>',
             f'<div class="headline">{e(result.headline)}</div>']
    if result.quote:
        parts.append(f'<div class="quote">{e(result.quote)}</div>')
    if result.facts:
        parts.append('<table>' + ''.join(f'<tr><td>{e(str(k))}</td><td{move_class(v)}>{e(str(v))}</td></tr>'
                                         for k, v in result.facts) + '</table>')
    if result.warning:
        parts.append(f'<div class="warn">{e(result.warning)}</div>')
    parts.append(f'<div class="meta">{seconds:.1f}s</div></div>')
    return ''.join(parts)


def move_class(value):
    text = str(value)
    return ' class="up"' if text.startswith('▲') else ' class="down"' if text.startswith('▼') else ''


def parse_args():
    env = os.environ.get
    p = argparse.ArgumentParser(description='Test a secret from the Secrets Store against its service.')
    # PARAM_ variables first (a cleared field arrives as ''), so blank stays blank (see SCRIPTING.md)
    p.add_argument('--secret', default=env('PARAM_SECRET', 'all'),
                   help='a product name, or a line from --choices')
    p.add_argument('--choices', action='store_true', help='print the dropdown lines and exit')
    p.add_argument('--symbol', default=env('PARAM_SYMBOL', DEFAULT_SYMBOL))
    p.add_argument('--prompt', default=env('PARAM_PROMPT', DEFAULT_PROMPT))
    p.add_argument('--ask-ai', default=env('PARAM_ASK_AI', 'yes'), choices=['yes', 'no'])
    p.add_argument('--notify', default=env('PARAM_NOTIFY', 'yes'), choices=['yes', 'no'])
    opts = p.parse_args()
    opts.secret = (opts.secret or 'all').split(' | ')[0].strip()
    opts.symbol = (opts.symbol or DEFAULT_SYMBOL).strip().upper()
    opts.prompt = (opts.prompt or DEFAULT_PROMPT).strip()
    opts.ask_ai = opts.ask_ai == 'yes'
    opts.notify = opts.notify == 'yes'
    return opts


def main():
    opts = parse_args()
    if opts.choices:
        print('\n'.join(choices()), flush=True)
        return 0
    if opts.secret != 'all' and opts.secret not in CHECKS:
        print(f'Unknown secret "{html.escape(opts.secret)}". Choose one of: all, '
              + ', '.join(sorted(CHECKS)), flush=True)
        return 2

    products = list(CHECKS) if opts.secret == 'all' else [opts.secret]
    print(STYLE, flush=True)

    if opts.secret == 'all':
        # Only test what's set; list the rest at the end.
        results = {}
        to_run = [p for p in products if all(get_secret(p, k, register=False) for k in CHECKS[p][2])]
        unset = [p for p in products if p not in to_run]
        print(f'<div class="meta">Testing {len(to_run)} of {len(products)} secrets '
              f'({len(unset)} not set). Results appear as they finish.</div>', flush=True)
        print('<div class="grid">', flush=True)
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(run_check, p, opts) for p in to_run]
            for future in as_completed(futures):
                product, result, missing, seconds = future.result()
                results[product] = result
                print(card_html(product, result, missing, seconds), flush=True)
        print('</div>', flush=True)
        if unset:
            print('<h2>Not set yet</h2><div class="grid">', flush=True)
            for product in unset:
                _p, result, missing, seconds = run_check(product, opts)
                print(card_html(product, result, missing, seconds), flush=True)
            print('</div>', flush=True)
        failed = sum(1 for r in results.values() if r and not r.ok)
        passed = sum(1 for r in results.values() if r and r.ok and r.verified)
        unsure = sum(1 for r in results.values() if r and r.ok and not r.verified)
        print(f'<div class="meta">{passed} working, {unsure} unverified, {failed} failed, '
              f'{len(unset)} not set. '
              f'Test a Secret {html.escape(own_version())}.</div>', flush=True)
        return 1 if failed else 0

    product, result, missing, seconds = run_check(products[0], opts)
    print('<div class="grid">' + card_html(product, result, missing, seconds) + '</div>', flush=True)
    print(f'<div class="meta">Test a Secret {html.escape(own_version())}.</div>', flush=True)
    if result is None:
        return 1
    return 0 if result.ok else 1


if __name__ == '__main__':
    sys.exit(main())
