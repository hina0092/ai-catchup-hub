import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError

from collector.collect import collect, main, normalize_url, parse_date, parse_feed, plain_text, write_articles

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCE = {'name': 'Fixture', 'url': 'https://example.com/feed', 'category': 'techniques'}


class CollectorTests(unittest.TestCase):
    def test_rss_fields_and_sanitizing(self):
        rows = parse_feed((FIXTURES / 'rss.xml').read_bytes(), SOURCE, 'now')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['url'], 'https://example.com/post?id=1')
        self.assertEqual(rows[0]['summary'], '短い概要')
        self.assertEqual(rows[0]['published_at'], '2026-10-18T00:00:00+00:00')
        self.assertIsNone(rows[2]['published_at'])
        self.assertEqual(set(rows[0]), {'id', 'title', 'url', 'source', 'published_at', 'summary', 'category', 'collected_at'})

    def test_atom(self):
        row = parse_feed((FIXTURES / 'atom.xml').read_bytes(), SOURCE, 'now')[0]
        self.assertEqual(row['url'], 'https://example.com/new')
        self.assertEqual(row['summary'], 'Atom概要')

    def test_dedup_sort_and_stable_id(self):
        feeds = [(FIXTURES / name).read_bytes() for name in ('rss.xml', 'atom.xml')]
        rows, successes = collect([SOURCE, SOURCE], lambda _: feeds.pop(0))
        self.assertEqual(successes, 2)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['title'], 'Atom記事')
        self.assertIsNone(rows[-1]['published_at'])
        repeated = parse_feed((FIXTURES / 'rss.xml').read_bytes(), SOURCE, 'later')[0]
        self.assertEqual(rows[1]['id'], repeated['id'])

    def test_partial_failure(self):
        responses = iter([URLError('offline'), (FIXTURES / 'atom.xml').read_bytes()])
        def fetcher(_):
            response = next(responses)
            if isinstance(response, Exception):
                raise response
            return response
        with self.assertLogs(level='WARNING'):
            rows, successes = collect([SOURCE, SOURCE], fetcher)
        self.assertEqual((len(rows), successes), (1, 1))

    def test_empty_and_malformed_logs(self):
        with self.assertLogs(level='INFO') as logs:
            self.assertEqual(collect([SOURCE], lambda _: b'<rss><channel/></rss>'), ([], 1))
        self.assertIn('0 articles', ' '.join(logs.output))
        with self.assertLogs(level='WARNING'):
            self.assertEqual(collect([SOURCE], lambda _: b'<broken'), ([], 0))

    def test_invalid_urls(self):
        for value in ('javascript:alert(1)', 'https://a:bad/', 'https://user:pass@a/', 'https://', 'https://a/has space'):
            with self.subTest(value=value):
                self.assertIsNone(normalize_url(value))
        self.assertEqual(normalize_url('https://example.com/?id=2&utm_medium=x'), 'https://example.com/?id=2')

    def test_dates(self):
        for value in (None, 'bad', '2026-10-19T12:00:00'):
            self.assertIsNone(parse_date(value))

    def test_summary_length(self):
        self.assertEqual(len(plain_text('あ' * 500)), 240)
        self.assertEqual(plain_text('<style>hidden</style><p>A &amp; B</p>'), 'A & B')

    def test_reject_dtd(self):
        for data in (b'<!DOCTYPE rss><rss/>', '<!DOCTYPE rss><rss/>'.encode('utf-16')):
            with self.assertRaises(ValueError):
                parse_feed(data, SOURCE, 'now')

    def test_html_doctype_inside_cdata_is_not_xml_dtd(self):
        data = b'<rss><channel><item><title>Test</title><link>https://example.com/</link><description><![CDATA[<!DOCTYPE html><p>Summary</p>]]></description></item></channel></rss>'
        self.assertEqual(parse_feed(data, SOURCE, 'now')[0]['summary'], 'Summary')

    def test_output_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'articles.json'
            write_articles(path, [{'title': '日本語'}])
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                write_articles(path, [{'title': 'other'}])
            with self.assertRaises(ValueError):
                write_articles(path, [], overwrite=True)
            self.assertEqual(path.read_bytes(), original)
            write_articles(path, [{'title': '更新'}], overwrite=True)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))[0]['title'], '更新')

    def test_cli_total_failure_preserves_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'articles.json'
            output.write_text('[{"old": true}]', encoding='utf-8')
            with patch('collector.collect.collect', return_value=([], 0)):
                self.assertEqual(main(['--output', str(output), '--overwrite']), 1)
            self.assertEqual(output.read_text(encoding='utf-8'), '[{"old": true}]')


if __name__ == '__main__':
    unittest.main()
