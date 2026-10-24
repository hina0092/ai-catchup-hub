"""Manual GitHub trial: persist request reservations on a dedicated branch.

Never pushes application code or Pages data. An interrupted or conflicted run
leaves active=true and later runs stop until the state is explicitly reviewed.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re

from collector.card_trial import JST, MODEL, exclusive_json, run_trial, validate_inputs
from collector.gemini import live_allowed
from tools.ai_cache import git

BRANCH = 'card-trial-state'
FILE = 'state.json'
RECORD = re.compile(r'\d{4}-\d{2}-\d{2}-[a-z][a-z0-9-]{0,39}-[a-f0-9]{12}\.json\Z')
STOP = re.compile(r'\d{4}-\d{2}-\d{2}\.stop\Z')


def validate_state(state):
    if (not isinstance(state, dict) or set(state) != {'format', 'active', 'files'}
            or state['format'] != 1 or type(state['active']) is not bool
            or not isinstance(state['files'], dict) or len(state['files']) > 10000):
        raise ValueError('invalid trial state')
    for name, record in state['files'].items():
        if STOP.fullmatch(name):
            if record is not None:
                raise ValueError('invalid stop record')
        elif RECORD.fullmatch(name):
            if (not isinstance(record, dict) or set(record) != {'id', 'fingerprint', 'version'}
                    or not isinstance(record['id'], str)
                    or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', record['id'])
                    or not isinstance(record['fingerprint'], str)
                    or not re.fullmatch(r'[a-f0-9]{64}', record['fingerprint'])
                    or type(record['version']) is not int or record['version'] < 1
                    or name[11:] != f'{record["id"]}-{record["fingerprint"][:12]}.json'):
                raise ValueError('invalid reservation')
        else:
            raise ValueError('invalid trial filename')
    return state


class TrialState:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / FILE
        self.state = None

    def load(self):
        if git(self.directory, 'branch', '--show-current').stdout.strip() != BRANCH:
            raise ValueError('wrong trial branch')
        if self.path.is_symlink() or self.path.stat().st_size > 4_000_000:
            raise ValueError('invalid trial state file')
        self.state = validate_state(json.loads(self.path.read_text(encoding='utf-8')))
        return self.state

    def save(self):
        validate_state(self.state)
        if git(self.directory, 'branch', '--show-current').stdout.strip() != BRANCH:
            raise ValueError('wrong trial branch')
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        git(self.directory, 'add', '--', FILE)
        if git(self.directory, 'diff', '--cached', '--quiet', check=False).returncode != 0:
            git(self.directory, '-c', 'user.name=github-actions[bot]',
                '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                'commit', '-m', 'Record isolated card trial budget [skip ci]')
        # Always push: an earlier failed push must not look like successful persistence.
        git(self.directory, 'push', 'origin', f'HEAD:refs/heads/{BRANCH}')

    def begin(self, ledger):
        if self.state is None:
            self.load()
        if self.state['active']:
            raise ValueError('unfinished trial requires review')
        ledger = Path(ledger)
        ledger.mkdir(parents=True, exist_ok=False)
        for name, value in self.state['files'].items():
            path = ledger / name
            if value is None:
                path.touch()
            else:
                exclusive_json(path, value)
        self.state['active'] = True
        self.save()

    def persist(self, ledger):
        records = dict(self.state['files'])
        for path in Path(ledger).iterdir():
            if path.name == 'trial.lock':
                continue
            if path.is_symlink() or not path.is_file():
                raise ValueError('invalid local ledger')
            if path.stat().st_size > 4096:
                raise ValueError('oversized reservation')
            records[path.name] = None if STOP.fullmatch(path.name) else json.loads(path.read_text(encoding='utf-8'))
        self.state['files'] = records
        self.save()

    def finish(self, ledger):
        # First persist all reservations/stops while still active.
        self.persist(ledger)
        self.state['active'] = False
        self.save()


def setup(directory, remote, initialize=False):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    git(directory, 'init')
    git(directory, 'remote', 'add', 'origin', remote)
    found = git(directory, 'ls-remote', '--exit-code', 'origin', f'refs/heads/{BRANCH}', check=False)
    store = TrialState(directory)
    if found.returncode == 0:
        git(directory, 'fetch', '--depth=1', 'origin', f'refs/heads/{BRANCH}')
        git(directory, 'checkout', '-b', BRANCH, 'FETCH_HEAD')
        store.load()
    elif found.returncode == 2 and initialize:
        git(directory, 'checkout', '--orphan', BRANCH)
        store.state = dict(format=1, active=False, files={})
        store.save()
    else:
        raise OSError('trial state missing or unavailable; no automatic reset')
    return store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--ledger-dir', type=Path, required=True)
    parser.add_argument('--initialize-state', action='store_true')
    args = parser.parse_args()
    try:
        repository = os.environ.get('GITHUB_REPOSITORY', '')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('invalid repository')
        now = datetime.now(JST)
        if (os.environ.get('GEMINI_MODEL', MODEL) != MODEL
                or not live_allowed({'enabled': True}, os.environ, now.date().isoformat())
                or not os.environ.get('GH_TOKEN')):
            raise ValueError('free trial gates closed')
        data = json.loads(args.input.read_text(encoding='utf-8'))
        validate_inputs(data)
        if args.output.exists():
            raise ValueError('existing output')
        store = setup(args.state_dir, f'https://github.com/{repository}.git', args.initialize_state)
        store.begin(args.ledger_dir)
        report = run_trial(data, args.output, live=True, now=now, ledger_dir=args.ledger_dir, persist=store.persist)
        store.finish(args.ledger_dir)
        print(json.dumps({'mode': 'live', 'statuses': [r['status'] for r in report['results']]}))
        return 0 if all(r['status'] == 'accepted' for r in report['results']) else 2
    except (OSError, ValueError, TypeError, KeyError):
        print('Trial stopped; no deployment. Unfinished state requires review. Details redacted.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
