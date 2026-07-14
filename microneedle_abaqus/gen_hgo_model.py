# -*- coding: utf-8 -*-
# ======================================================================
#  gen_hgo_model.py
#
#  (b) HGO 이방성 + 사전인장 3D 쿼터모델 입력파일 생성기.
#
#  섬유가 x축 대칭(+-gamma)이므로 x=0, y=0 이 대칭면 -> 1/4 모델.
#  니들축(x=y=0)이 두 대칭면의 교선에 위치 = 축대칭 니들의 1/4.
#
#  실행:  python gen_hgo_model.py   ->  02_hgo_pretension.inp
# ======================================================================

# --- 격자 파라미터 -----------------------------------------------------
LX, LY, LZ = 1.5, 1.5, 1.2          # 블록 치수 [mm]
NX, NY, NZ = 12, 12, 10             # 방향별 요소 수
ISTR, JSTR, KSTR = 1, 100, 10000    # 절점번호 증분
EJSTR, EKSTR = 100, 10000           # 요소번호 증분(행/층)
PRE = 0.10                          # 사전인장 변형률(10%)
PUSH_DEPTH = 1.0                    # 니들 하강량 [mm]


def nid(i, j, k):
    return 1 + i * ISTR + j * JSTR + k * KSTR


def eid(i, j, k):
    return 1 + i + j * EJSTR + k * EKSTR


def main():
    L = []
    w = L.append

    w("*HEADING")
    w("(b) HGO anisotropic skin + pretension - 3D quarter model (C3D8R)")
    w("Fibers +-gamma about x-axis; x=0,y=0 symmetry planes")
    w("Units: mm, N, MPa, tonne, s")

    # ---------- 절점 ----------
    w("*NODE")
    for k in range(NZ + 1):
        z = LZ * k / NZ
        for j in range(NY + 1):
            y = LY * j / NY
            for i in range(NX + 1):
                x = LX * i / NX
                w("%d, %.5f, %.5f, %.5f" % (nid(i, j, k), x, y, z))

    # ---------- 요소 ----------
    w("*ELEMENT, TYPE=C3D8R")
    for k in range(NZ):
        for j in range(NY):
            for i in range(NX):
                n1 = nid(i, j, k)
                n2 = nid(i + 1, j, k)
                n3 = nid(i + 1, j + 1, k)
                n4 = nid(i, j + 1, k)
                n5 = nid(i, j, k + 1)
                n6 = nid(i + 1, j, k + 1)
                n7 = nid(i + 1, j + 1, k + 1)
                n8 = nid(i, j + 1, k + 1)
                w("%d, %d,%d,%d,%d, %d,%d,%d,%d"
                  % (eid(i, j, k), n1, n2, n3, n4, n5, n6, n7, n8))
    w("*ELSET, ELSET=SKIN, GENERATE")
    w("%d, %d, 1" % (eid(0, 0, 0), eid(NX - 1, NY - 1, NZ - 1)))
    w("*SURFACE, TYPE=ELEMENT, NAME=SKIN_SURF")
    w("SKIN,")

    # ---------- 절점 집합 ----------
    def nset(name, pts):
        w("*NSET, NSET=%s" % name)
        line = []
        for n in pts:
            line.append(str(n))
            if len(line) == 8:
                w(", ".join(line)); line = []
        if line:
            w(", ".join(line))

    pbot = [nid(i, j, 0) for j in range(NY + 1) for i in range(NX + 1)]
    xsym = [nid(0, j, k) for k in range(NZ + 1) for j in range(NY + 1)]
    ysym = [nid(i, 0, k) for k in range(NZ + 1) for i in range(NX + 1)]
    xout = [nid(NX, j, k) for k in range(NZ + 1) for j in range(NY + 1)]
    yout = [nid(i, NY, k) for k in range(NZ + 1) for i in range(NX + 1)]
    nset("PBOT", pbot)
    nset("XSYM", xsym)
    nset("YSYM", ysym)
    nset("XOUT", xout)
    nset("YOUT", yout)

    # ---------- 강체 니들 (회전면 해석적 강체) ----------
    w("*NODE")
    w("9999, 0.0, 0.0, %.5f" % (LZ + 0.02))
    w("*NSET, NSET=NREF")
    w("9999,")
    w("*SURFACE, TYPE=REVOLUTION, NAME=NEEDLE, FILLET RADIUS=0.01")
    w("0.,0.,0., 0.,0.,1.")
    w("START, 0.02, %.5f" % (LZ + 0.02))
    w("LINE,  0.15, %.5f" % (LZ + 0.40))
    w("LINE,  0.15, %.5f" % (LZ + 1.80))
    w("*RIGID BODY, ANALYTICAL SURFACE=NEEDLE, REF NODE=NREF")

    # ---------- 재료 (HGO VUMAT) ----------
    w("*MATERIAL, NAME=DERMIS_HGO")
    w("*DENSITY")
    w("1.1e-9,")
    w("*USER MATERIAL, CONSTANTS=8")
    # C10, D1, k1, k2, kappa, gamma[deg], lam_d, lam_f
    w("0.02, 1.0, 0.5, 8.0, 0.2, 30.0, 1.6, 2.3")
    w("*DEPVAR, DELETE=1")
    w("4")
    w("1, DELFLAG, deletion flag")
    w("2, LAMMAX, max principal stretch")
    w("3, DAMAGE, damage variable")
    w("4, JVOL, relative volume")
    w("*SOLID SECTION, ELSET=SKIN, MATERIAL=DERMIS_HGO")

    # ---------- 진폭 ----------
    w("*AMPLITUDE, NAME=PRE, DEFINITION=SMOOTH STEP, TIME=STEP TIME")
    w("0.0, 0.0, 0.005, 1.0")
    w("*AMPLITUDE, NAME=PUSH, DEFINITION=SMOOTH STEP, TIME=STEP TIME")
    w("0.0, 0.0, 0.010, 1.0")

    # ---------- 전역 접촉(모델 레벨) ----------
    w("*SURFACE INTERACTION, NAME=IPROP")
    w("*FRICTION")
    w("0.1,")

    dx = LX * PRE
    dy = LY * PRE

    # ================= STEP 1 : 사전인장 =================
    w("*STEP, NAME=PRETENSION")
    w("*DYNAMIC, EXPLICIT")
    w(", 0.005")
    w("*FIXED MASS SCALING, DT=5.0e-7, TYPE=BELOW MIN")
    w("*BOUNDARY")
    w("XSYM, 1, 1")
    w("YSYM, 2, 2")
    w("PBOT, 3, 3")
    w("NREF, 1, 6")
    w("*BOUNDARY, AMPLITUDE=PRE")
    w("XOUT, 1, 1, %.5f" % dx)
    w("YOUT, 2, 2, %.5f" % dy)
    w("*CONTACT")
    w("*CONTACT INCLUSIONS, ALL EXTERIOR")
    w("*CONTACT INCLUSIONS")
    w("NEEDLE, SKIN_SURF")
    w("*CONTACT PROPERTY ASSIGNMENT")
    w(" ,  , IPROP")
    w("*OUTPUT, FIELD, NUMBER INTERVAL=5")
    w("*ELEMENT OUTPUT, ELSET=SKIN")
    w("S, LE, SDV, STATUS")
    w("*NODE OUTPUT")
    w("U")
    w("*END STEP")

    # ================= STEP 2 : 니들 삽입 =================
    w("*STEP, NAME=INSERTION")
    w("*DYNAMIC, EXPLICIT")
    w(", 0.010")
    w("*FIXED MASS SCALING, DT=5.0e-7, TYPE=BELOW MIN")
    # 사전인장 유지 + 대칭 + 니들 하강 (OP=NEW 로 전체 재정의)
    w("*BOUNDARY, OP=NEW")
    w("XSYM, 1, 1")
    w("YSYM, 2, 2")
    w("PBOT, 3, 3")
    w("XOUT, 1, 1, %.5f" % dx)
    w("YOUT, 2, 2, %.5f" % dy)
    w("NREF, 1, 1")
    w("NREF, 2, 2")
    w("NREF, 4, 6")
    w("*BOUNDARY, AMPLITUDE=PUSH")
    w("NREF, 3, 3, %.5f" % (-PUSH_DEPTH))
    w("*OUTPUT, FIELD, NUMBER INTERVAL=25")
    w("*ELEMENT OUTPUT, ELSET=SKIN")
    w("S, LE, SDV, STATUS")
    w("*NODE OUTPUT")
    w("U, V")
    w("*OUTPUT, HISTORY, TIME INTERVAL=1.0e-4")
    w("*NODE OUTPUT, NSET=NREF")
    w("U3, V3, RF3")
    w("*ENERGY OUTPUT")
    w("ALLIE, ALLKE, ALLSE, ALLWK")
    w("*END STEP")

    with open("02_hgo_pretension.inp", "w") as f:
        f.write("\n".join(L) + "\n")
    print("wrote 02_hgo_pretension.inp : %d nodes, %d elements"
          % ((NX + 1) * (NY + 1) * (NZ + 1), NX * NY * NZ))


if __name__ == "__main__":
    main()
