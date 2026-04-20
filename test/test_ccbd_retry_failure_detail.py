from __future__ import annotations

from types import SimpleNamespace

from ccbd.services.dispatcher_runtime.finalization_retry_runtime.details import retry_failure_detail


def test_retry_failure_detail_collects_reason_and_diagnostics() -> None:
    decision = SimpleNamespace(
        reason="api_error",
        diagnostics={
            "error_type": "timeout",
            "error_code": "408",
            "error_message": "request timed out",
            "fault_rule_id": "rule-1",
        },
    )

    detail = retry_failure_detail(decision)

    assert detail == (
        "reason=api_error, error_type=timeout, error_code=408, "
        "error_message=request timed out, fault_rule_id=rule-1"
    )


def test_retry_failure_detail_falls_back_to_default_reason() -> None:
    decision = SimpleNamespace(reason="", diagnostics={})

    assert retry_failure_detail(decision) == "reason=api_error"
