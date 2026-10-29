from copy import deepcopy
from unittest import TestCase
from collector.card_trial import PROMPT, SCHEMA, Rejected, validate_result
from collector.commenters import COMMENTERS, NAMES, validate_cast
from tests.test_card_trial import result


class CommenterTests(TestCase):
    def test_shared_cast_and_dialects_reach_generation_prompt_and_schema(self):
        self.assertEqual(len(COMMENTERS), 8)
        self.assertEqual(len(set(NAMES)), 8)
        self.assertEqual(SCHEMA['properties']['comments']['items']['properties']['name']['enum'], list(NAMES))
        for person in COMMENTERS:
            self.assertIn(person['name'], PROMPT)
        dialects = {p['name']: p['dialect'] for p in COMMENTERS}
        self.assertEqual(dialects['ドパガキ'], 'standard')
        self.assertEqual(dialects['バグ太郎'], 'kansai')

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
