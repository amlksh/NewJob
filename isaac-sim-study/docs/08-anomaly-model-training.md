# 08. 이상탐지 모델 학습 (M3)

> 목표: [07](07-replicator-synthetic-data.md)에서 만든 합성 데이터로 **이상을 잡아내는 모델**을 만든다.
> 이 단계가 끝나면 "보여줄 게 있는 상태"(PoC 최소 성공선)에 도달한다.
> 대상: Python 보통. 밑바닥 구현 없이 **Anomalib 설정 + 실행** 중심.

## 1. 왜 "이상탐지(Anomaly Detection)"인가

| 일반 분류기 | 이상탐지 |
|-------------|----------|
| 정상·불량 **둘 다** 많이 필요 | **정상만** 많이 있으면 학습됨 |
| 불량 종류를 미리 다 알아야 함 | 처음 보는 이상도 "정상과 다름"으로 잡음 |
| 데이터 라벨링 부담 큼 | 부담 최소 |

조립 라인은 불량이 드물기 때문에 **이상탐지가 정답에 가깝다.**
불량 *종류 구분*이 꼭 필요할 때만 분류/검출을 얹는다(→ 9장 대응 정책에서 활용).

## 2. 환경 준비

```bash
# (Isaac Sim과 별개) 일반 Python 환경에서 진행 가능
python3 -m venv ~/env_anomalib
source ~/env_anomalib/bin/activate
pip install --upgrade pip
pip install anomalib            # 필요한 추가 의존성은 안내에 따라 설치
```
> Anomalib은 버전에 따라 CLI/설정 방식이 바뀐다. 설치 후 공식 README의
> "Getting Started"를 1차 기준으로 삼는다.

데이터는 [07. §4](07-replicator-synthetic-data.md)의 MVTec 폴더 구조를 그대로 사용:
```
assembly_dataset/
├── train/good/        # 정상(학습)
└── test/
    ├── good/          # 정상(평가)
    ├── missing/       # 이상-누락
    └── misaligned/    # 이상-오부착/이탈
```

## 3. 모델 선택 (입문 추천)

| 모델 | 특징 | 추천 상황 |
|------|------|-----------|
| **PADIM** | 가볍고 빠름, 설정 간단 | 첫 시도 |
| **PatchCore** | 정확도 높음(대표적 SOTA급) | 데모 품질 올릴 때 |
| **EfficientAD** | 빠른 추론 | 실시간 데모 |

**PADIM으로 시작 → 잘 되면 PatchCore로 교체**가 무난하다.

## 4. 학습 → 추론 (개념 흐름)

Anomalib은 보통 **설정(config) 또는 짧은 Python 스크립트**로 끝난다.

```python
# 구조를 보여주는 스켈레톤 (정확한 클래스/인자는 설치 버전 문서 확인)
from anomalib.data import Folder
from anomalib.models import Padim
from anomalib.engine import Engine

datamodule = Folder(
    name="assembly",
    root="assembly_dataset",
    normal_dir="train/good",
    abnormal_dir="test/missing",     # 평가용 이상
    normal_test_dir="test/good",
)

model = Padim()
engine = Engine()

engine.fit(model=model, datamodule=datamodule)     # 학습(정상 패턴 습득)
engine.test(model=model, datamodule=datamodule)    # 성능 평가
# 단일 이미지 추론 → 이상 점수 + 히트맵(이상 위치) 산출
predictions = engine.predict(model=model, datamodule=datamodule)
```

산출물 두 가지가 데모의 재료가 된다:
1. **이상 점수(anomaly score)** — 임계값을 넘으면 "이상" 판정 → 9장 대응의 입력
2. **히트맵(anomaly map)** — 어디가 이상인지 색으로 표시 → 회장님 데모에서 강력함

## 5. 성능 확인 포인트
- [ ] 정상 이미지는 낮은 점수, 이상 이미지는 높은 점수가 나오는가
- [ ] 임계값(threshold)을 어디로 잡아야 정상/이상이 갈리는가
- [ ] 히트맵이 실제 이상 부위를 가리키는가
- [ ] (선택) AUROC 등 지표 확인

> 잘 안 되면? 대부분 **데이터 문제**다. 정상 이미지 다양성(조명·각도) 부족,
> 이상이 너무 미세함 등 → [07]로 돌아가 랜덤화/이상 강도를 조정한다.

## 6. 산출물 (M3 완료 기준)
- [ ] 학습된 모델 파일(weights)
- [ ] "정상 vs 이상" 추론 결과 + 히트맵 이미지 몇 장
- [ ] 임계값 1개 결정 → 다음 장(대응 에이전트)의 입력으로 사용

---
**이전 ←** [07. Replicator 합성 데이터](07-replicator-synthetic-data.md) | **다음 →** [09. 대응 에이전트](09-response-agent.md)

## 참고 링크
- [Anomalib](https://github.com/open-edge-platform/anomalib)
- [Anomalib 문서](https://anomalib.readthedocs.io/)
- [PatchCore 논문](https://arxiv.org/abs/2106.08265)
