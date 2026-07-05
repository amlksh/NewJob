# MVP 범위 정의 및 기술 스택 확정안

> **변경 반영**: MVP 대상을 **FMH Digital Twin**으로 확정 (「DTOS MVP 개발 방향 변경 및 추가 요청사항」, [08 문서](08-FMH-DigitalTwin-Plugin-설계.md) 참조). FMH는 DTOS 최초의 Digital Twin Plugin이자 표준 Twin Agent(`prepare/run/validate/report`)의 레퍼런스 구현이다.

---

## 1. MVP 정의

**"자연어 요청 → FMH 충돌 케이스 매트릭스 생성(타겟×접근각) → 사람 승인 → Abaqus 자동 실행 → HIC(d) 자동 판정 → 보고서 초안 → 사람 승인 → 발행"** 을 실제 FMH 프로젝트 1건에서 end-to-end로 완주하는 것. 구현 형태는 `plugins/fmh_twin/` Digital Twin Plugin(08 문서 §3)이다.

성공 기준 (측정 가능):

1. 템플릿 커버리지 내 요청의 **80% 이상**이 사람 수정 없이 케이스 생성 통과
2. Job 실행~결과 추출까지 **무인 자동화 100%** (실패 시 자동 분류·보고 포함)
3. **HIC(d) 판정이 기존 수동 프로세스 결과와 100% 일치** (판정 일치율 — 08 문서 §7)
4. 보고서 초안 작성 시간: 수작업 대비 **50% 이상 단축** (기준선 실측 대비)
5. 모든 run이 원장에 기록되어 KPI 자동 집계 가능

## 2. MVP 필수 기능 vs 후속 기능

### 2.1 MVP 필수 (Phase 1, 0~3개월)

| 영역 | 포함 기능 |
|---|---|
| Orchestrator | Intent→Task Plan, 워크플로우 카탈로그(1종: `fmh_impact/1.0`), HITL 게이트 2개, checkpoint 재개, 실패 분류·재시도, 원장 기록 |
| **FMH Twin Plugin** | `plugins/fmh_twin/`: TwinAgent 구현(`prepare/run/validate/report`), FMH 템플릿(기존 자동화 자산 이식), 도메인 게이트, HIC(d) 판정, manifest 정적 로딩 (08 문서) |
| Plugin SDK(최소) | TwinAgent 베이스 클래스 + task-api 자동 노출 + manifest 스키마 — FMH가 필요로 하는 범위까지만 (일반화 동결은 P2 말) |
| `libs/cae_toolkit` | INP 조립, ODB 추출, .sta/.msg 파싱 등 도구 공통 로직 (구 CAE Agent 로직의 라이브러리화) |
| Abaqus Runner | 큐 폴링 실행, .sta/.msg 파싱, 진행 이벤트, 라이선스 확인, 취소 |
| Report Agent(공용) | `generate`(docx+html, FMVSS 템플릿), `revise`, 수치 일관성 검사 — Twin의 `report()`가 호출 |
| Web UI | 프로젝트/run 목록, 진행 모니터링(WebSocket), 승인/반려 화면, 산출물 뷰어 |
| 저장소 | Postgres 스키마(01 문서 5.1) + 자산 URN/lineage 컬럼, MinIO, Template DB, Material DB(수동 등록) |
| LLM Gateway | 마스킹, 비용 계측, 프롬프트/응답 로깅 |
| Quality Gate | `gate.input.*`, `gate.run.convergence`, `gate.fmh.*`(energy, target_grid, hic_sanity), `gate.report.consistency` |
| Evaluation Engine(최소) | 원장 기반 KPI 집계 + FMH KPI 등록(판정 일치율, 자동 성공률, 케이스당 시간) |

### 2.2 후속 기능 (명시적 제외 → 어느 Phase에서)

| 기능 | Phase | 제외 사유 |
|---|---|---|
| `diabetes_twin` Plugin (FMU/질환 Solver) | P2 | MVP 단일 파이프라인 집중. P2에서 두 번째 플러그인으로 SDK 계약 검증 |
| Plugin SDK 공개 계약 동결·동적 설치/샌드박스 | P2 말~P3 | 플러그인 2개 통과 전 일반화 금지 (08 문서 §1) |
| `hearing_twin`/`spine_twin`/`battery_twin` | P3+ | 도메인 자산 준비 후 |
| CoU/QoI/MRA·CAR 초안, Test Harness | P2 | 규제 문서는 검증 체계 후 |
| Evaluation 대시보드·회귀 실행 | P2 | 원장은 MVP부터, 시각화는 P2 |
| MBSE Agent, Traceability Matrix | P3 | 요구사항 관리 프로세스 정착 필요 |
| Knowledge Graph, 유사 프로젝트 추천 | P3 | pgvector RAG로 대체 시작 |
| 워크플로우 동적 합성, 재해석 파라미터 자동 적용 | P3 | 안전성 |
| 온프레미스 LLM, RBAC, k8s | P3 | 운영 규모 도달 후 |
| Isaac Sim/Omniverse/ROS2 | P4 | 06 문서 |
| 다국어 보고서, PPT 출력, 고객별 템플릿 UI | P2~P3 | 부가 기능 |

---

## 3. 기술 스택 확정안 (계획서 11장 대비 선택 확정)

| 영역 | 확정 | 선택 이유 / 계획서 대비 |
|---|---|---|
| LLM | Claude API (또는 OpenAI) + LLM Gateway 추상화 | 코드/구조화 출력 품질. 게이트웨이로 추상화해 P3 온프레미스(vLLM) 전환 대비 |
| Agent Framework | **LangGraph** | HITL interrupt + Postgres checkpointer 내장 — 며칠 걸리는 해석 Job 중단/재개에 필수. AutoGen/CrewAI는 장시간 중단·재개 모델이 약함 |
| Backend | Python 3.11 + FastAPI + Pydantic v2 | 계획서와 동일. Agent 입출력 스키마 = Pydantic 모델 단일 소스 |
| 비동기 실행 | **Celery + Redis** | MVP 단순성. Airflow는 배치 지향이라 부적합, Prefect는 P3에서 관측성 필요 시 승격 검토 |
| Frontend | **React(Vite) + TypeScript**, UI 킷: shadcn/ui 또는 Ant Design | 승인/반려·진행 모니터링 UX는 Streamlit로는 한계. 단, 1개월차 내부 검증용 화면은 Streamlit 허용 |
| DB | PostgreSQL 16 + **pgvector** | 별도 Vector DB 대신 pgvector로 시작(운영 대상 1개 축소). 규모 커지면 Qdrant 분리 |
| Artifact Store | MinIO (S3 호환) | ODB/보고서/이미지 불변 저장, 해석서버↔백엔드 파일 교환로 |
| 문서 생성 | python-docx(docx), Jinja2+WeasyPrint(HTML→PDF) | reportlab보다 템플릿 유지보수 용이 |
| CAE 연동 | Abaqus Python API(스크립트 조립), ODB API(결과 추출), 자체 .sta/.msg 파서 | VPK 기존 자산 이식 |
| FMU (P2) | FMPy | 순수 Python, 병렬 스윕 용이 |
| 관측성 | structlog + OpenTelemetry, Grafana(선택) | LLM 호출·step 지연 추적 |
| 배포 | Docker Compose (P3에서 k8s 검토) | MVP 단일 호스트 |
| 저장소/CI | Git(모노레포) + GitHub Actions, pytest | 워크플로우 YAML·템플릿도 Git 버전관리 |

### 모노레포 구조 제안

```
dtos/
├── apps/
│   ├── gateway/          # FastAPI: 인증, 프로젝트/run API, LLM Gateway
│   ├── orchestrator/     # LangGraph 그래프, 카탈로그 로더, HITL
│   ├── web/              # React SPA
│   └── runners/          # = Connector 실행기
│       ├── abaqus_runner/
│       └── fmu_runner/         # P2
├── sdk/                  # Plugin SDK: TwinAgent 베이스, task-api 자동 노출,
│                         #   manifest 스키마, 엔벨로프 모델 (구 agents/common)
├── plugins/              # ★ Digital Twin Plugin (도메인 응집 패키지, 08 문서)
│   ├── fmh_twin/         #   MVP: agent + templates + gates + kpi + workflows + tests
│   ├── diabetes_twin/    #   P2
│   └── ...               #   hearing/spine/battery(P3) · robot(P4)
├── services/
│   ├── report/           # 공용 Report 서비스 (Twin의 report()가 호출)
│   ├── vnv/              # P2: CoU/QoI/MRA·CAR (도메인 공통 V&V)
│   └── mbse/             # P3
├── libs/
│   ├── cae_toolkit/      # INP 조립, ODB 추출, .sta 파싱 (도구 공통 로직)
│   └── core/             # artifact client(URN/lineage), ledger, gates(룰 엔진)
└── infra/                # docker-compose, 마이그레이션(alembic)
```

(구조 변경: 구 `agents/` 디렉터리는 Twin 중심 재정의에 따라 `sdk/` + `plugins/` + `services/`로 재편 — 08 문서 §3)
