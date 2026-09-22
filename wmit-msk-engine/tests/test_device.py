"""장치 파라미터(CAD 인터페이스) 검증 테스트.

핵심: 해석에 영향을 주는 값이 비거나 틀린 채로 조용히 통과하지 않는지 본다.
장치 질량이 0 이거나 ROM 강성이 없으면 결과가 '장치 없음' 과 구분되지 않는다.
"""

from __future__ import annotations

import pytest
import yaml

from msk_engine.device.spec import DeviceSpec, load_device_spec
from msk_engine.errors import ConfigurationError

MINIMAL = {
    "name": "brace",
    "segments": [
        {
            "name": "cuff",
            "mass_kg": 0.5,
            "attachment": {"host_body": "femur_r", "location": [0.0, -0.2, 0.0]},
        }
    ],
}


def parse(overrides: dict | None = None, tmp_path=None) -> DeviceSpec:
    from pathlib import Path

    data = {**MINIMAL, **(overrides or {})}
    return DeviceSpec.parse(data, Path(tmp_path) if tmp_path else Path("."))


class TestSegments:
    def test_minimal_spec_parses(self):
        spec = parse()
        assert spec.name == "brace"
        assert spec.total_mass_kg == 0.5
        assert spec.host_bodies == ("femur_r",)

    def test_zero_mass_rejected(self):
        """질량 0 인 장치는 해석에 아무 영향을 주지 않는다 — 실수일 가능성이 높다."""
        with pytest.raises(ConfigurationError) as exc:
            parse({"segments": [{**MINIMAL["segments"][0], "mass_kg": 0.0}]})
        assert "mass_kg" in str(exc.value)

    def test_negative_inertia_rejected(self):
        with pytest.raises(ConfigurationError):
            parse({
                "segments": [
                    {**MINIMAL["segments"][0], "inertia": [-1.0, 1.0, 1.0, 0, 0, 0]}
                ]
            })

    def test_inertia_needs_six_components(self):
        with pytest.raises(ConfigurationError) as exc:
            parse({"segments": [{**MINIMAL["segments"][0], "inertia": [1.0, 1.0, 1.0]}]})
        assert "여섯" in str(exc.value)

    def test_duplicate_segment_names_rejected(self):
        with pytest.raises(ConfigurationError) as exc:
            parse({"segments": [MINIMAL["segments"][0], MINIMAL["segments"][0]]})
        assert "중복" in str(exc.value)

    def test_empty_segments_rejected(self):
        with pytest.raises(ConfigurationError):
            parse({"segments": []})

    def test_typo_in_key_is_rejected(self):
        """오타를 조용히 무시하면 값이 빠진 채로 해석이 돈다."""
        with pytest.raises(ConfigurationError) as exc:
            parse({"segments": [{**MINIMAL["segments"][0], "masss_kg": 1.0}]})
        assert "masss_kg" in str(exc.value)

    def test_inertia_defaults_to_zero_but_warns(self):
        spec = parse()
        assert any("관성" in w for w in spec.warnings())


class TestActuation:
    def test_assistive_needs_max_torque(self):
        with pytest.raises(ConfigurationError) as exc:
            parse({"actuation": {"mode": "assistive", "coordinate": "knee_angle_r"}})
        assert "max_torque_nm" in str(exc.value)

    def test_assistive_parses(self):
        spec = parse({
            "actuation": {
                "mode": "assistive", "coordinate": "knee_angle_r", "max_torque_nm": 20.0
            }
        })
        assert spec.actuation.mode == "assistive"
        assert spec.actuation.max_torque_nm == 20.0

    def test_passive_needs_stiffness(self):
        with pytest.raises(ConfigurationError):
            parse({"actuation": {"mode": "passive", "coordinate": "knee_angle_r"}})

    def test_prescribed_torque_needs_profile(self):
        with pytest.raises(ConfigurationError) as exc:
            parse({"actuation": {"mode": "prescribed_torque", "coordinate": "knee_angle_r"}})
        assert "torque_file" in str(exc.value)

    def test_prescribed_motion_is_refused_not_ignored(self):
        """P1 범위 밖인 방식은 조용히 무시하지 않고 거절한다."""
        with pytest.raises(ConfigurationError) as exc:
            parse({"actuation": {"mode": "prescribed_motion", "coordinate": "knee_angle_r"}})
        assert "ADR-0004" in str(exc.value)

    def test_unknown_mode_rejected(self):
        with pytest.raises(ConfigurationError):
            parse({"actuation": {"mode": "telekinesis", "coordinate": "knee_angle_r"}})

    def test_mode_needs_coordinate(self):
        with pytest.raises(ConfigurationError) as exc:
            parse({"actuation": {"mode": "assistive", "max_torque_nm": 5.0}})
        assert "coordinate" in str(exc.value)


class TestRangeOfMotion:
    def test_rom_parses(self):
        spec = parse({
            "rom": {
                "coordinate": "knee_angle_r", "min_deg": 0, "max_deg": 120,
                "stiffness_nm_per_deg": 5.0,
            }
        })
        assert spec.rom is not None
        assert spec.rom.max_deg == 120

    def test_inverted_range_rejected(self):
        with pytest.raises(ConfigurationError):
            parse({
                "rom": {
                    "coordinate": "knee_angle_r", "min_deg": 120, "max_deg": 0,
                    "stiffness_nm_per_deg": 5.0,
                }
            })

    def test_zero_stiffness_rejected(self):
        """강성 0 인 스토퍼는 아무것도 막지 않는다."""
        with pytest.raises(ConfigurationError) as exc:
            parse({
                "rom": {
                    "coordinate": "knee_angle_r", "min_deg": 0, "max_deg": 120,
                    "stiffness_nm_per_deg": 0.0,
                }
            })
        assert "stiffness" in str(exc.value)


class TestHinge:
    def test_zero_axis_rejected(self):
        with pytest.raises(ConfigurationError):
            parse({"hinge": {"axis": [0, 0, 0], "expressed_in": "femur_r"}})

    def test_axis_is_normalised(self):
        spec = parse({"hinge": {"axis": [0, 0, 5], "expressed_in": "femur_r"}})
        assert spec.hinge is not None
        assert spec.hinge.unit_axis == pytest.approx((0.0, 0.0, 1.0))


class TestTraceability:
    def test_missing_cad_source_warns(self):
        spec = parse()
        assert any("CAD 출처" in w for w in spec.warnings())

    def test_recorded_source_is_traceable(self):
        spec = parse({"source": {"cad_file": "brace.step", "revision": "B"}})
        assert spec.source.is_traceable
        assert not any("CAD 출처" in w for w in spec.warnings())


class TestLoadFromFile:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "device.yaml"
        path.write_text(yaml.safe_dump(MINIMAL), encoding="utf-8")
        spec = load_device_spec(path)
        assert spec.name == "brace"
        assert spec.spec_file == path.resolve()

    def test_missing_file(self, tmp_path):
        with pytest.raises(ConfigurationError):
            load_device_spec(tmp_path / "absent.yaml")

    def test_error_message_names_the_file(self, tmp_path):
        path = tmp_path / "device.yaml"
        path.write_text(yaml.safe_dump({"name": "x"}), encoding="utf-8")
        with pytest.raises(ConfigurationError) as exc:
            load_device_spec(path)
        assert "device.yaml" in str(exc.value)


class TestPlaceholderSource:
    """TBD 는 값이 아니다 — 출처가 없는 기기가 추적 가능해 보이면 안 된다."""

    @pytest.mark.parametrize("placeholder", ["TBD", "tbd", "TODO", "미정", ""])
    def test_placeholder_source_is_not_traceable(self, placeholder):
        spec = parse({"source": {"cad_file": placeholder, "revision": placeholder}})
        assert not spec.source.is_traceable
        assert any("CAD 출처" in w for w in spec.warnings())


class TestShippedExamples:
    """저장소에 들어 있는 예시 파일이 실제로 읽히는지."""

    def test_knee_rehab_brace_example_parses(self, repo_root):
        spec = load_device_spec(
            repo_root / "configs" / "devices" / "knee_rehab_brace_example.yaml"
        )
        assert spec.actuation.mode == "assistive"
        assert spec.rom is not None
        # 예시값이므로 CAD 출처가 비어 있다는 경고가 남아 있어야 한다
        assert any("CAD 출처" in w for w in spec.warnings())
