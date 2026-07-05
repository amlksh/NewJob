# Architecture Freeze 및 실행 우선순위 (제안 검토 반영)

> 제안된 우선순위(①Architecture Freeze → ②Repo 구성 → ③**Interface Spec v1.0**⭐ → ④FMH Plugin → ⑤Runner → ⑥Orchestrator → ⑦Dashboard → ⑧FMH Demo)에 대한 개발팀 검토 의견 및 확정 실행 계획.

---

## 1. 제안 검토 결과: 동의 + 수정의견 3건

**"Interface Specification이 최우선"이라는 판단에 전적으로 동의한다.** 03/08 문서는 계약의 *존재와 역할*을 정의했지만, 여러 개발자가 동시 작업하려면 필드 단위 스키마·상태 기계·에러 의미까지 확정한 명세가 필요하다. → [11-V-DTOS-Interface-Specification-v1.0](11-V-DTOS-Interface-Specification-v1.0.md)으로 작성 완료.

다만 ④~⑦의 실행 순서에 수정의견이 있다.

### 수정의견 1 — 컴포넌트 순차 완성이 아니라 "Walking Skeleton 먼저"

④FMH Plugin → ⑤Runner → ⑥Orchestrator → ⑦Dashboard를 **각각 완성해가는 순서**로 진행하면, 통합이 마지막에 몰린다. 각 컴포넌트가 개별적으로는 동작해도 계약 해석 차이(진행 이벤트 타이밍, 에러 클래스 의미, 아티팩트 참조 형식)는 반드시 통합 시점에 터진다.

**대안**: Interface Spec 확정 직후, **전 구간을 관통하는 가장 얇은 한 줄(Walking Skeleton)** 을 먼저 만든다.

```
[Skeleton 범위 — 2주 목표]
Orchestrator(고정 워크플로우 1개, LLM 없음)
  → FMH Plugin prepare() (템플릿 1개, 파라미터 하드코딩 허용)
  → Abaqus Runner (초소형 INP 1건 실제 실행)
  → validate() (HIC 계산 1개 케이스)
  → report() (한 페이지 docx)
  → HITL 승인 최소 화면 (Streamlit 허용)
```

이 한 줄이 돌고 나면 ④~⑦은 **각자 살을 붙이는 병렬 작업**이 되고, 매주 데모 가능한 상태가 유지된다. ⑧FMH Demo는 "마지막에 만드는 것"이 아니라 skeleton의 점진적 확장이 된다.

### 수정의견 2 — Runner는 FMH Plugin보다 앞이거나 병행

제안 순서는 ④FMH Plugin → ⑤Runner인데, FMH Plugin의 `run()`은 Runner 없이는 목업으로만 개발·검증된다. 반대로 Runner는 Plugin 없이도 "수동 제출 INP 실행"으로 독립 검증이 가능하다(WBS 1.4가 이미 그렇게 설계됨). **Runner를 skeleton에 포함해 먼저 세우고, FMH Plugin이 그 위에서 개발되는 순서**가 재작업이 적다.

### 수정의견 3 — Dashboard는 2단계로 분리

- **7a. HITL 최소 화면** (승인/반려 + 사유 코드 + run 로그 보기): skeleton에 포함. 이것 없이는 데모의 핵심 서사("AI가 하고 사람이 승인한다")가 성립하지 않는다.
- **7b. 본격 Dashboard** (프로젝트 현황, KPI, 산출물 뷰어): Demo 이후. React 전환 시점도 여기.

### 확정 실행 순서 (수정 반영)

| 순서 | 항목 | 산출물 | 기간(안) |
|---|---|---|---|
| 1 | Architecture Freeze | 본 문서 §2 동결 목록 + ADR 절차 가동 | 1주 내 |
| 2 | Repo 생성·초기 구조 | 모노레포 스캐폴드, CI 최소 파이프라인 (§3) | 1주 내 (1과 병행) |
| 3 | **Interface Spec v1.0** ⭐ | 11 문서 → 리뷰 → **v1.0 태깅** | 완료(리뷰 대기) |
| 4 | **Walking Skeleton** | 전 구간 관통 1케이스 (Runner 포함, HITL 최소 화면 포함) | 2주 |
| 5 | FMH Plugin 본 구현 | 타겟 그리드 전개, 포지셔닝, 케이스 매트릭스, HIC 판정 일치율 | 3~4주 (병렬) |
| 6 | Orchestrator 본 구현 | Intent 해석(LLM), foreach 팬아웃, checkpoint 재개, 실패 분류 | 3~4주 (병렬) |
| 7 | Dashboard 7b | run 모니터링, 산출물 뷰어, KPI | 2~3주 (병렬 후반) |
| 8 | FMH Digital Twin Demo | 실제 프로젝트 1건 end-to-end + 데모 시나리오 | M3 말 |

WBS(05 문서)와의 정합: 위 1~4가 M1, 5~6이 M2, 7~8이 M3에 대응한다. 총 일정 불변.

---

## 2. Architecture Freeze: 동결 목록과 변경 절차

"Freeze"는 전부를 얼리는 것이 아니라, **바꾸면 여러 컴포넌트가 흔들리는 결정만 골라 동결**하고 나머지는 유동으로 두는 것이다.

### 2.1 동결 대상 (변경 시 ADR 필수)

| # | 동결 결정 | 근거 문서 |
|---|---|---|
| F1 | 4대 계약: `task-api/v1`, `twin-agent/v1`, `tooljob/v1`, Workflow Schema v1 | 11 문서 |
| F2 | 아티팩트 불변 + 참조 전달(pass-by-reference) + URN 문법 | 01 §5, 11 §7 |
| F3 | Runner pull 모델 (큐 폴링, outbound-only, LLM 호출 금지) | 01 §3~4 |
| F4 | Orchestration = LangGraph(제어) + Celery/Redis(실행) 분리, HITL은 checkpoint 기반 | 02 |
| F5 | 템플릿 우선 원칙 (LLM 자유 생성물의 실행계 직접 투입 금지, Quality Gate 필수) | 00 §2.1 |
| F6 | Digital Twin Plugin이 1차 구성 단위 (manifest 기반 등록) | 07 §6, 08 |
| F7 | 에러 4분류(`tool_transient/tool_numerical/agent_generation/input_error`)와 재시도 정책의 의미 | 02 §5 |
| F8 | 원장(ledger) 기록 의무: 모든 step·승인·LLM 호출 (반려 사유 코드 포함) | 01 §6, 09 |

### 2.2 유동 항목 (자유 변경, ADR 불필요)

- Gate 임계값, 템플릿 내용, 프롬프트 (단, 09 문서의 회귀 절차는 준수)
- UI 컴포넌트/디자인, Streamlit→React 전환 시점
- Runner 내부 구현(파서, 재시도 백오프 값), DB 인덱스/컬럼 추가(additive)
- Plugin 내부 구조 (manifest 계약만 지키면 자유)

### 2.3 변경 절차: 경량 ADR (Architecture Decision Record)

```
docs/adr/NNNN-제목.md  (1페이지 고정)
  상태: proposed | accepted | superseded
  맥락 / 결정 / 대안과 기각 사유 / 영향(어느 계약·컴포넌트) / 마이그레이션
```

- 동결 항목(F1~F8) 변경은 ADR 작성 + Architect 승인 후에만 반영.
- 계약(F1) 변경은 11 문서 §2.6의 버전 규칙(semver)을 따른다 — 파괴적 변경은 v2 신설이며 v1 즉시 폐기 금지.

---

## 3. Repository 생성 및 초기 구조

### 3.1 저장소 전략 (권장)

| 저장소 | 용도 | 비고 |
|---|---|---|
| `v-dtos` (신규, 권장명) | 플랫폼 모노레포 — 코드 전체 | 04 문서 §3 구조로 스캐폴드 |
| 본 저장소(NewJob) | 설계 문서(00~11) 보관 | 코드 저장소 확정 후 `v-dtos/docs/design/`으로 이관 권장 |

> **사용자 결정 필요**: 신규 저장소의 조직/이름/공개범위(사내 private 권장). 결정되면 스캐폴드를 바로 생성할 수 있다.

### 3.2 초기 구조 (04 문서 §3 확정판 + 초기화 항목)

```
v-dtos/
├── apps/{gateway, orchestrator, web}
├── apps/runners/abaqus_runner
├── sdk/                      # TwinAgent 베이스, 계약 모델(Pydantic), 계약 테스트
├── plugins/fmh_twin/
├── services/report/
├── libs/{core, cae_toolkit}
├── contracts/                # ★ 11 문서의 기계가독 사본: JSON Schema + golden examples
│   ├── task-api/v1/*.json
│   ├── twin-agent/v1/*.json
│   ├── tooljob/v1/*.json
│   └── examples/             # 계약 테스트가 검증하는 golden 메시지
├── docs/{design, adr}
├── infra/{docker-compose.yml, migrations}
└── .github/workflows/ci.yml  # lint + unit + 계약 테스트 (아래)
```

### 3.3 초기화 체크리스트

1. 모노레포 스캐폴드 + `uv`/`ruff`/`pytest` 셋업, pre-commit
2. **contracts/ 디렉터리에 11 문서의 JSON Schema를 코드로 등록** — 문서와 스키마가 어긋나면 CI 실패
3. 계약 테스트 하네스: 모든 Agent/Runner 구현은 `sdk`의 공용 contract test를 통과해야 merge 가능
4. CI: PR마다 lint + unit + contract test, `main`은 trunk-based(짧은 브랜치 + PR)
5. docker-compose로 postgres/redis/minio 로컬 기동 1커맨드화

---

## 4. Interface Spec의 지위

- 11 문서가 리뷰를 통과하면 **v1.0으로 태깅**하고 F1으로 동결된다.
- 이후 구현 중 발견되는 스키마 결함은 v1.0.x(패치, 하위호환)로만 수정하고, 필드 추가는 v1.1(minor)로 누적한다.
- 문서(11)와 기계가독 스키마(contracts/)의 **단일 진실은 contracts/** 다 — 문서가 스키마를 요약하고, 스키마가 CI를 구속한다.
