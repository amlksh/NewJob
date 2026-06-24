# 02. 튜토리얼 시작하기

설치가 끝났다면 GUI에 익숙해지는 것이 첫 단계입니다.

## 1. UI 한눈에 보기

| 영역 | 역할 |
|------|------|
| **Viewport** | 3D 씬을 보고 카메라를 움직이는 메인 화면 |
| **Stage** (우상단) | 씬의 모든 객체(Prim)를 트리로 보여줌 → USD 구조의 핵심 |
| **Property** (우하단) | 선택한 Prim의 속성(위치, 물리, 머티리얼 등) 편집 |
| **Content** (하단) | 에셋(USD, 텍스처 등) 파일 브라우저 |
| **Toolbar** (좌측) | 이동/회전/스케일, Play(시뮬레이션 재생) 버튼 |
| **Console / Script Editor** | 로그 확인 및 Python 직접 실행 |

뷰포트 조작 (마우스):
- **Alt + 좌클릭 드래그**: 회전(궤도)
- **Alt + 우클릭 / 휠**: 줌
- **마우스 휠 클릭 드래그**: 이동(팬)
- **F**: 선택한 객체에 카메라 포커스

## 2. 첫 씬 만들기 (5분)

1. `Create > Physics > Ground Plane` — 바닥 추가
2. `Create > Shape > Cube` — 큐브 추가, 위로 살짝 올림
3. 큐브 선택 → `Add > Physics > Rigid Body` (질량/충돌 부여)
4. 좌측 툴바의 **Play(▶)** 클릭 → 큐브가 중력으로 떨어지면 성공
5. **Stop(■)** 으로 초기 상태 복귀

> 핵심 감각: GUI에서 한 모든 행동이 결국 **USD Stage에 Prim을 추가/수정**하는 것입니다 (→ 문서 03).

## 3. 내장 예제 둘러보기

`Window > Examples` (또는 `Isaac Examples` 메뉴)에서 공식 데모를 실행할 수 있습니다.

추천 순서:
1. **Hello World** — 가장 기본적인 코드 구조
2. **Add a Robot / Franka** — 로봇 팔 불러오기
3. **Manipulation / Pick & Place** — 로봇 제어 기초
4. **ROS 2 샘플** — ROS 연동 (→ 문서 04)

## 4. Python으로 제어하기

Isaac Sim은 두 가지 워크플로우가 있습니다.

### (a) GUI 내장 Script Editor
`Window > Script Editor`에서 바로 실행:
```python
from isaacsim.core.api import World
from isaacsim.core.api.objects import DynamicCuboid
import numpy as np

world = World()
world.scene.add_default_ground_plane()
cube = world.scene.add(
    DynamicCuboid(prim_path="/World/cube", position=np.array([0, 0, 1.0]))
)
world.reset()
for _ in range(120):
    world.step(render=True)   # 큐브가 떨어지는 시뮬레이션
```
> ⚠️ API 모듈 경로는 버전마다 다릅니다(`omni.isaac.core` ↔ `isaacsim.core`).
> 자동완성과 공식 예제 코드를 기준으로 맞추세요.

### (b) Standalone 스크립트 (헤드리스/자동화)
```bash
./python.sh my_script.py        # Isaac Sim에 포함된 python 사용
```
`SimulationApp`을 직접 띄우는 방식으로, 학습/배치 실행에 사용합니다.

## 5. 추천 외부 학습 자료
- 공식 Tutorials: https://docs.isaacsim.omniverse.nvidia.com/latest/
- NVIDIA Developer YouTube의 Isaac Sim 입문 시리즈
- j3soon의 비공식 튜토리얼: https://tutorial.j3soon.com/robotics/isaac-sim/

---
**이전 ←** [01. 설치](01-installation.md) | **다음 →** [03. USD 구조](03-usd-structure.md)
