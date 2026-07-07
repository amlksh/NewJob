# 15. Solver Adapter Family (실 Solver 자산 연결 일반화)

> 지시: "실 Solver는 .exe 형태가 아니므로 exe 방식만 고집하지 말 것 — Adapter를 일반화.
> index.html(당뇨 Solver 자산) 분석 후 HtmlSolverAdapter 우선 검토, FMU는 구조만 준비.
> **DTOS Core는 절대 HTML 내부 로직에 종속되면 안 된다.**"

---

## 1. 원칙 — Core 독립은 계층으로 보장한다

```
Core(PlatformEngine) ── plugin 이름만 앎 ──▶ Plugin(diabetes_twin)
                                              │ ToolJob(계약: tooljob/v1)
                                              ▼
Runner(disease_solver_runner) ── DiseaseSolverTool(수명주기 구동기)
                                              │ Adapter 4메서드 (Spec §14 동결)
        ┌──────────┬──────────┬───────────┬───┴──────┬──────────┐
        ▼          ▼          ▼           ▼          ▼          ▼
      Mock       Exe(Cli)   Python      Html       Fmu*      Rest*
   (test double) (실행파일)  (스크립트)  (JS 커널)   (예약)     (예약)
```

- Core·Plugin·계약(glucose.csv `patient_id,t_min,glucose_mgdl`)은 **무변경**.
- HTML 함수명·단위(mmol/L)·시간축 등 자산 내부 지식은 **HtmlSolverAdapter 안에만** 존재.
  Core가 아는 것은 여전히 "plugin 이름"뿐 — E2E 테스트가 도구 주입 한 줄만 바꿔 완주함을 검증.
- \* FmuSolverAdapter·RestSolverAdapter는 수명주기 표면만 확정(구조 예약, §5).

## 2. 어댑터 매트릭스

| 이름 | 자산 형태 | 지정(환경변수) | 상태 |
|---|---|---|---|
| mock | CI/개발 test double | - | 운영 중 |
| exe (=solver) | 실행 파일·임의 커맨드 | `TWINOS_DISEASE_SOLVER_CMD` | 운영 중 |
| python | Python 스크립트 | `TWINOS_DISEASE_SOLVER_PY` | 운영 중 |
| **html** | HTML 단일 페이지 앱(JS 커널) | `TWINOS_DISEASE_SOLVER_HTML` (기본: 동봉 자산) | **이번 단계 구현** |
| fmu | FMU (Functional Mock-up Unit) | `TWINOS_DISEASE_SOLVER_FMU` | 다음 단계 (표면 예약) |
| rest | 원격 HTTP Solver API | `TWINOS_DISEASE_SOLVER_URL` | 예약 |

선택: `--tool <이름>` (skeleton/AI 콘솔 공통). 전부 동일 수명주기
`initialize → execute → collect → shutdown` (Spec §14 — 동결)과 동일 출력 계약.

## 3. index.html 자산 분석 결과 (HtmlSolverAdapter 타당성 — 채택)

대상: `DiabetesSystem | 디지털 트윈 임상 플랫폼` (단일 HTML, ~260KB, Chart.js CDN)

| 분석 항목 | 결과 |
|---|---|
| 시뮬레이션 커널 | `runSim_compute(cfg)` — **DOM 비종속 순수 JS 함수** (RK4, 미니멀 모델 5-상태) |
| 커널 의존성 | 상수 `const P={...}` + 보조 `function cv(G)` 뿐 — UI 코드와 완전 분리 가능 |
| 입력 cfg | beta(β세포능), IR(인슐린 저항성), G_b/I_b(기저), meal_g/ms/md(식사), met/pump/ex(중재) |
| 출력 | t[분 0~300, 1분 간격], G[**mmol/L**], I, Ra, U + KPI(pk·tir·auc·g2h) |
| 결정성 | 난수 없음(RK4 고정 스텝) → Runner 원칙(F3) 충족, 동일 입력=동일 출력 테스트로 검증 |
| 실행 방식 | **브라우저 불필요** — 커널 선언부만 추출(중괄호 매칭, 자산 무수정)해 quickjs로 실행 |

어댑터가 흡수하는 변환(자산 내부 지식의 전부 — Core 비노출):
- 단위: mmol/L × 18.0182 → mg/dL
- cohort 프로필 매핑: `baseline_mgdl`→G_b(/18.0182), `insulin_sensitivity`→IR(역수),
  `meal_response`→meal_g(기준 55 대비 75g 정규화)
- 시간축: 커널 고정 300분(식후 창) — 식후 혈당 평가 목적과 일치

검토한 대안과 기각 사유:
- Headless 브라우저(Playwright): 자산 전체 로딩으로 충실도는 높으나 배포 의존성
  (~150MB 브라우저)·오프라인 CDN 이슈 → 커널이 순수 JS로 확인되어 불필요.
- JS 커널을 Python으로 포팅: "기존 Solver 무수정" 원칙 위반(수치 검증 부담) → 기각.

## 4. HtmlSolverAdapter 동작

```
initialize: TWINOS_DISEASE_SOLVER_HTML 로드(기본: 동봉 자산) → 커널 추출(P·cv·entry)
            → quickjs Context 생성  (quickjs 미설치 시 명확한 안내 오류)
execute   : 환자별 cfg 매핑 → runSim_compute 호출 → 시계열 수집
collect   : glucose.csv(mg/dL 변환) + solver.log(커널 KPI) → ToolResult
shutdown  : JS 컨텍스트 해제
```

의존성: `pip install -e ".[html]"` (quickjs — 경량, 브라우저·네트워크 불필요).
다른 HTML 자산 연결 시: 엔트리 함수명이 다르면 `HtmlSolverAdapter(entry=...)` 지정.

## 5. FMU 준비 구조 (다음 단계)

- `FmuSolverAdapter` 표면 확정: 동일 4메서드 + `TWINOS_DISEASE_SOLVER_FMU`.
  다음 단계 구현 내용: fmpy 기반 `simulate_fmu` + scenario→FMU 변수 매핑 + 동일 출력 계약.
- `RestSolverAdapter` 동일 원리로 예약 (`TWINOS_DISEASE_SOLVER_URL`).
- 두 어댑터 모두 현재는 명확한 안내 메시지로 실패한다(테스트로 고정) — 표면 변경 없이
  내부만 채우면 되므로 Plugin·Core·데모 스크립트는 그대로다.

## 6. 검증 (CI)

- 커널 추출·순수성(`document.` 비포함)·quickjs 실행 가능
- 단위 변환(초기값≈baseline_mgdl)·결정성(동일 입력=동일 출력)
- Core 무변경 E2E: 도구 주입만 `html`로 바꿔 계획→실행→판정→보고서→Audit 완주
- FMU 표면 예약 동작
