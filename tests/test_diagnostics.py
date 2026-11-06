"""Operational failures are useful in public logs without disclosing inputs."""
import io
import json
import logging
from pathlib import Path
import socket
import ssl
import subprocess
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from collector.diagnostics import error_fields, failure, response_failure, stage, OperationalError
from collector.article_source import article_text
from collector.card_trial import request_card, MODEL, Rejected
from collector.collect import collect
from collector.daily_cards import generate, empty_feed
from tools.ai_cache import git
from tests.test_card_trial import ENV, NOW
from tests.test_daily_cards import CONFIG, EXCERPT, row, provider

SECRET = 'PRIVATE_KEY_SOURCE\n::warning::injected'


class DiagnosticTests(TestCase):
    def test_transport_error_classification_never_serializes_message_or_headers(self):
        cases = [(URLError(socket.gaierror(1, SECRET)), 'dns_error'),
                 (URLError(TimeoutError(SECRET)), 'timeout'),
                 (TimeoutError(SECRET), 'timeout'),
                 (URLError(ssl.SSLError(SECRET)), 'tls_error'),
                 (ConnectionResetError(SECRET), 'connection_error'),
                 (URLError(SECRET), 'unexpected_error'),
                 (PermissionError(SECRET), 'permission_denied'),
                 (json.JSONDecodeError(SECRET, SECRET, 0), 'json_decode'),
                 (ValueError(SECRET), 'invalid_value'),
                 (KeyError(SECRET), 'missing_key')]
        for error, reason in cases:
            with self.subTest(reason=reason), self.assertLogs('safe', level='WARNING') as logs:
                failure(logging.getLogger('safe'), 'test_failure', 'response', error)
            self.assertEqual(json.loads(logs.records[0].getMessage())['reason'], reason)
            self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))
        for status in (400, 403, 404, 429, 500, 503):
            error = HTTPError('https://private/' + SECRET, status, SECRET, {'secret': SECRET}, io.BytesIO(SECRET.encode()))
            self.assertEqual(error_fields(error), dict(reason='http_error', http_status=status))

    def test_response_enum_allowlist_and_missing_candidates(self):
        for data, expected in [({'candidates': [{'finishReason': 'MAX_TOKENS'}]}, 'MAX_TOKENS'),
                               ({'candidates': [{'finishReason': SECRET}]}, 'unknown'),
                               ({'promptFeedback': {'blockReason': 'SAFETY'}}, None)]:
            with self.assertLogs('safe', level='WARNING') as logs:
                response_failure(logging.getLogger('safe'), data)
            record = json.loads(logs.records[0].getMessage())
            self.assertEqual(record.get('finish_reason'), expected)
            self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))

    def test_git_timeout_and_failed_push_record_operation_without_stderr(self):
        for outcome, reason in [(subprocess.TimeoutExpired(SECRET, 45), 'git_timeout'),
                                (Mock(returncode=128, stderr=SECRET), 'git_failed')]:
            with patch('tools.ai_cache.subprocess.run') as command:
                if isinstance(outcome, Exception): command.side_effect = outcome
                else: command.return_value = outcome
                with self.assertLogs('collector.diagnostics', level='WARNING') as logs:
                    with self.assertRaises(OSError): git(Path('.'), 'push', 'origin', SECRET)
            record = json.loads(logs.records[0].getMessage())
            self.assertEqual((record['phase'], record['reason']), ('git_push', reason))
            self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))

    def test_stage_records_start_for_interruption_and_failure_without_message(self):
        with self.assertLogs('collector.diagnostics', level='INFO') as logs:
            with self.assertRaises(PermissionError):
                with stage('feed_persist'): raise PermissionError(SECRET)
        records = [json.loads(r.getMessage()) for r in logs.records]
        self.assertEqual([r['event'] for r in records], ['operation_started', 'operation_failed'])
        self.assertEqual(records[-1]['phase'], 'feed_persist')
        self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))

    def test_validation_failure_records_only_allowlisted_relative_code_location(self):
        from collector.daily_cards import checked_feed
        with self.assertLogs('safe', level='WARNING') as logs:
            try:
                checked_feed({'secret': SECRET})
            except ValueError as error:
                failure(logging.getLogger('safe'), 'test_failure', 'feed_restore', error)
        record = json.loads(logs.records[0].getMessage())
        self.assertEqual(record['origin_file'], 'collector/daily_cards.py')
        self.assertGreater(record['origin_line'], 0)
        self.assertNotIn('C:', str(logs.output))
        self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))

    def test_source_failure_identifies_index_and_parse_or_network_without_response(self):
        sources = [dict(name=SECRET, url='https://example.com', category='tech')]
        for error, phase, reason in [(HTTPError(SECRET, 503, SECRET, {}, None), 'source_fetch', 'http_error'),
                                      (None, 'source_parse', 'xml_parse')]:
            fetcher = Mock(side_effect=error) if error else Mock(return_value=b'<broken')
            with self.assertLogs('collector.collect', level='WARNING') as logs:
                self.assertEqual(collect(sources, fetcher), ([], 0))
            record = json.loads(logs.records[-1].getMessage())
            self.assertEqual((record['phase'], record['reason'], record['source_index']), (phase, reason, 1))
            self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))

    def test_article_distinguishes_policy_body_and_transport_failures(self):
        cases = [(['User-agent: *\nDisallow: /'], 'robots_denied', 'article_robots'),
                 (['User-agent: *\nCrawl-delay: 20'], 'crawl_delay', 'article_robots'),
                 (['User-agent: *\nAllow: /', '<meta name="robots" content="noai">'], 'meta_denied', 'article_parse'),
                 (['User-agent: *\nAllow: /', '<nav>PRIVATE_KEY_SOURCE</nav>'], 'empty_body', 'article_parse'),
                 ([URLError(socket.gaierror(1, SECRET))], 'dns_error', 'article_robots'),
                 (['User-agent: *\nAllow: /', HTTPError(SECRET, 403, SECRET, {}, None)], 'http_error', 'article_fetch')]
        for effects, reason, phase in cases:
            with self.subTest(reason=reason), self.assertLogs('collector.article_source', level='WARNING') as logs:
                self.assertEqual(article_text('https://zenn.dev/a', ['zenn.dev'], reader=Mock(side_effect=effects)), '')
            record = json.loads(logs.records[-1].getMessage())
            self.assertEqual((record['reason'], record['phase']), (reason, phase))
            self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))

    def test_daily_provider_failure_preserves_cards_budget_and_stops_without_retry(self):
        for error in (HTTPError(SECRET, 503, SECRET, {}, None), URLError(TimeoutError(SECRET)),
                      HTTPError(SECRET, 429, SECRET, {}, None)):
            with self.subTest(error=type(error).__name__), TemporaryDirectory() as directory:
                def respond(*args):
                    if send.call_count == 1:
                        return provider(*args)
                    raise error
                send = Mock(side_effect=respond)
                with self.assertLogs('collector.daily_cards', level='INFO') as logs:
                    feed = generate([row(i) for i in range(4)], empty_feed(), Path(directory), CONFIG,
                                    ENV, Mock(), now=NOW, provider=send,
                                    reader=Mock(return_value=EXCERPT), sleep=Mock())
                self.assertEqual(send.call_count, 2)
                self.assertEqual(len(feed['entries']), 1)
                self.assertEqual(len(list(Path(directory).glob('*.json'))), 2)
                self.assertEqual((Path(directory) / f'{NOW.date().isoformat()}.stop').exists(),
                                 isinstance(error, HTTPError) and error.code == 429)
                records = [json.loads(r.getMessage()) for r in logs.records]
                failed = next(r for r in records if r['event'] == 'daily_provider_failed')
                self.assertEqual(failed['attempt'], 2)
                self.assertEqual(records[-1]['attempts'], 2)
                self.assertEqual(records[-1]['accepted'], 1)
                self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output) + json.dumps(feed))
                self.assertNotIn('http_status', json.dumps(feed))

    def test_daily_first_failure_reserves_only_one_and_keeps_previous_time(self):
        with TemporaryDirectory() as directory:
            send = Mock(side_effect=HTTPError(SECRET, 500, SECRET, {}, None))
            with self.assertLogs('collector.daily_cards', level='WARNING'):
                feed = generate([row()], empty_feed(), Path(directory), CONFIG, ENV, Mock(),
                                now=NOW, provider=send, reader=Mock(return_value=EXCERPT))
            self.assertEqual(feed['status'], 'provider_error')
            self.assertIsNone(feed['updated_at'])
            send.assert_called_once()
            self.assertEqual(len(list(Path(directory).glob('*.json'))), 1)

    def test_response_adapter_reports_json_stage_without_disclosing_body(self):
        article = json.loads(Path('validation/card-inputs.json').read_text(encoding='utf-8'))['articles'][0]
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = SECRET.encode()
        with patch('collector.card_trial.build_opener') as opener:
            opener.return_value.open.return_value = response
            with self.assertLogs('collector.card_trial', level='WARNING') as logs:
                with self.assertRaises(Rejected): request_card(MODEL, SECRET, article)
        self.assertIn('response_envelope_json', str(logs.output))
        self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))

    def test_closed_gates_explain_each_missing_condition_without_values_or_api_calls(self):
        with TemporaryDirectory() as directory:
            send = Mock()
            with self.assertLogs('collector.daily_cards', level='INFO') as logs:
                feed = generate([row()], empty_feed(), Path(directory), CONFIG,
                                {'GEMINI_MODEL': SECRET, 'GEMINI_FREE_TIER_REVIEWED_ON': SECRET},
                                Mock(), now=NOW, provider=send)
            send.assert_not_called()
            record = next(json.loads(r.getMessage()) for r in logs.records
                          if json.loads(r.getMessage())['event'] == 'generation_skipped')
            self.assertEqual(set(record['reasons']), {'generation_disabled', 'billing_unconfirmed',
                'key_missing', 'model_not_allowed', 'review_date_invalid'})
            self.assertEqual(feed['status'], 'generation_paused')
            self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))

    def test_candidate_filter_and_short_body_explain_zero_additions(self):
        from datetime import timedelta
        rows = [row(0), row(0), row(1), row(2), row(3)]
        rows[2]['published_at'] = SECRET
        rows[3]['published_at'] = (NOW - timedelta(days=90)).isoformat()
        rows[4]['source'] = SECRET
        with TemporaryDirectory() as directory:
            send = Mock()
            with self.assertLogs('collector.daily_cards', level='INFO') as logs:
                feed = generate(rows, empty_feed(), Path(directory), CONFIG, ENV, Mock(),
                                now=NOW, provider=send, reader=Mock(return_value='短い本文'))
            records = [json.loads(r.getMessage()) for r in logs.records]
            filtered = next(r for r in records if r['event'] == 'candidate_filter')
            self.assertEqual(filtered['eligible'], 1)
            self.assertEqual(filtered['excluded'], dict(already_published=0, duplicate=1,
                invalid_date=1, invalid_or_disallowed=1, outside_date_range=1))
            self.assertTrue(any(r.get('reason') == 'body_too_short' for r in records))
            self.assertEqual(feed['status'], 'source_unavailable')
            send.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))

    def test_failed_reservation_identifies_stage_and_prevents_api(self):
        with TemporaryDirectory() as directory:
            send = Mock()
            with self.assertLogs('collector.diagnostics', level='WARNING') as logs:
                with self.assertRaises(OSError):
                    generate([row()], empty_feed(), Path(directory), CONFIG, ENV,
                        Mock(side_effect=OSError(SECRET)), now=NOW,
                        provider=send, reader=Mock(return_value=EXCERPT))
            send.assert_not_called()
            self.assertIn('reservation_persist', str(logs.output))
            self.assertNotIn('PRIVATE_KEY_SOURCE', str(logs.output))
