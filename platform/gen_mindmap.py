# -*- coding: utf-8 -*-
# ======================================================================
#  gen_mindmap.py — Fortran(VUMAT) ↔ Abaqus 프로세스 마인드맵 생성
#
#  의존성 없이 자립형 HTML(인라인 SVG)로 두-측면 마인드맵을 그린다.
#  JS 불필요 -> 오프라인/인쇄/PDF 저장 가능.
#
#  실행:  python gen_mindmap.py   ->  mindmap_vumat.html
# ======================================================================

TITLE = "Fortran(VUMAT) ↔ Abaqus/Explicit 해석 프로세스"
SUB = "사용자 서브루틴이 Abaqus 풀이 과정에 참여하는 흐름 (마이크로니들 관통 예)"

# (branch label, color, [children])
BR = [
    ("① 입력 준비", "#2b6cb0", [
        ".inp: *MATERIAL",
        "*USER MATERIAL, CONSTANTS=n",
        "*DEPVAR, DELETE=1 (STATEV)",
        ".f 소스 (고정형식)",
        "abaqus job= user=..f double=both",
    ]),
    ("② 컴파일·링크", "#0d9488", [
        "ifort/ifx 컴파일 (/fpp /extend-source)",
        "explicitU-D 라이브러리 링크",
        "verify -user_explicit (사전검증)",
        ".log 에서 컴파일 성공 확인",
    ]),
    ("③ 초기화 (t=0)", "#16a34a", [
        "순수탄성으로 시작 (초기탄성계수)",
        "STATEV 초기화 (DELFLAG=1)",
    ]),
    ("④ 증분 루프 (Δt·블록)", "#ea580c", [
        "입력: stretchNew/defgrad/strainInc",
        "응력계산(동회전): B=U·U, J=det",
        "구성식: Neo-Hookean / HGO",
        "반환: stressNew, stateNew",
        "에너지 갱신: enerInternNew",
    ]),
    ("⑤ 손상·요소삭제 (Erosion)", "#dc2626", [
        "최대주신축비 λ → 손상 D",
        "D ≥ 1 → STATEV(1)=0",
        "*DEPVAR DELETE → 요소 제거",
        "새 접촉면 노출 → 관통 진행",
    ]),
    ("⑥ 안정성·시간", "#7c3aed", [
        "안정증분 (얇은 각질층→작음)",
        "질량스케일링 (FIXED MASS SCALING)",
        "준정적 확인: ALLKE ≪ ALLIE",
    ]),
    ("⑦ 출력·후처리 (Post)", "#475569", [
        ".odb: S, SDV, STATUS, U/RF",
        ".sta / .dat / .msg / .log",
        "postprocess.py (힘-깊이·삭제)",
        "odb_snapshot.py (이미지)",
    ]),
]

# 오른쪽 / 왼쪽 분배 (읽기 순서: 오른쪽 위→아래, 왼쪽 위→아래)
RIGHT = [0, 1, 2, 3]
LEFT = [4, 5, 6]

CHILD_LH = 40      # 자식 한 줄 높이
GAP = 34           # 브랜치 블록 간 간격
TOPM = 130         # 상단 여백(제목)
BOTM = 70
BRANCH_INNER = 185  # 중심~브랜치 안쪽 모서리
CHILD_INNER = 430   # 중심~자식 안쪽 모서리 (main에서 브랜치폭 기준 자동보정)


def cw(s, size):
    w = 0.0
    for c in s:
        o = ord(c)
        if o > 0x1100:      # 한글/기호(전각)
            w += size * 1.02
        elif o < 128:
            w += size * 0.56
        else:
            w += size * 0.62
    return w


def box_w(s, size, pad):
    return cw(s, size) + 2 * pad


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def main():
    global CHILD_INNER
    # 브랜치 박스 최대폭 -> 자식 안쪽 모서리를 겹치지 않게 자동 보정
    maxBW = max(box_w(BR[k][0], 15, 16) for k in range(len(BR)))
    CHILD_INNER = BRANCH_INNER + maxBW + 40

    # 자식 박스 최대폭(측면별) -> 캔버스 폭 계산
    def side_maxcw(idxs):
        m = 0.0
        for k in idxs:
            for ch in BR[k][2]:
                m = max(m, box_w(ch, 13.5, 13))
        return m
    maxR = side_maxcw(RIGHT)
    maxL = side_maxcw(LEFT)

    cx = CHILD_INNER + maxL + 40
    W = cx + CHILD_INNER + maxR + 40

    def side_total(idxs):
        t = 0
        for n, k in enumerate(idxs):
            t += max(1, len(BR[k][2])) * CHILD_LH
        t += (len(idxs) - 1) * GAP
        return t
    totR = side_total(RIGHT)
    totL = side_total(LEFT)
    Hbody = max(totR, totL)
    H = TOPM + Hbody + BOTM
    cy = TOPM + Hbody / 2.0

    svg = []
    a = svg.append

    def bez(x1, y1, x2, y2, col):
        mx = (x1 + x2) / 2.0
        a('<path d="M%.1f %.1f C %.1f %.1f %.1f %.1f %.1f %.1f" '
          'fill="none" stroke="%s" stroke-width="2" opacity="0.45"/>'
          % (x1, y1, mx, y1, mx, y2, x2, y2, col))

    def node(x, y, w, h, fill, text, tcol, size, bold, anchor='middle',
             lborder=None):
        rx = 9
        a('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d" '
          'fill="%s" stroke="#00000012"/>'
          % (x, y, w, h, rx, fill))
        if lborder:
            a('<rect x="%.1f" y="%.1f" width="4" height="%.1f" rx="2" '
              'fill="%s"/>' % (x, y, h, lborder))
        tx = x + w / 2.0
        a('<text x="%.1f" y="%.1f" font-size="%.1f" fill="%s" '
          'text-anchor="middle" font-weight="%s" '
          'font-family="-apple-system,Segoe UI,Malgun Gothic,sans-serif">'
          '%s</text>' % (tx, y + h / 2.0 + size * 0.35, size, tcol,
                         '700' if bold else '400', esc(text)))

    # --- 루트 ---
    rootTxt = "Fortran VUMAT\\n↔ Abaqus/Explicit"
    rw = box_w("Fortran VUMAT ↔ Abaqus/Explicit", 15, 18)
    rh = 62
    # 루트 박스 + 2줄 텍스트
    a('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="14" '
      'fill="#0f2b46" stroke="#0b2136"/>'
      % (cx - rw / 2, cy - rh / 2, rw, rh))
    a('<text x="%.1f" y="%.1f" font-size="16" fill="#fff" '
      'text-anchor="middle" font-weight="700" '
      'font-family="-apple-system,Segoe UI,Malgun Gothic,sans-serif">'
      'Fortran VUMAT</text>' % (cx, cy - 4))
    a('<text x="%.1f" y="%.1f" font-size="14" fill="#9ec5ff" '
      'text-anchor="middle" '
      'font-family="-apple-system,Segoe UI,Malgun Gothic,sans-serif">'
      '↔ Abaqus/Explicit</text>' % (cx, cy + 16))

    def draw_side(idxs, sign):
        total = side_total(idxs)
        yc = cy - total / 2.0
        for k in idxs:
            label, col, kids = BR[k]
            nk = max(1, len(kids))
            blockH = nk * CHILD_LH
            bY = yc + blockH / 2.0
            bw = box_w(label, 15, 16)
            bh = 40
            if sign > 0:
                bInnerX = cx + BRANCH_INNER
                bx = bInnerX
                b_outer = bx + bw
                root_pt = cx + rw / 2
            else:
                bInnerX = cx - BRANCH_INNER
                bx = bInnerX - bw
                b_outer = bx
                root_pt = cx - rw / 2
            # 루트 -> 브랜치
            bez(root_pt, cy, bInnerX, bY, col)
            node(bx, bY - bh / 2, bw, bh, col, label, "#fff", 15, True)
            # 브랜치 -> 자식들
            for i, ch in enumerate(kids):
                chY = yc + i * CHILD_LH + CHILD_LH / 2.0
                chw = box_w(ch, 13.5, 13)
                chh = 30
                if sign > 0:
                    cInner = cx + CHILD_INNER
                    chx = cInner
                    c_pt = cInner
                else:
                    cInner = cx - CHILD_INNER
                    chx = cInner - chw
                    c_pt = cInner
                bez(b_outer, bY, c_pt, chY, col)
                node(chx, chY - chh / 2, chw, chh, "#f8fafc", ch,
                     "#1f2937", 13.5, False, lborder=col)
            yc += blockH + GAP

    draw_side(RIGHT, +1)
    draw_side(LEFT, -1)

    svg_str = ('<svg viewBox="0 0 %.0f %.0f" width="100%%" '
               'xmlns="http://www.w3.org/2000/svg" '
               'font-family="sans-serif">' % (W, H)
               + '<rect width="%.0f" height="%.0f" fill="#ffffff"/>' % (W, H)
               + '<text x="%.1f" y="52" font-size="26" font-weight="800" '
               'fill="#0f2b46" text-anchor="middle" '
               'font-family="-apple-system,Segoe UI,Malgun Gothic,sans-serif">'
               '%s</text>' % (W / 2, esc(TITLE))
               + '<text x="%.1f" y="84" font-size="15" fill="#5b6b7b" '
               'text-anchor="middle" '
               'font-family="-apple-system,Segoe UI,Malgun Gothic,sans-serif">'
               '%s</text>' % (W / 2, esc(SUB))
               + ''.join(svg) + '</svg>')

    html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + esc(TITLE) + '</title>'
            '<style>body{margin:0;background:#eef1f5;'
            'font-family:-apple-system,"Segoe UI","Malgun Gothic",sans-serif}'
            '.wrap{max-width:1400px;margin:0 auto;padding:16px}'
            '.card{background:#fff;border-radius:12px;padding:8px;'
            'box-shadow:0 2px 12px #0002;overflow-x:auto}'
            '.note{max-width:1400px;margin:12px auto;padding:0 20px;'
            'color:#334;font-size:14px;line-height:1.7}'
            'code{background:#eef1f5;padding:.1em .4em;border-radius:4px;'
            'font-family:Consolas,monospace;font-size:.92em;color:#c026a0}'
            '@media print{body{background:#fff}.card{box-shadow:none}}'
            '</style></head><body><div class="wrap"><div class="card">'
            + svg_str + '</div></div>'
            '<div class="note"><b>핵심 요약</b> — Abaqus는 매 증분마다 각 '
            '요소블록의 <b>변형정보(stretch/defgrad/strainInc)</b>를 '
            'VUMAT에 넘기고, VUMAT은 <b>동회전 좌표계</b>에서 응력을 계산해 '
            '<code>stressNew</code>·<code>stateNew</code>로 돌려줍니다. '
            '손상변수가 임계에 도달하면 <code>STATEV(1)=0</code> → '
            '<code>*DEPVAR,DELETE=1</code>이 요소를 삭제해 관통(절개)이 '
            '진행되고, 전역접촉이 새 표면을 인식합니다. 서브루틴은 실행 시 '
            '<code>ifort/ifx</code>로 컴파일되므로 <code>double=both</code>가 '
            '필요합니다.</div></body></html>')

    with open("mindmap_vumat.html", "w") as f:
        f.write(html)
    print("wrote mindmap_vumat.html  (canvas %.0f x %.0f)" % (W, H))


if __name__ == "__main__":
    main()
