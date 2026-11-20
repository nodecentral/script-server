"""Test a Secret (scripts/secret_test.py): every default secret has a test, and the checks read
providers' replies correctly. Replies are canned: no network, no real keys."""
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'scripts', 'shared'))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

import secret_test  # noqa: E402

DEFAULTS = os.path.join(REPO, 'conf', 'secrets_defaults.json')
RUNNER = os.path.join(REPO, 'conf', 'runners', 'secret_test.json')


def opts(**overrides):
    values = dict(symbol='AAPL', prompt='hi', ask_ai=True, notify=True)
    values.update(overrides)
    return SimpleNamespace(**values)


class EveryDefaultHasATest(unittest.TestCase):
    """The rule: a secret in conf/secrets_defaults.json always arrives with a way to try it."""

    def setUp(self):
        with open(DEFAULTS, encoding='utf-8') as f:
            self.defaults = {}
            for entry in json.load(f):
                self.defaults.setdefault(entry['product'], set()).add(entry['key'])

    def test_every_default_secret_has_a_check(self):
        for product, keys in self.defaults.items():
            self.assertIn(product, secret_test.CHECKS,
                          f'{product} is in secrets_defaults.json but Test a Secret has no check for it')
            self.assertEqual(keys, set(secret_test.CHECKS[product][2]),
                             f'{product}: the check and secrets_defaults.json list different keys')

    def test_every_check_is_a_default_secret(self):
        for product in secret_test.CHECKS:
            self.assertIn(product, self.defaults,
                          f'Test a Secret checks {product}, which secrets_defaults.json does not list')

    def test_dropdown_lines_parse_back_to_checks(self):
        lines = secret_test.choices()
        self.assertEqual(secret_test.ALL_CHOICE, lines[0])
        self.assertEqual(['all'] + list(secret_test.CHECKS), [line.split(' | ')[0] for line in lines])

    def test_runner_default_is_a_dropdown_line(self):
        with open(RUNNER, encoding='utf-8') as f:
            runner = json.load(f)
        secret = next(p for p in runner['parameters'] if p['env_var'] == 'PARAM_SECRET')
        self.assertIn(secret['default'], secret_test.choices())
        self.assertIn('secret_test.py --choices', secret['values']['script'])


class ChecksReadReplies(unittest.TestCase):
    def reply(self, *responses):
        return mock.patch.object(secret_test, 'http_json', side_effect=list(responses))

    def test_finnhub_quote(self):
        with self.reply((200, {'c': 231.5, 'd': -1.25, 'dp': -0.54})):
            r = secret_test.check_finnhub({'API_KEY': 'k'}, opts())
        self.assertTrue(r.ok)
        self.assertEqual('AAPL: 231.50', r.headline)
        self.assertIn(('Today', '▼ -1.25 (-0.54%)'), r.facts)

    def test_finnhub_unknown_symbol(self):
        with self.reply((200, {'c': 0, 'd': None})):
            with self.assertRaises(secret_test.CheckFailed):
                secret_test.check_finnhub({'API_KEY': 'k'}, opts(symbol='NOPE'))

    def test_rejected_key(self):
        with self.reply((401, {'error': 'Invalid API key.'})):
            with self.assertRaisesRegex(secret_test.CheckFailed, 'rejected the key \\(401\\): Invalid API key'):
                secret_test.check_finnhub({'API_KEY': 'k'}, opts())

    def test_fred_inflation(self):
        obs = [{'date': '2026-10-01', 'value': '330.0'}] + \
              [{'date': f'2026-{m:02d}-01', 'value': '325.0'} for m in range(9, 0, -1)] + \
              [{'date': '2025-12-01', 'value': '322.0'}, {'date': '2025-11-01', 'value': '321.0'},
               {'date': '2025-10-01', 'value': '320.0'}]
        with self.reply((200, {'observations': obs})):
            r = secret_test.check_fred({'API_KEY': 'k'}, opts())
        self.assertEqual('US inflation: 3.1% a year (CPI, 2026-10)', r.headline)

    def test_alphavantage_warns_and_reports_rate_limit(self):
        with self.reply((200, {'Global Quote': {'01. symbol': 'AAPL', '05. price': '231.5',
                                                '09. change': '1.5', '10. change percent': '0.65%'}})):
            r = secret_test.check_alphavantage({'API_KEY': 'k'}, opts())
        self.assertTrue(r.ok)
        self.assertFalse(r.verified)
        self.assertIn('doesn\'t prove', r.warning)
        self.assertIn('UNVERIFIED', secret_test.card_html('alphavantage', r, [], 0.1))
        with self.reply((200, {'Information': 'Thank you for using Alpha Vantage! Our standard API rate limit is 25 requests per day.'})):
            with self.assertRaisesRegex(secret_test.CheckFailed, 'rate limit'):
                secret_test.check_alphavantage({'API_KEY': 'k'}, opts())

    def test_openai_style_lists_models_then_chats_with_a_small_one(self):
        models = {'data': [{'id': 'gpt-5'}, {'id': 'gpt-5-mini'}, {'id': 'gpt-realtime-mini'}, {'id': 'tts-1'}]}
        chat = {'model': 'gpt-5-mini', 'choices': [{'message': {'content': 'Fans hum softly'}}],
                'usage': {'prompt_tokens': 12, 'completion_tokens': 9}}
        with self.reply((200, models), (200, chat)) as http:
            r = secret_test.check_openai({'API_KEY': 'k'}, opts())
        self.assertEqual('gpt-5-mini', http.call_args_list[1].args[2]['model'])
        self.assertEqual('Fans hum softly', r.quote)
        self.assertIn(('Tokens', '12 in, 9 out'), r.facts)

    def test_ai_key_only_mode_makes_no_chat_call(self):
        with self.reply((200, {'data': [{'id': 'deepseek-chat'}]})) as http:
            r = secret_test.check_deepseek({'API_KEY': 'k'}, opts(ask_ai=False))
        self.assertEqual(1, http.call_count)
        self.assertEqual('Key works: 1 models available', r.headline)

    def test_gemini_picks_a_flash_model(self):
        models = {'models': [{'name': 'models/gemini-pro', 'supportedGenerationMethods': ['generateContent']},
                             {'name': 'models/gemini-flash-lite', 'supportedGenerationMethods': ['generateContent']},
                             {'name': 'models/embedding', 'supportedGenerationMethods': ['embedContent']}]}
        reply = {'candidates': [{'content': {'parts': [{'text': 'Disks spin'}]}}],
                 'usageMetadata': {'promptTokenCount': 5, 'candidatesTokenCount': 4}}
        with self.reply((200, models), (200, reply)) as http:
            r = secret_test.check_gemini({'API_KEY': 'k'}, opts())
        self.assertIn('models/gemini-flash-lite:generateContent', http.call_args_list[1].args[0])
        self.assertEqual('Disks spin', r.quote)

    def test_paperless_library(self):
        stats = {'documents_total': 1234, 'documents_inbox': 7, 'tag_count': 40}
        latest = {'results': [{'title': 'Council tax bill', 'added': '2026-11-19T10:00:00Z'}]}
        with self.reply((200, stats), (200, latest)):
            r = secret_test.check_paperless({'URL': 'http://10.0.0.41:8777/', 'TOKEN': 't'}, opts())
        self.assertEqual('Paperless: 1,234 documents, 7 in the inbox', r.headline)
        self.assertIn(('Documents', '1,234'), r.facts)
        self.assertIn(('Newest document', 'Council tax bill (2026-11-19)'), r.facts)

    def test_coinapi_rate(self):
        with self.reply((200, {'time': '2026-11-20T09:15:00.0000000Z', 'rate': 91234.567})):
            r = secret_test.check_coinapi({'API_KEY': 'k'}, opts())
        self.assertEqual('1 BTC = 91,234.57 USD', r.headline)


class RunCheck(unittest.TestCase):
    def test_not_set_is_reported_without_registering_a_placeholder(self):
        with mock.patch.object(secret_test, 'get_secret', return_value=None) as get:
            product, result, missing, _ = secret_test.run_check('paperless', opts())
        self.assertIsNone(result)
        self.assertEqual(['URL', 'TOKEN'], missing)
        for call in get.call_args_list:
            self.assertEqual(False, call.kwargs.get('register'))

    def test_key_is_removed_from_error_text(self):
        key = 'sk-secret-123456'

        def leaky(_s, _o):
            raise secret_test.CheckFailed(f'provider said: key {key} is invalid')

        with mock.patch.object(secret_test, 'get_secret', return_value=key), \
                mock.patch.dict(secret_test.CHECKS, {'finnhub': ('Finnhub', 'Finance', ['API_KEY'], leaky)}):
            _p, result, _m, _s = secret_test.run_check('finnhub', opts())
        self.assertFalse(result.ok)
        self.assertNotIn(key, result.headline)
        self.assertIn('•••', result.headline)

    def test_masked_key_fragments_and_urls(self):
        self.assertEqual('Incorrect API key provided: •••. See docs',
                         secret_test.redact('Incorrect API key provided: sk-proj-****abcd. See docs', []))
        self.assertEqual('Your api key: ••• is invalid',
                         secret_test.redact('Your api key: ****abcd is invalid', []))

        def unreachable(s, _o):
            raise secret_test.CheckFailed(f'Could not reach {s["URL"]}')

        values = {'URL': 'http://10.0.0.41:3011', 'TOKEN': 'gitea-token-123456'}
        with mock.patch.object(secret_test, 'get_secret', side_effect=lambda _p, k, **_kw: values[k]), \
                mock.patch.dict(secret_test.CHECKS, {'gitea': ('Gitea', 'Services', ['URL', 'TOKEN'], unreachable)}):
            _p, result, _m, _s = secret_test.run_check('gitea', opts())
        self.assertEqual('Could not reach http://10.0.0.41:3011', result.headline)

    def test_unexpected_error_becomes_a_failed_card(self):
        def broken(_s, _o):
            return {}['missing']

        with mock.patch.object(secret_test, 'get_secret', return_value='k'), \
                mock.patch.dict(secret_test.CHECKS, {'tiingo': ('Tiingo', 'Finance', ['API_KEY'], broken)}):
            _p, result, _m, _s = secret_test.run_check('tiingo', opts())
        self.assertFalse(result.ok)
        self.assertIn('KeyError', result.headline)


if __name__ == '__main__':
    unittest.main()
