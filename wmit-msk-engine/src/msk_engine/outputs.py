"""결과 추출 — 관절가동범위, 관절 모멘트, 근육력, 관절반력.

설계 문서의 QoI 네 가지(V&V 추적표 §QoI)를 해석 결과 파일에서 뽑아
`results/summary.json` 하나로 모은다. 웹 계층(P2/P3)이 읽을 것도 이 파일이다.

규칙 두 가지를 지킨다 (CLAUDE.md §4):
  - 단위와 좌표계를 결과에 명시한다. 관절반력은 표현 좌표계가 없으면
    숫자만으로는 의미가 없다.
  - 품질 지표를 함께 싣는다. 마커 오차와 잔차를 모르는 관절반력 값은
    인용할 수 없다.

값이 없으면 0 이나 빈 목록으로 채우지 않고 `notes` 에 이유를 남긴다.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

from msk_engine.quality import read_storage

#: 장치가 만든 구성요소 이름 접두사 (device.builder.DEVICE_PREFIX 와 같아야 한다)
DEVICE_PREFIX = "device"

#: Inverse Dynamics 열 접미사 → (물리량, 단위)
_ID_SUFFIXES = {"_moment": ("joint_moment", "N*m"), "_force": ("joint_force", "N")}

#: 관절반력 열 접미사
_REACTION_FORCE = ("fx", "fy", "fz")
_REACTION_MOMENT = ("mx", "my", "mz")


@dataclass
class CoordinateRange:
    """한 좌표의 가동범위 (QoI-4 ROM)."""

    coordinate: str
    minimum: float
    maximum: float
    span: float
    unit: str


@dataclass
class PeakSeries:
    """한 열의 최댓값·최솟값 (QoI-2 모멘트, QoI-3 근육력)."""

    name: str
    peak_absolute: float
    minimum: float
    maximum: float
    unit: str
    kind: str = ""


@dataclass
class JointReactionPeak:
    """한 관절의 반력 최댓값 (QoI-1).

    label 은 OpenSim 이 만든 열 접두사이며 `<관절>_on_<물체>_in_<좌표계>` 형태다.
    표현 좌표계가 여기에 들어 있으므로 그대로 보존한다.
    """

    label: str
    peak_force_n: float | None
    peak_moment_nm: float | None
    expressed_in: str = ""


@dataclass
class ResultSummary:
    """한 번의 해석에서 뽑은 QoI 전체."""

    range_of_motion: list[CoordinateRange] = field(default_factory=list)
    joint_moments: list[PeakSeries] = field(default_factory=list)
    muscle_forces: list[PeakSeries] = field(default_factory=list)
    device_loads: list[PeakSeries] = field(default_factory=list)
    other_actuators: list[PeakSeries] = field(default_factory=list)
    joint_reactions: list[JointReactionPeak] = field(default_factory=list)
    quality: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    def write(self, run_dir: str | Path, filename: str = "summary.json") -> Path:
        target = Path(run_dir) / "results" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return target


def _series(rows: list[list[float | None]], index: int) -> list[float]:
    return [
        row[index]
        for row in rows
        if index < len(row) and row[index] is not None and not math.isnan(row[index])
    ]


def coordinate_ranges(
    motion_file: str | Path, coordinates: list[str] | None = None
) -> tuple[list[CoordinateRange], list[str]]:
    """IK 결과에서 좌표별 가동범위를 뽑는다.

    회전 좌표의 단위는 파일 헤더의 inDegrees 를 따른다. 추정하지 않는다.
    """
    motion_file = Path(motion_file)
    notes: list[str] = []
    if not motion_file.exists():
        return [], [f"IK 결과 파일 없음: {motion_file}"]

    metadata, header, rows = read_storage(motion_file)
    if not rows:
        return [], [f"IK 결과에 데이터가 없음: {motion_file}"]

    in_degrees = metadata.get("inDegrees", "").strip().lower()
    if in_degrees == "yes":
        unit = "deg"
    elif in_degrees == "no":
        unit = "rad"
    else:
        unit = "unknown"
        notes.append(
            f"{motion_file.name} 헤더에 inDegrees 가 없어 각도 단위를 확정할 수 없음"
        )

    wanted = set(coordinates) if coordinates else None
    missing = set(wanted) - set(header) if wanted else set()
    if missing:
        notes.append(f"IK 결과에 없는 좌표: {', '.join(sorted(missing))}")

    ranges: list[CoordinateRange] = []
    for index, name in enumerate(header):
        if name == "time" or (wanted is not None and name not in wanted):
            continue
        values = _series(rows, index)
        if not values:
            notes.append(f"좌표 '{name}' 에 읽을 수 있는 값이 없음")
            continue
        ranges.append(
            CoordinateRange(
                coordinate=name,
                minimum=min(values),
                maximum=max(values),
                span=max(values) - min(values),
                unit=unit,
            )
        )
    return ranges, notes


def joint_moments(
    id_file: str | Path, coordinates: list[str] | None = None
) -> tuple[list[PeakSeries], list[str]]:
    """Inverse Dynamics 결과에서 좌표별 모멘트·힘의 최댓값을 뽑는다."""
    id_file = Path(id_file)
    if not id_file.exists():
        return [], [f"Inverse Dynamics 결과 파일 없음: {id_file}"]

    _, header, rows = read_storage(id_file)
    if not rows:
        return [], [f"Inverse Dynamics 결과에 데이터가 없음: {id_file}"]

    notes: list[str] = []
    wanted = set(coordinates) if coordinates else None
    peaks: list[PeakSeries] = []
    for index, name in enumerate(header):
        if name == "time":
            continue
        kind, unit = "", ""
        base = name
        for suffix, (label, suffix_unit) in _ID_SUFFIXES.items():
            if name.endswith(suffix):
                kind, unit, base = label, suffix_unit, name[: -len(suffix)]
                break
        if wanted is not None and base not in wanted:
            continue
        values = _series(rows, index)
        if not values:
            notes.append(f"'{name}' 에 읽을 수 있는 값이 없음")
            continue
        peaks.append(
            PeakSeries(
                name=name,
                peak_absolute=max(abs(v) for v in values),
                minimum=min(values),
                maximum=max(values),
                unit=unit or "unknown",
                kind=kind or "unknown",
            )
        )
    return peaks, notes


def classify_actuators(model_file: str | Path) -> dict[str, str]:
    """모델을 읽어 액추에이터 이름을 muscle / device / actuator 로 나눈다.

    이름 규칙으로 짐작하지 않고 모델에 직접 묻는다. 근육과 예비(reserve)
    액추에이터를 섞어 보고하면 '근육력' 이 실제보다 커 보인다.
    """
    import opensim as osim  # noqa: PLC0415 - OpenSim 이 있을 때만 쓴다

    model = osim.Model(str(model_file))
    model.initSystem()

    kinds: dict[str, str] = {}
    muscles = model.getMuscles()
    for index in range(muscles.getSize()):
        kinds[muscles.get(index).getName()] = "muscle"

    forces = model.getForceSet()
    for index in range(forces.getSize()):
        name = forces.get(index).getName()
        if name in kinds:
            continue
        kinds[name] = "device" if name.startswith(f"{DEVICE_PREFIX}_") else "actuator"
    return kinds


def actuator_peaks(
    force_file: str | Path, kinds: dict[str, str] | None = None
) -> tuple[dict[str, list[PeakSeries]], list[str]]:
    """Static Optimization 결과에서 액추에이터별 힘/토크 최댓값을 뽑는다.

    kinds 를 주지 않으면 장치 접두사만으로 나누고, 근육과 예비 액추에이터를
    구분할 수 없다는 사실을 notes 에 남긴다.
    """
    force_file = Path(force_file)
    empty: dict[str, list[PeakSeries]] = {"muscle": [], "device": [], "actuator": []}
    if not force_file.exists():
        return empty, [f"Static Optimization 결과 파일 없음: {force_file}"]

    _, header, rows = read_storage(force_file)
    if not rows:
        return empty, [f"Static Optimization 결과에 데이터가 없음: {force_file}"]

    notes: list[str] = []
    if kinds is None:
        notes.append(
            "모델을 읽지 못해 근육과 예비 액추에이터를 구분하지 못함 — "
            "muscle 목록에 예비 액추에이터가 섞일 수 있다"
        )

    grouped: dict[str, list[PeakSeries]] = {"muscle": [], "device": [], "actuator": []}
    for index, name in enumerate(header):
        if name == "time":
            continue
        if kinds is not None:
            kind = kinds.get(name, "actuator")
        else:
            kind = "device" if name.startswith(f"{DEVICE_PREFIX}_") else "muscle"

        values = _series(rows, index)
        if not values:
            notes.append(f"'{name}' 에 읽을 수 있는 값이 없음")
            continue
        # SO 결과의 단위는 액추에이터 종류에 따라 다르다. 근육은 N,
        # 좌표 액추에이터는 그 좌표가 회전이면 N*m 다. 모델 없이 단정할 수 없다.
        unit = "N" if kind == "muscle" else "N or N*m"
        grouped.setdefault(kind, []).append(
            PeakSeries(
                name=name,
                peak_absolute=max(abs(v) for v in values),
                minimum=min(values),
                maximum=max(values),
                unit=unit,
                kind=kind,
            )
        )
    return grouped, notes


def joint_reaction_peaks(
    reaction_file: str | Path,
) -> tuple[list[JointReactionPeak], list[str]]:
    """관절반력 결과에서 관절별 합력·합모멘트의 최댓값을 뽑는다.

    열 이름은 `<관절>_on_<물체>_in_<좌표계>_fx` 형태다. 접두사로 묶어
    성분을 모은 뒤 크기를 계산한다.
    """
    reaction_file = Path(reaction_file)
    if not reaction_file.exists():
        return [], [f"관절반력 결과 파일 없음: {reaction_file}"]

    _, header, rows = read_storage(reaction_file)
    if not rows:
        return [], [f"관절반력 결과에 데이터가 없음: {reaction_file}"]

    groups: dict[str, dict[str, int]] = {}
    for index, name in enumerate(header):
        if name == "time" or "_" not in name:
            continue
        label, _, component = name.rpartition("_")
        if component in _REACTION_FORCE + _REACTION_MOMENT:
            groups.setdefault(label, {})[component] = index

    notes: list[str] = []
    if not groups:
        return [], [
            f"{reaction_file.name} 에 반력 성분 열이 없음 — "
            "Setup XML 의 joint_names 가 모델과 맞는지 확인할 것"
        ]

    peaks: list[JointReactionPeak] = []
    for label, columns in sorted(groups.items()):
        force = _peak_magnitude(rows, [columns[c] for c in _REACTION_FORCE if c in columns])
        moment = _peak_magnitude(rows, [columns[c] for c in _REACTION_MOMENT if c in columns])
        if force is None and moment is None:
            notes.append(f"'{label}' 에서 읽을 수 있는 성분이 없음")
            continue
        _, _, expressed_in = label.partition("_in_")
        peaks.append(
            JointReactionPeak(
                label=label,
                peak_force_n=force,
                peak_moment_nm=moment,
                expressed_in=expressed_in,
            )
        )
    return peaks, notes


def _peak_magnitude(rows: list[list[float | None]], columns: list[int]) -> float | None:
    """성분 열들을 벡터로 보고 크기의 최댓값을 구한다.

    한 성분이라도 비면 그 시점은 건너뛴다 — 빠진 성분을 0 으로 두면
    크기가 작게 나와 안전한 쪽으로 틀린다.
    """
    if len(columns) != 3:
        return None
    peak: float | None = None
    for row in rows:
        values = [row[c] for c in columns if c < len(row) and row[c] is not None]
        if len(values) != 3:
            continue
        magnitude = math.sqrt(sum(v * v for v in values))
        peak = magnitude if peak is None else max(peak, magnitude)
    return peak


def summarise(
    outputs: dict[str, Path],
    *,
    quality: dict | None = None,
    metadata: dict | None = None,
    coordinates: list[str] | None = None,
    analysis_model: str | Path | None = None,
) -> ResultSummary:
    """해석 결과 파일들에서 QoI 네 가지를 모은다."""
    summary = ResultSummary(quality=quality or {}, metadata=dict(metadata or {}))

    ranges, notes = coordinate_ranges(outputs["ik_motion"], coordinates)
    summary.range_of_motion = ranges
    summary.notes.extend(notes)

    moments, notes = joint_moments(outputs["id_forces"], coordinates)
    summary.joint_moments = moments
    summary.notes.extend(notes)

    kinds: dict[str, str] | None = None
    if analysis_model is not None and Path(analysis_model).is_file():
        try:
            kinds = classify_actuators(analysis_model)
        except Exception as exc:  # noqa: BLE001 - 분류 실패가 해석을 막지는 않는다
            summary.notes.append(f"모델에서 액추에이터 종류를 읽지 못함: {exc}")

    grouped, notes = actuator_peaks(outputs["so_forces"], kinds)
    summary.muscle_forces = grouped.get("muscle", [])
    summary.device_loads = grouped.get("device", [])
    summary.other_actuators = grouped.get("actuator", [])
    summary.notes.extend(notes)

    reactions, notes = joint_reaction_peaks(outputs["jr_reaction"])
    summary.joint_reactions = reactions
    summary.notes.extend(notes)

    summary.metadata.setdefault(
        "units",
        {
            "length": "m",
            "force": "N",
            "moment": "N*m",
            "angle": ranges[0].unit if ranges else "unknown",
        },
    )
    return summary
