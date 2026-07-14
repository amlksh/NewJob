# -*- coding: utf-8 -*-
# ======================================================================
#  optimize.py — 1D 파라미터 자동 튜닝(목표 지표 맞추기)
#
#  템플릿 inp의 {{PARAM}} 값을 이분탐색으로 조정해, 결과 지표(기본: peak
#  관통력)가 목표값에 수렴하도록 반복 실행한다. (지표는 param에 단조라고 가정)
#
#  실행(실제):
#    python optimize.py --template base.inp --param C10 --job opt \
#        --target 0.25 --lo 0.01 --hi 0.10 --user vumat_skin.f --maxit 8
#  실행(탐색로직 자기검증, Abaqus 불필요):
#    python optimize.py --mock --mock-slope 0.5 --target 0.2 --lo 0 --hi 1
# ======================================================================
import sys
import os
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import regression   # noqa: E402  (metrics_from_fd 재사용)


def real_evaluator(a):
    def f(x):
        with open(a.template, 'rb') as fp:
            txt = fp.read().decode('utf-8')
        txt = txt.replace("{{%s}}" % a.param, repr(x))
        with open(a.job + ".inp", 'wb') as fp:
            fp.write(txt.encode('utf-8'))
        uf = ("user=%s double=both " % a.user) if a.user else ""
        subprocess.call("%s job=%s input=%s.inp %scpus=%d interactive"
                        % (a.abaqus, a.job, a.job, uf, a.cpus), shell=True)
        subprocess.call("%s python postprocess.py %s.odb"
                        % (a.abaqus, a.job), shell=True)
        m = regression.metrics_from_fd(a.job + "_fd.csv")
        return m.get(a.metric, 0.0)
    return f


def bisect_to_target(f, lo, hi, target, tol, maxit, log):
    flo, fhi = f(lo), f(hi)
    log("  x=%.5g -> %.5g" % (lo, flo))
    log("  x=%.5g -> %.5g" % (hi, fhi))
    if (flo - target) * (fhi - target) > 0:
        log("  [경고] 목표가 [lo,hi] 구간에 브래킷되지 않음. "
            "가장 가까운 끝점 반환.")
        return (lo if abs(flo - target) < abs(fhi - target) else hi), None
    for k in range(maxit):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        log("  it%d  x=%.5g -> %.5g  (목표 %.5g)" % (k + 1, mid, fm, target))
        if abs(fm - target) <= tol * max(1.0, abs(target)):
            return mid, fm
        # 단조 가정: flo,fhi 부호로 방향 결정
        if (flo - target) * (fm - target) <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi), fm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--template')
    ap.add_argument('--param', default='C10')
    ap.add_argument('--job', default='opt')
    ap.add_argument('--user', default='')
    ap.add_argument('--abaqus', default='abaqus')
    ap.add_argument('--cpus', type=int, default=4)
    ap.add_argument('--metric', default='peak_force')
    ap.add_argument('--target', type=float, required=True)
    ap.add_argument('--lo', type=float, required=True)
    ap.add_argument('--hi', type=float, required=True)
    ap.add_argument('--tol', type=float, default=0.03)
    ap.add_argument('--maxit', type=int, default=8)
    ap.add_argument('--mock', action='store_true')
    ap.add_argument('--mock-slope', type=float, default=1.0)
    ap.add_argument('--mock-intercept', type=float, default=0.0)
    a = ap.parse_args()

    def log(s):
        print(s)

    print("=" * 60)
    print(" OPTIMIZE: %s 를 조정해 %s=%.5g 맞추기"
          % (a.param, a.metric, a.target))
    print("=" * 60)

    if a.mock:
        f = lambda x: a.mock_slope * x + a.mock_intercept  # noqa: E731
    else:
        if not a.template:
            print("--template 필요(또는 --mock).")
            return 2
        f = real_evaluator(a)

    x, fx = bisect_to_target(f, a.lo, a.hi, a.target, a.tol, a.maxit, log)
    print("-" * 60)
    if fx is None:
        print("수렴 실패(브래킷 안됨). 근사 %s=%.6g" % (a.param, x))
        return 1
    print("결과: %s=%.6g 에서 %s=%.6g (목표 %.6g, 오차 %.2g)"
          % (a.param, x, a.metric, fx, a.target, abs(fx - a.target)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
