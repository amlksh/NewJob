# 서브루틴 컴파일 · 실행 가이드 (Windows 로컬 / Linux 클러스터)

이 예제의 VUMAT(`vumat_skin.f`, `vumat_skin_hgo.f`)은 **Abaqus/Explicit
사용자 서브루틴**이므로, Abaqus가 실행 시점에 Fortran 컴파일러로 컴파일·
링크합니다. 따라서 (1) 호환 컴파일러 설치, (2) Abaqus–컴파일러 링크 확인,
(3) `user=` 로 잡 실행의 3단계가 필요합니다.

> 아래 경로/버전은 사용자가 제공한 로컬 환경(Windows,
> `DESKTOP-5VO32D7`)을 기준으로 정리했습니다. **저장소에는 머신 종속
> 절대경로를 커밋하지 않습니다** — 각자 환경에 맞게 확인해 사용하세요.

---

## 0. 먼저 링크 상태 확인 (가장 중요)

Abaqus에 어떤 컴파일러가 연결됐는지 실제 값을 출력합니다.

```bat
REM Windows
abaqus info=system
```
```bash
# Linux 클러스터
abaqus info=system        # 필요 시 모듈 로드 후
```
출력의 **Fortran Compiler / C++ Compiler 경로·버전**이 실제 링크 값입니다.
이어서 아래로 "컴파일러가 실제로 동작하는지"까지 검증하세요.

```bat
abaqus verify -user_explicit    REM VUMAT/VEXTERNALDB 등 Explicit 유저루틴 링크 검증
abaqus verify -user_std         REM UMAT 등 Standard 유저루틴 링크 검증
```
`PASS` 가 나오면 우리 VUMAT도 동일 경로로 컴파일됩니다.

---

## 1. Windows 로컬 환경 (제공된 설정 요약)

| 항목 | 값(로컬 기준) |
|------|--------------|
| Abaqus | 2025, `ABA_HOME = C:\SIMULIA\EstProducts\2025\win_b64` |
| 실행 명령 | `abaqus` |
| Fortran | Intel oneAPI 2024 `ifort` (`IFORT_COMPILER24 = C:\Program Files (x86)\Intel\oneAPI\compiler\2024.0\windows\`) |
| `ifort.exe` | `...\2024.0\windows\bin\intel64\ifort.exe` |
| C++ | Visual Studio `cl` (`compile_cpp`) |

Abaqus 환경파일의 관련 항목(참고, 편집 불필요한 경우가 많음):
```python
compile_fortran = ['ifort', '/c', '/fpp', '/extend-source',
                   '/DABQ_WIN86_64', ...]
```
- `/fpp` : 전처리(우리 코드의 `include 'vaba_param.inc'` 처리)
- `/extend-source` : **고정형식(fixed-form) 소스 확장** — 우리 `.f` 는
  고정형식(7열부터 코드, 6열 연속행)이라 이 플래그와 호환됩니다.

### 컴파일러 초기화가 필요할 때
`ifort` 가 PATH에 없다는 오류가 나면, Intel 환경을 먼저 로드합니다:
```bat
call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
```
그 뒤 같은 명령창에서 `abaqus ...` 를 실행하세요. (경로에 공백이
있으므로 반드시 따옴표로 감쌉니다.)

### 실행 명령 (Windows)
```bat
REM (a) 3층 피부
abaqus job=ml01  input=01_multilayer_skin.inp   user=vumat_skin.f     double=both cpus=4

REM (b) HGO + 사전인장  (먼저 입력파일 생성)
python gen_hgo_model.py
abaqus job=hgo02 input=02_hgo_pretension.inp     user=vumat_skin_hgo.f double=both cpus=4

REM (c) 니들 좌굴 (서브루틴 불필요)
abaqus job=buck03 input=03_needle_buckling.inp

REM 후처리
abaqus python postprocess.py hgo02.odb
```
> 이 환경에서는 `abaqus` 실행이 확인되었습니다
> (job buck03 COMPLETED, ref04 VUMAT COMPLETED, 2026-07-14).

---

## 2. Linux 클러스터 (cae20 ~ cae23)

로컬과 **컴파일러 경로가 다릅니다.** 클러스터의 oneAPI는 보통
`/opt/intel/oneapi/...` 에 있으므로, 먼저 실제 경로/버전을 확인하세요.

```bash
# 로그인 노드 또는 배치 스크립트에서
source /opt/intel/oneapi/setvars.sh          # 클러스터 실제 경로로 대체
which ifort ifx                               # 존재 여부 확인
abaqus info=system                            # Abaqus가 링크한 컴파일러 확인
abaqus verify -user_explicit                  # 링크 검증
```

### ifort vs ifx (중요)
- oneAPI 2024 부터 클래식 **`ifort` 는 지원 종료(deprecated)** 이며,
  이후 버전(2025+)에서는 **`ifx`(LLVM 기반)만** 제공될 수 있습니다.
- 클러스터에 `ifort` 가 없고 `ifx` 만 있으면, Abaqus의 Linux 환경파일에서
  `compile_fortran` 의 컴파일러 이름을 `ifx` 로 바꿔야 합니다.
- `ifx` 고정형식 플래그는 `-extend-source`(=132열), 전처리는 `-fpp`.
  우리 `.f` 는 고정형식이라 그대로 컴파일됩니다.

환경파일 오버라이드 예 (잡 디렉터리에 `abaqus_v6.env` 로 두면 우선 적용):
```python
# --- Linux, ifx 로 강제할 때의 예시 (경로/플래그는 환경에 맞게 확인) ---
compile_fortran = ['ifx', '-c', '-fpp', '-extend-source',
                   '-DABQ_LNX86_64', '-auto', '-mcmodel=medium',
                   '-fPIC', '-O2', '-I%I']
```
> 실제 표준 플래그 세트는 `abaqus info=system` 출력의 기본
> `compile_fortran` 을 복사한 뒤 컴파일러 이름만 교체하는 것이 안전합니다.
> 위는 이름·플래그 감을 잡기 위한 예시입니다.

### 실행 명령 (Linux, 예: SLURM 배치 안에서)
```bash
source /opt/intel/oneapi/setvars.sh
python gen_hgo_model.py

abaqus job=ml01  input=01_multilayer_skin.inp  user=vumat_skin.f     double=both cpus=8
abaqus job=hgo02 input=02_hgo_pretension.inp   user=vumat_skin_hgo.f double=both cpus=8
abaqus job=buck03 input=03_needle_buckling.inp
abaqus python postprocess.py hgo02.odb
```
클러스터에서는 `abaqus` 실행 전에 모듈 로드가 필요할 수 있으니 사이트
안내를 따르세요. Explicit 다중 CPU는 `cpus=N`(자동 도메인 분할)로 지정합니다.

---

## 3. 자주 겪는 문제

| 증상 | 원인 / 해결 |
|------|-------------|
| `ifort: command not found` / `is not recognized` | 컴파일러 환경 미로드 → `setvars`(bat/sh) 먼저 실행 |
| `abaqus verify -user_*` FAIL | Abaqus–컴파일러 버전 비호환 또는 링크 경로 오류 → `info=system` 으로 경로 확인, VS/oneAPI 버전 조합 점검 |
| 고정형식 소스 컬럼 오류 | `/extend-source`(Win) / `-extend-source`(Linux) 누락 → 환경파일 확인 |
| `include 'vaba_param.inc'` 관련 오류 | 전처리 플래그 `/fpp`(Win)·`-fpp`(Linux) 누락 |
| 정밀도 관련 이상/발산 | `double=both` 누락 → 반드시 지정(VUMAT 배정밀도) |
| Linux에서 `ifort` 없음 | oneAPI 2025+ → `ifx` 로 `compile_fortran` 교체(2절) |

---

## 4. 실행 전 권장 순서

1. `abaqus info=system` → 링크된 컴파일러 경로/버전 기록.
2. `abaqus verify -user_explicit` → `PASS` 확인.
3. `(c) 03_needle_buckling.inp` 먼저 실행(서브루틴 없이 모델·환경 sanity).
4. `(a) 01_multilayer_skin.inp` (Explicit + VUMAT) 실행 → `ALLKE ≪ ALLIE`
   (준정적성)·관통력 곡선 확인.
5. `(b) 02_hgo_pretension.inp` 실행 → 사전인장 효과 확인.

> 이 저장소의 서브루틴/입력파일은 문법·구성 정합성을 코드 레벨로
> 검토했으나, **실제 Abaqus 실행 검증은 사용자 환경에서 수행**해야 합니다.
> 첫 실행에서 나오는 `.log`/`.dat`/`.sta` 메시지를 공유해 주시면 함께
> 디버깅하겠습니다.

---

## 5. 전문가 피드백 반영 모델 — A · B · C (신규, 실행검증 필요)

세 모델 모두 마이크로 단위계(µm, µN, MPa, s, 밀도 kg/µm³)입니다.
먼저 생성기를 돌려 `.inp` 를 만든 뒤 실행하세요.

```bat
python gen_microneedle_discrete.py   REM -> 11_microneedle_discrete.inp
python gen_cohesive_axi.py           REM -> 12_ , 13_ 동시 생성
```

### (A) 이산 강체(Discrete Rigid) 중공 니들 + 접촉 필렛
니들 벽을 **RAX2**(축대칭 강체요소)로 이산화 → 요소기반 강체표면은
일반접촉에서 **자동 양면(two-sided)** 처리(외벽·보어 동시 접촉). 팁 코너를
원호 노드열로 물리적으로 둥글려 접촉 응력집중/튐을 억제.
```bat
abaqus job=mn11 input=11_microneedle_discrete.inp user=vumat_skin.f double=both cpus=4 interactive
abaqus python postprocess.py mn11.odb
```
- 확인 포인트: 접촉력–깊이 곡선이 매끈한지(팁 필렛 효과), 관통 시작 깊이.
- 참고: 요소삭제 VUMAT 유지(니들/접촉 안정성 검증이 목적).

### (A-2) 변형 가능한 "두께 있는" 니들 (2D CAX4R, 강체선 대체)
니들을 1D 강체선(RAX2)이 아니라 **변형 가능한 축대칭 2D 요소(CAX4R)**
로 모사 — CAE에서 "축대칭 shell 파트(2D 면) + Solid section" 방식.
면의 기하 폭이 곧 벽 두께라 화면에서 실제로 두껍게 보임(두께 property
불필요). 실제 형상(내경 30 / 팁 20µm → 샤프트 120µm 가변 벽) 사용.
상단을 참조점 9999에 운동학적 결합해 하강 구동(RF2 = 삽입력).
```bat
python gen_microneedle_shell.py
abaqus job=mn14 input=14_microneedle_shell.inp user=vumat_skin.f double=both cpus=4 interactive
abaqus python postprocess.py mn14.odb
```
- 니들 물성: 스테인리스강 예시(E=200 GPa, ν=0.3, ρ=7.9e-15). 필요 시
  `gen_microneedle_shell.py` 상단 `NDL_*` 로 실리콘/폴리머 교체.
- 뷰어에서 두께 확인: 니들 요소가 r-z 평면에서 폭을 가진 2D 밴드로 표시.
- **주의(축대칭 한계):** 좌굴/굽힘(비축대칭) 불가 → 축방향 압축·반경변형
  만. 측면 좌굴은 `03_needle_buckling` 이 담당.
- 강성 니들 + 미세요소라 안정증분이 작음 → 질량스케일링 필수(적용됨).
  실행 후 `ALLKE/ALLIE` 준정적성 확인 권장.

### (B) 축대칭 Cohesive 절개 ⭐ (요소 삭제 없음)
반경 `R_CUT=50µm` 원통면에 두께 0 **COHAX4** cohesive 삽입 → 강체
니들이 코어를 밀며 견인-분리로 매끈한 원통형 절개. **서브루틴 불필요**.
```bat
abaqus job=coh12 input=12_cohesive_axi.inp double=both cpus=4 interactive
abaqus python postprocess.py coh12.odb
```
- CZM: 초기강성 4000 MPa/mm(=4 MPa/µm), 강도 2 MPa, Gc 10 µN/µm.
- 확인 포인트: cohesive `SDEG`(손상)·`STATUS`, 코어 분리, `ALLDMD`(손상소산).

### (C) 사용자 정의 이중선형 CZM VUMAT
(B)의 내장 cohesive 를 사용자 `vumat_cohesive.f`(혼합모드 I/II, 손상이력)
로 교체. PROPS = K, t0, Gc, T0, β. **cohesive 요소에 `user=` 필수**.
```bat
abaqus job=coh13 input=13_cohesive_axi_vumat.inp user=vumat_cohesive.f double=both cpus=4 interactive
abaqus python postprocess.py coh13.odb
```
- 확인 포인트: `SDV5`(손상 d)·`SDV7`(유효분리)·`STATUS`. (B)와 힘–깊이
  곡선이 일치하면 VUMAT 검증 완료.
- 성분규약: 인덱스1=법선, 2..=전단(COHAX4=2성분). 힘–깊이가 (B)와
  어긋나면 `vumat_cohesive.f` 헤더의 성분규약 주석을 확인하세요.

> A/B/C 는 코드 레벨(린터·기하·고정형식) 정합성까지 확인했으나 원격
> 컨테이너에서 Abaqus 실행은 불가하여 **사용자 환경 실행검증이 필요**합니다.

### (결합) 이원화 피부: 코어(삭제) / 외부(비삭제) + cohesive ⭐ 최종
피부를 **니들 반경(r=50µm) 기준으로 이원화**해 니들 투과 간섭을 제거:
- **코어 (r<50, 빨강)**: VUMAT **hyperelastic + damage(요소삭제)** -> 니들
  경로의 요소를 제거(깨끗한 관통, 간섭 없음).
- **외부 (r>50, 노랑)**: **삭제 없는** 내장 Neo-Hookean(순수 변형).
- **경계 r=R_CUT**: COHAX4 **cohesive**(니들 삽입 시 debonding).
니들: **CAX4R 2D 솔리드 메쉬 + 강체(Rigid Body)**, 축(r=0) 중심 blunt 둥근
팁. 요소기반 표면이라 침식(erosion) 접촉이 해석적 강체보다 강건.
접촉부·코어 요소 -30%, 코어반경 R_CUT=35um(-30%)로 세밀화.
삭제-투과 대책: 접촉 stabilization(*CONTACT DAMPING)은 투과를 "안정"으로
오인·고착시켜 **제거**함. 접촉은 hard + `ALL EXTERIOR`(삭제로 노출된 내부
면 자동 포함=Interior Surfaces)로 일원화. 잔여 대책: `DAMP_ALPHA`(재료
damping)·`MS_DT`(증분). 여전히 투과 시 `MS_DT`↓(1e-7->5e-8)·요소 추가 세밀화.
```bat
python gen_microneedle_cohesive.py
abaqus job=mn15 input=15_microneedle_cohesive.inp user=vumat_skin.f double=both cpus=4 interactive
abaqus python postprocess.py mn15.odb
```
- 확인 포인트: 코어 `STATUS`(삭제 관통) + cohesive `SDEG`(절개), 힘-깊이(RF2).
- 여전히 왜곡 시 `PUSH`(현재 300µm) 축소, 또는 층 `lam_f`(파단 stretch) 하향.
- cohesive 를 사용자 CZM 으로: COHMAT 을 vumat_cohesive.f(작업 C)로 교체.

### (16) 니들 관통 - 솔리드 원뿔 3층 (CAE Assistant 방식, 삭제+cohesive 병용)
"Needle Puncture of Skin by Injection" 레퍼런스 구성: 솔리드 원뿔 니들
+ 3층(표피/진피/피하) **hyperelastic + cohesive + 층 damage(요소삭제)**.
삭제가 첨두 아래 코어를 제거해 과도변형 중단을 막고, r=R_CONE cohesive 가
깨끗한 절개 경계를 만듦(두 메커니즘 병용).
```bat
python gen_needle_puncture.py
abaqus job=np16 input=16_needle_puncture.inp user=vumat_skin.f double=both cpus=4 interactive
abaqus python postprocess.py np16.odb
```
- 층: 표피(stiff)/진피/피하(soft fat), VUMAT deletion(C10,D1,lam_d,lam_f).
- 확인: 코어 `STATUS`(삭제 관통) + cohesive `SDEG`(절개), 힘-깊이(RF2).
- 삭제+cohesive 병용이라 15의 코어 과압축 중단 위험이 낮음(가장 강건).

### (17) 논문 정렬 모델 — Ogden 2층 + 순수 요소삭제 ⭐ 접촉투과 해결
Yolai et al. (Mater. & Design 259, 2025) 방법. **cohesive 를 버리고 순수
요소삭제**로 회귀 -> debond-vs-delete 충돌·stabilization 고착 문제 원천 제거.
- 피부 2층(표피 0.1 / 진피 2.4mm), **1차 Ogden 초탄성**(논문 Table 2 값).
- 파단: **von Mises 응력 OR 등가변형** 요소삭제 (`vumat_skin_ogden.f`).
  표피 σf=5.8/εf=0.084, 진피 σf=15/εf=0.45.
- 접촉: General Contact `ALL EXTERIOR`(삭제 노출면 자동 포함) + **마찰 0.42**.
  stabilization/contact damping **미사용**.
- 접촉부 메쉬 **8µm**(논문 mesh sensitivity) -> 삭제 진동↓.
```bat
python gen_needle_paper.py
abaqus job=np17 input=17_needle_paper.inp user=vumat_skin_ogden.f double=both cpus=4 interactive
abaqus python postprocess.py np17.odb
```
- 단위 **mm, N, MPa, tonne, s**(논문 동일). 니들 원뿔(팁경0.04/기저0.3/H1.2).
- 논문 핵심: 삭제 후 니들이 순간적으로 구속해제→다음 층 접촉까지 힘-변위
  **작은 진동**(투과 아님, 메쉬 세밀화로 완화). cohesive 불필요.
- 진피 α=57.89 는 강한 변형경화 -> 질량스케일링·증분 주의(ALLKE/ALLIE 확인).
- **단위 주의**: 논문 D1=1.03e-7 은 SI(1/Pa). MPa 단위 변환 -> **D1=0.103**
  (K=19.4 MPa). 1e-7 그대로 쓰면 K=19.4 GPa -> 초비압축 -> 질량스케일링
  폭주 -> ALLKE≫ALLIE(관성 지배)·삽입력 0 의 비물리 결과. 반드시 0.103 사용.
