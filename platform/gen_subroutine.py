# -*- coding: utf-8 -*-
# ======================================================================
#  gen_subroutine.py — Abaqus 사용자 서브루틴 스켈레톤 생성기
#
#  실행:
#    python gen_subroutine.py --type vumat --name mymat --out subroutines
#    타입: vumat | umat | umatht | vdload | dflux
# ======================================================================
import sys
import os
import argparse

HDR = """C ======================================================================
C  {name}.f  ({typ} 스켈레톤)  — 자동생성, 내용 채워 넣으세요
C  실행:  abaqus job=<job> input=<inp> {runopt}
C ======================================================================
"""

VUMAT = """      subroutine vumat(
     1     nblock, ndir, nshr, nstatev, nfieldv, nprops, lanneal,
     2     stepTime, totalTime, dt, cmname, coordMp, charLength,
     3     props, density, strainInc, relSpinInc,
     4     tempOld, stretchOld, defgradOld, fieldOld,
     5     stressOld, stateOld, enerInternOld, enerInelasOld,
     6     tempNew, stretchNew, defgradNew, fieldNew,
     7     stressNew, stateNew, enerInternNew, enerInelasNew )
      include 'vaba_param.inc'
      dimension props(nprops), density(nblock), coordMp(nblock,*),
     1     charLength(nblock), strainInc(nblock,ndir+nshr),
     2     relSpinInc(nblock,nshr), tempOld(nblock),
     3     stretchOld(nblock,ndir+nshr),
     4     defgradOld(nblock,ndir+nshr+nshr),
     5     fieldOld(nblock,nfieldv), stressOld(nblock,ndir+nshr),
     6     stateOld(nblock,nstatev), enerInternOld(nblock),
     7     enerInelasOld(nblock), tempNew(nblock),
     8     stretchNew(nblock,ndir+nshr),
     9     defgradNew(nblock,ndir+nshr+nshr),
     1     fieldNew(nblock,nfieldv),
     2     stressNew(nblock,ndir+nshr), stateNew(nblock,nstatev),
     3     enerInternNew(nblock), enerInelasNew(nblock)
      character*80 cmname
C     TODO: props 로 물성, stretchNew/strainInc 로 응력(동회전) 계산
      do k = 1, nblock
         do i = 1, ndir+nshr
            stressNew(k,i) = stressOld(k,i)
         end do
C        TODO: 상태변수/손상, 삭제조건 시 stateNew(k,1)=0
      end do
      return
      end
"""

UMAT = """      subroutine umat(stress,statev,ddsdde,sse,spd,scd,
     1 rpl,ddsddt,drplde,drpldt,stran,dstran,time,dtime,temp,dtemp,
     2 predef,dpred,cmname,ndi,nshr,ntens,nstatv,props,nprops,
     3 coords,drot,pnewdt,celent,dfgrd0,dfgrd1,noel,npt,layer,kspt,
     4 kstep,kinc)
      include 'aba_param.inc'
      character*80 cmname
      dimension stress(ntens),statev(nstatv),ddsdde(ntens,ntens),
     1 ddsddt(ntens),drplde(ntens),stran(ntens),dstran(ntens),
     2 time(2),predef(1),dpred(1),props(nprops),coords(3),drot(3,3),
     3 dfgrd0(3,3),dfgrd1(3,3)
C     TODO: ddsdde(자코비안)과 stress 갱신
      return
      end
"""

UMATHT = """      subroutine umatht(u,dudt,dudg,flux,dfdt,dfdg,
     1 statev,temp,dtemp,dtemdx,time,dtime,predef,dpred,
     2 cmname,ntgrd,nstatv,props,nprops,coords,pnewdt,noel,npt,
     3 layer,kspt,kstep,kinc)
      include 'aba_param.inc'
      character*80 cmname
      dimension dudg(ntgrd),flux(ntgrd),dfdt(ntgrd),
     1 dfdg(ntgrd,ntgrd),statev(nstatv),dtemdx(ntgrd),
     2 time(2),predef(1),dpred(1),props(nprops),coords(3)
C     TODO: 내부에너지 u/dudt, 열유속 flux/dfdg 갱신
      return
      end
"""

VDLOAD = """      subroutine vdload(
     1 nblock, ndim, stepTime, totalTime, amplitude, curCoords,
     2 velocity, dirCos, jltyp, sname, value )
      include 'vaba_param.inc'
      dimension curCoords(nblock,ndim), velocity(nblock,ndim),
     1 dirCos(nblock,ndim,ndim), value(nblock)
      character*80 sname
      do k = 1, nblock
         value(k) = 0.d0
C        TODO: 위치/시간 종속 분포하중
      end do
      return
      end
"""

DFLUX = """      subroutine dflux(flux,sol,kstep,kinc,time,noel,npt,coords,
     1 jltyp,temp,press,sname)
      include 'aba_param.inc'
      dimension flux(2),time(2),coords(3)
      character*80 sname
C     TODO: flux(1)=크기.  이동열원이면 coords/time 사용
      flux(1) = 0.d0
      return
      end
"""

BODIES = {"vumat": VUMAT, "umat": UMAT, "umatht": UMATHT,
          "vdload": VDLOAD, "dflux": DFLUX}
RUNOPT = {"vumat": "user=%s.f double=both", "vdload": "user=%s.f double=both",
          "umat": "user=%s.f", "umatht": "user=%s.f", "dflux": "user=%s.f"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--type', required=True, choices=list(BODIES.keys()))
    ap.add_argument('--name', default=None)
    ap.add_argument('--out', default='.')
    a = ap.parse_args()
    name = a.name or (a.type + "_skeleton")
    body = BODIES[a.type]
    hdr = HDR.format(name=name, typ=a.type.upper(),
                     runopt=(RUNOPT[a.type] % name))
    if not os.path.isdir(a.out):
        os.makedirs(a.out)
    out = os.path.join(a.out, name + ".f")
    with open(out, 'wb') as f:
        f.write((hdr + body).encode('utf-8'))
    print("wrote %s  (%s)" % (out, a.type))
    return 0


if __name__ == '__main__':
    sys.exit(main())
