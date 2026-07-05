"""dtos.twin-agent/v1 — Twin 수명주기 계약 (Spec §4, 08 문서 §4).

TwinAgent 구현체는 HTTP를 직접 다루지 않는다(MUST NOT). task-api 노출·멱등·
원장 기록은 SDK 서버(Sprint 1에서 apps/orchestrator와 함께 구현)가 대행한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TwinContext:
    """작업 실행 컨텍스트 — 아티팩트 접근과 ToolJob 발행 인터페이스를 제공한다."""

    task_id: str
    run_id: str
    project_id: str
    artifacts_base: str
    # Sprint 1: artifact client / tooljob publisher 주입 지점
    services: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseSpec:
    twin_kind: str
    params: dict[str, Any]
    asset_refs: dict[str, str]
    template_overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Case:
    case_id: str
    ref: str
    label: str = ""
    est_wall_sec: int = 0


@dataclass(frozen=True)
class Check:
    severity: str  # info | warning | error
    code: str
    message: str
    location: str = ""


@dataclass(frozen=True)
class PrepareResult:
    cases: list[Case]
    case_summary: str
    checks: list[Check] = field(default_factory=list)


@dataclass(frozen=True)
class RunResult:
    result_ref: str
    run_metrics: dict[str, Any]


@dataclass(frozen=True)
class VerdictItem:
    case_id: str
    qoi: str
    measured: float
    limit: float
    direction: str  # max | min
    verdict: str    # pass | fail
    evidence_ref: str = ""


@dataclass(frozen=True)
class ValidateResult:
    verdicts_ref: str
    items: list[VerdictItem]
    worst_cases: list[str] = field(default_factory=list)

    @property
    def n_cases(self) -> int:
        return len(self.items)

    @property
    def n_fail(self) -> int:
        return sum(1 for i in self.items if i.verdict == "fail")


@dataclass(frozen=True)
class ReportResult:
    report_ref: str
    numbers_manifest_ref: str
    summary_ref: str = ""


class TwinAgent(ABC):
    """모든 Digital Twin Plugin이 구현하는 표준 수명주기 인터페이스."""

    @abstractmethod
    def prepare(self, ctx: TwinContext, spec: CaseSpec) -> PrepareResult:
        """케이스 생성: 템플릿 선택·파라미터 주입·입력 검증."""

    @abstractmethod
    def run(self, ctx: TwinContext, case_ref: str, execution: dict[str, Any]) -> RunResult:
        """Connector(Runner) 경유 실행 — 도구 직접 실행 금지."""

    @abstractmethod
    def validate(self, ctx: TwinContext, result_refs: list[str],
                 criteria: list[dict[str, Any]]) -> ValidateResult:
        """도메인 검증: QoI 산출·판정표 생성. result_refs 외 데이터 사용 금지."""

    @abstractmethod
    def report(self, ctx: TwinContext, verdicts: ValidateResult,
               report_spec: dict[str, Any]) -> ReportResult:
        """보고서 생성 — 수치는 생성하지 않고 numbers_manifest로 출처 선언."""
