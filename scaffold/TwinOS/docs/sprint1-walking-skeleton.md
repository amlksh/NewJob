# Sprint 1 — Walking Skeleton (2주)

## 목표 (유일한 목표)

기능 확장이 아니라, 아래 End-to-End 흐름이 **한 번이라도 실제로 동작**하는 것:

```
Task 생성 → Orchestrator → FMH Plugin → Runner → Abaqus 실행
        → ODB 결과 추출 → HIC 계산 → 1페이지 Report → Human Approval
```

Demo 가능한 End-to-End 동작이 모든 개별 컴포넌트의 완성도보다 우선한다.

## 허용되는 단순화 (명시적)

| 구간 | Sprint 1 허용 | 금지 (여기서만은 실물) |
|---|---|---|
| Task 생성 | REST 수동 호출(curl/스크립트), LLM Intent 없음 | — |
| Orchestrator | 워크플로우 1개 하드로딩, foreach 없이 케이스 1건 | 원장 기록은 생략 불가 |
| FMH Plugin | 템플릿 1개, 파라미터 하드코딩 | TwinAgent 4메서드 경유는 생략 불가 |
| Runner | 재시도/heartbeat 최소 | **Abaqus 실제 실행** (목업 금지) |
| 결과 추출 | 가속도 곡선 1개 추출 | **실제 ODB에서 추출** |
| HIC | libs/cae_toolkit.hic 사용 | 판정 로직 하드코딩 금지 |
| Report | 1페이지 docx, 양식 미적용 | 수치는 validate 출력만 사용 |
| Approval | Streamlit 승인/반려 버튼 + 사유 코드 | 사유 코드 생략 금지 (09 문서) |

## Definition of Done

1. 초소형 FMH 케이스 1건이 위 흐름을 무인으로 통과하고, 승인 후 docx가 MinIO에 존재한다.
2. 전 단계가 ledger(steps)에 기록되어 있다.
3. 모든 구간 간 메시지가 contracts/ 스키마로 검증된다 (CI green).
4. 팀원 누구나 `make up` + README 절차로 로컬 재현 가능하다.

## 스켈레톤 이후 (Sprint 2+)

타겟 그리드 전개(케이스 매트릭스), foreach 병렬, HITL checkpoint 재개, HIC 판정
일치율 검증(WBS 2.5), FMVSS 보고서 양식 — docs/design/05 WBS 참조.
