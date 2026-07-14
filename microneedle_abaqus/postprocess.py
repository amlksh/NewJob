# -*- coding: utf-8 -*-
# ======================================================================
#  postprocess.py
#
#  마이크로니들 관통 해석 결과(.odb)에서 니들 참조점의
#  하강 변위(U2)와 반력(RF2)을 추출해 관통력-침투깊이 곡선을 생성.
#
#  실행 (Abaqus Python 환경):
#      abaqus python postprocess.py microneedle.odb
#
#  결과:
#      force_displacement.csv   (침투깊이[mm], 관통력[N])
#  matplotlib 이 있으면 force_displacement.png 도 함께 생성.
# ======================================================================
import sys
from odbAccess import openOdb


def _find_reg(step):
    """니들 참조점 히스토리 영역과 하강방향 성분(U2/RF2 또는 U3/RF3)을 탐색."""
    for name, hr in step.historyRegions.items():
        ho = hr.historyOutputs
        for u, rf in (('U3', 'RF3'), ('U2', 'RF2')):
            if (u in ho) and (rf in ho):
                return hr, u, rf
    return None, None, None


def extract(odb_path):
    odb = openOdb(odb_path, readOnly=True)

    # 삽입 스텝 자동 선택 (INSERTION > PENETRATION > 마지막 스텝)
    names = list(odb.steps.keys())
    if 'INSERTION' in names:
        step = odb.steps['INSERTION']
    elif 'PENETRATION' in names:
        step = odb.steps['PENETRATION']
    else:
        step = odb.steps[names[-1]]

    reg, uc, rfc = _find_reg(step)
    if reg is None:
        raise RuntimeError('RF/U history output for NREF not found - '
                           'check *NODE OUTPUT (U2/RF2 or U3/RF3)')

    uu = dict(reg.historyOutputs[uc].data)
    rr = dict(reg.historyOutputs[rfc].data)

    rows = []
    for t in sorted(uu.keys()):
        if t in rr:
            depth = -uu[t]          # 하강(+) 침투깊이
            force = -rr[t]           # 조직이 니들에 가하는 저항력(+)
            rows.append((t, depth, force))
    odb.close()
    return rows


def main():
    import os
    odb_path = sys.argv[1] if len(sys.argv) > 1 else 'microneedle.odb'
    base = os.path.splitext(os.path.basename(odb_path))[0]
    rows = extract(odb_path)

    csv_name = base + '_fd.csv'
    with open(csv_name, 'w') as f:
        f.write('time_s,depth_mm,force_N\n')
        for t, d, p in rows:
            f.write('%.6e,%.6e,%.6e\n' % (t, d, p))
    print('wrote %s (%d points)' % (csv_name, len(rows)))

    # 관통 개시(peak) 지점 리포트
    if rows:
        pk = max(rows, key=lambda r: r[2])
        print('peak force = %.4f N at depth = %.4f mm' % (pk[2], pk[1]))

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        d = [r[1] for r in rows]
        p = [r[2] for r in rows]
        plt.figure(figsize=(6, 4))
        plt.plot(d, p, '-b', lw=1.6)
        plt.xlabel('Penetration depth [mm]')
        plt.ylabel('Insertion force [N]')
        plt.title('Insertion force-depth: ' + base)
        plt.grid(True, ls=':')
        plt.tight_layout()
        plt.savefig(base + '_fd.png', dpi=150)
        print('wrote %s_fd.png' % base)
    except Exception as e:
        print('plot skipped: %s' % e)


if __name__ == '__main__':
    main()
