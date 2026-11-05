"""Shared fictional cast; strict checks apply only to newly generated conversations."""
import hashlib
import json
from pathlib import Path
import re

COMMENTERS = json.loads((Path(__file__).resolve().parents[1] / 'frontend/src/commenters.json').read_text(encoding='utf-8'))
NAMES = tuple(person['name'] for person in COMMENTERS)
ALIASES = {alias: person['name'] for person in COMMENTERS for alias in person.get('aliases', [])}


def canonical_names(names):
    return {ALIASES.get(name, name) for name in names}


def select_cast(article):
    """Choose before sending, without random state or additional API requests."""
    title = article.get('title', '').casefold()
    # Short how-to conversations use three; other topics normally use four.
    count = 3 if re.search(r'入門|使い方|する方法|手順|\bhow to\b', title) else 4
    seed = article.get('url') or article.get('id') or title
    def rank(person):
        return hashlib.sha256(f"{seed}:{person['id']}".encode()).hexdigest()
    ranked = sorted(COMMENTERS, key=rank)
    selected = ranked[:count]
    if {p['name'] for p in selected} == canonical_names(article.get('previous_commenters', ())):
        selected[-1] = ranked[count]
    return selected


def cast_prompt(selected=None):
    selected = COMMENTERS if selected is None else selected
    names = '・'.join(person['name'] for person in selected)
    lines = [f'今回の参加者はプログラムで確定済み：{names}。人数やメンバーを選び直さない。',
             'この参加者だけで合計8コメントの会話を作る。全参加者が最低1回話し、同じ人が何度話してもよい。',
             '名前を増やさず、名簿を紹介する8人分の発言も作らない。nameは指定の表記と完全一致させる。',
             '性格は自然に出し、毎回の決め台詞や質問役・説明役・反対役を固定しない。全員が質問も説明もできる。',
             '会話中の誤解は同じ会話内で記事の根拠に沿って訂正する。架空の体験やAIの内部事情を事実として作らない。']
    lines.extend([
        '各コメントは発言者自身の話し方・一人称を守る。他の参加者の方言や敬語に引っ張られない。会話全体の口調を統一しない。',
        '人物設定と口調例は架空のキャラを演じ分ける材料であり、記事の事実の根拠ではない。口調例の内容をニュースへ転用しない。',
        '軽くツッコみつつ各人に一理ある会話にする。特定の人を毎回ボケや笑われ役に固定しない。',
    ])
    for person in selected:
        dialect = '関西弁' if person['dialect'] == 'kansai' else '標準語。関西弁の語尾を使わない'
        register = ('敬語。です・ます調で丁寧に話す' if person['register'] == 'polite'
                    else 'ため口・普通体。です・ます調の敬語にしない')
        pronoun = f"一人称は「{person['first_person']}」" if person['first_person'] else '一人称を無理に入れる必要はない'
        lines.append(f"【{person['name']}】属性：{person['attributes']}。性格：{person['personality']}")
        lines.append(f"見る視点：{person['viewpoint']} 話し方：{dialect}。{register}。{pronoun}。{person['speech_style']}")
        lines.append(f"口調例（内容は転用しない）：「{person['example']}」")
    lines.append('出力前にnameごとに発言を読み直し、方言・敬語／ため口・指定の一人称がその人物に合うか確認する。根拠の範囲内で口調を整える。')
    return '\n'.join(lines)


def validate_cast(comments, rejected, previous=(), selected=None):
    names = {comment['name'] for comment in comments}
    if not names.issubset(NAMES):
        raise rejected('comment_speaker')
    if selected is not None and not names.issubset(person['name'] for person in selected):
        raise rejected('comment_speaker')
    if len(names) not in (3, 4):
        raise rejected('comment_cast_count')
    if previous and names == canonical_names(previous):
        raise rejected('comment_cast_repeated')
