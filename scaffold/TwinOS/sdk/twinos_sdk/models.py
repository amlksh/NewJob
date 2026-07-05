"""계약 데이터 모델 (Pydantic v2) — contracts/ JSON Schema와 1:1 대응.

단일 진실은 contracts/의 JSON Schema다(10 문서 §4). 이 모듈이 스키마와
어긋나면 tests/contracts/의 golden example 테스트가 실패해야 한다.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Spec §1.6: 수신자는 모르는 필드를 무시한다(MUST)
_LENIENT = ConfigDict(extra="ignore")


class ErrorClass(StrEnum):
    TOOL_TRANSIENT = "tool_transient_error"
    TOOL_NUMERICAL = "tool_numerical_error"
    AGENT_GENERATION = "agent_generation_error"
    INPUT = "input_error"


class ErrorInfo(BaseModel):
    model_config = _LENIENT
    error_class: ErrorClass = Field(alias="class")
    message: str = Field(max_length=500)
    retryable: bool
    detail_ref: str | None = None
    data: dict[str, Any] | None = None


class ArtifactRef(BaseModel):
    model_config = _LENIENT
    uri: str = Field(pattern=r"^s3://")
    kind: str = Field(pattern=r"^[a-z0-9_]+\.[a-z0-9_]+$")
    urn: str | None = None
    checksum: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    size: int | None = Field(default=None, ge=0)


class TaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED)


class TaskContext(BaseModel):
    model_config = _LENIENT
    artifacts_base: str = Field(pattern=r"^s3://")
    callback_url: str | None = None
    deadline: datetime | None = None
    trace_id: str | None = None


class TaskRequest(BaseModel):
    model_config = _LENIENT
    task_id: str = Field(pattern=r"^step-[0-9A-HJKMNP-TV-Z]{26}$")
    run_id: str = Field(pattern=r"^run-[0-9A-HJKMNP-TV-Z]{26}$")
    project_id: str = Field(pattern=r"^PRJ-[0-9]+$")
    agent: str
    action: str
    inputs: dict[str, Any]
    context: TaskContext


class Progress(BaseModel):
    model_config = _LENIENT
    pct: float | None = Field(default=None, ge=0, le=100)
    message: str | None = None
    updated_at: datetime | None = None


class GateResult(BaseModel):
    model_config = _LENIENT
    gate_key: str = Field(pattern=r"^gate\.")
    gate_version: str
    status: str  # pass | fail | warn — 미지 값은 unknown 처리 대상(Spec §1.6)
    measured: dict[str, Any] | None = None
    threshold: dict[str, Any] | None = None
    evidence_ref: str | None = None
    message: str | None = None
    ts: datetime


class TaskStatus(BaseModel):
    model_config = _LENIENT
    task_id: str
    status: TaskState
    progress: Progress | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    gate_results: list[GateResult] = Field(default_factory=list)
    error: ErrorInfo | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
