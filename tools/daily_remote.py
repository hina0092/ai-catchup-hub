"""Persist daily feed beside the existing shared request ledger, then export for build."""
import argparse
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re

from collector.card_trial import ROOT, JST
from collector.collect import collect
from collector.daily_cards import checked_feed, configuration, empty_feed, generate, budget_reason
from tools.ai_cache import git
from tools.card_trial_remote import setup
from collector.diagnostics import OperationalError, failure, stage, LOGGER

FEED_FILE = 'feed.json'


def load_feed(store):
    if store.state['active']:
        raise OperationalError('active_generation')
    path = store.directory / FEED_FILE
    if not path.exists():
        return empty_feed()
    if path.is_symlink() or path.stat().st_size > 2_000_000:
        raise OperationalError('invalid_feed')
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
    with stage('config_validate'):
        configuration(config)
    with stage('feed_restore'):
        feed = load_feed(store)
    env = dict(os.environ if env is None else env)
    now = now or datetime.now(JST)
    if live:
        # The validated remote ledger is authoritative. Do not fetch sources or
        # toggle active after the day is exhausted; export the existing feed as-is.
        today = now.astimezone(JST).date().isoformat()
        records = store.state['files']
        used = sum(name.startswith(f'{today}-') and name.endswith('.json') for name in records)
        blocked = budget_reason(used, f'{today}.stop' in records, config)
        if blocked:
            LOGGER.info(json.dumps(dict(event='generation_skipped', reason=blocked, used=used)))
            live = False
    if live:
        with stage('sources_load'):
            sources = json.loads((ROOT / 'collector/sources.json').read_text(encoding='utf-8'))
        selected = [s for s in sources if s['name'] in config['source_names']]
        with stage('ledger_begin'):
            store.begin(ledger)
        try:
            with stage('source_collect'):
                rows, successes = collector(selected)
            if successes and rows:
                with stage('card_generate'):
                    feed = generator(rows, feed, ledger, config, env, store.persist, now=now)
            else:
                feed = {**feed, 'checked_at': now.isoformat(), 'status': 'source_unavailable'}
            with stage('feed_persist'):
                persist_feed(store, feed)
            with stage('ledger_finish'):
                store.finish(ledger)
        except Exception:
            # Never clear the durable active marker after an interrupted/failed save.
            raise
    output = Path(output)
    with stage('feed_export'):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(checked_feed(feed), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return feed


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
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
        with stage('config_load'):
            config = json.loads((ROOT / 'collector/daily_config.json').read_text(encoding='utf-8'))
        with stage('state_setup'):
            store = setup(args.state_dir, f'https://github.com/{repository}.git')
        feed = run(store, config, args.output, args.ledger_dir, live=args.live)
        print(json.dumps({'status': feed['status'], 'published_cards': len(feed['entries']),
                          'updated_at': feed['updated_at']}, ensure_ascii=True))
        return 0
    except Exception as error:
        failure(LOGGER, 'daily_update_stopped', 'daily_main', error)
        print('Daily update stopped; existing public site preserved. Details redacted.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
