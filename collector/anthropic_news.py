"""Read Anthropic's public news listing; no third-party feed or invented time."""
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
import logging
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from collector.diagnostics import OperationalError, stage

URL = 'https://www.anthropic.com/news'
AGENT = 'AI-Catchup-Hub'
LOGGER = logging.getLogger(__name__)


class NewsListing(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.title = False
        self.time = False
        self.blocked = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name', '').lower() in ('robots', AGENT.lower()):
            self.blocked |= any(t in attrs.get('content', '').lower() for t in ('noai', 'nosnippet', 'noindex'))
        if tag == 'li' and 'data-listing-row' in attrs:
            self.row = dict(title=[], date=[], url='')
        if self.row is None:
            return
        # Keep the semantic suffix, accepting both old __ and current _ separators.
        if tag == 'a' and any(c.endswith('_title-link') for c in attrs.get('class', '').split()):
            self.title = True
            self.row['url'] = urljoin(URL, attrs.get('href', ''))
        if tag == 'time':
            self.time = True

    def handle_endtag(self, tag):
        if tag == 'a':
            self.title = False
        if tag == 'time':
            self.time = False
        if tag == 'li' and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.row is not None:
            if self.title:
                self.row['title'].append(data)
            if self.time:
                self.row['date'].append(data)


def collect_news(source, collected_at, reader):
    if source['url'] != URL or source['name'] != 'Anthropic News':
        raise ValueError('unsupported HTML source')
    robots = RobotFileParser()
    with stage('listing_robots'):
        robots.parse(reader('https://www.anthropic.com/robots.txt').decode('utf-8').splitlines())
    if not robots.can_fetch(AGENT, URL) or (robots.crawl_delay(AGENT) or robots.crawl_delay('*') or 0) > 15:
        raise OperationalError('listing_denied')
    parser = NewsListing()
    with stage('listing_fetch_parse'):
        parser.feed(reader(URL).decode('utf-8'))
    if parser.blocked:
        raise OperationalError('meta_denied')
    result = []
    counts = dict(rows=len(parser.rows), title_links=0, titles=0, valid_dates=0,
                  invalid_urls=0, invalid_titles=0, invalid_dates=0, accepted=0)
    for row in parser.rows:
        url = row['url']
        parsed = urlsplit(url)
        title = ' '.join(''.join(row['title']).split())
        counts['title_links'] += bool(url)
        counts['titles'] += bool(title)
        valid_url = (parsed.scheme == 'https' and parsed.netloc == 'www.anthropic.com'
                     and parsed.path.startswith('/news/') and not parsed.query and not parsed.fragment)
        valid_title = bool(title) and len(title) <= 300
        counts['invalid_urls'] += not valid_url
        counts['invalid_titles'] += not valid_title
        published_on = None
        try:
            # Month abbreviations are explicit, independent of the runner locale.
            month, day, year = ''.join(row['date']).strip().replace(',', '').split()
            month_number = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].index(month) + 1
            published_on = datetime(int(year), month_number, int(day)).date().isoformat()
        except (ValueError, TypeError, OverflowError):
            counts['invalid_dates'] += 1
        else:
            counts['valid_dates'] += 1
        if not valid_url or not valid_title or published_on is None:
            continue
        result.append(dict(id=hashlib.sha256(url.encode()).hexdigest()[:24],
            title=title, url=url, source=source['name'], category=source['category'],
            published_at=None, published_on=published_on, date_precision='day',
            summary='', collected_at=collected_at))
    counts['accepted'] = len(result)
    LOGGER.info(json.dumps(dict(event='listing_summary', **counts), sort_keys=True))
    if not result:
        raise OperationalError('listing_structure')
    return result
