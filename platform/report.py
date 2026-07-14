# -*- coding: utf-8 -*-
# ======================================================================
#  report.py — 해석 결과 -> 템플릿 HTML 보고서 자동 생성
#
#  postprocess.py 의 <job>_fd.csv 와 odb_snapshot.py 의 <job>_*.png 를
#  모아 표지·요약·그래프·이미지·결론이 포함된 단일 HTML 보고서를 만든다.
#  Abaqus 불필요(순수 Python), 그래프는 인라인 SVG, 이미지는 data URI 임베드.
#
#  실행:
#    python report.py --job ref04 --dir . --project "마이크로니들 관통" \
#                     --author "홍길동" --date 2026-07-14 [--pcr 0.219]
#  결과:  <job>_report.html  (오프라인/인쇄/PDF 저장 가능)
# ======================================================================
import sys
import os
import glob
import base64
import argparse


def read_fd(path):
    rows = []
    with open(path) as f:
        next(f, None)
        for ln in f:
            p = ln.strip().split(',')
            if len(p) >= 3:
                try:
                    rows.append((float(p[0]), float(p[1]), float(p[2])))
                except ValueError:
                    pass
    return rows


def svg_chart(rows, w=660, h=380):
    if not rows:
        return ''
    m = {'l': 70, 'r': 20, 't': 20, 'b': 55}
    pw, ph = w - m['l'] - m['r'], h - m['t'] - m['b']
    xs = [r[1] for r in rows]
    ys = [r[2] for r in rows]
    xmin, xmax = 0.0, max(xs) or 1.0
    ymin, ymax = 0.0, max(ys) or 1.0
    ymax *= 1.1

    def X(v):
        return m['l'] + (v - xmin) / (xmax - xmin) * pw

    def Y(v):
        return m['t'] + ph - (v - ymin) / (ymax - ymin) * ph

    s = ['<svg viewBox="0 0 %d %d" width="100%%" '
         'xmlns="http://www.w3.org/2000/svg" '
         'font-family="Segoe UI,Malgun Gothic,sans-serif">' % (w, h)]
    s.append('<rect width="%d" height="%d" fill="#fff"/>' % (w, h))
    # 축
    s.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="#333"/>'
             % (m['l'], m['t'], m['l'], m['t'] + ph))
    s.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="#333"/>'
             % (m['l'], m['t'] + ph, m['l'] + pw, m['t'] + ph))
    # 눈금
    for k in range(6):
        xv = xmin + (xmax - xmin) * k / 5.0
        yv = ymin + (ymax - ymin) * k / 5.0
        px, py = X(xv), Y(yv)
        s.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" '
                 'stroke="#eee"/>' % (m['l'], py, m['l'] + pw, py))
        s.append('<text x="%.0f" y="%.0f" font-size="11" fill="#555" '
                 'text-anchor="end">%.3f</text>' % (m['l'] - 6, py + 4, yv))
        s.append('<text x="%.0f" y="%.0f" font-size="11" fill="#555" '
                 'text-anchor="middle">%.2f</text>'
                 % (px, m['t'] + ph + 18, xv))
    # 곡선
    pts = ' '.join('%.1f,%.1f' % (X(r[1]), Y(r[2])) for r in rows)
    s.append('<polyline points="%s" fill="none" stroke="#2b6cb0" '
             'stroke-width="2"/>' % pts)
    # peak
    pk = max(rows, key=lambda r: r[2])
    s.append('<circle cx="%.1f" cy="%.1f" r="4" fill="#dc2626"/>'
             % (X(pk[1]), Y(pk[2])))
    s.append('<text x="%.1f" y="%.1f" font-size="12" fill="#dc2626" '
             'text-anchor="middle">peak %.3f N</text>'
             % (X(pk[1]), Y(pk[2]) - 10, pk[2]))
    # 축 라벨
    s.append('<text x="%.0f" y="%.0f" font-size="13" fill="#333" '
             'text-anchor="middle">Penetration depth [mm]</text>'
             % (m['l'] + pw / 2, h - 8))
    s.append('<text x="16" y="%.0f" font-size="13" fill="#333" '
             'text-anchor="middle" transform="rotate(-90 16 %.0f)">'
             'Insertion force [N]</text>'
             % (m['t'] + ph / 2, m['t'] + ph / 2))
    s.append('</svg>')
    return ''.join(s)


def img_datauri(path):
    with open(path, 'rb') as f:
        b = base64.b64encode(f.read()).decode('ascii')
    return 'data:image/png;base64,' + b


IMG_CAPTION = {
    '_status': 'STATUS — 삭제(관통)된 요소가 비워져 보임',
    '_damage': '손상 SDV3 분포',
    '_stretch': '최대 주신축비 SDV2',
    '_mises': 'von Mises 응력',
    '_deformed': '변형형상 (관통 채널)',
    '_fd': '관통력–침투깊이 (postprocess)',
}

CSS = """
body{margin:0;background:#f7f7f8;color:#1a1a1a;
 font-family:-apple-system,"Segoe UI","Malgun Gothic",sans-serif;line-height:1.7}
.wrap{max-width:900px;margin:0 auto;padding:36px 26px 70px;background:#fff;
 box-shadow:0 0 0 1px #eee}
.cover{border-bottom:3px solid #2b6cb0;padding-bottom:16px;margin-bottom:24px}
.cover h1{font-size:1.9em;margin:.2em 0}
.meta{color:#555;font-size:.95em}
h2{color:#2b6cb0;border-bottom:1px solid #e2e8f0;padding-bottom:.25em;
 margin-top:1.8em}
.kpis{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.kpi{flex:1 1 160px;background:#f2f6fc;border:1px solid #dbe6f5;border-radius:10px;
 padding:12px 14px}
.kpi .v{font-size:1.5em;font-weight:700;color:#12395e}
.kpi .l{font-size:.82em;color:#5b6b7b}
.verdict{padding:12px 16px;border-radius:8px;font-weight:600;margin:12px 0}
.ok{background:#e9f9ee;border:1px solid #a7e0b8;color:#1a6b34}
.warn{background:#fffbeb;border:1px solid #f0d98a;color:#7a5a10}
.bad{background:#fdeaea;border:1px solid #eaa;color:#9b1c1c}
figure{margin:16px 0}figure img{max-width:100%;border:1px solid #e2e8f0;border-radius:8px}
figcaption{font-size:.88em;color:#555;margin-top:6px}
.chart{border:1px solid #e2e8f0;border-radius:8px;padding:8px;margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:.95em;margin:10px 0}
th,td{border:1px solid #dfe3e8;padding:7px 11px;text-align:left}
th{background:#eef3fa}
code{background:#eef1f5;padding:.1em .4em;border-radius:4px;
 font-family:Consolas,monospace;color:#c026a0}
@media print{body{background:#fff}.wrap{box-shadow:none}}
"""


def esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def build(job, d, project, author, date, pcr, title):
    fd_csv = os.path.join(d, job + '_fd.csv')
    rows = read_fd(fd_csv) if os.path.exists(fd_csv) else []
    pk = max(rows, key=lambda r: r[2]) if rows else None
    final = rows[-1] if rows else None

    H = []
    H.append('<div class="cover"><h1>%s</h1><div class="meta">'
             % esc(title or (project + ' 해석 보고서')))
    H.append('프로젝트: <b>%s</b> &nbsp;·&nbsp; Job: <code>%s</code>' %
             (esc(project), esc(job)))
    if author:
        H.append(' &nbsp;·&nbsp; 작성: %s' % esc(author))
    if date:
        H.append(' &nbsp;·&nbsp; %s' % esc(date))
    H.append('</div></div>')

    # 요약 KPI
    H.append('<h2>1. 요약</h2><div class="kpis">')
    if pk:
        H.append('<div class="kpi"><div class="v">%.4f</div>'
                 '<div class="l">peak 관통력 [N]</div></div>' % pk[2])
        H.append('<div class="kpi"><div class="v">%.3f</div>'
                 '<div class="l">peak 깊이 [mm]</div></div>' % pk[1])
    if final:
        H.append('<div class="kpi"><div class="v">%.3f</div>'
                 '<div class="l">최종 침투 [mm]</div></div>' % final[1])
    if pcr is not None:
        H.append('<div class="kpi"><div class="v">%.3f</div>'
                 '<div class="l">좌굴하중 P_cr [N]</div></div>' % pcr)
    H.append('</div>')

    # 판정 (F_ins vs P_cr)
    if pk and pcr is not None:
        if pk[2] < pcr:
            H.append('<div class="verdict ok">삽입 성공 예측: '
                     'F_ins=%.4f N &lt; P_cr=%.3f N (니들 좌굴 전 관통)</div>'
                     % (pk[2], pcr))
        else:
            H.append('<div class="verdict bad">삽입 실패 위험: '
                     'F_ins=%.4f N ≥ P_cr=%.3f N (니들 좌굴 우려)</div>'
                     % (pk[2], pcr))

    # 그래프
    if rows:
        H.append('<h2>2. 관통력–침투깊이</h2>')
        H.append('<div class="chart">%s</div>' % svg_chart(rows))
        drop = any(d0 > pk[1] and p0 < 0.7 * pk[2] for _, d0, p0 in rows)
        H.append('<p>관통 개시(peak 이후 30%%+ 급락) 감지: <b>%s</b></p>'
                 % ('YES — 관통 정황' if drop else 'NO — 압입 위주일 수 있음'))

    # 이미지들
    imgs = sorted(glob.glob(os.path.join(d, job + '_*.png')))
    imgs = [p for p in imgs if not p.endswith('_report.png')]
    if imgs:
        H.append('<h2>3. 결과 이미지</h2>')
        for p in imgs:
            key = os.path.splitext(os.path.basename(p))[0].replace(job, '', 1)
            cap = IMG_CAPTION.get(key, os.path.basename(p))
            try:
                uri = img_datauri(p)
                H.append('<figure><img src="%s"><figcaption>%s</figcaption>'
                         '</figure>' % (uri, esc(cap)))
            except Exception:
                pass

    # 결론 자리
    H.append('<h2>4. 결론 / 비고</h2><ul>')
    if pk:
        H.append('<li>peak 관통력 %.4f N (깊이 %.3f mm).</li>' % (pk[2], pk[1]))
    H.append('<li>준정적성(ALLKE/ALLIE)·요소삭제 수는 postprocess 출력 참조.</li>')
    H.append('<li>물성·치수는 예시값 → 실험/문헌으로 보정 필요.</li>')
    H.append('</ul>')

    body = ''.join(H)
    doc = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>%s</title><style>%s</style></head><body>'
           '<div class="wrap">%s</div></body></html>'
           % (esc(title or project), CSS, body))
    out = os.path.join(d, job + '_report.html')
    with open(out, 'wb') as f:
        f.write(doc.encode('utf-8'))
    print('wrote %s  (%d KB, points=%d, images=%d)'
          % (out, len(doc) // 1024, len(rows), len(imgs)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', required=True)
    ap.add_argument('--dir', default='.')
    ap.add_argument('--project', default='Abaqus 해석')
    ap.add_argument('--author', default='')
    ap.add_argument('--date', default='')
    ap.add_argument('--pcr', type=float, default=None)
    ap.add_argument('--title', default='')
    a = ap.parse_args()
    build(a.job, a.dir, a.project, a.author, a.date, a.pcr, a.title)


if __name__ == '__main__':
    main()
