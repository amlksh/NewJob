# Physical AI 확장 설계 (Isaac Sim / Omniverse / ROS2)

> Phase 4(M12+) 대상. 핵심 주장: **지금 아키텍처 결정 몇 가지만 지키면, Physical AI 확장은 "새 Agent + 새 Runner 추가"로 끝난다.**

---

## 1. 확장을 보장하는 현재(MVP) 설계 결정

| 설계 결정 (이미 01~03 문서에 반영) | Physical AI에서 의미 |
|---|---|
| 표준 Agent Task API (03 문서 §1) | Sim Agent가 같은 계약 구현 → Orchestrator/UI/원장 무변경 |
| Runner pull 모델 (큐 폴링, outbound only) | GPU 워크스테이션의 Isaac Sim Runner를 같은 방식으로 연결 |
| 아티팩트 참조 전달 + kind 메타데이터 | USD 씬, rosbag, 센서 로그도 아티팩트 kind 추가로 수용 |
| 워크플로우 카탈로그 (YAML) | `robot_sim_validation` 워크플로우를 카탈로그에 추가만 하면 됨 |
| Quality Gate 선언형 룰 | 물리 시뮬레이션용 게이트(관절 한계 초과, 충돌 등) 추가 가능 |

**추가로 MVP 단계에서 지켜야 할 것 2가지:**

1. `artifacts.kind`를 열거형 고정이 아닌 **네임스페이스 문자열**(`cae.odb`, `sim.usd`, `ros.bag`)로 설계
2. 진행 이벤트 스키마에 **시계열 스트림 채널**(현재는 .sta 진행률)을 범용화 — 나중에 시뮬레이션 텔레메트리 재사용

---

## 2. Phase 4 추가 컴포넌트

```
┌────────────┐   표준 Task API   ┌──────────────────┐
│ Orchestr.  │ ───────────────▶ │ Sim Agent         │
└────────────┘                  │ · load_scene      │
                                │ · run_episode     │
                                │ · collect_sensors │
                                └───────┬───────────┘
                                        │ ToolJob (큐)
                     ┌──────────────────▼──────────────────┐
                     │ Isaac Sim Runner (GPU 워크스테이션)     │
                     │ · Isaac Sim headless (Python API)     │
                     │ · USD 씬 로드(Nucleus/MinIO)           │
                     │ · ROS2 bridge (센서/제어 토픽)          │
                     │ · rosbag/센서로그 → MinIO 업로드         │
                     └───────────────────────────────────────┘
```

| 컴포넌트 | 내용 |
|---|---|
| Sim Agent | 시나리오(씬, 로봇, 태스크, 에피소드 수) → 실행 계획, 결과 지표화. 03 문서 §1 계약 구현 |
| Isaac Sim Runner | headless Isaac Sim 구동, USD 씬 로드, 에피소드 실행, 센서 데이터 수집 |
| Omniverse Nucleus (선택) | USD 자산 협업 저장소. 미도입 시 MinIO에 USD 직접 저장으로 시작 |
| ROS2 Bridge | 실기-시뮬레이션 동일 토픽 인터페이스. sim-to-real 검증의 기준면 |
| Asset Pipeline | CAD→USD 변환 (CAE 모델 자산 재활용 경로) |

## 3. CAE ↔ Physical AI 시너지 시나리오 (V-DTOS 차별화 포인트)

1. **모델 일관성**: 동일 제품의 CAE 모델(변형/강도)과 Isaac Sim 모델(동역학/센서)을 같은 프로젝트 아티팩트 계보로 관리 → Traceability Matrix가 "요구사항 → CAE 검증 + Sim 검증"을 한 표에서 추적
2. **FMU 연계**: FMU Agent의 플랜트 모델을 Isaac Sim에 co-simulation으로 연결 (FMI↔ROS2 브리지)
3. **V&V 재사용**: ASME V&V 40 스타일 신뢰성 평가 프레임을 로봇 시뮬레이션 검증(sim-to-real gap 평가)에 확장

## 4. 단계적 도입 계획

| 단계 | 내용 | 판단 기준 |
|---|---|---|
| P4-0 (M12) | GPU 1대 + Isaac Sim headless 기술 검증(스파이크 2주) | 라이선스/성능 확인 |
| P4-1 (M13) | Sim Agent + Runner 계약 구현, 단순 씬 자동 실행 | 표준 계약 무수정 통과 |
| P4-2 (M14~15) | 로봇 pick-and-place 또는 제조셀 PoC, 보고서 자동화 연결 | 고객 데모 가능 수준 |
| P4-3 (M16+) | ROS2 실기 연동, sim-to-real 검증 워크플로우 | 사업화 판단 |

## 5. 유의사항

- Isaac Sim은 GPU(RTX급)·드라이버·버전 의존성이 강하다. Runner를 컨테이너화(NVIDIA Container Toolkit)해 버전을 고정할 것.
- Omniverse Nucleus는 운영 부담이 있으므로 PoC까지는 MinIO 직저장으로 충분하다.
- Physical AI 인력(로봇/ROS2 경험)은 P4-0 스파이크 결과를 보고 채용/외주를 결정한다 — 계획서 13장 "과도한 범위" 리스크의 방어선.
