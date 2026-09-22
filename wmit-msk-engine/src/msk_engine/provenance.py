"""재현성 기록.

모든 해석 실행은 runs/<run_id>/provenance.json 을 남긴다.
V&V 추적성 요건이므로 선택 사항이 아니다.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

PROVENANCE_FILENAME = "provenance.json"


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """파일의 SHA-256. 큰 모션 파일도 메모리에 다 올리지 않는다."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def opensim_version() -> str | None:
    """설치된 OpenSim 버전. 미설치면 None."""
    try:
        import opensim  # noqa: PLC0415
    except ImportError:
        return None
    return getattr(opensim, "__version__", None) or getattr(
        opensim, "GetVersion", lambda: None
    )()


def git_commit(repo_root: str | Path | None = None) -> str | None:
    """현재 커밋 해시. git 저장소가 아니면 None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root) if repo_root else None,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def git_dirty(repo_root: str | Path | None = None) -> bool | None:
    """커밋되지 않은 변경이 있는지. 해석 결과의 재현 가능 여부에 영향을 준다."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root) if repo_root else None,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return bool(out.stdout.strip())


@dataclass
class Provenance:
    """한 번의 해석 실행에 대한 재현성 기록."""

    run_id: str
    case_name: str
    started_at: str
    finished_at: str | None = None
    status: str = "running"

    engine_version: str = ""
    opensim_version: str | None = None
    python_version: str = field(default_factory=lambda: sys.version.split()[0])
    platform: str = field(default_factory=platform.platform)

    git_commit: str | None = None
    git_dirty: bool | None = None

    model_file: str | None = None
    input_hashes: dict[str, str] = field(default_factory=dict)
    setup_xml_copies: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)

    # 결과 좌표계·단위를 명시한다. 나중에 FE 경계조건으로 넘길 때 필요하다.
    joint_reaction_frame: str = "tibia"
    length_unit: str = "m"
    force_unit: str = "N"

    @classmethod
    def start(
        cls,
        run_id: str,
        case_name: str,
        engine_version: str,
        repo_root: str | Path | None = None,
    ) -> Provenance:
        return cls(
            run_id=run_id,
            case_name=case_name,
            started_at=_now(),
            engine_version=engine_version,
            opensim_version=opensim_version(),
            git_commit=git_commit(repo_root),
            git_dirty=git_dirty(repo_root),
        )

    def record_input(self, label: str, path: str | Path) -> None:
        self.input_hashes[label] = sha256_file(path)

    def record_step(
        self,
        name: str,
        status: str,
        duration_s: float | None = None,
        outputs: list[str] | None = None,
        metrics: dict | None = None,
    ) -> None:
        self.steps.append(
            {
                "name": name,
                "status": status,
                "duration_s": duration_s,
                "outputs": outputs or [],
                "metrics": metrics or {},
            }
        )

    def finish(self, status: str) -> None:
        self.status = status
        self.finished_at = _now()

    def write(self, run_dir: str | Path) -> Path:
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        target = run_dir / PROVENANCE_FILENAME
        target.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return target


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
