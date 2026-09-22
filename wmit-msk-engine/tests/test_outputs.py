"""QoI 추출 테스트 (ROM, 관절 모멘트, 근육력, 관절반력).

핵심: 값이 없을 때 0 으로 채우지 않고 이유를 남기는지, 단위와 좌표계가
결과에 실려 나가는지 본다. 단위 없는 관절반력 숫자는 인용할 수 없다.
"""

from __future__ import annotations

from msk_engine.outputs import (
    actuator_peaks,
    coordinate_ranges,
    joint_moments,
    joint_reaction_peaks,
    summarise,
)


class TestRangeOfMotion:
    def test_reads_span_and_unit(self, sto_factory):
        path = sto_factory(
            "ik.mot", ["time", "knee_angle_r"], [[0.0, 5.0], [0.1, 65.0], [0.2, 20.0]]
        )
        ranges, notes = coordinate_ranges(path)
        assert not notes
        assert len(ranges) == 1
        assert ranges[0].coordinate == "knee_angle_r"
        assert ranges[0].minimum == 5.0
        assert ranges[0].maximum == 65.0
        assert ranges[0].span == 60.0
        assert ranges[0].unit == "deg"  # 헤더의 inDegrees=yes

    def test_filters_to_requested_coordinates(self, sto_factory):
        path = sto_factory(
            "ik.mot", ["time", "knee_angle_r", "hip_flexion_r"], [[0.0, 5.0, 10.0]]
        )
        ranges, _ = coordinate_ranges(path, coordinates=["knee_angle_r"])
        assert [r.coordinate for r in ranges] == ["knee_angle_r"]

    def test_requested_but_absent_coordinate_is_reported(self, sto_factory):
        path = sto_factory("ik.mot", ["time", "knee_angle_r"], [[0.0, 5.0]])
        _, notes = coordinate_ranges(path, coordinates=["ankle_angle_r"])
        assert any("ankle_angle_r" in n for n in notes)

    def test_missing_file_notes_not_empty_result(self, tmp_path):
        ranges, notes = coordinate_ranges(tmp_path / "absent.mot")
        assert ranges == []
        assert notes


class TestJointMoments:
    def test_units_follow_column_suffix(self, sto_factory):
        path = sto_factory(
            "id.sto",
            ["time", "knee_angle_r_moment", "pelvis_tx_force"],
            [[0.0, 40.0, 12.0], [0.1, -55.0, 5.0]],
        )
        peaks, notes = joint_moments(path)
        assert not notes
        by_name = {p.name: p for p in peaks}
        assert by_name["knee_angle_r_moment"].unit == "N*m"
        assert by_name["knee_angle_r_moment"].peak_absolute == 55.0
        assert by_name["pelvis_tx_force"].unit == "N"

    def test_missing_file_notes(self, tmp_path):
        peaks, notes = joint_moments(tmp_path / "absent.sto")
        assert peaks == []
        assert notes


class TestJointReaction:
    def test_groups_components_and_computes_magnitude(self, sto_factory):
        path = sto_factory(
            "jr.sto",
            [
                "time",
                "knee_r_on_tibia_r_in_tibia_r_fx",
                "knee_r_on_tibia_r_in_tibia_r_fy",
                "knee_r_on_tibia_r_in_tibia_r_fz",
                "knee_r_on_tibia_r_in_tibia_r_mx",
                "knee_r_on_tibia_r_in_tibia_r_my",
                "knee_r_on_tibia_r_in_tibia_r_mz",
            ],
            [[0.0, 3.0, 4.0, 0.0, 1.0, 0.0, 0.0], [0.1, 0.0, 0.0, 1.0, 0.0, 0.0, 2.0]],
        )
        peaks, notes = joint_reaction_peaks(path)
        assert not notes
        assert len(peaks) == 1
        assert peaks[0].peak_force_n == 5.0
        assert peaks[0].peak_moment_nm == 2.0
        # 표현 좌표계가 결과에 남아야 한다
        assert peaks[0].expressed_in == "tibia_r"

    def test_time_only_file_explains_why(self, sto_factory):
        """joint_names 가 모델과 안 맞으면 time 열만 남는다 — 이유를 말해야 한다."""
        path = sto_factory("jr.sto", ["time"], [[0.0], [0.1]])
        peaks, notes = joint_reaction_peaks(path)
        assert peaks == []
        assert any("joint_names" in n for n in notes)


class TestActuatorPeaks:
    def test_classifies_with_model_kinds(self, sto_factory):
        path = sto_factory(
            "so_force.sto",
            ["time", "vasmed_r", "device_brace_torque", "reserve_knee"],
            [[0.0, 100.0, 8.0, 0.5]],
        )
        kinds = {
            "vasmed_r": "muscle",
            "device_brace_torque": "device",
            "reserve_knee": "actuator",
        }
        grouped, notes = actuator_peaks(path, kinds)
        assert not notes
        assert [p.name for p in grouped["muscle"]] == ["vasmed_r"]
        assert [p.name for p in grouped["device"]] == ["device_brace_torque"]
        assert [p.name for p in grouped["actuator"]] == ["reserve_knee"]

    def test_without_model_says_it_cannot_separate_reserves(self, sto_factory):
        path = sto_factory("so_force.sto", ["time", "vasmed_r"], [[0.0, 100.0]])
        _, notes = actuator_peaks(path, None)
        assert any("예비 액추에이터" in n for n in notes)


class TestSummarise:
    def test_assembles_all_four_qois(self, sto_factory, tmp_path):
        outputs = {
            "ik_motion": sto_factory("ik.mot", ["time", "knee_angle_r"], [[0.0, 5.0], [0.1, 60.0]]),
            "id_forces": sto_factory("id.sto", ["time", "knee_angle_r_moment"], [[0.0, 40.0]]),
            "so_forces": sto_factory("so.sto", ["time", "vasmed_r"], [[0.0, 120.0]]),
            "jr_reaction": sto_factory(
                "jr.sto",
                ["time", "knee_r_on_tibia_r_in_tibia_r_fx",
                 "knee_r_on_tibia_r_in_tibia_r_fy", "knee_r_on_tibia_r_in_tibia_r_fz"],
                [[0.0, 3.0, 4.0, 0.0]],
            ),
        }
        summary = summarise(outputs, quality={"marker_rms_m": 0.01}, metadata={"case": "c"})
        assert summary.range_of_motion[0].span == 55.0
        assert summary.joint_moments[0].peak_absolute == 40.0
        assert summary.joint_reactions[0].peak_force_n == 5.0
        assert summary.quality["marker_rms_m"] == 0.01
        # 단위가 결과에 실려야 한다
        assert summary.metadata["units"]["force"] == "N"
        assert summary.metadata["units"]["angle"] == "deg"

    def test_writes_summary_json(self, sto_factory, tmp_path):
        import json

        outputs = {
            "ik_motion": sto_factory("ik.mot", ["time", "knee_angle_r"], [[0.0, 5.0]]),
            "id_forces": sto_factory("id.sto", ["time", "knee_angle_r_moment"], [[0.0, 40.0]]),
            "so_forces": sto_factory("so.sto", ["time", "vasmed_r"], [[0.0, 120.0]]),
            "jr_reaction": sto_factory("jr.sto", ["time"], [[0.0]]),
        }
        summary = summarise(outputs)
        path = summary.write(tmp_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert path.name == "summary.json"
        assert "range_of_motion" in payload
        # 반력이 비었으면 이유가 남아야 한다
        assert payload["notes"]


class TestUnknownColumns:
    """모델의 힘 집합에 없는 열은 액추에이터가 아니다.

    CoordinateLimitForce 는 힘과 함께 PotentialEnergy(J) 를 기록한다.
    이것을 액추에이터로 분류하면 단위가 다른 값이 근육력·기기 하중 표에
    섞이고, 회귀 기준선에도 잘못된 항목으로 굳는다.
    """

    def test_column_absent_from_model_is_not_an_actuator(self, sto_factory):
        path = sto_factory(
            "so_force.sto",
            ["time", "vasmed_r", "PotentialEnergy"],
            [[0.0, 100.0, 7.5]],
        )
        grouped, notes = actuator_peaks(path, {"vasmed_r": "muscle"})
        assert [p.name for p in grouped["muscle"]] == ["vasmed_r"]
        assert [p.name for p in grouped["actuator"]] == []
        assert [p.name for p in grouped["unknown"]] == ["PotentialEnergy"]
        assert any("PotentialEnergy" in n for n in notes)

    def test_without_a_model_the_limitation_is_declared(self, sto_factory):
        """모델이 없으면 열을 귀속시킬 수 없다 — 그 사실이 결과에 남아야 한다.

        실제 파이프라인은 항상 해석 모델을 넘기므로 이 경로는 퇴화 경로다.
        조용히 근육으로 분류하는 대신 notes 로 한계를 밝힌다.
        """
        outputs = {
            "ik_motion": sto_factory("ik.mot", ["time", "knee_angle_r"], [[0.0, 5.0]]),
            "id_forces": sto_factory("id.sto", ["time", "knee_angle_r_moment"], [[0.0, 40.0]]),
            "so_forces": sto_factory("so.sto", ["time", "PotentialEnergy"], [[0.0, 7.5]]),
            "jr_reaction": sto_factory("jr.sto", ["time"], [[0.0]]),
        }
        summary = summarise(outputs)
        assert any("예비 액추에이터" in n for n in summary.notes)
