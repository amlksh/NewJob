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


def extract(odb_path):
    odb = openOdb(odb_path, readOnly=True)
    step = odb.steps['PENETRATION']

    # 니들 참조점 히스토리 영역 탐색
    reg = None
    for name, hr in step.historyRegions.items():
        if ('U2' in hr.historyOutputs) and ('RF2' in hr.historyOutputs):
            reg = hr
            break
    if reg is None:
        raise RuntimeError('RF2/U2 history output not found - '
                           'check *NODE OUTPUT for NREF')

    u2 = dict(reg.historyOutputs['U2'].data)
    rf2 = dict(reg.historyOutputs['RF2'].data)

    rows = []
    for t in sorted(u2.keys()):
        if t in rf2:
            depth = -u2[t]          # 하강(+) 침투깊이
            force = -rf2[t]          # 조직이 니들에 가하는 저항력(+)
            rows.append((t, depth, force))
    odb.close()
    return rows


def main():
    odb_path = sys.argv[1] if len(sys.argv) > 1 else 'microneedle.odb'
    rows = extract(odb_path)

    with open('force_displacement.csv', 'w') as f:
        f.write('time_s,depth_mm,force_N\n')
        for t, d, p in rows:
            f.write('%.6e,%.6e,%.6e\n' % (t, d, p))
    print('wrote force_displacement.csv (%d points)' % len(rows))

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
        plt.title('Microneedle insertion force-depth')
        plt.grid(True, ls=':')
        plt.tight_layout()
        plt.savefig('force_displacement.png', dpi=150)
        print('wrote force_displacement.png')
    except Exception as e:
        print('plot skipped: %s' % e)


if __name__ == '__main__':
    main()
