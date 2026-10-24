"""Render a trial JSON as a local review page. No external assets or scripts."""
import argparse
from html import escape
import json
from pathlib import Path
from urllib.parse import urlsplit

from collector.card_trial import validate_result, Rejected


def review_html(report):
    if not isinstance(report, dict) or report.get('format') != 1 or not isinstance(report.get('results'), list):
        raise Rejected('report_schema')
    cards = []
    for entry in report['results']:
        ident = escape(str(entry.get('id', 'unknown')))
        status = escape(str(entry.get('status', 'unknown')))
        body = f'<p class="status">{ident} · {status}</p>'
        if entry.get('status') == 'accepted':
            card = validate_result({'sufficient': True, **entry['card']})
            body += f'<h2>{escape(card["title"])}</h2><p>{escape(card["lead"])}</p>'
            diagram = card['diagram']
            if diagram:
                sep = ' → ' if diagram['layout'] == 'steps' else ' ＋ '
                nodes = sep.join(escape(n) for n in diagram['nodes'])
                body += f'<figure><strong>{escape(diagram["question"])}</strong><p>{nodes}</p><b>↓ {escape(diagram["result"])}</b><figcaption>AIの模式図・実際の画面ではありません</figcaption></figure>'
            for key, heading in [('changed', '🔎 何が変わった？'), ('example', '💡 例えば'), ('caution', '📌 知っておきたいこと')]:
                body += f'<h3>{heading}</h3><p>{escape(card[key])}</p>'
            body += '<div class="fiction">💬 AIによる架空の会話。実在の投稿・利用者の声ではありません。</div><ol>'
            for index, comment in enumerate(card['comments']):
                parent = comment['reply_to']
                reply = f' ↳ {parent + 1}への返信' if parent is not None else ''
                body += f'<li><small>{index + 1} · {escape(comment["name"])}{reply}</small><p>{escape(comment["text"])}</p></li>'
            body += '</ol>'
        else:
            body += '<p>採用された生成結果はありません。</p>'
        url = entry.get('url', '')
        parsed = urlsplit(url)
        if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password:
            body += f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">元記事で事実を確認する ↗</a>'
        cards.append(f'<article>{body}</article>')
    mode = escape(str(report.get('mode', 'unknown')))
    return '''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>AIカード生成の検証結果</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f1f3ed;color:#2a4238;font-family:Meiryo,sans-serif;line-height:1.85}main{max-width:650px;margin:auto;padding:22px 14px}h1{font-size:24px}h2{font-size:23px}h3{font-size:14px;margin-bottom:4px}p{font-size:14px;margin-top:4px}article{padding:24px;background:#fffef9;border:1px solid #dce4d5;border-radius:18px;margin:22px 0;overflow-wrap:anywhere}figure{margin:20px 0;padding:18px;background:#e3eee2;border-radius:12px;font-size:13px}figcaption,.status,small{font-size:11px;color:#74816d}.fiction{padding:12px;background:#efeaf5;border-radius:10px;font-size:12px}li{margin:20px 0}a{color:#476542}.note{padding:15px;background:#e6ebdc;border-radius:12px;font-size:12px}
    </style></head><body><main><h1>🧪 AIカード生成の検証結果</h1>''' + f'<p class="note">モード：{mode}<br>入力は確認済み要点メモ。全文・RSSからの自動収集テストではありません。<br>形式チェック済みでも、事実と読み心地の確認が必要です。</p>' + ''.join(cards) + '</main></body></html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        page = review_html(json.loads(args.input.read_text(encoding='utf-8')))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as handle:
            handle.write(page)
        print('Review page saved locally.')
        return 0
    except (OSError, ValueError, TypeError, KeyError):
        print('Review page unavailable; existing output retained.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
