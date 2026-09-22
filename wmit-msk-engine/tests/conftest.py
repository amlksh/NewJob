from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def trc_factory(tmp_path):
    """TRC 파일을 만들어 주는 팩토리.

    표준 TRC 헤더 배치를 따른다:
      0 PathFileType / 1 메타 키 / 2 메타 값 / 3 마커명 / 4 축 라벨 / 5+ 데이터
    """

    def _make(
        name: str = "trial.trc",
        markers: list[str] | None = None,
        units: str | None = "m",
        frames: int = 10,
        scale: float = 1.0,
        missing_at: set[tuple[int, int]] | None = None,
    ) -> Path:
        markers = markers or ["RASI", "LASI", "RKNE"]
        missing_at = missing_at or set()

        meta_keys = [
            "DataRate",
            "CameraRate",
            "NumFrames",
            "NumMarkers",
            "Units",
            "OrigDataRate",
            "OrigDataStartFrame",
            "OrigNumFrames",
        ]
        meta_vals = [
            "100.0",
            "100.0",
            str(frames),
            str(len(markers)),
            units if units is not None else "",
            "100.0",
            "1",
            str(frames),
        ]
        if units is None:
            meta_keys.remove("Units")
            meta_vals.pop(4)

        lines = [
            f"PathFileType\t4\t(X/Y/Z)\t{name}",
            "\t".join(meta_keys),
            "\t".join(meta_vals),
            "Frame#\tTime\t" + "\t\t\t".join(markers),
            "\t\t"
            + "\t".join(
                f"X{i + 1}\tY{i + 1}\tZ{i + 1}" for i in range(len(markers))
            ),
        ]

        for frame in range(frames):
            cells = [str(frame + 1), f"{frame / 100:.4f}"]
            for m_index in range(len(markers)):
                for axis in range(3):
                    if (frame, m_index * 3 + axis) in missing_at:
                        cells.append("")
                    else:
                        value = (0.1 * (m_index + 1) + 0.01 * axis) * scale
                        cells.append(f"{value:.6f}")
            lines.append("\t".join(cells))

        path = tmp_path / name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return _make


@pytest.fixture
def sto_factory(tmp_path):
    """OpenSim STO 파일 팩토리."""

    def _make(name: str, columns: list[str], rows: list[list[float]]) -> Path:
        lines = [
            name,
            "version=1",
            f"nRows={len(rows)}",
            f"nColumns={len(columns)}",
            "inDegrees=yes",
            "endheader",
            "\t".join(columns),
        ]
        for row in rows:
            lines.append("\t".join(f"{v:.6f}" for v in row))
        path = tmp_path / name
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return _make
