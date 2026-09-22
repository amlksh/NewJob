"""A-1 발송 패키지 검증 (WO-G1 §6).

기기 측에 보내는 템플릿이 **해석 엔진의 스키마와 어긋나지 않는지** 본다.
템플릿이 낡으면 기기 측이 엉뚱한 항목을 채워 보내고, 그 회신은 로더에서
거절된다. 회신 리드타임이 외부 의존이라 한 번 어긋나면 되돌리는 비용이 크다.

여기서 확인하는 것:
  1. 템플릿 항목이 스키마가 받는 항목과 정확히 일치한다 (양쪽 방향 모두)
  2. 채우지 않은 템플릿은 거절된다 — 빈칸이 조용히 통과하면 안 된다
  3. 채운 회신은 통과한다 — 템플릿대로 채웠는데 거절되면 안 된다
  4. 채움 표시 `_` 가 남은 칸은 값으로 인정되지 않는다
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from msk_engine.device.spec import (
    ACTUATION_KEYS,
    ATTACHMENT_KEYS,
    HINGE_KEYS,
    ROM_KEYS,
    SEGMENT_KEYS,
    SOURCE_KEYS,
    DeviceSpec,
)
from msk_engine.errors import ConfigurationError

PACKAGE = Path(__file__).resolve().parent.parent / "docs" / "interfaces" / "device_parameter_request"
TEMPLATE = PACKAGE / "device_parameter_template.yaml"
REQUEST = PACKAGE / "README.md"


@pytest.fixture
def template() -> dict:
    return yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))


def _filled(template: dict) -> dict:
    """기기 측이 채워 보낸 회신을 흉내 낸다. [VPK] 칸도 B-2 기준으로 채운다."""
    data = copy.deepcopy(template)
    data["name"] = "knee_rehab_brace"
    data["description"] = "무릎 재활 보조기"
    data["source"] = {
        "cad_file": "brace_revB.step",
        "revision": "revB",
        "exported_by": "담당자",
        "exported_at": "2026-09-30",
        "notes": "최대 토크는 연속 정격",
    }
    for segment in data["segments"]:
        segment["mass_kg"] = 0.35
        segment["center_of_mass"] = [0.0, -0.04, 0.02]
        segment["inertia"] = [0.0018, 0.0007, 0.0018, 0.0, 0.0, 0.0]
        segment["attachment"]["location"] = [0.0, -0.20, 0.04]
        segment["attachment"]["orientation_deg"] = [0.0, 0.0, 0.0]
    data["hinge"]["axis"] = [0.0, 0.0, 1.0]
    data["hinge"]["location"] = [0.0, -0.40, 0.05]
    data["rom"].update(
        {"min_deg": 0.0, "max_deg": 120.0,
         "stiffness_nm_per_deg": 5.0, "damping_nm_s_per_deg": 0.5}
    )
    data["actuation"].update({"mode": "assistive", "max_torque_nm": 18.0})
    for key in ("torque_file", "stiffness_nm_per_rad", "damping_nm_s_per_rad"):
        data["actuation"][key] = None
    return data


class TestTemplateMatchesSchema:
    """템플릿과 스키마가 같은 항목을 말하는지. 어긋나면 회신이 거절된다."""

    def test_top_level_keys(self, template):
        assert set(template) == set(DeviceSpec.TOP_LEVEL_KEYS)

    def test_source_keys(self, template):
        assert set(template["source"]) == set(SOURCE_KEYS)

    def test_hinge_keys(self, template):
        assert set(template["hinge"]) == set(HINGE_KEYS)

    def test_rom_keys(self, template):
        assert set(template["rom"]) == set(ROM_KEYS)

    def test_actuation_keys(self, template):
        assert set(template["actuation"]) == set(ACTUATION_KEYS)

    @pytest.mark.parametrize("index", [0, 1, 2])
    def test_segment_keys(self, template, index):
        segment = template["segments"][index]
        assert set(segment) == set(SEGMENT_KEYS)
        assert set(segment["attachment"]) == set(ATTACHMENT_KEYS)

    def test_covers_thigh_and_shank(self, template):
        """§6 은 대퇴·하퇴 각각의 부착점을 요구한다."""
        hosts = {s["attachment"]["host_body"] for s in template["segments"]}
        assert {"femur_r", "tibia_r"} <= hosts


class TestTemplateBehaviour:
    def test_unfilled_template_is_refused(self, template):
        """빈 템플릿이 통과하면 값 없는 기기로 해석이 돌아간다."""
        with pytest.raises(ConfigurationError) as exc:
            DeviceSpec.parse(template, PACKAGE)
        assert "mass_kg" in str(exc.value)

    def test_filled_reply_is_accepted(self, template):
        """템플릿대로 채운 회신이 거절되면 템플릿이 잘못된 것이다."""
        spec = DeviceSpec.parse(_filled(template), PACKAGE)
        assert spec.name == "knee_rehab_brace"
        assert spec.actuation.mode == "assistive"
        assert spec.rom is not None and spec.hinge is not None
        assert spec.source.is_traceable
        assert spec.warnings() == []

    def test_leftover_fill_marker_is_not_a_value(self, template):
        """`_` 를 지우지 않고 회신한 칸이 값으로 인정되면 안 된다."""
        data = _filled(template)
        data["source"]["revision"] = "_"
        spec = DeviceSpec.parse(data, PACKAGE)
        assert not spec.source.is_traceable

    def test_prescribed_motion_is_refused_with_a_pointer(self, template):
        """CPM 모드를 템플릿에 적으면 거절되고 사유가 나와야 한다 (§7)."""
        data = _filled(template)
        data["actuation"]["mode"] = "prescribed_motion"
        with pytest.raises(ConfigurationError) as exc:
            DeviceSpec.parse(data, PACKAGE)
        assert "ADR-0004" in str(exc.value)


class TestRequestDocument:
    """발송 문서가 지시받은 내용을 담고 있는지."""

    @pytest.fixture
    def text(self) -> str:
        return REQUEST.read_text(encoding="utf-8")

    def test_states_the_reply_deadline(self, text):
        assert "W6" in text

    def test_explains_why_the_deadline_matters(self, text):
        """C-1 이 이 회신에 종속된다는 사실이 있어야 기한이 근거를 갖는다."""
        assert "C-1" in text

    def test_carries_the_tier_distinction(self, text):
        assert "Tier 1" in text and "Tier 2" in text

    def test_carries_the_prescribed_motion_notice(self, text):
        assert "prescribed_motion" in text
        assert "CPM" in text

    def test_points_at_the_template(self, text):
        assert TEMPLATE.name in text

    def test_separates_landmark_attachment_from_model_frame(self, text):
        """부착점은 기기 측이 모델 좌표계로 줄 수 없다 — 분리가 명시돼야 한다."""
        assert "랜드마크" in text
        assert "[VPK]" in text
