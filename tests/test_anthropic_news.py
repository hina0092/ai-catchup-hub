from datetime import timedelta
from unittest import TestCase
from unittest.mock import Mock

from collector.anthropic_news import URL, collect_news
from collector.collect import collect
from collector.daily_cards import candidates, empty_feed
from tests.test_card_trial import NOW
from tests.test_daily_cards import CONFIG

SOURCE = dict(name='Anthropic News', url=URL, category='ai-tools', format='anthropic_news', max_articles=10)
ROBOTS = b'User-agent: *\nAllow: /'


def listing(url='/news/example', date='Oct 23, 2026'):
    return f'<li data-listing-row="id"><a class="Table__title-link" href="{url}"><h3>Example &amp; AI</h3></a><time>{date}</time></li>'


def reader(html):
    return Mock(side_effect=lambda url: ROBOTS if url.endswith('/robots.txt') else html.encode())


class AnthropicNewsTests(TestCase):
    def test_official_listing_retains_date_precision_and_does_not_invent_time(self):
        fetcher = reader(listing())
        rows = collect_news(SOURCE, NOW.isoformat(), fetcher)
        self.assertEqual(rows[0]['title'], 'Example & AI')
        self.assertEqual(rows[0]['published_on'], '2026-10-23')
        self.assertIsNone(rows[0]['published_at'])
        self.assertEqual(rows[0]['date_precision'], 'day')
        self.assertEqual(rows[0]['url'], 'https://www.anthropic.com/news/example')
        self.assertEqual([c.args[0] for c in fetcher.call_args_list], ['https://www.anthropic.com/robots.txt', URL])

    def test_listing_rejects_offsite_links_invalid_dates_and_changed_markup(self):
        for html in (listing('https://evil.test/news/a'), listing('//www.anthropic.com.evil.test/news/a'),
                     listing('/news/a?secret=x'), listing(date='Oct 99, 2026'), '<a href="/news/example">Undated article</a>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                collect_news(SOURCE, NOW.isoformat(), reader(html))

    def test_listing_respects_robots_and_meta_opt_outs(self):
        denied = Mock(return_value=b'User-agent: *\nDisallow: /')
        with self.assertRaises(ValueError):
            collect_news(SOURCE, NOW.isoformat(), denied)
        self.assertEqual(denied.call_count, 1)
        for name, content in [('robots', 'noai'), ('robots', 'nosnippet'), ('AI-Catchup-Hub', 'noindex')]:
            with self.subTest(content=content), self.assertRaises(ValueError):
                collect_news(SOURCE, NOW.isoformat(), reader(f'<meta name="{name}" content="{content}">'+listing()))

    def test_html_adapter_is_limited_to_the_exact_official_source(self):
        for changes in ({'url':'https://evil.test'}, {'name':'Another source'}):
            fetcher = Mock()
            with self.assertRaises(ValueError):
                collect_news({**SOURCE, **changes}, NOW.isoformat(), fetcher)
            fetcher.assert_not_called()

    def test_collector_dispatches_and_caps_the_official_listing(self):
        html = ''.join(listing(f'/news/article-{i}', f'Oct {i+1}, 2026') for i in range(12))
        rows, successes = collect([SOURCE], fetcher=reader(html))
        self.assertEqual(successes, 1)
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]['published_on'], '2026-10-12')
        self.assertTrue(all(r['published_at'] is None for r in rows))

    def test_day_precision_candidates_exclude_future_old_and_invalid_dates(self):
        rows = collect_news(SOURCE, NOW.isoformat(), reader(listing()))
        valid = rows[0]
        bad = [{**valid, 'url':valid['url']+str(i), 'published_on':date} for i,date in enumerate(
            [(NOW+timedelta(days=1)).date().isoformat(), '2020-01-01', 'not-a-date'])]
        selected = candidates([valid, *bad], empty_feed(), CONFIG, NOW)
        self.assertEqual([r['url'] for r in selected], [valid['url']])
        self.assertEqual(selected[0]['_date'].date().isoformat(), valid['published_on'])
