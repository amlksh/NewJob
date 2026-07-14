# -*- coding: utf-8 -*-
# ======================================================================
#  selftest.py — platform 도구 자기검증 (CI에서 실행)
#  실행:  python tests/selftest.py     (성공 시 종료코드 0)
# ======================================================================
import sys
import os
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLAT = os.path.dirname(HERE)
sys.path.insert(0, PLAT)

import inp_lint      # noqa: E402
import diagnose      # noqa: E402
import gen_subroutine  # noqa: E402

fails = []


def check(name, cond):
    print(("  PASS " if cond else "  FAIL ") + name)
    if not cond:
        fails.append(name)


GOOD_INP = """*HEADING
t
*SURFACE INTERACTION, NAME=IPROP
*FRICTION
0.1,
*MATERIAL, NAME=M
*USER MATERIAL, CONSTANTS=4
1,1,1,1
*DEPVAR, DELETE=1
4
*STEP
*DYNAMIC, EXPLICIT
,0.01
*CONTACT PROPERTY ASSIGNMENT
 , , IPROP
*END STEP
"""

BAD_INP = """*HEADING
t
*STEP
*DYNAMIC, EXPLICIT
,0.01
*CONTACT PROPERTY ASSIGNMENT
 , , IPROP
*SURFACE INTERACTION, NAME=IPROP
*FRICTION
0.1,
*END STEP
"""


def w(txt, suffix=".inp"):
    fd, p = tempfile.mkstemp(suffix=suffix)
    os.write(fd, txt.encode('utf-8'))
    os.close(fd)
    return p


def main():
    print("== inp_lint ==")
    p = w(GOOD_INP)
    F, meta = inp_lint.lint(p)
    nerr = sum(1 for s, _, _ in F if s == inp_lint.ERROR)
    check("정상 inp -> ERROR 0", nerr == 0)
    os.remove(p)

    p = w(BAD_INP)
    F, meta = inp_lint.lint(p)
    nerr = sum(1 for s, _, _ in F if s == inp_lint.ERROR)
    msgs = " ".join(m for _, _, m in F)
    check("SURFACE INTERACTION 스텝뒤 -> ERROR 검출", nerr >= 1)
    check("오류메시지에 SURFACE INTERACTION 언급", "SURFACE INTERACTION" in msgs)
    os.remove(p)

    print("== diagnose ==")
    p = w("***ERROR: *CONTACT PROPERTY ASSIGNMENT CAN ONLY REFERENCE "
          "SURFACE INTERACTIONS THAT ARE\n", ".dat")
    hits = diagnose.scan(p)
    causes = " ".join(c for _, c, _, _ in hits)
    check("diagnose가 SURFACE INTERACTION 원인 식별", "SURFACE INTERACTION" in causes)
    os.remove(p)

    p = w("THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n", ".sta")
    hits = diagnose.scan(p)
    sevs = [s for s, _, _, _ in hits]
    check("diagnose가 성공완료 인식", "OK" in sevs)
    os.remove(p)

    print("== gen_subroutine ==")
    d = tempfile.mkdtemp()
    for t in ("vumat", "umat", "umatht", "vdload", "dflux"):
        sys.argv = ['g', '--type', t, '--name', 'x_' + t, '--out', d]
        gen_subroutine.main()
        f = os.path.join(d, 'x_' + t + '.f')
        ok = os.path.exists(f) and os.path.getsize(f) > 200
        check("스켈레톤 생성 " + t, ok)

    print()
    if fails:
        print("실패 %d: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("모든 자기검증 통과")
    return 0


if __name__ == '__main__':
    sys.exit(main())
