"""입력 검증.

해석 전에 막는 것이 해석 후에 원인을 추적하는 것보다 싸다.
검증 결과는 결과와 함께 보고한다 — 통과했다는 사실도 기록이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from msk_engine.errors import InputValidationError

# TRC 마커 좌표가 m 단위인지 mm 단위인지 판별하는 경계.
# 사람 키 범위(~2 m)를 크게 넘는 값이 나오면 mm 로 본다.
_MM_THRESHOLD_M = 10.0

# TRC 표준 헤더 배치 (0-based)
#   0: PathFileType ...
#   1: DataRate CameraRate NumFrames NumMarkers Units ...
#   2: 위 항목의 값
#   3: Frame#  Time  <마커명들>
#   4: 축 라벨 (X1 Y1 Z1 ...)
#   5+: 데이터
_TRC_META_KEY_ROW = 1
_TRC_META_VAL_ROW = 2
_TRC_MARKER_ROW = 3
_TRC_DATA_START = 5

SUPPORTED_MARKER_SUFFIXES = {".trc", ".c3d"}
SUPPORTED_GRF_SUFFIXES = {".mot", ".sto", ".c3d"}


@dataclass
class ValidationReport:
    """검증 결과. errors 가 비어 있어야 해석을 시작한다."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    facts: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_failed(self) -> None:
        if not self.ok:
            raise InputValidationError("입력 검증 실패", self.errors)

    def merge(self, other: ValidationReport, prefix: str = "") -> ValidationReport:
        """다른 보고서를 흡수한다. prefix 로 출처를 남긴다."""
        tag = f"[{prefix}] " if prefix else ""
        self.errors.extend(f"{tag}{e}" for e in other.errors)
        self.warnings.extend(f"{tag}{w}" for w in other.warnings)
        for key, value in other.facts.items():
            self.facts[f"{prefix}.{key}" if prefix else key] = value
        return self


@dataclass
class SubjectInput:
    """가상환자 1명분 입력."""

    height_m: float
    mass_kg: float
    marker_file: Path
    grf_file: Path | None = None
    static_trial: Path | None = None

    def __post_init__(self) -> None:
        self.marker_file = Path(self.marker_file)
        if self.grf_file is not None:
            self.grf_file = Path(self.grf_file)
        if self.static_trial is not None:
            self.static_trial = Path(self.static_trial)


def validate_subject(subject: SubjectInput) -> ValidationReport:
    """신장·체중과 파일 존재·형식을 확인한다.

    생리학적으로 불가능한 값은 오류로, 드문 값은 경고로 둔다.
    판단을 대신 내리지 않고 사용자가 확인하게 한다.
    """
    report = ValidationReport()

    if not (0.5 <= subject.height_m <= 2.5):
        report.errors.append(
            f"신장 {subject.height_m} m 는 허용 범위(0.5–2.5 m)를 벗어남. 단위가 cm 인지 확인할 것"
        )
    elif not (1.4 <= subject.height_m <= 2.1):
        report.warnings.append(f"신장 {subject.height_m} m 는 성인 표준 범위 밖")

    if not (10.0 <= subject.mass_kg <= 250.0):
        report.errors.append(f"체중 {subject.mass_kg} kg 는 허용 범위(10–250 kg)를 벗어남")

    _check_file(report, subject.marker_file, "마커 파일", SUPPORTED_MARKER_SUFFIXES)
    if subject.grf_file is not None:
        _check_file(report, subject.grf_file, "GRF 파일", SUPPORTED_GRF_SUFFIXES)
    else:
        report.warnings.append(
            "GRF 파일 없음 — Inverse Dynamics 와 Joint Reaction 결과를 신뢰할 수 없음"
        )
    if subject.static_trial is not None:
        _check_file(report, subject.static_trial, "정적 trial", SUPPORTED_MARKER_SUFFIXES)
    else:
        report.warnings.append("정적 trial 없음 — Scaling 정확도가 떨어짐")

    report.facts["height_m"] = subject.height_m
    report.facts["mass_kg"] = subject.mass_kg
    return report


def validate_trc(
    path: str | Path,
    required_markers: list[str] | None = None,
    max_missing_fraction: float = 0.1,
) -> ValidationReport:
    """TRC 마커 파일의 헤더·단위·결측을 확인한다.

    C3D 는 OpenSim 쪽 리더를 쓰므로 여기서 다루지 않는다.
    """
    path = Path(path)
    report = ValidationReport()

    if not path.exists():
        report.errors.append(f"마커 파일 없음: {path}")
        return report

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) <= _TRC_DATA_START:
        report.errors.append(f"TRC 파일이 너무 짧음 ({len(lines)}행) — 헤더가 불완전")
        return report

    # strict=False 의도: 키/값 개수가 안 맞는 헤더는 예외로 터뜨리지 않고
    # 아래 Units 검사에서 '항목 없음' 오류로 보고한다.
    meta = dict(
        zip(
            (k.strip() for k in lines[_TRC_META_KEY_ROW].split("\t")),
            (v.strip() for v in lines[_TRC_META_VAL_ROW].split("\t")),
            strict=False,
        )
    )

    units = meta.get("Units")
    if units:
        report.facts["declared_units"] = units
        if units not in {"m", "mm"}:
            report.warnings.append(f"선언된 단위 '{units}' 를 해석할 수 없음")
    else:
        report.errors.append("TRC 헤더에 Units 항목이 없음 — 단위를 추정하지 않는다")

    marker_names = [
        name.strip()
        for name in lines[_TRC_MARKER_ROW].split("\t")
        if name.strip() and name.strip() not in {"Frame#", "Time"}
    ]
    report.facts["marker_count"] = len(marker_names)
    report.facts["markers"] = marker_names

    if required_markers:
        missing_markers = [m for m in required_markers if m not in marker_names]
        if missing_markers:
            report.errors.append(
                f"모델이 요구하는 마커 누락: {', '.join(missing_markers)} "
                "— 마커명 매핑을 먼저 정의할 것"
            )

    data_rows = [ln for ln in lines[_TRC_DATA_START:] if ln.strip()]
    report.facts["frame_count"] = len(data_rows)
    if not data_rows:
        report.errors.append("데이터 행이 없음")
        return report

    total = 0
    missing = 0
    max_abs = 0.0
    for row in data_rows:
        for cell in row.split("\t")[2:]:  # Frame#, Time 제외
            cell = cell.strip()
            total += 1
            if not cell:
                missing += 1
                continue
            try:
                value = abs(float(cell))
            except ValueError:
                missing += 1
                continue
            max_abs = max(max_abs, value)

    fraction = missing / total if total else 1.0
    report.facts["missing_fraction"] = round(fraction, 4)
    report.facts["max_abs_coordinate"] = max_abs
    if fraction > max_missing_fraction:
        report.errors.append(
            f"마커 결측 비율 {fraction:.1%} 이 허용치 {max_missing_fraction:.0%} 초과 "
            "— 임의 보간으로 메우지 않는다"
        )
    elif missing:
        report.warnings.append(f"마커 결측 {fraction:.1%} — 해당 구간을 결과에 표시할 것")

    inferred = "mm" if max_abs > _MM_THRESHOLD_M else "m"
    report.facts["inferred_units"] = inferred
    if units in {"m", "mm"} and units != inferred:
        report.errors.append(
            f"선언된 단위 '{units}' 와 데이터 크기로 추정한 단위 '{inferred}' 가 불일치 "
            f"(최대 좌표 절댓값 {max_abs:.3g})"
        )

    times = _column(data_rows, index=1)
    if times:
        report.facts["time_range"] = [times[0], times[-1]]

    return report


def validate_grf_sync(
    grf_time_range: tuple[float, float] | None,
    marker_time_range: tuple[float, float] | None,
    tolerance_s: float = 0.02,
) -> ValidationReport:
    """마커와 GRF 의 시간축이 겹치는지 확인한다."""
    report = ValidationReport()
    if grf_time_range is None or marker_time_range is None:
        report.warnings.append("시간 범위를 확인할 수 없어 GRF 동기화 검증을 건너뜀")
        return report

    g0, g1 = grf_time_range
    m0, m1 = marker_time_range
    report.facts["grf_time_range"] = [g0, g1]
    report.facts["marker_time_range"] = [m0, m1]

    if g1 < m0 - tolerance_s or g0 > m1 + tolerance_s:
        report.errors.append(
            f"GRF({g0:.3f}–{g1:.3f}s) 와 마커({m0:.3f}–{m1:.3f}s) 시간축이 겹치지 않음"
        )
        return report

    if abs(g0 - m0) > tolerance_s or abs(g1 - m1) > tolerance_s:
        report.warnings.append(
            f"GRF 와 마커 시간 범위 차이가 {tolerance_s}s 를 초과 — 겹치는 구간만 해석됨"
        )
    return report


def _column(rows: list[str], index: int) -> list[float]:
    values: list[float] = []
    for row in rows:
        parts = row.split("\t")
        if len(parts) <= index:
            continue
        try:
            values.append(float(parts[index].strip()))
        except ValueError:
            continue
    return values


def _check_file(
    report: ValidationReport, path: Path, label: str, suffixes: set[str]
) -> None:
    if not path.exists():
        report.errors.append(f"{label} 없음: {path}")
        return
    if path.suffix.lower() not in suffixes:
        report.errors.append(
            f"{label} 확장자 '{path.suffix}' 미지원 (지원: {', '.join(sorted(suffixes))})"
        )
    elif path.stat().st_size == 0:
        report.errors.append(f"{label} 이 비어 있음: {path}")
