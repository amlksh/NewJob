# MVP 범위 정의 및 기술 스택 확정안

---

## 1. MVP 정의

**"자연어 요청 → 낙하/FMH 해석 케이스 생성 → 사람 승인 → Abaqus 자동 실행 → 자동 검증 → 보고서 초안 → 사람 승인 → 발행"** 을 실제 프로젝트 1건에서 end-to-end로 완주하는 것.

성공 기준 (측정 가능):

1. 템플릿 커버리지 내 요청의 **80% 이상**이 사람 수정 없이 케이스 생성 통과
2. Job 실행~결과 추출까지 **무인 자동화 100%** (실패 시 자동 분류·보고 포함)
3. 보고서 초안 작성 시간: 수작업 대비 **50% 이상 단축** (기준선 실측 대비)
4. 모든 run이 원장에 기록되어 KPI 자동 집계 가능

## 2. MVP 필수 기능 vs 후속 기능

### 2.1 MVP 필수 (Phase 1, 0~3개월)

| 영역 | 포함 기능 |
|---|---|
| Orchestrator | Intent→Task Plan, 워크플로우 카탈로그(1종: drop_test), HITL 게이트 2개, checkpoint 재개, 실패 분류·재시도, 원장 기록 |
| CAE Agent | `generate_case`(템플릿 2종), `validate_input`, `run_job`, `extract_results`, `diagnose`(룰 기반) |
| Abaqus Runner | 큐 폴링 실행, .sta/.msg 파싱, 진행 이벤트, 라이선스 확인, 취소 |
| V&V Agent | `check_results` (판정표) — 최소 구현 |
| Report Agent | `generate`(docx+html, 템플릿 1종), `revise`, 수치 일관성 검사 |
| Web UI | 프로젝트/run 목록, 진행 모니터링(WebSocket), 승인/반려 화면, 산출물 뷰어 |
| 저장소 | Postgres 스키마(01 문서 5.1), MinIO, Template DB, Material DB(수동 등록) |
| LLM Gateway | 마스킹, 비용 계측, 프롬프트/응답 로깅 |
| Quality Gate | `gate.input.*`, `gate.run.convergence`, `gate.run.energy`, `gate.report.consistency` |

### 2.2 후속 기능 (명시적 제외 → 어느 Phase에서)

| 기능 | Phase | 제외 사유 |
|---|---|---|
| FMU/질환 Solver Agent 전체 | P2 | MVP 단일 파이프라인 집중 |
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
│   └── runners/
│       ├── abaqus_runner/
│       └── fmu_runner/         # P2
├── agents/
│   ├── common/           # 표준 Task API 서버 베이스, 엔벨로프 모델
│   ├── cae/
│   ├── vnv/
│   ├── report/
│   ├── fmu/              # P2
│   └── mbse/             # P3
├── workflows/            # YAML 카탈로그 (버전 디렉터리)
├── templates/            # INP/스크립트/보고서/V&V 템플릿
├── libs/                 # 공용: artifact client, ledger, gates(룰 엔진)
└── infra/                # docker-compose, 마이그레이션(alembic)
```
