# -*- coding: utf-8 -*-
# ======================================================================
#  diagnose.py — Abaqus 실패 로그 자동진단
#
#  .dat / .msg / .log / .sta 를 스캔해 "알려진 오류 패턴"을 찾아
#  원인과 조치를 제안한다. (이 프로젝트에서 실제로 겪은 오류 포함)
#
#  실행:
#    python diagnose.py <job>            # <job>.dat/.msg/.log/.sta 자동탐색
#    python diagnose.py file1.dat file2.msg ...
# ======================================================================
import sys
import os
import re

# (정규식, 심각도, 원인, 조치)
RULES = [
    (r"CONTACT PROPERTY ASSIGNMENT CAN ONLY REFERENCE SURFACE INTERACTIONS",
     "ERROR", "*SURFACE INTERACTION 이 스텝 안에 정의됨(모델데이터 위치 오류)",
     "*SURFACE INTERACTION/*FRICTION 을 첫 *STEP 앞으로 이동. inp_lint.py 로 사전 점검."),
    (r"(Abaqus/Foundation).{0,80}(checked out)",
     "INFO", "Foundation 토큰으로 실행됨(Standard 계열)",
     "VUMAT 관통 해석은 Abaqus/Explicit 토큰 필요 → abaqus licensing ru 확인."),
    (r"(licen[cs]e).{0,60}(not|fail|unavailable|denied|error)|ABAQUSLM|FLEXlm|flexnet.{0,30}error",
     "ERROR", "라이선스 서버/토큰 문제",
     "라이선스 서버(예: 27001@localhost) 데몬 상태 확인·재기동, abaqus licensing ru."),
    (r"catastrophic error|error #\d+|Severe|unresolved external|cannot open include file|vaba_param",
     "ERROR", "서브루틴 컴파일/링크 오류(ifort/ifx)",
     "고정형식(.f, 7열)·double=both·컴파일러 환경 확인, abaqus verify -user_explicit."),
    (r"exited with an error|Abaqus/Analysis exited with errors",
     "ERROR", "해석 중단",
     "같은 잡의 .dat 의 ***ERROR 줄을 확인(가장 구체적)."),
    (r"too many attempts made for this increment|time increment .* less than",
     "ERROR", "증분 수렴 실패/안정증분 과소",
     "질량 스케일링 목표 dt 조정, 메쉬/접촉 점검, 준정적성(ALLKE/ALLIE) 확인."),
    (r"excessively distorted|negative .*jacobian|distortion",
     "ERROR", "요소 과도 왜곡(관통 전 압입 등)",
     "경로 메쉬 세밀화, 질량 스케일링, ALE 적응메쉬(06) 병용, 손상/삭제 기준 재검토."),
    (r"has \d+ nodes .* not .*constrained|numerical singularity|zero pivot",
     "WARN", "구속 부족/특이(강체운동)",
     "경계조건·구속·접촉 초기 관통 여부 확인."),
    (r"must be defined as purely elastic .* stepTime=0",
     "INFO", "VUMAT 초기 탄성 안내(정상)",
     "조치 불필요(informative). 초기 증분 순수탄성 반환이면 정상."),
    (r"THE ANALYSIS HAS COMPLETED SUCCESSFULLY|JOB .* COMPLETED",
     "OK", "해석 정상 완료",
     "후처리(postprocess.py)·보고서(report.py) 진행."),
]

EXTS = [".dat", ".msg", ".log", ".sta"]


def collect(argv):
    files = []
    for a in argv:
        if os.path.isfile(a) and os.path.splitext(a)[1].lower() in EXTS + [".txt"]:
            files.append(a)
        else:
            base = os.path.splitext(a)[0]
            for e in EXTS:
                if os.path.isfile(base + e):
                    files.append(base + e)
    return files


def scan(path):
    hits = []
    try:
        with open(path, 'rb') as f:
            text = f.read().decode('utf-8', 'replace')
    except Exception as e:
        return [("ERROR", "파일 열기 실패", str(e), 0)]
    lines = text.split('\n')
    for i, ln in enumerate(lines):
        for rx, sev, cause, fix in RULES:
            if re.search(rx, ln, re.I):
                hits.append((sev, cause, fix, i + 1))
    return hits


def main():
    if len(sys.argv) < 2:
        print("usage: python diagnose.py <job|file...>")
        return 2
    files = collect(sys.argv[1:])
    if not files:
        print("진단할 파일 없음(.dat/.msg/.log/.sta).")
        return 2

    seen = {}
    order = []
    for path in files:
        for sev, cause, fix, ln in scan(path):
            key = (sev, cause)
            if key not in seen:
                seen[key] = {"sev": sev, "cause": cause, "fix": fix,
                             "where": []}
                order.append(key)
            seen[key]["where"].append("%s:L%d" % (os.path.basename(path), ln))

    print("=" * 64)
    print(" DIAGNOSE :", ", ".join(os.path.basename(f) for f in files))
    print("=" * 64)
    rank = {"ERROR": 0, "WARN": 1, "INFO": 2, "OK": 3}
    n_err = 0
    for key in sorted(order, key=lambda k: rank.get(seen[k]["sev"], 9)):
        d = seen[key]
        if d["sev"] == "ERROR":
            n_err += 1
        print("[%-5s] %s" % (d["sev"], d["cause"]))
        print("        ↳ 조치: %s" % d["fix"])
        print("        ↳ 위치: %s" % ", ".join(d["where"][:5]))
    if not order:
        print("알려진 오류 패턴 없음. .dat 의 ***ERROR 줄을 직접 확인하세요.")
    print("=" * 64)
    return 1 if n_err else 0


if __name__ == '__main__':
    sys.exit(main())
