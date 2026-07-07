# 16. DTOS Service API (CTO Development Directive No.003)

> 목적: DTOS 표준 Service API 구축 — WMIT 사업에서는 **Diabetes Service만** 외부 제공.
> 본 API 구조는 향후 모든 Solver(FMH·Hearing·MSK)가 공통 사용하는 표준이다.

---

## 1. 표준 아키텍처 (지시서 §2 — 5계층)

```
Client ─▶ API Layer(apps/api) ─▶ Service Layer(services/diabetes)
              │ REST·인증·요청검증·         │ Run 생성·상태/검증/보고서/아티팩트
              │ 봉투/오류 (비즈니스 금지)     │ 제공·Audit(Engine 경유) (계산 금지)
              ▼                            ▼
        Plugin Layer(plugins/diabetes_twin — 도메인 로직)
              ▼
        Adapter Layer(disease_solver_runner — 입출력 규격 흡수)
              ▼
        Solver(DiabetesSystem HTML 커널 — 절대 무수정)
```

### 계층 규칙(§3) 이행 방식 — 전부 정적 검사로 강제 (tests/api)

| Rule | 이행 |
|---|---|
| 1. Core 수정 금지 | Core 파일 diff 0. run_id 포착은 Ledger **상속 확장**(`_CapturingLedger`) — Core 코드 무변경 |
| 2. Solver 수정 금지 | 자산 파일 읽기만 (기존 보장 유지) |
| 3. API는 Service만 호출 | `apps/api`는 `services.diabetes` + 모델만 import — Core/Runner/Plugin 토큰 금지 검사 |
| 4. Service는 Plugin만 호출 (Adapter 직접 호출 금지) | Service는 `engine.execute(plugin)`로 Plugin을 구동. Adapter는 **생성(팩토리 `make_tool`)·Runner 배선(DI)**만 하고 수명주기 호출은 하지 않음 — Adapter 클래스명 import 금지 검사 |
| 5·6. Plugin→Adapter→Solver | 기존 동결 구조 그대로 (ToolJob 큐 → Runner → Adapter → Solver) |

## 2. API 표면 (§4·§5)

버전 `/api/v1` · 도메인 `/{domain}` — 도메인 라우터는 팩토리
`build_domain_router(domain, service)`로 생성한다. **신규 질환 =
Service 클래스 구현 + 라우터 등록 한 줄** (API 코드 복제 없음).

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/v1/status` | 플랫폼 상태 (무인증) |
| POST | `/api/v1/diabetes/runs` | 실행 생성 (202, 비동기) |
| GET | `/api/v1/diabetes/runs/{run_id}` | 상태 (queued→running→waiting_approval→succeeded/failed/rejected) |
| GET | `/api/v1/diabetes/runs/{run_id}/validation` | 판정 결과 (n_pass/n_fail/items) |
| GET | `/api/v1/diabetes/runs/{run_id}/report` | 보고서 docx |
| GET | `/api/v1/diabetes/runs/{run_id}/artifacts` | 아티팩트 목록 (+`/{urn}` 개별 다운로드) |

- 요청/응답 봉투·오류 규격은 지시서 §6·§7·§9 그대로:
  `{"status":"success","data":{...}}` / `{"status":"error","error_code","message"}`
- 공통 오류 코드: `ERR_INVALID_PARAMETER`(400) · `ERR_UNAUTHORIZED`(401) ·
  `ERR_NOT_FOUND`(404) · `ERR_NOT_READY`(409) · `ERR_INTERNAL`(500)
- 인증(§8): `X-API-Key` 헤더 — 허용 키 `TWINOS_API_KEYS`(콤마 구분, 기본 dev-key).
  OAuth/SSO/RBAC은 차기 Release.
- run_id 형식: 동결된 ID 문법(`run-<ULID>`, Spec §1.1)을 따른다 — 지시서의
  `RUN-20260708-001`은 예시 표기로 간주(Interface Freeze 우선).

## 3. scenario → Plugin 파라미터 매핑 (Service 책임)

| 요청 필드 | 매핑 |
|---|---|
| `scenario.type` | `meal_response`만 허용 (그 외 ERR_INVALID_PARAMETER) |
| `scenario.n_patients` | `params.n_patients` (cohort 결정적 확장 — Plugin 소관) |
| `scenario.duration_min` | `params.duration_h` (분→시) |
| `scenario.meal_carbs_g` | `params.meal_carbs_g` → Plugin이 시나리오에 기재 → HTML Adapter가 커널 `meal_g`로 반영 |
| `solver.adapter` / `asset_ref` | Runner 배선 선택 (html 기본 — 동봉 DiabetesSystem) |
| `auto_approve` | true(기본): 해당 run만 자동 승인 / false: 운영 콘솔 HITL 대기 |

## 4. 비동기 실행 모델

POST /runs → 워커 스레드가 `engine.execute` 수행. Engine이 발급하는 run_id는
`_CapturingLedger.start_run` 훅(스레드 로컬 상관)으로 즉시 포착되어 202 응답에
실린다. 이후 상태·결과는 전부 **원장(runs/approvals/steps/artifacts)**에서 읽는다
(`services/common/ledger_read.py` — 읽기 전용, Core 무수정).

## 5. DoD 산출물

- 구현: `apps/api/`(FastAPI) + `services/diabetes/` — 테스트 8건(E2E 실자산 경유 포함)
- OpenAPI: `/openapi.json` (내보내기: `api/openapi-service-v1.json`)
- Swagger UI: `/docs` · Postman: `api/DTOS-diabetes.postman_collection.json`
- 기동: `scripts\run_api.bat` (127.0.0.1:8600) / `make api`
