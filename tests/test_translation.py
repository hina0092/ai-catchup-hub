import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from collector.translate import enrich, main, request_translation, valid_result


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'cache.sqlite3'
        self.config = dict(enabled=True, model='mock-model', english_sources=['GitHub Blog AI & ML'],
                           max_requests=3, max_input_bytes=6000, max_output_tokens=600,
                           max_run_tokens=30000, max_run_usd=.05, max_month_usd=.5,
                           input_usd_per_million=1, output_usd_per_million=2)
        self.article = dict(id='1', title='New developer tool', url='https://example.com/tool',
                            summary='A developer tool automates repetitive tasks.', source='GitHub Blog AI & ML')
        self.provider = Mock(return_value=dict(title_ja='開発者向けの新しいツール', summary_ja='これはテスト用の要約です。' * 8))

    def run_enrich(self, rows=None, **kwargs):
        return enrich(rows if rows is not None else [self.article], self.config, self.cache,
                      allow_api=kwargs.pop('allow_api', True), api_key=kwargs.pop('api_key', 'test-only'),
                      provider=self.provider, initialize_cache=kwargs.pop('initialize_cache', True), **kwargs)

    def test_additive_and_persistent_cache_without_key(self):
        rows, stats = self.run_enrich()
        self.assertEqual(stats['requests'], 1)
        self.assertEqual(rows[0]['title'], self.article['title'])
        self.assertNotIn('translation', self.article)
        cached, stats = self.run_enrich(allow_api=False, api_key='')
        self.assertEqual(cached, rows)
        self.assertEqual(stats['cache_hits'], 1)
        self.provider.assert_called_once()

    def test_gates_and_missing_cache_never_call_provider(self):
        for kwargs in [dict(allow_api=False), dict(api_key=''), dict(initialize_cache=False)]:
            self.run_enrich(**kwargs)
        self.config['enabled'] = False
        self.run_enrich()
        self.provider.assert_not_called()

    def test_japanese_and_unlisted_sources_are_unchanged(self):
        rows = [dict(self.article, title='日本語の記事'), dict(self.article, source='unknown')]
        self.assertEqual(self.run_enrich(rows)[0], rows)
        self.provider.assert_not_called()

    def test_content_and_model_changes_invalidate_cache(self):
        self.run_enrich()
        self.run_enrich([dict(self.article, summary='Changed description')])
        self.config['model'] = 'mock-model-2'
        self.run_enrich()
        self.assertEqual(self.provider.call_count, 3)

    def test_missing_description_only_translates_title(self):
        rows, _ = self.run_enrich([dict(self.article, summary='')])
        self.assertIsNone(rows[0]['translation']['summary_ja'])

    def test_budgets_and_size_block_calls(self):
        for key in ['max_run_tokens', 'max_run_usd', 'max_month_usd', 'max_input_bytes']:
            original = self.config[key]
            self.config[key] = 1 if 'tokens' in key or 'bytes' in key else .000001
            rows, stats = self.run_enrich()
            self.assertEqual(stats['requests'], 0, key)
            self.assertNotIn('translation', rows[0])
            self.config[key] = original
        self.provider.assert_not_called()

    def test_request_limit_and_partial_failure(self):
        self.config['max_requests'] = 2
        success = self.provider.return_value
        self.provider.side_effect = [TimeoutError('secret must not appear'), success]
        rows, stats = self.run_enrich([dict(self.article, url=f'https://example.com/{i}') for i in range(3)])
        self.assertEqual(stats['requests'], 2)
        self.assertEqual(stats['failures'], 1)
        self.assertNotIn('translation', rows[0])
        self.assertIn('translation', rows[1])
        self.assertNotIn('translation', rows[2])

    def test_monthly_reservations_survive_failed_requests(self):
        self.provider.side_effect = TimeoutError()
        _, first = self.run_enrich()
        self.config['max_month_usd'] = first['reserved_usd'] * 1.5
        _, second = self.run_enrich()
        self.assertEqual(second['requests'], 0)
        self.assertEqual(self.provider.call_count, 1)

    def test_invalid_results_are_not_cached(self):
        for result in [None, {}, dict(title_ja='English', summary_ja=None),
                       dict(title_ja='日本語', summary_ja='短い'),
                       dict(title_ja='<script>日本語</script>', summary_ja=None)]:
            self.provider.return_value = result
            rows, stats = self.run_enrich()
            self.assertNotIn('translation', rows[0])
            self.assertEqual(stats['failures'], 1)

    def test_corrupt_cache_preserves_input_file(self):
        self.cache.write_bytes(b'not a database')
        source = self.root / 'articles.json'
        source.write_text(json.dumps([self.article]), encoding='utf-8')
        config = self.root / 'config.json'
        config.write_text(json.dumps(self.config), encoding='utf-8')
        before = source.read_bytes()
        self.assertEqual(main(['--input', str(source), '--output', str(source), '--overwrite',
                               '--config', str(config), '--cache', str(self.cache)]), 1)
        self.assertEqual(source.read_bytes(), before)

    def test_bad_cached_record_can_be_replaced(self):
        self.run_enrich()
        with closing(sqlite3.connect(self.cache)) as db:
            db.execute("UPDATE translations SET value='{}'")
            db.commit()
        _, stats = self.run_enrich()
        self.assertEqual(stats['requests'], 1)

    def test_invalid_pricing_disables_network(self):
        for value in [None, -1, float('nan'), '1']:
            self.config['input_usd_per_million'] = value
            self.run_enrich()
        self.provider.assert_not_called()

    def test_response_adapter_and_incomplete_response(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(dict(status='completed', output=[dict(type='message',
            content=[dict(type='output_text', text=json.dumps(self.provider.return_value))])])).encode()
        with patch('collector.translate.urlopen', return_value=response) as network:
            self.assertEqual(valid_result(request_translation({}, 'test-only')), self.provider.return_value)
            request = network.call_args.args[0]
            self.assertEqual(request.full_url, 'https://api.openai.com/v1/responses')
            response.read.return_value = b'{"status":"incomplete","output":[]}'
            with self.assertRaises(ValueError):
                request_translation({}, 'test-only')


if __name__ == '__main__':
    unittest.main()
