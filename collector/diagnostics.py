"""Public-safe operational diagnostics. Never serialize exception text or payloads."""
from contextlib import contextmanager
import json
import logging
from pathlib import Path
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
ORIGIN_FILES = frozenset(('collector/diagnostics.py', 'collector/daily_cards.py',
    'collector/card_trial.py', 'collector/card_grounding.py', 'collector/card_evidence.py',
    'collector/commenters.py', 'collector/gemini.py', 'collector/article_source.py',
    'collector/collect.py', 'collector/anthropic_news.py', 'tools/daily_remote.py',
    'tools/card_trial_remote.py', 'tools/ai_cache.py'))


class OperationalError(OSError, ValueError):
    def __init__(self, reason):
        super().__init__('operation failed; see safe diagnostics')
        self.reason = reason


REASONS = frozenset(('git_timeout', 'git_failed', 'state_missing',
    'active_generation', 'invalid_feed', 'input_too_large', 'robots_denied',
    'crawl_delay', 'meta_denied', 'empty_body', 'invalid_url', 'host_denied',
    'listing_structure', 'listing_denied', 'source_format', 'feed_format',
    'feed_entities', 'source_limit'))


def error_fields(error):
    # Unwrap only standard URL transport errors, never inspect response bodies.
    if isinstance(error, HTTPError):
        result = {'reason': 'http_error'}
        if type(error.code) is int and 100 <= error.code <= 599:
            result['http_status'] = error.code
        return result
    if isinstance(error, URLError):
        error = error.reason
    if isinstance(error, OperationalError):
        return {'reason': error.reason if isinstance(error.reason, str)
                and error.reason in REASONS else 'operation_error'}
    classes = ((socket.gaierror, 'dns_error'), (ssl.SSLError, 'tls_error'),
               (TimeoutError, 'timeout'), (ConnectionError, 'connection_error'),
               (FileNotFoundError, 'file_missing'), (FileExistsError, 'file_exists'),
               (PermissionError, 'permission_denied'), (json.JSONDecodeError, 'json_decode'),
               (UnicodeError, 'text_decode'), (ET.ParseError, 'xml_parse'),
               (ValueError, 'invalid_value'), (TypeError, 'invalid_type'),
               (KeyError, 'missing_key'), (OSError, 'io_error'))
    return next(({'reason': reason} for cls, reason in classes if isinstance(error, cls)),
                {'reason': 'unexpected_error'})


def failure(logger, event, phase, error, **counts):
    # Call sites supply fixed event/phase names; metadata is integers only.
    record = dict(event=event, phase=phase, **error_fields(error))
    trace = error.__traceback__
    while trace is not None:
        try:
            relative = Path(trace.tb_frame.f_code.co_filename).resolve().relative_to(ROOT).as_posix()
        except (OSError, ValueError):
            relative = None
        if relative in ORIGIN_FILES:
            record.update(origin_file=relative, origin_line=trace.tb_lineno)
        trace = trace.tb_next
    record.update({key: value for key, value in counts.items()
                   if key in ('attempt', 'slot', 'source_index', 'candidate_index', 'exit_code')
                   and type(value) is int and 0 <= value <= 1_000_000})
    logger.warning(json.dumps(record, sort_keys=True))


@contextmanager
def stage(phase):
    """Log before rethrowing, so a failed write keeps its existing stop semantics."""
    started = time.monotonic()
    LOGGER.info(json.dumps(dict(event='operation_started', phase=phase)))
    try:
        yield
    except Exception as error:
        failure(LOGGER, 'operation_failed', phase, error)
        raise
    else:
        LOGGER.info(json.dumps(dict(event='operation_completed', phase=phase,
                                    elapsed_ms=int((time.monotonic() - started) * 1000))))


def git_operation(args):
    # Never echo arguments, paths, remote URLs, stdout, or stderr.
    for arg in args:
        if arg in ('init', 'remote', 'ls-remote', 'fetch', 'checkout', 'branch',
                   'add', 'diff', 'commit', 'push'):
            return 'git_' + arg.replace('-', '_')
    return 'git_other'


def response_failure(logger, data):
    """Only documented enum labels and counts; never model-generated text."""
    record = dict(event='provider_response_rejected')
    if isinstance(data, dict):
        candidates = data.get('candidates')
        if isinstance(candidates, list):
            record['candidate_count'] = len(candidates)
            if candidates and isinstance(candidates[0], dict):
                reason = candidates[0].get('finishReason')
                if isinstance(reason, str):
                    record['finish_reason'] = reason if reason in (
                        'STOP', 'MAX_TOKENS', 'SAFETY', 'RECITATION', 'OTHER',
                        'BLOCKLIST', 'PROHIBITED_CONTENT', 'SPII', 'MALFORMED_FUNCTION_CALL',
                        'UNEXPECTED_TOOL_CALL', 'FINISH_REASON_UNSPECIFIED') else 'unknown'
        feedback = data.get('promptFeedback')
        if isinstance(feedback, dict) and isinstance(feedback.get('blockReason'), str):
            reason = feedback['blockReason']
            record['block_reason'] = reason if reason in (
                'SAFETY', 'OTHER', 'BLOCKLIST', 'PROHIBITED_CONTENT',
                'BLOCK_REASON_UNSPECIFIED') else 'unknown'
    logger.warning(json.dumps(record, sort_keys=True))
