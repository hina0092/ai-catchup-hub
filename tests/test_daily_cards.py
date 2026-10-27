from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock
from urllib.error import HTTPError

from collector.card_trial import ROOT, Rejected, exclusive_json
from collector.daily_cards import (checked_feed, configuration, empty_feed, generate,
                                   candidates, DAILY_PROMPT)
from collector.article_source import article_text
from tests.test_card_trial import ENV, NOW, result

CONFIG = json.loads((ROOT / 'collector/daily_config.json').read_text(encoding='utf-8'))
EXCERPT = 'これは入力から抽出された記事本文のテストです。' * 40


def row(index=0, host='zenn.dev', source='Zenn AI', **extra):
    return dict(title='AIのしくみを試した記録', url=f'https://{host}/articles/daily-{index}',
                source=source, published_at=(NOW - timedelta(hours=index)).isoformat(), **extra)


def provider(model, key, article):
    return result({**article, 'article_kind': 'practice' if article['article_kind'] == 'auto' else article['article_kind']})


class DailyCardsTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.ledger = Path(self.temp.name)

    def generate(self, rows=None, feed=None, **changes):
        args = dict(rows=rows if rows is not None else [row(i) for i in range(5)],
                    feed=feed or empty_feed(), ledger=self.ledger, config=CONFIG, env=ENV,
                    persist=Mock(), now=NOW, provider=provider,
                    reader=Mock(return_value=EXCERPT), sleep=Mock())
        args.update(changes)
        return generate(**args)

    def test_three_requests_reserved_before_calls_and_not_repeated(self):
        durable = []
        def persist(ledger):
            durable[:] = list(ledger.glob('2026-10-24-*.json'))
        def send(*args):
            self.assertGreater(len(durable), send.calls)
            send.calls += 1
            return provider(*args)
        send.calls = 0
        feed = self.generate(persist=persist, provider=send)
        self.assertEqual(len(feed['entries']), 3)
        self.assertEqual(send.calls, 3)
        self.assertEqual(self.generate(feed=feed, provider=send)['status'], 'budget_limit')
        self.assertEqual(send.calls, 3)
        self.assertNotIn('source_text', json.dumps(feed))
        self.assertNotIn('grounding', json.dumps(feed))

    def test_manual_trial_budget_is_shared_and_no_api_is_sent(self):
        for i in range(5):
            exclusive_json(self.ledger / f'2026-10-24-trial{i}.json', {})
        send = Mock()
        self.assertEqual(self.generate(provider=send)['status'], 'budget_limit')
        send.assert_not_called()

    def test_morning_schedule_uses_new_day_budget_once_without_resetting_previous_reservations(self):
        night = NOW.replace(hour=23, minute=17)
        for i in range(3):
            exclusive_json(self.ledger / f'{night.date().isoformat()}-prior{i}.json', {})
        send = Mock(side_effect=provider)
        blocked = self.generate(now=night, provider=send)
        self.assertEqual(blocked['status'], 'budget_limit')
        send.assert_not_called()
        morning = (night + timedelta(days=1)).replace(hour=0, minute=17)
        feed = self.generate(now=morning, provider=send, feed=blocked)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(feed['status'], 'ready')
        self.assertEqual(len(feed['entries']), 3)
        self.assertEqual(len(list(self.ledger.glob('*.json'))), 6)
        later = self.generate(now=morning.replace(hour=5), provider=send, feed=feed)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(later['status'], 'budget_limit')
        self.assertEqual(later['entries'], feed['entries'])
        self.assertEqual(later['updated_at'], feed['updated_at'])

    def test_failed_persistence_prevents_provider(self):
        send = Mock()
        with self.assertRaises(OSError):
            self.generate(provider=send, persist=Mock(side_effect=OSError('offline')))
        send.assert_not_called()

    def test_rejected_results_use_budget_and_do_not_replace_previous_cards(self):
        previous = self.generate(rows=[row()])
        broken = provider(None, None, dict(article_kind='practice', source_text=EXCERPT))
        broken['grounding'][0]['quote'] = '本文に存在しない引用'
        send = Mock(return_value=broken)
        updated = self.generate(rows=[row(i) for i in range(1, 4)], feed=previous, provider=send)
        self.assertEqual(updated['entries'], previous['entries'])
        self.assertEqual(updated['updated_at'], previous['updated_at'])
        self.assertEqual(updated['status'], 'invalid_outputs')
        self.assertEqual(send.call_count, 2)

    def test_source_gaps_do_not_call_model_and_can_try_next_publisher(self):
        send = Mock(side_effect=provider)
        read = Mock(side_effect=['tiny', EXCERPT])
        feed = self.generate(rows=[row(), row(1)], reader=read, provider=send)
        self.assertEqual(len(feed['entries']), 1)
        self.assertEqual(send.call_count, 1)

    def test_rejection_logs_fixed_reason_and_phase_without_source_or_raw_output(self):
        secret = 'PRIVATE_SOURCE_AND_API_KEY'
        def invalid(*args):
            value = provider(*args)
            value['grounding'][0]['quote'] = secret
            return value
        with self.assertLogs('collector.daily_cards', level='WARNING') as logs:
            feed = self.generate(rows=[row()], provider=invalid)
        diagnostic = json.loads(logs.records[0].getMessage())
        self.assertEqual(diagnostic, dict(event='daily_card_rejected', attempt=1,
            phase='validation', reason='grounding_quote'))
        self.assertEqual(feed['status'], 'invalid_outputs')
        self.assertNotIn(secret, str(logs.output) + json.dumps(feed))
        self.assertNotIn('diagnostics', feed)

    def test_response_rejections_are_allowlisted_and_unknown_messages_are_redacted(self):
        send = Mock(side_effect=[Rejected('incomplete_response'),
            Rejected('PRIVATE_KEY\n::warning::injected'), Rejected('result_schema')])
        with self.assertLogs('collector.daily_cards', level='WARNING') as logs:
            feed = self.generate(provider=send)
        records = [json.loads(r.getMessage()) for r in logs.records]
        self.assertEqual(records, [dict(event='daily_card_rejected', attempt=i + 1,
            phase='response', reason=reason) for i, reason in enumerate(
                ['incomplete_response', 'invalid_result', 'result_schema'])])
        self.assertEqual(send.call_count, 3)
        self.assertEqual(len(list(self.ledger.glob('*.json'))), 3)
        self.assertEqual(feed['entries'], [])
        self.assertNotIn('PRIVATE_KEY', str(logs.output))
        self.assertNotIn('::warning::', str(logs.output))

    def test_valid_generation_emits_no_rejection_diagnostic(self):
        with self.assertNoLogs('collector.daily_cards', level='WARNING'):
            feed = self.generate(rows=[row()])
        self.assertEqual(feed['status'], 'ready')

    def test_429_stops_without_retry_and_persists_stop_marker(self):
        send = Mock(side_effect=HTTPError('https://example.com', 429, 'limit', {}, None))
        persist = Mock()
        feed = self.generate(provider=send, persist=persist)
        self.assertEqual(feed['status'], 'rate_limit')
        self.assertTrue((self.ledger / '2026-10-24.stop').exists())
        self.assertEqual(persist.call_count, 2)
        self.generate(provider=send)
        self.assertEqual(send.call_count, 1)

    def test_free_tier_gate_expiry_and_paid_model_fail_closed(self):
        for change in ({'ENABLE_GEMINI': 'false'}, {'GEMINI_BILLING_DISABLED': 'false'},
                       {'GEMINI_MODEL': 'paid'}, {'GEMINI_FREE_TIER_REVIEWED_ON': '2026-08-01'}):
            send = Mock()
            with self.subTest(change=change):
                self.assertEqual(self.generate(env={**ENV, **change}, provider=send)['status'], 'generation_paused')
                send.assert_not_called()

    def test_candidates_skip_duplicates_future_unsafe_and_old_and_prefer_publishers(self):
        rows = [row(), row(), row(1), row(2, 'github.blog', 'GitHub Blog AI & ML'),
                {**row(3), 'published_at': (NOW + timedelta(days=1)).isoformat()},
                {**row(4), 'published_at': (NOW - timedelta(days=60)).isoformat()},
                {**row(5), 'url': 'https://zenn.dev@127.0.0.1/private'},
                {**row(6), 'published_at': None}]
        selected = candidates(rows, empty_feed(), CONFIG, NOW)
        self.assertEqual([r['url'] for r in selected], [row()['url'], row(2, 'github.blog')['url'], row(1)['url']])

    def test_success_is_not_regenerated_next_day_and_timestamp_is_honest(self):
        feed = self.generate(rows=[row()])
        send = Mock()
        after = self.generate(rows=[row()], feed=feed, provider=send, now=NOW + timedelta(days=1))
        send.assert_not_called()
        self.assertEqual(after['status'], 'no_new')
        self.assertEqual(after['updated_at'], feed['updated_at'])
        self.assertNotEqual(after['checked_at'], feed['checked_at'])

    def test_known_guide_misclassification_and_unsupported_mobile_are_rejected(self):
        guide = {**row(), 'title': 'How to continue a Copilot session'}
        def wrong(*args):
            value = provider(*args); value['changed'] = '新発表です。引き継ぎできます。'
            return value
        feed = self.generate(rows=[guide], provider=wrong)
        self.assertEqual(feed['entries'], [])
        self.assertEqual(feed['status'], 'invalid_outputs')

    def test_invalid_cached_feed_never_silently_becomes_empty(self):
        feed = self.generate(rows=[row()])
        for mutate in (lambda f: f['entries'][0].update(url='javascript:alert(1)'),
                       lambda f: f['entries'][0]['card']['comments'][0].update(reply_to=0),
                       lambda f: f['entries'].append(deepcopy(f['entries'][0]))):
            bad = deepcopy(feed); mutate(bad)
            with self.assertRaises(ValueError):
                checked_feed(bad)

    def test_configuration_and_prompt_do_not_claim_human_review(self):
        bad = {**CONFIG, 'daily_requests': 99}
        with self.assertRaises(ValueError): configuration(bad)
        self.assertIn('機械抽出した本文の一部', DAILY_PROMPT)
        self.assertIn('関西弁まじりの短い掛け合い', DAILY_PROMPT)
        self.assertNotIn('人が確認して要点化した資料です', DAILY_PROMPT)

    def test_article_extraction_prefers_actual_post_body_over_related_article_cards(self):
        html = '<main><section class="post__content">Actual article body.<div class="post-content-cta">Advertisement.</div></section><article>Unrelated new product.</article></main>'
        reader = lambda url, limit: 'User-agent: *\nAllow: /' if url.endswith('/robots.txt') else html
        self.assertEqual(article_text('https://github.blog/a/', ['github.blog'], reader=reader), 'Actual article body.')
        html = '<section class="post__content"><img src="video-cover.jpg"></section><article>Unrelated new product.</article>'
        self.assertEqual(article_text('https://github.blog/a/', ['github.blog'], reader=reader), '')
