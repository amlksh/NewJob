"""장치를 인체 모델에 붙여 해석용 모델을 만든다.

P1 결합 방식 (Tier 1, ADR-0004):
  - 장치 세그먼트를 인체 body 에 **용접(WeldJoint)** 한다. 새 자유도는 없다.
    따라서 늘어나는 것은 질량·관성이고, 닫힌 운동 사슬은 생기지 않는다.
  - 장치의 가동범위는 인체 좌표에 CoordinateLimitForce 로 건다.
  - 장치의 구동은 인체 좌표에 작용하는 CoordinateActuator 로 표현한다.

왜 이렇게 하는가:
  장치를 자기 자유도를 가진 별도 사슬로 모델링하면 인체와 장치가 두 곳에서
  붙으면서 닫힌 루프가 생기고, ID/SO 가 구속조건을 동반한 문제로 바뀐다.
  P1 목표(관절 모멘트·근육력·관절반력 산출)에는 Tier 1 로 충분하고,
  Tier 2 는 장치 내부 하중이 필요해질 때 ADR 을 갱신하고 간다.

**적용 한계** — 결과를 인용할 때 같이 말해야 하는 것들:
  - 스트랩의 유연성·미끄러짐 없음 (완전 강체 부착)
  - 장치 내부 부재에 걸리는 하중은 나오지 않는다 (Tier 2 영역)
  - 힌지 축이 인체 관절 축과 어긋나도 그 구속력은 표현되지 않는다.
    어긋남은 경고로만 남긴다.

**스케일링 이후에 붙여야 한다.** 장치 치수는 CAD 로 고정되어 있으므로
피험자에 맞춰 늘리면 안 된다. 파이프라인이 scale → device 순서로 부른다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from msk_engine.device.spec import DeviceSpec
from msk_engine.errors import StepExecutionError

#: 장치가 만든 구성요소 이름 앞에 붙인다. 결과 파일에서 인체 것과 구분된다.
DEVICE_PREFIX = "device"


@dataclass
class DeviceBuildResult:
    """장치를 붙인 결과."""

    model_file: Path
    added_bodies: list[str] = field(default_factory=list)
    added_forces: list[str] = field(default_factory=list)
    added_controllers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: 장치 토크를 담당하는 액추에이터 이름. 결과 추출에서 이 이름을 찾는다.
    actuator_name: str | None = None
    hinge_misalignment_deg: float | None = None

    def as_dict(self) -> dict:
        return {
            "model_file": str(self.model_file),
            "added_bodies": self.added_bodies,
            "added_forces": self.added_forces,
            "added_controllers": self.added_controllers,
            "actuator_name": self.actuator_name,
            "hinge_misalignment_deg": self.hinge_misalignment_deg,
            "warnings": self.warnings,
        }


def _require_opensim():
    try:
        import opensim  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise StepExecutionError(
            "device",
            "OpenSim 파이썬 패키지를 찾을 수 없음. "
            "`pip install opensim` 또는 docker/Dockerfile 환경을 사용할 것",
        ) from exc
    return opensim


def _body_names(model: Any) -> list[str]:
    return [model.getBodySet().get(i).getName() for i in range(model.getBodySet().getSize())]


def _coordinate_names(model: Any) -> list[str]:
    return [
        model.getCoordinateSet().get(i).getName()
        for i in range(model.getCoordinateSet().getSize())
    ]


def attach_device(
    model_file: str | Path, spec: DeviceSpec, output_file: str | Path
) -> DeviceBuildResult:
    """스케일된 인체 모델에 장치를 붙여 새 .osim 을 쓴다.

    입력 모델은 건드리지 않는다. 장치가 붙은 모델은 따로 저장되어
    provenance 에 남고, 이후 IK/ID/SO/JR 이 이 모델을 쓴다.
    """
    osim = _require_opensim()
    model_file = Path(model_file)
    output_file = Path(output_file)

    if not model_file.is_file():
        raise StepExecutionError("device", f"인체 모델 파일 없음: {model_file}")

    model = osim.Model(str(model_file))
    model.initSystem()
    result = DeviceBuildResult(model_file=output_file)

    _check_targets_exist(model, spec)

    for segment in spec.segments:
        body = osim.Body(
            f"{DEVICE_PREFIX}_{segment.name}",
            segment.mass_kg,
            osim.Vec3(*segment.center_of_mass),
            osim.Inertia(*segment.inertia),
        )
        model.addBody(body)

        host = model.getBodySet().get(segment.attachment.host_body)
        weld = osim.WeldJoint(
            f"{DEVICE_PREFIX}_{segment.name}_weld",
            host,
            osim.Vec3(*segment.attachment.location),
            osim.Vec3(*segment.attachment.orientation_rad),
            body,
            osim.Vec3(0, 0, 0),
            osim.Vec3(0, 0, 0),
        )
        model.addJoint(weld)
        result.added_bodies.append(body.getName())

    if spec.rom is not None:
        result.added_forces.append(_add_rom_limit(osim, model, spec))

    _add_actuation(osim, model, spec, result)

    # 연결을 확정하고 시스템을 한 번 만들어 본다. 여기서 터지면 모델이
    # 성립하지 않는 것이므로, 해석을 시작하기 전에 멈춘다.
    model.finalizeConnections()
    try:
        state = model.initSystem()
    except Exception as exc:  # noqa: BLE001 - OpenSim 예외 타입이 다양하다
        raise StepExecutionError(
            "device",
            f"장치를 붙인 모델을 초기화할 수 없음: {exc}",
        ) from exc

    if spec.hinge is not None:
        misalignment, note = _check_hinge_alignment(osim, model, state, spec)
        result.hinge_misalignment_deg = misalignment
        if note:
            result.warnings.append(note)

    result.warnings.extend(spec.warnings())

    output_file.parent.mkdir(parents=True, exist_ok=True)
    model.printToXML(str(output_file))
    if not output_file.is_file():
        raise StepExecutionError("device", f"장치 모델을 쓰지 못함: {output_file}")
    return result


def _check_targets_exist(model: Any, spec: DeviceSpec) -> None:
    """장치가 가리키는 인체 body·좌표가 실제로 있는지 본다.

    이름이 틀리면 OpenSim 이 나중에 엉뚱한 곳에서 실패하므로 여기서 잡는다.
    """
    bodies = _body_names(model)
    missing_bodies = sorted({b for b in spec.host_bodies if b not in bodies})
    if missing_bodies:
        raise StepExecutionError(
            "device",
            f"모델에 없는 인체 body 에 붙이려 함: {', '.join(missing_bodies)}. "
            f"모델의 body: {', '.join(bodies)}",
        )

    coordinates = _coordinate_names(model)
    wanted = {
        label: name
        for label, name in (
            ("rom.coordinate", spec.rom.coordinate if spec.rom else None),
            ("actuation.coordinate", spec.actuation.coordinate or None),
        )
        if name
    }
    missing = {label: name for label, name in wanted.items() if name not in coordinates}
    if missing:
        detail = ", ".join(f"{label}={name}" for label, name in sorted(missing.items()))
        raise StepExecutionError(
            "device",
            f"모델에 없는 좌표를 가리킴: {detail}. "
            f"모델의 좌표: {', '.join(coordinates)}",
        )

    if spec.hinge is not None and spec.hinge.expressed_in not in bodies:
        raise StepExecutionError(
            "device",
            f"hinge.expressed_in '{spec.hinge.expressed_in}' 가 모델에 없음. "
            f"모델의 body: {', '.join(bodies)}",
        )


def _add_rom_limit(osim: Any, model: Any, spec: DeviceSpec) -> str:
    """장치 스토퍼를 CoordinateLimitForce 로 건다.

    CoordinateLimitForce 는 회전 좌표에서 각도를 **도(deg)** 로 받는다.
    그래서 DeviceSpec 도 deg 로 받아 그대로 넘긴다 — 중간에 변환하면
    단위가 두 번 바뀌어 조용히 틀린다.
    """
    rom = spec.rom
    assert rom is not None
    limit = osim.CoordinateLimitForce(
        rom.coordinate,
        rom.max_deg,
        rom.stiffness_nm_per_deg,
        rom.min_deg,
        rom.stiffness_nm_per_deg,
        rom.damping_nm_s_per_deg,
        rom.transition_deg,
        False,
    )
    limit.setName(f"{DEVICE_PREFIX}_{spec.name}_rom")
    model.addForce(limit)
    return limit.getName()


def _add_actuation(osim: Any, model: Any, spec: DeviceSpec, result: DeviceBuildResult) -> None:
    """구동 방식에 맞는 구성요소를 붙인다."""
    actuation = spec.actuation
    if actuation.mode == "none":
        return

    if actuation.mode == "passive":
        spring = osim.SpringGeneralizedForce(actuation.coordinate)
        spring.setName(f"{DEVICE_PREFIX}_{spec.name}_spring")
        spring.setStiffness(actuation.stiffness_nm_per_rad)
        spring.setRestLength(math.radians(actuation.rest_angle_deg))
        spring.setViscosity(actuation.damping_nm_s_per_rad or 0.0)
        model.addForce(spring)
        result.added_forces.append(spring.getName())
        return

    actuator = osim.CoordinateActuator(actuation.coordinate)
    actuator.setName(f"{DEVICE_PREFIX}_{spec.name}_torque")
    model.addForce(actuator)
    result.added_forces.append(actuator.getName())
    result.actuator_name = actuator.getName()

    if actuation.mode == "assistive":
        # optimal_force 가 장치가 낼 수 있는 최대 토크가 된다. Static
        # Optimization 은 control 을 [-1, 1] 에서 찾으므로 결과 토크의
        # 절댓값은 max_torque_nm 을 넘지 않는다.
        actuator.setOptimalForce(actuation.max_torque_nm)
        actuator.setMinControl(-1.0)
        actuator.setMaxControl(1.0)
        return

    if actuation.mode == "prescribed_torque":
        # 토크가 이미 정해져 있으므로 optimal_force 를 1 로 두고
        # 제어값 자체를 N·m 로 준다. 그래야 파일의 숫자가 그대로 토크가 된다.
        actuator.setOptimalForce(1.0)
        times, torques = _read_torque_profile(actuation.torque_file)
        bound = max(abs(v) for v in torques)
        actuator.setMinControl(-bound - 1.0)
        actuator.setMaxControl(bound + 1.0)

        spline = osim.GCVSpline(3, len(times), _double_array(osim, times), _double_array(osim, torques))
        spline.setName(f"{DEVICE_PREFIX}_{spec.name}_torque_profile")

        controller = osim.PrescribedController()
        controller.setName(f"{DEVICE_PREFIX}_{spec.name}_controller")
        controller.addActuator(actuator)
        controller.prescribeControlForActuator(actuator.getName(), spline)
        model.addController(controller)
        result.added_controllers.append(controller.getName())


def _double_array(osim: Any, values: list[float]):
    array = osim.ArrayDouble()
    for index, value in enumerate(values):
        array.set(index, float(value))
    return array


def _read_torque_profile(path: Path | None) -> tuple[list[float], list[float]]:
    """time, torque 두 열을 가진 STO/MOT 를 읽는다.

    결측이나 빈 파일을 0 으로 메우지 않는다 — 조용히 '토크 없음' 이 되어
    장치가 없는 해석과 구분되지 않기 때문이다.
    """
    if path is None or not path.is_file():
        raise StepExecutionError("device", f"토크 프로파일 파일 없음: {path}")

    from msk_engine.quality import _read_sto  # noqa: PLC0415

    header, rows = _read_sto(path)
    if not rows:
        raise StepExecutionError("device", f"토크 프로파일에 데이터가 없음: {path}")
    if len(header) < 2:
        raise StepExecutionError(
            "device", f"토크 프로파일에 열이 부족함 (time, torque 필요): {path}"
        )

    times: list[float] = []
    torques: list[float] = []
    for row in rows:
        if len(row) < 2 or row[0] is None or row[1] is None:
            raise StepExecutionError(
                "device",
                f"토크 프로파일에 읽을 수 없는 값이 있음: {path} — 보간으로 메우지 않는다",
            )
        times.append(row[0])
        torques.append(row[1])
    return times, torques


def _check_hinge_alignment(
    osim: Any, model: Any, state: Any, spec: DeviceSpec
) -> tuple[float | None, str]:
    """CAD 힌지 축과 인체 관절 축이 얼마나 어긋났는지 본다.

    P1 모델은 어긋남에서 생기는 구속력을 표현하지 않는다. 그래도 값을 남기는
    이유는, 장치 설계가 해부학적 축과 크게 다르면 그 해석 결과의 적용 범위가
    좁아진다는 사실을 결과와 함께 남겨야 하기 때문이다.

    기본 자세(default pose)에서 두 축을 지면 좌표계로 옮겨 사잇각을 잰다.
    축의 부호는 의미가 없으므로 예각으로 환산한다.
    """
    hinge = spec.hinge
    assert hinge is not None
    coordinate_name = spec.actuation.coordinate or (spec.rom.coordinate if spec.rom else "")
    if not coordinate_name:
        return None, ""

    joint_axis = _joint_axis_in_ground(osim, model, state, coordinate_name)
    if joint_axis is None:
        return None, (
            f"'{coordinate_name}' 의 관절 축을 특정할 수 없어 힌지 정합성을 점검하지 못함 "
            "(PinJoint/CustomJoint 만 지원)"
        )

    frame = model.getBodySet().get(hinge.expressed_in)
    device_axis = frame.expressVectorInGround(state, osim.Vec3(*hinge.unit_axis))
    device = [device_axis.get(i) for i in range(3)]

    dot = sum(a * b for a, b in zip(device, joint_axis, strict=True))
    norm = math.sqrt(sum(v * v for v in device)) * math.sqrt(sum(v * v for v in joint_axis))
    if norm == 0:
        return None, "축 길이가 0 이라 힌지 정합성을 점검하지 못함"

    angle = math.degrees(math.acos(min(1.0, max(-1.0, abs(dot) / norm))))
    if angle > hinge.alignment_tolerance_deg:
        return angle, (
            f"장치 힌지 축이 '{coordinate_name}' 관절 축과 {angle:.1f}° 어긋남 "
            f"(허용 {hinge.alignment_tolerance_deg:.1f}°). "
            "P1 모델은 이 어긋남이 만드는 구속력을 표현하지 않는다"
        )
    return angle, ""


def _joint_axis_in_ground(
    osim: Any, model: Any, state: Any, coordinate_name: str
) -> list[float] | None:
    """좌표를 움직이는 관절 축을 지면 좌표계 벡터로 돌려준다."""
    coordinate = model.getCoordinateSet().get(coordinate_name)
    joint = coordinate.getJoint()
    parent = joint.getParentFrame()

    axis: list[float] | None = None
    custom = osim.CustomJoint.safeDownCast(joint)
    if custom is not None:
        transform = custom.getSpatialTransform()
        for index in range(3):  # 회전 축 세 개만 본다
            transform_axis = transform.getTransformAxis(index)
            names = transform_axis.getCoordinateNames()
            owned = [names.get(i) for i in range(names.getSize())]
            if coordinate_name in owned:
                raw = transform_axis.getAxis()
                axis = [raw.get(i) for i in range(3)]
                break
    elif osim.PinJoint.safeDownCast(joint) is not None:
        axis = [0.0, 0.0, 1.0]  # PinJoint 는 관절 좌표계의 Z 축

    if axis is None:
        return None
    in_ground = parent.expressVectorInGround(state, osim.Vec3(*axis))
    return [in_ground.get(i) for i in range(3)]
