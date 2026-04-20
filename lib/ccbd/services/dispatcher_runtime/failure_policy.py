from __future__ import annotations

from completion.models import CompletionDecision

_NON_RETRYABLE_API_AUTH_CODES = frozenset(
    {
        'unauthorized',
        'authenticationerror',
        'authenticationfailed',
        'invalidapikey',
        'invalidauthtoken',
        'invalidtoken',
        'notauthenticated',
        'notloggedin',
        'loginrequired',
        'missingapikey',
    }
)
_NON_RETRYABLE_API_PERMISSION_CODES = frozenset(
    {
        'permissiondenied',
        'accessdenied',
        'forbidden',
        'notauthorized',
    }
)
_NON_RETRYABLE_API_BILLING_CODES = frozenset(
    {
        'insufficientquota',
        'quotaexceeded',
        'paymentrequired',
        'billinghardlimitreached',
        'billingnotactive',
        'insufficientbalance',
        'balanceexhausted',
        'creditbalancetoolow',
    }
)
_NON_RETRYABLE_API_AUTH_MESSAGE_MARKERS = (
    'unauthorized',
    'not logged in',
    'login required',
    'authentication failed',
    'invalid api key',
    'invalid auth',
    'invalid token',
    'run codex login',
    'run login',
)
_NON_RETRYABLE_API_PERMISSION_MESSAGE_MARKERS = (
    'permission denied',
    'access denied',
    'forbidden',
    'not authorized',
)
_NON_RETRYABLE_API_BILLING_MESSAGE_MARKERS = (
    'insufficient quota',
    'quota exceeded',
    'payment required',
    'insufficient balance',
    'billing',
    'credit balance too low',
)


def normalized_error_token(value: object) -> str:
    lowered = str(value or '').strip().lower()
    if not lowered:
        return ''
    return ''.join(ch for ch in lowered if ch.isalnum())


def failure_message_text(decision: CompletionDecision) -> str:
    return ' '.join(
        str(value or '').strip().lower()
        for value in (
            decision.diagnostics.get('error_message'),
            decision.diagnostics.get('fault_message'),
            decision.diagnostics.get('error'),
            decision.diagnostics.get('message'),
            decision.diagnostics.get('text'),
        )
        if str(value or '').strip()
    )


def nonretryable_api_failure_kind(decision: CompletionDecision) -> str | None:
    if decision.status.value != 'failed':
        return None
    tokens = {
        normalized_error_token(decision.reason),
        normalized_error_token(decision.diagnostics.get('error_type')),
        normalized_error_token(decision.diagnostics.get('error_code')),
    }
    tokens.discard('')
    if tokens & _NON_RETRYABLE_API_AUTH_CODES:
        return 'authentication'
    if tokens & _NON_RETRYABLE_API_PERMISSION_CODES:
        return 'permission'
    if tokens & _NON_RETRYABLE_API_BILLING_CODES:
        return 'billing'

    message_text = failure_message_text(decision)
    if any(marker in message_text for marker in _NON_RETRYABLE_API_AUTH_MESSAGE_MARKERS):
        return 'authentication'
    if any(marker in message_text for marker in _NON_RETRYABLE_API_PERMISSION_MESSAGE_MARKERS):
        return 'permission'
    if any(marker in message_text for marker in _NON_RETRYABLE_API_BILLING_MESSAGE_MARKERS):
        return 'billing'
    return None


def is_nonretryable_api_failure(decision: CompletionDecision) -> bool:
    return nonretryable_api_failure_kind(decision) is not None


__all__ = [
    'failure_message_text',
    'is_nonretryable_api_failure',
    'nonretryable_api_failure_kind',
    'normalized_error_token',
]
