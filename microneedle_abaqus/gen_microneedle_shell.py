# -*- coding: utf-8 -*-
# ======================================================================
#  gen_microneedle_shell.py  ->  14_microneedle_shell.inp
#
#  [작업 A-2] 사용자 요청 반영: 니들을 "1D 강체선(RAX2)"에서
#  "두께를 갖는 변형 가능한 축대칭 2D 요소(CAX4R)"로 교체.
#
#   * CAE 용어: 축대칭 shell 파트(=r-z 평면의 2D 면) + Solid section.
#     이 2D 면의 "폭"이 곧 니들 벽 두께 -> 화면에서 실제로 두껍게 보임
#     (1D 와이어는 shell property, 2D 면은 solid property 로 정의).
#   * 실제 벽 단면(가변 두께)을 그대로 2D 로 채움: 내경 R_IN=30 일정,
#     외경은 팁 R_TIP=50 -> 테이퍼 -> 샤프트 R_OUT=150. solid section
#     이므로 두께 property 불필요(면의 기하 폭이 곧 벽 두께).
#   * 변형 가능(니들 물성 E,nu,rho 부여). 상단 모서리를 참조점 9999에
#     운동학적 결합(*KINEMATIC COUPLING) -> 강체 액추에이터로 하강 구동
#     (참조점 RF2 = 총 삽입력, postprocess.py 의 NREF 규약과 호환).
#
#  주의: 축대칭은 좌굴/굽힘(비축대칭)을 못 잡음 -> 축방향 압축·반경변형만.
#        측면 좌굴은 03_needle_buckling 이 담당.
#  피부: 모델 11 과 동일한 3층 + 요소삭제 VUMAT(vumat_skin.f).
#
#  단위: 길이 um, 응력 MPa, 힘 uN, 질량 kg, 시간 s
#  실행: python gen_microneedle_shell.py
#    abaqus job=mn14 input=14_microneedle_shell.inp user=vumat_skin.f \
#           double=both cpus=4 interactive
# ======================================================================
EPS = 1.0e-9

# --- 피부 (um) : 3층 (모델 11 과 동일) ---
Z_TOP, Z_SC, Z_EPI = 1500.0, 1480.0, 1400.0
R_MAX = 2000.0
DR_FINE = 5.0
R_FINE = 300.0
R_GROW = 1.20
DZ_SC = 2.5
DZ_EPI = 10.0
DZ_DTOP = 10.0
Z_GROW = 1.30

# --- 변형 니들 (um) : 실제 벽 단면(가변 두께)을 2D 로 채움 ---
#  2D 면 + solid section 이므로 "두께"는 메시된 면의 기하 폭 -> 균일두께
#  불필요. 실제 형상(두꺼운 샤프트 R_OUT -> 얇은 환형 팁)을 그대로 사용.
R_IN = 30.0             # 내경(bore, 일정) -> 벽 안쪽 경계
R_TIP = 50.0            # 팁 외경 -> 팁 벽두께 = R_TIP-R_IN = 20um
R_OUT = 150.0           # 샤프트 외경 -> 샤프트 벽두께 = 120um
NW = 4                  # 벽두께방향 요소수(팁 dr=5um, 샤프트 dr=30um)
GAP = 50.0              # 피부 상면 위 초기간격
PUSH = 1200.0           # 니들 하강량
H_NDL = 2000.0          # 니들 높이(팁 기준)
TAPER_H = 300.0         # 외벽 테이퍼 높이(팁 R_TIP -> 샤프트 R_OUT)
DZ_TIP = 5.0            # 팁 근처 축방향 요소크기
DZ_MAX = 40.0           # 상부 축방향 최대 요소크기
DZ_GROW = 1.15

# 니들 물성 (스테인리스강 예시): E[MPa], nu, rho[kg/um^3]
NDL_E = 200000.0
NDL_NU = 0.3
NDL_RHO = "7.9e-15"

# 층별 재료 (VUMAT): C10[MPa], D1[1/MPa], lam_d, lam_f
MAT = {
    "STRATUM":   ("1.2e-15", "1.0, 0.02, 1.2, 1.5"),
    "EPIDERMIS": ("1.1e-15", "0.1, 0.1, 1.4, 1.9"),
    "DERMIS":    ("1.1e-15", "0.02, 1.0, 1.6, 2.5"),
}
JSTR = 100000


# ---------------------------------------------------------------- 피부 격자
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


# ------------------------------------------------------------- 니들 z-격자
def needle_z():
    zt = Z_TOP + GAP
    zn, z, dz = [zt], zt, DZ_TIP
    while z < zt + H_NDL - EPS:
        z = min(z + dz, zt + H_NDL)
        zn.append(round(z, 4))
        dz = min(dz * DZ_GROW, DZ_MAX)
    return zn, zt


def r_out_at(z, zt):
    """외벽: 팁(z=zt) R_TIP -> 테이퍼 -> 샤프트(z>=zt+TAPER_H) R_OUT."""
    if z >= zt + TAPER_H:
        return R_OUT
    return R_TIP + (R_OUT - R_TIP) * (z - zt) / TAPER_H


# ------------------------------------------------------------------- 조립
def main():
    xs, zs = build_x(), build_z()
    nx, nz = len(xs), len(zs)

    def nid(i, j):
        return 1 + i + JSTR * j

    L = []
    w = L.append
    w("*HEADING")
    w("[A-2] Deformable thick-wall shell microneedle (CAX4R tube)")
    w("Units: um, uN, MPa, s ; needle=deformable 2D solid, wall=20um")

    # ---- 피부 절점/요소 ----
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

    # ---- 변형 니들 : CAX4R 튜브 ----
    zn, zt = needle_z()
    nrows = len(zn)
    nmax = nid(nx - 1, nz - 1)
    nbase = ((nmax // 1000000) + 2) * 1000000
    ebase = 800000
    zstr = 1000                      # 니들 z-행 절점 증분

    def Nid(i, j):
        return nbase + i + zstr * j

    w("**")
    w("** --- Deformable needle wall as 2D solid (CAX4R, variable wall) ---")
    w("**  R_in=%.0f (bore) ; outer R_tip=%.0f -> taper %.0fum -> R_out=%.0f"
      % (R_IN, R_TIP, TAPER_H, R_OUT))
    w("*NODE")
    for j, z in enumerate(zn):
        ro = r_out_at(z, zt)
        for i in range(NW + 1):
            r = R_IN + (ro - R_IN) * i / NW
            w("%d, %.4f, %.4f" % (Nid(i, j), r, z))
    # 참조(제어)점: 축상 상단
    w("%d, 0.0, %.4f" % (9999, zt + H_NDL))
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
    # 상단 모서리 노드집합/노드기반 표면 -> 참조점 결합(강체 그립)
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

    # ---- 결합(상단 모서리 -> 참조점 9999) : Explicit 은 *COUPLING+*KINEMATIC
    #  (*KINEMATIC COUPLING 단독 키워드는 Standard 전용) ----
    w("*COUPLING, CONSTRAINT NAME=NDL_GRIP, REF NODE=9999, SURFACE=NDLTOP_S")
    w("*KINEMATIC")
    w("1, 2")

    # ---- 접촉 상호작용(모델 데이터: 첫 *STEP 앞) ----
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
    w("*ELEMENT OUTPUT, ELSET=NEEDLE_EL")
    w("S, LE")
    w("*NODE OUTPUT")
    w("U, V")
    w("*OUTPUT, HISTORY, TIME INTERVAL=1.0e-4")
    w("*NODE OUTPUT, NSET=NREF")
    w("U2, V2, RF2")
    w("*ENERGY OUTPUT")
    w("ALLIE, ALLKE, ALLSE, ALLWK")
    w("*END STEP")

    with open("14_microneedle_shell.inp", "w") as f:
        f.write("\n".join(L) + "\n")
    ne = sum(len(v) for v in elems.values())
    print("wrote 14_microneedle_shell.inp : skin %d nodes / %d elems"
          % (nx * nz, ne))
    print("  needle: deformable CAX4R wall, %d nodes / %d elems "
          "(across-wall=%d elems, rows=%d)"
          % ((NW + 1) * nrows, len(ndl_el), NW, nrows))
    print("  bore R=%.0f ; wall: tip %.0fum -> shaft %.0fum ; E=%.0f MPa"
          % (R_IN, R_TIP - R_IN, R_OUT - R_IN, NDL_E))


if __name__ == "__main__":
    main()
