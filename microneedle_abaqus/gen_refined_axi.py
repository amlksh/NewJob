# -*- coding: utf-8 -*-
# ======================================================================
#  gen_refined_axi.py
#
#  니들 경로 부근 메쉬 바이어스 세밀화 축대칭 3층 피부 관통 모델 생성기.
#
#    - 반경방향 : 축(r=0) 근처 세밀, 바깥으로 기하급수 성김
#    - 깊이방향 : 상면(각질층) 세밀, 하부(진피)로 성김
#
#  generate(...) 함수로 파라미터화하여 메쉬 수렴성 스터디에서 재사용.
#  material mode:
#    reg=False : 변형률(주신축비) 기반 손상  -> vumat_skin.f
#                PROPS = C10, D1, lam_d, lam_f
#    reg=True  : 파단에너지(charLength) 정규화 -> vumat_skin_reg.f
#                PROPS = C10, D1, lam_d, uf   (uf=파단변위[mm])
#
#  실행(기본):  python gen_refined_axi.py   ->  04_refined_path.inp
# ======================================================================

EPS = 1.0e-9

# 층 z-경계 [mm]
Z_TOP, Z_SC, Z_EPI = 1.50, 1.48, 1.40
DZ_EPI = 0.02          # 표피 요소크기
DZ_DERM_TOP = 0.02     # 진피 상단 요소크기

# 층별 재료상수 (mode 에 따라 4번째 값 의미가 lam_f 또는 uf)
MAT_STRAIN = {   # C10, D1, lam_d, lam_f
    "STRATUM":   "1.0, 0.02, 1.2, 1.5",
    "EPIDERMIS": "0.1, 0.1, 1.4, 1.9",
    "DERMIS":    "0.02, 1.0, 1.6, 2.5",
}
MAT_ENERGY = {   # C10, D1, lam_d, uf[mm]
    "STRATUM":   "1.0, 0.02, 1.2, 0.003",
    "EPIDERMIS": "0.1, 0.1, 1.4, 0.010",
    "DERMIS":    "0.02, 1.0, 1.6, 0.030",
}
RHO = {"STRATUM": "1.2e-9", "EPIDERMIS": "1.1e-9", "DERMIS": "1.1e-9"}


def _build_x(dr_fine, r_fine_zone, r_max, r_grow):
    xs = [0.0]
    for k in range(1, int(round(r_fine_zone / dr_fine)) + 1):
        xs.append(round(dr_fine * k, 6))
    x, dx = xs[-1], dr_fine
    while x < r_max - EPS:
        dx *= r_grow
        x += dx
        if x > r_max:
            x = r_max
        xs.append(round(x, 6))
    return xs


def _build_z(dz_sc, z_grow):
    zs = set()
    zs.add(round(Z_EPI, 6))
    z, dz = Z_EPI, DZ_DERM_TOP
    while z > EPS:                     # 진피 : 상단에서 아래로 성장
        dz *= z_grow
        z -= dz
        zs.add(round(max(z, 0.0), 6))
    z = Z_EPI                          # 표피
    while z < Z_SC - EPS:
        z += DZ_EPI
        zs.add(round(min(z, Z_SC), 6))
    z = Z_SC                           # 각질층
    while z < Z_TOP - EPS:
        z += dz_sc
        zs.add(round(min(z, Z_TOP), 6))
    return sorted(zs)


def _layer(zmid):
    if zmid >= Z_SC:
        return "STRATUM"
    if zmid >= Z_EPI:
        return "EPIDERMIS"
    return "DERMIS"


def generate(outfile="04_refined_path.inp", dr_fine=0.03, dz_sc=0.005,
             r_fine_zone=0.30, r_max=2.0, r_grow=1.25, z_grow=1.30,
             reg=False, verbose=True):
    xs = _build_x(dr_fine, r_fine_zone, r_max, r_grow)
    zs = _build_z(dz_sc, z_grow)
    nx, nz = len(xs), len(zs)
    jstr = 10 ** len(str(nx + 1))     # 열보다 큰 자릿수 자동 확보

    def nid(i, j):
        return 1 + i + jstr * j

    mats = MAT_ENERGY if reg else MAT_STRAIN
    L = []
    w = L.append
    tag = "energy-regularized" if reg else "stretch-based"
    w("*HEADING")
    w("Path-refined axisymmetric 3-layer skin penetration (%s failure)" % tag)
    w("Units: mm, N, MPa, tonne, s")

    w("*NODE")
    for j, z in enumerate(zs):
        for i, x in enumerate(xs):
            w("%d, %.6f, %.6f" % (nid(i, j), x, z))

    conn, elems = [], {"STRATUM": [], "EPIDERMIS": [], "DERMIS": []}
    e = 0
    for j in range(nz - 1):
        lay = _layer(0.5 * (zs[j] + zs[j + 1]))
        for i in range(nx - 1):
            e += 1
            conn.append((e, nid(i, j), nid(i + 1, j),
                         nid(i + 1, j + 1), nid(i, j + 1)))
            elems[lay].append(e)
    w("*ELEMENT, TYPE=CAX4R")
    for (e, a, b, c, d) in conn:
        w("%d, %d, %d, %d, %d" % (e, a, b, c, d))

    def wlist(name, ids, kw="ELSET"):
        w("*%s, %s=%s" % ("ELSET" if kw == "ELSET" else "NSET", kw, name))
        line = []
        for v in ids:
            line.append(str(v))
            if len(line) == 12:
                w(", ".join(line)); line = []
        if line:
            w(", ".join(line))

    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        wlist(lay, elems[lay])
    w("*ELSET, ELSET=SKIN_ALL")
    w("STRATUM, EPIDERMIS, DERMIS")
    w("*SURFACE, TYPE=ELEMENT, NAME=SKIN_SURF")
    w("SKIN_ALL,")

    wlist("NBOT", [nid(i, 0) for i in range(nx)], kw="NSET")
    wlist("NAXIS", [nid(0, j) for j in range(nz)], kw="NSET")
    wlist("NRIGHT", [nid(nx - 1, j) for j in range(nz)], kw="NSET")

    w("*NODE")
    w("9999, 0.0, %.5f" % (Z_TOP + 0.02))
    w("*NSET, NSET=NREF")
    w("9999,")
    w("*SURFACE, TYPE=SEGMENTS, NAME=NEEDLE, FILLET RADIUS=0.01")
    w("START, 0.02, %.5f" % (Z_TOP + 0.02))
    w("LINE,  0.15, %.5f" % (Z_TOP + 0.40))
    w("LINE,  0.15, %.5f" % (Z_TOP + 2.00))
    w("*RIGID BODY, ANALYTICAL SURFACE=NEEDLE, REF NODE=NREF")

    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        w("*MATERIAL, NAME=MAT_%s" % lay)
        w("*DENSITY")
        w("%s," % RHO[lay])
        w("*USER MATERIAL, CONSTANTS=4")
        w(mats[lay])
        w("*DEPVAR, DELETE=1")
        w("4")
        w("1, DELFLAG, deletion flag")
        w("2, LAMMAX, max principal stretch")
        w("3, DAMAGE, damage variable")
        w("4, JVOL, relative volume")
    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        w("*SOLID SECTION, ELSET=%s, MATERIAL=MAT_%s" % (lay, lay))

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

    with open(outfile, "w") as f:
        f.write("\n".join(L) + "\n")
    ne = sum(len(v) for v in elems.values())
    if verbose:
        print("wrote %s : %d nodes, %d elems (r-nodes=%d, z-nodes=%d), "
              "dr_fine=%.4f dz_sc=%.4f, %s"
              % (outfile, nx * nz, ne, nx, nz, dr_fine, dz_sc, tag))
    return {"file": outfile, "nodes": nx * nz, "elems": ne,
            "nx": nx, "nz": nz, "dr_fine": dr_fine, "dz_sc": dz_sc}


if __name__ == "__main__":
    generate()
