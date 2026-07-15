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

# --- 피부 (um) : 3층 ---  (접촉부·코어 요소 -30%, 코어반경 -30%)
Z_TOP, Z_SC, Z_EPI = 1500.0, 1480.0, 1400.0
R_MAX = 2000.0
R_CUT = 35.0            # 절개(원통) 반경 = 니들 반경 (50 -> 35, -30%)
NC = 10                 # 코어(r<R_CUT) 반경 요소수 (dr=3.5um, -30%)
DR_OUT0 = 3.5           # 절개면 바깥 첫 요소크기 (5 -> 3.5, -30%)
XG = 1.20               # 외부 반경 성장비
DZ_SC = 1.75           # 각질층 요소(접촉부) (2.5 -> 1.75, -30%)
DZ_EPI = 7.0           # 표피 요소 (10 -> 7, -30%)
DZ_DTOP = 10.0
Z_GROW = 1.30

# --- 니들 (um) : 2D CAX4R 솔리드 메쉬 + 강체(Rigid Body) ---
#  축(r=0) 중심 솔리드 원뿔, 둥근 blunt 팁. 요소기반 접촉(침식 접촉 강건).
GAP = 50.0
PUSH = 300.0            # 하강량
NDL_RTIP = 5.0         # blunt 팁 반경(축 중심, 둥근 팁)
NDL_CONE_H = 120.0     # 원뿔 높이(팁 -> 샤프트)
NDL_H = 1000.0         # 니들 총 높이
NW_N = 10              # 니들 반경방향 요소열
NDL_DZ0 = 3.5          # 팁 근처 축방향 요소크기(접촉부)
NDL_DZMAX = 20.0
NDL_DZG = 1.2
NDL_E = 200000.0       # 강체이지만 mass 위한 명목 물성
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

# 삭제 후 탄성 복원(snap-back)-투과 대책 (모두 튜닝 가능)
DAMP_ALPHA = 5.0e4      # 재료 질량비례 damping [1/s] (*DAMPING, ALPHA)
CONT_DAMP = 0.5         # 접촉 임계감쇠 분율 (*CONTACT DAMPING)
MS_DT = 1.0e-7          # 질량스케일링 목표 증분 [s] (작을수록 시간분해능↑)

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


def needle_z(zt):
    """니들 z-레벨(팁 zt 에서 위로, 팁 근처 세밀)."""
    zn, z, dz = [zt], zt, NDL_DZ0
    while z < zt + NDL_H - EPS:
        z = min(z + dz, zt + NDL_H)
        zn.append(round(z, 4))
        dz = min(dz * NDL_DZG, NDL_DZMAX)
    return zn


def needle_rout(z, zt):
    """니들 외곽반경: 팁(zt) blunt R -> 원뿔 -> 샤프트 R_CUT."""
    if z >= zt + NDL_CONE_H:
        return R_CUT
    return NDL_RTIP + (R_CUT - NDL_RTIP) * (z - zt) / NDL_CONE_H


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

    # ---- 니들: CAX4R 2D 솔리드 메쉬 + 강체(Rigid Body) ----
    #  축(r=0) 중심 솔리드 원뿔(blunt 둥근 팁). 요소기반 표면 -> 침식 접촉
    #  강건. 최대반경 = R_CUT -> 코어(r<R_CUT) 삭제하며 관통, r=R_CUT debond.
    zt = Z_TOP + GAP
    znn = needle_z(zt)
    nrow_n = len(znn)
    nbase = 6000000
    zstr = 1000

    def Nid(i, j):
        return nbase + i + zstr * j

    w("**")
    w("** --- Needle: CAX4R solid, rigid body (axis-centered, blunt tip) ---")
    w("*NODE")
    for j, z in enumerate(znn):
        ro = needle_rout(z, zt)
        for i in range(NW_N + 1):
            w("%d, %.4f, %.4f" % (Nid(i, j), ro * i / NW_N, z))
    w("9999, 0.0, %.4f" % (zt + NDL_H))       # 참조점(강체 제어)
    w("*NSET, NSET=NREF")
    w("9999,")
    w("*ELEMENT, TYPE=CAX4R")
    ndl_el = []
    for j in range(nrow_n - 1):
        for i in range(NW_N):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Nid(i, j), Nid(i + 1, j),
                                      Nid(i + 1, j + 1), Nid(i, j + 1)))
            ndl_el.append(e)
    w("*ELSET, ELSET=NEEDLE_EL, GENERATE")
    w("%d, %d, 1" % (ndl_el[0], ndl_el[-1]))
    w("*SURFACE, TYPE=ELEMENT, NAME=NEEDLE")
    w("NEEDLE_EL,")
    # 연속체 요소를 강체로: 물성/단면은 mass 용, 변형은 무시됨.
    w("*RIGID BODY, ELSET=NEEDLE_EL, REF NODE=NREF")

    # ---- 재료 ----
    w("*MATERIAL, NAME=NEEDLE_MAT")
    w("*DENSITY")
    w("%s," % NDL_RHO)
    w("*ELASTIC")
    w("%.4g, %.4g" % (NDL_E, NDL_NU))
    w("*SOLID SECTION, ELSET=NEEDLE_EL, MATERIAL=NEEDLE_MAT")
    # 코어 재료: VUMAT hyperelastic + damage(요소삭제)  [vumat_skin.f]
    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        rho, cst = BULK[lay]
        w("*MATERIAL, NAME=MATC_%s" % lay)
        w("*DENSITY")
        w("%s," % rho)
        w("*DAMPING, ALPHA=%.4g" % DAMP_ALPHA)
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
        w("*DAMPING, ALPHA=%.4g" % DAMP_ALPHA)
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
    # 삭제-복원 재접촉 시 급속 접근 감쇠 -> 투과 억제
    w("*CONTACT DAMPING, DEFINITION=CRITICAL DAMPING FRACTION")
    w("%.4g," % CONT_DAMP)

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
    w("*FIXED MASS SCALING, DT=%.2g, TYPE=BELOW MIN" % MS_DT)
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
    print("  core(삭제)=%d, outer(비삭제)=%d, cohesive=%d, needle CAX4R(rigid)=%d"
          % (ncore, nout, len(coh), len(ndl_el)))
    print("  r-core=%d, r-out=%d, z-rows=%d ; R_CUT=%.0f, PUSH=%.0f um"
          % (nco, no, nz, R_CUT, PUSH))
    print("  이원화: 코어 VUMAT damage+삭제 / 외부 내장 hyper(비삭제) ; "
          "needs user=vumat_skin.f")


if __name__ == "__main__":
    main()
