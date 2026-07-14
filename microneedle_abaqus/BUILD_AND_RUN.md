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
REM Windows (호트픽스 드라이버)
abq2025hf4 info=system
```
```bash
# Linux 클러스터
abaqus info=system        # 또는 abq2025, 모듈 로드 후
```
출력의 **Fortran Compiler / C++ Compiler 경로·버전**이 실제 링크 값입니다.
이어서 아래로 "컴파일러가 실제로 동작하는지"까지 검증하세요.

```bat
abq2025hf4 verify -user_explicit    REM VUMAT/VEXTERNALDB 등 Explicit 유저루틴 링크 검증
abq2025hf4 verify -user_std         REM UMAT 등 Standard 유저루틴 링크 검증
```
`PASS` 가 나오면 우리 VUMAT도 동일 경로로 컴파일됩니다.

---

## 1. Windows 로컬 환경 (제공된 설정 요약)

| 항목 | 값(로컬 기준) |
|------|--------------|
| Abaqus | 2025, `ABA_HOME = C:\SIMULIA\EstProducts\2025\win_b64` |
| 실행 드라이버 | `abq2025hf4.bat` |
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
그 뒤 같은 명령창에서 `abq2025hf4 ...` 를 실행하세요. (경로에 공백이
있으므로 반드시 따옴표로 감쌉니다.)

### 실행 명령 (Windows)
```bat
REM (a) 3층 피부
abq2025hf4 job=ml01  input=01_multilayer_skin.inp   user=vumat_skin.f     double=both cpus=4

REM (b) HGO + 사전인장  (먼저 입력파일 생성)
python gen_hgo_model.py
abq2025hf4 job=hgo02 input=02_hgo_pretension.inp     user=vumat_skin_hgo.f double=both cpus=4

REM (c) 니들 좌굴 (서브루틴 불필요)
abq2025hf4 job=buck03 input=03_needle_buckling.inp

REM 후처리
abq2025hf4 python postprocess.py hgo02.odb
```

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
클러스터에서는 `abaqus` 대신 모듈/버전 별칭(`abq2025` 등)일 수 있으니
사이트 안내를 따르세요. Explicit 다중 CPU는 `cpus=N`(자동 도메인 분할)로
지정합니다.

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
