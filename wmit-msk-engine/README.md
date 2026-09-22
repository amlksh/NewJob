# WMIT MSK Simulation Engine — P1 PoC

WMIT 통합플랫폼용 OpenSim 기반 근골격 시뮬레이션 엔진. 현재 **P1 기술검증 PoC** 단계.

무릎 가상환자 해석 파이프라인(Scale → IK → ID → Static Optimization → Joint Reaction)을
서버에서 자동 실행하고, 재현성 기록과 품질 지표를 함께 남기는 것이 이 저장소의 범위다.
웹 계층(API 서버, UI)은 P2/P3에서 별도로 붙인다.

## 빠른 시작

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q -m "not opensim"        # OpenSim 없이도 도는 테스트
```

OpenSim까지 포함한 실행은 컨테이너를 권장한다.

```bash
docker build -t wmit-msk -f docker/Dockerfile .
docker run --rm -v "$PWD/data:/app/data" -v "$PWD/runs:/app/runs" wmit-msk \
    python scripts/run_poc.py --case configs/cases/kneeloads_example.yaml
```

## 현재 상태

파이프라인 골격, 입력 검증, 재현성 기록, 품질 지표 계산은 구현되어 있다.
`steps.py`의 각 OpenSim 도구 호출부는 **실제 데이터와 모델을 붙이면서 채워야 하는 자리**이며,
`NotImplementedError` 대신 조용히 통과하는 일이 없도록 표시해 두었다.

## 문서

| 문서 | 내용 |
| --- | --- |
| `CLAUDE.md` | 과제 맥락, 기술 기준, 작업 규칙 (Claude Code가 따르는 규칙) |
| `docs/decisions/` | ADR — 기술 결정 기록 |
| `docs/vv/traceability.md` | V&V 추적표 |
| `docs/license_register.md` | 모델·플러그인·데이터 라이선스 대장 |
| `data/README.md` | 외부 데이터 취득 방법 |

## 라이선스

이 저장소의 코드는 VPK 내부 과제 산출물이다.
OpenSim API는 Apache 2.0이나, **모델·예제·플러그인·데이터는 각자 라이선스를 따른다.**
`docs/license_register.md`를 먼저 확인할 것.
