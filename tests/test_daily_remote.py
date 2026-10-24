from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from collector.daily_cards import empty_feed
from tools.ai_cache import git
from tools.card_trial_remote import setup
from tools.daily_remote import load_feed, persist_feed, run
from tests.test_card_trial import ENV, NOW
from tests.test_daily_cards import CONFIG, EXCERPT, row, provider
from collector.daily_cards import generate


class DailyRemoteTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict('os.environ', {'GH_TOKEN': ''}); self.env.start(); self.addCleanup(self.env.stop)
        self.remote = self.root / 'remote.git'; self.remote.mkdir()
        git(self.remote, 'init', '--bare')
        self.store = setup(self.root / 'first', str(self.remote), initialize=True)

    def test_real_git_feed_and_budget_survive_runner_restart_and_push_build_uses_no_api(self):
        def mocked_generator(*args, **kwargs):
            return generate(*args, **kwargs, provider=provider, reader=Mock(return_value=EXCERPT), sleep=Mock())
        feed = run(self.store, CONFIG, self.root / 'export.json', self.root / 'ledger', live=True,
                   env=ENV, now=NOW, collector=Mock(return_value=([row()], 1)), generator=mocked_generator)
        self.assertEqual(len(feed['entries']), 1)
        next_store = setup(self.root / 'next', str(self.remote))
        self.assertEqual(load_feed(next_store), feed)
        self.assertEqual(len(next_store.state['files']), 1)
        forbidden = Mock(side_effect=AssertionError('no API on code push'))
        exported = run(next_store, CONFIG, self.root / 'again.json', self.root / 'unused',
                       collector=forbidden, generator=forbidden)
        self.assertEqual(exported, feed)
        forbidden.assert_not_called()

    def test_feed_failure_stops_export_and_keeps_active_marker(self):
        with patch('tools.daily_remote.persist_feed', side_effect=OSError('push failed')):
            with self.assertRaises(OSError):
                run(self.store, CONFIG, self.root / 'export.json', self.root / 'ledger', live=True,
                    now=NOW, collector=Mock(return_value=([], 0)))
        self.assertFalse((self.root / 'export.json').exists())
        next_store = setup(self.root / 'next', str(self.remote))
        self.assertTrue(next_store.state['active'])
        with self.assertRaises(ValueError): load_feed(next_store)

    def test_all_sources_fail_preserves_cards_and_records_check_time(self):
        feed = {**empty_feed(), 'checked_at': NOW.isoformat(), 'status': 'no_new'}
        persist_feed(self.store, feed)
        generated = Mock()
        out = run(self.store, CONFIG, self.root / 'export.json', self.root / 'ledger', live=True,
                  now=NOW, collector=Mock(return_value=([], 0)), generator=generated)
        self.assertEqual(out['entries'], feed['entries'])
        self.assertEqual(out['status'], 'source_unavailable')
        self.assertFalse(self.store.state['active'])
        generated.assert_not_called()

    def test_corrupt_cache_is_not_reset(self):
        path = self.store.directory / 'feed.json'; path.write_text('{broken')
        with self.assertRaises(ValueError): load_feed(self.store)
        self.assertEqual(path.read_text(), '{broken')
