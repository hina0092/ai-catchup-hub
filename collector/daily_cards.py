"""Daily source excerpts -> checked cards. Shares the manual trial request ledger.

Quoted source fragments are checked for presence, not semantic entailment.
Only derived cards are persisted publicly; source excerpts and quotes stay local.
"""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import logging
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit

from collector.article_source import article_text
from collector.card_trial import (JST, MODEL, PROMPT, KINDS, REASONS, Rejected, TEXT_LIMITS,
                                  exclusive_json, request_card, validate_result)
from collector.gemini import live_allowed

STATUSES = {'waiting', 'ready', 'no_new', 'budget_limit', 'generation_paused',
            'source_unavailable', 'invalid_outputs', 'rate_limit', 'provider_error'}
HOSTS = {'zenn.dev', 'github.blog', 'aws.amazon.com', 'openai.com', 'blog.google', 'www.anthropic.com'}
LOGGER = logging.getLogger(__name__)
DAILY_PROMPT = PROMPT.replace(
    '入力は公開記事を人が確認して要点化した資料です。全文ではありません。',
    '入力evidence_candidatesは公開記事から機械抽出した本文の一部と見出しです。人の確認済み要点ではなく、全文とも限りません。')
DAILY_PROMPT = DAILY_PROMPT.replace(
    'article_kindは入力の値をそのまま返す。guideは既存機能の手順紹介で、新発表と呼ばない。',
    'article_kindは記事の内容から判定する。入力がautoの場合も公開日だけを根拠にannouncementにしない。'
    '入力がguide等を指定している場合はその値を守る。guideは既存機能の手順紹介で、新発表と呼ばない。')
DAILY_PROMPT += '\n記事中の見出し・実例と一般化を区別する。仕組みが読み取れなければ図はnull。'
DAILY_PROMPT += '\nタイトルは短く身近に。製品名の表記を変えず、ポリートのような誤記をしない。'


def configuration(value):
    if (not isinstance(value, dict) or type(value.get('enabled')) is not bool
            or type(value.get('daily_requests')) is not int or not 1 <= value['daily_requests'] <= 3
            or type(value.get('retained_cards')) is not int or not 5 <= value['retained_cards'] <= 30
            or type(value.get('max_age_days')) is not int or not 1 <= value['max_age_days'] <= 30
            or not isinstance(value.get('article_hosts'), list) or not value['article_hosts']
            or not set(value['article_hosts']).issubset(HOSTS)
            or not isinstance(value.get('source_names'), list) or not value['source_names']
            or any(not isinstance(n, str) or not n for n in value['source_names'])):
        raise ValueError('daily configuration')
    return value


def empty_feed():
    return dict(format=1, checked_at=None, updated_at=None, status='waiting', entries=[])


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timestamp timezone')
    return parsed


def checked_feed(value):
    if (not isinstance(value, dict)
            or set(value) != {'format', 'checked_at', 'updated_at', 'status', 'entries'}
            or value['format'] != 1 or value['status'] not in STATUSES
            or not isinstance(value['entries'], list) or len(value['entries']) > 30):
        raise ValueError('daily feed schema')
    for name in ('checked_at', 'updated_at'):
        if value[name] is not None:
            timestamp(value[name])
    urls, ids = set(), set()
    for entry in value['entries']:
        if (not isinstance(entry, dict) or set(entry) !=
                {'id', 'url', 'source', 'published_on', 'generated_at', 'article_kind', 'card'}
                or not re.fullmatch(r'a[a-f0-9]{20}', entry.get('id', ''))
                or entry['id'] in ids or entry['url'] in urls
                or not safe_url(entry['url']) or not isinstance(entry['source'], str)
                or not 1 <= len(entry['source']) <= 100 or entry['article_kind'] not in KINDS
                or not isinstance(entry['card'], dict)
                or set(entry['card']) != {*TEXT_LIMITS, 'diagram', 'comments'}):
            raise ValueError('daily feed entry')
        datetime.strptime(entry['published_on'], '%Y-%m-%d')
        timestamp(entry['generated_at'])
        validate_result({'sufficient': True, **entry['card']})
        ids.add(entry['id']); urls.add(entry['url'])
    if value['entries'] and value['updated_at'] is None:
        raise ValueError('missing successful update time')
    return value


def safe_url(value):
    if not isinstance(value, str):
        return False
    try:
        p = urlsplit(value)
        return (isinstance(value, str) and not any(c.isspace() for c in value)
                and p.scheme == 'https' and p.hostname in HOSTS and not p.username
                and not p.password and p.port in (None, 443) and not p.query and not p.fragment)
    except (ValueError, TypeError):
        return False


def candidates(rows, feed, config, now):
    existing = {e['url'] for e in feed['entries']}
    unique = {}
    for row in rows:
        if (not isinstance(row, dict) or not safe_url(row.get('url'))
                or urlsplit(row['url']).hostname not in config['article_hosts']
                or row.get('source') not in config['source_names'] or row['url'] in existing
                or not isinstance(row.get('title'), str) or not 1 <= len(row['title']) <= 500):
            continue
        if (row.get('date_precision') == 'day' and row.get('source') == 'Anthropic News'
                and urlsplit(row['url']).hostname == 'www.anthropic.com'):
            try:
                day = datetime.strptime(row.get('published_on', ''), '%Y-%m-%d').date()
            except (TypeError, ValueError):
                continue
            today = now.astimezone(JST).date()
            if not today - timedelta(days=config['max_age_days']) <= day <= today:
                continue
            # Internal calendar-day sorting boundary, not a publication time.
            date = datetime.combine(day, datetime.min.time(), tzinfo=JST)
        else:
            try:
                date = timestamp(row.get('published_at'))
            except (TypeError, ValueError):
                continue
            if not now - timedelta(days=config['max_age_days']) <= date <= now:
                continue
        unique.setdefault(row['url'], {**row, '_date': date})
    ordered = sorted(unique.values(), key=lambda r: (r['_date'], r['url']), reverse=True)
    # Prefer different publishers before filling remaining slots by recency.
    first, rest, hosts = [], [], set()
    for row in ordered:
        host = urlsplit(row['url']).hostname
        (rest if host in hosts else first).append(row)
        hosts.add(host)
    return (first + rest)[:12]


def daily_provider(model, key, article):
    return request_card(model, key, article, prompt=DAILY_PROMPT)


def generate(rows, feed, ledger, config, env, persist, *, now=None,
             provider=daily_provider, reader=article_text, sleep=time.sleep):
    """Each request is reserved durably before it can be sent. No retries."""
    configuration(config)
    output = deepcopy(checked_feed(feed))
    now = now or datetime.now(JST)
    output['checked_at'] = now.isoformat()
    today = now.astimezone(JST).date().isoformat()
    ledger = Path(ledger)
    if not ledger.is_dir():
        raise ValueError('persistent ledger required')
    used = len(list(ledger.glob(f'{today}-*.json')))
    output['status'] = 'no_new'
    if used >= config['daily_requests'] or (ledger / f'{today}.stop').exists():
        output['status'] = 'budget_limit'
        return output
    if (env.get('GEMINI_MODEL', MODEL) != MODEL
            or not live_allowed(config, env, today)):
        output['status'] = 'generation_paused'
        return output
    queue = candidates(rows, output, config, now)
    if not queue:
        return output
    attempts, successes = 0, 0
    for row in queue:
        if used >= config['daily_requests']:
            break
        ident = 'a' + hashlib.sha256(row['url'].encode()).hexdigest()[:20]
        if any(ledger.glob(f'{today}-{ident}-*.json')):
            continue
        excerpt = reader(row['url'], config['article_hosts'], limit=10000)
        if not isinstance(excerpt, str) or len(excerpt.strip()) < 400:
            continue
        hint = 'guide' if re.search(r'\bhow to\b|入門|使い方|する方法|手順', row['title'], re.I) else 'auto'
        unsupported = [t for t in ('スマホ', '移動中', 'モバイル')
                       if 'copilot' in row['title'].lower() and t not in excerpt]
        article = dict(id=ident, url=row['url'], source=row['source'], title=row['title'],
                       published_on=row['_date'].astimezone(JST).date().isoformat(),
                       article_kind=hint, source_text=excerpt.strip(), unsupported_terms=unsupported,
                       source_basis='article_excerpt')
        fingerprint = hashlib.sha256(json.dumps(article, sort_keys=True).encode()).hexdigest()
        exclusive_json(ledger / f'{today}-{ident}-{fingerprint[:12]}.json',
                       dict(id=ident, fingerprint=fingerprint, version=2))
        persist(ledger)  # Exceptions stop the job; never call the provider without a pushed reservation.
        if used:
            sleep(15)
        used += 1; attempts += 1
        phase = 'response'
        try:
            raw = provider(MODEL, env['GEMINI_API_KEY'], article)
            phase = 'validation'
            expected = hint if hint != 'auto' else raw.get('article_kind') if isinstance(raw, dict) else None
            result = validate_result(raw, {**article, 'article_kind': expected})
            # Do not publish input excerpts or the private grounding quote list.
            card = {k: result[k] for k in (*TEXT_LIMITS, 'diagram', 'comments')}
            output['entries'].append(dict(id=ident, url=row['url'], source=row['source'],
                published_on=article['published_on'], generated_at=now.isoformat(),
                article_kind=result['article_kind'], card=card))
            successes += 1
        except Rejected as error:
            output['status'] = 'invalid_outputs'
            # Public Actions logs: allowlisted codes only, never exception text,
            # URLs, source excerpts, raw model output, keys or tracebacks.
            reason = str(error) if str(error) in REASONS else 'invalid_result'
            LOGGER.warning(json.dumps(dict(event='daily_card_rejected',
                attempt=attempts, phase=phase, reason=reason), sort_keys=True))
        except HTTPError as error:
            output['status'] = 'rate_limit' if error.code == 429 else 'provider_error'
            if error.code == 429:
                (ledger / f'{today}.stop').touch(exist_ok=True)
                persist(ledger)
            break
        except (OSError, ValueError, TypeError, KeyError):
            output['status'] = 'provider_error'
            break
    if successes:
        output['entries'].sort(key=lambda e: (e['published_on'], e['generated_at'], e['id']), reverse=True)
        output['entries'] = output['entries'][:config['retained_cards']]
        output['updated_at'] = now.isoformat()
        output['status'] = 'ready'
    elif not attempts and queue:
        output['status'] = 'source_unavailable'
    return checked_feed(output)
