"""파이프라인 오케스트레이션.

Scale → IK → ID → Static Optimization → Joint Reaction 을 순서대로 돌리고,
각 실행마다 runs/<run_id>/ 에 결과·설정 XML 사본·provenance.json 을 남긴다.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from msk_engine import __version__, steps
from msk_engine.errors import ConfigurationError
from msk_engine.inputs import (
    SubjectInput,
    ValidationReport,
    validate_grf_sync,
    validate_subject,
    validate_trc,
)
from msk_engine.provenance import Provenance
from msk_engine.quality import (
    QualityMetrics,
    Thresholds,
    parse_ik_marker_errors,
    peak_residuals,
)

log = logging.getLogger(__name__)


@dataclass
class CaseSpec:
    """Case 정의 (configs/cases/*.yaml)."""

    name: str
    subject: SubjectInput
    model_file: Path
    templates: dict[str, Path]
    thresholds: Thresholds = field(default_factory=Thresholds.undecided)
    required_markers: list[str] = field(default_factory=list)
    joint_reaction_frame: str = "tibia"
    # 해석 구간. 생략하면 마커 파일 전체 구간을 쓴다 (임의의 값을 넣지 않는다).
    time_range: tuple[float, float] | None = None
    static_time_range: tuple[float, float] | None = None
    notes: str = ""

    @classmethod
    def from_yaml(cls, path: str | Path) -> CaseSpec:
        path = Path(path)
        if not path.exists():
            raise ConfigurationError(f"Case 파일 없음: {path}")
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        base = path.parent

        try:
            subject_raw = raw["subject"]
            templates_raw = raw["templates"]
            model_file = raw["model_file"]
            name = raw["name"]
        except KeyError as exc:
            raise ConfigurationError(f"{path.name} 에 필수 항목 누락: {exc}") from exc

        subject = SubjectInput(
            height_m=float(subject_raw["height_m"]),
            mass_kg=float(subject_raw["mass_kg"]),
            marker_file=_resolve(base, subject_raw["marker_file"]),
            grf_file=_resolve_optional(base, subject_raw.get("grf_file")),
            static_trial=_resolve_optional(base, subject_raw.get("static_trial")),
        )

        thresholds_raw = raw.get("thresholds") or {}
        thresholds = Thresholds(
            marker_rms_m=_opt_float(thresholds_raw.get("marker_rms_m")),
            marker_max_m=_opt_float(thresholds_raw.get("marker_max_m")),
            residual_force_n=_opt_float(thresholds_raw.get("residual_force_n")),
            residual_moment_nm=_opt_float(thresholds_raw.get("residual_moment_nm")),
        )

        return cls(
            name=name,
            subject=subject,
            model_file=_resolve(base, model_file),
            templates={k: _resolve(base, v) for k, v in templates_raw.items()},
            thresholds=thresholds,
            required_markers=list(raw.get("required_markers") or []),
            joint_reaction_frame=raw.get("joint_reaction_frame", "tibia"),
            time_range=_opt_range(raw.get("time_range"), "time_range", path.name),
            static_time_range=_opt_range(
                raw.get("static_time_range"), "static_time_range", path.name
            ),
            notes=raw.get("notes", ""),
        )


@dataclass
class PipelineResult:
    run_id: str
    run_dir: Path
    status: str
    validation: ValidationReport
    quality: QualityMetrics
    provenance_path: Path | None = None
    steps: list[steps.StepResult] = field(default_factory=list)
    # 단계별 출력 경로. 분석 결과 이름은 OpenSim 이 정하므로 호출자가
    # 직접 조립하지 말고 이 값을 쓴다.
    outputs: dict[str, Path] = field(default_factory=dict)


def new_run_id(case_name: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{_slug(case_name)}_{uuid.uuid4().hex[:6]}"


def validate_case(case: CaseSpec) -> ValidationReport:
    """해석 전 입력 검증. 오류가 있으면 해석을 시작하지 않는다."""
    report = ValidationReport()
    report.merge(validate_subject(case.subject), prefix="subject")

    if case.subject.marker_file.suffix.lower() == ".trc":
        marker_report = validate_trc(
            case.subject.marker_file, required_markers=case.required_markers
        )
        report.merge(marker_report, prefix="markers")

        if case.subject.grf_file is not None:
            marker_range = marker_report.facts.get("time_range")
            grf_range = _sto_time_range(case.subject.grf_file)
            report.merge(
                validate_grf_sync(
                    grf_time_range=grf_range,
                    marker_time_range=tuple(marker_range) if marker_range else None,
                ),
                prefix="sync",
            )
    else:
        report.warnings.append(
            f"{case.subject.marker_file.suffix} 입력은 OpenSim 리더로 처리되며 "
            "여기서 사전 검증하지 않음"
        )

    if not case.model_file.exists():
        report.errors.append(f"모델 파일 없음: {case.model_file}")

    for step_name in steps.STEP_ORDER:
        if step_name not in case.templates:
            report.errors.append(f"Setup XML 템플릿 누락: {step_name}")
        elif not case.templates[step_name].exists():
            report.errors.append(
                f"Setup XML 템플릿 파일 없음: {case.templates[step_name]}"
            )

    external = case.templates.get("external_loads")
    if case.subject.grf_file is not None:
        if external is None:
            report.errors.append(
                "GRF 파일은 있으나 external_loads 템플릿이 없음 "
                "— ID/SO/JR 이 GRF 없이 돌게 된다"
            )
        elif not external.exists():
            report.errors.append(f"external_loads 템플릿 파일 없음: {external}")

    return report


def run_case(
    case: CaseSpec,
    runs_root: str | Path = "runs",
    repo_root: str | Path | None = None,
    dry_run: bool = False,
) -> PipelineResult:
    """Case 하나를 끝까지 실행한다.

    dry_run=True 면 검증과 Setup XML 생성까지만 하고 OpenSim 을 부르지 않는다.
    OpenSim 없는 환경에서 설정을 점검할 때 쓴다.
    """
    run_id = new_run_id(case.name)
    # 절대경로여야 한다. OpenSim 은 Setup XML 을 읽을 때 그 파일이 있는
    # 디렉터리로 작업 디렉터리를 옮기므로, 상대경로로 적힌 출력 파일은
    # setup/ 밑의 없는 경로를 가리키게 되고 도구는 성공을 반환하면서
    # 아무것도 쓰지 않는다 (OpenSim 4.6 실측 확인).
    run_dir = (Path(runs_root) / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    prov = Provenance.start(
        run_id=run_id,
        case_name=case.name,
        engine_version=__version__,
        repo_root=repo_root,
    )
    prov.joint_reaction_frame = case.joint_reaction_frame
    prov.model_file = str(case.model_file)

    validation = validate_case(case)
    _write_validation(run_dir, validation)

    if not validation.ok:
        prov.finish("failed_validation")
        provenance_path = prov.write(run_dir)
        log.error("입력 검증 실패 — 해석을 시작하지 않음 (%s)", run_dir)
        return PipelineResult(
            run_id=run_id,
            run_dir=run_dir,
            status="failed_validation",
            validation=validation,
            quality=QualityMetrics(),
            provenance_path=provenance_path,
        )

    for label, path in _input_files(case).items():
        prov.record_input(label, path)

    time_range = _resolve_time_range(case, validation)
    static_time_range = _resolve_static_time_range(case, time_range)
    chosen = _chosen_output_paths(run_dir)
    setup_files = _render_all_setups(
        case, run_dir, chosen, time_range, static_time_range
    )
    outputs = _all_output_paths(run_dir, chosen, setup_files)
    prov.analysis_time_range = [time_range[0], time_range[1]]
    prov.setup_xml_copies = [
        str(steps.archive_setup_xml(p, run_dir)) for p in setup_files.values()
    ]

    if dry_run:
        prov.finish("dry_run")
        provenance_path = prov.write(run_dir)
        log.info("dry-run 완료 — Setup XML 생성까지만 수행 (%s)", run_dir)
        return PipelineResult(
            run_id=run_id,
            run_dir=run_dir,
            status="dry_run",
            validation=validation,
            quality=QualityMetrics(),
            provenance_path=provenance_path,
            outputs=outputs,
        )

    results: list[steps.StepResult] = []
    runners = {
        "scale": lambda: steps.run_scale(
            setup_files["scale"], run_dir, outputs["scaled_model"]
        ),
        "ik": lambda: steps.run_ik(setup_files["ik"], run_dir, outputs["ik_motion"]),
        "id": lambda: steps.run_id(setup_files["id"], run_dir, outputs["id_forces"]),
        "so": lambda: steps.run_static_optimization(
            setup_files["so"], run_dir, outputs["so_activation"]
        ),
        "jr": lambda: steps.run_joint_reaction(
            setup_files["jr"], run_dir, outputs["jr_reaction"]
        ),
    }

    try:
        for step_name in steps.STEP_ORDER:
            log.info("[%s] 실행", step_name)
            result = runners[step_name]()
            results.append(result)
            prov.record_step(
                name=result.name,
                status=result.status,
                duration_s=result.duration_s,
                outputs=[str(p) for p in result.outputs],
                metrics=result.metrics,
            )
    except Exception:
        prov.finish("failed")
        prov.write(run_dir)
        raise

    quality = _collect_quality(outputs, case.thresholds)
    prov.record_step("quality", "ok", metrics=quality.as_dict())
    prov.finish("ok")
    provenance_path = prov.write(run_dir)

    return PipelineResult(
        run_id=run_id,
        run_dir=run_dir,
        status="ok",
        validation=validation,
        quality=quality,
        provenance_path=provenance_path,
        steps=results,
        outputs=outputs,
    )


def _render_all_setups(
    case: CaseSpec,
    run_dir: Path,
    chosen: dict[str, Path],
    time_range: tuple[float, float],
    static_time_range: tuple[float, float],
) -> dict[str, Path]:
    """템플릿을 치환해 run 디렉터리에 Setup XML 을 쓴다.

    렌더 순서가 중요하다. JR 이 참조하는 근육력 파일 이름은 SO 의 Setup XML 이
    정해야 알 수 있으므로, SO 를 먼저 렌더하고 그 결과에서 경로를 유도한다.
    STEP_ORDER 가 so → jr 순이라 순회 순서만 지키면 된다.
    """
    setup_dir = run_dir / "setup"
    results_dir = run_dir / "results"

    # ID / SO / JR 이 공유하는 ExternalLoads. GRF 가 없으면 만들지 않고,
    # 세 Setup XML 에는 Unassigned 를 넣는다 — 없는 파일을 가리키면
    # 도구가 파일 열기에 실패한다.
    external_template = case.templates.get("external_loads")
    use_external = external_template is not None and case.subject.grf_file is not None
    external_path: Path | None = setup_dir / "external_loads.xml" if use_external else None

    subs_common = {
        "MODEL_FILE": case.model_file,
        "RUN_DIR": run_dir,
        "MARKER_FILE": case.subject.marker_file,
        "GRF_FILE": case.subject.grf_file or "",
        "STATIC_TRIAL": case.subject.static_trial or "",
        "SUBJECT_MASS": case.subject.mass_kg,
        "SUBJECT_HEIGHT": case.subject.height_m,
        "JR_FRAME": case.joint_reaction_frame,
        "TIME_START": _fmt_time(time_range[0]),
        "TIME_END": _fmt_time(time_range[1]),
        "STATIC_TIME_START": _fmt_time(static_time_range[0]),
        "STATIC_TIME_END": _fmt_time(static_time_range[1]),
        "EXTERNAL_LOADS": external_path if external_path is not None else "Unassigned",
    }

    rendered: dict[str, Path] = {}
    if external_path is not None:
        rendered["external_loads"] = steps.render_setup_xml(
            template=external_template,
            substitutions=subs_common,
            destination=external_path,
        )

    for step_name in steps.STEP_ORDER:
        subs = {**subs_common, **_step_substitutions(step_name, chosen, rendered, results_dir)}
        if step_name == "scale":
            subs = _relativise_for_scale(subs, setup_dir)
        rendered[step_name] = steps.render_setup_xml(
            template=case.templates[step_name],
            substitutions=subs,
            destination=setup_dir / f"{step_name}_setup.xml",
        )
    return rendered


def _relativise_for_scale(subs: dict[str, object], setup_dir: Path) -> dict[str, object]:
    """ScaleTool 이 쓰는 경로만 Setup XML 디렉터리 기준 상대경로로 바꾼다.

    ScaleTool 은 다른 도구와 달리 파일 이름 앞에 Setup XML 의 디렉터리를
    그대로 이어 붙인다. 절대경로를 주면 `<setup 디렉터리>/<절대경로>` 가 되어
    파일을 못 연다 (OpenSim 4.6 실측 확인).

    GUI 로 같은 XML 을 돌려도 같은 파일을 가리키도록, 작업 디렉터리가 아니라
    Setup XML 위치를 기준으로 삼는다 (CLAUDE.md §2 코드 검증).
    """
    relativised = dict(subs)
    for key in ("MODEL_FILE", "STATIC_TRIAL", "SCALED_MODEL", "RUN_DIR"):
        value = subs.get(key)
        if value in (None, "", "Unassigned"):
            continue
        relativised[key] = _relative_to(Path(str(value)), setup_dir)
    return relativised


def _relative_to(target: Path, base: Path) -> str:
    """base 기준 상대경로. 같은 드라이브가 아니면 멈춘다."""
    try:
        return os.path.relpath(target, base)
    except ValueError as exc:  # Windows 에서 드라이브가 다른 경우
        raise ConfigurationError(
            f"ScaleTool 설정 경로를 상대경로로 만들 수 없음: {target} (기준 {base}). "
            "입력 파일과 runs 디렉터리를 같은 드라이브에 둘 것"
        ) from exc


def _step_substitutions(
    step_name: str,
    chosen: dict[str, Path],
    rendered: dict[str, Path],
    results_dir: Path,
) -> dict[str, object]:
    """단계별 추가 치환 값."""
    if step_name == "scale":
        return {"SCALED_MODEL": chosen["scaled_model"]}
    if step_name == "ik":
        return {"SCALED_MODEL": chosen["scaled_model"], "IK_MOTION": chosen["ik_motion"]}
    if step_name == "id":
        return {
            "SCALED_MODEL": chosen["scaled_model"],
            "IK_MOTION": chosen["ik_motion"],
            "ID_FORCES": chosen["id_forces"],
        }
    if step_name == "so":
        return {"SCALED_MODEL": chosen["scaled_model"], "IK_MOTION": chosen["ik_motion"]}
    if step_name == "jr":
        # 근육력 파일 이름은 SO 의 Setup XML 이 정한다. 파이프라인이 임의로
        # 정할 수 없으므로 렌더된 so_setup.xml 에서 유도한다.
        return {
            "SCALED_MODEL": chosen["scaled_model"],
            "IK_MOTION": chosen["ik_motion"],
            "SO_FORCES": steps.analysis_output_path(rendered["so"], results_dir, "force"),
        }
    raise ConfigurationError(f"알 수 없는 단계: {step_name}")


def _chosen_output_paths(run_dir: Path) -> dict[str, Path]:
    """파이프라인이 이름을 정하는 출력. Setup XML 에 그대로 써 넣는다."""
    out = run_dir / "results"
    out.mkdir(parents=True, exist_ok=True)
    return {
        "scaled_model": out / "scaled_model.osim",
        "ik_motion": out / "ik.mot",
        "id_forces": out / "id_forces.sto",
    }


def _all_output_paths(
    run_dir: Path, chosen: dict[str, Path], setup_files: dict[str, Path]
) -> dict[str, Path]:
    """파이프라인이 정한 출력 + OpenSim 이 이름을 정하는 출력.

    분석(Analysis) 결과와 IK 마커 오차 파일의 이름은 설정으로 바꿀 수 없다.
    렌더된 Setup XML 의 도구·분석 이름에서 유도해야 실제 파일과 일치한다.
    """
    out = run_dir / "results"
    return {
        **chosen,
        "ik_marker_errors": steps.ik_marker_error_path(setup_files["ik"], out),
        "so_activation": steps.analysis_output_path(setup_files["so"], out, "activation"),
        "so_forces": steps.analysis_output_path(setup_files["so"], out, "force"),
        "jr_reaction": steps.analysis_output_path(
            setup_files["jr"], out, "ReactionLoads"
        ),
    }


def _resolve_time_range(case: CaseSpec, validation: ValidationReport) -> tuple[float, float]:
    """해석 구간을 정한다. Case 에 없으면 마커 파일 전체 구간을 쓴다.

    둘 다 없으면 멈춘다. 0 0 같은 값을 채우면 도구가 한 프레임만 풀고도
    성공을 반환하므로, 조용히 잘못된 결과가 나온다.
    """
    if case.time_range is not None:
        return case.time_range
    fact = validation.facts.get("markers.time_range")
    if fact and len(fact) == 2:
        return float(fact[0]), float(fact[1])
    raise ConfigurationError(
        "해석 구간을 정할 수 없음 — Case 에 time_range 를 적거나, "
        "시간 정보를 읽을 수 있는 마커 파일(.trc)을 쓸 것"
    )


def _resolve_static_time_range(
    case: CaseSpec, fallback: tuple[float, float]
) -> tuple[float, float]:
    """Scaling 에 쓸 정적 trial 구간. 정적 trial 이 없으면 fallback 을 쓴다.

    정적 trial 이 없으면 ScaleTool 은 어차피 마커 파일 없이 실패하므로,
    이 값은 그 경우 쓰이지 않는다.
    """
    if case.static_time_range is not None:
        return case.static_time_range
    static = case.subject.static_trial
    if static is not None and static.suffix.lower() == ".trc":
        facts = validate_trc(static).facts
        fact = facts.get("time_range")
        if fact and len(fact) == 2:
            return float(fact[0]), float(fact[1])
    return fallback


def _fmt_time(value: float) -> str:
    """Setup XML 에 넣을 시간 문자열. 지수 표기를 피한다."""
    return f"{float(value):.6f}"


def _collect_quality(outputs: dict[str, Path], thresholds: Thresholds) -> QualityMetrics:
    metrics = parse_ik_marker_errors(outputs["ik_marker_errors"])
    force, moment = peak_residuals(outputs["id_forces"])
    metrics.residual_force_n = force
    metrics.residual_moment_nm = moment
    return metrics.judge(thresholds)


def _input_files(case: CaseSpec) -> dict[str, Path]:
    files = {"model": case.model_file, "markers": case.subject.marker_file}
    if case.subject.grf_file is not None:
        files["grf"] = case.subject.grf_file
    if case.subject.static_trial is not None:
        files["static_trial"] = case.subject.static_trial
    return {k: v for k, v in files.items() if v.exists()}


def _write_validation(run_dir: Path, report: ValidationReport) -> Path:
    import json

    target = run_dir / "validation.json"
    target.write_text(
        json.dumps(
            {
                "ok": report.ok,
                "errors": report.errors,
                "warnings": report.warnings,
                "facts": report.facts,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return target


def _sto_time_range(path: Path) -> tuple[float, float] | None:
    from msk_engine.quality import _read_sto  # noqa: PLC0415

    if not path.exists() or path.suffix.lower() not in {".mot", ".sto"}:
        return None
    _, rows = _read_sto(path)
    times = [r[0] for r in rows if r and r[0] is not None]
    if not times:
        return None
    return times[0], times[-1]


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def _resolve_optional(base: Path, value: str | None) -> Path | None:
    return _resolve(base, value) if value else None


def _opt_range(value: Any, key: str, where: str) -> tuple[float, float] | None:
    """[start, end] 형식의 선택 항목을 읽는다."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ConfigurationError(f"{where} 의 {key} 는 [start, end] 형식이어야 함: {value!r}")
    start, end = float(value[0]), float(value[1])
    if end <= start:
        raise ConfigurationError(
            f"{where} 의 {key} 끝 시각({end})이 시작 시각({start})보다 커야 함"
        )
    return start, end


def _opt_float(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and value.strip().upper() == "TBD"):
        return None
    return float(value)


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in text).strip("-")
