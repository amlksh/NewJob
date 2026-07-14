# -*- coding: utf-8 -*-
# ======================================================================
#  postprocess.py   (Abaqus Python / Python 2.7)
#
#  마이크로니들 관통 해석 결과(.odb) 종합 리포트:
#    1) 관통력–침투깊이 곡선 (NREF의 U2/RF2 또는 U3/RF3)  -> <base>_fd.csv
#    2) 에너지 요약 + 준정적성 판정 (ALLKE/ALLIE 최대비)
#    3) 요소 삭제(관통) 개수 (STATUS 필드) + 손상 SDV 요약
#    4) (matplotlib 있으면) 힘–깊이 그래프  -> <base>_fd.png
#
#  실행:  abaqus python postprocess.py <job>.odb
# ======================================================================
import sys
import os
from odbAccess import openOdb


# ---------- 1) 관통력–침투깊이 ----------
def _find_reg(step):
    for name, hr in step.historyRegions.items():
        ho = hr.historyOutputs
        for u, rf in (('U3', 'RF3'), ('U2', 'RF2')):
            if (u in ho) and (rf in ho):
                return hr, u, rf
    return None, None, None


def force_depth(step):
    reg, uc, rfc = _find_reg(step)
    if reg is None:
        return None
    uu = dict(reg.historyOutputs[uc].data)
    rr = dict(reg.historyOutputs[rfc].data)
    rows = []
    for t in sorted(uu.keys()):
        if t in rr:
            rows.append((t, -uu[t], -rr[t]))   # depth(+), force(+)
    return rows


# ---------- 2) 에너지 / 준정적성 ----------
def energy_hist(step):
    keys = ['ALLIE', 'ALLKE', 'ALLSE', 'ALLWK', 'ALLAE', 'ALLDMD']
    out = {}
    for name, hr in step.historyRegions.items():
        for k in keys:
            if k in hr.historyOutputs and k not in out:
                out[k] = dict(hr.historyOutputs[k].data)
    return out


# ---------- 3) 요소 삭제 / 손상 ----------
def deletion_report(step, n_total):
    frames = step.frames
    if not frames:
        return None
    last = frames[-1]
    fo = last.fieldOutputs
    info = {'n_total': n_total}
    # STATUS 필드로 활성 요소 판정
    if 'STATUS' in fo:
        vals = fo['STATUS'].values
        active = 0
        present = 0
        for v in vals:
            present += 1
            if v.data > 0.5:
                active += 1
        info['status_present'] = present
        info['status_active'] = active
        info['deleted'] = max(0, n_total - active)
    # SDV 손상(DAMAGE=SDV3) 최대값
    for nm in ('SDV3', 'SDV_DAMAGE', 'SDV3_DAMAGE'):
        if nm in fo:
            dmax = 0.0
            for v in fo[nm].values:
                if v.data > dmax:
                    dmax = v.data
            info['damage_max'] = dmax
            break
    # SDV2 = 최대 주신축비(LAMMAX)
    for nm in ('SDV2', 'SDV_LAMMAX'):
        if nm in fo:
            lmax = 0.0
            for v in fo[nm].values:
                if v.data > lmax:
                    lmax = v.data
            info['lammax'] = lmax
            break
    return info


def main():
    odb_path = sys.argv[1] if len(sys.argv) > 1 else 'microneedle.odb'
    base = os.path.splitext(os.path.basename(odb_path))[0]
    odb = openOdb(odb_path, readOnly=True)

    names = list(odb.steps.keys())
    if 'INSERTION' in names:
        step = odb.steps['INSERTION']
    elif 'PENETRATION' in names:
        step = odb.steps['PENETRATION']
    else:
        step = odb.steps[names[-1]]

    # 요소 총수
    n_total = 0
    try:
        for inst in odb.rootAssembly.instances.values():
            n_total += len(inst.elements)
    except Exception:
        n_total = 0

    print('=' * 64)
    print(' MICRONEEDLE PENETRATION REPORT :  %s' % base)
    print('   step = %s   frames = %d   elements = %d'
          % (step.name, len(step.frames), n_total))
    print('=' * 64)

    # --- 1) 힘-깊이 ---
    rows = force_depth(step)
    peak = None
    if rows:
        with open(base + '_fd.csv', 'w') as f:
            f.write('time_s,depth_mm,force_N\n')
            for t, d, p in rows:
                f.write('%.6e,%.6e,%.6e\n' % (t, d, p))
        peak = max(rows, key=lambda r: r[2])
        final = rows[-1]
        print('[1] 관통력-침투깊이  (-> %s_fd.csv, %d pts)' % (base, len(rows)))
        print('    peak insertion force = %.5f N  at depth = %.4f mm'
              % (peak[2], peak[1]))
        print('    final depth = %.4f mm ,  final force = %.5f N'
              % (final[1], final[2]))
        # puncture(급락) 감지: peak 이후 force가 peak의 70% 이하로 떨어지면
        drop = False
        for t, d, p in rows:
            if d > peak[1] and p < 0.7 * peak[2]:
                drop = True
                break
        print('    puncture(peak 이후 30%%+ 급락) 감지: %s'
              % ('YES (관통 개시 정황)' if drop else 'NO (압입 위주일 수 있음)'))
    else:
        print('[1] 관통력 이력 없음 - *NODE OUTPUT(NREF, U2/RF2) 확인 필요')

    # --- 2) 에너지 / 준정적성 ---
    en = energy_hist(step)
    if 'ALLIE' in en and 'ALLKE' in en:
        ie = en['ALLIE']
        ke = en['ALLKE']
        ie_final = ie[max(ie.keys())]
        ke_max = max(ke.values()) if ke else 0.0
        ratio = (ke_max / ie_final * 100.0) if ie_final else 0.0
        print('[2] 에너지 / 준정적성')
        print('    ALLIE(final) = %.4e mJ   ALLKE(max) = %.4e mJ'
              % (ie_final, ke_max))
        print('    ALLKE/ALLIE(max) = %.2f %%   -> %s'
              % (ratio, '양호(<5%)' if ratio < 5 else
                 ('주의(5~10%)' if ratio < 10 else '과함(>10%): 질량스케일링 재검토')))
        if 'ALLDMD' in en:
            dm = en['ALLDMD']
            print('    ALLDMD(final, 손상소산) = %.4e mJ'
                  % dm[max(dm.keys())])
    else:
        print('[2] 에너지 이력 없음 - *ENERGY OUTPUT(ALLIE,ALLKE...) 확인')

    # --- 3) 요소 삭제 / 손상 ---
    di = deletion_report(step, n_total)
    if di:
        print('[3] 요소 삭제 / 손상 (마지막 프레임)')
        if 'deleted' in di:
            print('    deleted(관통) elements = %d / %d  (활성 %d)'
                  % (di['deleted'], di['n_total'], di.get('status_active', -1)))
            if di['deleted'] == 0:
                print('    -> 삭제 0: 관통(절개) 미발생. 압입만 했거나 '
                      'lam_f/uf 가 큼. 물성/하강량 조정 필요할 수 있음.')
        if 'damage_max' in di:
            print('    max damage(SDV3) = %.3f' % di['damage_max'])
        if 'lammax' in di:
            print('    max principal stretch(SDV2) = %.3f' % di['lammax'])

    odb.close()

    # --- 4) 그래프 ---
    if rows:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            d = [r[1] for r in rows]
            p = [r[2] for r in rows]
            plt.figure(figsize=(6, 4))
            plt.plot(d, p, '-b', lw=1.6)
            if peak:
                plt.plot([peak[1]], [peak[2]], 'ro')
                plt.annotate('peak %.3f N' % peak[2],
                             xy=(peak[1], peak[2]))
            plt.xlabel('Penetration depth [mm]')
            plt.ylabel('Insertion force [N]')
            plt.title('Insertion force-depth: ' + base)
            plt.grid(True, ls=':')
            plt.tight_layout()
            plt.savefig(base + '_fd.png', dpi=150)
            print('[4] 그래프 -> %s_fd.png' % base)
        except Exception as e:
            print('[4] plot skipped: %s' % e)
    print('=' * 64)


if __name__ == '__main__':
    main()
