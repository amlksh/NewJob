"""OpenSim 을 실제로 부르는 통합 테스트.

목적은 해석 정확도가 아니라 **파이프라인과 OpenSim 사이의 계약**을 지키는 것이다.
아래 네 가지는 코드만 읽어서는 확인할 수 없고, 틀리면 조용히 잘못된 결과가 나온다.

  1. Setup XML 의 경로가 절대경로여야 한다.
     OpenSim 은 Setup XML 이 있는 디렉터리로 작업 디렉터리를 옮기므로,
     상대경로 출력은 도구가 성공을 반환하면서도 파일이 만들어지지 않는다.
  2. 해석 구간이 치환되어야 한다. 0 0 이면 한 프레임만 풀린다.
  3. 분석(Analysis) 결과 파일 이름은 OpenSim 이 정한다.
     <도구이름>_<분석이름>_<항목>.sto 로 유도하지 않으면 기대 경로가 빗나간다.
  4. GRF 가 없을 때 external_loads_file 은 Unassigned 여야 한다.
     없는 파일을 가리키면 도구가 파일 열기에 실패한다.

Scaling 은 MeasurementSet 을 모델·마커셋에 맞춰 채워야 돌아가므로 여기서 다루지
않는다. 대신 이미 스케일된 모델이 있는 상태에서 IK → ID → SO → JR 을 확인한다.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import toy_model
from msk_engine import steps
from msk_engine.pipeline import CaseSpec, run_case
from msk_engine.quality import parse_ik_marker_errors

pytestmark = pytest.mark.opensim

FRAMES = toy_model.FRAMES
RATE = toy_model.RATE

@pytest.fixture
def toy_case(tmp_path, repo_root):
    """토이 모델 + 마커 파일 + 저장소 템플릿을 쓰는 Case."""
    model_path = tmp_path / "toy.osim"
    model, state = toy_model.build_model(model_path)
    trc = tmp_path / "gait.trc"
    toy_model.write_markers(trc, model, state)

    case_file = toy_model.write_case_yaml(
        tmp_path / "case.yaml", model_path, trc, repo_root / "configs" / "templates"
    )
    return CaseSpec.from_yaml(case_file), model_path


def _rendered_run(case, model_path, runs_root: Path):
    """Setup XML 만 렌더하고, 스케일된 모델 자리에 토이 모델을 놓는다."""
    result = run_case(case, runs_root=runs_root, dry_run=True)
    assert result.status == "dry_run"
    shutil.copy2(model_path, result.outputs["scaled_model"])
    return result


class TestSetupRendering:
    def test_paths_are_absolute(self, toy_case, tmp_path):
        """상대경로로 렌더되면 OpenSim 이 작업 디렉터리를 옮긴 뒤 출력을 못 쓴다."""
        case, model_path = toy_case
        result = _rendered_run(case, model_path, tmp_path / "runs")
        text = (result.run_dir / "setup" / "ik_setup.xml").read_text(encoding="utf-8")
        for tag in ("model_file", "results_directory", "output_motion_file"):
            value = text.split(f"<{tag}>")[1].split(f"</{tag}>")[0].strip()
            assert Path(value).is_absolute(), f"{tag} 가 상대경로: {value}"

    def test_relative_runs_root_is_resolved(self, toy_case, tmp_path, monkeypatch):
        """runs_root 를 상대경로로 줘도 출력이 실제로 만들어져야 한다.

        OpenSim 은 Setup XML 이 있는 디렉터리로 작업 디렉터리를 옮긴다.
        run_dir 를 절대경로로 바꾸지 않으면 도구는 True 를 반환하면서
        setup/ 밑의 없는 경로에 쓰려다 조용히 실패한다.
        """
        case, model_path = toy_case
        workdir = tmp_path / "workdir"
        workdir.mkdir()
        monkeypatch.chdir(workdir)

        result = _rendered_run(case, model_path, Path("runs"))
        assert result.run_dir.is_absolute()

        ik = steps.run_ik(
            result.run_dir / "setup" / "ik_setup.xml",
            result.run_dir,
            result.outputs["ik_motion"],
        )
        assert ik.status == "ok"
        assert result.outputs["ik_motion"].exists()
        assert result.outputs["ik_marker_errors"].exists()

    def test_time_range_comes_from_marker_file(self, toy_case, tmp_path):
        case, model_path = toy_case
        result = _rendered_run(case, model_path, tmp_path / "runs")
        text = (result.run_dir / "setup" / "ik_setup.xml").read_text(encoding="utf-8")
        start, end = text.split("<time_range>")[1].split("</time_range>")[0].split()
        assert float(start) == pytest.approx(0.0)
        assert float(end) == pytest.approx((FRAMES - 1) / RATE)

    def test_external_loads_unassigned_without_grf(self, toy_case, tmp_path):
        """GRF 가 없으면 없는 파일을 가리키지 않고 Unassigned 여야 한다."""
        case, model_path = toy_case
        result = _rendered_run(case, model_path, tmp_path / "runs")
        for step in ("id", "so", "jr"):
            text = (result.run_dir / "setup" / f"{step}_setup.xml").read_text(encoding="utf-8")
            assert "<external_loads_file>Unassigned</external_loads_file>" in text


class TestToolsProduceExpectedFiles:
    """도구가 실제로 쓰는 파일과 파이프라인이 기대하는 경로가 같은지 본다."""

    def test_full_chain_after_scaling(self, toy_case, tmp_path):
        case, model_path = toy_case
        result = _rendered_run(case, model_path, tmp_path / "runs")
        run_dir, outputs = result.run_dir, result.outputs
        setup = run_dir / "setup"

        ik = steps.run_ik(setup / "ik_setup.xml", run_dir, outputs["ik_motion"])
        assert ik.status == "ok"
        assert outputs["ik_motion"].exists()

        # 마커 오차 파일 이름은 OpenSim 이 정한다 — 유도한 경로와 일치해야 한다
        assert outputs["ik_marker_errors"].exists(), sorted(
            p.name for p in (run_dir / "results").iterdir()
        )

        identified = steps.run_id(setup / "id_setup.xml", run_dir, outputs["id_forces"])
        assert identified.status == "ok"
        assert outputs["id_forces"].exists()

        so = steps.run_static_optimization(
            setup / "so_setup.xml", run_dir, outputs["so_activation"]
        )
        assert so.status == "ok"
        assert outputs["so_activation"].exists()
        # JR 이 입력으로 받는 근육력 파일
        assert outputs["so_forces"].exists()

        jr = steps.run_joint_reaction(
            setup / "jr_setup.xml", run_dir, outputs["jr_reaction"]
        )
        assert jr.status == "ok"
        assert outputs["jr_reaction"].exists()

    def test_ik_solves_every_frame(self, toy_case, tmp_path):
        """해석 구간이 치환되지 않으면 여기서 프레임 수가 1 로 떨어진다."""
        case, model_path = toy_case
        result = _rendered_run(case, model_path, tmp_path / "runs")
        steps.run_ik(
            result.run_dir / "setup" / "ik_setup.xml",
            result.run_dir,
            result.outputs["ik_motion"],
        )
        lines = result.outputs["ik_motion"].read_text(encoding="utf-8").splitlines()
        data_start = next(i for i, ln in enumerate(lines) if ln.strip().lower() == "endheader")
        rows = [ln for ln in lines[data_start + 2 :] if ln.strip()]
        assert len(rows) == FRAMES

    def test_marker_errors_are_readable_and_small(self, toy_case, tmp_path):
        """마커 궤적을 모델에서 만들었으므로 오차는 0 에 가까워야 한다."""
        case, model_path = toy_case
        result = _rendered_run(case, model_path, tmp_path / "runs")
        steps.run_ik(
            result.run_dir / "setup" / "ik_setup.xml",
            result.run_dir,
            result.outputs["ik_motion"],
        )
        metrics = parse_ik_marker_errors(result.outputs["ik_marker_errors"])
        assert metrics.marker_rms_m is not None, metrics.notes
        assert metrics.marker_rms_m < 1e-3
