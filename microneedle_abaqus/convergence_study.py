# -*- coding: utf-8 -*-
# ======================================================================
#  convergence_study.py
#
#  메쉬 수렴성 스터디 도구.
#  gen_refined_axi.generate() 로 여러 해상도의 입력파일을 만들고,
#  각 잡을 실행한 뒤(사용자 환경) 산출된 *_fd.csv 들을 모아
#  "peak 관통력 vs 메쉬 크기" 수렴 그래프를 만든다.
#
#  사용 순서
#  ---------
#  1) 입력파일 + 실행 스크립트 생성 (로컬 python):
#        python convergence_study.py gen              # 변형률기반
#        python convergence_study.py gen --reg        # 파단에너지 정규화
#     -> conv_r0.030.inp, conv_r0.020.inp, ...  및
#        run_convergence.sh / run_convergence.bat
#
#  2) 해석 실행 (Abaqus 환경):
#        bash run_convergence.sh          (Linux)
#        run_convergence.bat              (Windows)
#     각 잡마다 postprocess.py 가 conv_r0.030_fd.csv 등을 생성.
#
#  3) 결과 집계/그래프 (Abaqus 또는 로컬 python):
#        python convergence_study.py agg
#     -> convergence.csv (mesh, dr, dz, elems, peak_force) + convergence.png
# ======================================================================
import sys
import glob
import os

import gen_refined_axi as G

# (dr_fine, dz_sc) 해상도 목록 : 성글게 -> 세밀하게
LEVELS = [
    (0.060, 0.0100),
    (0.040, 0.0067),
    (0.030, 0.0050),
    (0.020, 0.0033),
    (0.015, 0.0025),
]


def tag(dr):
    return "conv_r%.3f" % dr


def do_gen(reg):
    jobs = []
    for dr, dz in LEVELS:
        inp = tag(dr) + ".inp"
        info = G.generate(inp, dr_fine=dr, dz_sc=dz, reg=reg)
        jobs.append((tag(dr), info["elems"], dr, dz))

    user = "vumat_skin_reg.f" if reg else "vumat_skin.f"
    common = "user=%s double=both cpus=4" % user

    with open("run_convergence.sh", "w") as f:
        f.write("#!/usr/bin/env bash\nset -e\n")
        for jt, ne, dr, dz in jobs:
            f.write("abaqus job=%s input=%s.inp %s\n" % (jt, jt, common))
            f.write("abaqus python postprocess.py %s.odb\n" % jt)
    with open("run_convergence.bat", "w") as f:
        f.write("@echo off\n")
        for jt, ne, dr, dz in jobs:
            f.write("call abaqus job=%s input=%s.inp %s\n"
                    % (jt, jt, common))
            f.write("call abaqus python postprocess.py %s.odb\n" % jt)

    # 메타(집계 시 dr/dz/elems 참조)
    with open("convergence_jobs.csv", "w") as f:
        f.write("job,dr_fine,dz_sc,elems\n")
        for jt, ne, dr, dz in jobs:
            f.write("%s,%.4f,%.4f,%d\n" % (jt, dr, dz, ne))

    print("generated %d input files + run_convergence.sh/.bat "
          "(material: %s)" % (len(jobs), "energy-reg" if reg else "strain"))
    print("next: run the batch in your Abaqus env, then: "
          "python convergence_study.py agg")


def _peak(csv):
    fmax, dpk = 0.0, 0.0
    with open(csv) as f:
        next(f, None)
        for ln in f:
            p = ln.strip().split(",")
            if len(p) == 3:
                fr = float(p[2])
                if fr > fmax:
                    fmax, dpk = fr, float(p[1])
    return fmax, dpk


def do_agg():
    meta = {}
    if os.path.exists("convergence_jobs.csv"):
        with open("convergence_jobs.csv") as f:
            next(f, None)
            for ln in f:
                p = ln.strip().split(",")
                if len(p) == 4:
                    meta[p[0]] = (float(p[1]), float(p[2]), int(p[3]))

    rows = []
    for csv in sorted(glob.glob("conv_r*_fd.csv")):
        job = csv[:-7]                      # strip "_fd.csv"
        fmax, dpk = _peak(csv)
        dr, dz, ne = meta.get(job, (float("nan"),) * 3)
        rows.append((job, dr, dz, ne, fmax, dpk))

    if not rows:
        print("no conv_r*_fd.csv found - run the jobs first.")
        return
    rows.sort(key=lambda r: -r[1])          # 성긴 -> 세밀

    with open("convergence.csv", "w") as f:
        f.write("job,dr_fine,dz_sc,elems,peak_force_N,depth_mm\n")
        for r in rows:
            f.write("%s,%.4f,%.4f,%s,%.5f,%.5f\n"
                    % (r[0], r[1], r[2], r[3], r[4], r[5]))
    print("wrote convergence.csv")
    print("%-14s %8s %8s %8s %12s" %
          ("job", "dr", "dz", "elems", "peakF[N]"))
    for r in rows:
        print("%-14s %8.4f %8.4f %8s %12.5f"
              % (r[0], r[1], r[2], r[3], r[4]))

    # 상대변화(수렴 지표)
    if len(rows) >= 2:
        f_fin = rows[-1][4]
        if f_fin != 0:
            dpc = 100.0 * (rows[-2][4] - f_fin) / f_fin
            print("relative change (2 finest) = %.2f %%" % dpc)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        dr = [r[1] for r in rows]
        pf = [r[4] for r in rows]
        plt.figure(figsize=(6, 4))
        plt.plot(dr, pf, "o-b", lw=1.6)
        plt.gca().invert_xaxis()            # 세밀할수록 오른쪽
        plt.xlabel("near-axis element size dr [mm] (finer ->)")
        plt.ylabel("peak insertion force [N]")
        plt.title("Mesh convergence of peak penetration force")
        plt.grid(True, ls=":")
        plt.tight_layout()
        plt.savefig("convergence.png", dpi=150)
        print("wrote convergence.png")
    except Exception as e:
        print("plot skipped: %s" % e)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "gen"
    reg = "--reg" in sys.argv
    if mode == "gen":
        do_gen(reg)
    elif mode == "agg":
        do_agg()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
