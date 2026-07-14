# -*- coding: utf-8 -*-
# ======================================================================
#  gen_refined_axi.py
#
#  (1) 니들 경로 부근 메쉬 바이어스 세밀화  ->  04_refined_path.inp
#
#  2D 축대칭 3층 피부(각질층/표피/진피). 요소 삭제 경로를 매끈하게 하고
#  메쉬 의존성을 줄이기 위해:
#    - 반경방향 : 축(r=0) 근처를 세밀(~0.03), 바깥으로 기하급수 성김
#    - 깊이방향 : 상면(각질층) 근처를 세밀, 하부(진피)로 성김
#  텐서곱 격자를 좌표배열로 직접 생성하여 절점/요소 번호를 보장.
#
#  실행:  python gen_refined_axi.py
# ======================================================================

# --- 반경/깊이 파라미터 -----------------------------------------------
R_FINE_ZONE = 0.30     # 축 근처 균일 세밀영역 반경 [mm]
DR_FINE     = 0.03     # 세밀영역 반경 요소크기
R_MAX       = 2.0      # 전체 반경 [mm]
R_GROW      = 1.25     # 세밀영역 밖 반경 성장비

Z_TOP       = 1.50     # 피부 상면 z [mm]
Z_EPI       = 1.40     # 진피/표피 경계
Z_SC        = 1.48     # 표피/각질층 경계
DZ_SC       = 0.005    # 각질층 요소크기 (얇고 세밀)
DZ_EPI      = 0.02     # 표피 요소크기
DZ_DERM_TOP = 0.02     # 진피 상단(경계) 요소크기
Z_GROW      = 1.30     # 진피 하향 성장비

JSTR = 1000            # 절점 z-행 번호 증분
EPS  = 1.0e-9


def build_x():
    xs = [0.0]
    for k in range(1, int(round(R_FINE_ZONE / DR_FINE)) + 1):
        xs.append(round(DR_FINE * k, 6))
    x = xs[-1]
    dx = DR_FINE
    while x < R_MAX - EPS:
        dx *= R_GROW
        x += dx
        if x > R_MAX:
            x = R_MAX
        xs.append(round(x, 6))
    return xs


def build_z():
    zs = set()
    # 진피 : 상단(Z_EPI)에서 아래로 성장
    zs.add(round(Z_EPI, 6))
    z = Z_EPI
    dz = DZ_DERM_TOP
    while z > EPS:
        dz *= Z_GROW
        z -= dz
        if z < 0.0:
            z = 0.0
        zs.add(round(z, 6))
    # 표피
    z = Z_EPI
    while z < Z_SC - EPS:
        z += DZ_EPI
        zs.add(round(min(z, Z_SC), 6))
    # 각질층
    z = Z_SC
    while z < Z_TOP - EPS:
        z += DZ_SC
        zs.add(round(min(z, Z_TOP), 6))
    return sorted(zs)


def layer_of(zmid):
    if zmid >= Z_SC:
        return "STRATUM"
    if zmid >= Z_EPI:
        return "EPIDERMIS"
    return "DERMIS"


def main():
    xs = build_x()
    zs = build_z()
    nx, nz = len(xs), len(zs)

    def nid(i, j):
        return 1 + i + JSTR * j

    L = []
    w = L.append
    w("*HEADING")
    w("(1) Path-refined axisymmetric 3-layer skin penetration (CAX4R + VUMAT)")
    w("Biased mesh: fine near axis r=0 and near top surface (stratum corneum)")
    w("Units: mm, N, MPa, tonne, s")

    # ---- 절점 ----
    w("*NODE")
    for j, z in enumerate(zs):
        for i, x in enumerate(xs):
            w("%d, %.6f, %.6f" % (nid(i, j), x, z))

    # ---- 요소 (층별 ELSET 분류) ----
    elems = {"STRATUM": [], "EPIDERMIS": [], "DERMIS": []}
    conn = []
    e = 0
    for j in range(nz - 1):
        zmid = 0.5 * (zs[j] + zs[j + 1])
        lay = layer_of(zmid)
        for i in range(nx - 1):
            e += 1
            n1 = nid(i, j)
            n2 = nid(i + 1, j)
            n3 = nid(i + 1, j + 1)
            n4 = nid(i, j + 1)
            conn.append((e, n1, n2, n3, n4))
            elems[lay].append(e)
    w("*ELEMENT, TYPE=CAX4R")
    for (e, n1, n2, n3, n4) in conn:
        w("%d, %d, %d, %d, %d" % (e, n1, n2, n3, n4))

    def elset(name, ids):
        w("*ELSET, ELSET=%s" % name)
        line = []
        for v in ids:
            line.append(str(v))
            if len(line) == 12:
                w(", ".join(line)); line = []
        if line:
            w(", ".join(line))

    elset("STRATUM", elems["STRATUM"])
    elset("EPIDERMIS", elems["EPIDERMIS"])
    elset("DERMIS", elems["DERMIS"])
    w("*ELSET, ELSET=SKIN_ALL")
    w("STRATUM, EPIDERMIS, DERMIS")
    w("*SURFACE, TYPE=ELEMENT, NAME=SKIN_SURF")
    w("SKIN_ALL,")

    # ---- 경계 절점집합 ----
    def nset(name, pts):
        w("*NSET, NSET=%s" % name)
        line = []
        for n in pts:
            line.append(str(n))
            if len(line) == 12:
                w(", ".join(line)); line = []
        if line:
            w(", ".join(line))

    nset("NBOT", [nid(i, 0) for i in range(nx)])
    nset("NAXIS", [nid(0, j) for j in range(nz)])
    nset("NRIGHT", [nid(nx - 1, j) for j in range(nz)])

    # ---- 강체 니들 (해석적 강체) ----
    w("*NODE")
    w("9999, 0.0, %.5f" % (Z_TOP + 0.02))
    w("*NSET, NSET=NREF")
    w("9999,")
    w("*SURFACE, TYPE=SEGMENTS, NAME=NEEDLE, FILLET RADIUS=0.01")
    w("START, 0.02, %.5f" % (Z_TOP + 0.02))
    w("LINE,  0.15, %.5f" % (Z_TOP + 0.40))
    w("LINE,  0.15, %.5f" % (Z_TOP + 2.00))
    w("*RIGID BODY, ANALYTICAL SURFACE=NEEDLE, REF NODE=NREF")

    # ---- 층별 재료 (VUMAT: C10, D1, lam_d, lam_f) ----
    mats = [("MAT_SC",   "1.2e-9", "1.0, 0.02, 1.2, 1.5", "STRATUM"),
            ("MAT_EPI",  "1.1e-9", "0.1, 0.1, 1.4, 1.9",  "EPIDERMIS"),
            ("MAT_DERM", "1.1e-9", "0.02, 1.0, 1.6, 2.5", "DERMIS")]
    for name, rho, consts, _ in mats:
        w("*MATERIAL, NAME=%s" % name)
        w("*DENSITY")
        w("%s," % rho)
        w("*USER MATERIAL, CONSTANTS=4")
        w(consts)
        w("*DEPVAR, DELETE=1")
        w("4")
        w("1, DELFLAG, deletion flag")
        w("2, LAMMAX, max principal stretch")
        w("3, DAMAGE, damage variable")
        w("4, JVOL, relative volume")
    for name, _, _, els in mats:
        w("*SOLID SECTION, ELSET=%s, MATERIAL=%s" % (els, name))

    # ---- 경계조건 / 스텝 ----
    w("*BOUNDARY")
    w("NBOT, 2, 2")
    w("NAXIS, 1, 1")
    w("NRIGHT, 1, 1")
    w("NREF, 1, 1")
    w("NREF, 6, 6")
    w("*AMPLITUDE, NAME=PUSH, DEFINITION=SMOOTH STEP")
    w("0.0, 0.0, 0.01, 1.0")
    w("*STEP, NAME=PENETRATION")
    w("*DYNAMIC, EXPLICIT")
    w(", 0.01")
    w("*FIXED MASS SCALING, DT=2.0e-7, TYPE=BELOW MIN")
    w("*BOUNDARY, AMPLITUDE=PUSH")
    w("NREF, 2, 2, -1.2")
    w("*CONTACT")
    w("*CONTACT INCLUSIONS, ALL EXTERIOR")
    w("*CONTACT INCLUSIONS")
    w("NEEDLE, SKIN_SURF")
    w("*CONTACT PROPERTY ASSIGNMENT")
    w(" ,  , IPROP")
    w("*SURFACE INTERACTION, NAME=IPROP")
    w("*FRICTION")
    w("0.1,")
    w("*OUTPUT, FIELD, NUMBER INTERVAL=25")
    w("*ELEMENT OUTPUT, ELSET=SKIN_ALL")
    w("S, LE, SDV, STATUS")
    w("*NODE OUTPUT")
    w("U, V")
    w("*OUTPUT, HISTORY, TIME INTERVAL=1.0e-4")
    w("*NODE OUTPUT, NSET=NREF")
    w("U2, V2, RF2")
    w("*ENERGY OUTPUT")
    w("ALLIE, ALLKE, ALLSE, ALLWK")
    w("*END STEP")

    with open("04_refined_path.inp", "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote 04_refined_path.inp")
    print("  radial nodes = %d (fine dr=%.3f near axis, %d in fine zone)"
          % (nx, DR_FINE, int(round(R_FINE_ZONE / DR_FINE))))
    print("  depth  nodes = %d" % nz)
    print("  elements = %d (SC=%d, EPI=%d, DERM=%d)"
          % (sum(len(v) for v in elems.values()),
             len(elems["STRATUM"]), len(elems["EPIDERMIS"]),
             len(elems["DERMIS"])))
    print("  smallest element ~ dr=%.3f x dz=%.3f (near tip)"
          % (DR_FINE, DZ_SC))


if __name__ == "__main__":
    main()
