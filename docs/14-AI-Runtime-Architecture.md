# 14. AI Runtime Architecture (Sprint 1 수정 — AI Runtime First)

> 「수정 업무지시서: DTOS Sprint 1 (AI Runtime First)」 설계 문서.
> 목적: **Planner보다 AI Runtime을 먼저 구축**하고, 모든 AI Agent가 Runtime을 통해서만
> LLM을 호출하게 한다. 직접 LLM API 호출은 금지한다. Core·Plugin은 변경하지 않는다.

---

## 1. 위치 — Runtime은 모든 Agent 아래, Core 밖에 있다

```
┌────────────────────────────────────────────────────────────────────┐
│ AI Agents        Planner · Reviewer · (향후 Conversation 지능화 등)   │
│                  — Runtime API(complete_json)만 호출, SDK 직접 금지   │
├────────────────────────────  AI Runtime  ──────────────────────────┤
│  Runtime API   complete_json(agent, prompt, vars, schema, session)  │
│  ┌─────────────┬──────────────┬──────────────┬──────────────────┐  │
│  │ Provider    │ Prompt       │ Context      │ Tool Registry     │  │
│  │ Interface   │ Registry     │ Builder      │ (Workflow·Plugin· │  │
│  │ (Mock·      │ (버전 관리,   │ (Project·Run· │  Report·          │  │
│  │  Claude·    │  prompts/    │  Plugin·      │  Validation)      │  │
│  │  OpenAI·    │  파일 기반)   │  History)     │                   │  │
│  │  Gemini·    ├──────────────┼──────────────┼──────────────────┤  │
│  │  Local)     │ Model        │ Runtime      │ Audit             │  │
│  │             │ Registry     │ Memory       │ (Prompt·Token·    │  │
│  │             │ (모델·단가)   │ (Memory      │  Cost·Latency·    │  │
│  │             │              │  Manager 연계)│  Retry)           │  │
│  └─────────────┴──────────────┴──────────────┴──────────────────┘  │
│  Retry(지수 백오프) · Cost Tracking(ModelRegistry 단가) · Streaming*  │
├────────────────────────────────────────────────────────────────────┤
│ DTOS Core (불변)   PlatformEngine · Plugin Registry · Ledger/Audit  │
│ Plugins (불변)     prepare/run/validate/report                      │
└────────────────────────────────────────────────────────────────────┘
```
\* Streaming은 이번 Sprint 설계만(인터페이스 예약) — 구현 제외 목록과 동일하게 후속.

**흐름(수정 지시서):** AI Runtime → Planner → Conversation → Workflow → Plugin → Reviewer → Memory

## 2. 컴포넌트 설계 (지시서 10항목)

| # | 컴포넌트 | 이번 Sprint | 설계 |
|---|---|---|---|
| 1 | Provider Interface | ✅ 구현 | `Provider` 프로토콜: `complete(system, user) -> ProviderResponse(text, tokens)`. 어댑터: **Mock**(CI/테스트), Anthropic(Claude), OpenAI, Gemini, Local(OpenAI 호환 endpoint). 교체 = 주입 교체 |
| 2 | Prompt Engine | ✅ Prompt Registry | `prompts/<name>/<version>.md` 파일 기반. `===USER===` 구분자로 system/user 분리, `{변수}` 렌더링. 최신/고정 버전 조회, 버전 목록 |
| 3 | Context Builder | ✅ 구현 | Project·Run History·Plugin(manifest nl)·Memory 요약을 프롬프트 변수로 조립. Agent가 아니라 Runtime이 조립 책임 |
| 4 | Tool Registry | ✅ 구현 | 플랫폼 능력 카탈로그: plugin manifest에서 workflow 도구 자동 등록(+report/validation은 파이프라인 단계로 명시). Planner의 계획 재료 |
| 5 | Model Registry | ✅ 구현 | 모델 메타(provider, 단가 $/MTok in/out). Cost Tracking의 단가 원천. 신규 모델 = 레코드 추가 |
| 6 | Runtime Memory | ✅ 연계 | Memory Manager(13 문서 §2.3)를 Context Builder가 소비 — 중복 구현하지 않음 |
| 7 | Audit | ✅ 구현 | `ai_call_log` 테이블(append-only): ts·session·agent·provider·model·prompt name/version·input/output tokens·cost_usd·latency_ms·attempts·status·error. **모든 호출 기록(실패 포함)** |
| 8 | Retry | ✅ 구현 | Runtime API 내 지수 백오프 재시도(기본 2회). 시도 횟수는 Audit에 기록 |
| 9 | Streaming | 설계만 | Provider 프로토콜에 후속 `stream()` 예약. 대화형 UI 도입 시 구현 |
| 10 | Cost Tracking | ✅ 구현 | 호출별 cost = tokens × ModelRegistry 단가 → Audit 저장, 세션/기간 합산 조회 |

## 3. Runtime API — 모든 신규 Agent가 재사용하는 단일 진입점

```python
runtime = make_runtime(provider=make_provider("anthropic"), ...)   # 조립은 앱 진입점에서 1회

result = runtime.complete_json(
    agent="planner",                      # Audit 주체
    prompt="planner.task-plan",           # Prompt Registry 이름(@버전 고정 가능)
    variables={"request": text, ...},     # 템플릿 변수(Context Builder 산출 포함)
    schema=TASK_PLAN_SCHEMA,              # 응답 JSON 안내/검증
    session_id=session_id)
result.data        # 파싱된 JSON (dict)
result.model / result.provider / result.cost_usd / result.latency_ms / result.attempts
```

- **금지 규칙(정적 검사로 강제)**: `apps/ai`의 Agent 코드는 `anthropic`/`openai`/`google` SDK를
  import할 수 없다. SDK import는 `libs/ai/runtime/providers.py` 한 곳뿐이다.
- provider가 없으면(`TWINOS_LLM_PROVIDER` 미설정) `runtime.has_llm == False` — Agent는
  결정적 폴백 경로(키워드·정규식, 13 문서 §2.1)로 동작한다. CI는 이 경로 + MockProvider
  경로 둘 다 검증한다.

## 4. Planner Runtime 연동 (지시서: Runtime을 사용하는 첫 Agent)

```
Planner.plan(text)
  ├─ runtime.has_llm?
  │    ├─ 예: runtime.complete_json("planner", "planner.task-plan",
  │    │      variables=ContextBuilder(카탈로그=ToolRegistry, 기억=Memory), schema=task-plan)
  │    │      → 계약 검증 → TaskPlan   (실패 시 폴백으로 흡수, 사유는 reason에 기록)
  │    └─ 아니오: 결정적 폴백(키워드 매칭 + 단위 정규식 — 전부 manifest nl 선언 기반)
  └─ 두 경로 모두 contracts/ai-planner/v1/task-plan 계약을 출력 → Reasoning Trace 기록
```

Reviewer의 LLM 서술 보강도 동일하게 `runtime.complete_json("reviewer", "reviewer.narrative", ...)`.

## 5. Definition of Done 매핑

| DoD | 검증 방법 (CI) |
|---|---|
| Runtime을 통해 Planner가 요청 처리 | E2E: MockProvider 주입 → Planner가 Runtime 경유로 Task Plan 산출 |
| Provider 교체 가능 | 동일 테스트를 서로 다른 provider(name)로 실행, Audit에 provider 기록 확인 |
| 모든 AI 호출이 Audit에 기록 | 호출 수 == ai_call_log 행 수 (실패 호출 포함, attempts 기록) |
| Prompt Version 관리 | prompts/에 2개 버전 두고 최신/고정 조회 테스트 |
| Runtime API를 모든 신규 Agent가 재사용 | Planner·Reviewer가 같은 `complete_json` 사용 + SDK 직접 import 금지 정적 검사 |

## 6. 제외 (지시서)

RAG · Vector DB · Fine-tuning · Autonomous Agent · Multi-Agent Collaboration.
(13 문서의 제외 목록과 합집합으로 유지)
