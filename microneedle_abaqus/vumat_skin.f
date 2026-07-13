C ======================================================================
C  vumat_skin.f
C
C  Abaqus/Explicit VUMAT : 마이크로니들 피부 관통 해석용 사용자 재료
C
C  물성 모델
C    - 압축성 Neo-Hookean 초탄성 (연조직/피부의 준-비압축 거동)
C          W = C10 (I1bar - 3) + (1/D1)(J - 1)^2
C    - 최대 주신축비(principal stretch) 기반 손상/파단
C          람다 < lam_d          : 손상 없음  (D = 0)
C          lam_d <= 람다 < lam_f : 선형 손상   (0 < D < 1)
C          람다 >= lam_f         : 완전 파단 -> 요소 삭제
C      손상 D 는 응력을 (1-D) 로 연화시키며, D=1 이 되면 상태변수
C      STATEV(1)=0 을 통해 요소가 삭제되어 니들이 조직을 '절개'하며
C      전진하는 물리 현상을 모사한다.
C
C  재료 상수 (PROPS)
C    PROPS(1) = C10     [MPa]  Neo-Hookean 전단 파라미터 (mu = 2*C10)
C    PROPS(2) = D1      [1/MPa] 체적 파라미터 (K = 2/D1)
C    PROPS(3) = lam_d   [-]    손상 개시 최대 주신축비
C    PROPS(4) = lam_f   [-]    파단(요소 삭제) 최대 주신축비
C
C  상태 변수 (STATEV) : *DEPVAR = 4, DELETE = 1
C    STATEV(1) = 삭제 플래그 (1=유지, 0=삭제)   <-- DELETE 지정 변수
C    STATEV(2) = 이력상 최대 주신축비
C    STATEV(3) = 손상 변수 D  (0~1)
C    STATEV(4) = 상대 체적 J = det(F)
C
C  단위계 (권장, 일관 SI-mm)
C    길이 mm, 힘 N, 응력 MPa, 질량 tonne, 밀도 tonne/mm^3, 시간 s
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
      dimension bmat(6), sdev(6), eig(3)
C
C --- 재료 상수 ----------------------------------------------------------
      c10   = props(1)
      d1    = props(2)
      alamd = props(3)
      alamf = props(4)
      if ( d1 .gt. zero ) then
         akmod = two / d1
      else
         akmod = zero
      end if
C
C --- 적분점(블록) 루프 --------------------------------------------------
      do k = 1, nblock
C
C     좌변 신축텐서 U (대칭) 성분을 6-성분 벡터로 전개.
C     VUMAT 전단성분 저장순서 : (12, 23, 31)
         u11 = stretchNew(k,1)
         u22 = stretchNew(k,2)
         u33 = stretchNew(k,3)
         u12 = zero
         u23 = zero
         u31 = zero
         if ( nshr .ge. 1 ) u12 = stretchNew(k,ndir+1)
         if ( nshr .ge. 2 ) u23 = stretchNew(k,ndir+2)
         if ( nshr .ge. 3 ) u31 = stretchNew(k,ndir+3)
C
C     좌 Cauchy-Green 텐서 B = U * U  (동회전좌표계에서 F=U)
         bmat(1) = u11*u11 + u12*u12 + u31*u31
         bmat(2) = u12*u12 + u22*u22 + u23*u23
         bmat(3) = u31*u31 + u23*u23 + u33*u33
         bmat(4) = u11*u12 + u12*u22 + u31*u23
         bmat(5) = u12*u31 + u22*u23 + u23*u33
         bmat(6) = u11*u31 + u12*u23 + u31*u33
C
C     상대 체적 J = det(U)
         detu = u11*(u22*u33 - u23*u23)
     1        - u12*(u12*u33 - u23*u31)
     2        + u31*(u12*u23 - u22*u31)
         if ( detu .le. zero ) detu = 1.d-6
         aj    = detu
         ajm23 = aj**(-two*third)
C
C     I1bar = J^(-2/3) * tr(B)
         trb    = bmat(1) + bmat(2) + bmat(3)
         ai1bar = ajm23 * trb
C
C     편차 Kirchhoff/Cauchy 응력 (Neo-Hookean)
C        sigma = (2/J)*C10*(Bbar - (1/3) I1bar I) + (2/D1)(J-1) I
         fac  = two * c10 / aj * ajm23
         phyd = akmod * ( aj - one )
         do i = 1, 3
            sdev(i) = fac * ( bmat(i) - third*trb ) + phyd
         end do
         do i = 4, 6
            sdev(i) = fac * bmat(i)
         end do
C
C --- 손상 / 파단 판정 (최대 주신축비) ---------------------------------
         call princ3( u11, u22, u33, u12, u23, u31, eig )
         alam = eig(1)
         do i = 2, 3
            if ( eig(i) .gt. alam ) alam = eig(i)
         end do
C
C     이력상 최대 주신축비
         alamx = stateOld(k,2)
         if ( alam .gt. alamx ) alamx = alam
C
C     손상 변수 D
         if ( alamf .gt. alamd ) then
            if ( alamx .le. alamd ) then
               dam = zero
            else if ( alamx .lt. alamf ) then
               dam = ( alamx - alamd ) / ( alamf - alamd )
            else
               dam = one
            end if
         else
            dam = zero
         end if
C
C     삭제 플래그 (첫 증분에서 초기화)
         delflag = stateOld(k,1)
         if ( totalTime .le. dt ) delflag = one
         if ( dam .ge. one ) then
            dam     = one
            delflag = zero
         end if
C
C     연화된 응력 반영
         fd = one - dam
         do i = 1, ndir+nshr
            stressNew(k,i) = fd * sdev(i)
         end do
C
C     삭제된 요소는 응력 0
         if ( delflag .eq. zero ) then
            do i = 1, ndir+nshr
               stressNew(k,i) = zero
            end do
         end if
C
C --- 상태변수 갱신 ----------------------------------------------------
         stateNew(k,1) = delflag
         stateNew(k,2) = alamx
         stateNew(k,3) = dam
         stateNew(k,4) = aj
C
C --- 내부(변형) 에너지 (단위질량당) 갱신 ------------------------------
         stpow = zero
         do i = 1, ndir
            stpow = stpow
     1            + half*( stressOld(k,i)+stressNew(k,i) )*strainInc(k,i)
         end do
         do i = ndir+1, ndir+nshr
            stpow = stpow
     1            + ( stressOld(k,i)+stressNew(k,i) )*strainInc(k,i)
         end do
         enerInternNew(k) = enerInternOld(k) + stpow / density(k)
         enerInelasNew(k) = enerInelasOld(k)
C
      end do
C
      return
      end
C
C ======================================================================
C  princ3 : 대칭 3x3 텐서의 고유값(주신축비) 해석해
C           성분 순서 (11,22,33,12,23,31)
C ======================================================================
      subroutine princ3( a11, a22, a33, a12, a23, a31, eig )
      include 'vaba_param.inc'
      dimension eig(3)
      parameter ( zero = 0.d0, one = 1.d0, two = 2.d0, three = 3.d0,
     1            half = 0.5d0, third = 1.d0/3.d0, six = 6.d0 )
C
      p1 = a12*a12 + a23*a23 + a31*a31
      if ( p1 .le. 1.d-20 ) then
C        대각(주축) 텐서
         eig(1) = a11
         eig(2) = a22
         eig(3) = a33
         return
      end if
C
      q  = ( a11 + a22 + a33 ) * third
      p2 = (a11-q)**2 + (a22-q)**2 + (a33-q)**2 + two*p1
      p  = sqrt( p2 / six )
C
C     B = (1/p)(A - q I)
      b11 = ( a11 - q ) / p
      b22 = ( a22 - q ) / p
      b33 = ( a33 - q ) / p
      b12 = a12 / p
      b23 = a23 / p
      b31 = a31 / p
C
C     r = det(B)/2
      detb = b11*(b22*b33 - b23*b23)
     1     - b12*(b12*b33 - b23*b31)
     2     + b31*(b12*b23 - b22*b31)
      r = detb * half
      if ( r .gt.  one ) r =  one
      if ( r .lt. -one ) r = -one
C
      phi = acos( r ) * third
      pi  = 3.141592653589793d0
C
      eig(1) = q + two*p*cos( phi )
      eig(3) = q + two*p*cos( phi + two*pi*third )
      eig(2) = three*q - eig(1) - eig(3)
C
      return
      end
