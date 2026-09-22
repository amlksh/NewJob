"""파이프라인 오케스트레이션.

Scale → IK → ID → Static Optimization → Joint Reaction 을 순서대로 돌리고,
각 실행마다 runs/<run_id>/ 에 결과·설정 XML 사본·provenance.json 을 남긴다.
"""

from __future__ import annotations

import logging
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
    run_dir = Path(runs_root) / run_id
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

    outputs = _output_paths(run_dir, case)
    setup_files = _render_all_setups(case, run_dir, outputs)
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
    )


def _render_all_setups(
    case: CaseSpec, run_dir: Path, outputs: dict[str, Path]
) -> dict[str, Path]:
    subs_common = {
        "MODEL_FILE": case.model_file,
        "RUN_DIR": run_dir,
        "MARKER_FILE": case.subject.marker_file,
        "GRF_FILE": case.subject.grf_file or "",
        "STATIC_TRIAL": case.subject.static_trial or "",
        "SUBJECT_MASS": case.subject.mass_kg,
        "SUBJECT_HEIGHT": case.subject.height_m,
        "JR_FRAME": case.joint_reaction_frame,
    }
    subs_by_step = {
        "scale": {"SCALED_MODEL": outputs["scaled_model"]},
        "ik": {
            "SCALED_MODEL": outputs["scaled_model"],
            "IK_MOTION": outputs["ik_motion"],
        },
        "id": {
            "SCALED_MODEL": outputs["scaled_model"],
            "IK_MOTION": outputs["ik_motion"],
            "ID_FORCES": outputs["id_forces"],
        },
        "so": {
            "SCALED_MODEL": outputs["scaled_model"],
            "IK_MOTION": outputs["ik_motion"],
            "SO_ACTIVATION": outputs["so_activation"],
        },
        "jr": {
            "SCALED_MODEL": outputs["scaled_model"],
            "IK_MOTION": outputs["ik_motion"],
            "SO_FORCES": outputs["so_forces"],
            "JR_REACTION": outputs["jr_reaction"],
        },
    }

    rendered: dict[str, Path] = {}
    setup_dir = run_dir / "setup"

    # ID / SO / JR 이 공유하는 ExternalLoads 를 먼저 만든다.
    # 세 Setup XML 이 @RUN_DIR@/setup/external_loads.xml 을 가리키므로 이름이 고정이다.
    external_template = case.templates.get("external_loads")
    if external_template is not None:
        rendered["external_loads"] = steps.render_setup_xml(
            template=external_template,
            substitutions=subs_common,
            destination=setup_dir / "external_loads.xml",
        )

    for step_name in steps.STEP_ORDER:
        rendered[step_name] = steps.render_setup_xml(
            template=case.templates[step_name],
            substitutions={**subs_common, **subs_by_step[step_name]},
            destination=setup_dir / f"{step_name}_setup.xml",
        )
    return rendered


def _output_paths(run_dir: Path, case: CaseSpec) -> dict[str, Path]:
    out = run_dir / "results"
    out.mkdir(parents=True, exist_ok=True)
    return {
        "scaled_model": out / "scaled_model.osim",
        "ik_motion": out / "ik.mot",
        "ik_marker_errors": out / "ik_marker_errors.sto",
        "id_forces": out / "id_forces.sto",
        "so_activation": out / "so_activation.sto",
        "so_forces": out / "so_force.sto",
        "jr_reaction": out / "jr_reaction_loads.sto",
    }


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


def _opt_float(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and value.strip().upper() == "TBD"):
        return None
    return float(value)


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in text).strip("-")
