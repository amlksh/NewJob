C ======================================================================
C  vumat_skin_reg.f
C
C  Abaqus/Explicit VUMAT : Neo-Hookean 피부 + 파단에너지(charLength) 정규화
C
C  vumat_skin.f 와 동일한 압축성 Neo-Hookean 초탄성이나, 손상 진전을
C  요소 특성길이(charLength)로 정규화하여 파단 에너지가 메쉬 크기에
C  무관하도록(mesh-objective) 만든다. (Hillerborg crack-band 방식)
C
C    손상개시 : 최대 주신축비 lam >= lam_d
C    등가 개구변위 : w = charLength * max(0, lam_hat - lam_d)
C    손상변수 : D = w / uf   (0~1),  D>=1 이면 요소 삭제
C
C  요소가 작아지면(charLength 감소) 같은 D 에 도달하는 데 더 큰 신축비가
C  필요 -> 파단에 소산되는 단위면적당 에너지 G ~ 0.5*sigma0*uf 가 요소
C  크기와 무관하게 유지된다. (uf 는 파단변위[mm], G = 0.5*sigma0*uf)
C
C  재료 상수 (PROPS), CONSTANTS=4
C    1 C10   [MPa]     Neo-Hookean 전단 파라미터
C    2 D1    [1/MPa]   체적 (K = 2/D1)
C    3 lam_d [-]       손상 개시 최대 주신축비
C    4 uf    [mm]      파단 개구변위 (에너지 정규화 파라미터)
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
      dimension bmat(6), sdev(6), eig(3)
C
      c10   = props(1)
      d1    = props(2)
      alamd = props(3)
      uf    = props(4)
      if ( d1 .gt. zero ) then
         akmod = two/d1
      else
         akmod = zero
      end if
C
      do k = 1, nblock
C
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
         bmat(1) = u11*u11 + u12*u12 + u31*u31
         bmat(2) = u12*u12 + u22*u22 + u23*u23
         bmat(3) = u31*u31 + u23*u23 + u33*u33
         bmat(4) = u11*u12 + u12*u22 + u31*u23
         bmat(5) = u12*u31 + u22*u23 + u23*u33
         bmat(6) = u11*u31 + u12*u23 + u31*u33
C
         detu = u11*(u22*u33 - u23*u23)
     1        - u12*(u12*u33 - u23*u31)
     2        + u31*(u12*u23 - u22*u31)
         if ( detu .le. zero ) detu = 1.d-6
         aj    = detu
         ajm23 = aj**(-two*third)
         trb   = bmat(1) + bmat(2) + bmat(3)
C
         fac  = two*c10/aj*ajm23
         phyd = akmod*( aj - one )
         do i = 1, 3
            sdev(i) = fac*( bmat(i) - third*trb ) + phyd
         end do
         do i = 4, 6
            sdev(i) = fac*bmat(i)
         end do
C
C        최대 주신축비
         call princ3( u11, u22, u33, u12, u23, u31, eig )
         alam = eig(1)
         do i = 2, 3
            if ( eig(i) .gt. alam ) alam = eig(i)
         end do
         alamx = stateOld(k,2)
         if ( alam .gt. alamx ) alamx = alam
C
C        파단에너지 정규화 손상
         if ( uf .gt. zero .and. alamx .gt. alamd ) then
            w   = charLength(k)*( alamx - alamd )
            dam = w/uf
            if ( dam .gt. one ) dam = one
         else
            dam = zero
         end if
C
         delflag = stateOld(k,1)
         if ( totalTime .le. dt ) delflag = one
         if ( dam .ge. one ) then
            dam     = one
            delflag = zero
         end if
C
         fd = one - dam
         do i = 1, ndir+nshr
            stressNew(k,i) = fd*sdev(i)
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
