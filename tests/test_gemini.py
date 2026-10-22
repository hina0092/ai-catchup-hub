from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from collector.gemini import enrich, validate, request_gemini, live_allowed, NO_IDEA, InvalidAIResult
from collector.article_source import article_text

NOW = datetime(2026, 10, 22, tzinfo=timezone(timedelta(hours=9)))
ENV = dict(ENABLE_GEMINI='true', GEMINI_BILLING_DISABLED='true', GEMINI_FREE_TIER_REVIEWED_ON='2026-10-22', GEMINI_API_KEY='fake', GEMINI_MODEL='gemini-3.5-flash-lite')
CONFIG = dict(enabled=True, max_articles=5, interval_seconds=15, max_input_chars=12000, article_hosts=[])
RESULT = dict(title_ja='日本語タイトル', summary_ja='要約の根拠となる情報です。' * 14, key_points=[s * 4 for s in ['技術の特徴を説明します。','利用時の注意点を示します。','改善の効果を確認します。']], work_idea='保守作業の一部を試行して改善効果を確認する提案です。' * 5)

def rows(n=1):
    return [dict(title='English title', url=f'https://example.com/{i}', summary='A public description. ' * 10) for i in range(n)]

def cache():
    return dict(format=1, entries={}, attempts={})

class GeminiTests(TestCase):
    def test_diagnostics_distinguish_fields_without_leaking_payload(self):
        for change, reason, field in [
            ({'summary_ja': 'SECRET'}, 'length', 'summary_ja'),
            ({'key_points': []}, 'count', 'key_points'),
            ({'work_idea': 123}, 'type', 'work_idea'),
            ({'title_ja': 'SECRET'}, 'language', 'title_ja'),
        ]:
            with self.subTest(reason=reason), self.assertLogs('collector.gemini', level='WARNING') as logs:
                out, stats = self.run_enrich(provider=Mock(return_value={**RESULT, **change}))
            message = '\n'.join(logs.output)
            self.assertIn('reason=' + reason, message)
            self.assertIn('field=' + field, message)
            self.assertIn('source_basis=rss', message)
            self.assertNotIn('SECRET', message)
            self.assertNotIn('https://', message)
            self.assertNotIn('ai_status', out[0])
            self.assertEqual(stats['failed'], 1)

    def test_diagnostics_never_log_exception_details(self):
        secret = 'PRIVATE-KEY-AND-RESPONSE'
        for error, reason in [(ValueError(secret), 'invalid_response'),
                              (OSError(secret), 'network_error'),
                              (HTTPError('https://example.com/?key=' + secret, 429, secret, {}, None), 'rate_limit')]:
            with self.subTest(reason=reason), self.assertLogs('collector.gemini', level='WARNING') as logs:
                self.run_enrich(provider=Mock(side_effect=error))
            self.assertIn('reason=' + reason, '\n'.join(logs.output))
            self.assertNotIn(secret, '\n'.join(logs.output))

    def test_adapter_distinguishes_insufficient_json_and_schema(self):
        for text, reason in [
            (json.dumps({**RESULT, 'sufficient': False}), 'insufficient_evidence'),
            ('PRIVATE malformed text', 'json'),
            (json.dumps({**RESULT, 'sufficient': 'false'}), 'schema'),
        ]:
            answer = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': text}]}}]}
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.read.return_value = json.dumps(answer).encode()
            opener = Mock(); opener.open.return_value = response
            with patch('collector.gemini.build_opener', return_value=opener):
                with self.assertRaises(InvalidAIResult) as caught:
                    request_gemini(ENV['GEMINI_MODEL'], 'PRIVATE_KEY', 'English', 'source')
            self.assertEqual(caught.exception.code, reason)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def run_enrich(self, articles=None, ledger=None, **kwargs):
        options=dict(provider=Mock(return_value=deepcopy(RESULT)), reader=Mock(return_value=''), sleep=Mock(), now=NOW)
        options.update(kwargs)
        return enrich(articles or rows(), ledger if ledger is not None else cache(), CONFIG, ENV, options.pop('persist', Mock()), **options)

    def test_english_japanese_and_work_idea(self):
        articles=rows(2); articles[1]['title']='日本語の原題'
        out, stats=self.run_enrich(articles)
        self.assertEqual(out[0]['title_ja'], RESULT['title_ja'])
        self.assertEqual(out[1]['title_ja'], articles[1]['title'])
        self.assertEqual(out[0]['work_idea'], RESULT['work_idea'])
        self.assertEqual(stats['success'], 2)
        self.assertNotIn('title_ja', articles[0])

    def test_cache_url_normalization_and_version_independence(self):
        ledger=cache(); self.run_enrich(ledger=ledger)
        ledger['entries']['https://example.com/0']['ai_version']=0
        provider=Mock(side_effect=AssertionError('must not call'))
        article=rows()[0]; article['url'] += '?utm_source=x#top'
        out,stats=self.run_enrich([article], ledger, provider=provider)
        self.assertEqual(stats['cache_hits'],1)
        self.assertEqual(out[0]['ai_version'],0)

    def test_missing_key_and_disabled_billing_gate(self):
        for env in [{**ENV,'GEMINI_API_KEY':''},{**ENV,'GEMINI_BILLING_DISABLED':'false'},{**ENV,'GEMINI_FREE_TIER_REVIEWED_ON':'2026-01-01'},{**ENV,'GEMINI_MODEL':'paid-model'},{**ENV,'ENABLE_GEMINI':'false'}]:
            provider=Mock(); reader=Mock()
            out,stats=enrich(rows(),cache(),CONFIG,env,Mock(),provider=provider,reader=reader,now=NOW)
            provider.assert_not_called(); reader.assert_not_called()
            self.assertNotIn('ai_status',out[0])

    def test_five_limit_and_spacing(self):
        sleeper=Mock(); _,stats=self.run_enrich(rows(8),sleep=sleeper)
        self.assertEqual(stats['processed'],5)
        self.assertEqual(sleeper.call_count,4)
        sleeper.assert_called_with(15)

    def test_429_stops_day_and_next_day_can_retry(self):
        ledger=cache(); provider=Mock(side_effect=HTTPError('https://example.com',429,'limit',{},None))
        _,stats=self.run_enrich(rows(3),ledger,provider=provider)
        self.assertEqual(provider.call_count,1)
        self.assertTrue(stats['stopped'])
        p=Mock(return_value=RESULT)
        self.run_enrich(rows(3),ledger,provider=p); p.assert_not_called()
        _,stats=self.run_enrich(rows(3),ledger,now=NOW+timedelta(days=1))
        self.assertEqual(stats['success'],3)

    def test_bad_result_keeps_original_and_same_day_not_retried(self):
        ledger=cache(); p=Mock(return_value={**RESULT,'key_points':[]})
        out,stats=self.run_enrich(ledger=ledger,provider=p)
        self.assertNotIn('ai_status',out[0]); self.assertEqual(stats['failed'],1)
        self.run_enrich(ledger=ledger,provider=p)
        self.assertEqual(p.call_count,1)

    def test_cache_write_failure_prevents_api_call(self):
        provider=Mock(); save=Mock(side_effect=OSError('conflict'))
        _,stats=self.run_enrich(provider=provider,persist=save)
        provider.assert_not_called(); self.assertTrue(stats['stopped'])

    def test_article_basis_and_rss_fallback(self):
        out,_=self.run_enrich(reader=Mock(return_value='本文です。'*200))
        self.assertEqual(out[0]['source_basis'],'article')
        out,_=self.run_enrich(reader=Mock(return_value=''))
        self.assertEqual(out[0]['source_basis'],'rss')
        p=Mock(); a=rows(); a[0]['summary']='tiny'
        self.run_enrich(a,provider=p); p.assert_not_called()

    def test_corrupt_cache_stops_without_reset(self):
        with self.assertRaises(ValueError): self.run_enrich(ledger={'format':2})

    def test_schema_bounds_and_no_idea(self):
        self.assertEqual(validate({**RESULT,'work_idea':NO_IDEA})['work_idea'],NO_IDEA)
        for change in [dict(summary_ja='短い'),dict(key_points=['短い']*3),dict(title_ja=42),dict(work_idea='a'*120)]:
            with self.assertRaises(ValueError): validate({**RESULT,**change})

    def test_http_adapter_schema_no_tools_and_redirection_block(self):
        answer={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({**RESULT,'sufficient':True})}]}}]}
        response=Mock(); response.__enter__=Mock(return_value=response); response.__exit__=Mock(return_value=False)
        response.read.return_value=json.dumps(answer).encode()
        opener=Mock(); opener.open.return_value=response
        with patch('collector.gemini.build_opener',return_value=opener):
            request_gemini(ENV['GEMINI_MODEL'],'fake','English','source')
        req=opener.open.call_args.args[0]; payload=json.loads(req.data)
        self.assertNotIn('tools',payload); self.assertNotIn('fake',req.full_url)
        self.assertEqual(payload['generationConfig']['responseJsonSchema']['properties']['key_points']['maxItems'],3)

class ArticleTests(TestCase):
    def test_robots_host_policy_and_clean_article(self):
        reader=Mock(side_effect=['User-agent: *\nAllow: /','<nav>menu</nav><article><p>本文です</p><script>bad</script><aside>ad</aside></article>'])
        self.assertEqual(article_text('https://zenn.dev/a/articles/b',['zenn.dev'],reader=reader),'本文です')
        reader=Mock(return_value='User-agent: *\nDisallow: /')
        self.assertEqual(article_text('https://zenn.dev/a',['zenn.dev'],reader=reader),'')
        self.assertEqual(reader.call_count,1)
        reader=Mock()
        self.assertEqual(article_text('https://127.0.0.1/a',['127.0.0.1'],reader=reader),'')
        reader.assert_not_called()

    def test_failure_meta_and_input_limit(self):
        reader=Mock(side_effect=OSError())
        self.assertEqual(article_text('https://zenn.dev/a',['zenn.dev'],reader=reader),'')
        reader=Mock(side_effect=['User-agent: *\nAllow: /','<meta name="robots" content="noai"><article>text</article>'])
        self.assertEqual(article_text('https://zenn.dev/a',['zenn.dev'],reader=reader),'')
        reader=Mock(side_effect=['User-agent: *\nAllow: /','<article>'+'あ'*100+'</article>'])
        self.assertEqual(len(article_text('https://zenn.dev/a',['zenn.dev'],limit=20,reader=reader)),20)
