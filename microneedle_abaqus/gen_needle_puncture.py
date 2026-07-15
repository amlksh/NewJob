# -*- coding: utf-8 -*-
# ======================================================================
#  gen_needle_puncture.py  ->  16_needle_puncture.inp
#
#  [모델 16] CAE Assistant "Needle Puncture of Skin by Injection" 방식.
#  솔리드 원뿔 니들 + 3층 피부(표피/진피/피하) hyperelastic
#  + cohesive 절개 + 층 damage(요소삭제)  -- 병용.
#
#   * 니들: 솔리드 원뿔(해석적 강체), 첨두 r=0 -> 테이퍼 -> 샤프트 R_CONE.
#   * 피부 3층: 표피(epidermis)/진피(dermis)/피하(hypodermis).
#     - hyperelastic + 최대주신축비 damage(요소삭제)  <- vumat_skin.f
#       => 니들 첨두 아래 코어가 삭제되어 관통(과도변형 중단 방지).
#     - r=R_CONE 원통면에 COHAX4 cohesive(견인-분리) => 깨끗한 절개 경계.
#   * 두 메커니즘 병용: 삭제가 코어 제거(안정), cohesive가 splitting 표현.
#
#  Dynamic/Explicit, 단위: um, uN, MPa, s.
#  실행: python gen_needle_puncture.py
#    abaqus job=np16 input=16_needle_puncture.inp user=vumat_skin.f \
#           double=both cpus=4 interactive
# ======================================================================
EPS = 1.0e-9

# --- 피부 3층 (um), z: 0(하단)~Z_TOP(상단) ---
Z_TOP = 1500.0
Z_DE = 1400.0          # 표피-진피 경계
Z_HD = 1000.0          # 진피-피하 경계
R_MAX = 1500.0
R_CONE = 100.0         # 니들(원뿔) 샤프트 반경 = 절개 반경
NC = 20                # 코어(r<R_CONE) 반경 요소수 (dr=5um)
DR_OUT0 = 5.0
XG = 1.20
DZ_TOP = 5.0           # 상면(표피) 요소크기
DZ_MAX = 40.0
Z_GROW = 1.15

GAP = 30.0             # 피부 상면 위 초기간격
PUSH = 800.0           # 니들 하강량(관통 깊이)
TAPER = 400.0          # 원뿔 테이퍼 높이(첨두->샤프트)

# 층 재료 (VUMAT deletion): C10[MPa], D1[1/MPa], lam_d, lam_f ; 밀도
MAT = {
    "EPIDERMIS":  ("1.2e-15", "0.2, 0.05, 1.3, 1.7"),
    "DERMIS":     ("1.1e-15", "0.05, 0.5, 1.5, 2.2"),
    "HYPODERMIS": ("1.1e-15", "0.01, 2.0, 1.6, 2.8"),
}
# CZM: 초기강성 4 MPa/um, 강도 2 MPa, Gc 5 uN/um, 두께 1um
CZM_E, CZM_STR, CZM_GC, CZM_T0 = 4.0, 2.0, 5.0, 1.0

STRI = 10000
OFF = 5000000


def build_z():
    zs = {round(Z_TOP, 4), round(Z_DE, 4), round(Z_HD, 4), 0.0}
    z, dz = Z_TOP, DZ_TOP                 # 상면에서 세밀 -> 하부 성김
    while z > EPS:
        z -= dz
        zs.add(round(max(z, 0.0), 4))
        dz = min(dz * Z_GROW, DZ_MAX)
    return sorted(zs)


def layer(zmid):
    if zmid >= Z_DE:
        return "EPIDERMIS"
    if zmid >= Z_HD:
        return "DERMIS"
    return "HYPODERMIS"


def main():
    zs = build_z()
    nz = len(zs) - 1
    r_core = [round(R_CONE * i / NC, 4) for i in range(NC + 1)]
    r_out, x, dx = [R_CONE], R_CONE, DR_OUT0
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
    w("[16] Needle puncture of skin (solid cone) - 3 layers")
    w("hyperelastic + cohesive + layer damage(deletion) ; Units um,uN,MPa,s")

    # ---- 절점 ----
    w("*NODE")
    for j, z in enumerate(zs):
        for i, r in enumerate(r_core):
            w("%d, %.4f, %.4f" % (Cid(i, j), r, z))
    for j, z in enumerate(zs):
        for i, r in enumerate(r_out):
            w("%d, %.4f, %.4f" % (Oid(i, j), r, z))

    # ---- 벌크 요소(CAX4R) : 층별 버킷 ----
    w("*ELEMENT, TYPE=CAX4R")
    e = 0
    elems = {"EPIDERMIS": [], "DERMIS": [], "HYPODERMIS": []}
    for j in range(nz):
        lay = layer(0.5 * (zs[j] + zs[j + 1]))
        for i in range(nco - 1):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Cid(i, j), Cid(i + 1, j),
                                      Cid(i + 1, j + 1), Cid(i, j + 1)))
            elems[lay].append(e)
        for i in range(no - 1):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Oid(i, j), Oid(i + 1, j),
                                      Oid(i + 1, j + 1), Oid(i, j + 1)))
            elems[lay].append(e)

    # ---- Cohesive(COHAX4) : r=R_CONE ----
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

    for lay in ("EPIDERMIS", "DERMIS", "HYPODERMIS"):
        wl(lay, elems[lay], "ELSET")
    w("*ELSET, ELSET=BULK")
    w("EPIDERMIS, DERMIS, HYPODERMIS")
    w("*ELSET, ELSET=COH, GENERATE")
    w("%d, %d, 1" % (coh[0], coh[-1]))
    w("*SURFACE, TYPE=ELEMENT, NAME=SKIN_SURF")
    w("BULK,")

    bot = ([Cid(i, 0) for i in range(nco)] + [Oid(i, 0) for i in range(no)])
    wl("NBOT", bot, "NSET")
    w("*NSET, NSET=NAXIS, GENERATE")
    w("%d, %d, %d" % (Cid(0, 0), Cid(0, nz), STRI))
    w("*NSET, NSET=NRIGHT, GENERATE")
    w("%d, %d, %d" % (Oid(no - 1, 0), Oid(no - 1, nz), STRI))

    # ---- 솔리드 원뿔 니들(해석적 강체) ----
    zt = Z_TOP + GAP
    w("*NODE")
    w("9999, 0.0, %.4f" % zt)
    w("*NSET, NSET=NREF")
    w("9999,")
    # 샤프트->첨두 순서(외향 법선이 피부/아래를 향함). 첨두 fillet.
    w("*SURFACE, TYPE=SEGMENTS, NAME=NEEDLE, FILLET RADIUS=5.0")
    w("START, %.4f, %.4f" % (R_CONE, zt + 2000.0))
    w("LINE,  %.4f, %.4f" % (R_CONE, zt + TAPER))
    w("LINE,  0.0, %.4f" % zt)
    w("*RIGID BODY, ANALYTICAL SURFACE=NEEDLE, REF NODE=NREF")

    # ---- 재료 (층별 VUMAT deletion) ----
    for lay in ("EPIDERMIS", "DERMIS", "HYPODERMIS"):
        rho, cst = MAT[lay]
        w("*MATERIAL, NAME=MAT_%s" % lay)
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
    # Enhanced hourglass(연조직 reduced-integration 안정화)
    w("*SECTION CONTROLS, NAME=SKINCTRL, HOURGLASS=ENHANCED")
    for lay in ("EPIDERMIS", "DERMIS", "HYPODERMIS"):
        w("*SOLID SECTION, ELSET=%s, MATERIAL=MAT_%s, CONTROLS=SKINCTRL"
          % (lay, lay))

    # ---- Cohesive 재료(내장 CZM) ----
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
    w("*STEP, NAME=PUNCTURE")
    w("*DYNAMIC, EXPLICIT")
    w(", 0.03")
    w("*FIXED MASS SCALING, DT=2.0e-7, TYPE=BELOW MIN")
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
    w("S, LE, SDV, STATUS")
    w("*ELEMENT OUTPUT, ELSET=COH")
    w("SDEG, STATUS")
    w("*NODE OUTPUT")
    w("U, V")
    w("*OUTPUT, HISTORY, TIME INTERVAL=1.0e-4")
    w("*NODE OUTPUT, NSET=NREF")
    w("U2, V2, RF2")
    w("*ENERGY OUTPUT")
    w("ALLIE, ALLKE, ALLSE, ALLDMD, ALLWK")
    w("*END STEP")

    with open("16_needle_puncture.inp", "w") as f:
        f.write("\n".join(L) + "\n")
    nb = sum(len(v) for v in elems.values())
    print("wrote 16_needle_puncture.inp")
    print("  layers: epidermis/dermis/hypodermis ; bulk=%d, cohesive=%d"
          % (nb, len(coh)))
    print("  r-core=%d, r-out=%d, z-rows=%d ; R_CONE=%.0f, PUSH=%.0f um"
          % (nco, no, nz, R_CONE, PUSH))
    print("  needle: solid cone (rigid) ; deletion+cohesive combined")


if __name__ == "__main__":
    main()
