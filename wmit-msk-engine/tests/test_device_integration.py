"""인체-장치 결합 해석 통합 테스트 (OpenSim 실행).

여기서 확인하는 것은 장치를 붙였을 때 **역학이 실제로 달라지는가** 이다.
장치 정의를 읽고 모델에 무언가를 추가하는 것만으로는 부족하다.
질량이 관절 모멘트에 반영되고, 구동 토크가 근육 대신 하중을 받아야
'결합했다' 고 말할 수 있다.

토이 모델 기준이므로 수치 자체는 생리학적 의미가 없다. 확인 대상은
파이프라인과 OpenSim 사이의 계약, 그리고 결합의 정성적 효과다.
"""

from __future__ import annotations

import re

import pytest

import toy_model
from msk_engine.device import attach_device, load_device_spec
from msk_engine.errors import StepExecutionError
from msk_engine.pipeline import CaseSpec, run_case
from msk_engine.quality import read_storage

pytestmark = pytest.mark.opensim


@pytest.fixture
def toy_inputs(tmp_path, repo_root):
    """토이 모델, 보행 trial, 정적 trial, 채워진 scale 템플릿."""
    templates = repo_root / "configs" / "templates"
    model_path = tmp_path / "toy.osim"
    model, state = toy_model.build_model(model_path)

    gait = tmp_path / "gait.trc"
    static = tmp_path / "static.trc"
    toy_model.write_markers(gait, model, state)
    toy_model.write_static_markers(static, model, state)
    scale_template = toy_model.write_scale_template(
        tmp_path / "scale_toy.xml", templates / "scale_setup.xml"
    )
    return {
        "tmp": tmp_path,
        "templates": templates,
        "model": model_path,
        "gait": gait,
        "static": static,
        "scale_template": scale_template,
    }


def _run(toy_inputs, device_spec=None, name="case.yaml"):
    case_file = toy_model.write_case_yaml(
        toy_inputs["tmp"] / name,
        toy_inputs["model"],
        toy_inputs["gait"],
        toy_inputs["templates"],
        scale_template=toy_inputs["scale_template"],
        static_trial=toy_inputs["static"],
        device_spec=device_spec,
    )
    return run_case(
        CaseSpec.from_yaml(case_file), runs_root=toy_inputs["tmp"] / f"runs_{name}"
    )


def _peak(path, column) -> float:
    _, header, rows = read_storage(path)
    index = header.index(column)
    return max(abs(r[index]) for r in rows if index < len(r) and r[index] is not None)


class TestHumanOnlyChain:
    """장치 없이 Scale → IK → ID → SO → JR 전체가 도는지."""

    def test_all_five_steps_complete(self, toy_inputs):
        result = _run(toy_inputs)
        assert result.status == "ok"
        assert [s.name for s in result.steps] == ["scale", "ik", "id", "so", "jr"]
        assert all(s.status == "ok" for s in result.steps)

    def test_scaling_a_model_against_its_own_markers_gives_unit_factors(self, toy_inputs):
        """마커를 모델에서 만들었으므로 스케일 계수는 1 이어야 한다.

        1 이 아니면 ScaleTool 이 엉뚱한 마커 거리를 본 것이다.
        """
        result = _run(toy_inputs)
        factors = result.outputs["scale_factors"].read_text(encoding="utf-8")
        values = [float(v) for v in re.findall(r"<scales>\s*([0-9.eE+-]+)", factors)]
        assert values, "스케일 계수가 기록되지 않았다"
        assert all(v == pytest.approx(1.0, abs=1e-6) for v in values), values

    def test_ik_reproduces_the_prescribed_motion(self, toy_inputs):
        result = _run(toy_inputs)
        assert result.quality.marker_rms_m is not None, result.quality.notes
        assert result.quality.marker_rms_m < 1e-4

    def test_summary_carries_all_four_qois(self, toy_inputs):
        """ROM, 관절 모멘트, 근육력, 관절반력이 모두 나와야 한다."""
        result = _run(toy_inputs)
        summary = result.summary
        assert summary is not None
        assert {r.coordinate for r in summary.range_of_motion} >= {toy_model.KNEE_COORDINATE}
        assert any(m.name.endswith("_moment") for m in summary.joint_moments)
        assert [m.name for m in summary.muscle_forces] == [toy_model.MUSCLE]
        assert summary.joint_reactions and summary.joint_reactions[0].peak_force_n
        # 좌표계와 단위가 결과에 실려야 한다 (CLAUDE.md §4)
        assert summary.joint_reactions[0].expressed_in == toy_model.SHANK_BODY
        assert summary.metadata["units"]["moment"] == "N*m"
        assert result.summary_path.is_file()


class TestDeviceCoupling:
    def test_welded_device_adds_no_degrees_of_freedom(self, toy_inputs, tmp_path):
        """Tier 1 결합은 자유도를 늘리지 않는다 — 닫힌 사슬을 만들지 않기 위해서다."""
        import opensim as osim

        spec = load_device_spec(toy_model.write_device_yaml(tmp_path / "device.yaml"))
        out = tmp_path / "with_device.osim"
        build = attach_device(toy_inputs["model"], spec, out)

        before = osim.Model(str(toy_inputs["model"]))
        before.initSystem()
        after = osim.Model(str(out))
        after.initSystem()

        assert after.getCoordinateSet().getSize() == before.getCoordinateSet().getSize()
        assert after.getBodySet().getSize() == before.getBodySet().getSize() + 2
        assert build.added_bodies == ["device_thigh_cuff", "device_shank_cuff"]

    def test_device_mass_raises_the_joint_moment(self, toy_inputs):
        """장치를 달면 하지 관성이 늘어 무릎 모멘트가 커져야 한다."""
        base = _run(toy_inputs, name="base.yaml")
        device_yaml = toy_model.write_device_yaml(toy_inputs["tmp"] / "device.yaml")
        with_device = _run(toy_inputs, device_spec=device_yaml, name="dev.yaml")

        column = f"{toy_model.KNEE_COORDINATE}_moment"
        assert _peak(with_device.outputs["id_forces"], column) > _peak(
            base.outputs["id_forces"], column
        )

    def test_assistive_device_carries_load_and_respects_its_limit(self, toy_inputs):
        """구동 장치가 실제로 토크를 내고, 정해진 최대치를 넘지 않아야 한다."""
        device_yaml = toy_model.write_device_yaml(
            toy_inputs["tmp"] / "device.yaml", max_torque_nm=20.0
        )
        result = _run(toy_inputs, device_spec=device_yaml, name="dev.yaml")

        loads = {p.name: p for p in result.summary.device_loads}
        torque = loads[f"device_{toy_model.DEVICE_NAME}_torque"]
        assert torque.peak_absolute > 0.0, "장치가 하중을 전혀 받지 않았다"
        assert torque.peak_absolute <= 20.0 + 1e-6, "최대 토크를 넘었다"

    def test_device_reduces_muscle_force(self, toy_inputs):
        """보조 장치가 하중을 나눠 받으면 근육력이 줄어야 한다.

        이것이 재활 보조기 해석의 핵심 결과다. 장치를 달았는데 근육력이
        그대로면 결합이 역학적으로 작동하지 않은 것이다.
        """
        base = _run(toy_inputs, name="base.yaml")
        device_yaml = toy_model.write_device_yaml(toy_inputs["tmp"] / "device.yaml")
        with_device = _run(toy_inputs, device_spec=device_yaml, name="dev.yaml")

        base_muscle = _peak(base.outputs["so_forces"], toy_model.MUSCLE)
        device_muscle = _peak(with_device.outputs["so_forces"], toy_model.MUSCLE)
        assert device_muscle < base_muscle, (base_muscle, device_muscle)

    def test_device_spec_is_archived_and_hashed(self, toy_inputs):
        """어느 장치 정의로 돌렸는지 재현 기록에 남아야 한다."""
        import json

        device_yaml = toy_model.write_device_yaml(toy_inputs["tmp"] / "device.yaml")
        result = _run(toy_inputs, device_spec=device_yaml, name="dev.yaml")
        payload = json.loads(result.provenance_path.read_text(encoding="utf-8"))
        assert "device_spec" in payload["input_hashes"]
        assert (result.run_dir / "setup" / "device.yaml").is_file()


class TestDeviceValidationAgainstModel:
    def test_unknown_host_body_names_the_available_bodies(self, toy_inputs, tmp_path):
        spec = load_device_spec(
            toy_model.write_device_yaml(tmp_path / "device.yaml", host_body="femur_r")
        )
        with pytest.raises(StepExecutionError) as exc:
            attach_device(toy_inputs["model"], spec, tmp_path / "out.osim")
        assert "femur_r" in str(exc.value)
        assert toy_model.THIGH_BODY in str(exc.value)

    def test_misaligned_hinge_is_reported(self, toy_inputs, tmp_path):
        """축이 어긋난 장치는 경고로 남는다 — P1 모델이 그 구속력을 못 그리기 때문이다."""
        spec = load_device_spec(
            toy_model.write_device_yaml(tmp_path / "device.yaml", hinge_axis=(1.0, 0.0, 0.0))
        )
        build = attach_device(toy_inputs["model"], spec, tmp_path / "out.osim")
        assert build.hinge_misalignment_deg == pytest.approx(90.0, abs=1e-6)
        assert any("어긋남" in w for w in build.warnings)

    def test_aligned_hinge_produces_no_warning(self, toy_inputs, tmp_path):
        spec = load_device_spec(
            toy_model.write_device_yaml(tmp_path / "device.yaml", hinge_axis=(0.0, 0.0, 1.0))
        )
        build = attach_device(toy_inputs["model"], spec, tmp_path / "out.osim")
        assert build.hinge_misalignment_deg == pytest.approx(0.0, abs=1e-6)
        assert not any("어긋남" in w for w in build.warnings)


class TestJointReactionGuard:
    def test_wrong_joint_name_fails_instead_of_writing_an_empty_result(self, toy_inputs):
        """JointReaction 은 관절 이름이 틀려도 오류 없이 time 열만 쓴다."""
        from msk_engine import steps

        result = _run(toy_inputs, name="base.yaml")
        setup = result.run_dir / "setup" / "jr_setup.xml"
        setup.write_text(
            setup.read_text(encoding="utf-8").replace(
                f"<joint_names> {toy_model.KNEE_JOINT} </joint_names>",
                "<joint_names> no_such_joint </joint_names>",
            ),
            encoding="utf-8",
        )
        with pytest.raises(StepExecutionError) as exc:
            steps.run_joint_reaction(setup, result.run_dir, result.outputs["jr_reaction"])
        assert "joint_names" in str(exc.value)
