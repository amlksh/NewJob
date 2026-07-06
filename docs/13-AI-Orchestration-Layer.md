# 13. AI Orchestration Layer (Sprint 1)

> 「업무지시서: Sprint 1 – AI Orchestration Layer 구축」 설계 문서.
> 목적: DTOS를 Workflow Engine에서 **AI가 계획(Planning)·실행(Execution)·검토(Review)·
> 기록(Memory)하는 AI Operating System**으로 발전 — 단, Core·Plugin은 변경하지 않는다.

---

## 1. Architecture Diagram — AI Layer는 Core와 사용자 사이에 위치한다

```
┌──────────────────────────────────────────────────────────────────┐
│ User (자연어 요청)                                                 │
└───────────────┬──────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────  AI Layer  ─────────────────────┐
│  Conversation ──▶ Planner Agent ──▶ (Workflow/Plugin 선택,        │
│   (질문/답변)        │                Task Plan, 질문 생성)          │
│                     │ 참조                                        │
│        Memory ◀─────┼──────▶ Knowledge Registry                   │
│     (플랫폼 기억)     │        (Workflow·Template·Rule·Prompt·      │
│                     │         Plugin Metadata·Reference)          │
│                     ▼                                             │
│              Reasoning Trace (판단 근거 저장 → Audit 연결)           │
│                     │                        ▲                    │
│                     │                 Reviewer Agent              │
│                     │            (결과 검토 — 수정 금지, 제안만)      │
└─────────────────────┼────────────────────────┼────────────────────┘
                      ▼                        │
┌──────────────────────────────────────────────┴────────────────────┐
│ DTOS Core (불변)  PlatformEngine · Plugin Registry · Ledger/Audit  │
├───────────────────────────────────────────────────────────────────┤
│ Plugins (불변)    diabetes_twin · fmh_twin · …                     │
│                   prepare() / run() / validate() / report()       │
└───────────────────────────────────────────────────────────────────┘
```

**아키텍처 원칙(업무지시서 §11) 보장 방식:**

| 원칙 | 보장 메커니즘 |
|---|---|
| Core는 AI를 모른다 | AI Layer가 Core의 공개 API(`engine.execute`)만 호출. Core 코드는 무변경 — CI의 import 정적 검사 유지 |
| Plugin은 AI를 모른다 | Plugin 코드·4메서드 인터페이스 무변경. Plugin은 **manifest의 `nl` 메타데이터**(설명·키워드·필수 파라미터 질문)만 선언 |
| AI는 도메인 지식을 갖지 않는다 | Planner/Reviewer의 판단 재료는 전부 **plugin manifest·계약 산출물(판정표·numbers_manifest)** — 의료/CAE 로직은 AI Layer 코드에 등장하지 않는다 |
| LLM 비종속 (CTO §14.1~2) | **모든 LLM 호출은 AI Runtime(14 문서) 경유** — Provider Interface(Mock·Claude·OpenAI·Gemini·Local) + **provider 없음(결정적 휴리스틱) 폴백**. 모델 교체는 provider 주입 교체로 끝남. Agent의 SDK 직접 호출 금지 |

## 2. 컴포넌트 설계

### 2.1 Planner Agent
- 입력: 사용자 자연어 + Plugin Catalog(manifest nl 메타데이터) + Memory 요약
- 출력: **Task Plan** (`contracts/ai-planner/v1/task-plan.schema.json`으로 CI 검증)
  `{plugin, workflow, params, open_questions[], reason}`
- 정보 부족 시 `open_questions` 생성 — 질문 문구도 plugin이 선언(도메인 문구를 AI가 만들지 않음)
- LLM 경로: 카탈로그를 프롬프트에 주입, JSON 스키마 강제 / 폴백 경로: 키워드 매칭 + 단위 정규식 추출(전부 manifest 선언 기반)

### 2.2 Conversation Layer
- Planner의 open_questions → 사용자 응답 → 파라미터 병합 → 재계획 루프
- **모든 질문·답변은 conversation_log(append-only)에 저장되고 Audit Log와 세션으로 연결**

### 2.3 Memory Manager (Platform Memory — LLM Memory 아님)
- 저장: 실행 결과·실패 원인·Validation 결과·Prompt Version·사용자 피드백·Report 수정 이력
- `memory_records(project_id, plugin, run_id, kind, content_json)` — 원장 DB 확장(additive)
- 조회: `recall(project_id, plugin)` → Planner 프롬프트의 컨텍스트로 주입 (동일 프로젝트 재수행 시 참조)

### 2.4 Knowledge Registry (RAG는 다음 Sprint)
- 관리 대상: Workflow·Template·Material·Validation Rule·Prompt·Plugin Metadata·Reference Document
- MVP: 파일시스템 스캔(plugins/*/workflows·templates·gates·kpi, prompts/) → `knowledge_items` 테이블 등록 + 조회 API. 임베딩/검색 없음

### 2.5 Reviewer Agent
- 입력: validate 출력(판정표)·report 출력·numbers_manifest·아티팩트 목록 — **계약 산출물만**
- 출력: findings `{severity, code, message, suggestion}` (`contracts/ai-reviewer/v1` 검증)
- **결과를 수정하지 않는다** — 문제 발견·제안만. 결정적 검사(수치 출처 누락, fail 존재, 기준 근접 마진)는 항상 수행, LLM은 서술 보강만(선택)

### 2.6 Reasoning Trace
- `reasoning_trace(run_id/session, agent, decision, reason, prompt_version, model, ts)`
- Planner(Workflow/Plugin 선택 이유)·Reviewer(판정 지적 이유) 기록 → Audit과 연결 → Explainable AI 기반

## 3. Sequence Diagram (DoD 시나리오)

```
User          Conversation   Planner      Knowledge/Memory   Core(Engine)   Plugin      Reviewer    Ledger
 │ "혈당 시뮬레이션 실행"                                                                             │
 ├────────────▶│ 기록(user)                                                                        ├ conv_log
 │             ├─ plan ─────▶│─ catalog/recall ─▶│                                                 │
 │             │◀ questions ─┤ "환자 수를 입력해주세요"          (trace: plugin 선택 이유)              ├ trace
 │◀─ 질문 ─────┤ 기록(assistant)                                                                    ├ conv_log
 │ "20명"      │ 기록(user)                                                                         ├ conv_log
 ├────────────▶│─ plan ─────▶│ → TaskPlan{diabetes_twin, n_patients:20}                            ├ trace
 │             │────────── execute(plugin, params) ──────────▶│─ prepare/run/validate/report ─▶│   ├ steps/audit
 │             │                                              │◀ outcome(판정·보고서) ──────────┤   │
 │             │──────────────────── review(계약 산출물) ────────────────────────────▶│             │
 │             │◀ findings(제안) ──────────────────────────────────────────────────── ┤            ├ trace
 │             │─ memory.record(결과·검토) ─▶│                                                      ├ memory
 │◀─ 보고서 경로 + 검토 의견 ─┤                                                                       │
```

## 4. 구현 범위 (업무지시서 §10 준수)

구현: **AI Runtime(14 문서 — Runtime First)** · Planner · Conversation · Memory · Reviewer · Reasoning Trace · Knowledge Registry
미구현(다음 Sprint 이후): RAG · Vector DB · Long-term Memory · Auto Learning · Fine Tuning · Autonomous/Self-Improving Agent · Multi-Agent Collaboration

> 수정 지시서(AI Runtime First) 반영: 실행 흐름은 **AI Runtime → Planner → Conversation →
> Workflow → Plugin → Reviewer → Memory**이며, Runtime 상세 설계는 14 문서를 따른다.

## 5. Demo Scenario (완료 기준 §13)

```
$ python -m apps.ai.console "20명의 가상환자에 대해 식후 혈당을 평가하고 보고서를 생성해줘" --auto-approve
→ Planner: diabetes_twin / diabetes_cohort 선택 (이유 trace 기록)
→ 실행: 20명 cohort 확장 → mock solver → TIR 판정 20건 → 보고서 docx
→ Reviewer: findings 출력 (예: 기준 근접 케이스 경고)
→ Memory·Audit·Trace 기록 확인

$ python -m apps.ai.console "혈당 시뮬레이션 실행" --auto-approve
→ Planner 질문: "환자 수를 입력해주세요." → 입력 "20명" → 이후 동일
```

두 시나리오 모두 **CI의 E2E 테스트로 매 커밋 재검증**된다 (LLM 키 불필요 — 폴백 경로).
LLM 사용 시: `TWINOS_LLM_PROVIDER=anthropic TWINOS_LLM_API_KEY=...` (provider 주입만 변경).
