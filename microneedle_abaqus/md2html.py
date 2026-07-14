# -*- coding: utf-8 -*-
# ======================================================================
#  md2html.py — 의존성 없는 Markdown -> 자립형 HTML 변환기
#
#  이 저장소 문서(README/매뉴얼 등)에 쓰인 마크다운 부분집합을 지원:
#    헤더(#..######), GFM 표, 코드펜스(```), 인용(>), 목록(-, 1.),
#    굵게(**), 인라인코드(`), 링크([]()), 수평선(---).
#
#  실행:  python md2html.py <input.md> [output.html]
#  결과:  내장 CSS 포함 단일 HTML (브라우저로 열기/인쇄/PDF 저장 가능)
# ======================================================================
import sys
import os
import re

CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;padding:0;background:#f7f7f8;color:#1a1a1a;
 font-family:-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo",sans-serif;
 line-height:1.7;font-size:16px}
.wrap{max-width:900px;margin:0 auto;padding:40px 24px 80px;background:#fff;
 box-shadow:0 0 0 1px #eee}
h1,h2,h3,h4{line-height:1.3;margin:1.6em 0 .6em;font-weight:700}
h1{font-size:2em;border-bottom:3px solid #2b6cb0;padding-bottom:.3em;margin-top:0}
h2{font-size:1.5em;border-bottom:1px solid #e2e8f0;padding-bottom:.25em;color:#2b6cb0}
h3{font-size:1.2em}h4{font-size:1.05em;color:#444}
p{margin:.7em 0}
a{color:#2b6cb0;text-decoration:none}a:hover{text-decoration:underline}
code{background:#eef1f5;padding:.12em .38em;border-radius:4px;
 font-family:"Consolas","SFMono-Regular",Menlo,monospace;font-size:.9em;color:#c026a0}
pre{background:#1e293b;color:#e2e8f0;padding:16px 18px;border-radius:8px;
 overflow-x:auto;line-height:1.5}
pre code{background:none;color:inherit;padding:0}
blockquote{margin:1em 0;padding:.6em 1em;border-left:4px solid #f0b429;
 background:#fffbeb;color:#5b4a12;border-radius:0 6px 6px 0}
blockquote code{background:#fdf3d0}
ul,ol{margin:.6em 0;padding-left:1.6em}li{margin:.25em 0}
hr{border:none;border-top:1px solid #e2e8f0;margin:2em 0}
.tablewrap{overflow-x:auto;margin:1em 0}
table{border-collapse:collapse;width:100%;font-size:.95em}
th,td{border:1px solid #dfe3e8;padding:8px 12px;text-align:left;vertical-align:top}
th{background:#2b6cb0;color:#fff;font-weight:600}
tr:nth-child(even) td{background:#f6f8fa}
@media print{body{background:#fff}.wrap{box-shadow:none;max-width:100%}
 pre{background:#f2f2f2;color:#111;border:1px solid #ccc}
 th{background:#ccc;color:#000}}
@media (max-width:640px){.wrap{padding:20px 14px}body{font-size:15px}}
"""


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def inline(s):
    parts = s.split('`')
    out = []
    for i, p in enumerate(parts):
        if i % 2 == 1:
            out.append('<code>' + esc(p) + '</code>')
        else:
            p = esc(p)
            p = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', p)
            p = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', p)
            out.append(p)
    return ''.join(out)


def convert(md):
    lines = md.split('\n')
    html = []
    i, n = 0, len(lines)
    in_code = False
    code_buf = []
    while i < n:
        line = lines[i]
        if line.startswith('```'):
            if not in_code:
                in_code, code_buf = True, []
            else:
                html.append('<pre><code>' + esc('\n'.join(code_buf))
                            + '</code></pre>')
                in_code = False
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        s = line.strip()
        if s == '':
            i += 1
            continue
        if s in ('---', '***', '___'):
            html.append('<hr>')
            i += 1
            continue
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            lv = len(m.group(1))
            html.append('<h%d>%s</h%d>' % (lv, inline(m.group(2)), lv))
            i += 1
            continue
        # GFM 표
        if (s.startswith('|') and i + 1 < n and '-' in lines[i + 1]
                and re.match(r'^\s*\|?[\s:|-]+\|?\s*$', lines[i + 1])):
            hdr = [c.strip() for c in s.strip('|').split('|')]
            i += 2
            body = []
            while i < n and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                body.append('<tr>' + ''.join('<td>' + inline(c) + '</td>'
                                              for c in cells) + '</tr>')
                i += 1
            html.append('<div class="tablewrap"><table><thead><tr>'
                        + ''.join('<th>' + inline(c) + '</th>' for c in hdr)
                        + '</tr></thead><tbody>' + ''.join(body)
                        + '</tbody></table></div>')
            continue
        if s.startswith('>'):
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(re.sub(r'^\s*>\s?', '', lines[i]))
                i += 1
            html.append('<blockquote>' + inline(' '.join(buf)) + '</blockquote>')
            continue
        if re.match(r'^\s*[-*]\s+', line):
            buf = []
            while i < n and re.match(r'^\s*[-*]\s+', lines[i]):
                buf.append('<li>' + inline(re.sub(r'^\s*[-*]\s+', '', lines[i]))
                           + '</li>')
                i += 1
            html.append('<ul>' + ''.join(buf) + '</ul>')
            continue
        if re.match(r'^\s*\d+\.\s+', line):
            buf = []
            while i < n and re.match(r'^\s*\d+\.\s+', lines[i]):
                buf.append('<li>' + inline(re.sub(r'^\s*\d+\.\s+', '', lines[i]))
                           + '</li>')
                i += 1
            html.append('<ol>' + ''.join(buf) + '</ol>')
            continue
        # 문단
        buf = [line]
        i += 1
        while i < n:
            t = lines[i]
            ts = t.strip()
            if (ts == '' or t.startswith('#') or t.startswith('```')
                    or ts.startswith('|') or ts.startswith('>')
                    or ts in ('---', '***', '___')
                    or re.match(r'^\s*[-*]\s+', t)
                    or re.match(r'^\s*\d+\.\s+', t)):
                break
            buf.append(t)
            i += 1
        html.append('<p>' + inline(' '.join(buf)) + '</p>')
    return '\n'.join(html)


def main():
    if len(sys.argv) < 2:
        print('usage: python md2html.py <input.md> [output.html]')
        return
    src = sys.argv[1]
    with open(src, 'rb') as f:
        md = f.read().decode('utf-8')
    m = re.search(r'^#\s+(.*)$', md, re.M)
    title = m.group(1).strip() if m else os.path.basename(src)
    body = convert(md)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + '.html'
    doc = ('<!doctype html>\n<html lang="ko"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>' + esc(title) + '</title><style>' + CSS + '</style></head>'
           '<body><div class="wrap">' + body + '</div></body></html>')
    with open(out, 'wb') as f:
        f.write(doc.encode('utf-8'))
    print('wrote %s (%d bytes)' % (out, len(doc)))


if __name__ == '__main__':
    main()
