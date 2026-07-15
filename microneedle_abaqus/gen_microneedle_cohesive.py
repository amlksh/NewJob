# -*- coding: utf-8 -*-
# ======================================================================
#  gen_microneedle_cohesive.py  ->  15_microneedle_cohesive.inp
#
#  [결합 모델] 두께 있는 변형 니들(모델 14) + cohesive 절개 피부(모델 12).
#  -> 요소 삭제(erosion) 없이 "splitting(절개)" 로 니들이 조직을 가름.
#
#   * 니들: 변형 가능한 축대칭 2D solid(CAX4R) 가변벽(내경30/팁50/샤프트150).
#   * 피부: 3층 내장 Neo-Hookean(비삭제) + 니들 팁 외경 r=R_CUT=50um 원통면에
#     두께 0 COHAX4 cohesive 삽입(단일 외측 절개).
#   * 니들 하강 -> r=50 cohesive 견인-분리 -> 코어(r<50)가 외피와 분리,
#     중공 보어(r<30)로 코어가 위로 빠져나가며 매끈하게 coring.
#   * 전 구성요소 내장 -> 서브루틴 불필요(단독 실행). (원하면 cohesive 를
#     작업 C 의 vumat_cohesive.f 로 교체 가능.)
#
#  단위: 길이 um, 응력 MPa, 힘 uN, 질량 kg, 시간 s
#  실행:  python gen_microneedle_cohesive.py
#     abaqus job=mn15 input=15_microneedle_cohesive.inp double=both cpus=4 interactive
# ======================================================================
EPS = 1.0e-9

# --- 피부 (um) : 3층 ---
Z_TOP, Z_SC, Z_EPI = 1500.0, 1480.0, 1400.0
R_MAX = 2000.0
R_CUT = 50.0            # 절개(원통) 반경 = 니들 팁 외경
NC = 10                 # 코어(r<R_CUT) 반경 요소수 (dr=5um)
DR_OUT0 = 5.0           # 절개면 바깥 첫 요소크기
XG = 1.20               # 외부 반경 성장비
DZ_SC = 2.5
DZ_EPI = 10.0
DZ_DTOP = 10.0
Z_GROW = 1.30

# --- 변형 니들 (um) : 모델 14 와 동일 가변벽 ---
R_IN = 30.0
R_TIP = 50.0
R_OUT = 150.0
NW = 4
GAP = 50.0
PUSH = 300.0            # 하강량(코어 과압축·왜곡 억제 -> 절개 시연에 충분)
H_NDL = 2000.0
TAPER_H = 300.0
DZ_TIP = 5.0
DZ_MAX = 40.0
DZ_GROW = 1.15
NDL_E = 200000.0
NDL_NU = 0.3
NDL_RHO = "7.9e-15"

# 층별 내장 Neo-Hookean: C10[MPa], D1[1/MPa] ; 밀도[kg/um^3]
BULK = {
    "STRATUM":   ("1.2e-15", "1.0, 0.02"),
    "EPIDERMIS": ("1.1e-15", "0.1, 0.1"),
    "DERMIS":    ("1.1e-15", "0.02, 1.0"),
}
# CZM (논문값 -> um): 초기강성 4 MPa/um, 강도 2 MPa, Gc 완화(절개 용이)
CZM_E, CZM_STR, CZM_GC, CZM_T0 = 4.0, 2.0, 5.0, 1.0

STRI = 10000            # 피부 z-행 절점 증분
OFF = 5000000           # 외부 블록 절점 오프셋


def build_z():
    zs = {round(Z_EPI, 4)}
    z, dz = Z_EPI, DZ_DTOP
    while z > EPS:
        dz *= Z_GROW
        z -= dz
        zs.add(round(max(z, 0.0), 4))
    z = Z_EPI
    while z < Z_SC - EPS:
        z += DZ_EPI
        zs.add(round(min(z, Z_SC), 4))
    z = Z_SC
    while z < Z_TOP - EPS:
        z += DZ_SC
        zs.add(round(min(z, Z_TOP), 4))
    return sorted(zs)


def layer(zmid):
    if zmid >= Z_SC:
        return "STRATUM"
    if zmid >= Z_EPI:
        return "EPIDERMIS"
    return "DERMIS"


def needle_z():
    zt = Z_TOP + GAP
    zn, z, dz = [zt], zt, DZ_TIP
    while z < zt + H_NDL - EPS:
        z = min(z + dz, zt + H_NDL)
        zn.append(round(z, 4))
        dz = min(dz * DZ_GROW, DZ_MAX)
    return zn, zt


def r_out_at(z, zt):
    if z >= zt + TAPER_H:
        return R_OUT
    return R_TIP + (R_OUT - R_TIP) * (z - zt) / TAPER_H


def main():
    zs = build_z()
    nz = len(zs) - 1
    r_core = [round(R_CUT * i / NC, 4) for i in range(NC + 1)]        # 0..R_CUT
    # 외부: 절개면(R_CUT)에서 세밀(DR_OUT0) -> 바깥으로 기하급수 성김
    r_out, x, dx = [R_CUT], R_CUT, DR_OUT0
    while x < R_MAX - EPS:
        x = min(x + dx, R_MAX)
        r_out.append(round(x, 4))
        dx *= XG
    nco, no = len(r_core), len(r_out)

    def Cid(i, j):
        return 1 + i + STRI * j

    def Oid(i, j):
        return OFF + i + STRI * j

    L = []
    w = L.append
    w("*HEADING")
    w("[15] Deformable thick needle + cohesive coring incision (no deletion)")
    w("Skin: 3-layer built-in Neo-Hookean; r=%.0f um: COHAX4 ; Units um,uN,MPa,s"
      % R_CUT)

    # ---- 피부 절점 (코어 + 외부) ----
    w("*NODE")
    for j, z in enumerate(zs):
        for i, r in enumerate(r_core):
            w("%d, %.4f, %.4f" % (Cid(i, j), r, z))
    for j, z in enumerate(zs):
        for i, r in enumerate(r_out):
            w("%d, %.4f, %.4f" % (Oid(i, j), r, z))

    # ---- 피부 벌크 요소 (CAX4R) : 층별 버킷 ----
    w("*ELEMENT, TYPE=CAX4R")
    e = 0
    elems = {"STRATUM": [], "EPIDERMIS": [], "DERMIS": []}
    core_ids = []                        # 코어(r<R_CUT) -> ALE 대상
    for j in range(nz):
        lay = layer(0.5 * (zs[j] + zs[j + 1]))
        for i in range(nco - 1):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Cid(i, j), Cid(i + 1, j),
                                      Cid(i + 1, j + 1), Cid(i, j + 1)))
            elems[lay].append(e)
            core_ids.append(e)
        for i in range(no - 1):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Oid(i, j), Oid(i + 1, j),
                                      Oid(i + 1, j + 1), Oid(i, j + 1)))
            elems[lay].append(e)

    # ---- Cohesive (COHAX4) : 원통면 r=R_CUT (코어우변 <-> 외부좌변) ----
    w("*ELEMENT, TYPE=COHAX4")
    coh = []
    for j in range(nz):
        e += 1
        w("%d, %d, %d, %d, %d" % (e, Cid(nco - 1, j), Cid(nco - 1, j + 1),
                                  Oid(0, j + 1), Oid(0, j)))
        coh.append(e)

    def wl(name, ids, kw):
        w("*%s, %s=%s" % (kw, kw, name))
        ln = []
        for v in ids:
            ln.append(str(v))
            if len(ln) == 12:
                w(", ".join(ln)); ln = []
        if ln:
            w(", ".join(ln))

    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        wl(lay, elems[lay], "ELSET")
    w("*ELSET, ELSET=BULK")
    w("STRATUM, EPIDERMIS, DERMIS")
    wl("CORE", core_ids, "ELSET")
    w("*ELSET, ELSET=COH, GENERATE")
    w("%d, %d, 1" % (coh[0], coh[-1]))
    w("*SURFACE, TYPE=ELEMENT, NAME=SKIN_SURF")
    w("BULK,")

    # ---- 경계 절점집합 ----
    bot = ([Cid(i, 0) for i in range(nco)] + [Oid(i, 0) for i in range(no)])
    wl("NBOT", bot, "NSET")
    w("*NSET, NSET=NAXIS, GENERATE")
    w("%d, %d, %d" % (Cid(0, 0), Cid(0, nz), STRI))
    w("*NSET, NSET=NRIGHT, GENERATE")
    w("%d, %d, %d" % (Oid(no - 1, 0), Oid(no - 1, nz), STRI))

    # ---- 변형 니들 : CAX4R 가변벽 ----
    zn, zt = needle_z()
    nrows = len(zn)
    nbase = 6000000
    zstr = 1000

    def Nid(i, j):
        return nbase + i + zstr * j

    w("**")
    w("** --- Deformable needle wall (CAX4R): bore %.0f, tip %.0f, shaft %.0f"
      % (R_IN, R_TIP, R_OUT))
    w("*NODE")
    for j, z in enumerate(zn):
        ro = r_out_at(z, zt)
        for i in range(NW + 1):
            r = R_IN + (ro - R_IN) * i / NW
            w("%d, %.4f, %.4f" % (Nid(i, j), r, z))
    w("9999, 0.0, %.4f" % (zt + H_NDL))
    w("*NSET, NSET=NREF")
    w("9999,")
    w("*ELEMENT, TYPE=CAX4R")
    ndl_el = []
    for j in range(nrows - 1):
        for i in range(NW):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Nid(i, j), Nid(i + 1, j),
                                      Nid(i + 1, j + 1), Nid(i, j + 1)))
            ndl_el.append(e)
    w("*ELSET, ELSET=NEEDLE_EL, GENERATE")
    w("%d, %d, 1" % (ndl_el[0], ndl_el[-1]))
    w("*SURFACE, TYPE=ELEMENT, NAME=NEEDLE")
    w("NEEDLE_EL,")
    wl("NDLTOP", [Nid(i, nrows - 1) for i in range(NW + 1)], "NSET")
    w("*SURFACE, TYPE=NODE, NAME=NDLTOP_S")
    w("NDLTOP,")

    # ---- 재료 ----
    w("*MATERIAL, NAME=NEEDLE_MAT")
    w("*DENSITY")
    w("%s," % NDL_RHO)
    w("*ELASTIC")
    w("%.4g, %.4g" % (NDL_E, NDL_NU))
    w("*SOLID SECTION, ELSET=NEEDLE_EL, MATERIAL=NEEDLE_MAT")

    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        rho, cst = BULK[lay]
        w("*MATERIAL, NAME=MAT_%s" % lay)
        w("*DENSITY")
        w("%s," % rho)
        w("*HYPERELASTIC, NEO HOOKE")
        w(cst)
    # 왜곡 제어(요소 뒤집힘 방지, 삭제 없음) + Enhanced hourglass
    w("*SECTION CONTROLS, NAME=SKINCTRL, DISTORTION CONTROL=YES,"
      " HOURGLASS=ENHANCED")
    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        w("*SOLID SECTION, ELSET=%s, MATERIAL=MAT_%s, CONTROLS=SKINCTRL"
          % (lay, lay))

    w("*MATERIAL, NAME=COHMAT")
    w("*DENSITY")
    w("1.1e-15,")
    w("*ELASTIC, TYPE=TRACTION")
    w("%.4g, %.4g, %.4g" % (CZM_E, CZM_E, CZM_E))
    w("*DAMAGE INITIATION, CRITERION=MAXS")
    w("%.4g, %.4g, %.4g" % (CZM_STR, CZM_STR, CZM_STR))
    w("*DAMAGE EVOLUTION, TYPE=ENERGY")
    w("%.4g," % CZM_GC)
    w("*COHESIVE SECTION, ELSET=COH, MATERIAL=COHMAT,"
      " RESPONSE=TRACTION SEPARATION, THICKNESS=SPECIFIED")
    w("%.4g," % CZM_T0)

    # ---- 결합(상단 모서리 -> 참조점) : Explicit *COUPLING+*KINEMATIC ----
    w("*COUPLING, CONSTRAINT NAME=NDL_GRIP, REF NODE=9999, SURFACE=NDLTOP_S")
    w("*KINEMATIC")
    w("1, 2")

    # ---- 접촉 상호작용(모델 데이터) ----
    w("*SURFACE INTERACTION, NAME=IPROP")
    w("*FRICTION")
    w("0.1,")
    w("*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=HARD")

    # ---- 경계/스텝 ----
    w("*BOUNDARY")
    w("NBOT, 2, 2")
    w("NAXIS, 1, 1")
    w("NRIGHT, 1, 1")
    w("NREF, 1, 1")
    w("NREF, 6, 6")
    w("*AMPLITUDE, NAME=PUSH, DEFINITION=SMOOTH STEP")
    w("0.0, 0.0, 0.03, 1.0")
    w("*STEP, NAME=PENETRATION")
    w("*DYNAMIC, EXPLICIT")
    w(", 0.03")
    w("*FIXED MASS SCALING, DT=2.0e-7, TYPE=BELOW MIN")
    # 코어 ALE 적응메쉬: 짓눌리는 코어를 재분할해 왜곡 완화(위상 불변,
    # cohesive 경계는 Lagrangian 유지). 절개는 cohesive 가 담당.
    w("*ADAPTIVE MESH, ELSET=CORE, FREQUENCY=5, MESH SWEEPS=3")
    w("*BOUNDARY, AMPLITUDE=PUSH")
    w("NREF, 2, 2, %.1f" % (-PUSH))
    w("*CONTACT")
    w("*CONTACT INCLUSIONS, ALL EXTERIOR")
    w("*CONTACT INCLUSIONS")
    w("NEEDLE, SKIN_SURF")
    w("*CONTACT PROPERTY ASSIGNMENT")
    w(" ,  , IPROP")
    w("*OUTPUT, FIELD, NUMBER INTERVAL=30")
    w("*ELEMENT OUTPUT, ELSET=BULK")
    w("S, LE")
    w("*ELEMENT OUTPUT, ELSET=COH")
    w("SDEG, STATUS")
    w("*ELEMENT OUTPUT, ELSET=NEEDLE_EL")
    w("S, LE")
    w("*NODE OUTPUT")
    w("U, V")
    w("*OUTPUT, HISTORY, TIME INTERVAL=1.0e-4")
    w("*NODE OUTPUT, NSET=NREF")
    w("U2, V2, RF2")
    w("*ENERGY OUTPUT")
    w("ALLIE, ALLKE, ALLSE, ALLDMD")
    w("*END STEP")

    with open("15_microneedle_cohesive.inp", "w") as f:
        f.write("\n".join(L) + "\n")
    nb = sum(len(v) for v in elems.values())
    print("wrote 15_microneedle_cohesive.inp")
    print("  skin bulk=%d, cohesive(COHAX4)=%d, needle CAX4R=%d"
          % (nb, len(coh), len(ndl_el)))
    print("  r-core=%d, r-out=%d, z-rows=%d ; R_CUT=%.0f, PUSH=%.0f um"
          % (nco, no, nz, R_CUT, PUSH))
    print("  no user subroutine (all built-in) -> standalone runnable")


if __name__ == "__main__":
    main()
