# 마이크로니들 피부 관통 해석 (Abaqus/Explicit + VUMAT)

마이크로니들(microneedle)이 피부에 삽입·관통되는 현상을 유한요소로 모사하는
**Abaqus/Explicit 사용자 재료 서브루틴(VUMAT)** 활용 예제입니다.

피부는 매우 무른 초탄성(hyperelastic) 연조직이며, 니들이 뚫고 들어가려면
조직이 국소적으로 **파단(찢김/절개)** 되어야 합니다. 이 예제는
초탄성 응력 계산 + 손상 기반 **요소 삭제(element deletion)** 를 하나의
VUMAT 안에 구현하여, 니들이 조직을 절개하며 전진하는 과정을 재현합니다.

---

## 1. 구성 파일

| 파일 | 설명 |
|------|------|
| `vumat_skin.f` | 피부 재료 VUMAT (Neo-Hookean 초탄성 + 주신축비 손상/삭제) |
| `vumat_skin_hgo.f` | 이방성 HGO 초탄성 VUMAT (3D, 섬유 2족 + 손상/삭제) |
| `microneedle_penetration.inp` | 2D 축대칭 기본 관통 모델 (니들=해석적 강체) |
| `01_multilayer_skin.inp` | **(a)** 3층 피부(각질층/표피/진피) 관통 모델 |
| `02_hgo_pretension.inp` | **(b)** 3D HGO 이방성 + 사전인장 관통 모델 (생성물) |
| `gen_hgo_model.py` | (b) 3D 입력파일 생성기 |
| `03_needle_buckling.inp` | **(c)** 니들 좌굴 파괴력 검증(`*BUCKLE`) 모델 |
| `postprocess.py` | `.odb`에서 관통력–침투깊이 곡선 추출 |
| `ANALYSIS_PLAN.md` | 문헌 기반 해석 방안 |
| `README.md` | 본 문서 |

> `microneedle_penetration.inp` 는 최소 기본 예제, `01`/`02`/`03` 은
> 참고문헌을 반영해 단계적으로 고도화한 확장 모델입니다(아래 8절).

---

## 2. 물리 모델

### 2.1 초탄성 구성식 (압축성 Neo-Hookean)

변형에너지 밀도
```
W = C10 (Ī1 − 3) + (1/D1)(J − 1)^2
```
- `Ī1 = J^(−2/3) tr(B)` : 편차 첫 번째 불변량, `B = F·Fᵀ`
- `J = det(F)` : 상대 체적
- `μ = 2·C10` (초기 전단계수), `K = 2/D1` (체적계수)

Cauchy 응력
```
σ = (2/J) C10 (B̄ − (1/3) Ī1 I) + (2/D1)(J − 1) I
```

VUMAT 은 **동회전(co-rotational) 좌표계**에서 응력을 돌려주어야 하므로,
회전을 제거한 신축텐서 `U`(=`stretchNew`)로부터 `B = U·U` 를 직접 계산합니다
(등방성 재료에서 타당). 따라서 별도 회전 변환이 필요 없습니다.

### 2.2 손상 및 요소 삭제

각 적분점에서 대칭 신축텐서 `U`의 **최대 주신축비 λ_max** 를 고유값으로 구하고,
이력상 최대값 `λ̂` 로 손상 변수 `D` 를 정의합니다.

```
λ̂ ≤ λ_d              → D = 0            (손상 없음)
λ_d < λ̂ < λ_f        → D = (λ̂ − λ_d)/(λ_f − λ_d)   (선형 연화)
λ̂ ≥ λ_f              → D = 1 → 요소 삭제
```

- 응력은 `(1 − D)` 로 연화됩니다.
- `D = 1` 이 되면 상태변수 `STATEV(1) = 0` 으로 설정되고,
  입력파일의 `*DEPVAR, DELETE=1` 지정에 의해 해당 요소가 삭제됩니다.
- 요소가 삭제되면 새 표면이 노출되고, **전역 접촉(general contact)** 이
  이를 자동 인식하여 니들이 계속 전진할 수 있습니다.

### 2.3 상태 변수 (SDV)

| SDV | 이름 | 의미 |
|-----|------|------|
| 1 | DELFLAG | 삭제 플래그 (1=유지, 0=삭제) — `DELETE` 지정 변수 |
| 2 | LAMMAX | 이력상 최대 주신축비 λ̂ |
| 3 | DAMAGE | 손상 변수 D (0~1) |
| 4 | JVOL | 상대 체적 J = det(F) |

---

## 3. 재료 상수 (`*USER MATERIAL, CONSTANTS=4`)

| PROPS | 기호 | 예시값 | 단위 | 의미 |
|-------|------|--------|------|------|
| 1 | C10 | 0.02 | MPa | Neo-Hookean 전단 파라미터 (μ = 2·C10 = 0.04 MPa) |
| 2 | D1 | 1.0 | 1/MPa | 체적 파라미터 (K = 2/D1 = 2 MPa, 준-비압축) |
| 3 | λ_d | 1.6 | – | 손상 개시 최대 주신축비 |
| 4 | λ_f | 2.2 | – | 파단(요소 삭제) 최대 주신축비 |

> 값은 예시입니다. 실제 피부는 층(각질층/표피/진피)마다 물성이 크게 다르므로,
> 문헌·실험 데이터로 층별 물성을 나누어 지정하는 것을 권장합니다
> (아래 5절 확장 참조).

---

## 4. 모델 개요 (`microneedle_penetration.inp`)

- **좌표계** : 2D 축대칭(CAX4R), r = X(반경), z = Y(깊이)
- **피부 블록** : r ∈ [0, 2.0] mm, z ∈ [0, 1.5] mm, 20×15 = 300 요소
- **니들** : 해석적 강체(analytical rigid), 원뿔형 첨두
  (첨두 반경 0.02 mm, 샤프트 반경 0.15 mm), 참조점 `NREF`로 하강 제어
- **경계조건** : 하면 z-고정, 대칭축·우측면 r-고정
- **하중** : 니들을 SMOOTH STEP 진폭으로 1.2 mm 하강 (준정적 외연해석)
- **접촉** : 전역 접촉 + 마찰계수 0.1 (요소 침식에 대응)
- **단위계** : mm, N, MPa, tonne, s (밀도 1.1e-9 tonne/mm³ = 1100 kg/m³)

---

## 5. 실행 방법

### 5.1 해석 실행
```bash
abaqus job=microneedle input=microneedle_penetration.inp \
       user=vumat_skin.f double=both cpus=4
```
- `double=both` : VUMAT 의 배정밀도 연산 안정성 확보(권장).
- Fortran 컴파일러(Intel oneAPI 등)와 Abaqus 링크 환경이 필요합니다.

### 5.2 후처리
```bash
abaqus python postprocess.py microneedle.odb
```
- `force_displacement.csv` : 침투깊이 vs 관통력
- (matplotlib 있으면) `force_displacement.png`
- 관통 개시(peak force) 지점을 자동 보고합니다.

관통력–깊이 곡선에서 첫 번째 급락(peak 이후 하강)이 곧 조직이 찢어지는
**관통 개시(puncture)** 순간에 해당합니다.

---

## 6. 확장 아이디어

1. **다층 피부** : 각질층(딱딱)·표피·진피(무름)를 서로 다른 `*MATERIAL`/
   `*SOLID SECTION` 으로 나누고 층별 (C10, D1, λ_d, λ_f) 지정.
2. **점탄성/율의존성** : 삽입 속도 효과가 중요하면 Prony 급수 또는 율의존
   손상항을 VUMAT 에 추가.
3. **3D 모델** : 사각뿔/육각뿔 니들이나 니들 어레이는 3D(C3D8R)로 확장
   (VUMAT 은 nshr=3 도 처리하도록 일반화되어 있음).
4. **손상 정규화** : 메시 의존성을 줄이려면 특성길이(`charLength`) 기반
   파단에너지(energy-based) 손상으로 개선.
5. **질량 스케일링 조정** : 연조직은 무르므로 안정 증분이 작습니다.
   `*FIXED MASS SCALING` 의 목표 dt 를 조정해 준정적성(ALLKE ≪ ALLIE)을
   확인하세요.

---

## 7. 검증 체크리스트

- [ ] 무손상 단축 인장에서 응력이 Neo-Hookean 해석해와 일치하는가
      (λ_d 를 크게 두고 확인).
- [ ] 운동에너지(ALLKE)가 내부에너지(ALLIE)의 5~10% 이내인가 (준정적성).
- [ ] 요소 삭제 후에도 관통 경로에서 관통이 매끄럽게 진행되는가.
- [ ] 관통력–깊이 곡선의 peak 값이 실험 범위와 부합하는가.

---

## 8. 확장 모델 (a → b → c)

문헌(특히 Shu et al., *Acta Biomater.* 2021; *Int. J. Pharm.* 2025)을
반영한 세 확장 모델입니다. 상세 근거는 `ANALYSIS_PLAN.md` 참조.

### (a) 3층 피부 모델 — `01_multilayer_skin.inp`
- 2D 축대칭. **각질층(딱딱·저파단) / 표피 / 진피(무름·고파단)** 를
  각각 별도 `*MATERIAL`(VUMAT)·`*SOLID SECTION` 으로 분리.
- 각질층은 얇고(0.02 mm) 파단 신축비가 낮아(λ_f=1.5) **관통 개시를 지배**
  하며, 진피는 크게 변형해도 잘 안 찢어지도록(λ_f=2.5) 설정.
- 층별 물성:

  | 층 | C10[MPa] | D1[1/MPa] | λ_d | λ_f |
  |----|---------|-----------|-----|-----|
  | 각질층 | 1.00 | 0.02 | 1.2 | 1.5 |
  | 표피 | 0.10 | 0.10 | 1.4 | 1.9 |
  | 진피 | 0.02 | 1.00 | 1.6 | 2.5 |

```bash
abaqus job=ml01 input=01_multilayer_skin.inp user=vumat_skin.f double=both cpus=4
abaqus python postprocess.py ml01.odb
```

### (b) HGO 이방성 + 사전인장 — `02_hgo_pretension.inp` (+`vumat_skin_hgo.f`)
- **3D 1/4 모델**. 섬유가 x축 대칭(±γ)이므로 x=0, y=0 이 대칭면이 되어
  1/4 만 모델링(니들축=두 대칭면 교선).
- 진피를 **HGO 이방성 초탄성**(콜라겐 섬유 2족, γ=30°, 분산 κ=0.2)으로.
- **2-스텝 해석**: ① 사전인장(외측면 10% 등이축 인장) → ② 니들 삽입.
  → 문헌 결과처럼 사전인장이 관통력·관통효율을 낮추는 효과 확인 가능.
- 입력파일은 생성기로 만듭니다(격자·절점집합 자동 생성):

```bash
python gen_hgo_model.py                    # -> 02_hgo_pretension.inp
abaqus job=hgo02 input=02_hgo_pretension.inp user=vumat_skin_hgo.f double=both cpus=4
abaqus python postprocess.py hgo02.odb     # INSERTION 스텝 자동 인식
```

> HGO VUMAT 상수(CONSTANTS=8): `C10, D1, k1, k2, kappa, gamma[deg],
> lam_d, lam_f`. 섬유는 인장에서만 강성 기여(`<E>=max(E,0)`).

### (c) 니들 좌굴 파괴력 검증 — `03_needle_buckling.inp`
- *Int. J. Pharm.* 2025 의 판정: **삽입 성공 ⇔ 삽입력 < 니들 좌굴 파괴력**.
- 용해성 폴리머 니들(E=3 GPa)을 테이퍼 원형 보(B31)로 모델링,
  기저 완전고정·첨두 축방향 단위하중으로 **`*BUCKLE` 고유값** 산출.
- 고유값 λ = 임계 좌굴하중 `P_cr`(N) (단위하중 1 N 기준).

```bash
abaqus job=buck03 input=03_needle_buckling.inp
# .dat 파일의 "EIGENVALUE" 표에서 최저 모드 = P_cr [N]
```

**판정 절차**
1. (a) 또는 (b) 해석에서 관통력 곡선의 peak = `F_ins` 추출.
2. (c) 에서 최저 좌굴모드 `P_cr` 추출.
3. `F_ins < P_cr` 이면 니들이 좌굴 전에 관통 → **삽입 성공**,
   `F_ins ≥ P_cr` 이면 니들이 먼저 좌굴 → **삽입 실패**(형상/재료 재설계 필요).

> 참고(개략 검산): 고정-자유 기둥의 Euler 임계하중
> `P_cr ≈ π²EI/(4L²)`. 대표반경 r≈0.085 mm, L=0.8 mm, E=3000 MPa 로
> 대입하면 `P_cr` 은 대략 0.5 N 수준(테이퍼·고차모드는 FE 고유값이 정확).
> 니들이 매우 가늘거나 길면 `P_cr` 이 급감하여 좌굴이 관통을 제약합니다.

### 확장 모델 실행 시 주의
- (a),(b) 는 Explicit + VUMAT → `user=...f double=both` 필요.
- (c) 는 Abaqus/Standard 선형섭동 → 서브루틴 불필요.
- 세 모델 모두 물성·치수는 **예시값**이며 실제 데이터로 보정 필요.
- 연조직·얇은 각질층으로 안정증분이 작으므로 질량 스케일링 사용 시
  반드시 `ALLKE ≪ ALLIE` (준정적성)를 확인하세요.
