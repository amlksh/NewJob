# -*- coding: utf-8 -*-
# ======================================================================
#  inp_lint.py — Abaqus 입력파일(.inp) 사전 린터
#
#  해석을 돌리기 전에, 흔히 겪는(그리고 이 프로젝트에서 실제로 겪은)
#  치명적 오류를 정적으로 잡아낸다. pre.exe가 죽기 전에 미리 알려줌.
#
#  실행:  python inp_lint.py <file1.inp> [file2.inp ...]
#  종료코드: ERROR가 하나라도 있으면 1, 아니면 0
# ======================================================================
import sys
import re

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"


def kw_of(line):
    """'*KEYWORD, p=v' -> ('KEYWORD', {params})   주석(**)·데이터는 None"""
    s = line.strip()
    if not s.startswith('*') or s.startswith('**'):
        return None, None
    body = s[1:]
    parts = [p.strip() for p in body.split(',')]
    name = parts[0].upper()
    params = {}
    for p in parts[1:]:
        if '=' in p:
            k, v = p.split('=', 1)
            params[k.strip().upper()] = v.strip()
        elif p:
            params[p.strip().upper()] = True
    return name, params


def lint(path):
    with open(path, 'rb') as f:
        lines = f.read().decode('utf-8', 'replace').split('\n')
    F = []  # (severity, lineno, msg)

    def add(sev, ln, msg):
        F.append((sev, ln, msg))

    first_step = None
    n_step = n_endstep = 0
    si_names = set()          # *SURFACE INTERACTION 로 정의된 이름
    si_lines = []             # (lineno) of *SURFACE INTERACTION
    cpa_refs = []             # (lineno, name) CONTACT PROPERTY ASSIGNMENT 참조
    has_user_mat = False
    has_explicit = False
    depvar_ctx = None         # (lineno, delete_k) 대기: 다음 데이터=개수
    mat_count = 0
    elem_types = set()

    i = 0
    while i < len(lines):
        name, params = kw_of(lines[i])
        ln = i + 1
        if name is None:
            i += 1
            continue

        if name == 'STEP':
            n_step += 1
            if first_step is None:
                first_step = ln
        elif name == 'ENDSTEP' or name == 'END STEP':
            n_endstep += 1
        elif name == 'SURFACE INTERACTION':
            si_lines.append(ln)
            if 'NAME' in params:
                si_names.add(params['NAME'].upper())
        elif name == 'CONTACT PROPERTY ASSIGNMENT':
            # 다음 데이터 라인들: "surf1, surf2, INTERACTION"
            j = i + 1
            while j < len(lines):
                nn, _ = kw_of(lines[j])
                if nn is not None or lines[j].strip() == '':
                    if lines[j].strip() == '':
                        j += 1
                        continue
                    break
                cells = [c.strip() for c in lines[j].split(',')]
                if len(cells) >= 3 and cells[2]:
                    cpa_refs.append((j + 1, cells[2].upper()))
                j += 1
        elif name == 'USER MATERIAL':
            has_user_mat = True
        elif name == 'MATERIAL':
            mat_count += 1
        elif name == 'DYNAMIC':
            if params and 'EXPLICIT' in params:
                has_explicit = True
        elif name == 'ELEMENT':
            if 'TYPE' in params:
                elem_types.add(params['TYPE'].upper())
        elif name == 'DEPVAR':
            k = None
            if 'DELETE' in params and params['DELETE'] is not True:
                try:
                    k = int(params['DELETE'])
                except ValueError:
                    k = None
            # 다음 비어있지 않은 데이터 = SDV 개수
            j = i + 1
            cnt = None
            while j < len(lines):
                if lines[j].strip() == '':
                    j += 1
                    continue
                nn, _ = kw_of(lines[j])
                if nn is not None:
                    break
                try:
                    cnt = int(lines[j].split(',')[0])
                except ValueError:
                    cnt = None
                break
            if k is not None and cnt is not None and k > cnt:
                add(ERROR, ln, "*DEPVAR DELETE=%d 인데 SDV 개수는 %d "
                    "(삭제변수 인덱스가 개수 초과)" % (k, cnt))
        i += 1

    # --- 규칙 판정 ---
    # R1: *SURFACE INTERACTION 은 모델 데이터(첫 *STEP 앞)
    if first_step is not None:
        for sln in si_lines:
            if sln > first_step:
                add(ERROR, sln, "*SURFACE INTERACTION 이 *STEP(줄 %d) 뒤에 "
                    "있음. 모델 데이터로 첫 *STEP 앞으로 이동해야 함 "
                    "(*CONTACT PROPERTY ASSIGNMENT가 참조 못 함)." % first_step)

    # R2: CONTACT PROPERTY ASSIGNMENT 가 참조하는 상호작용이 정의됐는가
    for (rln, nm) in cpa_refs:
        if nm not in si_names:
            add(ERROR, rln, "*CONTACT PROPERTY ASSIGNMENT 이 참조하는 "
                "'%s' 가 *SURFACE INTERACTION으로 정의되지 않음." % nm)

    # R3: STEP / END STEP 균형
    if n_step != n_endstep:
        add(ERROR, 0, "*STEP(%d) 와 *END STEP(%d) 개수 불일치."
            % (n_step, n_endstep))

    # R4: 런타임 플래그 리마인더
    if has_user_mat:
        add(WARN, 0, "사용자 재료(*USER MATERIAL) 사용 → 실행 시 "
            "`user=..f double=both` 필수 (린터가 실행옵션은 못 봄).")
    if has_explicit:
        add(INFO, 0, "Abaqus/Explicit 해석 → Explicit 라이선스 토큰 필요 "
            "(`abaqus licensing ru`로 확인).")

    return F, {
        'materials': mat_count, 'elem_types': sorted(elem_types),
        'steps': n_step, 'surface_interactions': len(si_names),
    }


def main():
    if len(sys.argv) < 2:
        print("usage: python inp_lint.py <file.inp> [...]")
        return 2
    worst = 0
    for path in sys.argv[1:]:
        try:
            F, meta = lint(path)
        except Exception as e:
            print("[%s] 열기 실패: %s" % (path, e))
            worst = 1
            continue
        n_err = sum(1 for s, _, _ in F if s == ERROR)
        n_wrn = sum(1 for s, _, _ in F if s == WARN)
        print("=" * 62)
        print(" LINT: %s" % path)
        print("   재료=%d, 요소=%s, 스텝=%d, SURFACE INTERACTION=%d"
              % (meta['materials'], ",".join(meta['elem_types']) or '-',
                 meta['steps'], meta['surface_interactions']))
        print("   -> ERROR %d, WARN %d" % (n_err, n_wrn))
        for sev, ln, msg in sorted(F, key=lambda x: (x[0] != ERROR, x[1])):
            loc = ("L%d" % ln) if ln else "  -"
            print("   [%-5s] %-5s %s" % (sev, loc, msg))
        if not F:
            print("   문제 없음 (clean)")
        if n_err:
            worst = 1
    print("=" * 62)
    return worst


if __name__ == '__main__':
    sys.exit(main())
