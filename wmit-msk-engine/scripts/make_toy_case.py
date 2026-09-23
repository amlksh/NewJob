#!/usr/bin/env python3
"""GUI 로 열어볼 수 있는 토이 케이스를 디스크에 만든다.

회귀 테스트(`tests/`)와 기준선 스크립트는 임시 폴더에서 돌고 끝나면 지운다.
그래서 OpenSim GUI 로 결과를 열어보려 해도 열 파일이 남지 않는다.
이 스크립트는 같은 토이 케이스를 **지워지지 않는 위치**에 만들어 둔다.

사용:
    python scripts/make_toy_case.py                 # 인체만
    python scripts/make_toy_case.py --device        # 무릎 보조기 착용
    python scripts/make_toy_case.py --out D:/demo   # 위치 지정
    python scripts/make_toy_case.py --no-run        # 입력만 만들고 해석은 생략

만들어지는 것:
    <out>/inputs/    토이 모델(.osim), 마커(.trc), 채워진 scale 템플릿, Case YAML
    <out>/runs/<run_id>/  해석 결과 — GUI 로 여는 대상

주의: 이것은 **토이 모델**이다. 실제 인체 모델도 계측 데이터도 아니므로
수치에 생리학적 의미가 없다. 파이프라인이 무엇을 만들어내는지 눈으로
확인하는 용도다. V&V 활동 V-13(GUI 대조)은 실데이터·실모델로 B-3 에서
수행하는 별개의 활동이며, 이 스크립트의 출력은 그 증거가 되지 않는다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
# 토이 모델 정의는 테스트 옆에 있다. 기준선 스크립트와 같은 정의를 쓴다.
sys.path.insert(0, str(REPO_ROOT / "tests"))

import toy_model  # noqa: E402
from msk_engine.pipeline import CaseSpec, run_case  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GUI 확인용 토이 케이스 생성")
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "runs" / "toy_demo"),
        help="만들 위치 (기본: runs/toy_demo — git 제외 대상)",
    )
    parser.add_argument("--device", action="store_true", help="무릎 보조기를 결합한다")
    parser.add_argument("--no-run", action="store_true", help="입력만 만들고 해석은 건너뛴다")
    args = parser.parse_args(argv)

    out = Path(args.out).expanduser().resolve()
    inputs = out / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)

    print(f"토이 케이스를 만듭니다: {out}")
    built = toy_model.build_reference_inputs(inputs, REPO_ROOT)
    device_spec = built["device"] if args.device else None

    case_file = toy_model.write_case_yaml(
        inputs / "case.yaml",
        built["model"],
        built["gait"],
        built["templates"],
        scale_template=built["scale_template"],
        static_trial=built["static"],
        device_spec=device_spec,
    )
    print(f"  입력    : {inputs}")
    print(f"  Case    : {case_file}")
    print(f"  기기 결합: {'예' if args.device else '아니오'}")

    if args.no_run:
        print("\n--no-run 이므로 해석은 건너뜁니다.")
        return 0

    result = run_case(CaseSpec.from_yaml(case_file), runs_root=out / "runs")
    if result.status != "ok":
        print(f"\n해석이 '{result.status}' 로 끝났습니다. {result.run_dir} 를 확인하십시오.")
        return 1

    _print_gui_guide(result)
    return 0


def _print_gui_guide(result) -> None:
    """GUI 에서 무엇을 어떤 순서로 열면 되는지."""
    outputs = result.outputs
    print(f"\n해석 완료: {result.run_dir}")

    print("\n── OpenSim GUI 에서 열 순서 ─────────────────────────")
    print("1) File > Open Model...")
    print(f"     {outputs['analysis_model']}")
    print("2) File > Load Motion...   (모델을 선택한 상태에서)")
    print(f"     {outputs['ik_motion']}")
    print("   → 타임라인 재생 버튼으로 동작을 볼 수 있습니다.")
    print("3) Tools > Plot...  으로 결과를 그래프로 봅니다.")
    for label, key in (
        ("관절 모멘트", "id_forces"),
        ("근육력·기기 하중", "so_forces"),
        ("관절반력", "jr_reaction"),
    ):
        print(f"     {label:16s} {outputs[key]}")

    print("\n── 요약 수치 ────────────────────────────────────────")
    summary = result.summary
    for item in summary.range_of_motion:
        print(f"   ROM  {item.coordinate:12s} {item.minimum:7.2f} ~ {item.maximum:7.2f} {item.unit}")
    for item in summary.joint_moments:
        print(f"   모멘트 {item.name:22s} 최대 {item.peak_absolute:8.3f} {item.unit}")
    for item in summary.muscle_forces:
        print(f"   근육력 {item.name:22s} 최대 {item.peak_absolute:8.3f} {item.unit}")
    for item in summary.device_loads:
        print(f"   기기   {item.name:22s} 최대 {item.peak_absolute:8.3f} {item.unit}")
    for item in summary.joint_reactions:
        force = "미산출" if item.peak_force_n is None else f"{item.peak_force_n:8.3f} N"
        print(f"   반력   {item.label:22s} 최대 {force} ({item.expressed_in} 좌표계)")

    print(f"\n   전체 요약: {result.summary_path}")
    print("\n※ 토이 모델입니다 — 수치에 생리학적 의미는 없습니다.")
    print("  V-13(GUI 대조)은 실데이터로 B-3 에서 하는 별개 활동입니다.")


if __name__ == "__main__":
    raise SystemExit(main())
