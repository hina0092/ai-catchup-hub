from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
import json

from collector.card_trial import run_trial, ROOT
from tools.ai_cache import git
from tools.card_trial_remote import BRANCH, setup, validate_state
from tests.test_card_trial import ENV, NOW, result


class RemoteTrialTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.environment = patch.dict('os.environ', {'GH_TOKEN': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.remote = self.root / 'remote.git'
        self.remote.mkdir()
        git(self.remote, 'init', '--bare')
        self.data = json.loads((ROOT / 'validation/card-inputs.json').read_text(encoding='utf-8'))

    def new_store(self, name, initialize=False):
        return setup(self.root / name, str(self.remote), initialize)

    def test_missing_state_requires_explicit_initialization(self):
        with self.assertRaises(OSError):
            self.new_store('unapproved')
        store = self.new_store('approved', True)
        self.assertEqual(store.state, {'format': 1, 'active': False, 'files': {}})
        self.assertEqual(git(self.remote, 'for-each-ref', '--format=%(refname:short)', 'refs/heads').stdout.strip(), BRANCH)

    def test_real_git_reservation_survives_restart_and_limits_repeated_runs(self):
        store = self.new_store('first', True)
        ledger = self.root / 'ledger1'
        store.begin(ledger)

        def provider(*args):
            saved = json.loads(git(self.remote, 'show', f'{BRANCH}:state.json').stdout)
            self.assertTrue(saved['active'])
            self.assertGreaterEqual(len(saved['files']), 1)
            return result()

        first = run_trial(self.data, self.root / 'first.json', live=True, env=ENV, now=NOW,
                          ledger_dir=ledger, provider=provider, sleep=Mock(), persist=store.persist)
        store.finish(ledger)
        self.assertEqual([r['status'] for r in first['results']], ['accepted'] * 5)
        restored = self.new_store('second')
        self.assertFalse(restored.state['active'])
        next_ledger = self.root / 'ledger2'
        restored.begin(next_ledger)
        provider2 = Mock()
        second = run_trial(self.data, self.root / 'second.json', live=True, env=ENV, now=NOW,
                           ledger_dir=next_ledger, provider=provider2, sleep=Mock(), persist=restored.persist)
        restored.finish(next_ledger)
        provider2.assert_not_called()
        self.assertTrue(all(r['status'] == 'already_attempted_today' for r in second['results']))

    def test_interrupted_run_blocks_even_when_initialize_is_requested_again(self):
        store = self.new_store('first', True)
        store.begin(self.root / 'ledger')
        restored = self.new_store('second', True)
        with self.assertRaises(ValueError):
            restored.begin(self.root / 'other-ledger')
        self.assertTrue(restored.state['active'])

    def test_persist_failure_prevents_api_and_keeps_remote_run_active(self):
        store = self.new_store('first', True)
        ledger = self.root / 'ledger'
        store.begin(ledger)
        provider = Mock()
        with self.assertRaises(OSError):
            run_trial(self.data, self.root / 'failed.json', live=True, env=ENV, now=NOW,
                      ledger_dir=ledger, provider=provider, sleep=Mock(),
                      persist=Mock(side_effect=OSError('failed state push')))
        provider.assert_not_called()
        self.assertTrue(self.new_store('restored').state['active'])

    def test_stale_writer_cannot_overwrite_state(self):
        first = self.new_store('first', True)
        stale = self.new_store('stale')
        first.begin(self.root / 'ledger1')
        # Both wrote the same active=true snapshot; the reservation makes the
        # first writer strictly newer before the stale writer tries to finish.
        path = self.root / 'ledger1/2026-10-24-polly-aaaaaaaaaaaa.json'
        path.write_text(json.dumps(dict(id='polly', fingerprint='a' * 64, version=1)))
        first.persist(self.root / 'ledger1')
        stale.state['files'] = {'2026-10-24.stop': None}
        with self.assertRaises(OSError):
            stale.save()
        remote = json.loads(git(self.remote, 'show', f'{BRANCH}:state.json').stdout)
        self.assertIn(path.name, remote['files'])
        self.assertNotIn('2026-10-24.stop', remote['files'])

    def test_state_rejects_path_traversal_and_malformed_records(self):
        for files in ({'../outside.json': {}}, {'2026-10-24.stop': 'raw'},
                      {'2026-10-24-polly-aaaaaaaaaaaa.json': dict(id='other', fingerprint='a' * 64, version=1)}):
            with self.assertRaises(ValueError):
                validate_state(dict(format=1, active=False, files=files))

    def test_workflow_is_manual_and_has_no_deployment_step(self):
        workflow = (ROOT / '.github/workflows/card-trial.yml').read_text(encoding='utf-8')
        self.assertIn('  workflow_dispatch:', workflow)
        self.assertNotIn('  schedule:', workflow)
        self.assertNotIn('  push:', workflow)
        self.assertNotIn('  pull_request:', workflow)
        self.assertNotIn('actions/deploy-pages', workflow)
        self.assertNotIn('actions/upload-pages-artifact', workflow)
        self.assertIn('actions/upload-artifact@v4', workflow)
        self.assertNotIn('frontend/public/data/articles.json', workflow)
        self.assertIn("github.repository == 'hina0092/ai-catchup-hub'", workflow)
