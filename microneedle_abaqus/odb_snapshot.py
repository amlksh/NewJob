# -*- coding: utf-8 -*-
# ======================================================================
#  odb_snapshot.py  —  Abaqus/Viewer 헤드리스 이미지(PNG) 자동 추출
#
#  .odb를 열어 마지막 프레임의 변형형상 + 주요 필드를 PNG로 저장한다.
#  요소 삭제(관통)된 부분은 뷰어가 자동으로 비워 표시하므로, 관통 경로가
#  이미지로 바로 확인된다.
#
#  실행 (Abaqus 환경, GUI 불필요):
#      abaqus viewer noGUI=odb_snapshot.py -- ref04.odb
#
#  산출물:
#      <base>_mises.png    변형형상 + von Mises 응력
#      <base>_damage.png   변형형상 + 손상 SDV3 (있으면)
#      <base>_stretch.png  변형형상 + 최대주신축비 SDV2 (있으면)
#      <base>_status.png   변형형상 + STATUS (삭제요소 시각화, 있으면)
#      <base>_deformed.png 변형형상(외곽/메쉬) — 관통 채널 확인
# ======================================================================
from abaqus import session
from abaqusConstants import *
import sys
import os


def get_odb_path():
    argv = sys.argv
    if '--' in argv:
        rest = argv[argv.index('--') + 1:]
        if rest:
            return rest[0]
    for a in argv:
        if a.lower().endswith('.odb'):
            return a
    return 'ref04.odb'


def main():
    odb_path = get_odb_path()
    base = os.path.splitext(os.path.basename(odb_path))[0]
    odb = session.openOdb(odb_path, readOnly=True)

    # noGUI viewer 호환: 새 뷰포트를 만들면 'expecting StubType' 오류가 나므로
    # 기본 뷰포트('Viewport: 1')를 사용한다.
    if 'Viewport: 1' in session.viewports.keys():
        vp = session.viewports['Viewport: 1']
    else:
        vp = session.Viewport(name='Viewport: 1', origin=(0, 0),
                              width=240, height=180)
    vp.makeCurrent()
    vp.setValues(displayedObject=odb)

    # 마지막 스텝의 마지막 프레임
    n_step = len(odb.steps)
    vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    try:
        vp.odbDisplay.setFrame(step=n_step - 1, frame=-1)
    except Exception:
        vp.odbDisplay.setFrame(step=0, frame=-1)

    vp.view.fitView()
    session.pngOptions.setValues(imageSize=(1600, 1200))
    session.printOptions.setValues(vpDecorations=ON, reduceColors=False)

    def shot(label, fname, invariant=None, position=INTEGRATION_POINT):
        try:
            if invariant:
                vp.odbDisplay.setPrimaryVariable(
                    variableLabel=label, outputPosition=position,
                    refinement=(INVARIANT, invariant))
            else:
                vp.odbDisplay.setPrimaryVariable(
                    variableLabel=label, outputPosition=position)
            vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
            vp.view.fitView()
            session.printToFile(fileName=base + fname, format=PNG,
                                canvasObjects=(vp,))
            print('  wrote %s%s.png' % (base, fname))
            return True
        except Exception as e:
            print('  skip %s%s.png : %s' % (base, fname, e))
            return False

    print('=' * 56)
    print(' ODB SNAPSHOTS : %s (steps=%d)' % (base, n_step))
    print('=' * 56)

    # 1) von Mises 응력
    shot('S', '_mises', invariant='Mises')
    # 2) 손상 SDV3
    shot('SDV3', '_damage')
    # 3) 최대 주신축비 SDV2
    shot('SDV2', '_stretch')
    # 4) STATUS (삭제 요소)
    shot('STATUS', '_status')

    # 5) 변형형상(외곽선) — 관통 채널/삭제 시각화
    try:
        vp.odbDisplay.display.setValues(plotState=(DEFORMED,))
        vp.odbDisplay.commonOptions.setValues(
            visibleEdges=FEATURE)
        vp.view.fitView()
        session.printToFile(fileName=base + '_deformed', format=PNG,
                            canvasObjects=(vp,))
        print('  wrote %s_deformed.png' % base)
    except Exception as e:
        print('  skip %s_deformed.png : %s' % (base, e))

    odb.close()
    print('=' * 56)
    print(' done. (이미지가 안 뜨면 GUI 없이도 PNG는 저장됩니다)')


if __name__ == '__main__' or True:
    main()
