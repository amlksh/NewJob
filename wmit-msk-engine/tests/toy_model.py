"""통합 테스트용 토이 모델.

실제 인체 모델(Rajagopal 등)은 라이선스 대장을 채우기 전에는 저장소에 둘 수
없고(CLAUDE.md §4), 크기 때문에 테스트에도 맞지 않는다. 대신 파이프라인과
OpenSim 사이의 계약을 확인하기에 충분한 최소 모델을 코드로 만든다.

이 모델로 확인할 수 있는 것: 경로·파일 이름 규약, 단계 간 연결, 장치 결합의
역학적 효과. 확인할 수 **없는** 것: 해석 정확도, 실제 보행 데이터 재현.
후자는 Grand Challenge 데이터로 하는 G1 항목이다.

무릎(knee) 한 자유도에 근육 하나와 약한 reserve 액추에이터를 둔다.
reserve 를 약하게(2 N·m) 두는 것은 실제 모델의 관행과 같다 — 강하면 Static
Optimization 이 근육 대신 reserve 로 모멘트를 내고, 근육력이 0 으로 나온다.
"""

from __future__ import annotations

import math
from pathlib import Path

FRAMES = 21
RATE = 100.0
MARKERS = ("M_THIGH_A", "M_THIGH_B", "M_SHANK_A", "M_SHANK_B")

#: 모델 안의 이름. Case YAML 과 장치 정의가 이 이름들을 가리킨다.
THIGH_BODY = "thigh"
SHANK_BODY = "shank"
KNEE_JOINT = "knee"
KNEE_COORDINATE = "knee_flex"
MUSCLE = "knee_musc"


def build_model(path: Path):
    """토이 모델을 만들어 저장하고 (model, state) 를 돌려준다."""
    import opensim as osim

    model = osim.Model()
    model.setName("toy")
    model.setGravity(osim.Vec3(0, -9.80665, 0))

    thigh = osim.Body(THIGH_BODY, 5.0, osim.Vec3(0), osim.Inertia(0.1, 0.1, 0.1))
    shank = osim.Body(SHANK_BODY, 3.0, osim.Vec3(0), osim.Inertia(0.05, 0.05, 0.05))
    model.addBody(thigh)
    model.addBody(shank)

    hip = osim.PinJoint("hip", model.getGround(), osim.Vec3(0, 1, 0), osim.Vec3(0),
                        thigh, osim.Vec3(0, 0.2, 0), osim.Vec3(0))
    knee = osim.PinJoint(KNEE_JOINT, thigh, osim.Vec3(0, -0.2, 0), osim.Vec3(0),
                         shank, osim.Vec3(0, 0.2, 0), osim.Vec3(0))
    hip.updCoordinate().setName("hip_flex")
    knee.updCoordinate().setName(KNEE_COORDINATE)
    model.addJoint(hip)
    model.addJoint(knee)

    placements = {
        "M_THIGH_A": (thigh, osim.Vec3(0.05, 0.1, 0.0)),
        "M_THIGH_B": (thigh, osim.Vec3(-0.05, -0.1, 0.02)),
        "M_SHANK_A": (shank, osim.Vec3(0.05, 0.1, 0.0)),
        "M_SHANK_B": (shank, osim.Vec3(-0.05, -0.1, 0.02)),
    }
    for name, (body, loc) in placements.items():
        model.addMarker(osim.Marker(name, body, loc))

    # 근육 경로 길이가 약 0.40 m 이므로 optimal fiber + tendon slack 을
    # 거기에 맞춘다. 맞추지 않으면 근육이 작동 범위 밖으로 늘어나 활성
    # 힘이 0 이 되고, 근육력 출력이 의미를 잃는다.
    muscle = osim.Millard2012EquilibriumMuscle(MUSCLE, 500.0, 0.15, 0.24, 0.0)
    muscle.addNewPathPoint("p1", thigh, osim.Vec3(0.04, 0.05, 0.0))
    muscle.addNewPathPoint("p2", shank, osim.Vec3(0.04, 0.05, 0.0))
    model.addForce(muscle)

    for coordinate in ("hip_flex", KNEE_COORDINATE):
        actuator = osim.CoordinateActuator(coordinate)
        actuator.setName(f"reserve_{coordinate}")
        actuator.setOptimalForce(2.0)
        model.addForce(actuator)

    state = model.initSystem()
    path.parent.mkdir(parents=True, exist_ok=True)
    model.printToXML(str(path))
    return model, state


def write_static_markers(path: Path, model, state) -> None:
    """정적 trial — 한 자세를 그대로 유지하는 마커 파일.

    Scaling 은 정적 자세를 전제로 한다. 움직이는 trial 을 정적 trial 로 쓰면
    MarkerPlacer 가 평균 자세로 마커를 옮겨, 스케일 결과가 원본 모델과
    달라진다. 실제 계측에서도 정적 trial 은 따로 찍는다.
    """
    _write_trc(path, model, state, moving=False)


def write_markers(path: Path, model, state) -> None:
    """모델 자신의 순기구학으로 마커 궤적을 만든다.

    측정 잡음이 없으므로 IK 마커 오차는 0 에 가까워야 한다.
    크게 나오면 파이프라인 쪽이 잘못된 것이다.
    """
    _write_trc(path, model, state, moving=True)


def _write_trc(path: Path, model, state, *, moving: bool) -> None:
    rows = []
    for index in range(FRAMES):
        t = index / RATE
        hip = 0.20 * math.sin(2 * math.pi * t) if moving else 0.0
        knee = 0.30 * math.sin(2 * math.pi * t + 0.5) if moving else 0.0
        model.updCoordinateSet().get("hip_flex").setValue(state, hip)
        model.updCoordinateSet().get(KNEE_COORDINATE).setValue(state, knee)
        model.realizePosition(state)
        coords: list[float] = []
        for name in MARKERS:
            point = model.getMarkerSet().get(name).getLocationInGround(state)
            coords += [point.get(0), point.get(1), point.get(2)]
        rows.append((index + 1, t, coords))

    lines = [
        f"PathFileType\t4\t(X/Y/Z)\t{path.name}",
        "DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\t"
        "OrigDataRate\tOrigDataStartFrame\tOrigNumFrames",
        f"{RATE}\t{RATE}\t{FRAMES}\t{len(MARKERS)}\tm\t{RATE}\t1\t{FRAMES}",
        "Frame#\tTime\t" + "\t\t\t".join(MARKERS),
        "\t\t" + "\t".join(f"X{i + 1}\tY{i + 1}\tZ{i + 1}" for i in range(len(MARKERS))),
    ]
    for index, t, coords in rows:
        lines.append("\t".join([str(index), f"{t:.5f}"] + [f"{c:.6f}" for c in coords]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_scale_template(path: Path, repo_template: Path) -> Path:
    """저장소의 scale 템플릿에 토이 모델용 측정·마커 과제를 채워 넣는다.

    저장소 템플릿은 MeasurementSet 과 MarkerPlacer 의 IKTaskSet 이 비어 있는
    '채워 쓰는 자리' 다. 모델·마커셋마다 내용이 다르기 때문이다. 여기서는
    토이 모델에 맞는 내용을 주입해 **템플릿의 자리표시자 배선까지 포함한**
    ScaleTool 실행을 확인한다.

    마커 궤적을 모델 자신에게서 만들었으므로, 제대로 돌면 스케일 계수는
    1 에 가까워야 한다. 그것이 이 단계의 검증 기준이 된다.
    """
    measurements = f"""
                <Measurement name="thigh_length">
                    <apply>true</apply>
                    <MarkerPairSet>
                        <objects>
                            <MarkerPair name="thigh_pair">
                                <markers> M_THIGH_A M_THIGH_B </markers>
                            </MarkerPair>
                        </objects>
                        <groups />
                    </MarkerPairSet>
                    <BodyScaleSet>
                        <objects>
                            <BodyScale name="{THIGH_BODY}">
                                <axes> X Y Z </axes>
                            </BodyScale>
                        </objects>
                        <groups />
                    </BodyScaleSet>
                </Measurement>
                <Measurement name="shank_length">
                    <apply>true</apply>
                    <MarkerPairSet>
                        <objects>
                            <MarkerPair name="shank_pair">
                                <markers> M_SHANK_A M_SHANK_B </markers>
                            </MarkerPair>
                        </objects>
                        <groups />
                    </MarkerPairSet>
                    <BodyScaleSet>
                        <objects>
                            <BodyScale name="{SHANK_BODY}">
                                <axes> X Y Z </axes>
                            </BodyScale>
                        </objects>
                        <groups />
                    </BodyScaleSet>
                </Measurement>
"""
    tasks = "".join(
        f"""
                    <IKMarkerTask name="{marker}">
                        <apply>true</apply>
                        <weight>1</weight>
                    </IKMarkerTask>"""
        for marker in MARKERS
    )

    text = repo_template.read_text(encoding="utf-8")
    before = text
    text = text.replace(
        "<MeasurementSet>\n                <objects />",
        f"<MeasurementSet>\n                <objects>{measurements}                </objects>",
        1,
    )
    text = text.replace(
        "<IKTaskSet>\n                <objects />",
        f"<IKTaskSet>\n                <objects>{tasks}\n                </objects>",
        1,
    )
    if text == before:
        raise AssertionError(
            "scale 템플릿 구조가 바뀌어 측정·마커 과제를 주입하지 못했다"
        )
    path.write_text(text, encoding="utf-8")
    return path


def write_case_yaml(
    path: Path,
    model_path: Path,
    marker_path: Path,
    templates: Path,
    *,
    scale_template: Path | None = None,
    static_trial: Path | None = None,
    device_spec: Path | None = None,
) -> Path:
    """토이 모델을 쓰는 Case YAML."""
    path.write_text(
        "\n".join(
            [
                "name: toy_case",
                "subject:",
                "  height_m: 1.75",
                "  mass_kg: 70.0",
                f"  marker_file: {marker_path}",
                *([f"  static_trial: {static_trial}"] if static_trial else []),
                f"model_file: {model_path}",
                *([f"device: {device_spec}"] if device_spec else []),
                "templates:",
                f"  scale: {scale_template or templates / 'scale_setup.xml'}",
                f"  ik: {templates / 'ik_setup.xml'}",
                f"  id: {templates / 'id_setup.xml'}",
                f"  so: {templates / 'so_setup.xml'}",
                f"  jr: {templates / 'jr_setup.xml'}",
                f"joint_reaction_frame: {SHANK_BODY}",
                f"joint_reaction_joints: [{KNEE_JOINT}]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


DEVICE_NAME = "toy_brace"
DEVICE_MASS_KG = 0.80


def write_device_yaml(
    path: Path,
    *,
    hinge_axis: tuple[float, float, float] = (0.0, 0.0, 1.0),
    actuation_mode: str = "assistive",
    max_torque_nm: float = 20.0,
    host_body: str = THIGH_BODY,
    cad_revision: str = "r0",
) -> Path:
    """토이 모델에 맞는 무릎 보조기 정의.

    값은 검증용이며 실제 기기에서 온 것이 아니다. CAD 값이 들어오면
    그대로 대체된다 — 스키마는 같다.
    """
    actuation = {
        "assistive": (
            f"actuation: {{mode: assistive, coordinate: {KNEE_COORDINATE}, "
            f"max_torque_nm: {max_torque_nm}}}"
        ),
        "none": "actuation: {mode: none}",
    }[actuation_mode]

    path.write_text(
        f"""name: {DEVICE_NAME}
source: {{cad_file: toy_brace.step, revision: {cad_revision}}}
segments:
  - name: thigh_cuff
    mass_kg: 0.45
    center_of_mass: [0.0, -0.05, 0.0]
    inertia: [0.0021, 0.0008, 0.0021, 0.0, 0.0, 0.0]
    attachment: {{host_body: {host_body}, location: [0.0, -0.05, 0.03]}}
  - name: shank_cuff
    mass_kg: 0.35
    center_of_mass: [0.0, 0.05, 0.0]
    inertia: [0.0015, 0.0006, 0.0015, 0.0, 0.0, 0.0]
    attachment: {{host_body: {SHANK_BODY}, location: [0.0, 0.05, 0.03]}}
hinge:
  axis: [{hinge_axis[0]}, {hinge_axis[1]}, {hinge_axis[2]}]
  expressed_in: {THIGH_BODY}
  location: [0.0, -0.2, 0.0]
  alignment_tolerance_deg: 10.0
rom:
  coordinate: {KNEE_COORDINATE}
  min_deg: -5.0
  max_deg: 110.0
  stiffness_nm_per_deg: 5.0
  damping_nm_s_per_deg: 0.5
{actuation}
""",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# 회귀 기준선용 기준 케이스
#
# 기준선을 만드는 스크립트(scripts/refresh_toy_baseline.py)와 그것을 검증하는
# 테스트가 **같은 정의**를 써야 한다. 정의가 둘로 갈라지면 기준선이 검증하는
# 대상과 달라져 회귀를 잡지 못한다.
# ---------------------------------------------------------------------------

REFERENCE_CASES: dict[str, tuple[str, bool]] = {
    "toy_human": ("인체만 — Scale → IK → ID → SO → JR", False),
    "toy_device": ("무릎 보조기 착용 — Scale → Device → IK → ID → SO → JR", True),
}


def build_reference_inputs(workdir: Path, repo_root: Path) -> dict:
    """기준 케이스가 쓰는 입력 일체."""
    templates = repo_root / "configs" / "templates"
    model_path = workdir / "toy.osim"
    model, state = build_model(model_path)

    gait = workdir / "gait.trc"
    static = workdir / "static.trc"
    write_markers(gait, model, state)
    write_static_markers(static, model, state)

    return {
        "templates": templates,
        "model": model_path,
        "gait": gait,
        "static": static,
        "scale_template": write_scale_template(
            workdir / "scale_toy.xml", templates / "scale_setup.xml"
        ),
        "device": write_device_yaml(workdir / "device.yaml"),
    }


def run_reference_case(name: str, with_device: bool, inputs: dict, workdir: Path):
    """기준 케이스 하나를 끝까지 실행한다."""
    from msk_engine.pipeline import CaseSpec, run_case

    case_file = write_case_yaml(
        workdir / f"{name}.yaml",
        inputs["model"],
        inputs["gait"],
        inputs["templates"],
        scale_template=inputs["scale_template"],
        static_trial=inputs["static"],
        device_spec=inputs["device"] if with_device else None,
    )
    result = run_case(CaseSpec.from_yaml(case_file), runs_root=workdir / f"runs_{name}")
    if result.status != "ok":
        raise RuntimeError(f"{name}: 해석이 '{result.status}' 로 끝났다")
    return result
