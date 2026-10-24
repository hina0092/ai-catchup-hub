from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from collector.card_trial import (ROOT, JST, MODEL, Rejected, run_trial,
                                  validate_result, request_card, validate_inputs)
from tools.render_card_trial import review_html

NOW = datetime(2026, 10, 24, 12, tzinfo=JST)
ENV = dict(ENABLE_GEMINI='true', GEMINI_BILLING_DISABLED='true',
           GEMINI_FREE_TIER_REVIEWED_ON='2026-10-23', GEMINI_API_KEY='SECRET_TEST_ONLY', GEMINI_MODEL=MODEL)


def result(article=None):
    card = dict(sufficient=True, title='入力からニュースを理解する', lead='短い説明です。',
                changed='何が変わったかを説明します。', example='例えば身近な作業への提案です。',
                caution='実際の効果は未確認です。', diagram=dict(layout='steps', question='何が起きる？',
                nodes=['入力を渡す', '結果を確認'], result='仕組みが分かる'),
                comments=[dict(name=f'人物{i}', text=f'論点{i}について確認したい。', reply_to=None if i % 2 == 0 else i - 1)
                          for i in range(8)])
    if article is not None:
        quote = article['source_text'][:40]
        card.update(article_kind=article['article_kind'], comment_kinds=['question'] * 8,
                    grounding=[dict(field=field, quote=quote) for field in
                               ['title', 'lead', 'changed', 'example', 'caution', 'diagram']])
    return card


class CardTrialTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = json.loads((ROOT / 'validation/card-inputs.json').read_text(encoding='utf-8'))

    def run_trial(self, **options):
        args = dict(live=True, env=ENV, now=NOW, ledger_dir=self.root / 'ledger', sleep=Mock(),
                    provider=Mock(side_effect=lambda *args: result(args[2])))
        args.update(options)
        return run_trial(self.data, self.root / 'report.json', **args)

    def test_dry_run_never_calls_provider_or_needs_key(self):
        provider = Mock(side_effect=AssertionError('must not call'))
        report = self.run_trial(live=False, env={}, provider=provider)
        self.assertEqual(report['mode'], 'dry-run')
        self.assertEqual(len(report['results']), 5)
        self.assertTrue(all(r['status'] == 'input_checked' and 'card' not in r for r in report['results']))
        provider.assert_not_called()

    def test_free_tier_gates_fail_closed(self):
        for change in ({'GEMINI_API_KEY': ''}, {'GEMINI_BILLING_DISABLED': 'false'},
                       {'ENABLE_GEMINI': 'false'}, {'GEMINI_FREE_TIER_REVIEWED_ON': '2026-08-01'},
                       {'GEMINI_MODEL': 'paid-model'}):
            provider = Mock()
            with self.subTest(change=change), self.assertRaises(Rejected):
                self.run_trial(env={**ENV, **change}, provider=provider)
            provider.assert_not_called()

    def test_requests_reserved_before_sending_and_five_per_day(self):
        def provider(*args):
            self.assertTrue(list((self.root / 'ledger').glob('2026-10-24-*.json')))
            return result(args[2])
        report = self.run_trial(provider=provider)
        self.assertEqual([r['status'] for r in report['results']], ['accepted'] * 5)
        changed = deepcopy(self.data)
        for row in changed['articles']:
            row['id'] += '-extra'
        mocked = Mock()
        second = run_trial(changed, self.root / 'second.json', live=True, env=ENV, now=NOW,
                           ledger_dir=self.root / 'ledger', provider=mocked)
        self.assertEqual([r['status'] for r in second['results']], ['daily_limit'] * 5)
        mocked.assert_not_called()

    def test_failure_counts_and_same_day_rerun_does_not_retry(self):
        provider = Mock(side_effect=Rejected('insufficient_evidence'))
        first = self.run_trial(provider=provider)
        self.assertEqual(provider.call_count, 5)
        self.assertTrue(all(r['status'] == 'rejected' for r in first['results']))
        second_provider = Mock()
        second = run_trial(self.data, self.root / 'second.json', live=True, env=ENV, now=NOW,
                           ledger_dir=self.root / 'ledger', provider=second_provider)
        self.assertTrue(all(r['status'] == 'already_attempted_today' for r in second['results']))
        second_provider.assert_not_called()

    def test_429_stops_current_and_later_runs(self):
        provider = Mock(side_effect=HTTPError('https://example.com', 429, 'SECRET', {}, None))
        first = self.run_trial(provider=provider)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(first['results'][0]['status'], 'rate_limit')
        second_provider = Mock()
        second = run_trial(self.data, self.root / 'second.json', live=True, env=ENV, now=NOW,
                           ledger_dir=self.root / 'ledger', provider=second_provider)
        self.assertTrue(all(r['status'] == 'stopped_for_today' for r in second['results']))
        second_provider.assert_not_called()

    def test_existing_output_and_concurrent_trial_refused_before_request(self):
        (self.root / 'report.json').write_text('keep')
        provider = Mock()
        with self.assertRaises(Rejected):
            self.run_trial(provider=provider)
        self.assertEqual((self.root / 'report.json').read_text(), 'keep')
        provider.assert_not_called()
        (self.root / 'ledger').mkdir()
        (self.root / 'ledger/trial.lock').touch()
        with self.assertRaises(Rejected):
            run_trial(self.data, self.root / 'other.json', live=True, env=ENV, now=NOW,
                      ledger_dir=self.root / 'ledger', provider=provider)
        provider.assert_not_called()

    def test_rejects_bad_shape_parent_duplicate_markup_and_short_input(self):
        for key, value in [('comments', []), ('diagram', {'layout': 'execute_code'}), ('title', '<script>日本語</script>')]:
            with self.subTest(key=key), self.assertRaises(Rejected):
                validate_result({**result(), key: value})
        for parent in (0, True, -1, 99):
            bad = result(); bad['comments'][0]['reply_to'] = parent
            with self.assertRaises(Rejected):
                validate_result(bad)
        bad = result(); bad['comments'][1]['text'] = bad['comments'][0]['text']
        with self.assertRaises(Rejected):
            validate_result(bad)
        bad = deepcopy(self.data); bad['articles'][0]['source_text'] = '短い'
        with self.assertRaises(Rejected):
            validate_inputs(bad)

    def test_optional_diagram_and_short_text_are_accepted(self):
        good = result(); good.update(diagram=None, changed='更新。')
        self.assertEqual(validate_result(good)['changed'], '更新。')

    def test_transport_incomplete_and_oversized_rejected_without_payload_leaks(self):
        for data in [b'x' * 1_000_001, json.dumps({'candidates': [{'finishReason': 'MAX_TOKENS'}]}).encode(), b'SECRET']:
            response = Mock(); response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
            response.read.return_value = data
            with patch('collector.card_trial.build_opener') as opener:
                opener.return_value.open.return_value = response
                with self.assertRaises(Rejected) as caught:
                    request_card(MODEL, 'SECRET', self.data['articles'][0])
                self.assertNotIn('SECRET', str(caught.exception))

    def test_live_adapter_uses_one_bounded_request_without_tools_or_url_key(self):
        response = Mock(); response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({'candidates': [{'finishReason': 'STOP',
            'content': {'parts': [{'text': json.dumps(result(), ensure_ascii=False)}]}}]}).encode()
        with patch('collector.card_trial.build_opener') as opener:
            opener.return_value.open.return_value = response
            value = request_card(MODEL, 'SECRET', self.data['articles'][0])
            req = opener.return_value.open.call_args.args[0]
            payload = json.loads(req.data)
            self.assertEqual(opener.return_value.open.call_count, 1)
            self.assertNotIn('SECRET', req.full_url)
            self.assertNotIn('SECRET', req.data.decode())
            self.assertNotIn('tools', payload)
            self.assertEqual(payload['generationConfig']['maxOutputTokens'], 6144)
            self.assertEqual(len(validate_result(value)['comments']), 8)

    def test_report_excludes_secret_errors_and_rejected_raw_output(self):
        self.run_trial(provider=Mock(side_effect=ValueError('SECRET_TEST_ONLY')))
        raw = (self.root / 'report.json').read_text(encoding='utf-8')
        self.assertNotIn('SECRET_TEST_ONLY', raw)
        self.assertNotIn('source_text', raw)

    def test_review_page_escapes_metadata_and_has_all_comments(self):
        report = self.run_trial()
        report['results'][0]['source'] = '<script>alert(1)</script>'
        page = review_html(report)
        self.assertEqual(page.count('<li>'), 40)
        self.assertNotIn('<script>', page)
        self.assertNotIn('続きを読む', page)
        self.assertIn('AIによる架空の会話', page)
