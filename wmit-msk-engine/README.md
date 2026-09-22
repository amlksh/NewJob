# WMIT MSK Simulation Engine — P1 PoC

WMIT 통합플랫폼용 OpenSim 기반 근골격 시뮬레이션 엔진. 현재 **P1 기술검증 PoC** 단계.

무릎 가상환자 해석 파이프라인(Scale → **Device** → IK → ID → Static Optimization →
Joint Reaction)을 서버에서 자동 실행하고, 재현성 기록과 품질 지표를 함께 남기는 것이
이 저장소의 범위다. 1차 Reference 사용 사례는 **무릎 재활 보조기 착용 해석**이다.

웹 계층(API 서버, UI)은 P2/P3에서 별도로 붙인다.
**Abaqus 연계는 이 저장소에 구현하지 않는다** — 별도 모듈로 분리한다 (ADR-0004).

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

## 산출물

한 번 실행하면 `runs/<run_id>/` 아래에 다음이 남는다.

| 파일 | 내용 |
| --- | --- |
| `results/summary.json` | **QoI 4종** — 관절가동범위(ROM), 관절 모멘트, 근육력, 관절반력 + 인용 가부 |
| `results/*.mot`, `*.sto` | 단계별 원본 결과 (IK 관절각, ID 모멘트, SO 근육력, JR 반력) |
| `results/scaled_model.osim` | 개인화된 인체 모델 |
| `results/device_model.osim` | 기기가 붙은 해석 모델 (기기가 있을 때) |
| `results/scale_factors.xml` | 적용된 스케일 계수 |
| `setup/*.xml` | 실행에 쓰인 Setup XML 사본 (GUI 로 그대로 재현 가능) |
| `provenance.json` | OpenSim·Python 버전, 입력 SHA-256, git commit, 해석 구간 |
| `validation.json` | 입력 검증 결과 |

`summary.json` 에는 단위와 좌표계가 함께 실린다. 관절반력은 표현 좌표계
(기본 경골)를 모르면 숫자만으로 의미가 없기 때문이다.

`provenance.json` 과 `summary.json` 은 그 결과를 대외 인용·납품에 쓸 수 있는지도
기록한다. 기기 CAD 출처(`source.revision`)가 `TBD` 면 `citable: false` 와 사유가
남는다. 자세한 규칙은 `docs/vv/traceability.md` §인용 가부.

## 의료기기 결합

무릎 재활 보조기 같은 기기를 인체 모델에 붙여 착용 효과를 본다.

```bash
# 기기 없이
python scripts/run_poc.py --case configs/cases/kneeloads_example.yaml
# 기기 착용
python scripts/run_poc.py --case configs/cases/knee_rehab_device_example.yaml
```

두 실행의 `summary.json` 에서 `muscle_forces` 와 `joint_reactions` 를 비교하는 것이
기본 사용법이다.

기기 파라미터는 CAD 에서 내보낸 YAML 로 받는다. 스키마와 단위 규약은
`docs/interfaces/cad_device_parameters.md`, 결합 방식과 **적용 한계**는
`docs/decisions/ADR-0004-device-coupling.md` 에 있다.

기기 측에 자료를 요청할 때 보내는 문서와 템플릿은
`docs/interfaces/device_parameter_request/` 에 있다.

받는 값: 힌지 축, 가동범위(ROM), 질량, 관성, 부착점, 구동 조건
(보조 토크 / 지정 토크 / 수동 강성).

P1 결합은 **Tier 1** — 기기 강체를 인체 분절에 용접하고, 구동은 인체 좌표에
작용하는 액추에이터로 표현한다. 자유도를 늘리지 않으므로 닫힌 운동 사슬이
생기지 않는다. 기기 내부 부재 하중은 나오지 않으며, 그것이 필요해지면
Tier 2 로 간다 (ADR-0004).

## 현재 상태

**Scale → Device → IK → ID → SO → JR 전체가 OpenSim 4.6 에서 도는 것을 확인했다**
(`tests/test_device_integration.py`, 토이 모델 기준).

확인한 내용 (**코드 검증** — 파이프라인이 OpenSim 을 올바르게 부르는가):

- 모델 자신에게서 만든 마커로 스케일링하면 **스케일 계수가 1** 로 나온다
- IK 가 원래 관절각을 되찾는다 (마커 RMS 오차 ~1e-6 m)
- 기기를 붙여도 **자유도가 늘지 않는다** (Tier 1 용접 결합)
- 기기 질량이 무릎 모멘트를 **키운다**
- 보조 토크가 근육 대신 하중을 받아 **근육력이 줄어든다**
- 기기 토크가 `max_torque_nm` 을 넘지 않는다

수치는 `tests/baselines/*.json` 에 **회귀 기준선**으로 고정되어 있다 (V-01).
실데이터 결과가 나빠졌을 때 파이프라인이 바뀐 것인지 데이터가 나쁜 것인지
가르는 기준이다. 갱신은 `scripts/refresh_toy_baseline.py` 로만 한다.

**확인하지 못한 것:**

- **기기 결합 검증은 미착수다** (V-10, V-11). 위 항목은 결합 *메커니즘*이
  의도대로 동작하는지를 토이 모델로 본 코드 검증이며, 실제 기기로 결합
  타당성을 확인한 것이 아니다.
- **실제 데이터 재현도 미착수다** (V-12). 위는 전부 토이 모델 기준이다.
- 실제 인체 모델(Rajagopal)은 라이선스 대장을 채우기 전까지 저장소에 두지 않는다.
- `configs/devices/` 의 값은 예시값이며, 그것으로 낸 결과는 `citable: false` 로
  표시되어 대외 인용·납품에 쓸 수 없다.

`configs/templates/scale_setup.xml` 의 `MeasurementSet` 과 `MarkerPlacer` 의
`IKTaskSet` 은 비어 있다 — 모델·마커셋마다 내용이 달라 채워 써야 하는 자리다.
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
| 관절반력 대상 관절 | `configs/cases/*.yaml` | `joint_reaction_joints` — 틀리면 빈 결과가 되므로 엔진이 잡는다 |
| 기기 질량·관성·부착점 | `configs/devices/*.yaml` | CAD 값으로 교체. 예시값으로 낸 결과는 인용 금지 |
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
- `JointReaction` 은 `joint_names` 가 모델과 안 맞아도 오류를 내지 않는다.
  `time` 열만 있는 파일을 쓰고 성공을 반환하므로, 파일 존재만 확인하면
  '관절반력 해석 완료' 로 보이면서 값이 없다.
- `ScaleTool` 의 `MarkerPlacer` 는 `IKTaskSet` 이 비면 **segmentation fault** 로 죽는다.

## 문서

| 문서 | 내용 |
| --- | --- |
| `CLAUDE.md` | 과제 맥락, 기술 기준, 작업 규칙 (Claude Code가 따르는 규칙) |
| `docs/decisions/` | ADR — 기술 결정 기록 (ADR-0004: 기기 결합 방식과 적용 한계) |
| `docs/interfaces/` | CAD → 해석 기기 파라미터 인터페이스 |
| `docs/vv/traceability.md` | V&V 추적표 |
| `docs/license_register.md` | 모델·플러그인·데이터 라이선스 대장 |
| `data/README.md` | 외부 데이터 취득 방법 |

## 라이선스

이 저장소의 코드는 VPK 내부 과제 산출물이다.
OpenSim API는 Apache 2.0이나, **모델·예제·플러그인·데이터는 각자 라이선스를 따른다.**
`docs/license_register.md`를 먼저 확인할 것.
