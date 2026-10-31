from copy import deepcopy
from unittest import TestCase
from collector.card_trial import PROMPT, SCHEMA, Rejected, validate_result
from collector.commenters import COMMENTERS, NAMES, cast_prompt, select_cast, validate_cast
from tests.test_card_trial import result


class CommenterTests(TestCase):
    def test_shared_cast_and_dialects_reach_generation_prompt_and_schema(self):
        self.assertEqual(len(COMMENTERS), 8)
        self.assertEqual(len(set(NAMES)), 8)
        self.assertEqual(SCHEMA['properties']['comments']['items']['properties']['name']['enum'], list(NAMES))
        for person in COMMENTERS:
            self.assertIn(person['name'], cast_prompt())
        dialects = {p['name']: p['dialect'] for p in COMMENTERS}
        self.assertEqual(dialects['ドパガキ'], 'standard')
        self.assertEqual(dialects['バグ太郎'], 'kansai')

    def test_selection_is_stable_topic_aware_and_does_not_mutate_input(self):
        article = dict(title='AIエージェントへの指示とコード', source_text='コードを確認する。', url='https://example.com/a')
        original = deepcopy(article)
        selected = select_cast(article)
        self.assertEqual(len(selected), 4)
        self.assertIn('バグ太郎', [p['name'] for p in selected])
        self.assertEqual(select_cast(article), selected)
        self.assertEqual(article, original)
        self.assertEqual(len(select_cast({**article, 'title': 'AIエージェントの使い方'})), 3)
        previous = [p['name'] for p in selected]
        self.assertNotEqual({p['name'] for p in select_cast({**article, 'previous_commenters': previous})}, set(previous))

    def test_request_limits_schema_and_prompt_to_preselected_people(self):
        import json
        from unittest.mock import patch
        from collector.card_trial import MODEL, request_card
        from tests.test_card_evidence import ARTICLE, response, wire_result
        article = {**ARTICLE, 'title': 'AIエージェントの使い方', 'previous_commenters': ['過去の人'],
                   'selected_commenters': ['入力による上書き不可']}
        original = deepcopy(article)
        chosen = [p['name'] for p in select_cast(article)]
        with patch('collector.card_trial.build_opener') as opener:
            opener.return_value.open.return_value = response(wire_result(article))
            card = request_card(MODEL, 'TEST_ONLY', article)
            payload = json.loads(opener.return_value.open.call_args.args[0].data)
        wire = json.loads(payload['contents'][0]['parts'][0]['text'])
        enum = payload['generationConfig']['responseJsonSchema']['properties']['comments']['items']['properties']['name']['enum']
        self.assertEqual(enum, chosen)
        self.assertEqual(wire['selected_commenters'], chosen)
        self.assertNotIn('previous_commenters', wire)
        prompt = payload['systemInstruction']['parts'][0]['text']
        for name in NAMES:
            self.assertEqual(name in prompt, name in chosen)
        self.assertEqual(article, original)
        self.assertEqual(SCHEMA['properties']['comments']['items']['properties']['name']['enum'], list(NAMES))
        validate_result(card, article, fixed_cast=True)
        outsider = next(name for name in NAMES if name not in chosen)
        card['comments'][0]['name'] = outsider
        with self.assertRaisesRegex(Rejected, '^comment_speaker$'):
            validate_result(card, article, fixed_cast=True)

    def test_new_cast_has_three_or_four_known_speakers(self):
        for count in (3, 4):
            card = result()
            for index, comment in enumerate(card['comments']):
                comment['name'] = NAMES[index % count]
            validate_result(card, fixed_cast=True)
        for count in (1, 2, 5, 8):
            card = result()
            for index, comment in enumerate(card['comments']):
                comment['name'] = NAMES[index % count]
            with self.assertRaisesRegex(Rejected, '^comment_cast_count$'):
                validate_result(card, fixed_cast=True)

    def test_unknown_name_is_rejected_only_for_new_generation(self):
        card = result()
        card['comments'][0]['name'] = '以前の匿名名'
        original = deepcopy(card)
        validate_result(card)  # Stored feeds and reader snapshots stay readable.
        self.assertEqual(card, original)
        with self.assertRaisesRegex(Rejected, '^comment_speaker$'):
            validate_result(card, fixed_cast=True)

    def test_same_group_is_rejected_even_if_order_changes(self):
        card = result()
        previous = sorted({c['name'] for c in card['comments']}, reverse=True)
        with self.assertRaisesRegex(Rejected, '^comment_cast_repeated$'):
            validate_cast(card['comments'], Rejected, previous)
        card['comments'][3]['name'] = 'パキちゃん'
        card['comments'][7]['name'] = 'パキちゃん'
        validate_cast(card['comments'], Rejected, previous)
