# -*- coding: utf-8 -*-
# ======================================================================
#  gen_cohesive.py   ->  07_cohesive_cut.inp
#
#  (4) 요소 삭제 대신 "cohesive 층"으로 절개를 모사하는 대안 모델.
#
#  평면변형(plane strain) 피부 블록의 중앙(x=0)에 두께 0 cohesive 층을
#  삽입하고, 강체 쐐기(니들)가 위에서 내려오며 cohesive 를 견인-분리
#  (traction-separation + 에너지기반 손상)시켜 조직을 가르는 과정을 모사.
#
#  장점 : 균열 경로가 사전 정의(x=0)되어 메쉬 지그재그/질량손실이 없고
#         파단에너지 Gc 가 물리량으로 직접 입력됨.
#  한계 : 균열 경로를 미리 알아야 함(직삽입에 적합). 벌크는 파단 없음.
#
#  벌크는 Abaqus 내장 Neo-Hookean -> 서브루틴 불필요(단독 실행 가능).
#
#  실행:  python gen_cohesive.py
# ======================================================================

W = 1.0            # 반폭 [mm] (전체 폭 2W)
H = 1.2            # 높이 [mm]
NH = 15            # 반폭 요소수 (x=0 근처 세밀)
NZ = 16            # 깊이 요소수 (상면 근처 세밀)
XG = 1.15          # 수평 성장비 (중앙->바깥)
ZG = 1.18          # 수직 성장비 (상면->하부)
STR = 1000         # 절점 z-행 증분
OFF = 1000000      # 우측 블록 절점 오프셋
EPS = 1.0e-9


def _biased(total, n, ratio):
    """[0,total] 을 n구간으로, 첫 구간이 가장 작은(세밀) 기하급수 분할.
    끝점을 정확히 맞춰 슬리버 요소가 생기지 않도록 정규화."""
    s0 = total * (ratio - 1.0) / (ratio ** n - 1.0)
    coords = [0.0]
    c = 0.0
    for k in range(n):
        c += s0 * ratio ** k
        coords.append(round(c, 6))
    coords[-1] = round(total, 6)
    return coords


def half_x():
    # 중앙(x=0)에서 세밀 -> 바깥으로 성김
    return _biased(W, NH, XG)


def zlevels():
    # 상면(z=H)에서 세밀 -> 하부로 성김
    d = _biased(H, NZ, ZG)               # 0(세밀)->H
    zs = sorted(round(H - x, 6) for x in d)
    zs[0] = 0.0
    zs[-1] = round(H, 6)
    return zs


def main():
    hx = half_x()
    nH = len(hx) - 1                     # 반폭 요소수
    zs = zlevels()
    nz = len(zs) - 1

    # 좌/우 블록 x좌표 (x=0 공유 열은 각각 별도 절점)
    xl = [round(-hx[nH - i], 6) for i in range(nH + 1)]   # -W .. 0
    xr = [round(hx[i], 6) for i in range(nH + 1)]         # 0 .. W

    def Lid(i, j):
        return 1 + i + STR * j

    def Rid(i, j):
        return OFF + i + STR * j

    L = []
    w = L.append
    w("*HEADING")
    w("(4) Cohesive-layer cutting - plane strain, needle wedge splits skin")
    w("Bulk: built-in Neo-Hookean; center x=0: cohesive traction-separation")
    w("Units: mm, N, MPa, tonne, s")

    # ---- 절점 ----
    w("*NODE")
    for j, z in enumerate(zs):
        for i in range(nH + 1):
            w("%d, %.6f, %.6f" % (Lid(i, j), xl[i], z))
    for j, z in enumerate(zs):
        for i in range(nH + 1):
            w("%d, %.6f, %.6f" % (Rid(i, j), xr[i], z))

    # ---- 벌크 요소 (CPE4R) ----
    w("*ELEMENT, TYPE=CPE4R")
    e = 0
    bulk = []
    for j in range(nz):
        for i in range(nH):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Lid(i, j), Lid(i + 1, j),
                                      Lid(i + 1, j + 1), Lid(i, j + 1)))
            bulk.append(e)
    for j in range(nz):
        for i in range(nH):
            e += 1
            w("%d, %d, %d, %d, %d" % (e, Rid(i, j), Rid(i + 1, j),
                                      Rid(i + 1, j + 1), Rid(i, j + 1)))
            bulk.append(e)
    bulk_lo, bulk_hi = bulk[0], bulk[-1]

    # ---- Cohesive 요소 (COH2D4) : 중앙 x=0 ----
    # 연결 (Lj, Lj+1, Rj+1, Rj) : 두 견인면 = 좌측열 / 우측열
    w("*ELEMENT, TYPE=COH2D4")
    coh = []
    for j in range(nz):
        e += 1
        w("%d, %d, %d, %d, %d" % (e, Lid(nH, j), Lid(nH, j + 1),
                                  Rid(0, j + 1), Rid(0, j)))
        coh.append(e)
    coh_lo, coh_hi = coh[0], coh[-1]

    w("*ELSET, ELSET=BULK, GENERATE")
    w("%d, %d, 1" % (bulk_lo, bulk_hi))
    w("*ELSET, ELSET=COH, GENERATE")
    w("%d, %d, 1" % (coh_lo, coh_hi))
    w("*SURFACE, TYPE=ELEMENT, NAME=SKIN_SURF")
    w("BULK,")

    # ---- 경계 절점집합 ----
    bot = ([Lid(i, 0) for i in range(nH + 1)]
           + [Rid(i, 0) for i in range(nH + 1)])
    w("*NSET, NSET=NBOT")
    line = []
    for n in bot:
        line.append(str(n))
        if len(line) == 12:
            w(", ".join(line)); line = []
    if line:
        w(", ".join(line))

    # ---- 강체 쐐기 니들 ----
    w("*NODE")
    w("9999, 0.0, %.5f" % (H + 0.02))
    w("*NSET, NSET=NREF")
    w("9999,")
    w("*SURFACE, TYPE=SEGMENTS, NAME=NEEDLE, FILLET RADIUS=0.01")
    w("START, -0.20, %.5f" % (H + 0.60))
    w("LINE,   0.00, %.5f" % (H + 0.02))
    w("LINE,   0.20, %.5f" % (H + 0.60))
    w("*RIGID BODY, ANALYTICAL SURFACE=NEEDLE, REF NODE=NREF")

    # ---- 재료 ----
    w("*MATERIAL, NAME=SKIN")
    w("*DENSITY")
    w("1.1e-9,")
    w("*HYPERELASTIC, NEO HOOKE")
    w("0.05, 0.5")
    w("*SOLID SECTION, ELSET=BULK, MATERIAL=SKIN")

    w("*MATERIAL, NAME=COHMAT")
    w("*DENSITY")
    w("1.1e-9,")
    w("*ELASTIC, TYPE=TRACTION")
    w("1000.0, 1000.0, 1000.0")            # Enn, Ess, Ett(무시)
    w("*DAMAGE INITIATION, CRITERION=MAXS")
    w("0.15, 0.15, 0.15")                  # 법선/전단 공칭강도 [MPa]
    w("*DAMAGE EVOLUTION, TYPE=ENERGY")
    w("0.01,")                             # 파단에너지 Gc [N/mm]
    w("*COHESIVE SECTION, ELSET=COH, MATERIAL=COHMAT,"
      " RESPONSE=TRACTION SEPARATION, THICKNESS=SPECIFIED")
    w("1.0,")

    # ---- 접촉 상호작용(모델 데이터: 첫 *STEP 앞) ----
    w("*SURFACE INTERACTION, NAME=IPROP")
    w("*FRICTION")
    w("0.1,")
    # ---- 경계 / 스텝 ----
    w("*BOUNDARY")
    w("NBOT, 1, 2")
    w("NREF, 1, 1")
    w("NREF, 6, 6")
    w("*AMPLITUDE, NAME=PUSH, DEFINITION=SMOOTH STEP")
    w("0.0, 0.0, 0.01, 1.0")
    w("*STEP, NAME=CUT")
    w("*DYNAMIC, EXPLICIT")
    w(", 0.01")
    w("*FIXED MASS SCALING, DT=5.0e-7, TYPE=BELOW MIN")
    w("*BOUNDARY, AMPLITUDE=PUSH")
    w("NREF, 2, 2, -0.8")
    w("*CONTACT")
    w("*CONTACT INCLUSIONS, ALL EXTERIOR")
    w("*CONTACT INCLUSIONS")
    w("NEEDLE, SKIN_SURF")
    w("*CONTACT PROPERTY ASSIGNMENT")
    w(" ,  , IPROP")
    w("*OUTPUT, FIELD, NUMBER INTERVAL=25")
    w("*ELEMENT OUTPUT, ELSET=BULK")
    w("S, LE")
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

    with open("07_cohesive_cut.inp", "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote 07_cohesive_cut.inp")
    print("  half-width elems=%d, depth elems=%d" % (nH, nz))
    print("  bulk elems=%d, cohesive elems=%d"
          % (len(bulk), len(coh)))


if __name__ == "__main__":
    main()
