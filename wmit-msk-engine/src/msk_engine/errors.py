"""예외 정의.

규칙: 해석이 실패하면 조용히 넘어가지 않고 예외로 멈춘다.
결측값을 임의 보간으로 메우거나, 실패를 성공처럼 보이게 만들지 않는다.
"""

from __future__ import annotations


class MskEngineError(Exception):
    """이 패키지의 모든 예외의 기반."""


class InputValidationError(MskEngineError):
    """입력 데이터가 해석에 쓸 수 없는 상태.

    마커명 불일치, 단위 불명, 결측 과다, GRF 비동기 등.
    """

    def __init__(self, message: str, findings: list[str] | None = None) -> None:
        self.findings = findings or []
        if self.findings:
            detail = "\n".join(f"  - {f}" for f in self.findings)
            message = f"{message}\n{detail}"
        super().__init__(message)


class StepExecutionError(MskEngineError):
    """OpenSim 도구 실행 실패."""

    def __init__(self, step: str, message: str, log_path: str | None = None) -> None:
        self.step = step
        self.log_path = log_path
        suffix = f" (로그: {log_path})" if log_path else ""
        super().__init__(f"[{step}] {message}{suffix}")


class ConfigurationError(MskEngineError):
    """Case 정의나 Setup XML 템플릿이 잘못됨."""
