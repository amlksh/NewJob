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
| `vumat_skin_reg.f` | 파단에너지(charLength) 정규화 VUMAT (메쉬 객관적 손상) |
| `microneedle_penetration.inp` | 2D 축대칭 기본 관통 모델 (니들=해석적 강체) |
| `01_multilayer_skin.inp` | **(a)** 3층 피부(각질층/표피/진피) 관통 모델 |
| `02_hgo_pretension.inp` | **(b)** 3D HGO 이방성 + 사전인장 관통 모델 (생성물) |
| `gen_hgo_model.py` | (b) 3D 입력파일 생성기 |
| `03_needle_buckling.inp` | **(c)** 니들 좌굴 파괴력 검증(`*BUCKLE`) 모델 |
| `04_refined_path.inp` | **경로 세밀화** 3층 관통 모델 (생성물) |
| `gen_refined_axi.py` | 경로 바이어스 세밀화 입력파일 생성기 (수렴성 스터디에서 재사용) |
| `06_ale_indentation.inp` | **ALE 적응메쉬** 깊은 압입(왜곡 완화) 예시 |
| `07_cohesive_cut.inp` | **Cohesive 절개** 대안 모델 (평면변형, 생성물) |
| `gen_cohesive.py` | (07) Cohesive 모델 생성기 |
| `convergence_study.py` | **메쉬 수렴성 스터디** 도구(생성/실행스크립트/집계) |
| `postprocess.py` | `.odb`에서 관통력–침투깊이 곡선 추출 |
| `ANALYSIS_PLAN.md` | 문헌 기반 해석 방안 |
| `BUILD_AND_RUN.md` | **서브루틴 컴파일·실행 가이드** (Windows 로컬 / Linux 클러스터) |
| `README.md` | 본 문서 |

> **실행 환경**: VUMAT은 실행 시 Fortran 컴파일러(Intel oneAPI `ifort`/`ifx`)로
> 컴파일됩니다. Windows 로컬(Abaqus 2025 + oneAPI 2024) 및 Linux 클러스터
> (cae20~cae23)에서의 링크 확인·빌드·실행 절차는 **`BUILD_AND_RUN.md`** 참조.

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

### 니들 경로 메쉬 세밀화 — `04_refined_path.inp` (+`gen_refined_axi.py`)
요소 삭제 방식의 **메쉬 의존성·지그재그 경로**를 줄이는 실효적 개선책은
리메쉬가 아니라 **경로 부근 메쉬 세밀화**입니다(질문 답변 참조). 본 모델은
(a) 3층 피부에 바이어스 격자를 적용합니다.

- **반경방향**: 축(r=0) 근처 세밀(Δr≈0.03) → 외곽으로 기하급수 성김(≈0.35).
  니들 관통이 일어나는 r<0.3 mm 영역을 집중 세밀화.
- **깊이방향**: 상면(각질층) 세밀(Δz≈0.005) → 진피 하부로 성김(≈0.29).
  얇은 각질층과 관통 개시부를 정밀 포착.
- 격자·절점집합은 생성기가 좌표배열 텐서곱으로 정확히 생성(418 요소).

```bash
python gen_refined_axi.py                  # -> 04_refined_path.inp
abaqus job=ref04 input=04_refined_path.inp user=vumat_skin.f double=both cpus=4
abaqus python postprocess.py ref04.odb
```

> 세밀화 정도(`DR_FINE`, `DZ_SC`, 성장비 `R_GROW`/`Z_GROW`)는 생성기 상단
> 상수로 조절합니다. 세밀할수록 경로가 매끄럽고 peak force가 수렴하지만
> 안정증분이 작아지니 질량 스케일링과 `ALLKE≪ALLIE` 를 함께 확인하세요.
> (메쉬 의존성을 더 줄이려면 `charLength` 기반 파단에너지 정규화를 병행.)

### 확장 모델 실행 시 주의
- (a),(b) 는 Explicit + VUMAT → `user=...f double=both` 필요.
- (c) 는 Abaqus/Standard 선형섭동 → 서브루틴 불필요.
- 세 모델 모두 물성·치수는 **예시값**이며 실제 데이터로 보정 필요.
- 연조직·얇은 각질층으로 안정증분이 작으므로 질량 스케일링 사용 시
  반드시 `ALLKE ≪ ALLIE` (준정적성)를 확인하세요.

---

## 9. 고급 기능 (파단에너지 정규화 · 수렴성 · ALE · Cohesive)

### 9.1 파단에너지 정규화 VUMAT — `vumat_skin_reg.f`
요소 삭제 손상의 **메쉬 크기 의존성**을 없애는 정공법입니다. 손상 진전을
요소 특성길이(`charLength`)로 정규화(Hillerborg crack-band)하여, 파단에
소산되는 **단위면적당 에너지가 메쉬와 무관**하도록 만듭니다.

- PROPS(=4): `C10, D1, lam_d, uf` — 4번째가 파단신축비 대신 **파단
  개구변위 `uf`[mm]**(에너지 파라미터, `G ≈ 0.5·σ0·uf`).
- 등가 개구변위 `w = charLength·max(0, λ̂−lam_d)`, 손상 `D = w/uf`.
  요소가 작아지면 같은 D 도달에 더 큰 λ 가 필요 → 에너지 일정.

```bash
# 04 경로세밀 격자를 에너지정규화 재료로 생성해 실행하려면
python -c "import gen_refined_axi as g; g.generate('04r_reg.inp', reg=True)"
abaqus job=r04reg input=04r_reg.inp user=vumat_skin_reg.f double=both cpus=4
```

### 9.2 메쉬 수렴성 스터디 — `convergence_study.py`
여러 해상도의 입력파일을 자동 생성하고, 실행 후 산출된 `*_fd.csv` 들을
모아 **peak 관통력 vs 메쉬 크기** 수렴 곡선을 만듭니다.

```bash
# 1) 생성 (변형률기반 / 파단에너지정규화)
python convergence_study.py gen            # 또는  gen --reg
#    -> conv_r0.060.inp ... conv_r0.015.inp, run_convergence.sh/.bat
# 2) 실행 (Abaqus 환경)
bash run_convergence.sh                     # Windows: run_convergence.bat
# 3) 집계/그래프
python convergence_study.py agg
#    -> convergence.csv, convergence.png, "2 finest 상대변화 %" 출력
```
정규화 재료(`--reg`)와 변형률기반을 각각 돌려 비교하면, **정규화 쪽이
메쉬 세밀화에 따라 peak force 가 더 빨리 수렴**함을 확인할 수 있습니다.

### 9.3 ALE 적응메쉬 — `06_ale_indentation.inp`
`*ADAPTIVE MESH` 는 **위상을 유지한 채 절점만 재배치**해 압입 단계의
요소 왜곡을 억제합니다(절개는 못 만듦 — 앞선 리메쉬 답변 참조). 따라서
본 예시는 **요소 삭제 없이 깊은 압입(0.6 mm)** 만 모사하여 ALE 효과를
보입니다. 벌크는 **내장 Neo-Hookean → 서브루틴 불필요**.

```bash
abaqus job=ale06 input=06_ale_indentation.inp double=both cpus=4
```
> 실제 관통(절개)은 요소 삭제(01/04) 또는 cohesive(07) 로 처리하고,
> ALE 는 관통 전 왜곡으로 해석이 중단될 때 벌크 안정화 보조로 병용합니다.

### 9.4 Cohesive 절개 대안 — `07_cohesive_cut.inp` (+`gen_cohesive.py`)
요소 삭제 대신 **사전 정의된 균열면(중앙 x=0)에 두께-0 cohesive 층**을
두고, 강체 쐐기가 내려오며 견인-분리(traction–separation + 에너지손상)로
조직을 가릅니다. 벌크는 내장 Neo-Hookean → **서브루틴 불필요**.

- 균열 경로가 정해져 **지그재그·질량손실이 없고** 파단에너지 `Gc` 를
  물리량으로 직접 입력(`*DAMAGE EVOLUTION, TYPE=ENERGY`).
- 평면변형(CPE4R 벌크 + COH2D4 cohesive), 좌/우 블록이 중앙 cohesive 로
  결합되었다가 손상 시 분리·삭제되어 쐐기가 진입.
- 한계: 균열 경로를 미리 알아야 함(직선 삽입에 적합).

```bash
python gen_cohesive.py                       # -> 07_cohesive_cut.inp
abaqus job=coh07 input=07_cohesive_cut.inp double=both cpus=4
```

### 절개(분리) 방법 선택 가이드
| 방법 | 파일 | 서브루틴 | 경로 자유도 | 특징 |
|------|------|:--:|:--:|------|
| 요소 삭제 | 01/04 | 필요(VUMAT) | 자유 | 표준·강건, 메쉬 의존·질량손실 |
| 요소 삭제+에너지정규화 | `vumat_skin_reg.f` | 필요 | 자유 | 메쉬 객관적 손상 |
| ALE(왜곡완화, 절개 X) | 06 | 불필요 | — | 압입 안정화 보조 |
| Cohesive | 07 | 불필요 | **사전정의** | 경로 정확·에너지 물리량, 경로 고정 |
