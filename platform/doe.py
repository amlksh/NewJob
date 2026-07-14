# -*- coding: utf-8 -*-
# ======================================================================
#  doe.py — 파라메트릭 스터디(DOE) 생성 + 케이스 비교 리포트
#
#  1) gen : 템플릿 inp({{PARAM}} 자리표시) + 그리드(csv) -> 케이스 inp들 +
#           manifest + 실행 스크립트(.bat/.sh)
#  2) agg : 각 케이스의 <case>_fd.csv 를 모아 관통력곡선 오버레이 +
#           peak 비교표 -> doe_comparison.html
#
#  실행:
#    python doe.py gen --template base.inp --grid grid.csv --prefix case \
#                  --user vumat_skin.f
#    (해석 실행: run_doe.bat / run_doe.sh)
#    python doe.py agg --grid grid.csv --prefix case
# ======================================================================
import sys
import os
import csv
import argparse
import glob

PALETTE = ["#2b6cb0", "#dc2626", "#16a34a", "#ea580c", "#7c3aed",
           "#0d9488", "#db2777", "#475569"]


def read_grid(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def do_gen(a):
    with open(a.template, 'rb') as f:
        tpl = f.read().decode('utf-8')
    grid = read_grid(a.grid)
    if not grid:
        print("그리드가 비었습니다.")
        return 1
    params = [k for k in grid[0].keys() if k.lower() != 'case']
    cases = []
    for i, row in enumerate(grid):
        case = row.get('case') or row.get('Case') or ("c%d" % (i + 1))
        txt = tpl
        for p in params:
            txt = txt.replace("{{%s}}" % p, str(row[p]))
        name = "%s_%s" % (a.prefix, case)
        with open(name + ".inp", 'wb') as f:
            f.write(txt.encode('utf-8'))
        cases.append(case)
        print("wrote %s.inp  (%s)" % (name,
              ", ".join("%s=%s" % (p, row[p]) for p in params)))

    userflag = ("user=%s double=both " % a.user) if a.user else ""
    with open("run_doe.sh", 'w') as f:
        f.write("#!/usr/bin/env bash\nset -e\n")
        for c in cases:
            n = "%s_%s" % (a.prefix, c)
            f.write("abaqus job=%s input=%s.inp %scpus=4 interactive\n"
                    % (n, n, userflag))
            f.write("abaqus python postprocess.py %s.odb\n" % n)
    with open("run_doe.bat", 'w') as f:
        f.write("@echo off\n")
        for c in cases:
            n = "%s_%s" % (a.prefix, c)
            f.write("call abaqus job=%s input=%s.inp %scpus=4 interactive\n"
                    % (n, n, userflag))
            f.write("call abaqus python postprocess.py %s.odb\n" % n)
    print("생성: %d 케이스 + run_doe.sh/.bat" % len(cases))
    print("다음: 해석 실행 후  python doe.py agg --grid %s --prefix %s"
          % (a.grid, a.prefix))
    return 0


def read_fd(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        next(f, None)
        for ln in f:
            p = ln.strip().split(',')
            if len(p) >= 3:
                try:
                    rows.append((float(p[1]), float(p[2])))
                except ValueError:
                    pass
    return rows


def multi_chart(series, w=720, h=420):
    m = {'l': 70, 'r': 150, 't': 20, 'b': 55}
    pw, ph = w - m['l'] - m['r'], h - m['t'] - m['b']
    allx = [x for _, pts in series for x, _ in pts] or [1]
    ally = [y for _, pts in series for _, y in pts] or [1]
    xmax = max(allx) or 1.0
    ymax = (max(ally) or 1.0) * 1.1

    def X(v):
        return m['l'] + v / xmax * pw

    def Y(v):
        return m['t'] + ph - v / ymax * ph
    s = ['<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI,Malgun Gothic,sans-serif">' % (w, h)]
    s.append('<rect width="%d" height="%d" fill="#fff"/>' % (w, h))
    s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333"/>' % (m['l'], m['t'], m['l'], m['t'] + ph))
    s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333"/>' % (m['l'], m['t'] + ph, m['l'] + pw, m['t'] + ph))
    for k in range(6):
        yv = ymax * k / 5.0
        xv = xmax * k / 5.0
        s.append('<line x1="%d" y1="%.0f" x2="%d" y2="%.0f" stroke="#eee"/>' % (m['l'], Y(yv), m['l'] + pw, Y(yv)))
        s.append('<text x="%d" y="%.0f" font-size="11" fill="#555" text-anchor="end">%.3f</text>' % (m['l'] - 6, Y(yv) + 4, yv))
        s.append('<text x="%.0f" y="%d" font-size="11" fill="#555" text-anchor="middle">%.2f</text>' % (X(xv), m['t'] + ph + 18, xv))
    for i, (name, pts) in enumerate(series):
        if not pts:
            continue
        col = PALETTE[i % len(PALETTE)]
        poly = ' '.join('%.1f,%.1f' % (X(x), Y(y)) for x, y in pts)
        s.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2"/>' % (poly, col))
        ly = m['t'] + 16 + i * 20
        s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="3"/>' % (m['l'] + pw + 12, ly, m['l'] + pw + 32, ly, col))
        s.append('<text x="%d" y="%d" font-size="12" fill="#333">%s</text>' % (m['l'] + pw + 38, ly + 4, name))
    s.append('<text x="%.0f" y="%d" font-size="13" text-anchor="middle">Penetration depth [mm]</text>' % (m['l'] + pw / 2, h - 8))
    s.append('<text x="16" y="%.0f" font-size="13" text-anchor="middle" transform="rotate(-90 16 %.0f)">Insertion force [N]</text>' % (m['t'] + ph / 2, m['t'] + ph / 2))
    s.append('</svg>')
    return ''.join(s)


def do_agg(a):
    grid = read_grid(a.grid)
    params = [k for k in grid[0].keys() if k.lower() != 'case']
    series = []
    table = []
    for i, row in enumerate(grid):
        case = row.get('case') or ("c%d" % (i + 1))
        n = "%s_%s" % (a.prefix, case)
        pts = read_fd(n + "_fd.csv")
        series.append((case, pts))
        peak = max((p[1] for p in pts), default=float('nan'))
        depth = next((d for d, f in pts if f == peak), float('nan')) if pts else float('nan')
        table.append((case, {p: row[p] for p in params}, peak, depth))

    rows_html = ""
    for case, pv, peak, depth in table:
        pcells = "".join("<td>%s</td>" % pv[p] for p in params)
        rows_html += "<tr><td><b>%s</b></td>%s<td>%.5f</td><td>%.4f</td></tr>" % (
            case, pcells, peak, depth)
    phead = "".join("<th>%s</th>" % p for p in params)
    chart = multi_chart(series)
    html = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>DOE 비교 - %s</title><style>
body{font-family:Segoe UI,Malgun Gothic,sans-serif;max-width:900px;margin:24px auto;padding:0 16px}
h1{border-bottom:3px solid #2b6cb0;padding-bottom:8px}
table{border-collapse:collapse;width:100%%;margin:14px 0}td,th{border:1px solid #e2e8f0;padding:8px 10px}
th{background:#eef3fa}.chart{border:1px solid #e2e8f0;border-radius:8px;padding:8px}
</style></head><body><h1>파라메트릭 비교 — %s</h1>
<div class="chart">%s</div>
<h2>peak 관통력 비교</h2>
<table><tr><th>case</th>%s<th>peak F [N]</th><th>depth [mm]</th></tr>%s</table>
</body></html>""" % (a.prefix, a.prefix, chart, phead, rows_html)
    out = "doe_comparison.html"
    with open(out, 'wb') as f:
        f.write(html.encode('utf-8'))
    print("wrote %s (%d cases)" % (out, len(table)))
    for case, pv, peak, depth in table:
        print("  %-8s peak=%.5f N @ %.4f mm" % (case, peak, depth))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    g = sub.add_parser('gen')
    g.add_argument('--template', required=True)
    g.add_argument('--grid', required=True)
    g.add_argument('--prefix', default='case')
    g.add_argument('--user', default='')
    ag = sub.add_parser('agg')
    ag.add_argument('--grid', required=True)
    ag.add_argument('--prefix', default='case')
    a = ap.parse_args()
    if a.cmd == 'gen':
        return do_gen(a)
    if a.cmd == 'agg':
        return do_agg(a)
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
