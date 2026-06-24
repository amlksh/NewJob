# 04. ROS 2 구조 이해

Isaac Sim을 ROS 2와 연결하면, 시뮬레이션 속 로봇을 실제 ROS 2 노드처럼 제어하고
센서 데이터를 토픽으로 받을 수 있습니다. (Sim-to-Real, 강화학습 데이터 수집 등에 핵심)

## 1. 전체 그림

```
  ┌─────────────────────┐         ROS 2 토픽/서비스          ┌──────────────────────┐
  │     Isaac Sim       │  /cmd_vel, /scan, /tf, /joint... │   당신의 ROS 2 노드   │
  │  (ROS 2 Bridge 확장)│ <───────────────────────────────> │  (rclpy / rclcpp)     │
  │   OmniGraph 노드들  │            DDS (Humble)           │  RViz2, Nav2, MoveIt  │
  └─────────────────────┘                                   └──────────────────────┘
```

- **ROS 2 Bridge**는 Isaac Sim의 **확장(extension)**입니다.
- 내부적으로 **OmniGraph 노드**로 동작합니다 (= 비주얼 노드 그래프로 데이터 흐름을 구성).
- 통신은 표준 **DDS**를 사용하므로, 외부의 일반 ROS 2 노드와 그대로 통신됩니다.

## 2. 사전 준비

1. **ROS 2 Humble** 설치 (권장 배포판) — Ubuntu 22.04
   ```bash
   source /opt/ros/humble/setup.bash
   echo $ROS_DISTRO        # humble 확인
   ```
2. (권장) DDS 구현 통일 — 환경변수로 명시:
   ```bash
   export ROS_DOMAIN_ID=0
   # Isaac Sim 문서에서 권장하는 RMW(fastdds/cyclonedds) 설정을 맞춰주세요
   ```
3. Isaac Sim에서 **ROS 2 Bridge 확장 활성화**:
   - `Window > Extensions` → "ROS2 Bridge" 검색 → **Enable**
   - 자주 쓰면 "Autoload" 체크

> ⚠️ 버전마다 활성화/설정 방식이 바뀝니다. 시작 전 반드시
> [ROS 설치 문서](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_ros.html)를 먼저 읽으세요.

## 3. OmniGraph / Action Graph — 연결의 핵심

ROS 2 연동은 코드보다 **그래프**로 먼저 배우는 것이 직관적입니다.

- **OmniGraph**: Isaac Sim의 비주얼 데이터플로우 시스템 (노드 연결 = 기능 조합).
- **Action Graph**: 매 프레임 실행되는 그래프. ROS 2 입출력은 여기에 노드로 추가.

자주 쓰는 ROS 2 OmniGraph 노드:
| 노드 | 역할 |
|------|------|
| `On Playback Tick` | 매 시뮬 프레임마다 그래프 실행 트리거 |
| `ROS2 Context` | DDS 도메인 등 ROS 2 컨텍스트 |
| `ROS2 Publish Clock` | `/clock` 발행 (시뮬 시간 동기화, 매우 중요) |
| `ROS2 Subscribe Twist` | `/cmd_vel` 구독 → 로봇 구동 |
| `ROS2 Publish Joint State` | 관절 상태 발행 |
| `Articulation Controller` | 받은 명령을 로봇 관절에 적용 |
| `ROS2 Publish LaserScan / Camera` | 센서 데이터 발행 |
| `ROS2 Publish Transform Tree` | `/tf` 발행 |

흐름 예 (차동 구동 로봇):
```
On Playback Tick ─► ROS2 Subscribe Twist (/cmd_vel) ─► Differential Controller ─► Articulation Controller
                └─► ROS2 Publish Clock (/clock)
                └─► ROS2 Publish Transform Tree (/tf)
```

## 4. 첫 연동 실습 (개념 순서)

1. 로봇 USD 불러오기 (예: Carter, Franka 등 내장 에셋)
   - URDF가 있다면 **URDF Importer 확장**으로 USD 변환 후 사용
     (Isaac Sim은 USD가 더 안정적으로 동작)
2. Action Graph 생성 → 위 노드들 연결
3. Isaac Sim **Play(▶)** 실행
4. 외부 터미널에서 토픽 확인:
   ```bash
   source /opt/ros/humble/setup.bash
   ros2 topic list                 # /cmd_vel, /clock, /tf 등이 보여야 함
   ros2 topic echo /clock
   ros2 run teleop_twist_keyboard teleop_twist_keyboard   # 키보드로 /cmd_vel 발행
   ```
5. RViz2로 센서/TF 시각화:
   ```bash
   rviz2
   ```

## 5. Python(rclpy) + Standalone Bridge

GUI 그래프 대신 코드로도 가능합니다 (Standalone 워크플로우):
```python
# Isaac Sim standalone 스크립트 내부 (./python.sh 로 실행)
from isaacsim import SimulationApp
sim = SimulationApp({"headless": False})

import rclpy
from rclpy.node import Node
# ... ROS 2 Bridge 확장 활성화 후 rclpy 노드와 시뮬 루프를 함께 구동
```
- 핵심은 **시뮬레이션 시간(`/clock`)과 ROS 2 노드의 시간 동기화**입니다.
  외부 노드에서 `use_sim_time:=true`를 설정하세요.

## 6. 자주 겪는 문제

| 증상 | 해결 |
|------|------|
| `ros2 topic list`에 아무것도 안 뜸 | Bridge 확장 비활성 / `source setup.bash` 누락 / `ROS_DOMAIN_ID` 불일치 |
| 토픽은 보이는데 데이터 없음 | Play(▶) 안 누름, 또는 그래프에 `On Playback Tick` 미연결 |
| 시간이 안 맞음(TF 경고) | `/clock` 미발행 또는 외부 노드 `use_sim_time` 미설정 |
| RMW 충돌 | Isaac Sim과 외부 노드의 DDS(RMW) 구현 불일치 |

## 7. 학습 체크포인트
- [ ] ROS 2 Bridge가 OmniGraph 노드로 동작함을 이해했다
- [ ] Action Graph로 `/cmd_vel` 구독 → 로봇 구동을 만들어봤다
- [ ] `/clock` 동기화의 중요성을 안다
- [ ] 외부 터미널에서 `ros2 topic`으로 데이터를 확인해봤다
- [ ] RViz2로 센서/TF를 시각화해봤다

---
**이전 ←** [03. USD 구조](03-usd-structure.md) | **다음 →** [05. 학습 로드맵](05-roadmap.md)

## 참고 링크
- [ROS / ROS 2 설치](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_ros.html)
- [ROS 2 튜토리얼](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/ros2_landing_page.html)
- [ROS 2 Reference Architecture](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/ros2_reference_architecture.html)
- [Isaac ROS (가속 패키지)](https://nvidia-isaac-ros.github.io/)
