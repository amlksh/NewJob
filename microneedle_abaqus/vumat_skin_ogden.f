C ======================================================================
C  vumat_skin_ogden.f
C
C  Abaqus/Explicit VUMAT : 1차(N=1) Ogden 초탄성 + 요소삭제
C  파단기준 = von Mises 응력 OR 등가 로그변형 (둘 중 먼저 도달 시 삭제).
C
C  근거: Yolai et al., "Finite element analysis of polymeric microneedle
C        insertion into skin", Materials & Design 259 (2025) 114936.
C        -> 피부를 1차 Ogden 초탄성, 파단은 층별 von Mises 응력 + 등가
C           변형 기준의 "요소삭제 알고리즘"으로 모사(cohesive 미사용).
C
C  재료 상수 (PROPS), *USER MATERIAL, CONSTANTS=5
C    PROPS(1) = mu     Ogden 전단계수 [MPa]
C    PROPS(2) = alpha  Ogden 지수
C    PROPS(3) = D1     체적 파라미터 [1/MPa]  (K = 2/D1)
C    PROPS(4) = sigf   파단 von Mises 응력 [MPa]
C    PROPS(5) = epsf   파단 등가 로그변형 [-]
C
C  상태 변수 (STATEV), *DEPVAR = 4, DELETE = 1
C    STATEV(1) = 삭제 플래그 (1=유지, 0=삭제)   <-- DELETE 지정 변수
C    STATEV(2) = von Mises 응력 [MPa]
C    STATEV(3) = 등가 로그변형 [-]
C    STATEV(4) = 상대 체적 J = det(U)
C
C  성분 규약: 축대칭 CAX4R (ndir=3: 11,22,33 ; nshr=1: 12).
C    평면(11,22,12) 2x2 고유치 + 후프(33) -> 주응력 -> 회전복원.
C
C  단위: 길이 mm, 힘 N, 응력 MPa, 질량 tonne, 시간 s (논문과 동일).
C  실행: abaqus job=.. input=17_needle_paper.inp user=vumat_skin_ogden.f
C        double=both cpus=4 interactive
C ======================================================================
      subroutine vumat(
C Read only -
     1     nblock, ndir, nshr, nstatev, nfieldv, nprops, lanneal,
     2     stepTime, totalTime, dt, cmname, coordMp, charLength,
     3     props, density, strainInc, relSpinInc,
     4     tempOld, stretchOld, defgradOld, fieldOld,
     5     stressOld, stateOld, enerInternOld, enerInelasOld,
C Write only -
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
C
      parameter ( zero = 0.d0, one = 1.d0, two = 2.d0, three = 3.d0,
     1            half = 0.5d0, third = 1.d0/3.d0 )
C
C --- 재료 상수 ----------------------------------------------------------
      amu   = props(1)
      alpha = props(2)
      d1    = props(3)
      sigf  = props(4)
      epsf  = props(5)
      if ( d1 .gt. zero ) then
         akmod = two / d1
      else
         akmod = zero
      end if
C
C --- 적분점(블록) 루프 --------------------------------------------------
      do k = 1, nblock
C
C     좌 신축텐서 U (동회전) : U11,U22,U33,U12 (축대칭)
         u11 = stretchNew(k,1)
         u22 = stretchNew(k,2)
         u33 = stretchNew(k,3)
         u12 = zero
         if ( nshr .ge. 1 ) u12 = stretchNew(k,ndir+1)
C
C     평면(11,22,12) 2x2 주신축비 + 회전
         savg = half * ( u11 + u22 )
         dd   = half * ( u11 - u22 )
         rr   = sqrt( dd*dd + u12*u12 )
         al1  = savg + rr
         al2  = savg - rr
         al3  = u33
         if ( al1 .le. zero ) al1 = 1.d-6
         if ( al2 .le. zero ) al2 = 1.d-6
         if ( al3 .le. zero ) al3 = 1.d-6
         if ( rr .gt. 1.d-12 ) then
            c2 = dd / rr
            s2 = u12 / rr
         else
            c2 = one
            s2 = zero
         end if
         cc = half * ( one + c2 )              ! cos^2 th
         ss = half * ( one - c2 )              ! sin^2 th
         cs = half * s2                        ! sin th cos th
C
C     J 와 등체적 주신축비
         aj = al1 * al2 * al3
         if ( aj .le. zero ) aj = 1.d-6
         ajm13 = aj ** ( -third )
         b1 = ajm13 * al1
         b2 = ajm13 * al2
         b3 = ajm13 * al3
C
C     1차 Ogden 주 Cauchy 응력
C        sig_i = (2 mu)/(alpha J) ( bbar_i^a - mean ) + (2/D1)(J-1)
         p1 = b1 ** alpha
         p2 = b2 ** alpha
         p3 = b3 ** alpha
         psum = third * ( p1 + p2 + p3 )
         fac  = two * amu / ( alpha * aj )
         phyd = akmod * ( aj - one )
         sig1 = fac * ( p1 - psum ) + phyd
         sig2 = fac * ( p2 - psum ) + phyd
         sig3 = fac * ( p3 - psum ) + phyd
C
C     평면 주응력 -> (11,22,12) 회전복원, 후프=33
         s11 = sig1 * cc + sig2 * ss
         s22 = sig1 * ss + sig2 * cc
         s12 = ( sig1 - sig2 ) * cs
         s33 = sig3
C
C     von Mises 응력
         svm = sqrt( half * ( (s11-s22)**2 + (s22-s33)**2
     1                      + (s33-s11)**2 ) + three*s12*s12 )
C
C     등가 로그변형(편차)
         e1 = log( al1 )
         e2 = log( al2 )
         e3 = log( al3 )
         em = third * ( e1 + e2 + e3 )
         eeq = sqrt( two*third * ( (e1-em)**2 + (e2-em)**2
     1                           + (e3-em)**2 ) )
C
C     파단/삭제 판정 (von Mises OR 등가변형)
         delflag = stateOld(k,1)
         if ( totalTime .le. dt ) delflag = one
         if ( svm .ge. sigf .or. eeq .ge. epsf ) delflag = zero
C
C     응력 대입
         stressNew(k,1) = s11
         stressNew(k,2) = s22
         stressNew(k,3) = s33
         if ( nshr .ge. 1 ) stressNew(k,ndir+1) = s12
         if ( delflag .eq. zero ) then
            do i = 1, ndir+nshr
               stressNew(k,i) = zero
            end do
         end if
C
C --- 상태변수 갱신 ----------------------------------------------------
         stateNew(k,1) = delflag
         stateNew(k,2) = svm
         stateNew(k,3) = eeq
         stateNew(k,4) = aj
C
C --- 내부에너지 갱신 --------------------------------------------------
         stpow = zero
         do i = 1, ndir
            stpow = stpow
     1            + half*(stressOld(k,i)+stressNew(k,i))*strainInc(k,i)
         end do
         do i = ndir+1, ndir+nshr
            stpow = stpow
     1            + (stressOld(k,i)+stressNew(k,i))*strainInc(k,i)
         end do
         enerInternNew(k) = enerInternOld(k) + stpow / density(k)
         enerInelasNew(k) = enerInelasOld(k)
C
      end do
C
      return
      end
