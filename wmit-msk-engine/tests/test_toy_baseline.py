"""토이 케이스 회귀 기준선 검증 (V-01 증거).

이 테스트가 지키는 것:

  실데이터 해석 결과가 나빠졌을 때, **파이프라인이 바뀐 것인지 데이터가 나쁜
  것인지** 가를 기준이 필요하다. 입력이 완전히 고정된 토이 케이스가 그 기준선이다.
  여기가 그대로인데 실데이터가 나빠졌다면 데이터·모델 쪽을 보고,
  여기가 움직였다면 파이프라인을 먼저 본다.

기준선 파일은 `tests/baselines/*.json` 이며 `scripts/refresh_toy_baseline.py`
로만 갱신한다. 테스트가 스스로 고쳐 쓰지 않는다 — 조용히 갱신되면 회귀를
잡는 의미가 없다.

수치가 어긋났을 때 `baseline.report()` 가 무엇이 얼마나 움직였는지와
환경(OpenSim 버전)이 바뀌었는지를 함께 알려준다. 버전이 바뀌면 수치가
달라질 수 있다는 것은 ADR-0001 에 적혀 있다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import toy_model
from msk_engine import baseline

# OpenSim 이 필요한 것은 파이프라인을 실제로 돌리는 것뿐이다. 기준선 파일을
# 읽고 비교하는 부분은 OpenSim 없이도 돌아야 한다 — CI 기본이 그 환경이다.
BASELINE_DIR = Path(__file__).resolve().parent / "baselines"


@pytest.fixture(scope="module")
def reference_runs(tmp_path_factory, request):
    """기준 케이스 전체를 한 번만 돌려 모듈 안에서 공유한다."""
    repo_root = Path(request.config.rootdir)
    workdir = tmp_path_factory.mktemp("baseline")
    inputs = toy_model.build_reference_inputs(workdir, repo_root)
    return {
        name: toy_model.run_reference_case(name, with_device, inputs, workdir)
        for name, (_, with_device) in toy_model.REFERENCE_CASES.items()
    }


@pytest.mark.opensim
@pytest.mark.parametrize("name", sorted(toy_model.REFERENCE_CASES))
class TestFrozenBaseline:
    def test_matches_committed_baseline(self, name, reference_runs):
        """고정된 수치와 이번 실행이 같아야 한다.

        어긋나면 파이프라인이 바뀐 것이다. 의도한 변경이면 기준선을 갱신하고
        그 diff 를 커밋에 남긴다.
        """
        recorded = baseline.load(BASELINE_DIR / f"{name}.json")
        current = baseline.extract(reference_runs[name])
        deviations = baseline.compare(recorded, current)
        assert not deviations, "\n" + baseline.report(recorded, deviations)

    def test_run_is_reproducible(self, name, reference_runs):
        """같은 입력을 두 번 뽑아도 같은 수치가 나와야 한다.

        재현되지 않으면 기준선을 고정하는 것 자체가 의미가 없다.
        """
        first = baseline.extract(reference_runs[name])
        second = baseline.extract(reference_runs[name])
        assert first == second


class TestBaselineMechanism:
    """기준선 장치 자체가 회귀를 잡을 수 있는지."""

    def test_detects_a_changed_value(self):
        recorded = baseline.load(BASELINE_DIR / "toy_human.json")
        tampered = dict(recorded["values"])
        key = "muscle.knee_musc.peak"
        tampered[key] = tampered[key] * 1.01  # 1% 변화
        deviations = baseline.compare(recorded, tampered)
        assert [d.key for d in deviations] == [key]
        assert deviations[0].kind == "changed"

    def test_detects_a_dropped_qoi(self):
        """QoI 가 조용히 사라지는 것이 값이 바뀌는 것보다 위험하다."""
        recorded = baseline.load(BASELINE_DIR / "toy_human.json")
        tampered = dict(recorded["values"])
        del tampered["reaction.knee_on_shank_in_shank.force"]
        deviations = baseline.compare(recorded, tampered)
        assert [d.kind for d in deviations] == ["missing"]

    def test_detects_an_added_quantity(self):
        recorded = baseline.load(BASELINE_DIR / "toy_human.json")
        tampered = {**recorded["values"], "muscle.new_muscle.peak": 1.0}
        deviations = baseline.compare(recorded, tampered)
        assert [d.kind for d in deviations] == ["added"]

    def test_tolerance_absorbs_float_noise_only(self):
        recorded = baseline.load(BASELINE_DIR / "toy_human.json")
        key = "muscle.knee_musc.peak"
        noise = {**recorded["values"], key: recorded["values"][key] * (1 + 1e-9)}
        assert not baseline.compare(recorded, noise)

    def test_report_names_the_environment(self):
        recorded = baseline.load(BASELINE_DIR / "toy_human.json")
        tampered = {**recorded["values"], "muscle.knee_musc.peak": 1.0}
        text = baseline.report(recorded, baseline.compare(recorded, tampered))
        assert "muscle.knee_musc.peak" in text
        assert "opensim" in text
        assert "refresh_toy_baseline" in text

    def test_schema_mismatch_is_refused(self, tmp_path):
        """구조가 바뀐 옛 기준선을 조용히 읽으면 비교가 거짓이 된다."""
        import json

        path = tmp_path / "old.json"
        path.write_text(json.dumps({"schema": 0, "values": {}}), encoding="utf-8")
        with pytest.raises(ValueError) as exc:
            baseline.load(path)
        assert "구조 버전" in str(exc.value)


class TestBaselineContent:
    """기준선이 실제로 QoI 4종을 담고 있는지. OpenSim 없이 확인한다."""

    @pytest.mark.parametrize("name", sorted(toy_model.REFERENCE_CASES))
    def test_records_the_environment_it_was_made_in(self, name):
        """어긋났을 때 가장 먼저 확인할 것이 OpenSim 버전이다 (ADR-0001)."""
        recorded = baseline.load(BASELINE_DIR / f"{name}.json")
        assert recorded["environment"]["opensim"] == "4.6"

    @pytest.mark.parametrize("name", sorted(toy_model.REFERENCE_CASES))
    def test_covers_all_four_qois(self, name):
        values = baseline.load(BASELINE_DIR / f"{name}.json")["values"]
        for prefix in ("rom.", "moment.", "muscle.", "reaction."):
            assert any(k.startswith(prefix) for k in values), f"{name}: {prefix} 없음"

    def test_device_case_freezes_the_device_load(self):
        values = baseline.load(BASELINE_DIR / "toy_device.json")["values"]
        assert any(k.startswith("device.") for k in values)

    def test_device_case_shows_lower_muscle_force_than_human_only(self):
        """기준선 자체가 결합의 방향성을 기록한다.

        이 관계가 뒤집히면 결합이 역학적으로 망가진 것이며, 수치 비교보다
        먼저 드러나야 한다.
        """
        human = baseline.load(BASELINE_DIR / "toy_human.json")["values"]
        device = baseline.load(BASELINE_DIR / "toy_device.json")["values"]
        key = f"muscle.{toy_model.MUSCLE}.peak"
        assert device[key] < human[key]
