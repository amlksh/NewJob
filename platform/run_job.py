# -*- coding: utf-8 -*-
# ======================================================================
#  run_job.py — 해석 잡 엔드투엔드 오케스트레이터
#
#  린트 → (Abaqus 실행) → 상태확인 → 실패시 자동진단 →
#  성공시 후처리·이미지·보고서 까지 한 번에.
#
#  실행:
#    python run_job.py --job ref04 --input 04_refined_path.inp \
#           --user vumat_skin.f --project "마이크로니들" --pcr 0.219
#    옵션: --no-run(실행 생략, 기존 odb로 후처리만) --dry-run --force(린트오류 무시)
# ======================================================================
import sys
import os
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import inp_lint      # noqa: E402
import diagnose      # noqa: E402


def sh(cmd, dry):
    print(">>", cmd)
    if dry:
        return 0
    return subprocess.call(cmd, shell=True)


def sta_ok(job):
    p = job + ".sta"
    if not os.path.exists(p):
        return None
    with open(p, 'rb') as f:
        t = f.read().decode('utf-8', 'replace')
    return "COMPLETED SUCCESSFULLY" in t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', required=True)
    ap.add_argument('--input', required=True)
    ap.add_argument('--user', default='')
    ap.add_argument('--abaqus', default='abaqus')
    ap.add_argument('--cpus', type=int, default=4)
    ap.add_argument('--project', default='Abaqus 해석')
    ap.add_argument('--author', default='')
    ap.add_argument('--date', default='')
    ap.add_argument('--pcr', type=float, default=None)
    ap.add_argument('--no-run', action='store_true')
    ap.add_argument('--images', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    dry = a.dry_run

    print("=" * 60)
    print(" RUN JOB :", a.job)
    print("=" * 60)

    # 1) 린트
    print("\n[1/5] 입력파일 린트")
    findings, meta = inp_lint.lint(a.input)
    n_err = sum(1 for s, _, _ in findings if s == inp_lint.ERROR)
    for sev, ln, msg in findings:
        loc = ("L%d" % ln) if ln else "-"
        print("   [%s] %s %s" % (sev, loc, msg))
    if n_err and not a.force:
        print("   → ERROR %d 개. 수정 후 재실행(또는 --force)." % n_err)
        return 1

    # 2) 실행
    if not a.no_run:
        print("\n[2/5] Abaqus 실행")
        uf = ("user=%s double=both " % a.user) if a.user else ""
        cmd = ("%s job=%s input=%s %scpus=%d interactive"
               % (a.abaqus, a.job, a.input, uf, a.cpus))
        rc = sh(cmd, dry)
        if rc != 0 and not dry:
            print("   → 실행 반환코드 %d" % rc)
    else:
        print("\n[2/5] 실행 생략(--no-run)")

    # 3) 상태 확인 + 실패 진단
    print("\n[3/5] 상태 확인")
    ok = sta_ok(a.job)
    if ok is False or (ok is None and not dry and not a.no_run):
        print("   → 완료 아님/불명 → 자동진단")
        old = sys.argv
        sys.argv = ['diagnose', a.job]
        try:
            diagnose.main()
        finally:
            sys.argv = old
        if not a.force:
            return 1
    else:
        print("   → COMPLETED SUCCESSFULLY" if ok else "   → (dry-run/no-run)")

    # 4) 후처리 + 이미지
    print("\n[4/5] 후처리")
    sh("%s python postprocess.py %s.odb" % (a.abaqus, a.job), dry)
    if a.images:
        sh("%s viewer noGUI=odb_snapshot.py -- %s.odb" % (a.abaqus, a.job), dry)

    # 5) 보고서
    print("\n[5/5] 보고서")
    rep = ('python report.py --job %s --dir . --project "%s"'
           % (a.job, a.project))
    if a.author:
        rep += ' --author "%s"' % a.author
    if a.date:
        rep += ' --date %s' % a.date
    if a.pcr is not None:
        rep += ' --pcr %s' % a.pcr
    sh(rep, dry)

    print("\n완료 → %s_report.html" % a.job)
    return 0


if __name__ == '__main__':
    sys.exit(main())
