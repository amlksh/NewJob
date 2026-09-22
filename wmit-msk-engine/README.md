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

pip install -e ".[dev,opensim]"   # OpenSim 4.6 까지
pytest -q                         # 통합 테스트 포함
```

OpenSim까지 포함한 실행은 컨테이너를 권장한다.

```bash
docker build -t wmit-msk -f docker/Dockerfile .
docker run --rm -v "$PWD/data:/app/data" -v "$PWD/runs:/app/runs" wmit-msk \
    python scripts/run_poc.py --case configs/cases/kneeloads_example.yaml
```

## 현재 상태

파이프라인 골격, 입력 검증, 재현성 기록, 품질 지표 계산이 구현되어 있고,
IK → ID → SO → JR 네 단계는 OpenSim 4.6 으로 실제 실행을 확인했다
(`tests/test_opensim_integration.py`, 토이 모델 기준).

Scaling 은 템플릿을 채우기 전까지 돌지 않는다. `configs/templates/scale_setup.xml` 의
`MeasurementSet` 과 `MarkerPlacer` 의 `IKTaskSet` 이 비어 있기 때문이다.

특히 `MarkerPlacer` 의 `IKTaskSet` 이 비어 있으면 OpenSim 4.6 은 예외가 아니라
**segmentation fault** 로 죽는다. 프로세스가 통째로 사라져 예외 처리도
`provenance.json` 기록도 돌지 않으므로, `steps.check_marker_placer_tasks()` 가
도구를 부르기 전에 이 조건을 잡아 `StepExecutionError` 로 멈춘다.

실제 데이터를 붙일 때 맞춰야 하는 자리는 다음과 같다.

| 자리 | 파일 | 내용 |
| --- | --- | --- |
| 측정 항목 | `configs/templates/scale_setup.xml` | `MeasurementSet` — 모델·마커셋에 맞는 스케일 측정 정의 |
| 마커 가중치 | `scale_setup.xml`, `ik_setup.xml` | `IKTaskSet` — 근거를 ADR 로 남기고 정할 것 |
| GRF 열 이름 | `configs/templates/external_loads.xml` | `force_identifier` 등, 데이터셋마다 다름 |
| 모델 body 이름 | `external_loads.xml`, `jr_setup.xml` | `applied_to_body`, `joint_names`, `express_in_frame` |
| 마커 이름 | `configs/cases/*.yaml` | `required_markers` |
| 합격기준 | `configs/cases/*.yaml` | `thresholds` — ADR-0003 확정 전까지 `TBD` |

### OpenSim 과의 계약 (실측으로 확인한 것)

아래는 코드만 읽어서는 드러나지 않고, 틀리면 **도구가 성공을 반환하면서도
결과가 비는** 항목이다. `tests/test_opensim_integration.py` 가 회귀를 막는다.

- Setup XML 의 경로는 절대경로여야 한다. OpenSim 은 Setup XML 이 있는
  디렉터리로 작업 디렉터리를 옮기므로, 상대경로 출력은 조용히 사라진다.
- 해석 구간은 반드시 치환해야 한다. `0 0` 이면 한 프레임만 풀린다.
- 분석 결과 파일 이름은 OpenSim 이 정한다 — `<도구이름>_<분석이름>_<항목>.sto`.
  설정으로 바꿀 수 없어 `steps.analysis_output_path()` 가 렌더된 XML 에서 유도한다.
  IK 마커 오차도 같다 — `<도구이름>_ik_marker_errors.sto`.
- GRF 가 없으면 `external_loads_file` 은 `Unassigned` 여야 한다.
  없는 파일을 가리키면 도구가 파일 열기에 실패한다.

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
