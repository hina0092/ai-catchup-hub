"""Shared fictional cast; strict checks apply only to newly generated conversations."""
import json
from pathlib import Path

COMMENTERS = json.loads((Path(__file__).resolve().parents[1] / 'frontend/src/commenters.json').read_text(encoding='utf-8'))
NAMES = tuple(person['name'] for person in COMMENTERS)


def cast_prompt():
    lines = ['commentsは次の固定メンバーだけから選ぶ。基本4人、話題によって3人、合計8コメント。',
             '記事との相性で選び、previous_commentersと同じ組み合わせを続けない。previous_commentersは前の会話の参加者名。',
             '性格は自然に出し、毎回の決め台詞や質問役・説明役・反対役を固定しない。全員が質問も説明もできる。',
             'ドパガキ等の誤解は同じ会話内で記事の根拠に沿って訂正する。架空の体験やAIの内部事情を事実として作らない。']
    for person in COMMENTERS:
        dialect = '関西弁' if person['dialect'] == 'kansai' else '標準語（関西弁にしない）'
        lines.append(f"{person['name']}：{dialect}。{person['personality']}")
    return '\n'.join(lines)


def validate_cast(comments, rejected, previous=()):
    names = {comment['name'] for comment in comments}
    if not names.issubset(NAMES):
        raise rejected('comment_speaker')
    if len(names) not in (3, 4):
        raise rejected('comment_cast_count')
    if previous and names == set(previous):
        raise rejected('comment_cast_repeated')
