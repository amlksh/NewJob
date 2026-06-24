# 07. Replicator 합성 데이터 가이드 (PoC의 심장)

> 목표: 조립 라인의 **정상/이상 이미지 + 자동 라벨**을 Isaac Sim에서 무한히 생성한다.
> 대상: Python 보통 / 주 5~10h. "밑바닥 구현"이 아니라 "예제 복사·수정".

이 문서가 PoC에서 가장 중요하고, 입문자가 가장 많이 막히는 지점이다.
여기만 넘으면 모델 학습([Anomalib])은 거의 설정 작업이다.

## 1. Replicator란?

**Omniverse Replicator** = Isaac Sim 안에서 **합성 데이터를 자동 생성**하는 도구.
- 씬을 랜덤화(조명·각도·위치·색)하면서 이미지를 찍고,
- **라벨(바운딩박스/세그멘테이션/정상-이상 등)을 자동으로** 같이 저장한다.
- 사람이 사진 찍고 라벨링하는 고통을 통째로 없앤다 → "데이터가 없다"는 벽을 깬다.

핵심 개념:
| 용어 | 뜻 |
|------|----|
| **Randomizer** | 매 프레임 무엇을 바꿀지(조명/포즈/색/텍스처) 정의 |
| **Trigger** | 언제 데이터를 찍을지 (`on_frame` 등) |
| **Render Product** | 어느 카메라/해상도로 렌더할지 |
| **Writer** | 결과(이미지+라벨)를 어떤 포맷으로 저장할지 (`BasicWriter` 등) |
| **Domain Randomization** | 위 랜덤화를 충분히 줘서 모델을 강건하게 만드는 전략 |

## 2. PoC용 데이터 설계 (조립 라인)

부품 1종 + 이상 2~3종으로 **작게 고정**한다.

| 클래스 | 예시 (토이 조립품) | 생성 방법 |
|--------|--------------------|-----------|
| 정상(normal) | 부품이 모두 제자리 | 기준 USD 그대로 |
| 이상-누락 | 나사/커넥터 1개 없음 | 해당 Prim을 숨김/삭제 |
| 이상-오부착 | 부품이 회전/뒤집힘 | Prim 포즈 랜덤 변형 |
| 이상-위치이탈 | 부품이 자리에서 벗어남 | translate 오프셋 |

> 이상탐지(Anomaly Detection)는 **정상 이미지만 많이** 있으면 학습된다.
> 이상 이미지는 **테스트/평가용**으로 소량만 만들어도 된다 → 입문자에게 가장 유리한 전략.

## 3. 최소 워크플로우 (두 갈래)

### (a) GUI로 먼저 감 잡기 — 추천 시작점
1. Isaac Sim 실행 → `Window > Extensions`에서 **Replicator** 관련 확장 활성화
2. `Replicator > Synthetic Data Recorder` (또는 스크립트 에디터)로 카메라/출력 설정
3. 몇 장 찍어서 출력 폴더에 이미지+라벨이 생기는지 확인

### (b) Python 스크립트로 자동화 — 본 작업
아래는 **구조를 보여주는 스켈레톤**이다. (API 경로/인자는 버전마다 다르니
자동완성과 공식 예제로 맞출 것. `omni.replicator.core`가 핵심 모듈.)

```python
import omni.replicator.core as rep

# 1) 대상 에셋과 카메라
product = rep.create.from_usd("/path/to/assembly_part.usd")   # 또는 기존 Prim 참조
camera = rep.create.camera(position=(0, 0, 1.5), look_at=(0, 0, 0))
render_product = rep.create.render_product(camera, (1024, 1024))

# 2) 랜덤화 정의 (Domain Randomization)
def randomize_scene():
    lights = rep.create.light(light_type="Sphere")
    with lights:
        rep.modify.attribute("intensity", rep.distribution.uniform(2000, 8000))
    with product:
        rep.modify.pose(
            rotation=rep.distribution.uniform((-5, -5, -5), (5, 5, 5)),
            position=rep.distribution.uniform((-0.02, -0.02, 0), (0.02, 0.02, 0)),
        )
    return product.node

rep.randomizer.register(randomize_scene)

# 3) 트리거: 프레임마다 랜덤화 후 촬영
with rep.trigger.on_frame(num_frames=500):
    rep.randomizer.randomize_scene()

# 4) Writer: 이미지(+필요 라벨) 저장
writer = rep.WriterRegistry.get("BasicWriter")
writer.initialize(
    output_dir="/data/assembly/normal",   # 정상은 normal/, 이상은 abnormal/
    rgb=True,
    bounding_box_2d_tight=True,            # 분류만 할 거면 생략 가능
)
writer.attach([render_product])

rep.orchestrator.run()    # 실행 (헤드리스: ./python.sh this_script.py)
```

이상(abnormal) 데이터는 위 스크립트에서 **부품 Prim을 숨기거나/포즈를 크게 틀어** 다시 돌려
`output_dir`만 `abnormal/...`로 바꿔 저장하면 된다.

## 4. Anomalib이 기대하는 폴더 구조 (MVTec 형식)

생성한 데이터를 아래처럼 정리하면 [Anomalib]로 거의 설정만으로 학습된다.

```
assembly_dataset/
├── train/
│   └── good/            # 정상 이미지만 (학습)
├── test/
│   ├── good/            # 정상 (평가)
│   ├── missing/         # 이상-누락
│   └── misaligned/      # 이상-오부착/이탈
└── ground_truth/        # (세그멘테이션 평가 시) 마스크
```

→ Anomalib에서 `dataset.format = mvtec`, `root = assembly_dataset` 식으로 지정하고
모델(예: PatchCore/PADIM)을 골라 학습 → 추론하면 끝.

## 5. 품질을 높이는 랜덤화 체크리스트
- [ ] 조명 세기·방향·색온도
- [ ] 카메라 각도·거리(±약간) — 실제 설치 오차 흉내
- [ ] 배경/컨베이어 텍스처
- [ ] 부품 재질·색상 약간의 변동
- [ ] (있다면) 모션블러/노이즈로 실제 카메라 흉내

> 목적은 "예쁜 이미지"가 아니라 **실제 라인에서도 통하는 강건함**(sim-to-real).

## 6. 학습 체크포인트
- [ ] Replicator로 정상 이미지 수백 장을 자동 생성했다
- [ ] 이상 이미지를 종류별로 소량 생성했다
- [ ] 출력이 MVTec 폴더 구조로 정리됐다
- [ ] Anomalib로 학습 → 정상/이상을 구분하는 추론을 돌려봤다

---
**이전 ←** [06. PoC 전략](06-physical-ai-poc-strategy.md) | **처음 →** [README](../README.md)

## 참고 링크
- [Omniverse Replicator 문서](https://docs.omniverse.nvidia.com/extensions/latest/ext_replicator.html)
- [Isaac Sim 합성 데이터 튜토리얼](https://docs.isaacsim.omniverse.nvidia.com/latest/)
- [Anomalib (이상탐지 라이브러리)](https://github.com/open-edge-platform/anomalib)
- [MVTec AD 데이터셋(폴더 구조 참고)](https://www.mvtec.com/company/research/datasets/mvtec-ad)

[Anomalib]: https://github.com/open-edge-platform/anomalib
