from copy import deepcopy
import json
from unittest import TestCase

from collector.card_trial import ROOT, PROMPT, Rejected, validate_inputs, validate_result
from tests.test_card_trial import result


class GroundingTests(TestCase):
    def setUp(self):
        data = json.loads((ROOT / 'validation/card-inputs.json').read_text(encoding='utf-8'))
        self.article = next(r for r in data['articles'] if r['id'] == 'copilot')
        self.good = result(self.article)

    def test_known_guide_misclassification_is_rejected(self):
        bad = deepcopy(self.good); bad['changed'] = '新発表です。作業を引き継げます。'
        with self.assertRaisesRegex(Rejected, 'unsupported_announcement'):
            validate_result(bad, self.article)
        bad = deepcopy(self.good); bad['article_kind'] = 'announcement'
        with self.assertRaisesRegex(Rejected, 'article_kind'):
            validate_result(bad, self.article)

    def test_unsupported_device_in_comments_and_diagram_is_rejected(self):
        for field in ('comment', 'diagram'):
            bad = deepcopy(self.good)
            if field == 'comment':
                bad['comments'][0]['text'] = 'スマホからそのまま使えるんやな。'
            else:
                bad['diagram']['nodes'][0] = '移動中にアプリを使う'
            with self.subTest(field=field), self.assertRaisesRegex(Rejected, 'unsupported_detail'):
                validate_result(bad, self.article)

    def test_quotes_must_really_exist_in_input(self):
        bad = deepcopy(self.good); bad['grounding'][0]['quote'] = '記事にはない都合のよい根拠'
        with self.assertRaisesRegex(Rejected, 'grounding_quote'):
            validate_result(bad, self.article)

    def test_all_fact_sections_and_fact_comments_need_refs(self):
        bad = deepcopy(self.good); bad['grounding'] = [g for g in bad['grounding'] if g['field'] != 'changed']
        with self.assertRaisesRegex(Rejected, 'grounding_missing'):
            validate_result(bad, self.article)
        bad = deepcopy(self.good); bad['comment_kinds'][2] = 'fact'
        with self.assertRaisesRegex(Rejected, 'grounding_missing'):
            validate_result(bad, self.article)
        bad['grounding'].append(dict(field='comments.2', quote=self.article['source_text'][:40]))
        self.assertEqual(validate_result(bad, self.article)['comment_kinds'][2], 'fact')

    def test_missing_kind_fails_before_generation_and_legacy_reports_still_render(self):
        data = dict(format=1, basis='reviewed_brief', articles=[deepcopy(self.article)])
        del data['articles'][0]['article_kind']
        with self.assertRaisesRegex(Rejected, 'article_kind'):
            validate_inputs(data)
        self.assertEqual(validate_result(result())['lead'], '短い説明です。')
        with self.assertRaisesRegex(Rejected, 'grounding_missing'):
            validate_result(result(), self.article)

    def test_valid_refs_do_not_prove_semantic_truth(self):
        # Deliberately document the limit: quotes can be genuine yet irrelevant.
        # This sentence is unsupported but is outside the known regression rules.
        bad = deepcopy(self.good); bad['changed'] = 'すべての作業が自動で完了します。'
        self.assertIn('changed', validate_result(bad, self.article))

    def test_prompt_restores_requested_voice_without_faking_experience(self):
        self.assertIn('関西弁まじりの短い掛け合い', PROMPT)
        self.assertIn('役割名にしない', PROMPT)
        self.assertIn('架空の体験を作らない', PROMPT)
