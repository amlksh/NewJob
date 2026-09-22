# CAD → 해석 기기 파라미터 인터페이스

CAD 쪽에서 이 문서의 스키마에 맞춘 YAML 을 내보내면, 해석 엔진이 그 파일만
읽어 기기를 인체 모델에 붙인다. 엔진은 CAD 파일을 직접 읽지 않는다.

**이유**: CAD 포맷과 도구는 과제 중간에 바뀔 수 있지만, 해석에 필요한 물리량
(질량, 관성, 부착점, 힌지 축, 가동범위, 구동 조건)은 바뀌지 않는다. 경계를
YAML 로 두면 CAD 쪽 변경이 해석 코드에 번지지 않고, 어느 리비전의 기기로
돌린 결과인지 `source` 에 남아 V&V 추적이 된다.

- **기기 측에 보낼 요청 패키지: `device_parameter_request/`** (WO-G1 / A-1)
  — 요청서와 값만 채우는 템플릿. 이 문서는 스키마 설명이고, 그쪽이 발송본이다.
- 스키마 구현: `src/msk_engine/device/spec.py`
- 모델 조립: `src/msk_engine/device/builder.py`
- 결합 방식과 적용 한계: `docs/decisions/ADR-0004-device-coupling.md`
- 예시: `configs/devices/knee_rehab_brace_example.yaml`

## 단위 규약

| 물리량 | 단위 | 비고 |
| --- | --- | --- |
| 길이·부착점 | **m** | CAD 가 mm 면 내보낼 때 변환할 것. 엔진은 추정하지 않는다 |
| 질량 | kg | |
| 관성 | kg·m² | 질량중심 기준, 세그먼트 좌표계 |
| 토크 | N·m | |
| 각도 (ROM, 자세) | **deg** | 사람과 CAD 가 deg 로 말하므로 입력은 deg. 내부에서 rad 로 변환한다 |
| 강성 (ROM 스토퍼) | N·m/deg | OpenSim `CoordinateLimitForce` 가 회전 좌표에서 deg 를 쓴다 |
| 강성 (passive) | N·m/rad | OpenSim `SpringGeneralizedForce` 는 rad 를 쓴다 |

> 강성 두 가지의 단위가 다르다. OpenSim 쪽 규약이 그러하므로 맞춘 것이며,
> 항목 이름(`stiffness_nm_per_deg`, `stiffness_nm_per_rad`)에 단위를 박아 두었다.

## 좌표계 규약

- `attachment.location` 은 **host_body 의 좌표계** 기준이다. 지면 기준이 아니다.
- `hinge.axis` 와 `hinge.location` 은 `hinge.expressed_in` 에 적은 body 의 좌표계 기준이다.
- 결과의 관절반력은 `joint_reaction_frame` (기본 경골)으로 표현된다 — 향후 FE 연계 기준.

## 스키마

```yaml
name: <문자열>                 # 필수. 기기 식별자
description: <문자열>          # 선택

source:                        # CAD 출처. 비거나 TBD 면 경고가 결과에 남는다
  cad_file: <문자열>
  revision: <문자열>
  exported_by: <문자열>
  exported_at: <문자열>
  notes: <문자열>

segments:                      # 필수, 최소 1개. 기기 강체
  - name: <문자열>             # 필수
    mass_kg: <양수>            # 필수. 0 이면 거절한다
    center_of_mass: [x, y, z]  # 선택, 기본 [0,0,0]
    inertia: [Ixx, Iyy, Izz, Ixy, Ixz, Iyz]   # 선택, 기본 0 (경고)
    attachment:                # 필수
      host_body: <인체 body 이름>   # 필수. 모델에 없으면 거절한다
      location: [x, y, z]      # host_body 좌표계, m
      orientation_deg: [x, y, z]

hinge:                         # 선택. 없으면 축 정합성을 점검하지 않는다
  axis: [x, y, z]              # 영벡터면 거절. 자동 정규화된다
  expressed_in: <body 이름>
  location: [x, y, z]
  alignment_tolerance_deg: <양수>   # 기본 10.0

rom:                           # 선택. 기기 스토퍼
  coordinate: <인체 좌표 이름>
  min_deg: <수>
  max_deg: <수>                # min 보다 커야 한다
  stiffness_nm_per_deg: <양수> # 0 이면 거절 — 아무것도 막지 못하는 스토퍼
  damping_nm_s_per_deg: <수>   # 기본 0
  transition_deg: <양수>       # 기본 2.0

actuation:                     # 선택, 기본 mode: none
  mode: none | assistive | prescribed_torque | passive
  coordinate: <인체 좌표 이름>  # mode 가 none 이 아니면 필수
  max_torque_nm: <양수>        # assistive 필수
  torque_file: <경로>          # prescribed_torque 필수. time, torque 두 열의 STO/MOT
  stiffness_nm_per_rad: <수>   # passive 필수
  damping_nm_s_per_rad: <수>   # passive 선택
  rest_angle_deg: <수>         # passive 선택, 기본 0
```

## 구동 방식 선택

| mode | 언제 쓰나 | 결과 해석 |
| --- | --- | --- |
| `none` | 수동 보조기, 질량·ROM 효과만 볼 때 | 착용 자체의 역학적 부담 |
| `assistive` | "이 동작을 도우려면 기기가 몇 N·m 를 내야 하나" | 장치 토크는 **최적화 결과**이지 기기 요구사양이 아니다 (ADR-0004 적용 한계) |
| `prescribed_torque` | 제어 프로파일이 이미 정해진 경우 | 파일의 토크가 그대로 작용한다 |
| `passive` | 스프링·댐퍼 기반 보조기 | 강성·감쇠는 rad 단위 |

`prescribed_motion`(기기가 관절각을 강제로 끌고 가는 CPM 방식)은 **P1 범위가
아니며 스키마에 적어도 거절한다.** 인체 좌표를 강제하면 IK 결과와 충돌하고,
기기가 자기 자유도를 가져야 제대로 표현된다 — ADR-0004 Tier 2.

## 검증되는 것 / 안 되는 것

엔진이 해석 전에 잡는 것:

- 필수 항목 누락, 오타(모르는 키는 거절한다), 단위 자리 바뀜으로 생기는 음수·0
- `host_body`·`coordinate` 가 모델에 실제로 있는지 — 없으면 모델의 이름 목록과 함께 거절
- 힌지 축이 인체 관절 축과 허용 오차 안에 있는지 — 넘으면 경고로 결과에 남는다
- CAD 출처가 비었는지 — 경고 (`TBD` 는 값으로 인정하지 않는다)

엔진이 **확인해 주지 않는** 것:

- 질량·관성 값이 실제 기기와 맞는지. 단위만 맞으면 그대로 받는다
- 부착점이 해부학적으로 타당한지
- ROM 스토퍼 강성이 실제 재료 특성과 맞는지

이 값들은 CAD·시험 데이터에서 와야 하며, 출처를 `source` 에 남기는 것이
유일한 방어선이다.

## 넘겨받을 때 확인할 것 (체크리스트)

- [ ] 길이 단위가 m 인가 (CAD 기본은 대개 mm)
- [ ] 관성이 **질량중심 기준**인가 (원점 기준이면 평행축 정리로 옮길 것)
- [ ] 부착점이 host_body 좌표계 기준인가 (조립체 원점 기준이 아닌가)
- [ ] `source.revision` 이 실제 리비전인가 (TBD 아님)
- [ ] ROM 이 기기 스토퍼 값인가 (환자 처방 ROM 과 다를 수 있다)
- [ ] `max_torque_nm` 이 연속 정격인가 최대 정격인가 — `notes` 에 적을 것
