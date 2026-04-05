from __future__ import annotations


def execution_restore_capability(adapter, *, provider: str) -> dict[str, object]:
    if adapter is None:
        return {
            'resume_supported': False,
            'restore_mode': 'resubmit_required',
            'restore_reason': 'adapter_missing',
            'restore_detail': f'provider {provider} has no registered execution adapter',
        }

    custom = getattr(adapter, 'restore_diagnostics', None)
    diagnostics = dict(custom() or {}) if callable(custom) else {}
    supports_export = callable(getattr(adapter, 'export_runtime_state', None))
    supports_resume = callable(getattr(adapter, 'resume', None))
    resume_supported = bool(diagnostics.get('resume_supported', supports_export and supports_resume))
    restore_mode = str(diagnostics.get('restore_mode', 'provider_resume' if resume_supported else 'resubmit_required'))
    restore_reason = diagnostics.get('restore_reason', None if resume_supported else 'provider_resume_unsupported')
    restore_detail = diagnostics.get(
        'restore_detail',
        'provider execution can be resumed after ccbd restart'
        if resume_supported
        else 'provider execution cannot be resumed after ccbd restart and requires resubmission',
    )
    return {
        'resume_supported': resume_supported,
        'restore_mode': restore_mode,
        'restore_reason': restore_reason,
        'restore_detail': restore_detail,
    }
