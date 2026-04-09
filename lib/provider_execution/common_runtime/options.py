from __future__ import annotations

from ccbd.api_models import JobRecord


NO_WRAP_PROVIDER_OPTION = 'no_wrap'


def no_wrap_requested(job_or_options: JobRecord | dict[str, object] | None) -> bool:
    if isinstance(job_or_options, JobRecord):
        provider_options = job_or_options.provider_options
    else:
        provider_options = job_or_options
    return bool(dict(provider_options or {}).get(NO_WRAP_PROVIDER_OPTION))


__all__ = ['NO_WRAP_PROVIDER_OPTION', 'no_wrap_requested']
