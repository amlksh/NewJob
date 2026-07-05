"""FmhTwinAgent — TwinOS 표준 TwinAgent의 레퍼런스 구현 (08 문서 §4).

Sprint 1 (Walking Skeleton) 구현 순서:
  1. prepare(): 고정 케이스 1건 (템플릿 1개, 파라미터 하드코딩 허용)
  2. run():     Abaqus Runner로 ToolJob 1건 발행 → 초소형 INP 실제 실행
  3. validate(): 가속도 곡선 → libs.cae_toolkit.hic.hic_d() → 판정 1건
  4. report():  1페이지 docx (services/report 경유)
이후 M2에서 타겟 그리드 전개·포지셔닝·케이스 매트릭스로 확장한다 (WBS 2.1).
"""

from __future__ import annotations

from typing import Any

from twinos_sdk import (
    CaseSpec,
    PrepareResult,
    ReportResult,
    RunResult,
    TwinAgent,
    TwinContext,
    ValidateResult,
)

HIC_D_REGULATORY_LIMIT = 1000.0  # FMVSS 201U


class FmhTwinAgent(TwinAgent):
    def prepare(self, ctx: TwinContext, spec: CaseSpec) -> PrepareResult:
        raise NotImplementedError("Sprint 1: 고정 케이스 1건 생성 (WBS 1.5/2.1)")

    def run(self, ctx: TwinContext, case_ref: str, execution: dict[str, Any]) -> RunResult:
        raise NotImplementedError("Sprint 1: abaqus ToolJob 발행 (WBS 1.4)")

    def validate(self, ctx: TwinContext, result_refs: list[str],
                 criteria: list[dict[str, Any]]) -> ValidateResult:
        raise NotImplementedError("Sprint 1: HIC(d) 산출·판정 (libs.cae_toolkit.hic)")

    def report(self, ctx: TwinContext, verdicts: ValidateResult,
               report_spec: dict[str, Any]) -> ReportResult:
        raise NotImplementedError("Sprint 1: 1페이지 docx (services/report)")
