"""Persist daily feed beside the existing shared request ledger, then export for build."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re

from collector.card_trial import ROOT, JST
from collector.collect import collect
from collector.daily_cards import checked_feed, configuration, empty_feed, generate
from tools.ai_cache import git
from tools.card_trial_remote import setup

FEED_FILE = 'feed.json'


def load_feed(store):
    if store.state['active']:
        raise ValueError('unfinished generation requires review')
    path = store.directory / FEED_FILE
    if not path.exists():
        return empty_feed()
    if path.is_symlink() or path.stat().st_size > 2_000_000:
        raise ValueError('invalid daily feed file')
    return checked_feed(json.loads(path.read_text(encoding='utf-8')))


def persist_feed(store, feed):
    checked_feed(feed)
    path = store.directory / FEED_FILE
    path.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    git(store.directory, 'add', '--', FEED_FILE)
    # save commits both staged feed and state. A failed push stops the public build.
    store.save()


def run(store, config, output, ledger, *, live=False, env=None, now=None,
        collector=collect, generator=generate):
    configuration(config)
    feed = load_feed(store)
    env = dict(os.environ if env is None else env)
    now = now or datetime.now(JST)
    if live:
        sources = json.loads((ROOT / 'collector/sources.json').read_text(encoding='utf-8'))
        selected = [s for s in sources if s['name'] in config['source_names']]
        store.begin(ledger)
        try:
            rows, successes = collector(selected)
            if successes and rows:
                feed = generator(rows, feed, ledger, config, env, store.persist, now=now)
            else:
                feed = {**feed, 'checked_at': now.isoformat(), 'status': 'source_unavailable'}
            persist_feed(store, feed)
            store.finish(ledger)
        except Exception:
            # Never clear the durable active marker after an interrupted/failed save.
            raise
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(checked_feed(feed), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return feed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--ledger-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'frontend/src/daily-feed.json')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    try:
        repository = os.environ.get('GITHUB_REPOSITORY', '')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('repository')
        config = json.loads((ROOT / 'collector/daily_config.json').read_text(encoding='utf-8'))
        store = setup(args.state_dir, f'https://github.com/{repository}.git')
        feed = run(store, config, args.output, args.ledger_dir, live=args.live)
        print(json.dumps({'status': feed['status'], 'published_cards': len(feed['entries']),
                          'updated_at': feed['updated_at']}, ensure_ascii=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError):
        print('Daily update stopped; existing public site preserved. Details redacted.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
