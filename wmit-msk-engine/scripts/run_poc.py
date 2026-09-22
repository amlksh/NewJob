#!/usr/bin/env python3
"""P1 PoC 실행 진입점.

사용 예:
    python scripts/run_poc.py --case configs/cases/kneeloads_example.yaml
    python scripts/run_poc.py --case configs/cases/kneeloads_example.yaml --dry-run

--dry-run 은 입력 검증과 Setup XML 생성까지만 수행하고 OpenSim 을 부르지 않는다.
OpenSim 없는 환경에서 설정을 점검할 때 쓴다.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from msk_engine.errors import MskEngineError  # noqa: E402
from msk_engine.pipeline import CaseSpec, run_case  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WMIT MSK 해석 PoC 실행")
    parser.add_argument("--case", required=True, help="Case YAML 경로")
    parser.add_argument("--runs-root", default=str(REPO_ROOT / "runs"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="검증과 Setup XML 생성까지만 수행 (OpenSim 미호출)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        case = CaseSpec.from_yaml(args.case)
        result = run_case(
            case,
            runs_root=args.runs_root,
            repo_root=REPO_ROOT,
            dry_run=args.dry_run,
        )
    except MskEngineError as exc:
        print(f"\n실패: {exc}", file=sys.stderr)
        return 1

    _report(result)
    return 0 if result.status in {"ok", "dry_run"} else 1


def _report(result) -> None:
    print()
    print(f"run_id : {result.run_id}")
    print(f"상태    : {result.status}")
    print(f"결과    : {result.run_dir}")

    if result.validation.warnings:
        print("\n경고:")
        for warning in result.validation.warnings:
            print(f"  - {warning}")

    if result.validation.errors:
        print("\n오류:")
        for error in result.validation.errors:
            print(f"  - {error}")

    if result.status == "ok":
        print("\n단계:")
        for step in result.steps:
            print(f"  {step.name:6s} {step.status:4s} {step.duration_s:>8.2f}s")

        _report_device(result)
        _report_qoi(result)

        print("\n품질 지표:")
        print(json.dumps(result.quality.as_dict(), indent=2, ensure_ascii=False))

        if result.quality.passed is None:
            print(
                "\n주의: 임계값이 정해지지 않아 품질 판정을 내리지 않았다. "
                "ADR-0003 에서 합격기준을 확정할 것."
            )
        elif result.quality.passed is False:
            print("\n주의: 품질 지표가 임계값을 벗어났다. 결과를 그대로 인용하지 말 것.")


def _report_device(result) -> None:
    """기기 결합 결과와 경고. 경고는 결과 해석에 영향을 주므로 함께 보여준다."""
    build = result.device_build
    if not build:
        return

    print("\n기기 결합:")
    print(f"  모델      : {build['model_file']}")
    print(f"  추가 강체 : {', '.join(build['added_bodies']) or '없음'}")
    print(f"  추가 힘   : {', '.join(build['added_forces']) or '없음'}")
    misalignment = build.get("hinge_misalignment_deg")
    if misalignment is not None:
        print(f"  힌지 정합 : 인체 관절 축과 {misalignment:.1f}° 차이")
    for warning in build.get("warnings", []):
        print(f"  ⚠ {warning}")


def _report_qoi(result) -> None:
    """QoI 4종 요약. 자세한 값은 results/summary.json 에 있다."""
    summary = result.summary
    if summary is None:
        return

    print("\n결과 요약 (QoI):")

    print("  관절가동범위:")
    for item in summary.range_of_motion:
        print(
            f"    {item.coordinate:24s} {item.minimum:8.2f} ~ {item.maximum:8.2f} "
            f"({item.span:.2f} {item.unit})"
        )

    print("  관절 모멘트/힘 (최대 절댓값):")
    for item in summary.joint_moments:
        print(f"    {item.name:24s} {item.peak_absolute:10.3f} {item.unit}")

    if summary.muscle_forces:
        print("  근육력 (최대, 상위 5):")
        top = sorted(summary.muscle_forces, key=lambda m: m.peak_absolute, reverse=True)
        for item in top[:5]:
            print(f"    {item.name:24s} {item.peak_absolute:10.3f} {item.unit}")

    if summary.device_loads:
        print("  기기 하중 (최대):")
        for item in summary.device_loads:
            print(f"    {item.name:24s} {item.peak_absolute:10.3f} {item.unit}")

    print("  관절반력 (최대):")
    for item in summary.joint_reactions:
        force = "미산출" if item.peak_force_n is None else f"{item.peak_force_n:10.3f} N"
        moment = "미산출" if item.peak_moment_nm is None else f"{item.peak_moment_nm:.3f} N*m"
        print(f"    {item.label:36s} {force}  모멘트 {moment}  ({item.expressed_in} 좌표계)")

    for note in summary.notes:
        print(f"  주의: {note}")

    if result.summary_path is not None:
        print(f"\n  전체 요약: {result.summary_path}")


if __name__ == "__main__":
    raise SystemExit(main())
