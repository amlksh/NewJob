# -*- coding: utf-8 -*-
# ======================================================================
#  gen_microneedle_discrete.py  ->  11_microneedle_discrete.inp
#
#  [작업 A] 전문가 피드백 1번 반영: 해석적 강체 -> "이산 강체(Discrete
#  Rigid)" 중공 니들 + 접촉 필렛(팁 에지 둥글림).
#
#   - 니들 벽을 RAX2(2절점 축대칭 강체요소)로 이산화한 표면으로 모사.
#     * TYPE=ELEMENT 강체표면은 Abaqus/Explicit '일반접촉'에서 자동으로
#       "양면(two-sided)"으로 취급됨 -> 피부가 외벽/내벽(bore) 양쪽과
#       접촉 가능(중공 니들의 핵심). 해석적 강체는 단면만 가능.
#   - 팁 에지(외측/내측 코너)를 "원호 노드열"로 물리적으로 둥글림.
#     해석적 강체의 FILLET RADIUS 대응물 -> 이산표면은 기하학적으로
#     둥글려야 접촉 응력집중/튐(chatter)을 없앰. (당신 '팁1' 지적 반영)
#   - 마이크로 단위계(um, uN, MPa, s), 근축 접촉부 피부 dr=5um.
#
#  재료: 요소삭제 VUMAT(vumat_skin.f) 유지 -> 니들/접촉 안정성 검증이
#        목적. (매끈절개=cohesive 는 작업 B/C 에서 다룸.)
#
#  단위: 길이 um, 응력 MPa(=uN/um^2), 힘 uN, 질량 kg, 시간 s
#  실행: python gen_microneedle_discrete.py
#    abaqus job=mn11 input=11_microneedle_discrete.inp user=vumat_skin.f \
#           double=both cpus=4 interactive
# ======================================================================
import math

EPS = 1.0e-9

# --- 피부 (um) : 3층 ---
Z_TOP, Z_SC, Z_EPI = 1500.0, 1480.0, 1400.0     # 상면/각질-표피/표피-진피
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
R_TIP = 50.0            # 첨두 외경(테이퍼 끝)
R_BORE = 30.0           # 내경(bore=구멍) 반경
GAP = 50.0              # 피부 상면 위 초기 간격
PUSH = 1200.0           # 니들 하강량 [um]
H_TOP = 2000.0          # 외벽/보어 상단 높이(팁 기준)
H_TAP = 300.0           # 샤프트->테이퍼 전이 높이(팁 기준)
H_BORE = 2000.0         # 보어 벽 높이(팁 기준)
RF_OUT = 8.0            # 외측 팁코너 필렛반경 [um]
RF_IN = 5.0             # 내측 팁코너(보어 입구) 필렛반경 [um]
# 니들 표면 이산화 요소크기 [um] (접촉활성부는 피부보다 촘촘하게)
SZ_SHAFT = 30.0         # 외벽 수직 샤프트
SZ_TAPER = 5.0          # 테이퍼(접촉 활성)
SZ_FACE = 3.0           # 환형 첨두면(접촉 활성, 최세밀)
SZ_BORE = 25.0          # 보어 벽
NSEG_ARC = 8            # 필렛 원호 분할수

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
    while z > EPS:                       # 진피
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


# ------------------------------------------------ 니들 프로파일(필렛 원호)
def _unit(dx, dz):
    L = math.hypot(dx, dz)
    return (dx / L, dz / L), L


def _fillet_arc(P0, P1, P2, rf, nseg):
    """코너 P1(이웃 P0,P2)을 반경 rf 원호로 둥글림.
    반환: (T0, [arc 내부점...], T2)  T0=P0쪽 접점, T2=P2쪽 접점."""
    (u0x, u0z), L0 = _unit(P0[0] - P1[0], P0[1] - P1[1])
    (u2x, u2z), L2 = _unit(P2[0] - P1[0], P2[1] - P1[1])
    dot = max(-1.0, min(1.0, u0x * u2x + u0z * u2z))
    half = math.acos(dot) / 2.0
    d = rf / math.tan(half)              # 접점까지 변길이
    d = min(d, 0.45 * L0, 0.45 * L2)     # 이웃변/필렛 침범 방지
    rf_eff = d * math.tan(half)
    T0 = (P1[0] + u0x * d, P1[1] + u0z * d)
    T2 = (P1[0] + u2x * d, P1[1] + u2z * d)
    (bxn, bzn), _ = _unit(u0x + u2x, u0z + u2z)   # 이등분선(코너 안쪽)
    C = (P1[0] + bxn * rf_eff / math.sin(half),
         P1[1] + bzn * rf_eff / math.sin(half))
    a0 = math.atan2(T0[1] - C[1], T0[0] - C[0])
    a2 = math.atan2(T2[1] - C[1], T2[0] - C[0])
    da = a2 - a0
    while da > math.pi:
        da -= 2 * math.pi
    while da < -math.pi:
        da += 2 * math.pi
    pts = []
    for k in range(1, nseg):
        a = a0 + da * k / nseg
        pts.append((C[0] + rf_eff * math.cos(a), C[1] + rf_eff * math.sin(a)))
    return T0, pts, T2


def build_needle_profile():
    """중공 니들 벽 프로파일(외벽 상단->테이퍼->환형첨두->보어벽 상단)을
    필렛 원호를 포함해 좌표점 리스트로 반환."""
    zt = Z_TOP + GAP
    V = [(R_OUT, zt + H_TOP),       # 0 외벽 상단
         (R_OUT, zt + H_TAP),       # 1 샤프트-테이퍼 전이
         (R_TIP, zt),               # 2 외측 팁코너   (필렛 RF_OUT)
         (R_BORE, zt),              # 3 내측 팁코너   (필렛 RF_IN)
         (R_BORE, zt + H_BORE)]     # 4 보어 상단
    seg_size = [SZ_SHAFT, SZ_TAPER, SZ_FACE, SZ_BORE]
    fillet = {2: RF_OUT, 3: RF_IN}

    arcs = {}
    for v, rf in fillet.items():
        arcs[v] = _fillet_arc(V[v - 1], V[v], V[v + 1], rf, NSEG_ARC)

    P = []

    def push(pt):
        # 4자리 반올림 후 비교(허용오차 1e-3 um) -> 접점/원호 이음부의
        # 부동소수 잔차로 생기는 0-길이(중복) RAX2 요소 방지.
        r, z = round(pt[0], 4), round(pt[1], 4)
        if not P or abs(P[-1][0] - r) > 1e-3 or abs(P[-1][1] - z) > 1e-3:
            P.append((r, z))

    def straight(A, B, size):
        L = math.hypot(B[0] - A[0], B[1] - A[1])
        n = max(1, int(round(L / size)))
        for k in range(n + 1):
            t = float(k) / n
            push((A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t))

    cur = V[0]
    for i in range(len(V) - 1):
        B = arcs[i + 1][0] if (i + 1) in arcs else V[i + 1]
        straight(cur, B, seg_size[i])
        if (i + 1) in arcs:
            _, pts, T2 = arcs[i + 1]
            for p in pts:
                push(p)
            push(T2)
            cur = T2
        else:
            cur = V[i + 1]
    return P, zt


# ------------------------------------------------------------------- 조립
def main():
    xs, zs = build_x(), build_z()
    nx, nz = len(xs), len(zs)

    def nid(i, j):
        return 1 + i + JSTR * j

    L = []
    w = L.append
    w("*HEADING")
    w("[A] Discrete-rigid hollow microneedle -> 3-layer skin (um, axisym)")
    w("Units: um, uN, MPa, s ; needle=RAX2 discrete rigid, two-sided contact")

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

    # ---- 이산 강체(Discrete Rigid) 중공 니들 : RAX2 ----
    prof, zt = build_needle_profile()
    nmax = nid(nx - 1, nz - 1)
    nbase = ((nmax // 1000000) + 2) * 1000000     # 피부 절점번호 위로 이격
    ebase = 800000
    w("**")
    w("** --- Discrete rigid hollow needle (RAX2, filleted tip) ---")
    w("**  outer wall R=%.0f -> taper -> annular tip (R=%.0f..%.0f) -> "
      "bore wall R=%.0f" % (R_OUT, R_BORE, R_TIP, R_BORE))
    w("**  tip corners rounded: outer rf=%.0f, inner rf=%.0f um" % (RF_OUT, RF_IN))
    w("*NODE")
    for m, (r, z) in enumerate(prof):
        w("%d, %.4f, %.4f" % (nbase + m, r, z))
    w("%d, 0.0, %.4f" % (9999, zt))               # 참조점(팁 중심축)
    w("*NSET, NSET=NREF")
    w("9999,")
    w("*ELEMENT, TYPE=RAX2, ELSET=NEEDLE_EL")
    for m in range(len(prof) - 1):
        w("%d, %d, %d" % (ebase + m, nbase + m, nbase + m + 1))
    # 이산요소 -> 강체(참조점 9999가 강체 운동 제어)
    w("*RIGID BODY, REF NODE=NREF, ELSET=NEEDLE_EL")
    # 요소기반 강체표면 -> 일반접촉에서 자동 양면 처리
    w("*SURFACE, TYPE=ELEMENT, NAME=NEEDLE")
    w("NEEDLE_EL,")

    # ---- 재료 ----
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
    w("*NODE OUTPUT")
    w("U, V")
    w("*OUTPUT, HISTORY, TIME INTERVAL=1.0e-4")
    w("*NODE OUTPUT, NSET=NREF")
    w("U2, V2, RF2")
    w("*ENERGY OUTPUT")
    w("ALLIE, ALLKE, ALLSE, ALLWK")
    w("*END STEP")

    with open("11_microneedle_discrete.inp", "w") as f:
        f.write("\n".join(L) + "\n")
    ne = sum(len(v) for v in elems.values())
    print("wrote 11_microneedle_discrete.inp : skin %d nodes / %d elems "
          "(r=%d, z=%d)" % (nx * nz, ne, nx, nz))
    print("  needle: RAX2 discrete rigid, %d nodes / %d elems, "
          "tip fillet out=%.0f in=%.0f um" % (len(prof), len(prof) - 1,
                                              RF_OUT, RF_IN))
    print("  needle node base=%d, elem base=%d" % (nbase, ebase))


if __name__ == "__main__":
    main()
