# DTOS Reference Architecture (3~5년 장기 청사진)

> 본 문서는 01~06 문서(MVP~Phase 4 실행 설계)의 상위 문서로, VPK가 장기 보유할 **Digital Twin Operating System 플랫폼**의 참조 아키텍처를 정의한다.
> 원칙: **MVP에서 만든 것을 버리지 않고 승격(promote)한다.** 각 장 끝에 "MVP → 플랫폼 진화 경로"를 명시했다.

---

## 1. 비전과 범위

### 1.1 3~5년 후 DTOS가 되어야 하는 것

- **운영체제 은유의 실현**: OS가 프로세스·파일·디바이스를 관리하듯, DTOS는 **트윈(Twin)·자산(Asset)·에이전트(Agent)·시뮬레이션(Simulation)** 을 관리하는 실행 기반이 된다.
- 개별 프로젝트의 자동화 도구가 아니라, **여러 도메인(의료기기·자동차·로봇·제조)의 디지털트윈이 등록·버전관리·실행·검증되는 단일 플랫폼**.
- **Digital Twin 중심 아키텍처**: 플랫폼의 1차 구성 단위는 도구가 아니라 **Digital Twin Plugin**(FMH → Diabetes → Hearing/Spine/Battery → Robot)이다. 첫 번째 플러그인은 FMH Digital Twin이며 MVP의 검증 대상이다(08 문서).
- 서드파티(고객사 엔지니어, 파트너)가 **Plugin SDK로 자체 Twin/Agent/Connector를 추가**할 수 있는 생태계.

### 1.2 계층 구조 (참조 아키텍처 전체 뷰)

```
┌─────────────────────────────────────────────────────────────────┐
│ Experience Layer                                                │
│  Project Workspace · Twin Explorer · Approval Center · KPI     │
└────────────────────────────┬────────────────────────────────────┘
┌────────────────────────────▼────────────────────────────────────┐
│ Orchestration Kernel  (DTOS의 "커널")                            │
│  Intent Service · Workflow Engine · Scheduler · HITL Gate      │
│  Policy/Quality Engine · Ledger(감사·KPI)                       │
└──┬──────────┬──────────┬──────────┬─────────────────────────────┘
   │          │          │          │
┌──▼──────┐ ┌─▼────────┐ ┌▼────────┐ ┌▼──────────────────────────┐
│ Agent   │ │ Twin     │ │ Asset   │ │ Simulation Graph          │
│ Registry│ │ Registry │ │ Registry│ │ Service                   │
│ (§3)    │ │ +Version │ │ (§2)    │ │ (§4)                      │
│         │ │ ing (§5) │ │         │ │                           │
└──┬──────┘ └──────────┘ └─────────┘ └───────────────────────────┘
   │  Plugin SDK (§6) — Agent/Connector/Gate/Template 확장점
┌──▼──────────────────────────────────────────────────────────────┐
│ Connector Layer (§7)                                            │
│  Abaqus · Dymola/Modelica · CATIA(Magic) · FMU · Isaac Sim ·   │
│  ROS2 · Office/문서 · PLM/PDM(장기)                              │
└──┬──────────────────────────────────────────────────────────────┘
┌──▼──────────────────────────────────────────────────────────────┐
│ Data & Knowledge Plane                                          │
│  Artifact Lake(불변 저장) · Metadata Catalog · Lineage Graph ·  │
│  Domain Knowledge(물성·규격·V&V) · Telemetry Store(P4)          │
└─────────────────────────────────────────────────────────────────┘
```

MVP(01 문서)의 6계층과의 관계: Orchestration Layer → **Kernel**, Storage/Knowledge → **Data & Knowledge Plane**, Tool Adapter → **Connector Layer**로 각각 승격되고, 4개 Registry/Service(§2~§5)가 신설된다.

---

## 2. Digital Twin Asset Registry

### 2.1 개념

트윈을 구성하는 모든 자산 — CAD/메시/INP, FMU, 물성, 요구사항, 검증 문서, USD 씬, 학습된 대리모델(surrogate) — 을 **타입·버전·계보(lineage)·품질 상태**와 함께 등록하는 중앙 카탈로그. "파일 저장소"가 아니라 **의미가 부여된 자산 그래프**다.

### 2.2 자산 모델

```yaml
asset:
  urn: "urn:dtos:asset:PRJ-024:pump-housing:mesh:v7"
  type: "cae.mesh"            # 네임스페이스 타입 (01 문서 artifacts.kind의 승격)
  twin_ref: "urn:dtos:twin:pump-A200"
  payload: "s3://dtos-lake/..."
  schema_version: "1.2"
  lineage:
    derived_from: ["urn:...:cad:v3"]        # 무엇에서 생성되었나
    generated_by: "run-0113/step-mesh"      # 어떤 실행이 만들었나
    tool: {name: "abaqus", version: "2026"}
  quality:
    status: "validated | draft | deprecated"
    gates_passed: ["gate.mesh.quality"]
    validated_by: "user:kim"                # HITL 승인 연결
  domain_meta: {units: "mm-t-s", element_count: 412000}
```

핵심 설계 결정:

| 결정 | 이유 |
|---|---|
| URN 기반 전역 식별자 | 프로젝트를 넘어 자산 재사용(물성, 템플릿, 대리모델) 가능 |
| lineage를 1급 데이터로 | "이 보고서의 수치는 어느 메시·물성·해석에서 왔는가"에 즉답 → 규제 대응(ASME V&V 40, 의료기기 CM&S)의 근간 |
| quality.status 수명주기 | draft→validated→deprecated. validated 자산만 Production 워크플로우에 투입 가능(Policy Engine 강제) |
| 타입 네임스페이스 개방 | `cae.*`, `fmu.*`, `mbse.*`, `sim.*`(USD/rosbag), `ml.*`(surrogate) — Physical AI·AI모델 자산까지 동일 체계 |

### 2.3 MVP → 플랫폼 진화 경로

| MVP (현재 설계) | 승격 |
|---|---|
| `artifacts` 테이블 (run 종속) | run 종속을 유지하되 URN 발급 + lineage 컬럼 추가 → Registry API로 감싸기 |
| `templates`, `materials` 테이블 | Asset Registry의 타입(`template.*`, `material.*`)으로 흡수 |
| MinIO 경로 규약 | Artifact Lake로 개명, 불변 규칙 동일 유지 |

---

## 3. Agent Registry

### 3.1 개념

Agent를 코드 배포가 아니라 **등록·발견·신뢰 관리** 대상으로 만든다. Orchestration Kernel은 하드코딩된 Agent 목록이 아니라 Registry를 조회해 라우팅한다.

### 3.2 등록 항목

```yaml
agent:
  name: "cae-agent"
  version: "2.4.0"
  contract: "dtos.task-api/v1"          # 03 문서 §1 표준 계약 버전
  capabilities:                          # /v1/capabilities와 동기화
    - action: "generate_case"
      input_schema: "..."
      asset_types_in: ["template.inp", "material.*"]
      asset_types_out: ["cae.case"]
  trust:
    tier: "core | partner | experimental"
    allowed_gates_bypass: []             # 항상 빈 배열(게이트 우회 불가)이 기본
    sandbox: "none | container | network-isolated"
  runtime: {endpoint: "...", health: "...", owner: "team-cae"}
  evaluation:                            # Test Harness 결과와 연동
    regression_suite: "suite:cae-nightly"
    success_rate_30d: 0.94
```

핵심 설계 결정:

- **capability를 자산 타입으로 선언** (`asset_types_in/out`) → Kernel이 "이 자산을 처리할 수 있는 Agent"를 자동 발견하고, Simulation Graph(§4) 구성 시 타입 검사가 가능해진다.
- **trust tier**: 서드파티(Plugin SDK) Agent는 `experimental`로 진입 → 회귀 스위트 통과 + 운영 이력으로 `partner` 승격. `core`만 규제 문서 생성 워크플로우에 참여 가능.
- **evaluation 연동**: Registry가 Agent별 최근 성공률을 보유 → Orchestrator의 라우팅·경고("이 Agent 최근 성공률 급락")에 활용.

### 3.3 MVP → 진화 경로

MVP의 `/v1/capabilities` 기동 시 검증(03 문서)이 곧 Registry의 씨앗이다. Phase 3에서 capabilities 스냅샷을 DB에 저장하는 것으로 시작 → 버전/trust/evaluation 필드를 점증 추가.

---

## 4. Simulation Graph

### 4.1 개념

하나의 트윈은 단일 해석이 아니라 **여러 모델(CAE, FMU, 대리모델, Isaac Sim 씬)이 연결된 그래프**다. Simulation Graph Service는 이 연결을 선언·검증·실행한다. 02 문서의 Workflow가 "업무 절차"라면, Simulation Graph는 **"모델 간 물리적/데이터 의존 구조"** 를 표현한다 — 워크플로우는 그래프의 실행 계획으로 컴파일된다.

### 4.2 그래프 정의 예 (인슐린 펌프 트윈)

```yaml
simulation_graph:
  twin: "urn:dtos:twin:pump-A200"
  version: "3.1"
  nodes:
    - id: structure     # Abaqus 낙하/강도
      kind: cae.model
      asset: "urn:...:inp:v12"
      qoi: [max_stress, deformation]
    - id: dosing        # 약물 주입 동역학
      kind: fmu.model
      asset: "urn:...:fmu:v4"
    - id: patient       # 질환(당뇨) Solver
      kind: fmu.model
      asset: "urn:...:glucose-solver:v9"
    - id: dosing_fast   # 대리모델(장기)
      kind: ml.surrogate
      trained_from: dosing
  edges:
    - {from: dosing, to: patient, map: {insulin_rate: u_insulin}, mode: co-sim}
    - {from: structure, to: dosing, map: {deformation: chamber_geom}, mode: one-way}
  fidelity_policy:
    default: [structure, dosing, patient]
    fast_screening: [structure, dosing_fast, patient]   # 스크리닝은 대리모델로
```

핵심 가치:

| 기능 | 설명 |
|---|---|
| 타입 검증 | edge의 변수 매핑을 Asset Registry의 io_spec과 대조(FMU modelDescription 등) — 실행 전 불일치 검출 |
| Multi-fidelity | 동일 노드에 고충실/대리모델을 병기하고 정책으로 선택 → 대규모 스크리닝과 정밀 검증을 같은 그래프로 |
| Co-simulation 계획 | edge의 `mode`에 따라 실행 순서/마스터 알고리즘 결정(FMI co-sim, one-way 체이닝) |
| V&V 연결 | 그래프 버전이 검증 근거(CAR)와 묶임 → "검증된 것은 정확히 이 그래프 v3.1" |

### 4.3 MVP → 진화 경로

MVP의 단일 CAE 파이프라인 = 노드 1개짜리 그래프. Phase 2의 FMU cohort 검증에서 2노드(one-way)가 등장하며, 이때 그래프 스키마(YAML)만 먼저 도입하고 Service화는 Phase 3에 수행한다.

---

## 5. Digital Twin Versioning

### 5.1 개념

트윈의 버전 = **구성 자산들의 스냅샷 + Simulation Graph 버전 + 검증 상태**의 묶음. Git의 commit처럼, "트윈 v3.1"이라고 하면 어떤 메시·물성·FMU·검증 문서 조합인지 재현 가능해야 한다.

```yaml
twin_version:
  twin: "urn:dtos:twin:pump-A200"
  version: "3.1"
  graph_version: "3.1"
  pinned_assets:
    - "urn:...:mesh:v7"
    - "urn:...:material:ti64:v2"
    - "urn:...:fmu:v4"
  baseline_of: ["PRJ-024"]              # 이 버전을 기준선으로 쓰는 프로젝트
  credibility:
    car_ref: "urn:...:car:v3"           # 이 버전에 대한 신뢰성 평가
    valid_scope: "낙하 1.5m 이하, 체온 범위 동작"
  change_log: "메시 v6→v7 (모서리 refinement), 근거: run-0098 수렴 이슈"
```

핵심 규칙:

1. **재현성**: 과거 트윈 버전으로 워크플로우 재실행 시 동일 자산이 로드된다(Artifact Lake 불변성이 전제 — MVP부터 지켜온 규칙).
2. **검증 범위의 명시**: `credibility.valid_scope` 밖의 사용 요청은 Policy Engine이 경고/차단 — "검증 안 된 조건에 검증된 트윈을 오용"하는 사고 방지. 규제 산업 차별화 포인트.
3. **branch/merge는 도입하지 않는다**: 선형 버전 + 파생 트윈(fork를 새 twin으로)으로 단순화. 엔지니어링 조직에 Git 수준의 브랜칭은 과설계.

### 5.2 MVP → 진화 경로

MVP의 `projects` + run 이력이 원형. Phase 3에서 `twins`, `twin_versions` 테이블 신설 후, 기존 run들의 자산 참조를 소급 연결(lineage가 MVP부터 기록되어 있으므로 가능).

---

## 6. Plugin SDK

### 6.1 확장점

| 확장점 | 만드는 것 | 예 |
|---|---|---|
| **Digital Twin Plugin** ★ | 아래 4종을 도메인 단위로 묶은 **복합(최상위) 확장점**. 표준 Twin Agent 인터페이스(`prepare/run/validate/report`) + 템플릿 + 게이트 + KPI + 워크플로우를 하나의 패키지로 제공 | `fmh_twin`(MVP), `diabetes_twin`, `robot_twin` — [08 문서](08-FMH-DigitalTwin-Plugin-설계.md) |
| **Agent Plugin** | 03 문서 §1 계약을 구현하는 신규 Agent | 고객사 사내 피로해석 Agent |
| **Connector Plugin** | §7 Connector 계약을 구현하는 도구 연동 | Ansys, Simulink 커넥터 |
| **Gate Plugin** | Quality Gate 룰 (선언형 YAML 또는 Python 함수) | 사내 설계 기준 검사 |
| **Template Pack** | 해석/보고서/V&V 템플릿 + param_schema 번들 | 자동차 충돌 템플릿 팩 |

**Twin 중심 재정의**: DTOS의 1차 구성 단위는 도구(Tool)가 아니라 **Digital Twin Plugin**이다. 플러그인이 도메인 지식(템플릿·게이트·KPI·보고서 양식)을 응집 소유하고, 도구 접근은 Connector Layer(§7)를 공유한다. 새 도메인 확장 = `plugins/` 아래 트윈 플러그인 1개 추가이며, Kernel·Registry·UI는 무변경이다. 상세 구조와 manifest 규약, 레퍼런스 구현(FMH)은 [08 문서](08-FMH-DigitalTwin-Plugin-설계.md) 참조.

```
plugins/
├── fmh_twin/        # MVP — 최초의 레퍼런스 플러그인 (08 문서)
├── diabetes_twin/   # P2
├── hearing_twin/    # P3+
├── spine_twin/      # P3+
├── battery_twin/    # P3+
└── robot_twin/      # P4
```

### 6.2 SDK 형태 (Python)

```python
from dtos_sdk import agent, action, Artifact

@agent(name="fatigue-agent", contract="dtos.task-api/v1")
class FatigueAgent:
    @action(input_schema=FatigueInput,
            asset_types_in=["cae.odb"], asset_types_out=["cae.fatigue_result"])
    def evaluate_fatigue(self, ctx, inputs) -> ActionResult:
        odb = ctx.assets.fetch(inputs.odb_ref)      # Artifact Lake 접근
        ...
        return ActionResult(outputs={...},
                            artifacts=[Artifact(kind="cae.fatigue_result", path=...)])
```

- SDK가 **엔벨로프/멱등/진행 이벤트/원장 기록을 전부 대행** — 플러그인 개발자는 도메인 로직만 작성.
- 배포는 컨테이너 이미지 + manifest(§3의 registry 항목) 제출 → `experimental` tier로 등록.
- 보안: experimental tier는 network-isolated 샌드박스에서 실행, Artifact Lake 접근은 해당 run 범위로 제한(스코프 토큰).

### 6.3 진화 경로

MVP의 `agents/common`(공통 서버 베이스)이 SDK의 전신이다. Phase 2~3에서 내부용으로 다듬고, 대외 공개(파트너 생태계)는 Horizon 3(§8) 판단 사항.

---

## 7. External Tool Connector

### 7.1 Connector 계약 (Runner의 일반화)

01 문서의 Runner를 **Connector 계약**으로 표준화한다. Connector = "특정 외부 도구를 DTOS 작업 큐에 연결하는 결정적(deterministic) 실행기".

```yaml
connector_manifest:
  name: "abaqus-connector"
  tool: {name: "abaqus", versions: ["2024","2026"]}
  operations:
    - {op: "run_job",  inputs: ["cae.case"], outputs: ["cae.odb","log.solver"]}
    - {op: "extract",  inputs: ["cae.odb"],  outputs: ["result.qoi_json","image.contour"]}
  execution:
    mode: "queue-pull"                 # inbound 포트 불필요 (01 문서 원칙 유지)
    placement: {requires: ["license:abaqus", "os:linux|windows"]}
    concurrency: {slots: "license_tokens/5"}
  license: {type: "flexlm", check_before_run: true}
  cancellation: supported
  telemetry: {progress: "sta-parser", heartbeat_sec: 30}
```

### 7.2 도구별 Connector 로드맵

| Connector | 연동 방식 | 시기 | 비고 |
|---|---|---|---|
| Abaqus | CLI + Python/ODB API, .sta/.msg 파싱 | MVP | 완성도 최우선 |
| FMU (FMPy) | in-process 라이브러리 | P2 | co-sim 마스터는 P3 |
| Dymola | 스크립트 배치 실행 → FMU export 경로 우선 | P3 | 직접 제어보다 FMU 경유가 안정적 |
| CATIA Magic | ReqIF/CSV 파일 교환 (00 문서 2.5 결정 유지) | P3 | Teamwork Cloud REST는 버전 확인 후 |
| Office/문서 | python-docx/WeasyPrint | MVP | Report Agent 내장 → P3에 Connector로 분리 |
| Isaac Sim | headless Python API, USD, 컨테이너 고정 | P4 | 06 문서 |
| ROS2 | bridge 노드, rosbag 수집 | P4 | sim-to-real 기준면 |
| PLM/PDM (Windchill, 3DEXPERIENCE 등) | 자산 동기화 (CAD→Asset Registry) | Horizon 3 | 고객 환경 의존, 수요 확인 후 |

원칙: **새 도구 지원 = Connector manifest + 컨테이너 1개 추가**. Kernel/Agent/UI는 무변경. 이것이 "Operating System"을 자칭할 수 있는 최소 조건이다.

---

## 8. Physical AI 확장 전략 (3~5년 Horizon)

06 문서(Phase 4 실행 계획)의 상위 전략. 3단계 Horizon으로 관리한다.

| Horizon | 기간 | 목표 | 핵심 투자 |
|---|---|---|---|
| **H1: 가상 검증 플랫폼** | ~M12 | CAE·FMU·V&V 자동화로 내부 생산성 입증 (01~05 문서) | 템플릿 자산, 원장/KPI, 표준 계약 |
| **H2: 트윈 플랫폼화** | M12~M30 | Registry·Graph·Versioning 도입, Isaac Sim PoC → 로봇/제조 트윈 상품화 | §2~§5 서비스화, Sim Agent, GPU 인프라 |
| **H3: Physical AI 운영** | M30~M60 | 실기 연결(ROS2 텔레메트리) — 시뮬레이션-실측 비교, sim-to-real 검증, 온라인 트윈 갱신 | Telemetry Store, 스트리밍 파이프라인, 대리모델(ml.surrogate) 학습 루프 |

### H3의 기술적 함의 (지금 결정에 영향을 주는 것만)

1. **Telemetry Store**: 실기 센서 데이터는 배치 아티팩트가 아니라 시계열 스트림이다. H3에서 TimescaleDB/Parquet 레이크를 Data Plane에 추가한다 — MVP에서 미리 만들 필요는 없으나, **진행 이벤트 스키마를 범용 시계열 채널로 설계**(06 문서 §1)해 두는 것이 그 준비의 전부다.
2. **대리모델 학습 루프**: 축적된 해석 결과(lineage 완비)가 곧 학습 데이터셋이다 — lineage를 MVP부터 기록하는 이유가 여기서 회수된다. `ml.surrogate` 자산 타입과 Simulation Graph의 fidelity_policy(§4)가 수용 구조.
3. **검증 프레임의 확장**: ASME V&V 40 기반 신뢰성 평가를 sim-to-real gap 평가로 확장 — V&V Agent와 twin_version.credibility(§5)가 그대로 재사용된다.
4. **하지 않는 것**: 실시간 제어 루프(트윈이 실기를 직접 제어)는 5년 범위에서 제외한다. 안전 인증 부담이 플랫폼 전체 리스크가 되므로, DTOS는 **분석·검증·의사결정 지원**에 집중한다.

---

## 9. 거버넌스: 청사진이 MVP를 삼키지 않게 하는 규칙

이 문서는 방향이지 백로그가 아니다. 다음 규칙으로 실행 설계(01~06)와의 긴장을 관리한다.

1. **Registry/Graph/Versioning은 Phase 3 전에 서비스로 만들지 않는다.** 단, 그 씨앗이 되는 데이터(URN 발급 가능한 ID 체계, lineage, capabilities 스냅샷, 불변 아티팩트)는 MVP 스키마에 이미 반영되어 있다 — 각 장의 "진화 경로"가 그 계약이다.
2. **표준 계약(dtos.task-api/v1)의 파괴적 변경은 버전 승격으로만** 허용한다. v1은 최소 H2까지 유지.
3. 분기마다 본 문서를 리뷰하여 Horizon 경계(특히 H2 진입 시점)를 사업 성과(KPI, PoC 수주)에 따라 재조정한다.
