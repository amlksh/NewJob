# CLAUDE.md — WMIT MSK Simulation Engine (OpenSim)

이 파일은 Claude Code가 이 저장소에서 작업할 때 따르는 규칙이다. 사람이 읽어도 과제 개요서 역할을 한다.

## 1. 과제 맥락

- 과제: WMIT 통합플랫폼용 OpenSim 기반 근골격(MSK) 시뮬레이션 엔진 구축 — VPK PLM기술팀
- 1차 목표: WMIT 서버에서 **무릎 가상환자 해석(Scale → Device → IK → ID → SO → JR)을 웹으로 실행하고 결과를 조회**하는 수준
- 1차 Reference 사용 사례: **무릎 재활 보조기 착용 해석**. 인체-기기 결합은 P1 범위 안이며 방식은 ADR-0004 (Tier 1: 용접 결합 + 좌표 구동)
- 1차 산출 QoI: 관절가동범위(ROM), 관절 모멘트, 근육력, 관절반력 — `results/summary.json`
- 1차 범위 제외: Virtual Cohort 대량 생성, **Abaqus 자동 연계**, 영상 기반 모션캡처, AI Agent
  - Abaqus 연계는 별도 모듈로 분리한다. `src/msk_engine/` 에 FE 관련 코드를 넣지 않는다.
    관절반력을 경골 좌표계로 남기는 것까지가 P1 의 준비 작업이다.
- 설계 문서: 「OpenSim MSK 시뮬레이션 엔진 개발 프로세스 설계」(Claude Docs). 단계·게이트·V&V 기준은 그 문서가 원본이며, 이 파일과 충돌하면 그 문서를 따르고 이 파일을 고친다.

**현재 단계: P1 기술검증 PoC.** G1 통과 기준:

1. Grand Challenge 데이터 1개 gait trial을 이 파이프라인으로 재현
2. OpenSim 기준 버전·Reference 모델 확정 (ADR로 기록)
3. V&V 계획서 승인, API 계약서(OpenAPI) 초안

## 2. 기술 기준

- OpenSim **4.6** — `pip install opensim`. PyPI 공식 wheel이 Linux(glibc 2.27+, x86-64) / Python 3.11–3.13으로 제공된다.
- Python 3.11 기본. 실행 환경의 기준은 `docker/Dockerfile`이다. 로컬 결과와 컨테이너 결과가 다르면 컨테이너가 정답이다.
- 기본 모델: Rajagopal 계열 전신 모델. OpenSim-JAM(Lenhart2015, COMAK)은 `poc/jam/`에서 호환성 시험만 한다. 본 파이프라인에 섞지 않는다.
- OpenSim 도구는 **Setup XML 기반으로 실행**한다. Python에서 속성을 하나씩 세팅하지 말고 `configs/templates/`의 XML을 채워 도구에 넘긴다. 이유: GUI 재현(코드 검증)과 V&V 추적이 쉬워진다.

## 3. 저장소 구조

```
src/msk_engine/      해석 엔진 패키지 (웹 계층 의존성 금지)
  pipeline.py        단계 실행 오케스트레이션
  steps.py           Scale/IK/ID/SO/JR 단계별 실행
  inputs.py          입력 검증 (마커명, 단위, 결측, GRF 동기화)
  outputs.py         QoI 추출 (ROM, 관절 모멘트, 근육력, 관절반력) → summary.json
  provenance.py      재현성 기록 (버전, 입력 해시, 설정 XML)
  quality.py         품질 지표 (마커 RMS, 잔차력), STO/MOT 읽기
  errors.py          예외 정의
  device/            의료기기 결합
    spec.py          CAD → 해석 파라미터 스키마 (질량, 관성, 부착점, 축, ROM, 구동)
    builder.py       인체 모델에 기기를 붙여 해석 모델 생성
configs/templates/   Setup XML 템플릿 (단계별)
configs/cases/       Case 정의 YAML
configs/devices/     기기 파라미터 YAML (CAD 에서 내보낸 값)
models/              모델 파일 — 라이선스 대장에 등록된 것만
data/                외부 데이터 — git 제외 (data/README.md 참조)
runs/                해석 결과 — git 제외
scripts/run_poc.py   PoC 실행 진입점
tests/               pytest (toy_model.py 는 통합 테스트용 최소 모델)
docs/decisions/      ADR (기술 결정 기록)
docs/interfaces/     외부 인터페이스 사양 (CAD → 기기 파라미터)
docs/vv/             V&V 추적표, 검증 결과
docs/license_register.md   모델·플러그인·데이터 라이선스 대장
poc/jam/             OpenSim-JAM 호환성 시험 (격리)
```

## 4. 작업 규칙

### 반드시

- 모든 해석 실행은 `runs/<run_id>/`에 결과와 함께 `provenance.json`을 남긴다: OpenSim 버전, Python 버전, 입력 파일 SHA-256, 사용한 설정 XML 사본, git commit.
- 새 모델·플러그인·데이터셋을 추가하기 전에 `docs/license_register.md`에 행을 추가한다. OpenSim API는 Apache 2.0이지만 **모델·예제·플러그인은 각자 라이선스가 다르다.**
- 기술 선택(버전, 모델, 알고리즘, 합격기준)은 `docs/decisions/ADR-NNNN-*.md`로 남긴다.
- 좌표계와 단위를 결과 메타데이터에 명시한다. 관절반력은 **경골(tibia) 좌표계** 표현을 기본으로 한다 (향후 FE 경계조건 연계).
- 결과 수치를 보고할 때 품질 지표(마커 RMS 오차, 잔차력·잔차모멘트)를 함께 보고한다.
- 기기는 **스케일링 다음에** 붙인다. 기기 치수는 CAD 로 고정되어 있으므로 피험자에 맞춰 늘리지 않는다.
- 기기 결과를 보고할 때 ADR-0004 의 적용 한계(강체 부착, 기기 내부 하중 없음,
  축 어긋남 구속력 없음, assistive 토크는 최적화 결과)를 함께 말한다.
- 기기 파라미터를 바꾸면 `source.revision` 을 갱신한다. `TBD` 인 기기로 낸 결과는 대외 인용·납품에 쓰지 않는다.

### 금지

- 합격기준 수치를 근거 없이 코드나 문서에 박지 않는다. 미정이면 `TBD`로 두고 ADR에서 근거와 함께 정한다.
- `data/`, `runs/`의 원본 데이터·결과를 git에 커밋하지 않는다. 환자 데이터는 비식별 상태로만 다룬다.
- 검증 데이터(Grand Challenge 계측 접촉력)를 모델 튜닝에 쓰지 않는다. 튜닝용과 검증용 trial을 분리하고 `docs/vv/traceability.md`에 기록한다.
- 해석이 실패했는데 성공처럼 보이는 결과를 만들지 않는다. 도구가 실패하면 예외로 멈추고 로그를 남긴다. 결측값을 임의 보간으로 메우지 않는다.

### 검증 방법

- 코드 변경 후: `pytest -q` (OpenSim 미설치 환경에서는 `pytest -q -m "not opensim"`)
- 파이프라인 변경 후: 기준 Case를 다시 돌려 이전 `runs/` 결과와 수치 비교(회귀). 차이가 나면 원인을 설명할 수 있어야 한다.
- 코드 검증(V&V): 같은 입력·같은 Setup XML을 OpenSim GUI로 돌린 결과와 일치해야 한다.

## 5. 자주 쓰는 명령

```bash
pip install -e ".[dev]"                     # 로컬 설치
pytest -q                                   # 테스트
python scripts/run_poc.py --case configs/cases/kneeloads_example.yaml
python scripts/run_poc.py --case configs/cases/knee_rehab_device_example.yaml   # 기기 착용
docker build -t wmit-msk -f docker/Dockerfile .
docker run --rm -v "$PWD/data:/app/data" -v "$PWD/runs:/app/runs" wmit-msk \
    python scripts/run_poc.py --case configs/cases/kneeloads_example.yaml
```

## 6. 열린 결정 (G1 전 확정)

- [ ] Reference 모델: Rajagopal 계열 확정 여부, JAM 1차 포함 여부
- [ ] Grand Challenge 사용 trial (튜닝용 / 검증용 분리)
- [ ] 검증 합격기준 (파형 상관, RMSE) — 문헌 근거로 ADR 작성
- [ ] WMIT 서버 OS·사양, 외부망 정책
- [ ] 기기 결합 Tier 2(기기 자체 자유도 + 구속조건)로 갈 조건 — ADR-0004
- [ ] 실제 재활 보조기 CAD 파라미터 확보 (현재 `configs/devices/` 는 예시값)
