"""Source-reference checks, not a semantic fact checker. Human review remains required."""
import re

KINDS = ('announcement', 'research', 'guide', 'practice')
META = {'article_kind', 'comment_kinds', 'grounding'}
GROUNDING_FIELDS = ('title', 'lead', 'changed', 'example', 'caution', 'diagram',
                    *(f'comments.{i}' for i in range(8)))


def validate_grounding(value, article, reject):
    if value.get('article_kind') not in KINDS:
        raise reject('article_kind')
    kinds = value.get('comment_kinds')
    if (not isinstance(kinds, list) or len(kinds) != 8
            or any(k not in ('fact', 'question', 'opinion') for k in kinds)):
        raise reject('comment_kind')
    refs = value.get('grounding')
    if not isinstance(refs, list) or not 5 <= len(refs) <= 22:
        raise reject('grounding_schema')
    required = set(GROUNDING_FIELDS[:5])
    if value.get('diagram') is not None:
        required.add('diagram')
    required.update(f'comments.{i}' for i, kind in enumerate(kinds) if kind == 'fact')
    allowed = required | {f'comments.{i}' for i in range(8)}
    covered = set()
    for ref in refs:
        if (not isinstance(ref, dict) or set(ref) != {'field', 'quote'}
                or not isinstance(ref['field'], str) or ref['field'] not in allowed
                or not isinstance(ref['quote'], str) or not 1 <= len(ref['quote']) <= 200):
            raise reject('grounding_schema')
        if article is not None and ref['quote'] not in article['title'] + '\n' + article['source_text']:
            raise reject('grounding_quote')
        covered.add(ref['field'])
    if not required.issubset(covered):
        raise reject('grounding_missing')
    if article is None:
        return
    if value['article_kind'] != article.get('article_kind'):
        raise reject('article_kind')
    texts = [value[k] for k in ('title', 'lead', 'changed', 'example', 'caution')]
    texts += [c['text'] for c in value['comments']]
    diagram = value.get('diagram')
    if diagram:
        texts += [diagram['question'], *diagram['nodes'], diagram['result']]
    combined = '\n'.join(texts)
    # Known regression checks. They deliberately do not claim full entailment checking.
    if article['article_kind'] != 'announcement' and re.search(r'新発表です|新たに発表され|新機能が登場', combined):
        raise reject('unsupported_announcement')
    for term in article.get('unsupported_terms', []):
        if term in combined:
            raise reject('unsupported_detail')


GROUNDING_SCHEMA = {
    'article_kind': {'type': 'string', 'enum': list(KINDS)},
    'comment_kinds': {'type': 'array', 'minItems': 8, 'maxItems': 8,
                      'items': {'type': 'string', 'enum': ['fact', 'question', 'opinion']}},
    'grounding': {'type': 'array', 'minItems': 5, 'maxItems': 22, 'items': {
        'type': 'object', 'properties': {
            'field': {'type': 'string', 'description': 'title/lead/changed/example/caution/diagram/comments.0〜comments.7'},
            'quote': {'type': 'string', 'description': '入力titleまたはsource_textから200文字以内でそのまま抜き出す。言い換え不可。'}},
        'required': ['field', 'quote'], 'additionalProperties': False}},
}
