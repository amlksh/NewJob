"""품질 지표.

결과 수치를 보고할 때 이 지표를 함께 보고한다.
관절반력 값만 떼어 보고하면 그 값이 믿을 만한지 알 수 없다.

임계값(marker RMS, 잔차력 한계)은 문헌 근거로 ADR 에서 정한다.
여기서는 임계값을 하드코딩하지 않고, 설정으로 받아 판정만 한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Thresholds:
    """품질 판정 임계값.

    None 인 항목은 '아직 정해지지 않음' 이며 판정하지 않는다.
    근거 없는 숫자를 기본값으로 박지 않는다 (ADR-0003 참조).
    """

    marker_rms_m: float | None = None
    marker_max_m: float | None = None
    residual_force_n: float | None = None
    residual_moment_nm: float | None = None

    @classmethod
    def undecided(cls) -> Thresholds:
        return cls()


@dataclass
class QualityMetrics:
    """한 번의 해석에 대한 품질 지표."""

    marker_rms_m: float | None = None
    marker_max_m: float | None = None
    marker_max_label: str | None = None
    residual_force_n: float | None = None
    residual_moment_nm: float | None = None
    saturated_muscle_fraction: float | None = None

    verdicts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def judge(self, thresholds: Thresholds) -> QualityMetrics:
        """임계값에 비추어 통과/실패를 기록한다.

        임계값이 없으면 'undecided' 로 남긴다. 조용히 통과시키지 않는다.
        """
        self.verdicts["marker_rms"] = _verdict(self.marker_rms_m, thresholds.marker_rms_m)
        self.verdicts["marker_max"] = _verdict(self.marker_max_m, thresholds.marker_max_m)
        self.verdicts["residual_force"] = _verdict(
            self.residual_force_n, thresholds.residual_force_n
        )
        self.verdicts["residual_moment"] = _verdict(
            self.residual_moment_nm, thresholds.residual_moment_nm
        )
        undecided = [k for k, v in self.verdicts.items() if v == "undecided"]
        if undecided:
            self.notes.append(
                "임계값 미정으로 판정하지 않은 항목: " + ", ".join(undecided)
            )
        return self

    @property
    def passed(self) -> bool | None:
        """모두 통과면 True, 하나라도 실패면 False, 판정 불가면 None."""
        values = set(self.verdicts.values())
        if "fail" in values:
            return False
        if values and values <= {"pass"}:
            return True
        return None

    def as_dict(self) -> dict:
        return {
            "marker_rms_m": self.marker_rms_m,
            "marker_max_m": self.marker_max_m,
            "marker_max_label": self.marker_max_label,
            "residual_force_n": self.residual_force_n,
            "residual_moment_nm": self.residual_moment_nm,
            "saturated_muscle_fraction": self.saturated_muscle_fraction,
            "verdicts": self.verdicts,
            "passed": self.passed,
            "notes": self.notes,
        }


def rms(values: list[float]) -> float | None:
    """제곱평균제곱근. 빈 목록이면 None (0.0 으로 위장하지 않는다)."""
    clean = [v for v in values if v is not None and not math.isnan(v)]
    if not clean:
        return None
    return math.sqrt(sum(v * v for v in clean) / len(clean))


def parse_ik_marker_errors(path: str | Path) -> QualityMetrics:
    """OpenSim IK 가 남기는 marker error STO 파일에서 RMS/최대 오차를 읽는다.

    열 구성: time, marker_error_RMS, marker_error_max, marker_error_max_marker
    (OpenSim 버전에 따라 열 이름이 다르므로 이름으로 찾는다.)
    """
    path = Path(path)
    metrics = QualityMetrics()
    if not path.exists():
        metrics.notes.append(f"IK 마커 오차 파일 없음: {path}")
        return metrics

    header, rows = _read_sto(path)
    if not rows:
        metrics.notes.append(f"IK 마커 오차 파일에 데이터 없음: {path}")
        return metrics

    rms_col = _find_column(header, ("marker_error_RMS", "RMS"))
    max_col = _find_column(header, ("marker_error_max", "max"))

    if rms_col is not None:
        series = [r[rms_col] for r in rows if rms_col < len(r)]
        metrics.marker_rms_m = rms([v for v in series if v is not None])
    else:
        metrics.notes.append("marker_error_RMS 열을 찾지 못함")

    if max_col is not None:
        series = [r[max_col] for r in rows if max_col < len(r)]
        clean = [v for v in series if v is not None]
        metrics.marker_max_m = max(clean) if clean else None
    else:
        metrics.notes.append("marker_error_max 열을 찾지 못함")

    return metrics


def peak_residuals(path: str | Path) -> tuple[float | None, float | None]:
    """Inverse Dynamics 결과에서 잔차력·잔차모멘트의 최댓값을 뽑는다.

    잔차가 크면 모델과 측정 데이터가 역학적으로 맞지 않는다는 뜻이며,
    관절반력 결과를 그대로 믿을 수 없다.
    """
    path = Path(path)
    if not path.exists():
        return None, None

    header, rows = _read_sto(path)
    if not rows:
        return None, None

    force_cols = [
        i
        for i, name in enumerate(header)
        if name.startswith(("pelvis_tx", "pelvis_ty", "pelvis_tz"))
    ]
    moment_cols = [
        i
        for i, name in enumerate(header)
        if name.startswith(("pelvis_tilt", "pelvis_list", "pelvis_rotation"))
    ]

    peak_force = _peak_magnitude(rows, force_cols)
    peak_moment = _peak_magnitude(rows, moment_cols)
    return peak_force, peak_moment


def _peak_magnitude(rows: list[list[float | None]], cols: list[int]) -> float | None:
    if not cols:
        return None
    peak: float | None = None
    for row in rows:
        values = [row[c] for c in cols if c < len(row) and row[c] is not None]
        if len(values) != len(cols):
            continue
        magnitude = math.sqrt(sum(v * v for v in values))
        peak = magnitude if peak is None else max(peak, magnitude)
    return peak


def read_storage(
    path: str | Path,
) -> tuple[dict[str, str], list[str], list[list[float | None]]]:
    """OpenSim STO/MOT 를 (헤더 메타데이터, 열 이름, 데이터) 로 읽는다.

    endheader 앞의 `key=value` 줄이 메타데이터다. 그 중 `inDegrees` 는
    회전값의 단위를 말하므로 결과를 보고할 때 반드시 함께 봐야 한다.
    """
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip().lower() == "endheader")
    except StopIteration:
        return {}, [], []

    metadata: dict[str, str] = {}
    for line in lines[:start]:
        if "=" in line:
            key, _, value = line.partition("=")
            metadata[key.strip()] = value.strip()

    header_line = start + 1
    if header_line >= len(lines):
        return metadata, [], []
    header = [h.strip() for h in lines[header_line].split("\t") if h.strip()]

    rows: list[list[float | None]] = []
    for line in lines[header_line + 1 :]:
        if not line.strip():
            continue
        row: list[float | None] = []
        for cell in line.split("\t"):
            cell = cell.strip()
            try:
                row.append(float(cell))
            except ValueError:
                row.append(None)
        rows.append(row)
    return metadata, header, rows


def _read_sto(path: Path) -> tuple[list[str], list[list[float | None]]]:
    """열 이름과 데이터만 필요할 때."""
    _, header, rows = read_storage(path)
    return header, rows


def _find_column(header: list[str], candidates: tuple[str, ...]) -> int | None:
    for i, name in enumerate(header):
        for candidate in candidates:
            if candidate.lower() in name.lower():
                return i
    return None


def _verdict(value: float | None, threshold: float | None) -> str:
    if value is None or threshold is None:
        return "undecided"
    return "pass" if value <= threshold else "fail"
