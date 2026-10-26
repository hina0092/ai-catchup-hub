"""Public RSS / Atom and official Anthropic news collector. Standard library only."""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html.parser import HTMLParser
import json
import logging
from pathlib import Path
import re
import tempfile
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from collector.anthropic_news import collect_news

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)
ATOM = '{http://www.w3.org/2005/Atom}'
MAX_BYTES = 5 * 1024 * 1024


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if not self.hidden:
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1
        self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value, limit=240):
    parser = PlainText()
    parser.feed(value or '')
    text = re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()
    return text if len(text) <= limit else text[:limit - 1] + '…'


def normalize_url(value):
    try:
        if not value or any(c.isspace() or ord(c) < 32 for c in value):
            return None
        url = urlsplit(value)
        if url.scheme.lower() not in ('http', 'https') or not url.hostname or url.username or url.password:
            return None
        host = url.hostname.lower().encode('idna').decode('ascii')
        if ':' in host:
            host = '[' + host + ']'
        port = url.port
        if port and (url.scheme.lower(), port) not in (('http', 80), ('https', 443)):
            host += ':' + str(port)
        query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')]
        return urlunsplit((url.scheme.lower(), host, url.path or '/', urlencode(query), ''))
    except (ValueError, UnicodeError):
        return None


def parse_date(value):
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if date.tzinfo is None:
        return None  # Do not invent the source timezone.
    return date.astimezone(timezone.utc).isoformat()


def parse_feed(data, source, collected_at):
    if len(data) > MAX_BYTES:
        raise ValueError('feed exceeds size limit')
    # Reject DTD/entity declarations, including UTF-16/32 encodings.
    declarations = re.sub(rb'<!\[CDATA\[.*?\]\]>', b'', data.replace(b'\x00', b''), flags=re.DOTALL).upper()
    if b'<!DOCTYPE' in declarations or b'<!ENTITY' in declarations:
        raise ValueError('DTD/entities are not supported')
    root = ET.fromstring(data)
    if root.tag == 'rss':
        channel = root.find('channel')
        if channel is None:
            raise ValueError('RSS channel missing')
        entries = channel.findall('item')
        atom = False
    elif root.tag == ATOM + 'feed':
        entries = root.findall(ATOM + 'entry')
        atom = True
    else:
        raise ValueError('unsupported feed format')
    result = []
    for entry in entries:
        prefix = ATOM if atom else ''
        title = plain_text(entry.findtext(prefix + 'title'), 300)
        link = entry.findtext('link') if not atom else next(
            (node.get('href') for node in entry.findall(ATOM + 'link')
             if node.get('rel', 'alternate') == 'alternate'), None)
        url = normalize_url(urljoin(source['url'], link)) if link else None
        if not title or not url:
            LOG.warning('%s: skipped entry with invalid title/URL', source['name'])
            continue
        summary_node = entry.find(prefix + ('summary' if atom else 'description'))
        summary = '' if summary_node is None else ''.join(summary_node.itertext())
        result.append({
            'id': hashlib.sha256(url.encode()).hexdigest()[:24],
            'title': title, 'url': url, 'source': source['name'],
            'published_at': parse_date(entry.findtext(prefix + ('published' if atom else 'pubDate'))),
            'summary': plain_text(summary), 'category': source['category'],
            'collected_at': collected_at,
        })
    return result


def fetch(url):
    if not normalize_url(url):
        raise ValueError('invalid feed URL')
    request = Request(url, headers={'User-Agent': 'AI-Catchup-Hub/0.1 RSS reader'})
    with urlopen(request, timeout=20) as response:
        if not normalize_url(response.geturl()):
            raise ValueError('invalid redirect URL')
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('feed exceeds size limit')
    return data


def collect(sources, fetcher=fetch):
    articles = {}
    successes = 0
    now = datetime.now(timezone.utc).isoformat()
    for source in sources:
        try:
            if source.get('format') == 'anthropic_news':
                entries = collect_news(source, now, fetcher)
            elif source.get('format', 'rss') == 'rss':
                entries = parse_feed(fetcher(source['url']), source, now)
            else:
                raise ValueError('unsupported source format')
            limit = source.get('max_articles')
            if limit is not None:
                if type(limit) is not int or limit < 1:
                    raise ValueError('max_articles must be a positive integer')
                unique = {entry['url']: entry for entry in reversed(entries)}
                entries = sorted(unique.values(), key=lambda item: (item['published_at'] or item.get('published_on', ''), item['url']), reverse=True)[:limit]
        except (OSError, ValueError, ET.ParseError) as error:
            LOG.warning('%s: failed: %s', source['name'], error)
            continue
        successes += 1
        LOG.info('%s: success, %d articles', source['name'], len(entries))
        for article in entries:
            articles.setdefault(article['url'], article)
    result = sorted(articles.values(), key=lambda item: (item['published_at'] or item.get('published_on', ''), item['url']), reverse=True)
    return result, successes


def write_articles(path, articles, overwrite=False):
    if not articles:
        raise ValueError('no articles; existing output preserved')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(articles, ensure_ascii=False, indent=2) + '\n'
    if not overwrite:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(payload)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=ROOT / 'collector/sources.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'frontend/public/data/articles.json')
    parser.add_argument('--overwrite', action='store_true', help='Explicitly allow replacing generated output')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    try:
        if args.output.exists() and not args.overwrite:
            raise FileExistsError('output exists; use a new path or explicitly pass --overwrite')
        sources = json.loads(args.sources.read_text(encoding='utf-8'))
        if not isinstance(sources, list) or not sources:
            raise ValueError('sources must be a nonempty list')
        for source in sources:
            if not isinstance(source, dict) or not all(isinstance(source.get(k), str) and source[k] for k in ('name', 'url', 'category')):
                raise ValueError('each source requires name, url and category strings')
            if not normalize_url(source['url']):
                raise ValueError('invalid source URL')
            if 'max_articles' in source and (type(source['max_articles']) is not int or source['max_articles'] < 1):
                raise ValueError('max_articles must be a positive integer')
        articles, successes = collect(sources)
        if not successes or not articles:
            raise ValueError('no usable articles; existing output preserved')
        write_articles(args.output, articles, args.overwrite)
        LOG.info('wrote %d unique articles to %s', len(articles), args.output)
        return 0
    except (OSError, ValueError) as error:
        LOG.error('%s', error)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
