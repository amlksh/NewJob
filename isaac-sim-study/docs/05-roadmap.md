# 05. 학습 로드맵 (4주 계획)

하루 1~2시간 기준의 입문 로드맵입니다. 속도는 자유롭게 조절하세요.

## 1주차 — 설치와 환경 적응
- [ ] RTX GPU / 드라이버 / Ubuntu 22.04 확인 ([01](01-installation.md))
- [ ] Isaac Sim Workstation 설치 및 첫 실행
- [ ] GUI 패널(Viewport, Stage, Property, Content) 익히기 ([02](02-tutorials.md))
- [ ] 큐브 떨어뜨리기 첫 씬 만들기
- [ ] 내장 Examples 3개 이상 실행해보기

**목표**: Isaac Sim을 켜고 씬을 직접 조작할 수 있다.

## 2주차 — USD 구조
- [ ] Stage / Prim / Property / Schema 개념 학습 ([03](03-usd-structure.md))
- [ ] 씬을 `.usda`로 저장해 텍스트 구조 읽어보기
- [ ] reference로 외부 에셋 가져오기
- [ ] Script Editor에서 `pxr`로 Stage 순회 / Prim 생성
- [ ] 물리 스키마(RigidBody, Collision) 직접 붙여보기

**목표**: "GUI 동작 = USD 변경"임을 체감하고, Python으로 씬을 만질 수 있다.

## 3주차 — 로봇과 ROS 2
- [ ] 내장 로봇(Carter/Franka) 불러오기
- [ ] URDF Importer로 URDF → USD 변환 ([04](04-ros2-structure.md))
- [ ] ROS 2 Humble 설치 및 Bridge 확장 활성화
- [ ] Action Graph로 `/cmd_vel` 구독 → 로봇 구동
- [ ] `ros2 topic` / RViz2로 데이터 확인

**목표**: 시뮬 로봇을 ROS 2 토픽으로 제어하고 센서를 받아볼 수 있다.

## 4주차 — 통합 미니 프로젝트
아래 중 하나를 골라 처음부터 끝까지:
- [ ] **A. 텔레옵 주행**: 차동 구동 로봇을 키보드로 주행 + LaserScan을 RViz2에 표시
- [ ] **B. 픽앤플레이스**: Franka 팔로 물체 집어 옮기기
- [ ] **C. 센서 파이프라인**: 카메라/LiDAR 데이터를 ROS 2로 발행해 외부 노드에서 처리

**목표**: 설치~USD~ROS2를 하나의 흐름으로 엮어 작은 결과물을 만든다.

## 다음 단계 (심화)
| 주제 | 설명 |
|------|------|
| **Isaac Lab** | 강화학습 프레임워크 (구 Orbit/Isaac Gym 후속) |
| **Synthetic Data (Replicator)** | 학습용 합성 데이터/라벨 자동 생성 |
| **Isaac ROS** | GPU 가속 ROS 2 인지 패키지 (Nav, Perception) |
| **Domain Randomization** | Sim-to-Real 갭 줄이기 |
| **OmniGraph 커스텀 노드** | 직접 노드를 만들어 파이프라인 확장 |

## 막힐 때
1. 공식 문서를 1순위로 (버전별 차이가 큼)
2. NVIDIA Developer Forums의 Isaac Sim 섹션
3. GitHub Issues: https://github.com/isaac-sim/IsaacSim/issues
4. 로그 확인: `~/.nvidia-omniverse/logs/`

---
**이전 ←** [04. ROS 2 구조](04-ros2-structure.md) | **처음 →** [README](../README.md)
