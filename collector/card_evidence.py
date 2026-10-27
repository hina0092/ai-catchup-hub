"""Bounded source excerpts selected by number, never transcribed by the model."""
from copy import deepcopy

from collector.card_grounding import GROUNDING_FIELDS

MAX_QUOTE = 200


def evidence_candidates(article):
    candidates = []
    for key, maximum in (('title', 500), ('source_text', 12000)):
        source = article.get(key)
        if not isinstance(source, str) or not 1 <= len(source) <= maximum:
            raise ValueError('invalid evidence input')
        start = 0
        while start < len(source):
            end = min(start + MAX_QUOTE, len(source))
            if end < len(source):
                # Prefer a sentence/word boundary, but keep excerpts large enough
                # that punctuation-heavy input cannot create unbounded candidates.
                boundary = max(source.rfind(mark, start + 100, end) + 1
                               for mark in '.!?。！？\n ')
                if boundary > start + 100:
                    end = boundary
            quote = source[start:end].strip()
            if quote:
                candidates.append(dict(id=len(candidates), part='title' if key == 'title' else 'body', text=quote))
            start = end
    if not candidates or len(candidates) > 128:
        raise ValueError('invalid evidence input')
    return candidates


def evidence_schema(schema, candidates):
    result = deepcopy(schema)
    result['properties']['grounding'] = {
        'type': 'array', 'minItems': 5, 'maxItems': 22,
        'items': {'type': 'object', 'properties': {
            'field': {'type': 'string', 'enum': list(GROUNDING_FIELDS)},
            'evidence_id': {'type': 'integer', 'minimum': 0, 'maximum': len(candidates) - 1,
                            'description': 'この入力のevidence_candidatesから選ぶ番号。'}},
            'required': ['field', 'evidence_id'], 'additionalProperties': False}}
    return result


def restore_grounding(value, candidates, reject):
    if isinstance(value, dict) and value.get('sufficient') is False:
        return value  # Existing validation still rejects insufficient evidence.
    if not isinstance(value, dict) or not isinstance(value.get('grounding'), list):
        raise reject('grounding_reference_schema')
    refs = value['grounding']
    if not 5 <= len(refs) <= 22:
        raise reject('grounding_reference_schema')
    restored = []
    for ref in refs:
        if (not isinstance(ref, dict) or set(ref) != {'field', 'evidence_id'}
                or ref.get('field') not in GROUNDING_FIELDS):
            raise reject('grounding_reference_schema')
        ident = ref['evidence_id']
        if type(ident) is not int or not 0 <= ident < len(candidates):
            raise reject('grounding_reference')
        restored.append(dict(field=ref['field'], quote=candidates[ident]['text']))
    return {**value, 'grounding': restored}
