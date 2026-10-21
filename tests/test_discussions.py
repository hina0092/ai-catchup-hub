import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from collector.discussions import enrich, main, story_metadata, fetch_json


class DiscussionTests(unittest.TestCase):
    def setUp(self):
        self.article = {'id': 'original', 'url': 'https://example.com/article', 'title': 'Original',
                        'translation': {'title_ja': '元記事'}}
        self.story = dict(id=1, type='story', url=self.article['url'], time=1700000000, descendants=12)
        self.responses = {'topstories.json': [1], 'newstories.json': [1], 'item/1.json': self.story}
        self.fetcher = Mock(side_effect=lambda path: self.responses[path])

    def run_enrich(self, **kwargs):
        return enrich([self.article], fetcher=self.fetcher, allow_api=True, **kwargs)

    def test_disabled_does_not_call_network(self):
        rows, stats = enrich([self.article], fetcher=self.fetcher)
        self.assertEqual(rows, [self.article])
        self.assertEqual(stats['requests'], 0)
        self.fetcher.assert_not_called()

    def test_match_is_additive_and_deduplicates_fetches(self):
        rows, stats = self.run_enrich()
        self.assertEqual(stats['requests'], 3)
        self.assertEqual(rows[0]['discussion']['comment_count'], 12)
        self.assertEqual(rows[0]['translation'], self.article['translation'])
        self.assertNotIn('discussion', self.article)

    def test_tracking_parameters_and_fragment_match(self):
        self.story['url'] += '?utm_source=hn#section'
        self.assertEqual(self.run_enrich()[1]['matched'], 1)

    def test_distinct_urls_never_match_by_title(self):
        for url in ['https://example.com/other', 'http://example.com/article',
                    'https://example.com/article?version=2', 'javascript:alert(1)']:
            self.story['url'] = url
            self.assertEqual(self.run_enrich()[1]['matched'], 0)

    def test_duplicate_submissions_choose_representative(self):
        self.responses['newstories.json'] = [2]
        self.responses['item/2.json'] = dict(self.story, id=2, descendants=50)
        d = self.run_enrich()[0][0]['discussion']
        self.assertEqual(d['story_id'], 2)
        self.assertEqual(d['comment_count'], 50)
        self.assertEqual(d['related_story_ids'], [2, 1])

    def test_missing_count_is_unknown_not_zero(self):
        del self.story['descendants']
        self.assertIsNone(self.run_enrich()[0][0]['discussion']['comment_count'])

    def test_invalid_deleted_dead_and_nonstory_items(self):
        for item in [None, [], {}, dict(self.story, deleted=True), dict(self.story, dead=True),
                     dict(self.story, type='comment'), dict(self.story, id=2),
                     dict(self.story, descendants=-1), dict(self.story, time=10**100),
                     dict(self.story, url=123), dict(self.story, id=True)]:
            self.assertIsNone(story_metadata(item, 1, 'now'))

    def test_request_budget_includes_list_calls(self):
        self.responses['newstories.json'] = [2, 3]
        self.run_enrich(max_requests=3)
        self.assertEqual(self.fetcher.call_count, 3)

    def test_elapsed_budget_stops_requests(self):
        clock = Mock(side_effect=[0, 121, 121])
        self.assertEqual(self.run_enrich(clock=clock)[1]['requests'], 0)
        self.fetcher.assert_not_called()

    def test_partial_list_failure_can_still_match(self):
        def fetch(path):
            if path == 'topstories.json':
                raise TimeoutError()
            return self.responses[path]
        self.fetcher.side_effect = fetch
        rows, stats = self.run_enrich()
        self.assertIn('discussion', rows[0])
        self.assertEqual(stats['failures'], 1)

    def test_total_failure_preserves_existing_data(self):
        self.fetcher.side_effect = OSError()
        rows, _ = self.run_enrich()
        self.assertEqual(rows, [self.article])

    def test_invalid_list_ids_are_not_requested(self):
        self.responses['topstories.json'] = [True, -1, '1', {}, 1]
        self.responses['newstories.json'] = {'invalid': []}
        self.assertEqual(self.run_enrich()[1]['requests'], 3)

    def test_cli_invalid_input_preserves_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'articles.json'
            path.write_text('{broken', encoding='utf-8')
            self.assertEqual(main(['--input', str(path), '--output', str(path), '--overwrite']), 1)
            self.assertEqual(path.read_text(), '{broken')

    def test_http_adapter_is_mocked(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(self.story).encode()
        with patch('collector.discussions.urlopen', return_value=response) as network:
            self.assertEqual(fetch_json('item/1.json'), self.story)
            self.assertEqual(network.call_args.args[0].full_url,
                             'https://hacker-news.firebaseio.com/v0/item/1.json')
            response.read.return_value = b'x' * 1_000_001
            with self.assertRaises(ValueError):
                fetch_json('item/1.json')


if __name__ == '__main__':
    unittest.main()
