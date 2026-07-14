# -*- coding: utf-8 -*-
# ======================================================================
#  md2docx.py — 의존성 없는 Markdown -> Word(.docx) 변환기
#
#  python-docx 없이 OOXML(zip)로 유효한 .docx를 직접 만든다.
#  지원: 헤더(#..###), 문단, 굵게(**), 표(GFM), 목록(-,1.). (이미지 제외)
#
#  실행:  python md2docx.py <input.md> [output.docx]
# ======================================================================
import sys
import os
import re
import zipfile

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"')


def xesc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def inline_runs(text):
    """**bold** 처리 + 코드/링크 정리 -> [(text, bold)]"""
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'\1 (\2)', text)
    parts = text.split('**')
    runs = []
    for i, p in enumerate(parts):
        if p:
            runs.append((p, i % 2 == 1))
    return runs or [("", False)]


def run_xml(t, bold, sz):
    rpr = '<w:rPr>'
    if bold:
        rpr += '<w:b/>'
    rpr += '<w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr>' % (sz, sz)
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, xesc(t))


def para(runs, sz=22, bold_all=False, spacing_before=0):
    ppr = ''
    if spacing_before:
        ppr = '<w:pPr><w:spacing w:before="%d"/></w:pPr>' % spacing_before
    body = ''.join(run_xml(t, bold_all or b, sz) for t, b in runs)
    return '<w:p>%s%s</w:p>' % (ppr, body)


def heading(text, lvl):
    sz = {1: 36, 2: 28, 3: 24}.get(lvl, 22)
    return para([(text, False)], sz=sz, bold_all=True, spacing_before=160)


def table_xml(header, rows):
    borders = ('<w:tblBorders>'
               + ''.join('<w:%s w:val="single" w:sz="4" w:space="0" '
                         'w:color="AAAAAA"/>' % s for s in
                         ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
               + '</w:tblBorders>')
    tblpr = ('<w:tblPr><w:tblW w:w="0" w:type="auto"/>%s</w:tblPr>' % borders)

    def cell(t, bold):
        return ('<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>%s</w:tc>'
                % para(inline_runs(t), sz=20, bold_all=bold))
    out = [tblpr]
    out.append('<w:tr>' + ''.join(cell(h, True) for h in header) + '</w:tr>')
    for r in rows:
        out.append('<w:tr>' + ''.join(cell(c, False) for c in r) + '</w:tr>')
    return '<w:tbl>' + ''.join(out) + '</w:tbl>'


def convert_body(md):
    lines = md.split('\n')
    out = []
    i, n = 0, len(lines)
    in_code = False
    code = []
    while i < n:
        line = lines[i]
        if line.startswith('```'):
            if not in_code:
                in_code, code = True, []
            else:
                for cl in code:
                    out.append(para([(cl, False)], sz=18))
                in_code = False
            i += 1
            continue
        if in_code:
            code.append(line)
            i += 1
            continue
        s = line.strip()
        if s == '' or s in ('---', '***'):
            i += 1
            continue
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            out.append(heading(m.group(2), len(m.group(1))))
            i += 1
            continue
        if (s.startswith('|') and i + 1 < n and '-' in lines[i + 1]
                and re.match(r'^\s*\|?[\s:|-]+\|?\s*$', lines[i + 1])):
            hdr = [c.strip() for c in s.strip('|').split('|')]
            i += 2
            body = []
            while i < n and lines[i].strip().startswith('|'):
                body.append([c.strip() for c in
                             lines[i].strip().strip('|').split('|')])
                i += 1
            out.append(table_xml(hdr, body))
            continue
        m = re.match(r'^\s*(?:[-*]|\d+\.)\s+(.*)$', line)
        if m:
            out.append(para([("•  ", False)] + inline_runs(m.group(1))))
            i += 1
            continue
        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not lines[i].startswith('#') \
                and not lines[i].strip().startswith('|') \
                and not lines[i].startswith('```'):
            buf.append(lines[i])
            i += 1
        out.append(para(inline_runs(' '.join(buf))))
    return ''.join(out)


CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                 '</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>')


def main():
    if len(sys.argv) < 2:
        print("usage: python md2docx.py <input.md> [output.docx]")
        return 2
    src = sys.argv[1]
    with open(src, 'rb') as f:
        md = f.read().decode('utf-8')
    body = convert_body(md)
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document %s><w:body>%s'
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" '
                'w:left="1134"/></w:sectPr></w:body></w:document>' % (NS, body))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + '.docx'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', CONTENT_TYPES)
        z.writestr('_rels/.rels', RELS)
        z.writestr('word/document.xml', document)
    print("wrote %s (%d bytes)" % (out, os.path.getsize(out)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
