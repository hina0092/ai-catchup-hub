import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock

from collector.article_source import article_text
from collector.card_trial import ROOT
from collector.daily_cards import configuration, empty_feed, generate, safe_url
from tests.test_card_trial import ENV, NOW
from tests.test_daily_cards import CONFIG, EXCERPT, provider, row


class OfficialSourcesTests(TestCase):
    def test_official_feeds_are_selected_with_bounded_requests(self):
        sources = json.loads((ROOT / 'collector/sources.json').read_text(encoding='utf-8'))
        selected = {s['name']: s for s in sources if s['name'] in CONFIG['source_names']}
        self.assertEqual(selected['OpenAI News']['url'], 'https://openai.com/news/rss.xml')
        self.assertEqual(selected['Google AI']['url'], 'https://blog.google/innovation-and-ai/technology/ai/rss/')
        self.assertEqual(CONFIG['daily_requests'], 3)
        self.assertEqual(selected['Anthropic News']['format'], 'anthropic_news')
        for name in ('OpenAI News', 'Google AI', 'Anthropic News'):
            self.assertEqual(selected[name]['max_articles'], 10)
        configuration(CONFIG)

    def test_new_publishers_generate_valid_feed_without_widening_host_policy(self):
        rows = [row(0, 'openai.com', 'OpenAI News'), row(1, 'blog.google', 'Google AI'),
                {**row(2, 'www.anthropic.com', 'Anthropic News'), 'published_at':None,
                 'published_on':NOW.date().isoformat(), 'date_precision':'day'}]
        with TemporaryDirectory() as directory:
            feed = generate(rows, empty_feed(), Path(directory), CONFIG, ENV, Mock(),
                now=NOW, provider=provider, reader=Mock(return_value=EXCERPT), sleep=Mock())
        self.assertEqual({e['source'] for e in feed['entries']}, {'OpenAI News', 'Google AI', 'Anthropic News'})
        for url in ('https://openai.com.evil.test/index/a', 'https://blog.google.evil.test/a',
                    'https://openai.com@evil.test/a', 'https://openai.com/a?private=1'):
            self.assertFalse(safe_url(url))

    def test_openai_canonical_path_and_google_body_obey_robots_and_noai(self):
        for url in ('https://openai.com/index/example', 'https://blog.google/example/', 'https://www.anthropic.com/news/example'):
            calls = []
            def reader(target, limit):
                calls.append(target)
                return 'User-agent: *\nAllow: /' if target.endswith('/robots.txt') else '<article>本文の例です。</article>'
            host = url.split('/')[2]
            self.assertEqual(article_text(url, [host], reader=reader), '本文の例です。')
            self.assertEqual(calls[-1], url + '/' if host == 'openai.com' else url)
            denied = Mock(return_value='User-agent: *\nDisallow: /')
            self.assertEqual(article_text(url, [host], reader=denied), '')
            self.assertEqual(denied.call_count, 1)
            def noai(target, limit):
                return 'User-agent: *\nAllow: /' if target.endswith('/robots.txt') else '<meta name="robots" content="noai"><article>取得禁止。</article>'
            self.assertEqual(article_text(url, [host], reader=noai), '')
            forbidden = Mock(side_effect=AssertionError('no access outside the allowlist'))
            self.assertEqual(article_text(url, [], reader=forbidden), '')
            forbidden.assert_not_called()
