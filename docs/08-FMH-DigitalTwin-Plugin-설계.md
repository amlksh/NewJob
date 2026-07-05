# FMH Digital Twin Plugin 설계 (MVP 확정 대상)

> 「DTOS MVP 개발 방향 변경 및 추가 요청사항」 반영 문서.
> MVP 대상을 일반 Abaqus 낙하해석에서 **FMH(Free Motion Headform) Digital Twin**으로 확정하고, FMH를 **DTOS 최초의 Digital Twin Plugin이자 표준 Agent 레퍼런스 구현**으로 정의한다.
> 상위 문서: [07-Reference-Architecture](07-DTOS-Reference-Architecture.md) §6.4(Digital Twin Plugin) · 실행 계획 반영: [04-MVP-범위-기술스택](04-MVP-범위-기술스택.md), [05-WBS-개발일정](05-WBS-개발일정.md)

---

## 1. MVP 대상 변경의 타당성 검토 (개발팀 의견)

변경에 **동의**한다. 설계 관점의 근거:

1. **템플릿 커버리지 리스크 최소화** — 00 문서 2.1에서 MVP 성공률은 "템플릿 커버리지"로 결정된다고 했다. FMH는 내부에서 이미 자동화가 완성된 도메인이므로, MVP의 최대 불확실성(검증된 템플릿 확보)이 사실상 제거된다.
2. **정량 판정 기준의 명확성** — FMH는 HIC(d) ≤ 1000 (FMVSS 201U)이라는 규격 기반 pass/fail 기준이 있어, V&V Agent의 `check_results`와 Quality Gate를 모호함 없이 구현·시연할 수 있다.
3. **Twin 중심 재정의의 자연스러운 출발점** — FMH는 "도구 자동화"가 아니라 "차량 실내 충돌 안전이라는 도메인 트윈"이므로, Digital Twin Plugin 모델(§3)의 레퍼런스로 적합하다.

유의점 1건: **Plugin SDK를 MVP에서 과도하게 일반화하지 말 것.** 두 번째 트윈(Diabetes, Phase 2)이 들어올 때까지 SDK의 추상화는 "FMH가 실제로 필요로 한 것"으로 한정한다. 하나의 사례로 일반화한 SDK는 반드시 다시 깨진다 — MVP에서는 **FMH Plugin을 SDK 규약대로 구조화하는 것까지만** 하고, SDK의 공개 계약 동결은 Phase 2 말(두 번째 플러그인 통과 후)로 미룬다.

---

## 2. FMH Digital Twin 개요

| 항목 | 내용 |
|---|---|
| 대상 업무 | 차량 실내 상부(필러, 헤드라이너 등) FMH 충돌 해석 (FMVSS 201U) |
| 물리 모델 | FMH 헤드폼(계측 질량 4.5kg) → 타겟 포인트에 24km/h 충돌, Abaqus/Explicit |
| 핵심 QoI | HIC(d) = 0.75446·HIC(36) + 166.4, 피크 가속도, 접촉력, 변형 모드 |
| 판정 기준 | HIC(d) ≤ 1000 (규격), 사내 설계 목표치(마진 포함)는 프로젝트별 파라미터 |
| 반복 구조 | 타겟 포인트 × 접근각 조합의 대량 케이스 → 병렬 실행 → 워스트 케이스 선별 |
| 기존 자산 | 사내 FMH 자동화 스크립트, 포지셔닝 로직, 템플릿, 실프로젝트 검증 이력 |

### MVP 파이프라인 (변경 요청 문서 2장)

```
사용자 요청 → AI Orchestrator → FMH Agent → Template Engine
           → Abaqus Runner → Evaluation Engine → Report Agent → Human Approval
```

기존 설계(02 문서)와의 매핑: 이 파이프라인은 02 문서의 표준 구조와 동일하며, `drop_test` 예시가 `fmh_impact` 워크플로우(§5)로 대체된다. Template Engine은 CAE Agent 내부 모듈이었던 것을 **Plugin이 소유하는 컴포넌트**로 재배치한 것이다(§3.2).

---

## 3. Digital Twin 중심 아키텍처 재정의

### 3.1 재정의의 의미

| 관점 | Tool 중심 (기존 서술) | **Twin 중심 (재정의)** |
|---|---|---|
| 1차 구성 단위 | Agent가 도구(Abaqus, FMU)를 감싼다 | **Digital Twin Plugin**이 도메인(FMH, 당뇨…)을 감싼다 |
| Agent의 위치 | 도구별 Agent (CAE Agent, FMU Agent) | Twin Plugin이 표준 Twin Agent 인터페이스를 구현하고, 도구 접근은 Connector를 공유 |
| 지식의 위치 | Template DB에 평면적으로 저장 | 템플릿·게이트·KPI·보고서 양식이 **Plugin 패키지에 응집** |
| 확장 방법 | 새 도구 지원 추가 | **새 트윈 플러그인 추가** (도구는 기존 Connector 재사용) |

재정의 후에도 **03 문서의 표준 Task API 계약과 01 문서의 Connector(Runner) 구조는 그대로 유지된다.** 바뀌는 것은 패키징과 소유권이다: "CAE Agent가 낙하도 FMH도 처리"하는 대신, "FMH Twin Plugin이 자기 도메인의 전 과정을 소유하고, Abaqus Connector를 빌려 쓴다."

기존 도구 지향 Agent(CAE/FMU Agent)의 지위: **공용 라이브러리로 강등**된다. INP 조립, ODB 추출, .sta 파싱 등 도구 공통 로직은 `libs/cae_toolkit`으로 이동하고, 각 Twin Plugin이 이를 조합한다. 03 문서의 CAE Agent action들은 FMH Plugin의 내부 구현으로 흡수된다.

### 3.2 Plugin 패키지 구조 (변경 요청 문서 4장 구체화)

```
plugins/
├── fmh_twin/                      # ★ MVP — 최초의 레퍼런스 플러그인
│   ├── manifest.yaml              # 플러그인 선언 (§3.3)
│   ├── agent.py                   # FmhTwinAgent(TwinAgent) — §4 인터페이스 구현
│   ├── templates/                 # Template Engine이 사용하는 검증된 템플릿
│   │   ├── headform_position.inp.j2
│   │   ├── impact_case.inp.j2
│   │   └── report_fmvss201.docx.j2
│   ├── gates/                     # 도메인 Quality Gate
│   │   ├── gate.fmh.target_grid.yaml      # 타겟 포인트 규격 적합성
│   │   ├── gate.fmh.energy.yaml           # ALLAE/ALLIE 임계
│   │   └── gate.fmh.hic_sanity.yaml       # HIC 신호 무결성(필터, 시간창)
│   ├── kpi/
│   │   └── fmh_kpi.yaml           # Evaluation Engine 등록 KPI (§7)
│   ├── workflows/
│   │   └── fmh_impact/1.0.yaml    # §5
│   ├── schemas/                   # 입력/파라미터 JSON Schema
│   └── tests/                     # 축소판 회귀 시나리오 (Test Harness 등록)
├── diabetes_twin/                 # Phase 2 (질환 Solver — FMU 기반)
├── hearing_twin/                  # Phase 3+
├── spine_twin/                    # Phase 3+
├── battery_twin/                  # Phase 3+
└── robot_twin/                    # Phase 4 (Isaac Sim/ROS2 — 06 문서)
```

### 3.3 Plugin Manifest

```yaml
# plugins/fmh_twin/manifest.yaml
twin_plugin:
  name: "fmh_twin"
  version: "1.0.0"
  twin_kind: "automotive.interior_impact.fmh"
  agent:
    class: "fmh_twin.agent:FmhTwinAgent"
    contract: "dtos.twin-agent/v1"           # §4 (task-api/v1 위에 정의)
  connectors_required: ["abaqus-connector>=1.0"]
  asset_types:                                # Asset Registry에 등록되는 타입
    - "fmh.headform_model"                    # 검증된 헤드폼 FE 모델
    - "fmh.target_grid"                       # 타겟 포인트/접근각 정의
    - "fmh.interior_mesh"                     # 차량 실내 트림 메시
    - "fmh.impact_result"
  gates: ["gate.fmh.target_grid", "gate.fmh.energy", "gate.fmh.hic_sanity"]
  kpis: ["hic_d", "peak_accel_g", "auto_success_rate", "wall_time_per_case"]
  workflows: ["fmh_impact/1.0"]
  regression_suite: "plugins/fmh_twin/tests"
  trust_tier: "core"
```

Orchestration Kernel은 기동 시 `plugins/`를 스캔해 manifest를 Agent Registry·Asset Registry(타입)·Gate/KPI 카탈로그·워크플로우 카탈로그에 자동 등록한다. **MVP에서는 이 등록이 정적 로딩(설정 파일 수준)이어도 된다** — 동적 설치/격리는 Phase 3(07 문서 §6).

---

## 4. 표준 Twin Agent 인터페이스: `prepare() / run() / validate() / report()`

변경 요청의 4-메서드 인터페이스를 **`dtos.twin-agent/v1`** 으로 정의한다. 이는 03 문서의 전송 계약(task-api/v1)을 **대체하지 않고 그 위에 얹히는 수명주기 계약**이다: 전송·멱등·아티팩트 규칙은 task-api가, 트윈 업무의 단계 의미는 twin-agent가 담당한다.

```python
# dtos_sdk (Plugin SDK) — Twin Agent 기반 클래스
class TwinAgent(ABC):

    @abstractmethod
    def prepare(self, ctx: TwinContext, spec: CaseSpec) -> PrepareResult:
        """케이스 생성: 템플릿 선택·파라미터 주입·입력 검증.
        FMH: 타겟 포인트 전개, 헤드폼 포지셔닝, INP 조립"""

    @abstractmethod
    def run(self, ctx: TwinContext, prepared: PrepareResult) -> RunResult:
        """Connector를 통한 실행 제출·모니터링 (직접 도구 실행 금지).
        FMH: 케이스별 ToolJob 발행 → Abaqus Runner, 진행 이벤트 중계"""

    @abstractmethod
    def validate(self, ctx: TwinContext, results: RunResult) -> ValidateResult:
        """도메인 검증: QoI 산출·게이트 판정·판정표 생성.
        FMH: HIC(d) 계산, 규격/목표 대비 판정, 에너지·신호 게이트"""

    @abstractmethod
    def report(self, ctx: TwinContext, verdicts: ValidateResult) -> ReportResult:
        """보고서 생성 (공용 Report 서비스 호출 + 도메인 양식 적용).
        FMH: FMVSS 201U 결과 보고서, 워스트 케이스 요약"""
```

### 4.1 task-api/v1과의 매핑

| twin-agent 수명주기 | task-api action (자동 노출) | 기존 03 문서 대응 |
|---|---|---|
| `prepare()` | `POST /v1/tasks {action: "prepare"}` | CAE Agent `generate_case`+`validate_input` 흡수 |
| `run()` | `{action: "run"}` | `run_job` 흡수 (foreach 팬아웃은 Orchestrator 담당 유지) |
| `validate()` | `{action: "validate"}` | `extract_results`+`diagnose` + V&V `check_results` 흡수 |
| `report()` | `{action: "report"}` | Report Agent `generate` 호출 래핑 |

- SDK가 4 메서드를 task-api 엔드포인트로 자동 노출하므로 **Orchestrator·원장·HITL·재시도 로직은 무변경**.
- 공용 Report Agent(03 문서 §7)는 유지된다 — Twin의 `report()`는 도메인 데이터 준비 후 공용 Report 서비스를 호출한다(수치 재계산 금지 원칙 동일).
- 후속 트윈의 동일 인터페이스 적용:

| Twin | prepare | run | validate | report |
|---|---|---|---|---|
| **fmh_twin** (MVP) | 타겟 전개·포지셔닝·INP | Abaqus Connector | HIC(d)·게이트 | FMVSS 보고서 |
| diabetes_twin (P2) | cohort 시나리오 생성 | FMU Connector(FMPy) | RMSE·TIR·실패요약 | 검증 보고서 |
| hearing_twin / spine_twin (P3) | 환자 파라미터 케이스 | Abaqus/FMU | 도메인 QoI | CM&S/CAR 연계 |
| battery_twin (P3) | 열·전기 시나리오 | FMU/CAE | 열폭주 마진 | 안전성 보고서 |
| robot_twin (P4) | USD 씬·에피소드 정의 | Isaac Sim Connector | sim-to-real gap | 검증 보고서 |

---

## 5. `fmh_impact` 워크플로우 (MVP 확정 워크플로우)

02 문서의 `drop_test` 예시를 대체하는 실제 MVP 카탈로그 항목.

```yaml
# plugins/fmh_twin/workflows/fmh_impact/1.0.yaml
key: fmh_impact
version: "1.0"
description: FMH 충돌 해석 (FMVSS 201U) → HIC 판정 → 보고서
input_schema: plugins/fmh_twin/schemas/fmh_input.json

steps:
  - id: prepare
    agent: fmh_twin
    action: prepare            # 타겟 그리드 전개 → 케이스 N개 생성
    gates_after: [gate.input.units, gate.fmh.target_grid]

  - id: approve_plan           # HITL #1: 케이스 목록·예상 소요·라이선스
    type: hitl
    gate_key: plan_approval
    show: [prepare.output.case_matrix_summary]

  - id: run
    agent: fmh_twin
    action: run
    foreach: prepare.output.cases        # 타겟×접근각 병렬 (라이선스 슬롯 내)
    retry: {max: 2, on: [tool_transient_error]}
    gates_after: [gate.run.convergence, gate.fmh.energy]
    on_gate_fail: escalate_hitl

  - id: validate
    agent: fmh_twin
    action: validate           # HIC(d) 산출, 판정표, 워스트 케이스 선별
    gates_after: [gate.fmh.hic_sanity]

  - id: report
    agent: fmh_twin
    action: report
    gates_after: [gate.report.consistency]

  - id: approve_report         # HITL #2
    type: hitl
    gate_key: report_approval
    on_reject: report
```

### Task Plan 예시

```json
{
  "intent": "fmh_impact_analysis",
  "workflow": {"key": "fmh_impact", "version": "1.0"},
  "inputs": {
    "interior_mesh_ref": "urn:dtos:asset:PRJ-031:trim-B:fmh.interior_mesh:v4",
    "headform_ref": "urn:dtos:asset:shared:fmh.headform_model:v2",
    "target_zone": "A-pillar_upper",
    "grid_spacing_mm": 25,
    "approach_angles": "per_fmvss201u",
    "hic_d_target": 900
  },
  "deliverables": [{"kind": "report", "format": "docx", "template": "report_fmvss201"}],
  "verification": ["gate.fmh.energy", "gate.fmh.hic_sanity", "gate.report.consistency"]
}
```

---

## 6. Asset Registry 연계 (FMH 자산의 Lineage·Version)

07 문서 §2의 자산 모델을 FMH에 적용한다. MVP에서는 URN 발급 + lineage 기록까지 구현한다(Registry 서비스화는 Phase 3 유지).

```
urn:dtos:asset:shared:fmh.headform_model:v2      ← 검증된 헤드폼 (전 프로젝트 공유, quality=validated)
urn:dtos:asset:PRJ-031:trim-B:fmh.interior_mesh:v4
    lineage.derived_from: [urn:...:cad:v9]
urn:dtos:asset:PRJ-031:run-0207:fmh.impact_result:case-A17
    lineage.generated_by: run-0207/run[case-A17]
    lineage.derived_from: [headform_model:v2, interior_mesh:v4, template:impact_case:v1.3]
```

규칙:

1. **헤드폼 모델은 `quality=validated` 자산만 사용 가능** — 규격 시험 상관관계가 확인된 버전만 워크플로우 투입 (Policy Gate). 이것이 "FMH Digital Twin의 신뢰성"의 뿌리다.
2. 모든 `fmh.impact_result`는 헤드폼·메시·템플릿 버전으로 lineage가 완결된다 → 보고서의 모든 HIC 수치가 자산 계보로 소급 가능.
3. FMH 트윈 버전(07 문서 §5): `twin:trim-B` v1.0 = interior_mesh v4 + headform v2 + fmh_twin plugin 1.0.0 스냅샷.

---

## 7. Evaluation Engine: FMH KPI 등록

01 문서 §6의 원장 기반 집계에 FMH 도메인 KPI를 추가한다. Plugin의 `kpi/fmh_kpi.yaml`이 선언하고 Evaluation Engine이 수집한다.

| KPI | 정의 | 원천 | MVP 목표 |
|---|---|---|---|
| `hic_d` (케이스별) | HIC(d) 값·판정 분포, 워스트 케이스 | validate 출력 | 판정 정확도: 기존 수동 결과와 100% 일치 |
| `auto_success_rate` | 사람 개입 없이 1회 성공한 케이스 비율 | steps ledger (`attempt=1 & succeeded`) | ≥ 80% |
| `wall_time_per_case` | 케이스당 prepare→validate 경과시간 | steps ledger | 수동 대비 ≥ 50% 단축 |
| `gate_pass_rate` | FMH 게이트 통과율 | gates ledger | ≥ 90% |
| `hic_signal_quality` | 필터/시간창 이상 감지 건수 | gate.fmh.hic_sanity | 0 (미검출 시 게이트 개선) |

주의: `hic_d` 자체는 "높을수록/낮을수록 좋은" 플랫폼 KPI가 아니라 **도메인 판정값**이다. Evaluation Engine에는 판정 일치율(기존 검증된 수동 프로세스와의 비교)로 등록한다 — MVP 기간 동안 자동 파이프라인의 신뢰를 만드는 핵심 지표.

---

## 8. 기존 문서에 대한 영향 (변경 반영 요약)

| 문서 | 변경 | 상태 |
|---|---|---|
| 00-검토의견 | 변경 이력 추가 (MVP 대상 FMH 확정) | 반영 |
| 02-오케스트레이터 | `drop_test` 예시는 교육용으로 유지, MVP 확정 워크플로우는 본 문서 §5 | 주석 추가 |
| 03-Agent-API | task-api/v1 유지. CAE Agent action은 FMH Plugin 내부로 흡수(§4.1), 공용 로직은 `libs/cae_toolkit` | 주석 추가 |
| 04-MVP-범위 | MVP 정의를 FMH로 교체, Plugin 구조 반영 | 반영 |
| 05-WBS | M1: FMH 자산 이식·템플릿화, M3 PoC를 FMH 프로젝트로 확정 | 반영 |
| 07-Reference-Architecture | §6에 Digital Twin Plugin(복합 확장점) 추가, Twin 중심 재정의 명시 | 반영 |

### WBS 관점의 이득

기존 M1 리스크 항목이었던 "템플릿 추출·검증"(1.5)이 **기존 FMH 자동화 자산 이식**으로 바뀌어 난이도가 하락한다. 확보되는 여유는 Plugin 구조화(manifest, TwinAgent 베이스)와 HIC 판정 일치율 검증(§7)에 투입한다 — 일정 총량은 변경하지 않는다.
