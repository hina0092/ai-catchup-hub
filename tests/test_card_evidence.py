from copy import deepcopy
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from collector.card_evidence import evidence_candidates, evidence_schema, restore_grounding
from collector.card_grounding import GROUNDING_FIELDS
from collector.card_trial import MODEL, PROMPT, Rejected, SCHEMA, request_card, validate_result
from collector.daily_cards import empty_feed, generate
from tests.test_card_trial import ENV, NOW, result
from tests.test_daily_cards import CONFIG, row


ARTICLE = dict(title='元記事の見出し', source_text='Original English evidence. No mobile support is stated. ' * 30,
               article_kind='practice', unsupported_terms=[])


def wire_result(article=ARTICLE):
    value = result(article)
    value['grounding'] = [dict(field=ref['field'], evidence_id=1) for ref in value['grounding']]
    return value


def response(value):
    handle = Mock()
    handle.__enter__ = Mock(return_value=handle)
    handle.__exit__ = Mock(return_value=False)
    handle.read.return_value = json.dumps({'candidates': [{'finishReason': 'STOP',
        'content': {'parts': [{'text': json.dumps(value)}]}}]}).encode()
    return handle


class EvidenceTests(TestCase):
    def test_candidates_are_bounded_exact_substrings_and_preserve_all_source_text(self):
        article = dict(title='Title ' * 83, source_text=('日本語。 English text! 🧭 ' * 600)[:12000])
        pool = evidence_candidates(article)
        self.assertLessEqual(len(pool), 128)
        self.assertEqual([p['id'] for p in pool], list(range(len(pool))))
        original = article['title'] + article['source_text']
        for candidate in pool:
            self.assertTrue(1 <= len(candidate['text']) <= 200)
            self.assertIn(candidate['text'], original)
        self.assertEqual(re.sub(r'\s', '', ''.join(p['text'] for p in pool)), re.sub(r'\s', '', original))
        self.assertEqual(pool, evidence_candidates(article))

    def test_punctuation_and_unbroken_text_cannot_explode_candidate_count(self):
        for body in ('。' * 12000, 'x' * 12000):
            pool = evidence_candidates(dict(title='t' * 500, source_text=body))
            self.assertLessEqual(len(pool), 128)
            self.assertTrue(all(len(p['text']) <= 200 for p in pool))
        for article in ({'title':'t', 'source_text':''}, {'title':'t', 'source_text':'x' * 12001}):
            with self.assertRaisesRegex(ValueError, '^invalid evidence input$'):
                evidence_candidates(article)

    def test_schema_has_only_known_fields_and_article_specific_integer_bounds(self):
        pool = evidence_candidates(ARTICLE)
        schema = evidence_schema(SCHEMA, pool)
        properties = schema['properties']['grounding']['items']['properties']
        self.assertEqual(set(properties), {'field', 'evidence_id'})
        self.assertEqual(properties['field']['enum'], list(GROUNDING_FIELDS))
        self.assertEqual(properties['evidence_id']['maximum'], len(pool) - 1)
        self.assertEqual(properties['evidence_id']['minimum'], 0)
        self.assertIn('quote', SCHEMA['properties']['grounding']['items']['properties'])
        self.assertIn('引用文を生成・翻訳・書き写さず', PROMPT)

    def test_reference_restoration_passes_the_original_quote_validator(self):
        pool = evidence_candidates(ARTICLE)
        value = wire_result()
        restored = restore_grounding(value, pool, Rejected)
        validated = validate_result(restored, ARTICLE)
        self.assertEqual(validated['grounding'][0]['quote'], pool[1]['text'])
        self.assertEqual(value['grounding'][0]['evidence_id'], 1)
        self.assertNotIn('evidence_id', json.dumps(restored))
        self.assertNotIn('grounding', restore_grounding({'sufficient':False}, pool, Rejected))
        with self.assertRaisesRegex(Rejected, 'insufficient_evidence'):
            validate_result(restore_grounding({'sufficient':False}, pool, Rejected), ARTICLE)
        # Previously saved quote-based reports remain readable.
        validate_result(result(ARTICLE), ARTICLE)

    def test_unknown_numbers_and_free_text_quotes_are_never_accepted(self):
        pool = evidence_candidates(ARTICLE)
        for ident in (True, -1, len(pool), '1', 1.5, None):
            value = wire_result(); value['grounding'][0]['evidence_id'] = ident
            with self.subTest(ident=ident), self.assertRaisesRegex(Rejected, '^grounding_reference$'):
                restore_grounding(value, pool, Rejected)
        for ref in (dict(field='comments[0]', evidence_id=1), dict(field='title', quote='PRIVATE'),
                    dict(field='title', evidence_id=1, quote='PRIVATE'), dict(field=[], evidence_id=1)):
            value = wire_result(); value['grounding'][0] = ref
            with self.assertRaisesRegex(Rejected, '^grounding_reference_schema$'):
                restore_grounding(value, pool, Rejected)

    def test_missing_fact_and_diagram_evidence_and_known_false_claims_still_fail(self):
        pool = evidence_candidates(ARTICLE)
        for mutate, reason in (
            (lambda v: v['grounding'].pop(), 'grounding_missing'),
            (lambda v: v['comment_kinds'].__setitem__(0, 'fact'), 'grounding_missing'),
            (lambda v: v.update(article_kind='guide'), 'article_kind'),
            (lambda v: v.update(changed='新発表です。'), 'unsupported_announcement')):
            value = wire_result(); mutate(value)
            with self.subTest(reason=reason), self.assertRaisesRegex(Rejected, reason):
                validate_result(restore_grounding(value, pool, Rejected), ARTICLE)

    def test_transport_uses_current_article_candidates_and_does_not_accept_old_wire_format(self):
        for body in ('First article sentence. ' * 30, 'Second article sentence. ' * 30):
            article = {**ARTICLE, 'source_text':body}
            with patch('collector.card_trial.build_opener') as opener:
                opener.return_value.open.return_value = response(wire_result(article))
                restored = request_card(MODEL, 'PRIVATE_KEY', article)
                payload = json.loads(opener.return_value.open.call_args.args[0].data)
            data = json.loads(payload['contents'][0]['parts'][0]['text'])
            self.assertNotIn('source_text', data)
            self.assertNotIn('PRIVATE_KEY', json.dumps(payload))
            self.assertIn(restored['grounding'][0]['quote'], body)
            validate_result(restored, article)
        with patch('collector.card_trial.build_opener') as opener:
            opener.return_value.open.return_value = response(result(ARTICLE))
            with self.assertRaisesRegex(Rejected, 'grounding_reference_schema'):
                request_card(MODEL, 'PRIVATE_KEY', ARTICLE)

    def test_real_adapter_with_mock_transport_preserves_budget_logs_and_public_privacy(self):
        invalid = wire_result(); invalid['grounding'][0]['evidence_id'] = 999999
        different_cast = wire_result()
        for comment in different_cast['comments']:
            if comment['name'] == 'なると':
                comment['name'] = 'パキちゃん'
        with TemporaryDirectory() as directory, patch('collector.card_trial.build_opener') as opener:
            opener.return_value.open.side_effect = [response(invalid), response(wire_result()), response(different_cast)]
            persisted = Mock()
            with self.assertLogs('collector.daily_cards', level='WARNING') as logs:
                feed = generate([row(i) for i in range(5)], empty_feed(), Path(directory), CONFIG, ENV,
                    persisted, now=NOW, reader=Mock(return_value=ARTICLE['source_text']), sleep=Mock())
            self.assertEqual(opener.return_value.open.call_count, 3)
            self.assertEqual(len(list(Path(directory).glob('*.json'))), 3)
            self.assertEqual(persisted.call_count, 3)
            self.assertEqual(len(feed['entries']), 2)
            self.assertEqual(feed['status'], 'ready')
            self.assertIn('grounding_reference', logs.output[0])
            for private in ('source_text', 'grounding', 'evidence_candidates', 'Original English', 'PRIVATE_KEY'):
                self.assertNotIn(private, json.dumps(feed))
            forbidden = Mock(side_effect=AssertionError('no fourth request'))
            after = generate([row(i) for i in range(5)], feed, Path(directory), CONFIG, ENV,
                persisted, now=NOW, provider=forbidden)
            self.assertEqual(after['status'], 'budget_limit')
            forbidden.assert_not_called()
