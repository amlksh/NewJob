# -*- coding: utf-8 -*-
# ======================================================================
#  gen_microneedle_cohesive.py  ->  15_microneedle_cohesive.inp
#
#  [결합 모델] 두께 있는 변형 니들 + cohesive 절개 + 층 damage(요소삭제).
#  -> "cohesive(절개) + damage(삭제)" 병용으로 splitting.
#
#   * 니들: 변형 가능한 축대칭 2D solid(CAX4R) 가변벽(내경30/팁50/샤프트150).
#   * 피부: 3층 hyperelastic + 최대주신축비 damage(요소삭제, vumat_skin.f)
#     + 니들 팁 외경 r=R_CUT=50um 원통면에 두께 0 COHAX4 cohesive.
#   * 니들 하강 -> (a) 첨두 아래 코어 요소삭제로 과도변형 중단 방지,
#     (b) r=50 cohesive 견인-분리로 코어/외피 절개 경계 형성.
#   * 삭제가 코어 압축을 해소하므로 ALE 불필요(제거 -> hourglass 충돌 없음).
#
#  단위: 길이 um, 응력 MPa, 힘 uN, 질량 kg, 시간 s
#  실행:  python gen_microneedle_cohesive.py
#     abaqus job=mn15 input=15_microneedle_cohesive.inp user=vumat_skin.f \
#            double=both cpus=4 interactive
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

# 층별 VUMAT(요소삭제): C10[MPa], D1[1/MPa], lam_d, lam_f ; 밀도[kg/um^3]
BULK = {
    "STRATUM":   ("1.2e-15", "1.0, 0.02, 1.2, 1.5"),
    "EPIDERMIS": ("1.1e-15", "0.1, 0.1, 1.4, 1.9"),
    "DERMIS":    ("1.1e-15", "0.02, 1.0, 1.6, 2.5"),
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
    w("[15] Bifurcated skin: core(damage+deletion) / outer(no deletion)")
    w("needle deformable ; r=%.0f um cohesive COHAX4 ; um,uN,MPa,s ; user=vumat"
      % R_CUT)

    # ---- 피부 절점 (코어 + 외부) ----
    w("*NODE")
    for j, z in enumerate(zs):
        for i, r in enumerate(r_core):
            w("%d, %.4f, %.4f" % (Cid(i, j), r, z))
    for j, z in enumerate(zs):
        for i, r in enumerate(r_out):
            w("%d, %.4f, %.4f" % (Oid(i, j), r, z))

    # ---- 피부 벌크 요소 (CAX4R) : 코어/외부 x 층별 버킷 ----
    #  코어(r<R_CUT): VUMAT damage+삭제.  외부(r>R_CUT): 삭제 없는 hyperelastic.
    w("*ELEMENT, TYPE=CAX4R")
    e = 0
    core_el = {"STRATUM": [], "EPIDERMIS": [], "DERMIS": []}
    out_el = {"STRATUM": [], "EPIDERMIS": [], "DERMIS": []}
    for j in range(nz):
        lay = layer(0.5 * (zs[j] + zs[j + 1]))
        for i in range(nco - 1):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Cid(i, j), Cid(i + 1, j),
                                      Cid(i + 1, j + 1), Cid(i, j + 1)))
            core_el[lay].append(e)
        for i in range(no - 1):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Oid(i, j), Oid(i + 1, j),
                                      Oid(i + 1, j + 1), Oid(i, j + 1)))
            out_el[lay].append(e)

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
        wl("C_" + lay, core_el[lay], "ELSET")     # 코어 층별
        wl("O_" + lay, out_el[lay], "ELSET")      # 외부 층별
    w("*ELSET, ELSET=CORE")
    w("C_STRATUM, C_EPIDERMIS, C_DERMIS")
    w("*ELSET, ELSET=OUTER")
    w("O_STRATUM, O_EPIDERMIS, O_DERMIS")
    w("*ELSET, ELSET=BULK")
    w("CORE, OUTER")
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

    # ---- 솔리드 니들(해석적 강체) : 축(r=0) 중심 + 둥근 팁 ----
    #  (1) 축 중심: 첨두가 r=0(피부 축)에 위치.  (3) 팁 라운드로 엣지접촉 개선.
    #  니들 최대반경 = R_CUT -> 코어(r<R_CUT)를 삭제하며 관통, r=R_CUT
    #  cohesive 가 debonding.
    zt = Z_TOP + GAP
    nose = 15.0                          # 팁 라운드(nose) 반경 [um]
    w("**")
    w("** --- Solid rigid needle (axis-centered, rounded conical tip) ---")
    w("*NODE")
    w("9999, 0.0, %.4f" % zt)            # 참조점 = 첨두(축 위)
    w("*NSET, NSET=NREF")
    w("9999,")
    # 세그먼트 순서 샤프트->첨두(외향 법선이 피부/아래를 향함).
    w("*SURFACE, TYPE=SEGMENTS, NAME=NEEDLE, FILLET RADIUS=5.0")
    w("START, %.4f, %.4f" % (R_CUT, zt + 2000.0))     # 샤프트 상단
    w("LINE,  %.4f, %.4f" % (R_CUT, zt + 150.0))      # 샤프트(r=R_CUT)
    w("LINE,  %.4f, %.4f" % (nose, zt + nose))        # 원뿔 테이퍼
    w("CIRCL, 0.0, %.4f, 0.0, %.4f" % (zt, zt + nose))  # 둥근 첨두->축
    w("*RIGID BODY, ANALYTICAL SURFACE=NEEDLE, REF NODE=NREF")

    # ---- 재료 ----
    # 코어 재료: VUMAT hyperelastic + damage(요소삭제)  [vumat_skin.f]
    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        rho, cst = BULK[lay]
        w("*MATERIAL, NAME=MATC_%s" % lay)
        w("*DENSITY")
        w("%s," % rho)
        w("*USER MATERIAL, CONSTANTS=4")
        w(cst)
        w("*DEPVAR, DELETE=1")
        w("4")
        w("1, DELFLAG, deletion flag")
        w("2, LAMMAX, max principal stretch")
        w("3, DAMAGE, damage variable")
        w("4, JVOL, relative volume")
    # 외부 재료: 삭제 없는 순수 내장 Neo-Hookean (C10,D1 = props 앞 2개)
    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        rho, cst = BULK[lay]
        c10, d1 = [t.strip() for t in cst.split(",")][:2]
        w("*MATERIAL, NAME=MATO_%s" % lay)
        w("*DENSITY")
        w("%s," % rho)
        w("*HYPERELASTIC, NEO HOOKE")
        w("%s, %s" % (c10, d1))
    # 코어(삭제)만 Enhanced hourglass+왜곡제어. 외부는 기본(내장 hyper).
    w("*SECTION CONTROLS, NAME=CORECTRL, DISTORTION CONTROL=YES,"
      " HOURGLASS=ENHANCED")
    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        w("*SOLID SECTION, ELSET=C_%s, MATERIAL=MATC_%s, CONTROLS=CORECTRL"
          % (lay, lay))
    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        w("*SOLID SECTION, ELSET=O_%s, MATERIAL=MATO_%s" % (lay, lay))

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
    # 코어 과압축은 요소삭제(damage)로 해소 -> ALE 불필요(제거).
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
    w("*ELEMENT OUTPUT, ELSET=CORE")
    w("SDV, STATUS")
    w("*ELEMENT OUTPUT, ELSET=COH")
    w("SDEG, STATUS")
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
    ncore = sum(len(v) for v in core_el.values())
    nout = sum(len(v) for v in out_el.values())
    print("wrote 15_microneedle_cohesive.inp")
    print("  core(삭제)=%d, outer(비삭제)=%d, cohesive=%d (needle=rigid)"
          % (ncore, nout, len(coh)))
    print("  r-core=%d, r-out=%d, z-rows=%d ; R_CUT=%.0f, PUSH=%.0f um"
          % (nco, no, nz, R_CUT, PUSH))
    print("  이원화: 코어 VUMAT damage+삭제 / 외부 내장 hyper(비삭제) ; "
          "needs user=vumat_skin.f")


if __name__ == "__main__":
    main()
