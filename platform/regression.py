# -*- coding: utf-8 -*-
# ======================================================================
#  regression.py — 해석 결과 회귀 테스트 (골든 기준선 대비 diff)
#
#  물성/버전/서브루틴을 바꿔도 핵심 결과(peak 관통력 등)가 허용오차 안에
#  있는지 자동 확인. baseline JSON에 케이스별 지표를 저장하고 비교한다.
#
#  실행:
#    python regression.py save  --key ref04 --from ref04_fd.csv [--extra deleted=12]
#    python regression.py check --key ref04 --from ref04_fd.csv --tol 0.05
#  종료코드: check 실패 시 1
# ======================================================================
import sys
import os
import json
import argparse

BASE = "regression_baseline.json"


def metrics_from_fd(path):
    m = {}
    if path and os.path.exists(path):
        pk = (0.0, 0.0)
        n = 0
        final_d = 0.0
        with open(path) as f:
            next(f, None)
            for ln in f:
                p = ln.strip().split(',')
                if len(p) >= 3:
                    try:
                        d, fr = float(p[1]), float(p[2])
                    except ValueError:
                        continue
                    n += 1
                    final_d = d
                    if fr > pk[1]:
                        pk = (d, fr)
        m['peak_force'] = pk[1]
        m['peak_depth'] = pk[0]
        m['final_depth'] = final_d
        m['n_points'] = n
    return m


def load_base():
    if os.path.exists(BASE):
        with open(BASE) as f:
            return json.load(f)
    return {}


def save_base(d):
    with open(BASE, 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def parse_extra(items):
    out = {}
    for it in items or []:
        if '=' in it:
            k, v = it.split('=', 1)
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out


def do_save(a):
    base = load_base()
    m = metrics_from_fd(a.frm)
    m.update(parse_extra(a.extra))
    base[a.key] = m
    save_base(base)
    print("baseline 저장: %s -> %s" % (a.key, m))
    return 0


def do_check(a):
    base = load_base()
    if a.key not in base:
        print("기준선에 '%s' 없음. 먼저 save 하세요." % a.key)
        return 2
    ref = base[a.key]
    cur = metrics_from_fd(a.frm)
    cur.update(parse_extra(a.extra))
    print("=" * 60)
    print(" REGRESSION CHECK : %s   (tol=%.1f%%)" % (a.key, a.tol * 100))
    print("=" * 60)
    fail = 0
    for k in sorted(set(ref) | set(cur)):
        rv = ref.get(k)
        cv = cur.get(k)
        if cv is None:
            print("  [SKIP] %-12s (이번 실행에서 미측정, ref=%s)" % (k, rv))
            continue
        if isinstance(rv, (int, float)) and isinstance(cv, (int, float)):
            denom = abs(rv) if abs(rv) > 1e-12 else 1.0
            rel = abs(cv - rv) / denom
            ok = rel <= a.tol
            if not ok:
                fail += 1
            print("  [%s] %-12s ref=%.5g cur=%.5g  (Δ%.1f%%)"
                  % ("PASS" if ok else "FAIL", k, rv, cv, rel * 100))
        else:
            ok = (rv == cv)
            if not ok:
                fail += 1
            print("  [%s] %-12s ref=%s cur=%s"
                  % ("PASS" if ok else "FAIL", k, rv, cv))
    print("=" * 60)
    print("결과: %s (%d 실패)" % ("PASS" if not fail else "FAIL", fail))
    return 1 if fail else 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    s = sub.add_parser('save')
    s.add_argument('--key', required=True)
    s.add_argument('--from', dest='frm', required=True)
    s.add_argument('--extra', nargs='*')
    c = sub.add_parser('check')
    c.add_argument('--key', required=True)
    c.add_argument('--from', dest='frm', required=True)
    c.add_argument('--tol', type=float, default=0.05)
    c.add_argument('--extra', nargs='*')
    a = ap.parse_args()
    if a.cmd == 'save':
        return do_save(a)
    if a.cmd == 'check':
        return do_check(a)
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
