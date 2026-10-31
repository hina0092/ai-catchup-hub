"""Shared fictional cast; strict checks apply only to newly generated conversations."""
import hashlib
import json
from pathlib import Path
import re

COMMENTERS = json.loads((Path(__file__).resolve().parents[1] / 'frontend/src/commenters.json').read_text(encoding='utf-8'))
NAMES = tuple(person['name'] for person in COMMENTERS)


TOPICS = {
    'ねこ背': ('自動化', '効率', '作業', '手間', 'workflow'),
    '積読ペンギン': ('モデル', '研究', '学習', 'model', 'research'),
    '山田': ('画像', '動画', 'ゲーム', 'アニメ', 'image', 'video'),
    '名無し': ('料金', '無料', '条件', '制限', 'price', 'limit'),
    'なると': ('生活', '料理', '使い道', '活用', '日常'),
    'ドパガキ': ('発表', '新機能', '公開', 'launch', 'release'),
    'パキちゃん': ('画面', 'デザイン', '画像', '音声', 'design', 'voice'),
    'バグ太郎': ('指示', 'エージェント', 'コード', 'prompt', 'agent', 'code'),
}


def select_cast(article):
    """Choose before sending, without random state or additional API requests."""
    title = article.get('title', '').casefold()
    # Short how-to conversations use three; other topics normally use four.
    count = 3 if re.search(r'入門|使い方|する方法|手順|\bhow to\b', title) else 4
    body = article.get('source_text', '').casefold()
    seed = article.get('url') or article.get('id') or title
    def rank(person):
        terms = TOPICS[person['name']]
        score = sum(3 * (term in title) + (term in body) for term in terms)
        tie = hashlib.sha256(f"{seed}:{person['id']}".encode()).hexdigest()
        return (-score, tie)
    ranked = sorted(COMMENTERS, key=rank)
    selected = ranked[:count]
    if {p['name'] for p in selected} == set(article.get('previous_commenters', ())):
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
    for person in selected:
        dialect = '関西弁' if person['dialect'] == 'kansai' else '標準語（関西弁にしない）'
        lines.append(f"{person['name']}：{dialect}。{person['personality']}")
    return '\n'.join(lines)


def validate_cast(comments, rejected, previous=(), selected=None):
    names = {comment['name'] for comment in comments}
    if not names.issubset(NAMES):
        raise rejected('comment_speaker')
    if selected is not None and not names.issubset(person['name'] for person in selected):
        raise rejected('comment_speaker')
    if len(names) not in (3, 4):
        raise rejected('comment_cast_count')
    if previous and names == set(previous):
        raise rejected('comment_cast_repeated')
