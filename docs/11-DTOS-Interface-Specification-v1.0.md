# DTOS Interface Specification v1.0 (Draft for Review)

> **문서 지위**: 본 명세는 DTOS 컴포넌트 간 통신·구현 계약의 단일 기준이다. 리뷰 통과 시 v1.0으로 태깅되어 Architecture Freeze 항목 F1이 된다(10 문서 §2).
> **표기**: MUST/SHOULD/MAY는 RFC 2119 의미로 사용한다.
> **기계가독 사본**: 본 문서의 모든 스키마는 코드 저장소 `contracts/` 디렉터리에 JSON Schema로 등록되며, 문서와 스키마가 다를 경우 **스키마가 우선**한다.

## 0. 계약 목록

| ID | 계약 | 사용 구간 | §
|---|---|---|---|
| A | `dtos.task-api/v1` | Orchestrator ↔ Agent(Plugin) | §3 |
| B | `dtos.twin-agent/v1` | SDK ↔ Twin Plugin 구현체 | §4 |
| C | `dtos.tooljob/v1` | Agent ↔ Runner (큐) | §5 |
| D | Artifact & URN 규약 | 전 구간 | §6 |
| E | Workflow Definition Schema v1 | 카탈로그 ↔ Orchestrator | §7 |
| F | Gate 정의·판정 규약 | Quality Gate 엔진 ↔ 워크플로우 | §8 |
| G | Orchestrator 외부 API (UI-facing) | Web UI ↔ Gateway | §9 |
| H | Twin Plugin Manifest v1 | Plugin ↔ Kernel 로더 | §10 |

---

## 1. 공통 규약 (Common Conventions)

### 1.1 식별자

| 종류 | 형식 | 예 | 발급자 |
|---|---|---|---|
| run_id | `run-` + ULID | `run-01J8ZC3AK7...` | Orchestrator |
| step_id(task_id) | `step-` + ULID | `step-01J8ZC4Q2M...` | Orchestrator |
| tooljob_id | `tj-` + ULID | `tj-01J8ZC5R8N...` | Agent |
| project_id | `PRJ-` + 숫자 | `PRJ-031` | Gateway |
| 자산 URN | §6 문법 | `urn:dtos:asset:PRJ-031:trim-B:fmh.interior_mesh:v4` | Artifact 서비스 |

- 모든 ID는 대소문자 구분(case-sensitive)이며 발급자 외에는 생성 MUST NOT.

### 1.2 공통 스칼라 규약

- 시각: ISO 8601 UTC (`2026-07-05T09:30:00Z`). 로컬 시간 MUST NOT.
- 단위: 수치 필드는 **필드명에 단위를 접미**한다 (`drop_height_m`, `velocity_kmh`, `wall_sec`). 무단위 수치 필드 신설 MUST NOT.
- 인코딩: UTF-8 JSON. 필드명은 `snake_case`.

### 1.3 에러 모델 (전 계약 공통)

```json
{
  "error": {
    "class": "tool_transient_error | tool_numerical_error | agent_generation_error | input_error",
    "message": "사람이 읽는 요약 (1문장, 한국어 허용)",
    "retryable": true,
    "detail_ref": "s3://.../job.msg",
    "data": {}
  }
}
```

- `class`의 의미와 기본 대응은 02 문서 §5를 따르며 동결 항목(F7)이다.
- `retryable`: 발신자가 판단해 명시 MUST. 수신자는 이 값과 워크플로우 retry 정책으로 재시도를 결정한다.
- 새로운 실패 유형은 4분류 중 하나로 귀속시켜야 하며, 분류 신설은 계약 minor 버전 업이다.

### 1.4 멱등성

- 쓰기 요청(작업 제출)은 발급자가 부여한 ID(step_id, tooljob_id)가 멱등키다.
- 동일 ID 재제출 시 수신자는 **새 작업을 만들지 않고 기존 작업의 현재 상태를 반환** MUST (HTTP 200, 큐는 dedup).
- 멱등키의 보존 기간은 최소 30일.

### 1.5 인증·전송

- 서비스 간 REST: `Authorization: Bearer <service-token>` (MVP: 정적 토큰, P3: OIDC client-credentials).
- Runner: 큐(Redis) 자격증명만 보유. inbound 포트 개방 MUST NOT (F3).
- 모든 REST 응답은 `Content-Type: application/json; charset=utf-8`.

### 1.6 버전·호환성 규칙

- 계약 버전은 URI/큐 이름에 명시한다 (`/v1/tasks`, `tooljob.abaqus.v1`).
- **하위호환(minor)**: 필드 추가, enum 값 추가(수신자는 미지의 enum을 `unknown`으로 처리 MUST), 신규 endpoint. 기존 필드의 의미 변경 MUST NOT.
- **파괴적(major)**: 필드 삭제/의미 변경/필수화 → v2 신설. v1은 최소 2 minor 릴리스 동안 병행 유지.
- 수신자는 **모르는 필드를 무시**하고 에러 내지 않아야 한다(MUST). 검증은 알려진 필드에만 적용.

---

## 2. 시스템 상호작용 지도

```
Web UI ──(G)── Gateway/Orchestrator ──(A)── Twin Plugin(Agent)
                     │  ▲                        │
                 (E,F)│  │(A: callback)       (C)│  Redis 큐
                     ▼  │                        ▼
              Workflow/Gate 카탈로그         Runner (Abaqus/FMU/...)
                                                 │
              전 구간 공통: (D) Artifact & URN ──┘ (MinIO)
```

---

## 3. Contract A — `dtos.task-api/v1` (Agent 전송 계약)

모든 Agent(Twin Plugin 포함)가 구현하는 REST 계약. SDK가 기본 구현을 제공한다.

### 3.1 엔드포인트

| Method | Path | 동작 | 응답 |
|---|---|---|---|
| POST | `/v1/tasks` | 작업 제출(비동기) | 202 + TaskStatus / 200(멱등 재제출) |
| GET | `/v1/tasks/{task_id}` | 상태 조회 | 200 TaskStatus / 404 |
| POST | `/v1/tasks/{task_id}/cancel` | 취소 요청 | 202 (취소는 비동기, 최종 상태는 조회로 확인) |
| GET | `/v1/capabilities` | 지원 action + 스키마 | 200 Capabilities |
| GET | `/v1/health` | 헬스체크 | 200 `{"status":"ok","version":"..."}` |

### 3.2 TaskRequest (POST /v1/tasks)

```json
{
  "task_id": "step-01J8ZC4Q2M",
  "run_id": "run-01J8ZC3AK7",
  "project_id": "PRJ-031",
  "agent": "fmh_twin",
  "action": "prepare",
  "inputs": { },
  "context": {
    "artifacts_base": "s3://dtos/PRJ-031/run-01J8ZC3AK7/step-01J8ZC4Q2M/",
    "callback_url": "https://orch/v1/callbacks/step-01J8ZC4Q2M",
    "deadline": "2026-07-06T00:00:00Z",
    "trace_id": "tr-..."
  }
}
```

- `inputs`는 action별 스키마(§4, capabilities에 공개)로 검증 MUST — 위반 시 400 + `input_error`.
- `callback_url`: 상태가 terminal(§3.4)이 될 때 Agent가 TaskStatus 전문을 POST한다(최대 3회 재시도, 지수 백오프). **콜백은 최적화이고 폴링이 기준**이다 — Orchestrator는 콜백 유실을 폴링으로 복구 MUST.

### 3.3 TaskStatus (GET 응답·콜백 공통)

```json
{
  "task_id": "step-01J8ZC4Q2M",
  "status": "queued",
  "progress": {"pct": 62, "message": "case 17/28 running", "updated_at": "..."},
  "outputs": { },
  "artifacts": [ {"kind": "fmh.case_bundle", "uri": "s3://...", "urn": "urn:...", "checksum": "sha256:..."} ],
  "metrics": {"wall_sec": 5400, "license_tokens": 5},
  "gate_results": [ ],
  "error": null,
  "started_at": "...", "finished_at": null
}
```

- `outputs`는 **64KB 이하의 JSON** MUST. 초과 데이터는 artifacts로 내리고 참조만 담는다.
- `gate_results`: Agent가 자체 수행한 게이트 판정(§8.2 GateResult 배열). 워크플로우의 `gates_after`는 Orchestrator가 별도 판정한다.

### 3.4 상태 기계

```
queued → running → succeeded | failed | cancelled
   └──────┴─────────→ cancelled
```

- terminal 상태(succeeded/failed/cancelled)에서의 상태 변경 MUST NOT.
- `cancel` 수신 시: queued면 즉시 cancelled, running이면 중단 시도 후 cancelled 또는 (중단 불가 시점이면) 완주 후 succeeded/failed. 어느 쪽이든 응답은 202.
- Agent 프로세스 재시작 시 running 작업은 복구하거나 failed(`tool_transient_error`, retryable=true)로 마감 MUST — 좀비 상태 금지.

### 3.5 Capabilities

```json
{
  "agent": "fmh_twin",
  "contracts": ["dtos.task-api/v1", "dtos.twin-agent/v1"],
  "plugin_version": "1.0.0",
  "actions": [
    {"action": "prepare", "input_schema": {"$ref": "contracts/twin-agent/v1/prepare-input.json"},
     "output_schema": {"$ref": "..."}, "asset_types_in": ["fmh.interior_mesh"], "asset_types_out": ["fmh.case_bundle"]}
  ]
}
```

Orchestrator는 기동 시 capabilities를 검증하고, 워크플로우가 요구하는 action이 없으면 해당 워크플로우를 비활성화 MUST.

---

## 4. Contract B — `dtos.twin-agent/v1` (Twin 수명주기 계약)

Twin Plugin이 구현하는 4개 action의 입출력 모델. task-api의 `inputs`/`outputs`에 실리는 내용의 표준이다.

### 4.1 공통 모델

```json
// CaseSpec — prepare 입력의 핵심 (워크플로우 input_schema가 도메인 필드를 추가 제약)
{
  "twin_kind": "automotive.interior_impact.fmh",
  "params": { "target_zone": "A-pillar_upper", "grid_spacing_mm": 25, "hic_d_target": 900 },
  "asset_refs": { "interior_mesh": "urn:...", "headform": "urn:..." },
  "template_overrides": {}          // MAY. 승인된 범위 내 템플릿 파라미터 재정의
}
```

### 4.2 action별 입출력 (요약 표 + 필수 필드)

| action | inputs (필수) | outputs (필수) |
|---|---|---|
| `prepare` | `case_spec: CaseSpec` | `cases[]`, `case_summary`, `checks[]` |
| `run` | `case_ref` (cases[i].ref), `execution{cpus, max_license_tokens}` | `result_ref`, `run_metrics` |
| `validate` | `result_refs[]`, `criteria[]` | `verdicts`, `worst_cases[]` |
| `report` | `verdicts_ref`, `report_spec{template_key, format, lang}` | `report_ref`, `summary_ref` |

```json
// prepare.outputs
{
  "cases": [
    {"case_id": "A17", "ref": "urn:...:fmh.case_bundle:...#A17",
     "label": "A-pillar upper / angle 50°", "est_wall_sec": 3600}
  ],
  "case_summary": "28 cases (7 targets × 4 angles), est. 6h on 5 tokens",
  "checks": [ {"severity": "warning", "code": "mesh.coarse_region", "message": "...", "location": "..."} ]
}

// run.outputs — 1 케이스 단위 (foreach 팬아웃은 Orchestrator가 case별 run task를 생성)
{
  "result_ref": "urn:...:fmh.impact_result:...",
  "run_metrics": {"increments": 41200, "warnings": 3, "energy_ratio": 0.041, "wall_sec": 3520}
}

// validate.outputs
{
  "verdicts": {
    "ref": "urn:...:fmh.verdict_table:...",        // 전체 판정표(아티팩트)
    "n_cases": 28, "n_pass": 26, "n_fail": 2,
    "items": [ {"case_id": "A17", "qoi": "hic_d", "measured": 1042.0,
                "limit": 1000.0, "direction": "max", "verdict": "fail",
                "evidence_ref": "urn:...#A17/accel_curve"} ]
  },
  "worst_cases": ["A17", "B03"]
}
// items는 최대 200개까지 인라인, 초과분은 ref 아티팩트에만 (64KB 규칙)

// report.outputs
{ "report_ref": "urn:...:report.docx:...", "summary_ref": "urn:...:report.html:...",
  "numbers_manifest_ref": "urn:..." }   // 보고서에 삽입된 모든 수치의 출처 목록 → gate.report.consistency가 검사
```

### 4.3 의미 규칙

- `validate`는 **전달받은 result_refs 외의 데이터를 재계산에 사용 MUST NOT** (lineage 보장).
- `report`는 수치를 생성하지 않고 `numbers_manifest`로 모든 수치의 출처(verdict item 또는 result_ref)를 선언 MUST.
- SDK는 4 메서드를 task-api action으로 노출하고 엔벨로프·멱등·원장 기록을 대행한다(08 문서 §4.1). Plugin 코드가 HTTP를 직접 다루는 것 MUST NOT.

---

## 5. Contract C — `dtos.tooljob/v1` (Runner 큐 계약)

### 5.1 큐 토폴로지 (Redis)

| 키 | 용도 |
|---|---|
| `tooljob.{tool}.v1` (LIST) | 작업 큐. 예: `tooljob.abaqus.v1` — Runner가 BRPOP |
| `tooljob.result.v1` (STREAM) | ToolJobResult 발행 (Agent가 소비) |
| `tooljob.progress.v1` (STREAM) | ProgressEvent 발행 (Orchestrator/UI 중계) |
| `tooljob.cancel.{tooljob_id}` (KEY, TTL 24h) | 취소 신호. Runner는 실행 중 주기 확인(≤30s 간격) MUST |
| `runner.heartbeat.{runner_id}` (KEY, TTL 90s) | 생존 신호. 30s마다 갱신 MUST |

### 5.2 ToolJob 메시지

```json
{
  "tooljob_id": "tj-01J8ZC5R8N",
  "task_id": "step-01J8ZC4Q2M", "run_id": "run-...",
  "tool": "abaqus", "op": "run_job",
  "inputs": [ {"uri": "s3://.../A17.inp", "checksum": "sha256:...", "dest": "A17.inp"} ],
  "params": {"job_name": "A17", "cpus": 4, "max_license_tokens": 5},
  "output_prefix": "s3://dtos/PRJ-031/run-.../step-.../A17/",
  "timeout_sec": 14400,
  "submitted_at": "..."
}
```

### 5.3 ToolJobResult

```json
{
  "tooljob_id": "tj-01J8ZC5R8N", "task_id": "step-01J8ZC4Q2M",
  "status": "succeeded | failed | cancelled",
  "artifacts": [ {"kind": "cae.odb", "uri": "s3://.../A17.odb", "checksum": "sha256:...", "size": 812345678} ],
  "metrics": {"wall_sec": 3520, "license_tokens": 5, "exit_code": 0},
  "tool_diagnosis": {"convergence_ok": true, "energy_ratio": 0.041, "warnings": 3},
  "error": null,
  "runner_id": "abaqus-runner-01", "finished_at": "..."
}
```

### 5.4 ProgressEvent

```json
{ "tooljob_id": "tj-...", "task_id": "step-...", "ts": "...",
  "channel": "sta",                       // 진행 채널: sta | stdout | telemetry.* (네임스페이스 개방 — 06 문서)
  "pct": 62, "message": "increment 1240/2000",
  "series": {"name": "kinetic_energy", "t": 0.0124, "v": 3.2e5} }  // MAY: 시계열 샘플
```

### 5.5 Runner 의무사항

- 실행 전: 입력 checksum 검증, 라이선스 토큰 확인(부족 시 큐 반환 — 소비하지 않은 것으로 처리), 디스크 확인. 위반 시 `tool_transient_error`.
- Runner는 결정적 실행기다: **LLM 호출 MUST NOT**, 입력 변형 MUST NOT (F3).
- heartbeat 만료 + running 작업 = Agent가 `tool_transient_error(retryable)`로 회수 MUST.
- 동일 tooljob_id 중복 수신 시(재큐잉) 기존 workdir 폐기 후 재실행 — 결과는 마지막 실행 기준.

---

## 6. Contract D — Artifact & URN 규약

### 6.1 URN 문법

```
urn:dtos:asset:{scope}:{name}:{kind}:{version}
  scope   = project_id | "shared"
  name    = [a-z0-9-]+            (자산 논리명)
  kind    = 네임스페이스 문자열 (§6.2)
  version = "v" 정수  |  ULID     (run 생성물은 ULID)
프래그먼트: urn...#A17            (번들 내 개별 항목)
```

### 6.2 kind 네임스페이스

- 형식: `{domain}.{type}` — 예: `cae.odb`, `fmh.impact_result`, `report.docx`, `ml.surrogate`, `sim.usd`, `ros.bag`.
- 신규 kind는 Plugin manifest의 `asset_types`로 선언하며 등록 시 예약된다. **enum 고정 MUST NOT** (F2, Physical AI 확장 근거).

### 6.3 저장 규칙

- 경로: `s3://dtos/{project}/{run}/{step}/{filename}` (01 문서 §5.2).
- 모든 아티팩트는 불변(immutable) MUST. 수정 = 새 버전 업로드 + 메타 행 추가.
- 업로드자는 `sha256` 체크섬을 메타에 기록 MUST, 다운로더는 검증 SHOULD(대용량 ODB는 크기+ETag 허용).
- ArtifactRef 객체 표준형: `{"urn": "...", "uri": "s3://...", "kind": "...", "checksum": "sha256:...", "size": 123}` — `uri`+`kind`는 필수, `urn`은 등록 후 필수.

---

## 7. Contract E — Workflow Definition Schema v1

02 문서 §4의 YAML 형식 확정판. 필드 정의:

| 필드 | 필수 | 타입/의미 |
|---|---|---|
| `key`, `version`, `description` | ✅ | 식별. `key`+`version`으로 카탈로그 유일 |
| `input_schema` | ✅ | Task Plan `inputs` 검증용 JSON Schema 경로 |
| `steps[].id` | ✅ | run 내 유일, `[a-z0-9_]+` |
| `steps[].type` | — | 생략 시 `agent`. `hitl` = 승인 게이트 |
| `steps[].agent` / `action` | agent형 ✅ | capabilities에 존재 MUST (기동 시 검증) |
| `steps[].inputs` | — | 표현식 바인딩: `{prev_step_id}.output.{path}` 또는 `inputs.{path}` |
| `steps[].foreach` | — | 배열 경로. Orchestrator가 원소별 task 팬아웃, 전체 join. 동시성은 리소스 정책(라이선스 슬롯)이 제한 |
| `steps[].retry` | — | `{max: int, on: [error_class...]}` — on에 없는 class는 즉시 실패 처리 |
| `steps[].gates_after` | — | §8 gate key 배열. 전부 pass여야 다음 step |
| `steps[].on_gate_fail` | — | `escalate_hitl`(기본) 또는 재실행할 step id |
| hitl형: `gate_key` | ✅ | approvals 기록 키 |
| hitl형: `show` | — | 승인 화면에 표시할 output 경로 배열 |
| hitl형: `on_reject` | — | 반려 시 재실행 step id (반려 사유가 해당 step inputs에 `review_comments`로 주입됨) |

실행 의미:

- step 순서는 선언 순서. 병렬화는 `foreach`로만 표현한다(v1). 임의 DAG는 v2 후보.
- HITL step에서 Orchestrator는 checkpoint 저장 후 정지 MUST. 승인 API(§9)가 재개한다. 대기 시간 무제한.
- 워크플로우 YAML은 Git 버전관리 + 카탈로그 등록으로만 활성화(사람 승인, F5·09 문서 승격 게이트).

---

## 8. Contract F — Gate 정의·판정

### 8.1 Gate 정의 (YAML)

```yaml
key: gate.fmh.energy
version: "1.0"
applies_to: "run"                    # input | run | result | report
impl: "builtin:ratio_threshold"      # 내장 룰 또는 "python:plugins.fmh_twin.gates:check_energy"
params: {numerator: "ALLAE", denominator: "ALLIE", max_ratio: 0.10}
on_fail_default: "escalate_hitl"
```

### 8.2 GateResult

```json
{ "gate_key": "gate.fmh.energy", "gate_version": "1.0",
  "status": "pass | fail | warn",
  "measured": {"ratio": 0.041}, "threshold": {"max_ratio": 0.10},
  "evidence_ref": "urn:...", "message": "artificial energy 4.1% < 10%", "ts": "..." }
```

- `warn`은 진행을 막지 않으나 원장에 기록되고 승인 화면에 노출 MUST.
- Gate 구현은 결정적 MUST — 같은 입력에 같은 판정. LLM 판단이 필요한 검사는 gate가 아니라 HITL 자료 생성으로 구현한다.

---

## 9. Contract G — Orchestrator 외부 API (UI-facing)

### 9.1 REST

| Method | Path | 요약 |
|---|---|---|
| POST | `/v1/intents` | `{project_id, text}` → `{task_plan, open_questions[], confidence}` |
| POST | `/v1/runs` | `{task_plan}` → 201 `{run_id}` (input_schema 검증) |
| GET | `/v1/runs/{id}` | RunView: run + steps 트리 + gate/approval 현황 |
| GET | `/v1/runs?project_id=&status=&page=` | 목록 (페이지네이션: `page`,`per_page≤100`) |
| POST | `/v1/runs/{id}/approvals/{gate_key}` | `{decision: approved|rejected, reason_code, comment}` → checkpoint 재개. **rejected 시 reason_code 필수** (09 문서) |
| POST | `/v1/runs/{id}/cancel` | 실행 취소 (하위 task/tooljob으로 전파) |
| GET | `/v1/workflows` | 카탈로그 목록 |

`reason_code` enum(v1): `condition_error | material_error | result_doubt | report_wording | judgment_hold | other`.

### 9.2 WebSocket 이벤트 (`/v1/runs/{id}/events`)

```json
{ "type": "step.progress", "run_id": "...", "ts": "...", "data": { } }
```

| type | data |
|---|---|
| `run.status` | `{status}` — run 상태 전이 |
| `step.status` | `{step_id, status, attempt, error?}` |
| `step.progress` | ProgressEvent 중계(§5.4) |
| `gate.result` | GateResult(§8.2) |
| `hitl.requested` | `{gate_key, show:[{label, ref|value}]}` |
| `artifact.created` | ArtifactRef |

- 이벤트는 at-least-once 전달. UI는 `type`+`ts` 중복 무시 SHOULD. 신규 type 추가는 minor(수신자는 미지 type 무시 MUST).

---

## 10. Contract H — Twin Plugin Manifest v1

08 문서 §3.3 형식의 필드 확정:

| 필드 | 필수 | 검증 규칙 |
|---|---|---|
| `name` | ✅ | `[a-z0-9_]+`, 전역 유일 |
| `version` | ✅ | semver |
| `twin_kind` | ✅ | `{domain}.{subdomain}.{name}` |
| `agent.class`, `agent.contract` | ✅ | contract는 `dtos.twin-agent/v1` |
| `connectors_required[]` | ✅ | `{name}>={semver}` — 기동 시 Runner 가용성 검사 |
| `asset_types[]` | ✅ | §6.2 형식. 타 플러그인과 충돌 시 로드 실패 |
| `gates[]`, `kpis[]`, `workflows[]` | ✅ | 참조 파일 존재 검증 |
| `regression_suite` | ✅ | Test Harness 등록 경로 |
| `trust_tier` | ✅ | `core|partner|experimental` — MVP는 core만 로드 |

로더 규칙: manifest 검증 실패 시 해당 플러그인만 비활성 + 경고 (전체 기동 중단 MUST NOT).

---

## 11. 적합성(Conformance)

1. **계약 테스트**: `sdk/`가 제공하는 공용 테스트 스위트를 모든 Agent·Runner 구현이 통과해야 merge 가능(CI 게이트). 스위트는 §3~§5의 상태 기계·멱등성·에러 모델·64KB 규칙을 자동 검사한다.
2. **Golden examples**: `contracts/examples/`에 본 문서의 모든 예시 메시지를 유효 인스턴스로 보관하고, JSON Schema 변경 시 CI가 재검증한다.
3. **버전 태깅**: 리뷰 승인 시 본 문서와 `contracts/`를 `interface-spec/v1.0.0`으로 태깅. 이후 변경은 §1.6 규칙.

## 12. 부록 — FMH 1건의 전형적 메시지 흐름

```
UI → G:POST /v1/intents            → task_plan(workflow=fmh_impact/1.0)
UI → G:POST /v1/runs               → run-…
Orch → A:POST /v1/tasks(prepare)   → cases[28], checks[]      (gate.input.*, gate.fmh.target_grid)
Orch ⏸ hitl.requested(plan_approval) … UI 승인(approved)
Orch → A:POST /v1/tasks(run) ×28   → Plugin → C:LPUSH tooljob.abaqus.v1 ×28
Runner → C:progress/result streams → run_metrics, cae.odb     (gate.run.convergence, gate.fmh.energy)
Orch → A:POST /v1/tasks(validate)  → verdicts(26 pass/2 fail), worst=[A17,B03]  (gate.fmh.hic_sanity)
Orch → A:POST /v1/tasks(report)    → report.docx + numbers_manifest             (gate.report.consistency)
Orch ⏸ hitl.requested(report_approval) … 승인 → run.status=succeeded
```
