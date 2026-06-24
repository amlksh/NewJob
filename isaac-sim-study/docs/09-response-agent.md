# 09. 대응 에이전트 (M4) — "검사기"와 "에이전트"의 분기점

> 목표: 8장의 이상 감지 결과를 받아 **무엇을 할지 스스로 선택**하는 레이어를 만든다.
> 이게 PoC의 핵심 차별점이자, 회장님 데모에서 "AI가 **행동했다**"의 증거다.
> 대상: Python 보통. 규칙 기반으로 시작 → 필요 시 확장.

## 1. 왜 이 레이어가 결정적인가

```
검사기:  이미지 → "불량입니다"  (끝)
에이전트: 이미지 → 이상 감지 → 종류·심각도 판단 → "라인을 멈추겠습니다" → 실제 신호 발신
```

- 8장까지는 "본다 + 판단한다"였다. 9장이 **"행동한다"**를 완성한다.
- 단순 규칙이어도 좋다. **중요한 건 루프가 닫히는 것**이다.

## 2. 입력 → 판단 → 행동 설계

### 입력 (8장에서 옴)
- `anomaly_score`: 이상 점수(0~1 등)
- `anomaly_map`: 이상 위치 히트맵 (어느 영역인지)
- (선택) `anomaly_type`: 분류기/규칙으로 추정한 이상 종류

### 판단 규칙 (예시 — 작게 시작)
| 조건 | 심각도 | 대응(행동) |
|------|--------|-----------|
| score < 임계값 | 정상 | 통과(로그만) |
| 임계값 ≤ score < 0.8 | 경미 | 경고 표시 + 스냅샷 저장 |
| score ≥ 0.8 또는 핵심부위 이상 | 중대 | **라인 정지 신호** + 리젝트 + 알람 |
| 애매(임계값 근처) | 모호 | **사람 호출**(이미지 첨부) |

> "핵심부위"는 히트맵에서 특정 영역(예: 커넥터 위치)의 이상 점수로 판단할 수 있다.

## 3. 구현 스켈레톤 (규칙 기반)

```python
from dataclasses import dataclass

@dataclass
class Detection:
    score: float
    region: str | None = None      # 히트맵에서 추정한 이상 영역
    atype: str | None = None       # (선택) 이상 종류

class ResponseAgent:
    def __init__(self, threshold=0.5, critical=0.8, critical_regions=("connector",)):
        self.threshold = threshold
        self.critical = critical
        self.critical_regions = critical_regions

    def decide(self, det: Detection) -> dict:
        if det.score < self.threshold:
            return self._act("PASS", det)
        if det.score >= self.critical or det.region in self.critical_regions:
            return self._act("STOP_LINE", det)        # 중대 → 라인 정지
        if abs(det.score - self.threshold) < 0.05:
            return self._act("CALL_HUMAN", det)        # 모호 → 사람 호출
        return self._act("WARN", det)                  # 경미 → 경고

    def _act(self, action: str, det: Detection) -> dict:
        # 실제 행동 실행부 (로그/알람/ROS2 신호/사람 호출)
        log = {"action": action, "score": det.score,
               "region": det.region, "type": det.atype}
        # 예: if action == "STOP_LINE": publish_ros2_stop()
        print("[AGENT]", log)
        return log
```

루프 연결:
```python
agent = ResponseAgent()
for frame in stream:                      # Isaac Sim 카메라 스트림
    det = Detection(*run_anomaly_model(frame))   # 8장 모델
    decision = agent.decide(det)                  # 판단 + 행동
```

## 4. 실제 "행동"을 트윈에 반영 (데모 임팩트)

말로만 "정지"가 아니라 **화면에서 보이게** 한다:
- **ROS 2 연동**([04](04-ros2-structure.md)): `STOP_LINE` → `/line_control` 토픽 발행 →
  Isaac Sim 안 컨베이어가 실제로 멈춤.
- **간단 버전**: Isaac Sim에서 컨베이어 속도 Prim을 0으로, 경고등 색을 빨강으로 변경.
- **대시보드**: 이상 점수 그래프 + 히트맵 + 현재 액션을 한 화면에.

> 회장님 데모의 30초: *이상 부품 등장 → 히트맵 빨갛게 → 화면에 "STOP_LINE" →
> 컨베이어 멈춤 → "사람 호출" 알림*. 이 흐름 하나면 충분하다.

## 5. (선택, M5) LLM 사고 리포트 — 보너스 임팩트

대응 직후 LLM/VLM으로 자연어 한 줄을 생성하면 "스스로 생각하는 AI" 인상이 강해진다.

```
"컨베이어 3번에서 커넥터 누락(신뢰도 0.91)을 감지해 라인을 정지하고 담당자를 호출했습니다."
```
- Claude 등 API에 (이상 종류·점수·위치)를 넣어 보고 문장을 생성.
- **핵심 루프(M4) 완성 전에는 손대지 않는다.** 어디까지나 보너스.

## 6. 산출물 (M4 완료 기준 = "에이전트라 부를 수 있는 상태")
- [ ] 이상 점수 → 대응 선택이 동작하는 `ResponseAgent`
- [ ] 최소 3가지 대응(통과/경고·정지/사람호출)이 조건에 따라 갈림
- [ ] 대응이 트윈 화면(또는 ROS2)에 **실제로 반영**됨
- [ ] 감지→판단→대응 엔드투엔드 데모 영상 1개

---
**이전 ←** [08. 이상탐지 모델 학습](08-anomaly-model-training.md) | **처음 →** [README](../README.md)

## 참고 링크
- [Isaac Sim ROS 2 튜토리얼](https://docs.isaacsim.omniverse.nvidia.com/latest/ros2_tutorials/ros2_landing_page.html)
- [Claude API (사고 리포트용, 선택)](https://docs.anthropic.com/)
