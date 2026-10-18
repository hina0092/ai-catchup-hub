"""Remove excerpts from a deployment copy, not the local original."""
import json
from pathlib import Path
import sys


def public_articles(rows):
    return [{k: v for k, v in row.items() if k != 'summary'} for row in rows]


if __name__ == '__main__':
    path = Path(sys.argv[1])
    rows = json.loads(path.read_text(encoding='utf-8'))
    path.write_text(json.dumps(public_articles(rows), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
