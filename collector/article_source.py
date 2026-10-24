"""Opt-in article extraction: reviewed hosts, robots, bounded HTML, no redirects."""
from html.parser import HTMLParser
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import re

AGENT = 'AI-Catchup-Hub'
# Enabling a host also requires a terms review by the operator (config article_hosts).
SUPPORTED = {'zenn.dev', 'qiita.com', 'github.blog', 'devblogs.microsoft.com', 'aws.amazon.com'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def read_url(url, limit):
    with build_opener(NoRedirect).open(Request(url, headers={'User-Agent': AGENT}), timeout=15) as response:
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('input too large')
        return raw.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []
        self.preferred_parts = []
        self.has_preferred = False
        self.blocked = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name', '').lower() in ('robots', AGENT.lower()):
            if any(t in attrs.get('content', '').lower() for t in ('noai', 'nosnippet', 'noindex')):
                self.blocked = True
        if tag in ('meta', 'link', 'img', 'br', 'hr', 'input', 'source', 'wbr'):
            return
        parent_active, parent_skip, parent_preferred = self.stack[-1][1:] if self.stack else (False, False, False)
        classes = attrs.get('class', '').lower()
        preferred = parent_preferred or bool(set(classes.split()) & {'entry-content', 'markdown-body', 'post__content'})
        self.has_preferred = self.has_preferred or preferred
        active = parent_active or tag == 'article' or preferred
        skip = parent_skip or tag in ('script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript') or bool(re.search(r'\b(advertisement|ads|cookie|navigation|author-bio|post-card|post-content-cta)\b', classes))
        self.stack.append((tag, active, skip, preferred))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                self.parts.append(' ')
                self.preferred_parts.append(' ')
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1][1] and not self.stack[-1][2]:
            self.parts.append(data)
            if self.stack[-1][3]:
                self.preferred_parts.append(data)


def article_text(url, hosts, limit=12000, reader=read_url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
        return ''
    if parsed.hostname not in SUPPORTED.intersection(hosts):
        return ''
    robots_url = f'https://{parsed.hostname}/robots.txt'
    try:
        robots = RobotFileParser()
        robots.parse(reader(robots_url, 128000).splitlines())
        if not robots.can_fetch(AGENT, url):
            return ''
        # Conservatively skip sites requiring long crawl delays.
        if (robots.crawl_delay(AGENT) or robots.crawl_delay('*') or 0) > 15:
            return ''
        parser = ArticleParser()
        parser.feed(reader(url, 2_000_000))
        if parser.blocked:
            return ''
        preferred = ' '.join(''.join(parser.preferred_parts).split())
        return (preferred if parser.has_preferred else ' '.join(''.join(parser.parts).split()))[:limit]
    except (OSError, ValueError):
        return ''
