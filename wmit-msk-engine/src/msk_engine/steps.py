"""해석 단계 실행.

규칙: OpenSim 도구는 Setup XML 로 실행한다 (CLAUDE.md §2).
Python 에서 속성을 하나씩 세팅하지 않는 이유는 두 가지다.
  1. GUI 로 같은 XML 을 돌려 결과를 대조할 수 있다 (코드 검증).
  2. 실행에 쓰인 설정이 파일로 남아 provenance 에 복사된다 (추적성).

각 단계는 템플릿 XML 을 치환해 run 디렉터리에 쓰고, 그 XML 로 도구를 돌린다.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from msk_engine.errors import ConfigurationError, StepExecutionError

STEP_ORDER = ("scale", "ik", "id", "so", "jr")


@dataclass
class StepResult:
    name: str
    status: str
    duration_s: float
    setup_xml: Path
    outputs: list[Path]
    metrics: dict


def render_setup_xml(
    template: str | Path,
    substitutions: dict[str, str],
    destination: str | Path,
) -> Path:
    """템플릿 XML 의 @PLACEHOLDER@ 를 치환해 run 디렉터리에 쓴다.

    치환되지 않고 남은 자리표시자가 있으면 실패시킨다.
    OpenSim 이 이상한 경로를 조용히 받아들이는 것보다 여기서 멈추는 편이 낫다.
    """
    template = Path(template)
    destination = Path(destination)
    if not template.exists():
        raise ConfigurationError(f"Setup XML 템플릿 없음: {template}")

    text = template.read_text(encoding="utf-8")
    for key, value in substitutions.items():
        text = text.replace(f"@{key}@", str(value))

    leftover = _leftover_placeholders(text)
    if leftover:
        raise ConfigurationError(
            f"{template.name} 에 치환되지 않은 자리표시자: {', '.join(sorted(leftover))}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")

    try:
        ElementTree.parse(destination)
    except ElementTree.ParseError as exc:
        raise ConfigurationError(f"{destination.name} 이 올바른 XML 이 아님: {exc}") from exc

    return destination


def _leftover_placeholders(text: str) -> set[str]:
    found: set[str] = set()
    parts = text.split("@")
    # 홀수 인덱스가 자리표시자 후보
    for token in parts[1::2]:
        if token and token.replace("_", "").isalnum() and token.isupper():
            found.add(token)
    return found


def require_opensim():
    """OpenSim 모듈을 가져온다. 없으면 명확히 실패한다."""
    try:
        import opensim  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise StepExecutionError(
            "setup",
            "OpenSim 파이썬 패키지를 찾을 수 없음. "
            "`pip install opensim` 또는 docker/Dockerfile 환경을 사용할 것",
        ) from exc
    return opensim


def run_scale(
    setup_xml: Path, run_dir: Path, model_out: Path
) -> StepResult:
    """ScaleTool — 정적 trial 과 신장·체중으로 모델을 개인화한다."""
    return _run_tool(
        step="scale",
        setup_xml=setup_xml,
        run_dir=run_dir,
        tool_factory=lambda osim: osim.ScaleTool(str(setup_xml)),
        expected_outputs=[model_out],
    )


def run_ik(setup_xml: Path, run_dir: Path, motion_out: Path) -> StepResult:
    """InverseKinematicsTool — 관절각(ROM) 산출."""
    return _run_tool(
        step="ik",
        setup_xml=setup_xml,
        run_dir=run_dir,
        tool_factory=lambda osim: osim.InverseKinematicsTool(str(setup_xml)),
        expected_outputs=[motion_out],
    )


def run_id(setup_xml: Path, run_dir: Path, forces_out: Path) -> StepResult:
    """InverseDynamicsTool — 관절 모멘트와 잔차 산출."""
    return _run_tool(
        step="id",
        setup_xml=setup_xml,
        run_dir=run_dir,
        tool_factory=lambda osim: osim.InverseDynamicsTool(str(setup_xml)),
        expected_outputs=[forces_out],
    )


def run_static_optimization(
    setup_xml: Path, run_dir: Path, activation_out: Path
) -> StepResult:
    """AnalyzeTool + StaticOptimization — 근육력 산출."""
    return _run_tool(
        step="so",
        setup_xml=setup_xml,
        run_dir=run_dir,
        tool_factory=lambda osim: osim.AnalyzeTool(str(setup_xml)),
        expected_outputs=[activation_out],
    )


def run_joint_reaction(
    setup_xml: Path, run_dir: Path, reaction_out: Path
) -> StepResult:
    """AnalyzeTool + JointReaction — 관절반력 산출.

    결과는 경골(tibia) 좌표계 표현을 기본으로 한다 (CLAUDE.md §4).
    표현 좌표계는 Setup XML 의 express_in_frame 으로 지정한다.
    """
    return _run_tool(
        step="jr",
        setup_xml=setup_xml,
        run_dir=run_dir,
        tool_factory=lambda osim: osim.AnalyzeTool(str(setup_xml)),
        expected_outputs=[reaction_out],
    )


def _run_tool(
    step: str,
    setup_xml: Path,
    run_dir: Path,
    tool_factory,
    expected_outputs: list[Path],
) -> StepResult:
    """OpenSim 도구 하나를 돌리고 결과를 검사한다.

    도구가 False 를 반환하거나 기대한 출력이 없으면 실패로 처리한다.
    OpenSim 은 실패해도 예외를 던지지 않는 경우가 있어 출력 존재를 직접 확인한다.
    """
    osim = require_opensim()
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / f"{step}.log"

    started = time.perf_counter()
    try:
        tool = tool_factory(osim)
        succeeded = tool.run()
    except Exception as exc:  # noqa: BLE001 - OpenSim 예외 타입이 다양하다
        raise StepExecutionError(step, f"도구 실행 중 예외: {exc}", str(log_path)) from exc
    duration = time.perf_counter() - started

    if succeeded is False:
        raise StepExecutionError(step, "도구가 실패를 반환함", str(log_path))

    missing = [str(p) for p in expected_outputs if not Path(p).exists()]
    if missing:
        raise StepExecutionError(
            step,
            "도구는 성공을 반환했으나 기대한 출력이 없음: " + ", ".join(missing),
            str(log_path),
        )

    return StepResult(
        name=step,
        status="ok",
        duration_s=round(duration, 3),
        setup_xml=setup_xml,
        outputs=[Path(p) for p in expected_outputs],
        metrics={},
    )


def archive_setup_xml(setup_xml: Path, run_dir: Path) -> Path:
    """실행에 쓰인 Setup XML 을 run 디렉터리에 보관한다."""
    run_dir = Path(run_dir)
    archive_dir = run_dir / "setup"
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / Path(setup_xml).name
    if Path(setup_xml).resolve() != target.resolve():
        shutil.copy2(setup_xml, target)
    return target
