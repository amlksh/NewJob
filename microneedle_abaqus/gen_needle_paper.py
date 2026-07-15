# -*- coding: utf-8 -*-
# ======================================================================
#  gen_needle_paper.py  ->  17_needle_paper.inp
#
#  [모델 17] 논문(Yolai et al., Mater. & Design 259 (2025) 114936) 정렬 모델.
#  접촉 투과 문제 해결 방향: cohesive 를 버리고 "순수 요소삭제"로 회귀.
#
#   * 피부 2층: 표피(epidermis 0.1mm) + 진피(dermis 2.4mm), 1차 Ogden 초탄성.
#   * 파단: von Mises 응력 OR 등가변형 기준의 요소삭제(vumat_skin_ogden.f).
#     -> cohesive 없음. debond-vs-delete 충돌·stabilization 고착 문제 원천 제거.
#   * 접촉: General Contact ALL EXTERIOR(삭제 노출면 자동 포함) + 마찰 0.42(논문).
#     stabilization/contact damping 미사용.
#   * 접촉부 메쉬 세밀(최소 8um, 논문 mesh sensitivity) -> 삭제 진동 감소.
#   * 니들: 원뿔 강체(팁경 0.04, 기저경 0.3, 높이 1.2mm, 팁각~14deg).
#
#  단위: mm, N, MPa, tonne, s (논문과 동일).
#  실행: python gen_needle_paper.py
#    abaqus job=np17 input=17_needle_paper.inp user=vumat_skin_ogden.f \
#           double=both cpus=4 interactive
# ======================================================================
EPS = 1.0e-9

# --- 피부 2층 (mm) ---
Z_TOP = 2.5            # 상면
Z_ED = 2.4            # 표피-진피 경계 (표피 0.1mm)
R_MAX = 2.0
DR_FINE = 0.008       # 접촉부 반경 요소크기 [mm] (=8um, 논문)
R_FINE = 0.25         # 세밀영역 반경
R_GROW = 1.20
DZ_FINE = 0.008       # 상면(표피) 요소크기 [mm]
DZ_INS = 0.020        # 삽입 경로 요소크기 [mm] (전체 깊이 세밀 유지)
Z_GROW = 1.18

GAP = 0.05            # 피부 상면 위 초기간격 [mm]
PUSH = 1.0            # 니들 하강량 [mm]
Z_FINE_BOT = 2.5 - 1.0 - 0.15   # 삽입 깊이(=Z_TOP-PUSH-여유)까지 세밀 유지

# 니들(원뿔 강체) [mm]
R_TIPN = 0.02         # 팁 반경(팁경 0.04)
R_BASE = 0.15         # 기저 반경(기저경 0.3)
H_CONE = 1.2          # 원뿔 높이

# 층 재료 (Ogden VUMAT): mu[MPa], alpha, D1[1/MPa], sigf[MPa], epsf ; 밀도
#  주의: 논문 D1=1.03e-7 은 SI(1/Pa). MPa 단위 변환 -> D1=0.103 /MPa
#  (K=2/D1=19.4 MPa, Poisson~0.48). 1e-7 그대로 쓰면 K=19.4 GPa -> 관성폭주.
MAT = {
    "EPIDERMIS": ("1.3e-9", "0.752, 8.68, 0.103, 5.8, 0.084"),
    "DERMIS":    ("1.2e-9", "7.33, 57.89, 0.103, 15.0, 0.45"),
}
JSTR = 100000


def build_x():
    xs = [0.0]
    for k in range(1, int(round(R_FINE / DR_FINE)) + 1):
        xs.append(round(DR_FINE * k, 6))
    x, dx = xs[-1], DR_FINE
    while x < R_MAX - EPS:
        dx *= R_GROW
        x += dx
        xs.append(round(min(x, R_MAX), 6))
    return xs


def build_z():
    # 상면(z=Z_TOP)에서 세밀 -> 삽입 경로 전체 깊이(Z_FINE_BOT) 세밀 유지
    # -> 하부로 성김. 표피/삽입 경계는 정확히 포함.
    zs = {round(Z_TOP, 6), round(Z_ED, 6), round(Z_FINE_BOT, 6), 0.0}
    z, dz = Z_TOP, DZ_FINE
    while z > EPS:
        z -= dz
        zs.add(round(max(z, 0.0), 6))
        if z > Z_FINE_BOT:
            dz = min(dz * 1.10, DZ_INS)     # 삽입 경로: 세밀 유지(<=20um)
        else:
            dz = min(dz * Z_GROW, 0.15)     # 하부: 성김
    return sorted(zs)


def layer(zmid):
    return "EPIDERMIS" if zmid >= Z_ED else "DERMIS"


def main():
    xs, zs = build_x(), build_z()
    nx, nz = len(xs), len(zs)

    def nid(i, j):
        return 1 + i + JSTR * j

    L = []
    w = L.append
    w("*HEADING")
    w("[17] Paper-aligned (Yolai 2025): Ogden 2-layer skin, pure deletion")
    w("Units: mm, N, MPa, tonne, s ; von Mises + strain failure, no cohesive")

    w("*NODE")
    for j, z in enumerate(zs):
        for i, x in enumerate(xs):
            w("%d, %.6f, %.6f" % (nid(i, j), x, z))

    conn, elems = [], {"EPIDERMIS": [], "DERMIS": []}
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

    for lay in ("EPIDERMIS", "DERMIS"):
        wl(lay, elems[lay], "ELSET")
    w("*ELSET, ELSET=SKIN_ALL")
    w("EPIDERMIS, DERMIS")
    # 내부 요소면까지 접촉 대상에 강제 포함: 요소 4면(S1~S4) 모두 명시.
    #  (element set 만 주면 자유면=외곽만 생성 -> 삭제 노출 내부면 누락.)
    #  4면 전부 포함 -> 삭제 순간 내부면이 이미 접촉 도메인에 있어 연속 접촉.
    w("*SURFACE, TYPE=ELEMENT, NAME=SKIN_SURF")
    w("SKIN_ALL, S1")
    w("SKIN_ALL, S2")
    w("SKIN_ALL, S3")
    w("SKIN_ALL, S4")
    wl("NBOT", [nid(i, 0) for i in range(nx)], "NSET")
    wl("NAXIS", [nid(0, j) for j in range(nz)], "NSET")
    wl("NRIGHT", [nid(nx - 1, j) for j in range(nz)], "NSET")

    # ---- 원뿔 니들 : 이산 강체(CAX4R rigid) - 요소기반 표면 ----
    #  해석적 강체는 침식 노출면 접촉이 불안정 -> 양쪽 요소기반으로 통일.
    #  blunt 둥근 팁(반경 R_TIPN, 축 중심), 원뿔 -> 기저 R_BASE.
    zt = Z_TOP + GAP
    H_NDL = 1.5
    NW_N = 5
    smax = nid(nx - 1, nz - 1)                  # 피부 최대 절점번호
    nbase = ((smax // 1000000) + 2) * 1000000   # 피부 범위 위로 이격(충돌 방지)
    zstr = 1000

    def Nid(i, j):
        return nbase + i + zstr * j

    znn, z, dz = [zt], zt, 0.008
    while z < zt + H_NDL - EPS:
        z = min(z + dz, zt + H_NDL)
        znn.append(round(z, 6))
        dz = min(dz * 1.2, 0.1)

    def rout_n(z):
        t = (z - zt) / H_CONE
        if t > 1.0:
            t = 1.0
        return R_TIPN + (R_BASE - R_TIPN) * t

    w("*NODE")
    for j, z in enumerate(znn):
        ro = rout_n(z)
        for i in range(NW_N + 1):
            w("%d, %.6f, %.6f" % (Nid(i, j), ro * i / NW_N, z))
    w("9999, 0.0, %.6f" % (zt + H_NDL))
    w("*NSET, NSET=NREF")
    w("9999,")
    w("*ELEMENT, TYPE=CAX4R")
    ndl = []
    for j in range(len(znn) - 1):
        for i in range(NW_N):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Nid(i, j), Nid(i + 1, j),
                                      Nid(i + 1, j + 1), Nid(i, j + 1)))
            ndl.append(e)
    w("*ELSET, ELSET=NEEDLE_EL, GENERATE")
    w("%d, %d, 1" % (ndl[0], ndl[-1]))
    w("*SURFACE, TYPE=ELEMENT, NAME=NEEDLE")
    w("NEEDLE_EL,")
    w("*RIGID BODY, ELSET=NEEDLE_EL, REF NODE=NREF")

    # ---- 재료 (Ogden VUMAT + 요소삭제) ----
    w("*MATERIAL, NAME=NEEDLE_MAT")
    w("*DENSITY")
    w("7.9e-9,")
    w("*ELASTIC")
    w("200000.0, 0.3")
    w("*SOLID SECTION, ELSET=NEEDLE_EL, MATERIAL=NEEDLE_MAT")
    for lay in ("EPIDERMIS", "DERMIS"):
        rho, cst = MAT[lay]
        w("*MATERIAL, NAME=MAT_%s" % lay)
        w("*DENSITY")
        w("%s," % rho)
        w("*USER MATERIAL, CONSTANTS=5")
        w(cst)
        w("*DEPVAR, DELETE=1")
        w("4")
        w("1, DELFLAG, deletion flag")
        w("2, SVM, von Mises stress")
        w("3, EEQ, equivalent log strain")
        w("4, JVOL, relative volume")
    # 삭제 요소 대응: enhanced hourglass(연조직 안정)
    w("*SECTION CONTROLS, NAME=SKINCTRL, HOURGLASS=ENHANCED")
    for lay in ("EPIDERMIS", "DERMIS"):
        w("*SOLID SECTION, ELSET=%s, MATERIAL=MAT_%s, CONTROLS=SKINCTRL"
          % (lay, lay))

    # ---- 접촉 상호작용(모델 데이터): 마찰 0.42, hard ----
    w("*SURFACE INTERACTION, NAME=IPROP")
    w("*FRICTION")
    w("0.42,")
    w("*SURFACE BEHAVIOR, PRESSURE-OVERCLOSURE=HARD")

    # ---- 경계(측면·하면 encastre, 축 대칭) ----
    w("*BOUNDARY")
    w("NBOT, 1, 2")
    w("NRIGHT, 1, 2")
    w("NAXIS, 1, 1")
    w("NREF, 1, 1")
    w("NREF, 6, 6")
    w("*AMPLITUDE, NAME=PUSH, DEFINITION=SMOOTH STEP")
    w("0.0, 0.0, 0.04, 1.0")
    w("*STEP, NAME=INSERTION")
    w("*DYNAMIC, EXPLICIT")
    w(", 0.04")
    # 준정적: D1 정상화로 안정증분↑ -> 질량스케일링 축소(관성↓). 하중도 느리게.
    w("*FIXED MASS SCALING, DT=2.0e-7, TYPE=BELOW MIN")
    w("*BOUNDARY, AMPLITUDE=PUSH")
    w("NREF, 2, 2, %.4f" % (-PUSH))
    w("*CONTACT")
    # SKIN_SURF(내부면 포함) 를 니들과 명시 접촉 -> 삭제 노출 내부면 접촉.
    # ALL EXTERIOR 는 니들 외곽 등 나머지 자기접촉 보강.
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

    with open("17_needle_paper.inp", "w") as f:
        f.write("\n".join(L) + "\n")
    ne = sum(len(v) for v in elems.values())
    print("wrote 17_needle_paper.inp : skin %d nodes / %d elems (r=%d, z=%d)"
          % (nx * nz, ne, nx, nz))
    print("  2-layer Ogden(표피/진피), pure element deletion(vMises+strain)")
    print("  needle cone: tip R=%.3f, base R=%.3f, H=%.1f mm ; friction 0.42"
          % (R_TIPN, R_BASE, H_CONE))
    print("  contact-region dr=dz=%.3f mm (=%.0f um) ; needs user=vumat_skin_ogden.f"
          % (DR_FINE, DR_FINE * 1000))


if __name__ == "__main__":
    main()
