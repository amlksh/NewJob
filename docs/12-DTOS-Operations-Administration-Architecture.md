# 12. DTOS Operations & Administration Architecture

> Enterprise DTOS의 운영 기준 문서. 「업무지시서: DTOS Architecture Reset (Sprint 0)」 §8~§12에 따라 작성.
> 원칙: **이번 Sprint는 구조 설계가 목표이며 구현은 최소화한다** — 각 절에 [MVP 구현] / [설계만] 을 명시한다.
> 상위 문서: [07-Reference-Architecture](07-DTOS-Reference-Architecture.md), [11-Interface-Spec](11-DTOS-Interface-Specification-v1.0.md)

---

## 0. 운영 아키텍처 전체 뷰

```
┌─────────────────────────────────────────────────────────────────┐
│ Identity & Access        User · Role · Permission (RBAC 설계)    │
├─────────────────────────────────────────────────────────────────┤
│ Workspace                Project · Run History · Approval       │
├─────────────────────────────────────────────────────────────────┤
│ Governance               Audit Log · Prompt Version · Config    │
├─────────────────────────────────────────────────────────────────┤
│ Registries               Plugin · Template · Model · Artifact   │
├─────────────────────────────────────────────────────────────────┤
│ Observability            Monitoring · Logging · Alerting        │
└─────────────────────────────────────────────────────────────────┘
```

모든 운영 데이터의 물리 저장은 기존 원장(ledger) DB를 확장한다 — 별도 운영 DB를 만들지
않는다(단일 감사 소스, F8). MVP는 SQLite, Phase 전환 시 Postgres(스키마 동일).

---

## 1. User Management [MVP 구현: 최소]

| 항목 | 설계 | MVP 구현 |
|---|---|---|
| 계정 모델 | `users(username, pw_hash, role, status, created_at)` | ✅ 로컬 계정 테이블 |
| 기본 관리자 | 최초 기동 시 admin 시드(초기 비밀번호 변경 강제 정책) | ✅ 시드 + 경고 표시 |
| 프로필/조직 | 부서·직무 속성, 조직 트리 | 설계만 (조직관리는 §10 연기 목록) |
| 계정 수명주기 | 생성/비활성/삭제, 휴면 처리 | 설계만 |

## 2. Authentication [MVP 구현: 최소]

| 단계 | 방식 |
|---|---|
| **MVP** | 로컬 계정 + 비밀번호 해시(sha256+salt→운영 전 bcrypt) 로그인. UI 세션 기반 |
| Phase 1+ | 토큰 발급(서비스 간은 이미 Bearer — Spec §1.5) |
| Enterprise | **LDAP/AD 연동 → SSO(OIDC)** — 설계 원칙: 인증 제공자를 교체 가능한 어댑터로 두고, 내부는 항상 `username` 문자열만 신뢰 (연기: §10) |

## 3. Authorization (Role/Permission) [설계만]

RBAC 모델을 설계하되 **MVP는 단일 역할(모두 admin)로 동작**한다.

```
Role:   admin | engineer | reviewer | viewer
Permission (리소스×행위):
  project:{create,read,archive}   run:{create,read,cancel}
  approval:{decide}               plugin:{register,configure}
  template:{promote}              config:{write}   audit:{read}
역할-권한 기본 매핑:
  viewer   = *:read
  reviewer = viewer + approval:decide
  engineer = reviewer + run:create,cancel + template:promote(제안)
  admin    = 전부
```

- 승인 위임 단계화(09 문서 §4.1)와 연동: 게이트별 자동 통과 전환 권한은 admin 전용.
- 구현 시점: 사용자 2명 이상이 서로 다른 권한을 필요로 하는 첫 순간 (예: PoC 고객 계정).

## 4. Project Management [MVP 구현]

| 항목 | 설계 |
|---|---|
| 모델 | `projects(project_id, name, customer, domain, status, created_at)` — 자산 URN scope와 동일 키 |
| MVP | ✅ 프로젝트 생성/조회, run은 반드시 project에 귀속 |
| 이후 | 멤버 배정(RBAC), 고객 메타데이터, 프로젝트 아카이브 |

## 5. Run History [MVP 구현]

기존 원장 `runs/steps` 테이블이 그 자체로 Run History다. MVP에서 추가하는 것:

- ✅ 조회 UI: run 목록(프로젝트/상태/기간 필터), run 상세(step 트리, 승인 이력, 아티팩트 링크)
- 이후: 재실행(re-run with same inputs — lineage 기반), run 비교 뷰

## 6. Audit Trail [MVP 구현 — 이번 Sprint 필수]

모든 실행에 대해 **불변 감사 레코드**를 기록한다 (업무지시서 §11의 필드 전체):

```
audit_log(id, ts, user, project_id, run_id, plugin, plugin_version,
          workflow, workflow_version, prompt_version, model,
          status, verdict_summary, report_urn, artifacts_count, details_json)
```

규칙:
1. run 종료 시점(성공/실패/반려 모두)에 1행 기록 — 누락 불가(엔진이 finally로 보장)
2. UPDATE/DELETE 금지(append-only). 정정은 새 레코드 + 참조
3. `prompt_version`/`model`: LLM 미사용 run은 `"-"` — LLM Gateway 도입 시 자동 채움
4. 승인/반려는 `approvals`(decided_by 포함)와 조인해 완전한 감사 뷰 구성
5. 활용: 품질 KPI 집계(01 문서 §6), 보안 감사, 규제 대응(ASME V&V 40 traceability)

## 7. Security [설계만 + 기존 유지]

| 영역 | 상태 |
|---|---|
| 서비스 간 인증 | Bearer 토큰 (Spec §1.5) — 유지 |
| Runner 격리 | outbound-only, LLM 호출 금지 (F3) — 유지 |
| 민감정보 | 실서버/계정은 config.local.yaml(비추적), LLM 마스킹 게이트웨이(P1 후반) |
| 비밀 관리 | MVP: 환경변수 → 이후 Vault/KMS 검토 |
| 데이터 보호 | 아티팩트 불변 + 계보(F2), Private 저장소 접근 통제 |
| 연기 | 네트워크 존 분리, 암호화 at-rest, 침입 탐지 (§10) |

## 8. Plugin Management (Plugin Registry) [MVP 구현: 정적]

| 단계 | 내용 |
|---|---|
| **MVP** | ✅ 기동 시 `plugins/*/manifest.yaml` 스캔 → 검증 → 메모리 등록. **Core는 manifest와 4메서드 계약만 알고 내부 구현을 모른다** (업무지시서 §2·§7) |
| Phase 2 | manifest 스냅샷을 DB 저장(버전 이력), trust tier 게이트 |
| Phase 3 | 동적 설치/비활성, 회귀 스위트 연동 성공률(07 문서 §3) |

## 9. Template / Model Registry · Prompt Version · Configuration [설계만]

| Registry | 설계 요지 | 구현 시점 |
|---|---|---|
| Template Registry | 템플릿 버전·검증자·param_schema (01 문서 §5.1 `templates`) — 승격 절차는 09 문서 Loop B | P1 후반 |
| Model Registry | LLM/대리모델의 버전·평가 결과·적용 범위(valid_scope) | P2(LLM), H2(surrogate) |
| Prompt Version | 프롬프트 Git 관리 + `llm_calls.prompt_ref` — 회귀 없이 변경 금지(Loop C) | P2 |
| LLM Configuration | Gateway 라우팅(모델/온도/마스킹 사전) 중앙 설정 | P1 후반 (Intent 도입 시) |
| System Configuration | `config(key, value, updated_by, updated_at)` — 변경도 audit 대상 | P2 |

## 10. Monitoring & Logging [설계만 + 최소]

- **MVP**: 구조화 로그(stdout JSON), run 진행 이벤트 스트림(기존), 원장 기반 상태 조회
- P2: KPI 대시보드(원장 집계), Runner heartbeat 감시, 실패율 알림
- P3: OpenTelemetry 트레이스(LLM 호출·step 지연), Grafana

---

## 11. MVP 구현 범위 요약 (업무지시서 §9 대응)

| 기능 | 상태 | 구현 위치 |
|---|---|---|
| Login | ✅ 필수 | users 테이블 + 승인센터(UI) 로그인 게이트 |
| Project | ✅ 필수 | projects 테이블 + run 귀속 |
| Run History | ✅ 필수 | 원장 조회 UI (승인센터 내 탭) |
| Audit Log | ✅ 필수 | audit_log append-only, run 종료 시 자동 기록 |
| Artifact 저장 | ✅ 필수 | 기존 ArtifactStore(불변) + artifacts 원장 |
| User 관리·기본 관리자 | 선택 | admin 시드 + 사용자 추가(관리자만) |
| RBAC·LDAP·SSO·조직·비용·Marketplace·Multi-tenant·API GW 고도화·모델관리 UI | ❌ 연기 | 본 문서에 설계만 (§3·§7·§9) |

## 12. 데이터 모델 추가분 (원장 확장, additive)

```
users(username PK, pw_hash, role, status, created_at)
projects(project_id PK, name, customer, domain, status, created_at)
audit_log(id PK, ts, user, project_id, run_id, plugin, plugin_version,
          workflow, workflow_version, prompt_version, model,
          status, verdict_summary, report_urn, artifacts_count, details_json)
approvals + decided_by 컬럼 (승인자 기록)
```

기존 테이블(runs/steps/approvals/artifacts)은 변경 없음 — additive 확장은 유동 항목(10 문서 §2.2).
