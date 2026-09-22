"""입력 검증 테스트.

핵심: 잘못된 입력이 조용히 통과하지 않는지 본다.
"""

from __future__ import annotations

import pytest

from msk_engine.errors import InputValidationError
from msk_engine.inputs import (
    SubjectInput,
    ValidationReport,
    validate_grf_sync,
    validate_subject,
    validate_trc,
)


class TestValidateSubject:
    def test_accepts_normal_adult(self, trc_factory):
        marker = trc_factory()
        report = validate_subject(
            SubjectInput(height_m=1.75, mass_kg=70.0, marker_file=marker)
        )
        assert report.ok

    def test_rejects_height_in_centimetres(self, trc_factory):
        """175 를 신장으로 넣으면 cm 를 m 로 착각한 것이다."""
        report = validate_subject(
            SubjectInput(height_m=175.0, mass_kg=70.0, marker_file=trc_factory())
        )
        assert not report.ok
        assert any("cm" in e for e in report.errors)

    def test_rejects_impossible_mass(self, trc_factory):
        report = validate_subject(
            SubjectInput(height_m=1.75, mass_kg=700.0, marker_file=trc_factory())
        )
        assert not report.ok

    def test_missing_marker_file_is_error(self, tmp_path):
        report = validate_subject(
            SubjectInput(
                height_m=1.75, mass_kg=70.0, marker_file=tmp_path / "nope.trc"
            )
        )
        assert not report.ok

    def test_missing_grf_warns_not_errors(self, trc_factory):
        """GRF 가 없어도 해석은 가능하나 결과 신뢰도가 떨어진다 — 경고."""
        report = validate_subject(
            SubjectInput(height_m=1.75, mass_kg=70.0, marker_file=trc_factory())
        )
        assert report.ok
        assert any("GRF" in w for w in report.warnings)

    def test_unsupported_extension(self, tmp_path):
        bad = tmp_path / "markers.csv"
        bad.write_text("a,b\n1,2\n", encoding="utf-8")
        report = validate_subject(
            SubjectInput(height_m=1.75, mass_kg=70.0, marker_file=bad)
        )
        assert not report.ok


class TestValidateTrc:
    def test_reads_header_and_markers(self, trc_factory):
        path = trc_factory(markers=["RASI", "LASI", "RKNE", "RANK"])
        report = validate_trc(path)
        assert report.ok
        assert report.facts["marker_count"] == 4
        assert report.facts["declared_units"] == "m"
        assert report.facts["frame_count"] == 10

    def test_missing_units_is_error(self, trc_factory):
        """단위를 추정하지 않는다 — 명시되어야 한다."""
        report = validate_trc(trc_factory(units=None))
        assert not report.ok
        assert any("Units" in e for e in report.errors)

    def test_unit_mismatch_detected(self, trc_factory):
        """m 로 선언했는데 값이 mm 크기면 잡아낸다."""
        path = trc_factory(units="m", scale=1000.0)
        report = validate_trc(path)
        assert not report.ok
        assert any("불일치" in e for e in report.errors)

    def test_consistent_mm_passes(self, trc_factory):
        report = validate_trc(trc_factory(units="mm", scale=1000.0))
        assert report.ok
        assert report.facts["inferred_units"] == "mm"

    def test_required_marker_missing(self, trc_factory):
        path = trc_factory(markers=["RASI", "LASI"])
        report = validate_trc(path, required_markers=["RASI", "RKNE"])
        assert not report.ok
        assert any("RKNE" in e for e in report.errors)

    def test_excess_missing_data_is_error(self, trc_factory):
        """결측이 많으면 임의 보간으로 메우지 않고 멈춘다."""
        missing = {(f, c) for f in range(10) for c in range(6)}
        path = trc_factory(markers=["A", "B", "C"], missing_at=missing)
        report = validate_trc(path, max_missing_fraction=0.1)
        assert not report.ok
        assert any("결측" in e for e in report.errors)

    def test_small_gaps_warn_only(self, trc_factory):
        path = trc_factory(markers=["A", "B", "C"], missing_at={(0, 0)})
        report = validate_trc(path, max_missing_fraction=0.1)
        assert report.ok
        assert report.warnings

    def test_truncated_file(self, tmp_path):
        path = tmp_path / "short.trc"
        path.write_text("PathFileType\t4\n", encoding="utf-8")
        report = validate_trc(path)
        assert not report.ok

    def test_records_time_range(self, trc_factory):
        report = validate_trc(trc_factory(frames=5))
        assert report.facts["time_range"] == [0.0, 0.04]


class TestGrfSync:
    def test_overlapping_ranges_pass(self):
        report = validate_grf_sync((0.0, 1.0), (0.0, 1.0))
        assert report.ok
        assert not report.warnings

    def test_disjoint_ranges_error(self):
        report = validate_grf_sync((5.0, 6.0), (0.0, 1.0))
        assert not report.ok

    def test_offset_ranges_warn(self):
        report = validate_grf_sync((0.0, 1.0), (0.5, 1.5))
        assert report.ok
        assert report.warnings

    def test_unknown_ranges_skip(self):
        report = validate_grf_sync(None, (0.0, 1.0))
        assert report.ok
        assert report.warnings


class TestValidationReport:
    def test_raise_if_failed(self):
        report = ValidationReport(errors=["bad"])
        with pytest.raises(InputValidationError) as exc:
            report.raise_if_failed()
        assert "bad" in str(exc.value)

    def test_merge_prefixes_messages(self):
        base = ValidationReport()
        other = ValidationReport(errors=["boom"], facts={"n": 1})
        base.merge(other, prefix="markers")
        assert base.errors == ["[markers] boom"]
        assert base.facts["markers.n"] == 1
