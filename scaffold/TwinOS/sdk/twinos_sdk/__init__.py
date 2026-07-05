"""TwinOS Plugin SDK — DTOS Interface Specification v1.0 구현.

MVP 범위(08 문서 §1 유의점): FMH Plugin이 실제 필요로 하는 것까지만 구현한다.
공개 계약 동결은 Phase 2 말(diabetes_twin 통과 후).
"""

from twinos_sdk.models import (
    ArtifactRef,
    ErrorClass,
    ErrorInfo,
    GateResult,
    TaskRequest,
    TaskState,
    TaskStatus,
)
from twinos_sdk.twin_agent import (
    CaseSpec,
    PrepareResult,
    ReportResult,
    RunResult,
    TwinAgent,
    TwinContext,
    ValidateResult,
)

__all__ = [
    "ArtifactRef", "ErrorClass", "ErrorInfo", "GateResult",
    "TaskRequest", "TaskStatus", "TaskState",
    "CaseSpec", "PrepareResult", "ReportResult", "RunResult",
    "TwinAgent", "TwinContext", "ValidateResult",
]
