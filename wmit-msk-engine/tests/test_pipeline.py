"""파이프라인·Setup XML·재현성 기록 테스트.

OpenSim 없이 도는 범위만 다룬다. 실제 도구 실행은 opensim 마커를 붙인다.
"""

from __future__ import annotations

import json
import re

import pytest

from msk_engine.errors import ConfigurationError
from msk_engine.pipeline import CaseSpec, run_case, validate_case
from msk_engine.provenance import Provenance, sha256_file
from msk_engine.steps import render_setup_xml


class TestRenderSetupXml:
    def test_substitutes_placeholders(self, tmp_path):
        template = tmp_path / "t.xml"
        template.write_text(
            '<?xml version="1.0"?><root><model>@MODEL_FILE@</model></root>',
            encoding="utf-8",
        )
        out = render_setup_xml(
            template, {"MODEL_FILE": "/models/a.osim"}, tmp_path / "out.xml"
        )
        assert "/models/a.osim" in out.read_text(encoding="utf-8")

    def test_leftover_placeholder_fails(self, tmp_path):
        """치환 누락을 조용히 넘기면 OpenSim 이 이상한 경로를 받는다."""
        template = tmp_path / "t.xml"
        template.write_text(
            '<?xml version="1.0"?><root><a>@MODEL_FILE@</a><b>@FORGOTTEN@</b></root>',
            encoding="utf-8",
        )
        with pytest.raises(ConfigurationError) as exc:
            render_setup_xml(template, {"MODEL_FILE": "x"}, tmp_path / "out.xml")
        assert "FORGOTTEN" in str(exc.value)

    def test_invalid_xml_fails(self, tmp_path):
        template = tmp_path / "t.xml"
        template.write_text("<root><unclosed>@A@", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            render_setup_xml(template, {"A": "1"}, tmp_path / "out.xml")

    def test_missing_template_fails(self, tmp_path):
        with pytest.raises(ConfigurationError):
            render_setup_xml(tmp_path / "absent.xml", {}, tmp_path / "out.xml")


class TestProvenance:
    def test_sha256_is_stable(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_text("hello", encoding="utf-8")
        assert sha256_file(path) == sha256_file(path)

    def test_records_inputs_and_steps(self, tmp_path):
        data = tmp_path / "in.trc"
        data.write_text("x", encoding="utf-8")

        prov = Provenance.start("run1", "case1", "0.1.0")
        prov.record_input("markers", data)
        prov.record_step("ik", "ok", duration_s=1.2, outputs=["ik.mot"])
        prov.finish("ok")
        written = prov.write(tmp_path / "run")

        payload = json.loads(written.read_text(encoding="utf-8"))
        assert payload["run_id"] == "run1"
        assert payload["status"] == "ok"
        assert "markers" in payload["input_hashes"]
        assert payload["steps"][0]["name"] == "ik"
        assert payload["joint_reaction_frame"] == "tibia"

    def test_records_units_and_frame(self, tmp_path):
        """FE 연계를 위해 좌표계·단위가 결과에 남아야 한다."""
        prov = Provenance.start("r", "c", "0.1.0")
        payload = json.loads(prov.write(tmp_path).read_text(encoding="utf-8"))
        assert payload["length_unit"] == "m"
        assert payload["force_unit"] == "N"


def _write_case(tmp_path, trc_factory, repo_root, *, with_grf: bool = False):
    """실제 템플릿을 쓰는 Case YAML 을 만든다."""
    markers = trc_factory(name="gait.trc")
    static = trc_factory(name="static.trc")
    model = tmp_path / "model.osim"
    model.write_text('<?xml version="1.0"?><OpenSimDocument/>', encoding="utf-8")

    templates = repo_root / "configs" / "templates"
    lines = [
        "name: unit_case",
        "subject:",
        "  height_m: 1.75",
        "  mass_kg: 70.0",
        f"  marker_file: {markers}",
        f"  static_trial: {static}",
    ]
    if with_grf:
        grf = tmp_path / "grf.mot"
        grf.write_text(
            "grf\nversion=1\nnRows=2\nnColumns=2\ninDegrees=no\nendheader\n"
            "time\tground_force_vy\n0.000000\t0.000000\n0.090000\t500.000000\n",
            encoding="utf-8",
        )
        lines.append(f"  grf_file: {grf}")

    lines += [
        f"model_file: {model}",
        "templates:",
        f"  scale: {templates / 'scale_setup.xml'}",
        f"  ik: {templates / 'ik_setup.xml'}",
        f"  id: {templates / 'id_setup.xml'}",
        f"  so: {templates / 'so_setup.xml'}",
        f"  jr: {templates / 'jr_setup.xml'}",
        f"  external_loads: {templates / 'external_loads.xml'}",
        "joint_reaction_frame: tibia_r",
        "thresholds:",
        "  marker_rms_m: TBD",
    ]
    case_file = tmp_path / "case.yaml"
    case_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return case_file


class TestCaseSpec:
    def test_loads_yaml(self, tmp_path, trc_factory, repo_root):
        case = CaseSpec.from_yaml(_write_case(tmp_path, trc_factory, repo_root))
        assert case.name == "unit_case"
        assert case.subject.mass_kg == 70.0
        assert case.joint_reaction_frame == "tibia_r"

    def test_tbd_threshold_becomes_none(self, tmp_path, trc_factory, repo_root):
        """TBD 는 0 이 아니라 '미정' 이다."""
        case = CaseSpec.from_yaml(_write_case(tmp_path, trc_factory, repo_root))
        assert case.thresholds.marker_rms_m is None

    def test_missing_file(self, tmp_path):
        with pytest.raises(ConfigurationError):
            CaseSpec.from_yaml(tmp_path / "absent.yaml")

    def test_missing_required_key(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("name: x\n", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            CaseSpec.from_yaml(bad)


class TestValidateCase:
    def test_valid_case_passes(self, tmp_path, trc_factory, repo_root):
        case = CaseSpec.from_yaml(_write_case(tmp_path, trc_factory, repo_root))
        assert validate_case(case).ok

    def test_grf_without_external_loads_template(
        self, tmp_path, trc_factory, repo_root
    ):
        case = CaseSpec.from_yaml(
            _write_case(tmp_path, trc_factory, repo_root, with_grf=True)
        )
        case.templates.pop("external_loads")
        report = validate_case(case)
        assert not report.ok
        assert any("external_loads" in e for e in report.errors)

    def test_missing_model_file(self, tmp_path, trc_factory, repo_root):
        case = CaseSpec.from_yaml(_write_case(tmp_path, trc_factory, repo_root))
        case.model_file.unlink()
        assert not validate_case(case).ok


class TestRunCaseDryRun:
    def test_dry_run_renders_setup_without_opensim(
        self, tmp_path, trc_factory, repo_root
    ):
        case = CaseSpec.from_yaml(
            _write_case(tmp_path, trc_factory, repo_root, with_grf=True)
        )
        result = run_case(case, runs_root=tmp_path / "runs", dry_run=True)

        assert result.status == "dry_run"
        setup_dir = result.run_dir / "setup"
        for name in ("scale", "ik", "id", "so", "jr"):
            assert (setup_dir / f"{name}_setup.xml").exists()
        assert (setup_dir / "external_loads.xml").exists()

        rendered = (setup_dir / "jr_setup.xml").read_text(encoding="utf-8")
        assert "tibia_r" in rendered
        # 치환되지 않고 남은 자리표시자가 없어야 한다
        assert not re.search(r"@[A-Z][A-Z0-9_]*@", rendered)

    def test_validation_failure_stops_before_analysis(
        self, tmp_path, trc_factory, repo_root
    ):
        """검증 실패 시 해석을 시작하지 않고 기록만 남긴다."""
        case = CaseSpec.from_yaml(_write_case(tmp_path, trc_factory, repo_root))
        case.subject.height_m = 175.0

        result = run_case(case, runs_root=tmp_path / "runs")
        assert result.status == "failed_validation"
        assert not result.validation.ok
        assert (result.run_dir / "validation.json").exists()
        assert result.provenance_path is not None
        assert not (result.run_dir / "results" / "ik.mot").exists()

    def test_provenance_written_on_dry_run(self, tmp_path, trc_factory, repo_root):
        case = CaseSpec.from_yaml(_write_case(tmp_path, trc_factory, repo_root))
        result = run_case(case, runs_root=tmp_path / "runs", dry_run=True)
        payload = json.loads(result.provenance_path.read_text(encoding="utf-8"))
        assert payload["joint_reaction_frame"] == "tibia_r"
        assert payload["input_hashes"]
        assert payload["setup_xml_copies"]


@pytest.mark.opensim
class TestWithOpenSim:
    def test_opensim_importable(self):
        import opensim

        assert opensim is not None
