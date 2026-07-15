# -*- coding: utf-8 -*-
# ======================================================================
#  gen_cohesive_axi.py  ->  12_cohesive_axi.inp
#
#  [작업 B] 전문가 피드백 4번 반영: "요소 삭제(erosion) 대신 cohesive
#  절개"의 축대칭판(⭐). 07(평면변형)을 축대칭으로 확장.
#
#   - 니들이 축을 따라 삽입될 때 절개면은 반경 R_CUT 의 "원통면".
#     그 원통면(r=R_CUT)에 두께 0 cohesive 요소(COHAX4)를 미리 삽입.
#   - 강체 니들(둥근 첨두, 반경 R_CUT)이 하강 -> 코어(r<R_CUT) 를 밀며
#     cohesive 가 견인-분리(traction-separation) -> 요소 삭제 없이
#     "매끈한 원통형 절개(coring incision)". 질량손실/지그재그 없음.
#   - CZM 파라미터: 논문값(초기강성 ~4000 MPa/mm, 강도 ~2 MPa)을
#     마이크로 단위계로 환산해 사용.
#
#  벌크는 Abaqus 내장 Neo-Hookean -> 서브루틴 불필요(단독 실행 가능).
#  (작업 C 에서 이 cohesive 를 사용자 VUMAT 로 대체한다.)
#
#  단위: 길이 um, 응력 MPa, 힘 uN, 질량 kg, 시간 s
#  실행:  python gen_cohesive_axi.py
#     abaqus job=coh12 input=12_cohesive_axi.inp double=both cpus=4 interactive
# ======================================================================

H = 800.0            # 피부 높이 [um]
R_MAX = 600.0        # 피부 외경 [um]
R_CUT = 50.0         # 절개(원통) 반경 = 니들 반경 [um]
NC = 10              # 코어(r<R_CUT) 반경 요소수
DR_OUT0 = 5.0        # 절개면 바깥 첫 요소크기 [um]
XG = 1.18            # 외부 반경 성장비
NZ = 60              # 깊이 요소수
ZG = 1.045           # 깊이 성장비(상면 세밀 -> 하부 성김)
GAP = 20.0           # 피부 상면 위 니들 초기간격 [um]
PUSH = 500.0         # 니들 하강량 [um]

STRI = 10000         # z-행 절점 증분
OFF = 5000000        # 외부 블록 절점 오프셋
EPS = 1.0e-9

# --- CZM (논문값 -> um 단위 환산) ---
#  초기강성 k_p = 4000 MPa/mm = 4.0 MPa/um.  THICKNESS=SPECIFIED T0=1um 이면
#  E = k_p * T0 = 4.0  (traction t = E * delta/T0).
#  강도 t0 = 2 MPa (MAXS).  파단에너지 Gc = 0.01 N/mm = 10 uN/um (=MPa*um).
#  -> delta_onset = t0/k_p = 0.5 um,  delta_fail = 2 Gc/t0 = 10 um.
CZM_E = 4.0
CZM_T0 = 1.0
CZM_STR = 2.0
CZM_GC = 10.0


def _biased(total, n, ratio):
    """[0,total] 을 n구간, 첫 구간 최소(세밀) 기하급수 분할(끝점 정확)."""
    s0 = total * (ratio - 1.0) / (ratio ** n - 1.0)
    coords, c = [0.0], 0.0
    for k in range(n):
        c += s0 * ratio ** k
        coords.append(round(c, 4))
    coords[-1] = round(total, 4)
    return coords


def main(vumat=False):
    outfile = "13_cohesive_axi_vumat.inp" if vumat else "12_cohesive_axi.inp"
    # 반경 좌표
    r_core = [round(R_CUT * i / NC, 4) for i in range(NC + 1)]      # 0..R_CUT
    r_out = [round(R_CUT + d, 4) for d in _biased(R_MAX - R_CUT,
             int(round((R_MAX - R_CUT) / DR_OUT0 / 3)) + 8, XG)]    # R_CUT..R_MAX
    # 깊이 좌표: 상면(z=H) 세밀 -> 하부 성김
    dz = _biased(H, NZ, ZG)
    zs = sorted(round(H - x, 4) for x in dz)
    zs[0], zs[-1] = 0.0, round(H, 4)
    nz = len(zs) - 1
    nco, no = len(r_core), len(r_out)

    def Cid(i, j):
        return 1 + i + STRI * j

    def Oid(i, j):
        return OFF + i + STRI * j

    L = []
    w = L.append
    tag = "[C] user VUMAT CZM" if vumat else "[B] built-in CZM"
    w("*HEADING")
    w("%s : axisymmetric cohesive cutting (coring incision)" % tag)
    w("Bulk: built-in Neo-Hookean; r=%.0f um: COHAX4 traction-separation"
      % R_CUT)
    w("Units: um, uN, MPa, s")

    # ---- 절점 ----
    w("*NODE")
    for j, z in enumerate(zs):
        for i, r in enumerate(r_core):
            w("%d, %.4f, %.4f" % (Cid(i, j), r, z))
    for j, z in enumerate(zs):
        for i, r in enumerate(r_out):
            w("%d, %.4f, %.4f" % (Oid(i, j), r, z))

    # ---- 벌크 요소 (CAX4R) : 코어 + 외부 ----
    w("*ELEMENT, TYPE=CAX4R")
    e = 0
    core_el, out_el = [], []
    for j in range(nz):
        for i in range(nco - 1):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Cid(i, j), Cid(i + 1, j),
                                      Cid(i + 1, j + 1), Cid(i, j + 1)))
            core_el.append(e)
    for j in range(nz):
        for i in range(no - 1):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Oid(i, j), Oid(i + 1, j),
                                      Oid(i + 1, j + 1), Oid(i, j + 1)))
            out_el.append(e)

    # ---- Cohesive 요소 (COHAX4) : 원통면 r=R_CUT ----
    #  연결순서(07 COH2D4 와 동일 패턴): (코어우변_j, 코어우변_j+1,
    #  외부좌변_j+1, 외부좌변_j).  두께방향=반경(r) -> 분리 delta_n = 절개폭.
    w("*ELEMENT, TYPE=COHAX4")
    coh = []
    for j in range(nz):
        e += 1
        w("%d, %d, %d, %d, %d" % (e, Cid(nco - 1, j), Cid(nco - 1, j + 1),
                                  Oid(0, j + 1), Oid(0, j)))
        coh.append(e)

    w("*ELSET, ELSET=CORE, GENERATE")
    w("%d, %d, 1" % (core_el[0], core_el[-1]))
    w("*ELSET, ELSET=OUTER, GENERATE")
    w("%d, %d, 1" % (out_el[0], out_el[-1]))
    w("*ELSET, ELSET=BULK")
    w("CORE, OUTER")
    w("*ELSET, ELSET=COH, GENERATE")
    w("%d, %d, 1" % (coh[0], coh[-1]))
    w("*SURFACE, TYPE=ELEMENT, NAME=SKIN_SURF")
    w("BULK,")

    # ---- 경계 절점집합 ----
    bot = ([Cid(i, 0) for i in range(nco)] + [Oid(i, 0) for i in range(no)])
    w("*NSET, NSET=NBOT")
    line = []
    for n in bot:
        line.append(str(n))
        if len(line) == 12:
            w(", ".join(line)); line = []
    if line:
        w(", ".join(line))
    w("*NSET, NSET=NAXIS, GENERATE")
    w("%d, %d, %d" % (Cid(0, 0), Cid(0, nz), STRI))
    w("*NSET, NSET=NRIGHT, GENERATE")
    w("%d, %d, %d" % (Oid(no - 1, 0), Oid(no - 1, nz), STRI))

    # ---- 강체 니들 (둥근 첨두, 반경 R_CUT) ----
    zt = H + GAP
    w("*NODE")
    w("9999, 0.0, %.4f" % zt)
    w("*NSET, NSET=NREF")
    w("9999,")
    w("*SURFACE, TYPE=SEGMENTS, NAME=NEEDLE, FILLET RADIUS=5.0")
    w("START, %.4f, %.4f" % (R_CUT, zt + 600.0))
    w("LINE,  %.4f, %.4f" % (R_CUT, zt + R_CUT))
    w("CIRCL, 0.0, %.4f, 0.0, %.4f" % (zt, zt + R_CUT))    # 반경 R_CUT 4분원
    w("*RIGID BODY, ANALYTICAL SURFACE=NEEDLE, REF NODE=NREF")

    # ---- 재료 ----
    w("*MATERIAL, NAME=SKIN")
    w("*DENSITY")
    w("1.1e-15,")
    w("*HYPERELASTIC, NEO HOOKE")
    w("0.05, 0.5")
    w("*SOLID SECTION, ELSET=BULK, MATERIAL=SKIN")

    w("*MATERIAL, NAME=COHMAT")
    w("*DENSITY")
    w("1.1e-15,")
    if vumat:
        # 사용자 CZM: PROPS = K, t0, Gc, T0, beta  (vumat_cohesive.f)
        w("*USER MATERIAL, CONSTANTS=5")
        w("%.4g, %.4g, %.4g, %.4g, 1.0"
          % (CZM_E / CZM_T0, CZM_STR, CZM_GC, CZM_T0))
        w("*DEPVAR, DELETE=6")
        w("7")
        w("1, EPSN, normal nominal strain")
        w("2, EPSS1, shear1 nominal strain")
        w("3, EPSS2, shear2 nominal strain")
        w("4, DMAX, max effective separation")
        w("5, SDEG, damage")
        w("6, STATUS, delete flag")
        w("7, DELM, effective separation")
    else:
        w("*ELASTIC, TYPE=TRACTION")
        w("%.4g, %.4g, %.4g" % (CZM_E, CZM_E, CZM_E))
        w("*DAMAGE INITIATION, CRITERION=MAXS")
        w("%.4g, %.4g, %.4g" % (CZM_STR, CZM_STR, CZM_STR))
        w("*DAMAGE EVOLUTION, TYPE=ENERGY")
        w("%.4g," % CZM_GC)
    w("*COHESIVE SECTION, ELSET=COH, MATERIAL=COHMAT,"
      " RESPONSE=TRACTION SEPARATION, THICKNESS=SPECIFIED")
    w("%.4g," % CZM_T0)

    # ---- 접촉 상호작용(모델 데이터: 첫 *STEP 앞) ----
    w("*SURFACE INTERACTION, NAME=IPROP")
    w("*FRICTION")
    w("0.1,")
    w("*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=HARD")

    # ---- 경계 / 스텝 ----
    w("*BOUNDARY")
    w("NBOT, 2, 2")
    w("NAXIS, 1, 1")
    w("NRIGHT, 1, 1")
    w("NREF, 1, 1")
    w("NREF, 6, 6")
    w("*AMPLITUDE, NAME=PUSH, DEFINITION=SMOOTH STEP")
    w("0.0, 0.0, 0.02, 1.0")
    w("*STEP, NAME=CUT")
    w("*DYNAMIC, EXPLICIT")
    w(", 0.02")
    w("*FIXED MASS SCALING, DT=2.0e-7, TYPE=BELOW MIN")
    w("*BOUNDARY, AMPLITUDE=PUSH")
    w("NREF, 2, 2, %.1f" % (-PUSH))
    w("*CONTACT")
    w("*CONTACT INCLUSIONS, ALL EXTERIOR")
    w("*CONTACT INCLUSIONS")
    w("NEEDLE, SKIN_SURF")
    w("*CONTACT PROPERTY ASSIGNMENT")
    w(" ,  , IPROP")
    w("*OUTPUT, FIELD, NUMBER INTERVAL=25")
    w("*ELEMENT OUTPUT, ELSET=BULK")
    w("S, LE")
    w("*ELEMENT OUTPUT, ELSET=COH")
    w("SDV, STATUS" if vumat else "SDEG, STATUS")
    w("*NODE OUTPUT")
    w("U, V")
    w("*OUTPUT, HISTORY, TIME INTERVAL=1.0e-4")
    w("*NODE OUTPUT, NSET=NREF")
    w("U2, V2, RF2")
    w("*ENERGY OUTPUT")
    w("ALLIE, ALLKE, ALLSE, ALLDMD")
    w("*END STEP")

    with open(outfile, "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote %s  (%s)" % (outfile, "user VUMAT" if vumat else "built-in"))
    print("  core elems=%d, outer elems=%d, cohesive(COHAX4)=%d"
          % (len(core_el), len(out_el), len(coh)))
    print("  r-core=%d, r-out=%d, z-rows=%d ; R_CUT=%.0f um"
          % (nco, no, nz, R_CUT))
    print("  CZM: k_p=%.3g MPa/um, strength=%.3g MPa, Gc=%.3g uN/um"
          % (CZM_E / CZM_T0, CZM_STR, CZM_GC))


if __name__ == "__main__":
    main(vumat=False)     # -> 12_cohesive_axi.inp   (Abaqus 내장 CZM)
    main(vumat=True)      # -> 13_cohesive_axi_vumat.inp (사용자 VUMAT)
