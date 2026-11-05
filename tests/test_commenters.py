from copy import deepcopy
from unittest import TestCase
from collector.card_trial import ROOT, PROMPT, SCHEMA, Rejected, validate_result
from collector.commenters import COMMENTERS, NAMES, cast_prompt, select_cast, validate_cast
from tests.test_card_trial import result


class CommenterTests(TestCase):
    def test_each_voice_is_explicit_and_examples_do_not_apply_to_other_speakers(self):
        import json
        cases = json.loads((ROOT / 'tests/fixtures/comment_voice_cases.json').read_text(encoding='utf-8'))['cases']
        profiles = {p['name']: p for p in COMMENTERS}
        for case in cases:
            person = profiles[case['name']]
            with self.subTest(name=case['name'], observed=case['observed']):
                self.assertEqual(person['dialect'], case['dialect'])
                self.assertEqual(person['register'], case['register'])
                prompt = cast_prompt([person])
                self.assertIn('標準語。関西弁の語尾を使わない', prompt)
                self.assertIn('ため口・普通体。です・ます調の敬語にしない', prompt)
                self.assertIn(person['example'], prompt)
                self.assertIn('他の参加者の方言や敬語に引っ張られない', prompt)
        learner = profiles['なると@初心者']
        self.assertEqual(learner['register'], 'polite')
        self.assertIn('敬語。です・ます調で丁寧に話す', cast_prompt([learner]))
        for name, pronoun in [('ねこ背', 'うち'), ('名無し', 'ワイ'), ('タナカラボ', '僕')]:
            self.assertIn(f'一人称は「{pronoun}」', cast_prompt([profiles[name]]))

    def test_style_does_not_add_a_new_rejection_or_rewrite_source_claims(self):
        card = result()
        card['comments'][0]['text'] = '引用した指示には「それでええんやで」とありますね。'
        original = deepcopy(card)
        validate_result(card, fixed_cast=True)
        self.assertEqual(card, original)

    def test_legacy_name_counts_as_the_same_person_for_group_rotation(self):
        names = ['ねこ背', '名無し', 'バグ太郎', 'なると@初心者']
        comments = [dict(name=name) for name in names]
        previous = ['ねこ背', '名無し', 'バグ太郎', 'なると']
        with self.assertRaisesRegex(Rejected, '^comment_cast_repeated$'):
            validate_cast(comments, Rejected, previous)

    def test_shared_cast_and_dialects_reach_generation_prompt_and_schema(self):
        self.assertEqual(len(COMMENTERS), 10)
        self.assertEqual(len(set(NAMES)), 10)
        self.assertEqual(SCHEMA['properties']['comments']['items']['properties']['name']['enum'], list(NAMES))
        for person in COMMENTERS:
            self.assertIn(person['name'], cast_prompt())
        dialects = {p['name']: p['dialect'] for p in COMMENTERS}
        self.assertEqual(dialects['ドパガキ'], 'standard')
        self.assertEqual(dialects['バグ太郎'], 'kansai')

    def test_selection_is_stable_and_does_not_mutate_input(self):
        article = dict(title='AIエージェントへの指示とコード', source_text='コードを確認する。', url='https://example.com/a')
        original = deepcopy(article)
        selected = select_cast(article)
        self.assertEqual(len(selected), 4)
        self.assertEqual(select_cast(article), selected)
        self.assertEqual(article, original)
        self.assertEqual(len(select_cast({**article, 'title': 'AIエージェントの使い方'})), 3)
        previous = [p['name'] for p in selected]
        self.assertNotEqual({p['name'] for p in select_cast({**article, 'previous_commenters': previous})}, set(previous))

    def test_topics_do_not_limit_any_person_including_naruto(self):
        tech = dict(title='新しい推論モデルを発表', source_text='エージェントのコードと研究。')
        everyday = dict(title='生活と料理への活用', source_text='日常の使い道。')
        seen = set()
        for index in range(40):
            url = f'https://example.com/article/{index}'
            selected = select_cast({**tech, 'url': url})
            self.assertEqual(selected, select_cast({**everyday, 'url': url}))
            seen.update(p['name'] for p in selected)
        self.assertEqual(seen, set(NAMES))

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
