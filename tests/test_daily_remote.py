from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from collector.daily_cards import empty_feed
from tools.ai_cache import git
from tools.card_trial_remote import setup
from tools.daily_remote import load_feed, persist_feed, run
from tests.test_card_trial import ENV, NOW
from tests.test_daily_cards import CONFIG, EXCERPT, row, provider
from collector.daily_cards import generate


class DailyRemoteTests(TestCase):
    def test_split_runs_restore_reservations_after_503_and_skip_collection_after_three(self):
        requested = []
        def send(model, key, article):
            requested.append(article['id'])
            if len(requested) == 1:
                raise HTTPError('https://example.com', 503, 'unavailable', {}, None)
            return provider(model, key, article)
        def mocked_generator(*args, **kwargs):
            return generate(*args, **kwargs, provider=send, reader=Mock(return_value=EXCERPT), sleep=Mock())
        collect = Mock(return_value=([row(i) for i in range(5)], 1))
        store = self.store
        statuses = []
        for index in range(4):
            if index:
                store = setup(self.root / f'runner-{index}', str(self.remote))
            feed = run(store, {**CONFIG, 'requests_per_run': 1}, self.root / f'feed-{index}.json',
                self.root / f'ledger-{index}', live=True, env=ENV, now=NOW,
                collector=collect, generator=mocked_generator)
            statuses.append(feed['status'])
            self.assertFalse(store.state['active'])
        self.assertEqual(statuses, ['provider_error', 'ready', 'ready', 'ready'])
        self.assertEqual(collect.call_count, 3)
        self.assertEqual(len(set(requested)), 3)
        self.assertEqual(len(store.state['files']), 3)
        self.assertEqual(len(feed['entries']), 2)
        self.assertEqual(feed['addition_stats'], dict(day=NOW.date().isoformat(), count=2, complete=True))
        self.assertFalse((self.root / 'ledger-3').exists())

    def test_exhausted_day_and_429_stop_export_without_collection_or_ledger_writes(self):
        feed = {**empty_feed(), 'checked_at': NOW.isoformat(), 'status': 'provider_error',
                'addition_stats': dict(day=NOW.date().isoformat(), count=0, complete=True)}
        persist_feed(self.store, feed)
        for stopped in (False, True):
            self.store.state['files'] = ({f'{NOW.date().isoformat()}.stop': None} if stopped else {
                f'{NOW.date().isoformat()}-trial{i}-abcdef123456.json': dict(id=f'trial{i}', fingerprint='abcdef123456'+'0'*52, version=2)
                for i in range(3)})
            self.store.save()
            forbidden = Mock(side_effect=AssertionError('do not collect or generate after daily stop'))
            with patch.object(self.store, 'begin', side_effect=AssertionError('no active marker write')):
                with patch.object(self.store, 'save', side_effect=AssertionError('no persistence')):
                    output = self.root / f'skip-{stopped}.json'
                    result = run(self.store, {**CONFIG, 'requests_per_run': 1}, output,
                        self.root / f'unused-{stopped}', live=True, now=NOW,
                        collector=forbidden, generator=forbidden)
            self.assertEqual(result, feed)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8')), feed)
            self.assertFalse((self.root / f'unused-{stopped}').exists())
            forbidden.assert_not_called()

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

    def test_next_day_collection_failure_keeps_previous_addition_totals_and_exports_safely(self):
        feed = {**empty_feed(), 'checked_at': NOW.isoformat(), 'status': 'no_new',
                'addition_stats': dict(day=NOW.date().isoformat(), count=0, complete=True)}
        persist_feed(self.store, feed)
        generator = Mock(side_effect=AssertionError('no generation on source failure'))
        out = run(self.store, CONFIG, self.root / 'export.json', self.root / 'ledger', live=True,
                  now=NOW + timedelta(days=1), collector=Mock(return_value=([], 0)), generator=generator)
        self.assertEqual(out['status'], 'source_unavailable')
        self.assertEqual(out['addition_stats'], feed['addition_stats'])
        self.assertEqual(json.loads((self.root / 'export.json').read_text()), out)
        self.assertFalse(self.store.state['active'])
        generator.assert_not_called()
