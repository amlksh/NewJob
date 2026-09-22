"""의료기기 결합 (P1: Tier 1 — 용접 부착 + 좌표 구동).

CAD 에서 넘어오는 파라미터는 `spec`, 모델에 붙이는 일은 `builder` 가 맡는다.
Abaqus 연계는 이 패키지에 넣지 않는다 — 별도 모듈로 분리한다 (ADR-0004).
"""

from msk_engine.device.builder import DeviceBuildResult, attach_device
from msk_engine.device.spec import DeviceSpec, load_device_spec

__all__ = ["DeviceSpec", "load_device_spec", "attach_device", "DeviceBuildResult"]
