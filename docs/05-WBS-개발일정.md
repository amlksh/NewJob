# V-DTOS 개발 일정 (WBS) 및 단계별 산출물

> 전제 인력: PM 1, Digital Twin Architect 1, CAE/Solver Specialist 1, AI Platform Engineer 1 (+P2부터 Domain/V&V Expert 0.5)
> 계획서 7장·14장의 로드맵을 주 단위 WBS로 구체화. MVP Use Case는 1개로 축소(00 문서 2.3)하며, 대상은 **FMH Digital Twin으로 확정**(08 문서). 기존 FMH 자동화 자산 이식으로 M1 템플릿 리스크가 낮아진 만큼, 확보 여유는 Plugin 구조화(TwinAgent·manifest)에 투입한다 — 일정 총량 불변.

---

## Phase 1 — MVP (M1~M3, 12주)

### M1 (주 1~4): 기반 구축

| WBS | 작업 | 담당 | 산출물 (완료 기준) |
|---|---|---|---|
| 1.1 | 요구사항 확정: FMH MVP 범위(대상 차종/존, 케이스 규모), 승인 프로세스 정의 | PM+전원 | 요구사항 정의서, 성공 기준 합의(HIC 판정 일치율 포함) |
| 1.2 | 데이터 스키마 구현: Postgres(runs/steps/artifacts/templates/materials) + 자산 URN/lineage, MinIO 규약 | Platform | 마이그레이션 + CRUD 테스트 통과 |
| 1.3 | Plugin SDK 최소 구현: TwinAgent 베이스(`prepare/run/validate/report`), task-api 자동 노출, manifest 스키마 | Platform | `sdk/` + 계약 테스트 |
| 1.4 | Abaqus Runner v0: 큐 폴링→실행→업로드, .sta 파서 | CAE+Platform | 수동 제출 INP의 무인 실행 성공 |
| 1.5 | FMH 자산 이식: 기존 FMH 자동화 스크립트→`plugins/fmh_twin/templates/`+`libs/cae_toolkit`, param_schema 작성 | CAE | FMH 템플릿 등록 + 파라미터 조립 검증 |
| 1.6 | LLM Gateway v0: 마스킹 사전, 호출 로깅 | Platform | 게이트웨이 경유 호출 데모 |
| 1.7 | UI 목업 + 내부 검증용 Streamlit 화면 | Architect | run 목록/로그 조회 가능 |

### M2 (주 5~8): 파이프라인 조립

| WBS | 작업 | 담당 | 산출물 |
|---|---|---|---|
| 2.1 | FmhTwinAgent 구현: `prepare`(타겟 전개·포지셔닝·INP)/`run`/`validate`(HIC(d) 산출·판정) | CAE+Platform | 케이스 매트릭스→ODB→HIC 판정까지 API로 완주 |
| 2.2 | Orchestrator v0: `fmh_impact/1.0` 워크플로우 로더, foreach 팬아웃, 순차 실행, 원장 기록 | Platform | 워크플로우 1회 무인 완주(승인 게이트 스텁) |
| 2.3 | Quality Gate v0: input/units, convergence, `gate.fmh.*`(energy, target_grid, hic_sanity) 룰 | CAE | 게이트 판정 테스트셋 통과 |
| 2.4 | Report 서비스: FMVSS 201U docx 템플릿, `generate`/`revise`, 일관성 검사 + Twin `report()` 연동 | Architect+Platform | 판정 JSON→보고서 초안 자동 생성 |
| 2.5 | **HIC 판정 일치율 검증**: 기존 수동 프로세스 결과 대비 자동 판정 비교 (과거 케이스 재현) | CAE | 판정 일치율 리포트(목표 100%) |
| 2.6 | Intent 해석: 자연어→Task Plan(분류+추출+질문), 평가셋 30문항 | Platform | 추출 정확도 리포트 |

### M3 (주 9~12): HITL·UI·PoC 적용

| WBS | 작업 | 담당 | 산출물 |
|---|---|---|---|
| 3.1 | HITL 게이트: LangGraph checkpoint(Postgres), 승인 API, 재개 | Platform | 승인 대기→며칠 후 재개 시나리오 통과 |
| 3.2 | React UI v1: run 모니터링(WebSocket), 승인/반려, 산출물 뷰어 | Platform+Architect | 내부 사용자 UI로 전 과정 수행 |
| 3.3 | 실패 복구: error_class 분류, 재시도, 에스컬레이션 | Platform | 장애 주입 테스트 통과 |
| 3.4 | **내부 PoC: 실제 FMH 프로젝트 1건 end-to-end 적용** | 전원 | PoC 결과 보고서, FMH KPI 1차 실측(판정 일치율·자동 성공률·케이스당 시간) |
| 3.5 | MVP 회고·Phase 2 계획 확정 | PM | Phase 2 백로그 |

**Phase 1 게이트 리뷰**: §MVP 성공 기준(04 문서 1장) 충족 여부 → 미충족 항목은 P2 진입 전 2주 버퍼로 보완.

---

## Phase 2 — Pilot (M4~M6)

| WBS | 작업 | 산출물 |
|---|---|---|
| 4.1 | `diabetes_twin` Plugin: TwinAgent 구현(cohort 시나리오→FMPy 실행→RMSE/TIR 판정) + FMU Runner | FMU cohort 검증 자동화 (계획서 Use Case 2) — **두 번째 플러그인으로 SDK 계약 검증** |
| 4.2 | `diabetes_cohort/1.0` 워크플로우 등록 + Plugin SDK 계약 동결(v1) | 워크플로우 2종 운영, SDK v1 확정 |
| 4.3 | V&V Agent 확장: CoU/QoI/MRA 초안, CAR 초안 (ASME V&V 40 템플릿) | CAR 자동 초안 + HITL 승인 흐름 |
| 4.4 | Test Harness: 축소판 회귀 시나리오 야간 실행, 성공률 리포트 | 회귀 대시보드 |
| 4.5 | Evaluation 대시보드: 원장 기반 KPI 자동 집계 | KPI 대시보드 (계획서 12장 지표) |
| 4.6 | CAE 진단 고도화: 실패 로그 LLM 요약, 재해석 파라미터 제안(승인 후 적용) | 진단 리포트 v2 |
| 4.7 | **PoC #2: 질환 Solver 검증 프로젝트 적용** | PoC 보고서, KPI 2차 실측 |

---

## Phase 3 — Platform (M7~M12)

| WBS | 작업 | 산출물 |
|---|---|---|
| 5.1 | MBSE Agent: 요구사항 추출, requirements/trace_links, ReqIF/CSV | Traceability Matrix 자동 생성 |
| 5.2 | Knowledge 고도화: 과거 run 임베딩, 유사 프로젝트 추천, 템플릿 추천 | 추천 기능 |
| 5.3 | 워크플로우 초안 합성 (기존 블록 조합, 사람 등록 후 실행) | 카탈로그 확장 도구 |
| 5.4 | Project Dashboard: 멀티 프로젝트 현황, 승인 대기함, KPI | 운영 대시보드 |
| 5.5 | 운영 전환: RBAC, 온프레미스 LLM 옵션 검증, k8s 검토, 백업/DR | 운영 준비도 점검표 |
| 5.6 | 고객 제출용 템플릿 확장(고객별 보고서, PPT) | 템플릿 카탈로그 |
| 5.7 | **외부/내부 프로젝트 3건 이상 운영** | 재사용성 KPI 달성 근거 |

---

## Phase 4 — Physical AI 확장 (M12+)

06 문서 참조. 주요 마일스톤: Sim Agent 계약 구현(M13) → Isaac Sim Runner PoC(M14~15) → 로봇/제조 디지털트윈 데모(M16+).

---

## 마일스톤 요약

| 시점 | 마일스톤 | 검증 방법 |
|---|---|---|
| M1 말 | 수동 INP 무인 실행 + FMH 템플릿 이식 완료 + SDK 최소 구현 | 데모 |
| M2 말 | `fmh_impact` 워크플로우 무인 완주(게이트 스텁) + HIC 판정 일치율 확인 | 데모 + 일치율 리포트 |
| M3 말 | **MVP: 실제 FMH 프로젝트 1건 end-to-end** | PoC 보고서 + FMH KPI 실측 |
| M6 말 | `diabetes_twin`(SDK 계약 검증) + CAR 초안 + KPI 대시보드 | PoC #2 |
| M12 말 | 플랫폼: 3개 프로젝트 동시 운영, Traceability | 운영 지표 |

## 리스크 버퍼 및 인력 유의사항

- 각 Phase 말 **2주 버퍼**를 명시적으로 확보 (위 표의 기간에 포함).
- 최대 병목은 **AI Platform Engineer 1명에 집중되는 부하** (Orchestrator+Gateway+Runner+UI). 계획서 13장의 "외부 개발자 1명 단기 투입"은 M1~M3 프론트엔드(React UI v1)에 배정하는 것이 가장 효과적이다.
- Abaqus 라이선스 토큰이 PoC 기간 병렬 실행의 상한을 결정하므로, M1에서 가용 토큰 기준 동시 실행 슬롯을 확정할 것.
