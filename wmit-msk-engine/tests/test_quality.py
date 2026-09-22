"""품질 지표 테스트.

핵심: 임계값이 없을 때 조용히 통과시키지 않는지 본다.
"""

from __future__ import annotations

from msk_engine.quality import (
    QualityMetrics,
    Thresholds,
    parse_ik_marker_errors,
    peak_residuals,
    rms,
)


class TestRms:
    def test_basic(self):
        assert rms([3.0, 4.0]) == 3.5355339059327378

    def test_empty_returns_none_not_zero(self):
        """빈 목록에 0.0 을 돌려주면 '오차 없음' 으로 오독된다."""
        assert rms([]) is None

    def test_ignores_nan(self):
        assert rms([float("nan"), 2.0]) == 2.0


class TestJudgement:
    def test_undecided_when_threshold_missing(self):
        metrics = QualityMetrics(marker_rms_m=0.02).judge(Thresholds.undecided())
        assert metrics.verdicts["marker_rms"] == "undecided"
        assert metrics.passed is None
        assert metrics.notes

    def test_pass_and_fail(self):
        thresholds = Thresholds(marker_rms_m=0.02, residual_force_n=25.0)
        good = QualityMetrics(marker_rms_m=0.01, residual_force_n=10.0).judge(thresholds)
        assert good.verdicts["marker_rms"] == "pass"
        assert good.verdicts["residual_force"] == "pass"

        bad = QualityMetrics(marker_rms_m=0.05, residual_force_n=10.0).judge(thresholds)
        assert bad.verdicts["marker_rms"] == "fail"
        assert bad.passed is False

    def test_passed_is_none_when_any_undecided(self):
        metrics = QualityMetrics(marker_rms_m=0.01).judge(
            Thresholds(marker_rms_m=0.02)
        )
        # residual 임계값이 없으므로 전체 판정은 보류
        assert metrics.passed is None

    def test_as_dict_round_trip(self):
        metrics = QualityMetrics(marker_rms_m=0.01).judge(Thresholds(marker_rms_m=0.02))
        data = metrics.as_dict()
        assert data["marker_rms_m"] == 0.01
        assert "verdicts" in data


class TestParseIkMarkerErrors:
    def test_reads_rms_and_max(self, sto_factory):
        path = sto_factory(
            "ik_marker_errors.sto",
            ["time", "marker_error_RMS", "marker_error_max"],
            [[0.0, 0.01, 0.02], [0.01, 0.03, 0.05]],
        )
        metrics = parse_ik_marker_errors(path)
        assert metrics.marker_rms_m is not None
        assert metrics.marker_max_m == 0.05

    def test_missing_file_records_note(self, tmp_path):
        metrics = parse_ik_marker_errors(tmp_path / "absent.sto")
        assert metrics.marker_rms_m is None
        assert metrics.notes

    def test_missing_column_records_note(self, sto_factory):
        path = sto_factory("ik.sto", ["time", "something_else"], [[0.0, 1.0]])
        metrics = parse_ik_marker_errors(path)
        assert metrics.marker_rms_m is None
        assert any("RMS" in n for n in metrics.notes)


class TestPeakResiduals:
    def test_computes_vector_magnitude(self, sto_factory):
        path = sto_factory(
            "id_forces.sto",
            ["time", "pelvis_tx_force", "pelvis_ty_force", "pelvis_tz_force"],
            [[0.0, 3.0, 4.0, 0.0], [0.01, 1.0, 1.0, 1.0]],
        )
        force, moment = peak_residuals(path)
        assert force == 5.0
        assert moment is None

    def test_missing_file(self, tmp_path):
        assert peak_residuals(tmp_path / "absent.sto") == (None, None)
