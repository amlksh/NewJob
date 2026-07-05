# Agent별 개발 범위 및 API 명세

> 계획서 5장(개발 대상 모듈)의 인터페이스 정의. 모든 Agent는 §1의 공통 계약을 구현한다.
>
> **주 (Twin 중심 재정의 반영)**: §1의 task-api/v1 전송 계약은 그대로 유효하다. 다만 Digital Twin 중심 재정의([08 문서](08-FMH-DigitalTwin-Plugin-설계.md))에 따라 도메인 Agent는 **Twin Plugin의 `TwinAgent`(`prepare/run/validate/report`, twin-agent/v1)** 로 구현되며, SDK가 이를 task-api action으로 자동 노출한다(08 문서 §4.1). 본 문서의 CAE Agent(§3) action들은 FMH Plugin 내부 구현 + `libs/cae_toolkit`으로 흡수되고, FMU Agent(§4)는 `diabetes_twin` Plugin으로 구현된다. Report(§7)·V&V(§6)·MBSE(§5)는 도메인 공통 **공용 서비스**로 유지된다.

---

## 1. 공통 Agent Task API (표준 계약)

모든 Agent는 아래 REST 계약을 구현하는 독립 서비스(또는 MVP에서는 동일 프로세스 내 모듈)다.
Orchestrator는 이 계약만 사용하므로, Agent 추가/교체가 워크플로우 YAML 수정만으로 가능하다.

### 1.1 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| POST | `/v1/tasks` | 작업 제출 (즉시 `task_id` 반환, 비동기) |
| GET | `/v1/tasks/{task_id}` | 상태/결과 조회 |
| POST | `/v1/tasks/{task_id}/cancel` | 취소 |
| GET | `/v1/capabilities` | 지원 action 목록 + 입력 JSON Schema (Orchestrator가 기동 시 검증) |
| GET | `/v1/health` | 헬스체크 |

### 1.2 공통 요청/응답 엔벨로프

```json
// POST /v1/tasks  요청
{
  "task_id": "step-01H...",            // Orchestrator가 발급 (멱등키)
  "run_id": "run-0113",
  "project_id": "PRJ-024",
  "action": "generate_case",
  "inputs": { ... },                   // action별 스키마 (capabilities에 공개)
  "context": {
    "artifacts_base": "s3://dtos/PRJ-024/run-0113/",
    "callback": "https://orch/v1/callbacks/step-01H..."   // 완료 통지(폴링 병행)
  }
}

// GET /v1/tasks/{id}  응답
{
  "task_id": "step-01H...",
  "status": "queued | running | succeeded | failed | cancelled",
  "progress": {"pct": 62, "message": "increment 1240/2000"},
  "outputs": { ... },                  // 소형 JSON만. 파일은 artifacts로
  "artifacts": [
    {"kind": "odb", "uri": "s3://.../drop_v3.odb", "checksum": "..."}
  ],
  "metrics": {"wall_sec": 5400, "license_tokens": 5},
  "error": {"class": "tool_numerical_error", "message": "...", "detail_ref": "s3://.../job.msg"}
}
```

규칙: 멱등(같은 `task_id` 재제출 시 기존 작업 반환) · 대용량은 아티팩트 참조 · `error.class`는 02 문서 5장의 4분류.

---

## 2. AI Orchestrator

(API는 02 문서 7장 참조. 여기서는 개발 범위만 정리)

| 개발 항목 | MVP | 후속 |
|---|---|---|
| Intent 해석 → Task Plan JSON | ✅ (워크플로우 분류 + 파라미터 추출 + 질문 생성) | 유사 프로젝트 추천 반영 |
| 워크플로우 카탈로그 로더 (YAML→LangGraph) | ✅ | 워크플로우 초안 합성(P3) |
| HITL 게이트 + checkpoint 재개 | ✅ | 위임/에스컬레이션 정책 |
| 실패 분류·재시도 | ✅ (재시도, 게이트 실패 에스컬레이션) | 원인 추정·파라미터 제안(P2) |
| 원장(ledger) 기록 | ✅ | KPI 대시보드(P2) |

---

## 3. CAE Agent

**개발 범위** (계획서 5.2 대비: "해석 조건 자동 생성"을 템플릿 기반으로 재정의)

| 기능 | MVP | 후속 |
|---|---|---|
| 템플릿 선택 + 파라미터 주입으로 케이스 생성 (INP 조립) | ✅ 낙하/FMH 2종 | 템플릿 커버리지 확대 |
| INP 정적 검사 (단위, 물성, BC/Contact 누락) | ✅ | CAE 파일(.cae) 검사 |
| Job 실행·모니터링 (Runner 경유) | ✅ | 다중 서버 스케줄링 |
| ODB 결과 추출 (QoI, 그래프, 컨투어 이미지) | ✅ | 자동 크리티컬 위치 탐색 |
| 수렴성/에너지/Contact 진단 리포트 | ✅ (룰 기반) | LLM 원인 요약(P2) |
| 재해석 파라미터 제안 | — | P2 (사람 승인 후 적용) |

**Actions**

| action | inputs (요약) | outputs |
|---|---|---|
| `generate_case` | `template_key`, `params{}` (JSON Schema 검증), `model_ref` | `case_ref`(inp), `case_summary`(사람이 읽는 요약), `checks[]` |
| `validate_input` | `case_ref` | `issues[]` (severity, message, location) |
| `run_job` | `case_ref`, `cpus`, `max_tokens` | `odb_ref`, `log_refs[]`, `run_metrics{increments, warnings, energy_ratio}` |
| `extract_results` | `odb_ref`, `qoi_spec[]` (변수, 위치/셋, 집계) | `results_json_ref`, `images[]`, `curves[]` |
| `diagnose` | `log_refs[]`, `run_metrics` | `diagnosis{convergence, energy, contact}`, `recommendations[]` |

---

## 4. Solver/FMU Agent (Phase 2)

**개발 범위**

| 기능 | Phase 2 | 후속 |
|---|---|---|
| FMU 입출력 변수 자동 인식 (modelDescription.xml 파싱) | ✅ | FMI 3.0 |
| 시나리오 파일 생성 (cohort/파라미터 스윕) | ✅ | 시나리오 추천 |
| FMPy 기반 실행 (Runner 경유, 병렬 스윕) | ✅ | Co-Simulation 마스터 |
| 결과 비교/통계 (RMSE, TIR, 실패 케이스 요약) | ✅ | 자동 캘리브레이션 |
| Dymola/Simulink 어댑터 | 인터페이스 정의만 | P3 구현 |

**Actions**

| action | inputs | outputs |
|---|---|---|
| `inspect_fmu` | `fmu_ref` | `io_spec{inputs[], outputs[], parameters[]}` |
| `generate_scenarios` | `fmu_ref`, `design{cohort_ref | sweep_spec}` | `scenario_set_ref` (CSV/JSON) |
| `run_simulation` | `fmu_ref`, `scenario_set_ref`, `solver_opts` | `results_ref`, `failed_cases[]` |
| `compare_results` | `results_ref`, `reference_ref`, `metrics[]` (rmse, tir, ...) | `comparison_json_ref`, `plots[]` |

---

## 5. MBSE Agent (Phase 3)

**개발 범위** — CATIA Magic 직접 제어 대신 **파일 표준(ReqIF/CSV) 우선**

| 기능 | Phase 3 | 비고 |
|---|---|---|
| 문서/표에서 UR/SR/SWR/TC 자동 분류·추출 (LLM) | ✅ | 사람 확정 후 DB 반영 |
| requirements/trace_links DB 관리 | ✅ | 01 문서 5.1 스키마 |
| Traceability Matrix 생성 (요구사항↔해석run↔보고서) | ✅ | 아티팩트 링크 자동 수집 |
| ReqIF/CSV Export·Import | ✅ | CATIA Magic 교환용 |

**Actions**: `extract_requirements(doc_ref) → candidates[]` · `build_trace_matrix(project_id) → matrix_ref(xlsx/html)` · `export_reqif(project_id) → reqif_ref` · `import_reqif(reqif_ref) → diff_summary`

---

## 6. V&V Agent (Phase 2)

**개발 범위**

| 기능 | 단계 | 비고 |
|---|---|---|
| 결과 판정 (`check_results`: 기준값 대비 pass/fail 판정표) | **MVP** | Report 이전 필수 단계라 MVP에 최소 구현 |
| CoU/QoI/MRA 정의 초안 생성 (템플릿 + LLM) | P2 | ASME V&V 40 템플릿 |
| 검증 시나리오 카탈로그 관리·Test Case 실행 취합 | P2 | Test Harness와 연동 |
| Credibility Assessment Report(CAR) 초안 생성 | P2 | 반드시 HITL 승인 |

**Actions**

| action | inputs | outputs |
|---|---|---|
| `check_results` | `results_json_ref`, `criteria[]` (QoI, limit, 방향) | `verdicts_json_ref` (판정+근거) |
| `draft_cou_qoi` | `project_context`, `intended_use` | `cou_doc_ref` (docx 초안) |
| `collect_test_evidence` | `test_case_ids[]` | `evidence_bundle_ref` |
| `draft_car` | `evidence_bundle_ref`, `template_key` | `car_draft_ref` |

---

## 7. Report Agent

**개발 범위**

| 기능 | MVP | 후속 |
|---|---|---|
| 템플릿 기반 docx/HTML 생성 (수치·표·그림 자동 삽입) | ✅ | PPT, PDF(WeasyPrint) |
| 요약본/상세본 분리 생성 | ✅ | 고객별 템플릿 관리 UI |
| 반려 사유 반영 재생성 (검토 의견 → 수정) | ✅ | 문단 단위 부분 재생성 |
| 수치 일관성 자기검사 (렌더링 후 본문 수치 = 입력 JSON 대조) | ✅ | 표절/규격 문구 검사 |

**Actions**

| action | inputs | outputs |
|---|---|---|
| `generate` | `template_key`, `results_ref`, `verdicts_ref`, `narrative_opts{lang, level}` | `report_ref(docx)`, `summary_ref(html)` |
| `revise` | `report_ref`, `review_comments[]` | `report_ref(v+1)`, `change_log` |
| `render` | `report_ref`, `format(pdf|html)` | `rendered_ref` |

원칙: Report Agent는 전달받은 `results/verdicts` JSON 외의 수치를 **생성하지 않는다**. 서술(narrative)만 LLM이 작성하고, 수치는 전부 치환 필드로 주입한다.

---

## 8. (Phase 4) Sim Agent — Physical AI

06 문서 참조. 동일한 §1 계약으로 `load_scene`, `run_episode`, `collect_sensors` action을 구현한다. 계약이 같으므로 Orchestrator·UI·원장·게이트가 그대로 재사용된다.
