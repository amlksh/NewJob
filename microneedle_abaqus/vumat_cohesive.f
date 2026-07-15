C ======================================================================
C  vumat_cohesive.f
C
C  Abaqus/Explicit VUMAT : 이중선형(bilinear) 혼합모드 CZM
C  cohesive 요소(COHAX4 / COH2D4 / COH3D8)용 사용자 견인-분리 재료.
C
C  [작업 C] 전문가 피드백 4번 반영: Abaqus 내장 cohesive(작업 B) 를
C  대체하는 "사용자 정의 CZM". 견인-분리 + 혼합모드 I/II + 손상이력.
C
C  물성 모델 (bilinear traction-separation)
C    - 탄성:  t = K * delta        (delta = nominal_strain * T0)
C    - 손상개시: 유효분리 delta_m >= delta0 = t0/K  에서 시작
C    - 선형연화: delta0 -> delta_f = 2*Gc/t0  에서 완전분리(d=1)
C    - 손상 d 는 (1-d) 로 견인을 연화. 압축(delta_n<0)은 감쇠 없이
C      full penalty 로 상호침투(interpenetration)를 막음.
C    - 유효분리(혼합모드):  delta_m = sqrt(<delta_n>^2 + delta_s^2)
C      (<>=Macaulay: 열림만, 전단 delta_s = sqrt(ds1^2+ds2^2))
C    - 이력 delta_max 로 비가역성(unloading 시 재손상 없음) 보장.
C
C  성분 규약 (cohesive VUMAT)
C    인덱스 1 = 법선(normal, 두께방향),  2.. = 전단(shear).
C    COHAX4/COH2D4 -> 2성분(법선+전단1),  COH3D8 -> 3성분(법선+전단2).
C    (내장 *ELASTIC,TYPE=TRACTION 의 Enn,Ess,Ett 순서와 동일)
C
C  재료 상수 (PROPS), *USER MATERIAL, CONSTANTS=5
C    PROPS(1) = K     penalty stiffness  [traction/sep] (예: MPa/um)
C    PROPS(2) = t0    강도(strength)      [MPa]
C    PROPS(3) = Gc    파단에너지          [MPa*um] (=견인*분리)
C    PROPS(4) = T0    구성두께(THICKNESS=SPECIFIED 와 일치) [um]
C    PROPS(5) = beta  전단/법선 강도비(예약; 기본 1)
C
C  상태 변수 (STATEV), *DEPVAR = 7, DELETE = 6
C    STATEV(1) = 누적 법선 공칭변형(nominal strain)  eps_n
C    STATEV(2) = 누적 전단1 공칭변형  eps_s1
C    STATEV(3) = 누적 전단2 공칭변형  eps_s2
C    STATEV(4) = 이력 최대 유효분리 delta_max
C    STATEV(5) = 손상 변수 d (0~1)
C    STATEV(6) = 삭제 플래그(1=유지,0=삭제)   <-- DELETE 지정
C    STATEV(7) = 현재 유효분리 delta_m (출력용)
C
C  단위계는 사용하는 모델과 일관되게(본 예제: um, uN, MPa, s).
C  실행:  abaqus job=.. input=13_cohesive_axi_vumat.inp
C         user=vumat_cohesive.f double=both cpus=4 interactive
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
      parameter ( zero = 0.d0, one = 1.d0, two = 2.d0, half = 0.5d0 )
C
C --- 재료 상수 ----------------------------------------------------------
      ak   = props(1)
      t0   = props(2)
      gc   = props(3)
      th0  = props(4)
      beta = props(5)
      if ( beta .le. zero ) beta = one
      if ( th0  .le. zero ) th0  = one
      if ( ak   .le. zero ) ak   = one
C
      ntot = ndir + nshr
C
C --- 순수모드 기준 개시/파단 분리 --------------------------------------
      d0 = t0 / ak                       ! 손상개시 분리
      df = two * gc / t0                 ! 완전분리(연화 끝)
      if ( df .le. d0 ) df = d0 * 1.0001d0
C
C --- 적분점(블록) 루프 --------------------------------------------------
      do k = 1, nblock
C
C     공칭변형 누적 (VUMAT 은 증분만 제공)
         en  = stateOld(k,1) + strainInc(k,1)
         es1 = zero
         es2 = zero
         if ( ntot .ge. 2 ) es1 = stateOld(k,2) + strainInc(k,2)
         if ( ntot .ge. 3 ) es2 = stateOld(k,3) + strainInc(k,3)
C
C     분리량 (separation = nominal strain * 구성두께)
         dn  = en  * th0
         ds1 = es1 * th0
         ds2 = es2 * th0
         dnp = dn
         if ( dnp .lt. zero ) dnp = zero          ! 열림만(Macaulay)
         dsh = sqrt( ds1*ds1 + ds2*ds2 )
         dm  = sqrt( dnp*dnp + dsh*dsh )           ! 유효분리
C
C     이력 최대 유효분리(비가역)
         dmax = stateOld(k,4)
         if ( totalTime .le. dt ) dmax = zero      ! 첫 증분 초기화
         if ( dm .gt. dmax ) dmax = dm
C
C     이중선형 손상변수
         if ( dmax .le. d0 ) then
            dam = zero
         else if ( dmax .ge. df ) then
            dam = one
         else
            dam = df * ( dmax - d0 ) / ( dmax * ( df - d0 ) )
         end if
         if ( dam .lt. zero ) dam = zero
         if ( dam .gt. one  ) dam = one
         fd = one - dam
C
C     견인(nominal traction)
         if ( dn .ge. zero ) then
            tn = fd * ak * dn
         else
            tn = ak * dn                           ! 압축: full penalty
         end if
         ts1 = fd * ak * ds1
         ts2 = fd * ak * ds2
C
C     응력(=견인) 성분 대입 (1=법선, 2..=전단)
         stressNew(k,1) = tn
         if ( ntot .ge. 2 ) stressNew(k,2) = ts1
         if ( ntot .ge. 3 ) stressNew(k,3) = ts2
C
C     삭제 플래그(완전분리 시 요소 제거)
         del = one
         if ( dam .ge. one ) del = zero
C
C --- 상태변수 갱신 ----------------------------------------------------
         stateNew(k,1) = en
         stateNew(k,2) = es1
         stateNew(k,3) = es2
         stateNew(k,4) = dmax
         stateNew(k,5) = dam
         stateNew(k,6) = del
         stateNew(k,7) = dm
C
C --- 내부에너지(단위질량당) : 견인 * 변형증분 -------------------------
         stpow = zero
         do i = 1, ntot
            stpow = stpow
     1            + half*(stressOld(k,i)+stressNew(k,i))*strainInc(k,i)
         end do
         enerInternNew(k) = enerInternOld(k) + stpow / density(k)
         enerInelasNew(k) = enerInelasOld(k)
C
      end do
C
      return
      end
