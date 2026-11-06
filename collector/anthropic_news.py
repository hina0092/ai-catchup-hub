"""Read Anthropic's public news listing; no third-party feed or invented time."""
from datetime import datetime
import hashlib
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from collector.diagnostics import OperationalError, stage

URL = 'https://www.anthropic.com/news'
AGENT = 'AI-Catchup-Hub'


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
        if tag == 'a' and any(c.endswith('__title-link') for c in attrs.get('class', '').split()):
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
    for row in parser.rows:
        url = row['url']
        parsed = urlsplit(url)
        title = ' '.join(''.join(row['title']).split())
        if (parsed.scheme != 'https' or parsed.netloc != 'www.anthropic.com'
                or not parsed.path.startswith('/news/') or parsed.query or parsed.fragment
                or not title or len(title) > 300):
            continue
        try:
            # Month abbreviations are explicit, independent of the runner locale.
            month, day, year = ''.join(row['date']).strip().replace(',', '').split()
            month_number = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].index(month) + 1
            published_on = datetime(int(year), month_number, int(day)).date().isoformat()
        except (ValueError, TypeError, OverflowError):
            continue
        result.append(dict(id=hashlib.sha256(url.encode()).hexdigest()[:24],
            title=title, url=url, source=source['name'], category=source['category'],
            published_at=None, published_on=published_on, date_precision='day',
            summary='', collected_at=collected_at))
    if not result:
        raise OperationalError('listing_structure')
    return result
