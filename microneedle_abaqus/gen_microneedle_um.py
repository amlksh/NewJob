# -*- coding: utf-8 -*-
# ======================================================================
#  gen_microneedle_um.py  ->  10_microneedle_um.inp
#
#  전문가 피드백 반영판 (v1, 실행검증 필요):
#   1) 중공(hollow) 니들: 축대칭에서 끝단 bore(구멍)가 열려 있고, 니들 벽을
#      "유한 두께 surface"(환형)로 모사. 첨두는 점(vertex)이 아니라 환형
#      첨두면(annular tip) -> sharp-vertex 수렴문제 회피 + 구멍 유지.
#   2) 마이크로 단위계: um, uN, MPa, s  (물성 MPa 값 불변, 길이 x1000,
#      밀도 x1e-6 = tonne/mm^3 -> (본 계) kg/um^3 등가).
#   3) 접촉부 피부 메쉬 세밀화(근축 dr=5um).
#
#  단위: 길이 um, 응력 MPa(=uN/um^2), 힘 uN, 밀도 [본계], 시간 s
#  실행: python gen_microneedle_um.py
#        abaqus job=mn10 input=10_microneedle_um.inp user=vumat_skin.f double=both cpus=4 interactive
# ======================================================================

EPS = 1.0e-9

# --- 피부 (um) : 3층 ---
Z_TOP, Z_SC, Z_EPI = 1500.0, 1480.0, 1400.0     # 상면/각질-표피/표피-진피 경계
R_MAX = 2000.0
DR_FINE = 5.0            # 근축 접촉부 반경 요소크기 [um]
R_FINE = 300.0          # 세밀영역 반경 [um]
R_GROW = 1.20
DZ_SC = 2.5             # 각질층 요소 [um]
DZ_EPI = 10.0
DZ_DTOP = 10.0
Z_GROW = 1.30

# --- 중공 니들 (um) ---
R_OUT = 150.0           # 샤프트 외경
R_TIP = 50.0            # 첨두 외경(테이퍼)
R_BORE = 30.0           # 내경(bore=구멍) 반경 -> 축에 구멍 유지
GAP = 50.0              # 피부 상면 위 초기 간격
PUSH = 1200.0           # 니들 하강량 [um]

# 층별 재료 (VUMAT): C10[MPa], D1[1/MPa], lam_d, lam_f  (값 불변)
MAT = {
    "STRATUM":   ("1.2e-15", "1.0, 0.02, 1.2, 1.5"),
    "EPIDERMIS": ("1.1e-15", "0.1, 0.1, 1.4, 1.9"),
    "DERMIS":    ("1.1e-15", "0.02, 1.0, 1.6, 2.5"),
}
JSTR = 100000


def build_x():
    xs = [0.0]
    for k in range(1, int(round(R_FINE / DR_FINE)) + 1):
        xs.append(round(DR_FINE * k, 4))
    x, dx = xs[-1], DR_FINE
    while x < R_MAX - EPS:
        dx *= R_GROW
        x += dx
        xs.append(round(min(x, R_MAX), 4))
    return xs


def build_z():
    zs = {round(Z_EPI, 4)}
    z, dz = Z_EPI, DZ_DTOP
    while z > EPS:                       # 진피: 상단에서 아래로 성김
        dz *= Z_GROW
        z -= dz
        zs.add(round(max(z, 0.0), 4))
    z = Z_EPI                            # 표피
    while z < Z_SC - EPS:
        z += DZ_EPI
        zs.add(round(min(z, Z_SC), 4))
    z = Z_SC                             # 각질층
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


def main():
    xs, zs = build_x(), build_z()
    nx, nz = len(xs), len(zs)

    def nid(i, j):
        return 1 + i + JSTR * j

    L = []
    w = L.append
    w("*HEADING")
    w("Hollow microneedle into 3-layer skin (um units, axisymmetric)")
    w("Units: um, uN, MPa, s  (hollow needle: open bore + annular tip surface)")

    w("*NODE")
    for j, z in enumerate(zs):
        for i, x in enumerate(xs):
            w("%d, %.4f, %.4f" % (nid(i, j), x, z))

    conn, elems = [], {"STRATUM": [], "EPIDERMIS": [], "DERMIS": []}
    e = 0
    for j in range(nz - 1):
        lay = layer(0.5 * (zs[j] + zs[j + 1]))
        for i in range(nx - 1):
            e += 1
            conn.append((e, nid(i, j), nid(i + 1, j),
                         nid(i + 1, j + 1), nid(i, j + 1)))
            elems[lay].append(e)
    w("*ELEMENT, TYPE=CAX4R")
    for (e, a, b, c, d) in conn:
        w("%d, %d, %d, %d, %d" % (e, a, b, c, d))

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
    w("*ELSET, ELSET=SKIN_ALL")
    w("STRATUM, EPIDERMIS, DERMIS")
    w("*SURFACE, TYPE=ELEMENT, NAME=SKIN_SURF")
    w("SKIN_ALL,")
    wl("NBOT", [nid(i, 0) for i in range(nx)], "NSET")
    wl("NAXIS", [nid(0, j) for j in range(nz)], "NSET")
    wl("NRIGHT", [nid(nx - 1, j) for j in range(nz)], "NSET")

    # ---- 중공 니들: 환형 벽(유한 두께) 해석적 강체 ----
    # open 프로파일 START(외경,위)->외벽 아래->테이퍼->첨두면(외->내)->
    #   내벽(bore) 위. 진행방향 왼쪽=외향법선이 피부/보어를 향함.
    zt = Z_TOP + GAP                    # 첨두 z (피부 위 GAP)
    w("*NODE")
    w("9999, 0.0, %.4f" % zt)
    w("*NSET, NSET=NREF")
    w("9999,")
    w("*SURFACE, TYPE=SEGMENTS, NAME=NEEDLE, FILLET RADIUS=10.0")
    w("START, %.2f, %.2f" % (R_OUT, zt + 2000.0))     # 외벽 top
    w("LINE,  %.2f, %.2f" % (R_OUT, zt + 300.0))       # 외벽(샤프트)
    w("LINE,  %.2f, %.2f" % (R_TIP, zt))               # 외벽 테이퍼->첨두외경
    w("LINE,  %.2f, %.2f" % (R_BORE, zt))              # 환형 첨두면(외->내)
    w("LINE,  %.2f, %.2f" % (R_BORE, zt + 2000.0))     # 내벽(bore, 구멍 유지)
    w("*RIGID BODY, ANALYTICAL SURFACE=NEEDLE, REF NODE=NREF")

    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
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
    for lay in ("STRATUM", "EPIDERMIS", "DERMIS"):
        w("*SOLID SECTION, ELSET=%s, MATERIAL=MAT_%s" % (lay, lay))

    w("*SURFACE INTERACTION, NAME=IPROP")
    w("*FRICTION")
    w("0.1,")
    w("*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=HARD")

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
    w("*BOUNDARY, AMPLITUDE=PUSH")
    w("NREF, 2, 2, %.1f" % (-PUSH))
    w("*CONTACT")
    w("*CONTACT INCLUSIONS, ALL EXTERIOR")
    w("*CONTACT INCLUSIONS")
    w("NEEDLE, SKIN_SURF")
    w("*CONTACT PROPERTY ASSIGNMENT")
    w(" ,  , IPROP")
    w("*OUTPUT, FIELD, NUMBER INTERVAL=30")
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

    with open("10_microneedle_um.inp", "w") as f:
        f.write("\n".join(L) + "\n")
    ne = sum(len(v) for v in elems.values())
    print("wrote 10_microneedle_um.inp : %d nodes, %d elems "
          "(r-nodes=%d, z-nodes=%d)" % (nx * nz, ne, nx, nz))
    print("  hollow needle: bore R=%.0f, tip R=%.0f..%.0f, shaft R=%.0f um"
          % (R_BORE, R_BORE, R_TIP, R_OUT))
    print("  near-axis dr=%.1f um, SC dz=%.1f um" % (DR_FINE, DZ_SC))


if __name__ == "__main__":
    main()
