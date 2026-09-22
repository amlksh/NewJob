"""회귀 기준선 — 해석 결과의 수치 지문을 고정하고 비교한다.

왜 필요한가:
  실데이터 결과가 나빠졌을 때 **파이프라인이 바뀐 것인지 데이터가 나쁜 것인지**
  가를 기준이 필요하다. 입력이 고정된 토이 케이스는 그 기준선이 된다.
  토이 수치가 그대로인데 실데이터가 나빠졌다면 데이터·모델 쪽이고,
  토이 수치가 움직였다면 파이프라인이 바뀐 것이다.

무엇을 고정하는가:
  QoI 4종(ROM, 관절 모멘트, 근육력, 관절반력)과 스케일 계수, 마커 오차의
  **수치**를 평탄한 {이름: 값} 으로 뽑아 JSON 으로 남긴다.
  파일 경로·타임스탬프·run_id 처럼 실행마다 달라지는 것은 넣지 않는다.

환경도 함께 남긴다:
  같은 입력이라도 OpenSim 버전이 바뀌면 수치가 달라질 수 있다 (ADR-0001).
  기준선에 환경을 적어 두면, 어긋났을 때 '버전이 바뀌었다' 를 먼저 확인할 수 있다.

기준선을 새로 만드는 것은 의도적인 행위다. `scripts/refresh_toy_baseline.py`
로만 갱신하고, 그 diff 를 커밋에 남겨 검토받는다. 테스트가 알아서 고쳐 쓰지 않는다.
"""

from __future__ import annotations

import json
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: 기준선 파일 구조 버전. 구조를 바꾸면 올리고, 옛 파일은 읽기를 거절한다.
BASELINE_SCHEMA = 1

#: 기본 허용 오차. 같은 환경에서는 비트 단위로 재현되므로 아주 좁게 잡는다.
#: 넓게 잡으면 파이프라인이 바뀐 것을 놓친다.
DEFAULT_RTOL = 1e-6
DEFAULT_ATOL = 1e-9

_SCALE_RE = re.compile(r"<scales>\s*([0-9.eE+-]+)")


@dataclass
class Deviation:
    """기준선과 어긋난 항목 하나."""

    key: str
    expected: float | None
    actual: float | None
    kind: str  # "changed" | "missing" | "added"

    @property
    def relative(self) -> float | None:
        if self.expected in (None, 0.0) or self.actual is None:
            return None
        return abs(self.actual - self.expected) / abs(self.expected)

    def describe(self) -> str:
        if self.kind == "missing":
            return f"  {self.key}: 기준선에 있으나 이번 실행에 없음 (기준 {self.expected})"
        if self.kind == "added":
            return f"  {self.key}: 기준선에 없던 항목이 생김 (이번 {self.actual})"
        relative = self.relative
        suffix = f", 상대차 {relative:.3e}" if relative is not None else ""
        return f"  {self.key}: 기준 {self.expected!r} → 이번 {self.actual!r}{suffix}"


def environment() -> dict[str, str]:
    """수치에 영향을 줄 수 있는 실행 환경."""
    try:
        import opensim  # noqa: PLC0415

        opensim_version = str(getattr(opensim, "__version__", "") or "unknown")
    except ImportError:  # pragma: no cover - 환경 의존
        opensim_version = "not-installed"
    return {
        "opensim": opensim_version,
        "python": sys.version.split()[0],
        "platform": platform.machine(),
    }


def _scale_factors(path: Path) -> dict[str, float]:
    """ScaleTool 이 남긴 계수. 값 자체보다 '1 이 아닌가' 가 중요하다."""
    if not path.is_file():
        return {}
    values = [float(v) for v in _SCALE_RE.findall(path.read_text(encoding="utf-8"))]
    if not values:
        return {}
    return {
        "scale.min": min(values),
        "scale.max": max(values),
        "scale.count": float(len(values)),
    }


def extract(result: Any) -> dict[str, float]:
    """PipelineResult 에서 비교할 수치만 평탄하게 뽑는다.

    경로·시각·run_id 는 제외한다. 실행마다 달라지므로 회귀 신호가 되지 못한다.
    """
    summary = result.summary
    if summary is None:
        raise ValueError("summary 가 없는 결과에서는 기준선을 만들 수 없다")

    values: dict[str, float] = {}

    for item in summary.range_of_motion:
        values[f"rom.{item.coordinate}.min"] = item.minimum
        values[f"rom.{item.coordinate}.max"] = item.maximum

    for item in summary.joint_moments:
        values[f"moment.{item.name}.peak"] = item.peak_absolute

    for item in summary.muscle_forces:
        values[f"muscle.{item.name}.peak"] = item.peak_absolute

    for item in summary.device_loads:
        values[f"device.{item.name}.peak"] = item.peak_absolute

    for item in summary.other_actuators:
        values[f"actuator.{item.name}.peak"] = item.peak_absolute

    for item in summary.joint_reactions:
        if item.peak_force_n is not None:
            values[f"reaction.{item.label}.force"] = item.peak_force_n
        if item.peak_moment_nm is not None:
            values[f"reaction.{item.label}.moment"] = item.peak_moment_nm

    # 품질 지표도 고정한다. 마커 오차가 커지면 IK 쪽이 바뀐 것이다.
    if result.quality.marker_rms_m is not None:
        values["quality.marker_rms_m"] = result.quality.marker_rms_m
    if result.quality.marker_max_m is not None:
        values["quality.marker_max_m"] = result.quality.marker_max_m

    scale_path = result.outputs.get("scale_factors")
    if scale_path is not None:
        values.update(_scale_factors(Path(scale_path)))

    return values


def build(result: Any, name: str, description: str = "") -> dict:
    """기준선 파일 내용을 만든다."""
    return {
        "schema": BASELINE_SCHEMA,
        "name": name,
        "description": description,
        "environment": environment(),
        "values": extract(result),
    }


def load(path: str | Path) -> dict:
    """기준선 파일을 읽는다. 구조 버전이 다르면 거절한다."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"기준선 파일 없음: {path}. scripts/refresh_toy_baseline.py 로 만들 것"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = payload.get("schema")
    if schema != BASELINE_SCHEMA:
        raise ValueError(
            f"{path.name}: 기준선 구조 버전이 {schema} 인데 코드는 {BASELINE_SCHEMA} 를 기대한다. "
            "기준선을 다시 만들 것"
        )
    return payload


def write(payload: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def compare(
    baseline: dict,
    current: dict[str, float],
    rtol: float = DEFAULT_RTOL,
    atol: float = DEFAULT_ATOL,
) -> list[Deviation]:
    """기준선과 이번 수치를 비교한다.

    항목이 사라지거나 생긴 것도 어긋남으로 본다. QoI 하나가 조용히 빠지는 것이
    값이 바뀌는 것보다 위험하다.
    """
    expected: dict[str, float] = baseline["values"]
    deviations: list[Deviation] = []

    for key, want in sorted(expected.items()):
        if key not in current:
            deviations.append(Deviation(key, want, None, "missing"))
            continue
        got = current[key]
        if abs(got - want) > atol + rtol * abs(want):
            deviations.append(Deviation(key, want, got, "changed"))

    for key in sorted(set(current) - set(expected)):
        deviations.append(Deviation(key, None, current[key], "added"))

    return deviations


def report(baseline: dict, deviations: list[Deviation]) -> str:
    """어긋남을 사람이 읽을 수 있게 정리한다.

    무엇이 얼마나 움직였는지와 함께, 환경이 바뀌었는지도 같이 보여준다.
    수치가 흔들렸을 때 가장 먼저 확인할 것이 그것이기 때문이다.
    """
    lines = [
        f"기준선 '{baseline.get('name')}' 과 {len(deviations)} 개 항목이 어긋났다.",
    ]
    recorded = baseline.get("environment", {})
    now = environment()
    if recorded != now:
        lines.append(
            f"  환경이 다르다: 기준선 {recorded} → 현재 {now} "
            "(OpenSim 버전이 바뀌면 수치가 달라질 수 있다 — ADR-0001)"
        )
    else:
        lines.append(f"  환경은 같다: {now}")
    lines.extend(d.describe() for d in deviations)
    lines.append(
        "  파이프라인을 의도적으로 바꾼 것이면 scripts/refresh_toy_baseline.py 로 "
        "기준선을 갱신하고 그 diff 를 커밋에 남길 것."
    )
    return "\n".join(lines)
