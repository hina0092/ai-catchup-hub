"""Optional HN metadata enrichment; no requests without --allow-api."""
import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from urllib.request import Request, urlopen

try:
    from .collect import normalize_url, write_articles
except ImportError:
    from collect import normalize_url, write_articles

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://hacker-news.firebaseio.com/v0/'
LOG = logging.getLogger(__name__)


def fetch_json(path):
    request = Request(BASE + path, headers={'User-Agent': 'AI-Catchup-Hub/0.2'})
    with urlopen(request, timeout=5) as response:
        data = response.read(1_000_001)
    if len(data) > 1_000_000:
        raise ValueError('HN response exceeds size limit')
    return json.loads(data)


def positive_id(value):
    return type(value) is int and value > 0


def story_metadata(item, expected_id, checked_at):
    if (not isinstance(item, dict) or item.get('id') != expected_id or
            not positive_id(item.get('id')) or item.get('type') != 'story' or
            item.get('deleted') or item.get('dead')):
        return None
    raw_url = item.get('url')
    url = normalize_url(raw_url) if isinstance(raw_url, str) else None
    timestamp = item.get('time')
    if not url or type(timestamp) is not int or timestamp < 0:
        return None
    try:
        published = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None
    count = item.get('descendants')
    if count is not None and (type(count) is not int or count < 0):
        return None
    return url, {'provider': 'hacker_news', 'story_id': expected_id,
                 'url': f'https://news.ycombinator.com/item?id={expected_id}',
                 'comment_count': count, 'published_at': published, 'checked_at': checked_at}


def enrich(articles, *, allow_api=False, max_requests=62, max_seconds=120,
           fetcher=fetch_json, clock=time.monotonic):
    if type(max_requests) is not int or not 2 <= max_requests <= 202:
        raise ValueError('max_requests must be 2..202')
    if type(max_seconds) is not int or not 1 <= max_seconds <= 300:
        raise ValueError('max_seconds must be 1..300')
    if not isinstance(articles, list) or any(not isinstance(row, dict) or
            not isinstance(row.get('url'), str) for row in articles):
        raise ValueError('invalid article data')
    rows = [dict(row) for row in articles]
    stats = dict(requests=0, failures=0, matched=0, examined=0, skipped=0)
    if not allow_api or not rows:
        return rows, stats
    deadline = clock() + max_seconds
    checked_at = datetime.now(timezone.utc).isoformat()
    targets = {normalize_url(row['url']) for row in rows} - {None}
    if not targets:
        return rows, stats

    def request(path):
        if stats['requests'] >= max_requests or clock() >= deadline:
            return None
        stats['requests'] += 1
        try:
            return fetcher(path)
        except (OSError, ValueError):
            stats['failures'] += 1
            LOG.warning('HN request failed; continuing without this response')
            return None

    lists = []
    for name in ('topstories.json', 'newstories.json'):
        values = request(name)
        lists.append([v for v in values if positive_id(v)][:500] if isinstance(values, list) else [])
    # Interleave top/new so a small request budget covers both lists.
    ids = list(dict.fromkeys(value for index in range(max(map(len, lists), default=0))
                             for values in lists if index < len(values) for value in [values[index]]))
    matches = {}
    for story_id in ids:
        if stats['requests'] >= max_requests or clock() >= deadline:
            break
        item = request(f'item/{story_id}.json')
        stats['examined'] += 1
        metadata = story_metadata(item, story_id, checked_at)
        if metadata is None:
            stats['skipped'] += 1
            continue
        url, discussion = metadata
        if url in targets:
            matches.setdefault(url, []).append(discussion)
    for row in rows:
        candidates = matches.get(normalize_url(row['url']))
        if candidates:
            # One representative thread, without summing unrelated comment counts.
            candidates.sort(key=lambda d: (d['comment_count'] if d['comment_count'] is not None else -1,
                                           d['published_at'], d['story_id']), reverse=True)
            row['discussion'] = dict(candidates[0], related_story_ids=[d['story_id'] for d in candidates])
            stats['matched'] += 1
    return rows, stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'frontend/public/data/articles.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-api', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--max-requests', type=int, default=62)
    parser.add_argument('--max-seconds', type=int, default=120)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    try:
        if args.output.exists() and not args.overwrite:
            raise ValueError('output exists; --overwrite required')
        articles = json.loads(args.input.read_text(encoding='utf-8'))
        rows, stats = enrich(articles, allow_api=args.allow_api,
                             max_requests=args.max_requests, max_seconds=args.max_seconds)
        write_articles(args.output, rows, args.overwrite)
        LOG.info('HN enrichment: %s', stats)
        return 0
    except (OSError, ValueError, TypeError):
        LOG.error('HN enrichment unavailable; existing output preserved')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
