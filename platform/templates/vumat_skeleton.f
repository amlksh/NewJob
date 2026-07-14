C ======================================================================
C  vumat_skeleton.f — VUMAT 시작 템플릿 (직접 채워 넣으세요)
C
C  실행:  abaqus job=<job> input=<inp> user=vumat_skeleton.f double=both
C  물성:  *USER MATERIAL, CONSTANTS=n  /  상태변수: *DEPVAR (DELETE=k)
C ======================================================================
      subroutine vumat(
     1     nblock, ndir, nshr, nstatev, nfieldv, nprops, lanneal,
     2     stepTime, totalTime, dt, cmname, coordMp, charLength,
     3     props, density, strainInc, relSpinInc,
     4     tempOld, stretchOld, defgradOld, fieldOld,
     5     stressOld, stateOld, enerInternOld, enerInelasOld,
     6     tempNew, stretchNew, defgradNew, fieldNew,
     7     stressNew, stateNew, enerInternNew, enerInelasNew )
C
      include 'vaba_param.inc'
C
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
C
      character*80 cmname
      parameter ( zero=0.d0, one=1.d0, two=2.d0 )
C
C     예시: 선형 등방 탄성 (E=props(1), nu=props(2))
      e   = props(1)
      xnu = props(2)
      alam = e*xnu/((one+xnu)*(one-two*xnu))
      amu  = e/(two*(one+xnu))
C
      do k = 1, nblock
C        TODO: strainInc 로 응력 갱신 (동회전 좌표계)
         do i = 1, ndir
            stressNew(k,i) = stressOld(k,i)
     1         + alam*(strainInc(k,1)+strainInc(k,2)+strainInc(k,3))
     2         + two*amu*strainInc(k,i)
         end do
         do i = ndir+1, ndir+nshr
            stressNew(k,i) = stressOld(k,i) + two*amu*strainInc(k,i)
         end do
C        TODO: 손상/상태변수 갱신, 삭제조건 시 stateNew(k,1)=0
      end do
C
      return
      end
