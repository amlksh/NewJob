#!/usr/bin/env python3
"""토이 케이스 회귀 기준선을 다시 만든다.

기준선은 **의도적으로만** 갱신한다. 파이프라인을 일부러 바꿨을 때 이 스크립트를
돌리고, 바뀐 수치의 diff 를 커밋에 남겨 검토받는다. 테스트가 스스로 고쳐 쓰지
않는 이유가 이것이다 — 조용히 갱신되면 회귀를 잡는 의미가 없다.

사용:
    python scripts/refresh_toy_baseline.py            # 무엇이 바뀌는지 보여주기만 한다
    python scripts/refresh_toy_baseline.py --write    # 실제로 기준선 파일을 갱신한다

기준선이 무엇을 고정하는지는 `src/msk_engine/baseline.py` 를 볼 것.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
# 토이 모델은 이것을 쓰는 테스트 옆에 둔다. 기준선 생성과 검증이 같은
# 모델 정의를 쓰도록 여기서 가져온다 — 정의가 둘로 갈라지면 기준선이 거짓이 된다.
sys.path.insert(0, str(REPO_ROOT / "tests"))

import toy_model  # noqa: E402
from msk_engine import baseline  # noqa: E402

BASELINE_DIR = REPO_ROOT / "tests" / "baselines"

CASES = toy_model.REFERENCE_CASES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="토이 회귀 기준선 갱신")
    parser.add_argument(
        "--write", action="store_true", help="기준선 파일을 실제로 덮어쓴다"
    )
    args = parser.parse_args(argv)

    changed = False
    with tempfile.TemporaryDirectory() as raw:
        workdir = Path(raw)
        inputs = toy_model.build_reference_inputs(workdir, REPO_ROOT)

        for name, (description, with_device) in CASES.items():
            result = toy_model.run_reference_case(name, with_device, inputs, workdir)
            payload = baseline.build(result, name, description)
            target = BASELINE_DIR / f"{name}.json"

            print(f"\n=== {name} ({description}) ===")
            if target.is_file():
                previous = baseline.load(target)
                deviations = baseline.compare(previous, payload["values"])
                if deviations:
                    changed = True
                    print(baseline.report(previous, deviations))
                else:
                    print("  기존 기준선과 같다 — 갱신할 것이 없다.")
            else:
                changed = True
                print(f"  새 기준선 ({len(payload['values'])} 개 항목)")

            if args.write:
                baseline.write(payload, target)
                print(f"  기록: {target.relative_to(REPO_ROOT)}")

    if not args.write and changed:
        print(
            "\n바뀐 내용이 있다. 의도한 변경이면 --write 로 갱신하고 "
            "diff 를 커밋에 남길 것."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
