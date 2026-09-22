"""의료기기 파라미터 정의 (CAD → OpenSim 입력 인터페이스).

이 모듈의 dataclass 들이 곧 **CAD 에서 넘어오는 값의 계약**이다.
CAD 도구를 직접 읽지 않는 이유는 두 가지다.

  1. CAD 포맷은 과제 중간에 바뀔 수 있지만, 해석에 필요한 물리량
     (질량, 관성, 부착점, 힌지 축, ROM, 구동 조건)은 바뀌지 않는다.
  2. 어떤 값이 어느 리비전에서 왔는지 `source` 에 남겨야 V&V 추적이 된다.

따라서 CAD 쪽에서 이 스키마에 맞춘 YAML 을 내보내고, 엔진은 그 YAML 만 읽는다.
스키마 설명은 `docs/interfaces/cad_device_parameters.md` 에 있다.

단위 규약 (OpenSim 내부 단위에 맞춘다):
  - 길이 m, 질량 kg, 관성 kg·m^2, 힘 N, 모멘트 N·m
  - **각도는 이 파일에서만 deg 로 받고** 모델에 넣을 때 rad 로 바꾼다.
    ROM 은 사람이 deg 로 말하고 CAD 도 deg 로 표기하므로, 변환 지점을
    한 곳(`to_radians`)으로 몰아 둔다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from msk_engine.errors import ConfigurationError

Vec3 = tuple[float, float, float]

#: 장치 구동 방식. P1 에서 구현된 것과 아닌 것을 여기서 구분한다 (ADR-0004).
ACTUATION_MODES = ("none", "assistive", "prescribed_torque", "passive")
#: 스키마에는 있으나 P1 에서 구현하지 않는 방식. 조용히 무시하지 않고 거절한다.
DEFERRED_ACTUATION_MODES = ("prescribed_motion",)


def _require(data: dict[str, Any], key: str, where: str) -> Any:
    if key not in data or data[key] is None:
        raise ConfigurationError(f"{where}: 필수 항목 '{key}' 없음")
    return data[key]


def _as_float(value: Any, where: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ConfigurationError(f"{where}: 숫자가 아님 — {value!r}") from None


def _as_vec3(value: Any, where: str) -> Vec3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ConfigurationError(f"{where}: [x, y, z] 세 성분이어야 함 — {value!r}")
    return (_as_float(value[0], where), _as_float(value[1], where), _as_float(value[2], where))


def _check_keys(data: dict[str, Any], allowed: tuple[str, ...], where: str) -> None:
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise ConfigurationError(
            f"{where}: 모르는 항목 {', '.join(unknown)} "
            f"(허용: {', '.join(sorted(allowed))}). 오타이거나 스키마가 바뀐 것이다"
        )


#: 미정을 나타내는 표기. 값으로 인정하지 않는다.
_PLACEHOLDERS = {"", "tbd", "todo", "미정", "none", "n/a"}


def _is_filled(value: str) -> bool:
    return value.strip().lower() not in _PLACEHOLDERS


def _as_mapping(value: Any, where: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where}: 매핑이어야 함 — {type(value).__name__}")
    return dict(value)


@dataclass(frozen=True)
class CadSource:
    """이 파라미터가 어느 CAD 산출물에서 나왔는지.

    값 자체보다 출처가 없는 것이 더 위험하다. 결과를 인용할 때 어느
    리비전의 기기였는지 말할 수 없으면 V&V 증거가 되지 않는다.
    """

    cad_file: str = ""
    revision: str = ""
    exported_by: str = ""
    exported_at: str = ""
    notes: str = ""

    @classmethod
    def parse(cls, data: Any) -> CadSource:
        where = "source"
        data = _as_mapping(data, where)
        _check_keys(data, ("cad_file", "revision", "exported_by", "exported_at", "notes"), where)
        return cls(
            cad_file=str(data.get("cad_file", "")),
            revision=str(data.get("revision", "")),
            exported_by=str(data.get("exported_by", "")),
            exported_at=str(data.get("exported_at", "")),
            notes=str(data.get("notes", "")),
        )

    @property
    def is_traceable(self) -> bool:
        """CAD 파일과 리비전이 **실제로** 적혀 있는지.

        이 저장소는 미정을 TBD 로 적는다 (ADR-0003 과 같은 규약).
        TBD 를 값으로 인정하면 출처가 없는 기기가 추적 가능한 것처럼
        보이므로, 빈 값과 똑같이 취급한다.
        """
        return bool(_is_filled(self.cad_file) and _is_filled(self.revision))


@dataclass(frozen=True)
class Attachment:
    """장치 세그먼트가 인체 body 에 붙는 위치와 자세.

    location 은 host_body 좌표계 기준이며 단위는 m 이다.
    P1 에서는 용접(WeldJoint) 으로만 붙인다 — 상대운동 없는 밴드·커프 가정.
    스트랩의 유연성이나 미끄러짐은 반영하지 않는다 (ADR-0004 적용 한계).
    """

    host_body: str
    location: Vec3 = (0.0, 0.0, 0.0)
    orientation_deg: Vec3 = (0.0, 0.0, 0.0)

    @classmethod
    def parse(cls, data: Any, where: str) -> Attachment:
        data = _as_mapping(data, where)
        _check_keys(data, ("host_body", "location", "orientation_deg"), where)
        return cls(
            host_body=str(_require(data, "host_body", where)),
            location=_as_vec3(data.get("location", [0.0, 0.0, 0.0]), f"{where}.location"),
            orientation_deg=_as_vec3(
                data.get("orientation_deg", [0.0, 0.0, 0.0]), f"{where}.orientation_deg"
            ),
        )

    @property
    def orientation_rad(self) -> Vec3:
        return tuple(math.radians(a) for a in self.orientation_deg)  # type: ignore[return-value]


@dataclass(frozen=True)
class DeviceSegment:
    """장치의 강체 세그먼트 하나 (커프, 링크, 액추에이터 하우징 등).

    질량과 관성은 해석 결과에 직접 영향을 준다. 장치를 달면 하지 관성이
    늘어 관절 모멘트가 달라지므로, CAD 값 없이 0 으로 두면 안 된다.
    """

    name: str
    mass_kg: float
    attachment: Attachment
    center_of_mass: Vec3 = (0.0, 0.0, 0.0)
    #: Ixx, Iyy, Izz, Ixy, Ixz, Iyz — 질량중심 기준, 세그먼트 좌표계 (kg·m^2)
    inertia: tuple[float, float, float, float, float, float] = (0.0,) * 6

    @classmethod
    def parse(cls, data: Any, index: int) -> DeviceSegment:
        where = f"segments[{index}]"
        data = _as_mapping(data, where)
        _check_keys(
            data, ("name", "mass_kg", "attachment", "center_of_mass", "inertia"), where
        )
        name = str(_require(data, "name", where)).strip()
        if not name:
            raise ConfigurationError(f"{where}.name: 비어 있음")

        mass = _as_float(_require(data, "mass_kg", where), f"{where}.mass_kg")
        if mass <= 0:
            raise ConfigurationError(
                f"{where}.mass_kg: 0 보다 커야 함 — {mass}. "
                "질량을 모르면 CAD 에서 받아 채울 것, 0 으로 두지 말 것"
            )

        inertia_raw = data.get("inertia", [0.0] * 6)
        if not isinstance(inertia_raw, (list, tuple)) or len(inertia_raw) != 6:
            raise ConfigurationError(
                f"{where}.inertia: [Ixx, Iyy, Izz, Ixy, Ixz, Iyz] 여섯 성분이어야 함"
            )
        inertia = tuple(_as_float(v, f"{where}.inertia") for v in inertia_raw)
        for label, value in zip(("Ixx", "Iyy", "Izz"), inertia[:3], strict=False):
            if value < 0:
                raise ConfigurationError(f"{where}.inertia.{label}: 음수일 수 없음 — {value}")

        return cls(
            name=name,
            mass_kg=mass,
            attachment=Attachment.parse(
                _require(data, "attachment", where), f"{where}.attachment"
            ),
            center_of_mass=_as_vec3(
                data.get("center_of_mass", [0.0, 0.0, 0.0]), f"{where}.center_of_mass"
            ),
            inertia=inertia,  # type: ignore[arg-type]
        )

    @property
    def has_inertia(self) -> bool:
        return any(v != 0.0 for v in self.inertia[:3])


@dataclass(frozen=True)
class Hinge:
    """장치 힌지 축 (CAD 기준).

    P1 에서 장치는 인체에 용접되므로 이 축이 새 자유도를 만들지는 않는다.
    대신 **인체 관절 축과 얼마나 어긋났는지 점검**하는 데 쓴다.
    축이 크게 어긋난 장치는 착용자에게 구속력을 만들지만 P1 모델은
    그것을 표현하지 않으므로, 어긋남을 경고로 남겨 해석 한계를 분명히 한다.

    Tier 2(장치가 자기 자유도를 갖는 모델)에서는 이 축이 실제 관절 축이 된다.
    """

    axis: Vec3
    expressed_in: str
    location: Vec3 = (0.0, 0.0, 0.0)
    alignment_tolerance_deg: float = 10.0

    @classmethod
    def parse(cls, data: Any) -> Hinge:
        where = "hinge"
        data = _as_mapping(data, where)
        _check_keys(
            data, ("axis", "expressed_in", "location", "alignment_tolerance_deg"), where
        )
        axis = _as_vec3(_require(data, "axis", where), f"{where}.axis")
        if math.isclose(math.sqrt(sum(a * a for a in axis)), 0.0, abs_tol=1e-12):
            raise ConfigurationError(f"{where}.axis: 영벡터일 수 없음")
        tolerance = _as_float(
            data.get("alignment_tolerance_deg", 10.0), f"{where}.alignment_tolerance_deg"
        )
        if tolerance < 0:
            raise ConfigurationError(f"{where}.alignment_tolerance_deg: 음수일 수 없음")
        return cls(
            axis=axis,
            expressed_in=str(_require(data, "expressed_in", where)),
            location=_as_vec3(data.get("location", [0.0, 0.0, 0.0]), f"{where}.location"),
            alignment_tolerance_deg=tolerance,
        )

    @property
    def unit_axis(self) -> Vec3:
        norm = math.sqrt(sum(a * a for a in self.axis))
        return tuple(a / norm for a in self.axis)  # type: ignore[return-value]


@dataclass(frozen=True)
class RangeOfMotion:
    """장치가 물리적으로 허용하는 가동범위.

    OpenSim 의 CoordinateLimitForce 로 표현한다. 딱딱한 정지면이 아니라
    강성·감쇠를 가진 힘이므로, 값은 CAD 스토퍼의 실제 특성에서 와야 한다.
    임의의 큰 수를 넣으면 적분이 불안정해지고 결과가 조용히 나빠진다.
    """

    coordinate: str
    min_deg: float
    max_deg: float
    stiffness_nm_per_deg: float
    damping_nm_s_per_deg: float = 0.0
    transition_deg: float = 2.0

    @classmethod
    def parse(cls, data: Any) -> RangeOfMotion:
        where = "rom"
        data = _as_mapping(data, where)
        _check_keys(
            data,
            (
                "coordinate", "min_deg", "max_deg", "stiffness_nm_per_deg",
                "damping_nm_s_per_deg", "transition_deg",
            ),
            where,
        )
        min_deg = _as_float(_require(data, "min_deg", where), f"{where}.min_deg")
        max_deg = _as_float(_require(data, "max_deg", where), f"{where}.max_deg")
        if max_deg <= min_deg:
            raise ConfigurationError(
                f"{where}: max_deg({max_deg}) 가 min_deg({min_deg}) 보다 커야 함"
            )
        stiffness = _as_float(
            _require(data, "stiffness_nm_per_deg", where), f"{where}.stiffness_nm_per_deg"
        )
        if stiffness <= 0:
            raise ConfigurationError(
                f"{where}.stiffness_nm_per_deg: 0 보다 커야 함 — "
                "스토퍼 강성을 모르면 ROM 제한을 걸지 말 것"
            )
        transition = _as_float(data.get("transition_deg", 2.0), f"{where}.transition_deg")
        if transition <= 0:
            raise ConfigurationError(f"{where}.transition_deg: 0 보다 커야 함")
        return cls(
            coordinate=str(_require(data, "coordinate", where)),
            min_deg=min_deg,
            max_deg=max_deg,
            stiffness_nm_per_deg=stiffness,
            damping_nm_s_per_deg=_as_float(
                data.get("damping_nm_s_per_deg", 0.0), f"{where}.damping_nm_s_per_deg"
            ),
            transition_deg=transition,
        )


@dataclass(frozen=True)
class Actuation:
    """장치 구동 조건.

    mode 별 의미:
      none              구동 없음 — 질량·관성·ROM 만 반영되는 수동 보조기
      assistive         Static Optimization 이 max_torque_nm 한도 안에서
                        장치 토크를 근육과 함께 분배한다. "이 동작을 도우려면
                        장치가 몇 N·m 를 내야 하는가" 를 묻는 해석이다.
      prescribed_torque 시간에 따른 토크가 이미 정해져 있다 (torque_file).
      passive           스프링·댐퍼로 표현되는 수동 요소.

    prescribed_motion(장치가 관절각을 강제로 끌고 가는 CPM 방식)은 P1 범위가
    아니다. 인체 좌표를 강제하면 IK 결과와 충돌하고, 장치가 자기 자유도를 가져야
    제대로 표현된다 (ADR-0004 Tier 2). 스키마에는 두되 실행은 거절한다.
    """

    mode: str = "none"
    coordinate: str = ""
    max_torque_nm: float | None = None
    torque_file: Path | None = None
    stiffness_nm_per_rad: float | None = None
    damping_nm_s_per_rad: float | None = None
    rest_angle_deg: float = 0.0

    @classmethod
    def parse(cls, data: Any, base_dir: Path) -> Actuation:
        where = "actuation"
        data = _as_mapping(data, where)
        _check_keys(
            data,
            (
                "mode", "coordinate", "max_torque_nm", "torque_file",
                "stiffness_nm_per_rad", "damping_nm_s_per_rad", "rest_angle_deg",
            ),
            where,
        )
        mode = str(data.get("mode", "none")).strip()
        if mode in DEFERRED_ACTUATION_MODES:
            raise ConfigurationError(
                f"{where}.mode '{mode}' 는 P1 에서 구현하지 않는다. "
                "인체 좌표를 강제하면 IK 결과와 충돌하며, 장치가 자기 자유도를 "
                "가져야 제대로 표현된다 — ADR-0004 Tier 2 참조"
            )
        if mode not in ACTUATION_MODES:
            raise ConfigurationError(
                f"{where}.mode: 알 수 없는 값 '{mode}' "
                f"(가능: {', '.join(ACTUATION_MODES)})"
            )

        coordinate = str(data.get("coordinate", "")).strip()
        if mode != "none" and not coordinate:
            raise ConfigurationError(f"{where}.coordinate: mode '{mode}' 에는 필수")

        torque_file = data.get("torque_file")
        resolved: Path | None = None
        if torque_file:
            path = Path(str(torque_file)).expanduser()
            resolved = path if path.is_absolute() else (base_dir / path)

        spec = cls(
            mode=mode,
            coordinate=coordinate,
            max_torque_nm=(
                _as_float(data["max_torque_nm"], f"{where}.max_torque_nm")
                if data.get("max_torque_nm") is not None
                else None
            ),
            torque_file=resolved,
            stiffness_nm_per_rad=(
                _as_float(data["stiffness_nm_per_rad"], f"{where}.stiffness_nm_per_rad")
                if data.get("stiffness_nm_per_rad") is not None
                else None
            ),
            damping_nm_s_per_rad=(
                _as_float(data["damping_nm_s_per_rad"], f"{where}.damping_nm_s_per_rad")
                if data.get("damping_nm_s_per_rad") is not None
                else None
            ),
            rest_angle_deg=_as_float(data.get("rest_angle_deg", 0.0), f"{where}.rest_angle_deg"),
        )
        spec._check_mode_requirements(where)
        return spec

    def _check_mode_requirements(self, where: str) -> None:
        if self.mode == "assistive":
            if self.max_torque_nm is None or self.max_torque_nm <= 0:
                raise ConfigurationError(
                    f"{where}.max_torque_nm: assistive 에는 0 보다 큰 값이 필요하다. "
                    "장치가 낼 수 있는 최대 토크는 해석 결과의 상한이 되므로 "
                    "CAD·사양서에서 받아 채울 것"
                )
        elif self.mode == "prescribed_torque":
            if self.torque_file is None:
                raise ConfigurationError(
                    f"{where}.torque_file: prescribed_torque 에는 필수 "
                    "(time, torque 두 열을 가진 STO/MOT)"
                )
        elif self.mode == "passive" and self.stiffness_nm_per_rad is None:
            raise ConfigurationError(f"{where}.stiffness_nm_per_rad: passive 에는 필수")


@dataclass(frozen=True)
class DeviceSpec:
    """의료기기 하나의 해석용 파라미터 전체."""

    name: str
    segments: tuple[DeviceSegment, ...]
    description: str = ""
    source: CadSource = field(default_factory=CadSource)
    hinge: Hinge | None = None
    rom: RangeOfMotion | None = None
    actuation: Actuation = field(default_factory=Actuation)
    spec_file: Path | None = None

    TOP_LEVEL_KEYS = (
        "name", "description", "source", "segments", "hinge", "rom", "actuation",
    )

    @classmethod
    def parse(cls, data: Any, base_dir: Path, spec_file: Path | None = None) -> DeviceSpec:
        data = _as_mapping(data, "device")
        if not data:
            raise ConfigurationError("device: 파일이 비어 있음")
        _check_keys(data, cls.TOP_LEVEL_KEYS, "device")

        segments_raw = _require(data, "segments", "device")
        if isinstance(segments_raw, (str, bytes)) or not isinstance(segments_raw, list):
            raise ConfigurationError("device.segments: 목록이어야 함")
        if not segments_raw:
            raise ConfigurationError(
                "device.segments: 최소 한 개 필요 — 질량 없는 장치는 해석에 의미가 없다"
            )
        segments = tuple(DeviceSegment.parse(s, i) for i, s in enumerate(segments_raw))

        names = [s.name for s in segments]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ConfigurationError(f"device.segments: 이름 중복 — {', '.join(duplicates)}")

        return cls(
            name=str(_require(data, "name", "device")).strip(),
            description=str(data.get("description", "")),
            source=CadSource.parse(data.get("source")),
            segments=segments,
            hinge=Hinge.parse(data["hinge"]) if data.get("hinge") else None,
            rom=RangeOfMotion.parse(data["rom"]) if data.get("rom") else None,
            actuation=Actuation.parse(data.get("actuation"), base_dir),
            spec_file=spec_file,
        )

    @property
    def total_mass_kg(self) -> float:
        return sum(s.mass_kg for s in self.segments)

    @property
    def host_bodies(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for segment in self.segments:
            seen.setdefault(segment.attachment.host_body, None)
        return tuple(seen)

    def warnings(self) -> list[str]:
        """멈출 정도는 아니지만 결과 해석에 영향을 주는 것들."""
        notes: list[str] = []
        if not self.source.is_traceable:
            notes.append(
                f"장치 '{self.name}' 의 CAD 출처(cad_file, revision)가 비어 있음 — "
                "결과를 증거로 인용하려면 채울 것"
            )
        for segment in self.segments:
            if not segment.has_inertia:
                notes.append(
                    f"세그먼트 '{segment.name}' 의 관성이 0 — "
                    "질량만 반영되고 회전 관성은 무시된다"
                )
        if self.rom is None:
            notes.append(f"장치 '{self.name}' 에 ROM 제한이 없음 — 가동범위를 구속하지 않는다")
        if self.hinge is None:
            notes.append(
                f"장치 '{self.name}' 에 힌지 축이 없음 — 인체 관절 축과의 정합성을 점검하지 않는다"
            )
        return notes


def load_device_spec(path: str | Path) -> DeviceSpec:
    """장치 파라미터 YAML 을 읽어 검증된 DeviceSpec 을 돌려준다."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise ConfigurationError(f"장치 정의 파일 없음: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"{path}: YAML 을 읽을 수 없음: {exc}") from exc
    try:
        return DeviceSpec.parse(raw, path.resolve().parent, spec_file=path.resolve())
    except ConfigurationError as exc:
        raise ConfigurationError(f"{path}: {exc}") from None
