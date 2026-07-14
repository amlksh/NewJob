C ======================================================================
C  vumat_skin_hgo.f
C
C  Abaqus/Explicit VUMAT : 이방성(HGO) 피부 재료 (3D)
C
C  Holzapfel-Gasser-Ogden (HGO) 초탄성 + 손상/요소 삭제.
C  진피의 콜라겐 섬유(2족, 평균방향 x축 대칭 +-gamma, x-y 평면)를 모사.
C
C  변형에너지
C    W = C10 (I1bar - 3)
C      + sum_i (k1/2k2)[ exp(k2 <E_i>^2) - 1 ]        (i=1,2)
C      + (1/D1)(J - 1)^2
C    E_i = kappa (I1bar - 3) + (1 - 3 kappa)(I4bar_i - 1)
C    <x> = max(x, 0)   (섬유는 인장에서만 강성 기여)
C
C  응력 (Cauchy, 동회전좌표계, F=U 대칭)
C    sigma = (2/J)[ psi1 dev(bbar) + sum_i psi4_i dev(bbar4_i) ]
C          + (2/D1)(J-1) I
C    psi1   = C10 + sum_i kappa * k1 E_i exp(k2 E_i^2)
C    psi4_i = (1-3 kappa) k1 E_i exp(k2 E_i^2)
C    bbar   = J^(-2/3) U*U ,  bbar4_i = J^(-2/3) (U a0_i)(x)(U a0_i)
C
C  재료 상수 (PROPS), CONSTANTS=8
C    1 C10   [MPa]      기질 전단 파라미터
C    2 D1    [1/MPa]    체적 (K = 2/D1)
C    3 k1    [MPa]      섬유 강성
C    4 k2    [-]        섬유 지수 파라미터
C    5 kappa [-]        섬유 분산도 (0=완전정렬 ~ 1/3=등방)
C    6 gamma [deg]      평균 섬유각 (x축 기준, x-y 평면)
C    7 lam_d [-]        손상 개시 최대 주신축비
C    8 lam_f [-]        파단(삭제) 최대 주신축비
C
C  상태변수 STATEV (*DEPVAR=4, DELETE=1)
C    1 DELFLAG, 2 LAMMAX, 3 DAMAGE, 4 JVOL
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
C
      parameter ( zero=0.d0, one=1.d0, two=2.d0, three=3.d0,
     1            half=0.5d0, third=1.d0/3.d0 )
C
      dimension bm(6), bd(6), sig(6), eig(3), a0(3,2), af(3,2), b4(6,2)
C
      c10   = props(1)
      d1    = props(2)
      ak1   = props(3)
      ak2   = props(4)
      akap  = props(5)
      gamma = props(6) * (3.141592653589793d0/180.d0)
      alamd = props(7)
      alamf = props(8)
      if ( d1 .gt. zero ) then
         akmod = two/d1
      else
         akmod = zero
      end if
C
C     기준배치 섬유방향 (x-y 평면, x축 대칭 +-gamma)
      a0(1,1) = cos(gamma)
      a0(2,1) = sin(gamma)
      a0(3,1) = zero
      a0(1,2) = cos(gamma)
      a0(2,2) = -sin(gamma)
      a0(3,2) = zero
C
      do k = 1, nblock
C
C        신축텐서 U (대칭, VUMAT 전단순서 12,23,31)
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
C        B = U*U  (= C, F=U 이므로)
         bm(1) = u11*u11 + u12*u12 + u31*u31
         bm(2) = u12*u12 + u22*u22 + u23*u23
         bm(3) = u31*u31 + u23*u23 + u33*u33
         bm(4) = u11*u12 + u12*u22 + u31*u23
         bm(5) = u12*u31 + u22*u23 + u23*u33
         bm(6) = u11*u31 + u12*u23 + u31*u33
C
         detu = u11*(u22*u33 - u23*u23)
     1        - u12*(u12*u33 - u23*u31)
     2        + u31*(u12*u23 - u22*u31)
         if ( detu .le. zero ) detu = 1.d-6
         aj    = detu
         ajm23 = aj**(-two*third)
C
         trb    = bm(1) + bm(2) + bm(3)
         ai1bar = ajm23 * trb
C
C        섬유별 현재방향 af = U a0, I4bar_i = J^(-2/3) |af|^2
         do m = 1, 2
            af(1,m) = u11*a0(1,m) + u12*a0(2,m) + u31*a0(3,m)
            af(2,m) = u12*a0(1,m) + u22*a0(2,m) + u23*a0(3,m)
            af(3,m) = u31*a0(1,m) + u23*a0(2,m) + u33*a0(3,m)
C           구조텐서 af (x) af  (성분순 11,22,33,12,23,31)
            b4(1,m) = af(1,m)*af(1,m)
            b4(2,m) = af(2,m)*af(2,m)
            b4(3,m) = af(3,m)*af(3,m)
            b4(4,m) = af(1,m)*af(2,m)
            b4(5,m) = af(2,m)*af(3,m)
            b4(6,m) = af(3,m)*af(1,m)
         end do
C
C        psi1(기질+섬유의 I1 기여), psi4_i
         psi1 = c10
         do m = 1, 2
            ai4b = ajm23*( af(1,m)*af(1,m)+af(2,m)*af(2,m)
     1                    +af(3,m)*af(3,m) )
            ee   = akap*(ai1bar-three) + (one-three*akap)*(ai4b-one)
            if ( ee .gt. zero ) then
               fexp = ak1*ee*exp(ak2*ee*ee)
               psi1 = psi1 + akap*fexp
               psi4 = (one-three*akap)*fexp
            else
               psi4 = zero
            end if
C           dev(bbar4_i) 를 응력에 누적
            tr4 = ajm23*( b4(1,m)+b4(2,m)+b4(3,m) )
            fac4 = two/aj*psi4*ajm23
            do i = 1, 3
               bd(i) = fac4*( b4(i,m) - third*(b4(1,m)+b4(2,m)+b4(3,m)) )
            end do
            do i = 4, 6
               bd(i) = fac4*b4(i,m)
            end do
            if ( m .eq. 1 ) then
               do i = 1, 6
                  sig(i) = bd(i)
               end do
            else
               do i = 1, 6
                  sig(i) = sig(i) + bd(i)
               end do
            end if
         end do
C
C        기질(+I1 섬유기여) dev(bbar) 항 + 체적항
         fac1 = two/aj*psi1*ajm23
         phyd = akmod*( aj - one )
         do i = 1, 3
            sig(i) = sig(i) + fac1*( bm(i) - third*trb ) + phyd
         end do
         do i = 4, 6
            sig(i) = sig(i) + fac1*bm(i)
         end do
C
C        손상 (최대 주신축비)
         call princ3( u11, u22, u33, u12, u23, u31, eig )
         alam = eig(1)
         do i = 2, 3
            if ( eig(i) .gt. alam ) alam = eig(i)
         end do
         alamx = stateOld(k,2)
         if ( alam .gt. alamx ) alamx = alam
         if ( alamf .gt. alamd ) then
            if ( alamx .le. alamd ) then
               dam = zero
            else if ( alamx .lt. alamf ) then
               dam = ( alamx - alamd )/( alamf - alamd )
            else
               dam = one
            end if
         else
            dam = zero
         end if
         delflag = stateOld(k,1)
         if ( totalTime .le. dt ) delflag = one
         if ( dam .ge. one ) then
            dam     = one
            delflag = zero
         end if
C
         fd = one - dam
         do i = 1, ndir+nshr
            stressNew(k,i) = fd*sig(i)
         end do
         if ( delflag .eq. zero ) then
            do i = 1, ndir+nshr
               stressNew(k,i) = zero
            end do
         end if
C
         stateNew(k,1) = delflag
         stateNew(k,2) = alamx
         stateNew(k,3) = dam
         stateNew(k,4) = aj
C
C        내부에너지
         stpow = zero
         do i = 1, ndir
            stpow = stpow
     1        + half*(stressOld(k,i)+stressNew(k,i))*strainInc(k,i)
         end do
         do i = ndir+1, ndir+nshr
            stpow = stpow
     1        + (stressOld(k,i)+stressNew(k,i))*strainInc(k,i)
         end do
         enerInternNew(k) = enerInternOld(k) + stpow/density(k)
         enerInelasNew(k) = enerInelasOld(k)
C
      end do
C
      return
      end
C
C ======================================================================
C  princ3 : 대칭 3x3 (11,22,33,12,23,31) 고유값
C ======================================================================
      subroutine princ3( a11, a22, a33, a12, a23, a31, eig )
      include 'vaba_param.inc'
      dimension eig(3)
      parameter ( one=1.d0, two=2.d0, three=3.d0, half=0.5d0,
     1            third=1.d0/3.d0, six=6.d0 )
      p1 = a12*a12 + a23*a23 + a31*a31
      if ( p1 .le. 1.d-20 ) then
         eig(1) = a11
         eig(2) = a22
         eig(3) = a33
         return
      end if
      q  = ( a11 + a22 + a33 )*third
      p2 = (a11-q)**2 + (a22-q)**2 + (a33-q)**2 + two*p1
      p  = sqrt( p2/six )
      b11 = (a11-q)/p
      b22 = (a22-q)/p
      b33 = (a33-q)/p
      b12 = a12/p
      b23 = a23/p
      b31 = a31/p
      detb = b11*(b22*b33-b23*b23)
     1     - b12*(b12*b33-b23*b31)
     2     + b31*(b12*b23-b22*b31)
      r = detb*half
      if ( r .gt.  one ) r =  one
      if ( r .lt. -one ) r = -one
      phi = acos(r)*third
      pi  = 3.141592653589793d0
      eig(1) = q + two*p*cos(phi)
      eig(3) = q + two*p*cos(phi + two*pi*third)
      eig(2) = three*q - eig(1) - eig(3)
      return
      end
