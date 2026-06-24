# 03. USD 구조 이해

Isaac Sim은 **USD-native** 시뮬레이터입니다. 즉 씬의 모든 것 — 로봇, 조명, 카메라,
물리 설정 — 이 USD로 표현됩니다. USD를 이해하면 Isaac Sim 전체가 쉬워집니다.

## 1. USD란?

**USD (Universal Scene Description)** 는 Pixar가 만든 오픈소스 3D 씬 기술 포맷입니다.
- 여러 파일/레이어를 합성(composition)해 하나의 씬을 구성
- 대규모 씬을 협업·재사용하기 좋게 설계됨
- 공식: https://openusd.org/

파일 확장자:
| 확장자 | 의미 |
|--------|------|
| `.usd` | 바이너리/텍스트 (자동) |
| `.usda` | 사람이 읽는 ASCII 텍스트 (공부할 때 열어보기 좋음) |
| `.usdc` | 바이너리 (Crate, 빠르고 작음) |
| `.usdz` | 압축 패키지 (배포용) |

## 2. 핵심 개념 4가지

```
Stage (씬 전체)
└── Prim (/World)              ← 객체 노드, 경로(path)로 식별
    ├── Prim (/World/Robot)
    │   ├── Property: xformOp:translate = (0, 0, 0)   ← Attribute(값)
    │   └── Relationship: material:binding -> /World/Looks/Steel  ← Relationship(연결)
    └── Prim (/World/Light)
```

### (1) Stage
- 씬 전체를 담는 컨테이너. Isaac Sim의 **Stage 패널**이 바로 이것.
- 하나 이상의 USD 레이어가 합성된 최종 결과.

### (2) Prim (Primitive)
- 씬을 구성하는 **모든 노드**. 파일시스템 경로처럼 `/World/Robot/Arm`로 식별.
- 각 Prim은 **타입**을 가짐: `Xform`(변환), `Mesh`(형상), `Camera`, `Light`,
  `PhysicsScene`, `RigidBodyAPI` 등.

### (3) Property = Attribute + Relationship
- **Attribute**: 실제 값. 예) `xformOp:translate`, `radius`, `points`.
- **Relationship**: 다른 Prim을 가리키는 연결. 예) 머티리얼 바인딩.

### (4) Schema (스키마)
- Prim이 가질 수 있는 속성의 "규격". 예) `UsdGeomMesh`, `UsdPhysicsRigidBodyAPI`.
- Isaac Sim의 물리는 **PhysX 스키마**(`PhysicsRigidBodyAPI`, `PhysicsCollisionAPI` 등)로
  Prim에 적용됩니다. GUI의 `Add > Physics`가 이 스키마를 붙이는 동작.

## 3. Composition (합성) — USD의 핵심 강점

여러 레이어를 조합해 씬을 만드는 메커니즘. 강도 순서(LIVRPS)는 외울 필요 없지만 개념은 중요:

| Arc | 용도 (한 줄 설명) |
|-----|-------------------|
| **sublayer** | 레이어를 통째로 겹쳐 쌓기 (포토샵 레이어처럼) |
| **reference** | 다른 USD 파일을 특정 Prim 아래로 가져오기 (에셋 재사용 핵심) |
| **payload** | reference의 지연 로딩 버전 (무거운 에셋을 필요할 때만 로드) |
| **inherits** | 다른 Prim의 속성 상속 |
| **variantSet** | 같은 Prim의 여러 버전 전환 (예: 색상/형상 variant) |

> 실전 팁: 로봇 에셋을 **reference**로 씬에 가져오고, 위치/물리 같은 변경은
> 상위 레이어에서 **override**하는 패턴이 가장 흔합니다.

## 4. `.usda` 파일 직접 읽어보기

ASCII로 저장하면 구조가 그대로 보입니다:
```usda
#usda 1.0
(
    defaultPrim = "World"
    upAxis = "Z"
    metersPerUnit = 1.0
)

def Xform "World"
{
    def Cube "box" (
        prepend apiSchemas = ["PhysicsRigidBodyAPI", "PhysicsCollisionAPI"]
    )
    {
        double size = 1.0
        float3 xformOp:translate = (0, 0, 2)
        uniform token[] xformOpOrder = ["xformOp:translate"]
    }

    def DistantLight "Sun"
    {
        float inputs:intensity = 3000
    }
}
```
읽는 법:
- `def Xform "World"` → `/World` 경로의 Xform 타입 Prim 정의(define)
- `apiSchemas = [...]` → 이 Prim에 물리 API 스키마를 적용
- `float3 xformOp:translate` → 위치 Attribute

## 5. Python으로 USD 다루기 (Isaac Sim 안에서)

```python
from pxr import Usd, UsdGeom, Gf
import omni.usd

stage = omni.usd.get_context().get_stage()       # 현재 Stage 가져오기

# Prim 생성
cube = UsdGeom.Cube.Define(stage, "/World/MyCube")
cube.AddTranslateOp().Set(Gf.Vec3f(0, 0, 2))

# 순회
for prim in stage.Traverse():
    print(prim.GetPath(), prim.GetTypeName())

# 속성 읽기/쓰기
prim = stage.GetPrimAtPath("/World/MyCube")
attr = prim.GetAttribute("size")
print(attr.Get())
```
- `pxr`는 USD의 공식 Python 바인딩(OpenUSD에서 옴).
- Isaac Sim API(`isaacsim.core...`)는 이 위에 로봇 친화적 래퍼를 얹은 것.

## 6. 학습 체크포인트
- [ ] Stage / Prim / Property / Schema를 말로 설명할 수 있다
- [ ] GUI에서 큐브를 만들고 `.usda`로 저장해 텍스트를 읽어봤다
- [ ] reference로 외부 에셋을 가져와봤다
- [ ] Python으로 Stage를 순회하고 Prim을 만들어봤다

---
**이전 ←** [02. 튜토리얼](02-tutorials.md) | **다음 →** [04. ROS 2 구조](04-ros2-structure.md)

## 참고 링크
- [OpenUSD 공식](https://openusd.org/release/index.html)
- [USD 용어집](https://openusd.org/release/glossary.html)
- [Isaac Sim — USD 워크플로우](https://docs.isaacsim.omniverse.nvidia.com/latest/)
