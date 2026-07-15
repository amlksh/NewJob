# Claude로 Abaqus 사용자 서브루틴 해석하기 — 사용자 매뉴얼

> **대상 독자**: Abaqus는 다뤄봤지만 Claude(Claude Code)로 서브루틴 해석을
> 자동화해 본 적 없는 동료. **환경설정 기초부터** 시작해 **마이크로니들
> 피부 관통 해석 샘플의 실사용 예시**까지 따라 하면 되도록 구성했습니다.
>
> **한 줄 요약**: Claude Code를 **당신 PC에 로컬로 설치**하면, Claude가
> 당신 PC의 Abaqus를 **직접 실행하고 로그를 읽어 리포트**해 줍니다.
> (웹/클라우드 Claude로는 당신 PC의 Abaqus를 못 돌립니다 — 아래 1장.)

---

## 목차
1. 큰 그림 — 로컬 vs 웹 Claude Code (가장 중요)
2. 사전 준비 (Abaqus · Fortran 컴파일러 · 라이선스)
3. Claude Code 설치 (CLI / 데스크톱 앱)
4. 연동 검증 — 서브루틴이 실제로 컴파일되는지
5. Claude로 작업하는 법 (프롬프트·승인·로그 읽기)
6. 실전 예제 — 마이크로니들 피부 관통 해석
7. 자주 겪는 문제 & 해결 (실전 트러블슈팅)
8. 서브루틴(VUMAT) 작성·디버깅을 Claude에게 시키기
9. 부록 — 명령어 치트시트 · 파일 목록
- 부록 A. **VUMAT ↔ Abaqus 프로세스 마인드맵**

---

## 1. 큰 그림 — 로컬 vs 웹 Claude Code (가장 중요)

Claude Code는 **실행 위치가 두 종류**입니다. 이걸 먼저 이해해야 합니다.

| | **로컬 Claude Code** | **웹/클라우드 Claude Code** |
|---|---|---|
| 설치/실행 | 내 PC (CLI 또는 데스크톱 앱) | 브라우저 `claude.ai/code` |
| 내 PC 파일 접근 | ✅ 직접 | ❌ (원격 컨테이너) |
| **내 PC의 Abaqus 실행** | ✅ **가능** | ❌ 불가 |
| 결과 로그 읽고 리포트 | ✅ | 파일을 업로드해야 함 |

**결론: Abaqus 서브루틴 해석은 반드시 "로컬 Claude Code"로 합니다.**
웹 세션은 코드 편집·저장소 정리엔 좋지만, 당신 PC에 설치된 Abaqus·
컴파일러·라이선스에 접근할 수 없습니다.

> 로컬로 시작하는 법 = **내 PC의 터미널(또는 데스크톱 앱)에서 `claude`
> 실행**. 브라우저에서 시작하면 웹 세션이 됩니다. (3장 참조)

---

## 2. 사전 준비 (환경)

Claude를 깔기 전에, **Abaqus 서브루틴을 손으로 돌릴 수 있는 환경**이 먼저
갖춰져 있어야 합니다. Claude는 그 환경을 "대신 조작"할 뿐이기 때문입니다.

### 2.1 Abaqus 본체
- Abaqus 2023 이상 권장 (본 매뉴얼은 **Abaqus 2025.HF4** 기준).
- 명령창에서 아래가 동작해야 합니다:
  ```bat
  abaqus information=release
  ```
  본 매뉴얼은 실행 명령을 **`abaqus`로 통일**합니다(검증 환경에서 동작 확인).

### 2.2 Fortran 컴파일러 (Intel oneAPI)
사용자 서브루틴(UMAT/VUMAT 등)은 **실행 시점에 Fortran으로 컴파일**됩니다.
따라서 Abaqus와 호환되는 컴파일러가 필요합니다.
- **Intel oneAPI Fortran** (`ifort` 클래식 또는 `ifx` LLVM기반) + Windows는
  **Visual Studio C++ (`cl`)** 도 필요.
- 본 매뉴얼 검증 환경: **Intel oneAPI 2024** `ifort` (버전 2021.11.1) +
  VS2022 `cl`, Abaqus 2025.
- oneAPI 2024부터 클래식 `ifort`는 지원 종료 예정 → 신규/클러스터는
  `ifx`로 전환될 수 있습니다(경고 #10448은 무해).

### 2.3 컴파일러–Abaqus 연동 방식 (중요)
컴파일러 환경(vcvars64 + oneAPI vars)은 보통 **전역 PATH가 아니라 Abaqus
실행 명령(`abaqus`)이 내부적으로 부르는 드라이버 배치파일에 주입**되어
있습니다. 그래서:
- **일반 셸에서 `ifort` 단독 호출은 안 보이는 게 정상**이고,
- **`abaqus` 로 호출할 때만** 서브루틴 컴파일이 동작합니다.
> Abaqus를 재설치하면 이 주입이 사라질 수 있으므로, 담당자가 드라이버
> 배치파일 백업을 두고 다시 적용하는 관리가 필요합니다.

### 2.4 라이선스 (자주 걸림)
- **Abaqus/Standard(또는 Foundation)** 토큰: `*STATIC`, `*BUCKLE` 등.
- **Abaqus/Explicit** 토큰: `*DYNAMIC, EXPLICIT` (VUMAT 관통 해석은 이것!).
- Standard만 있고 **Explicit 라이선스가 없으면 VUMAT 관통 해석이 막힙니다.**
- 확인: `abaqus licensing ru` (사용 가능 토큰 목록).
- 라이선스 서버(예: `27001@localhost`) 데몬이 죽으면 컴파일과 무관하게
  실행이 막힙니다 — 그 경우 서버 재기동 필요.

---

## 3. Claude Code 설치

### 3.1 CLI 설치 (Windows, WSL 불필요)
**PowerShell**에서:
```powershell
irm https://claude.ai/install.ps1 | iex
```
(대안: `winget install Anthropic.ClaudeCode`)

설치 후 확인:
```powershell
claude --version
```

### 3.2 PATH 등록 (설치 직후 흔한 함정)
설치 시 *"`C:\Users\<이름>\.local\bin` is not in your PATH"* 경고가 뜨면
`claude`가 인식되지 않습니다. **사용자 PATH에 영구 등록**:
```powershell
$p = [Environment]::GetEnvironmentVariable("Path","User")
[Environment]::SetEnvironmentVariable("Path", $p + ";$env:USERPROFILE\.local\bin", "User")
```
→ **터미널을 닫았다 새로 열면** 어디서든 `claude`가 됩니다.

### 3.3 터미널 — Windows Terminal 권장
구형 PowerShell 콘솔은 Claude 화면(ANSI)이 `^[[35m...`처럼 **깨져 보일 수**
있습니다. **Windows Terminal**을 쓰면 깔끔합니다:
```powershell
winget install Microsoft.WindowsTerminal
```
(임시 대안: `Set-ItemProperty -Path HKCU:\Console -Name VirtualTerminalLevel -Value 1` 후 터미널 재시작)

### 3.4 로그인
- 첫 `claude` 실행 시 브라우저로 로그인. **Claude Pro/Max 구독** 필요
  (무료 플랜은 Claude Code 미포함).

### 3.5 데스크톱 앱 대안 (GUI 선호 시)
[claude.com/download](https://claude.com/download) 설치 → **`Code`** 탭 →
**Environment** 드롭다운 **`Local`** → **Select folder**로 프로젝트 폴더
선택. GUI라 터미널 렌더링 문제가 없고, 시각적 diff·내장 터미널(`Ctrl+\``)이
편합니다. (Windows에서는 **Git 설치가 필수**.)

---

## 4. 연동 검증 — 서브루틴이 실제로 컴파일되는지 (건너뛰지 말 것)

Claude로 뭘 하기 전에, **Abaqus–컴파일러 연동이 실제로 되는지** 확인합니다.
```bat
abaqus info=system            REM 링크된 Fortran/C++ 컴파일러 경로·버전 출력
abaqus verify -user_std       REM UMAT 등 Standard 유저루틴 컴파일·링크 검증
abaqus verify -user_explicit  REM VUMAT 등 Explicit 유저루틴 컴파일·링크 검증
```
`PASS`가 나오면, 우리 서브루틴도 **동일 경로로 컴파일**됩니다. 여기서
실패하면 Claude 문제가 아니라 **환경(컴파일러/VS/라이선스) 문제**이므로
먼저 해결해야 합니다.

---

## 5. Claude로 작업하는 법

### 5.1 로컬 세션 시작
```powershell
cd "C:\Users\<이름>\Documents\...\프로젝트폴더"
claude
```
> 경로에 **공백**이 있으면 반드시 **따옴표**로 감쌉니다.
> (`cd C:\Users\SEONGHOON KIM\...` → 오류. `cd "C:\...\SEONGHOON KIM\..."` → OK)

### 5.2 지시는 "Claude 안"에서 (PowerShell 아님!)
`claude`가 뜨면 화면이 PowerShell(`PS C:\...>`)과 **다른 입력창**으로 바뀝니다.
**자연어 지시는 그 입력창에** 입력합니다.
- ❌ PowerShell 프롬프트(`PS ...>`)에 자연어를 치면 "명령 인식 안됨" 오류
- ✅ Claude 입력창(`PS` 없음)에 한국어로 지시

예시 지시:
```
microneedle_abaqus 폴더에서 04_refined_path 모델(job 이름 ref04)을
interactive로 실행하고, ref04.log·sta·msg 를 읽어 결과를 리포트해줘.
postprocess.py로 관통력-깊이 곡선도 뽑아줘.
```

### 5.3 승인(manual mode)
기본은 `manual mode`라, Claude가 명령 실행 전 **"실행할까요?"**를 묻습니다.
읽기 전용(`which`, `type` 등)이나 의도한 실행이면 **승인(1. Yes)**.
자주 쓰는 안전한 명령은 "2. 이 폴더에서 다시 안 물어보기"로 등록 가능.

### 5.4 abaqus.bat + bash 주의 (실전 팁)
Claude는 내부적으로 **bash(Git Bash)** 로 명령을 실행할 때가 있는데,
당신 Abaqus는 **`abaqus.bat`**(배치파일)이라 **bash에서 `which abaqus`가
"없음"** 으로 나올 수 있습니다(PowerShell에선 되는데도). 그럴 땐 Claude에게:
> abaqus는 abaqus.bat이야. bash에서 안 잡히면 `cmd //c "abaqus job=... "`
> 또는 PowerShell로 실행해줘.

### 5.5 결과를 "읽고 리포트"하게 하기
실행 후 생성되는 `*.log`(컴파일), `*.sta`(증분·에너지), `*.msg`(경고/에러),
`*.dat`(입력검증·결과), `*.odb`(결과DB)를 Claude가 읽어 요약하게 합니다.
> "ref04.sta랑 msg 읽고, 준정적성(ALLKE/ALLIE)이랑 요소삭제 여부 판단해줘."

---

## 6. 실전 예제 — 마이크로니들 피부 관통 해석

피부에 마이크로니들이 삽입·관통되는 현상을 **Abaqus/Explicit + VUMAT**
(초탄성 + 손상 기반 요소 삭제)로 모사하는 샘플입니다.

### 6.1 저장소 받기
```powershell
cd "C:\Users\<이름>\Documents\Claude"
git clone <저장소주소> NewJob
cd NewJob
git checkout claude/microneedle-abaqus-subroutine-vumii3
cd microneedle_abaqus
```

### 6.2 파일 구성 (요약)
| 파일 | 내용 |
|------|------|
| `vumat_skin.f` | 피부 VUMAT (Neo-Hookean + 주신축비 손상/삭제) |
| `vumat_skin_ogden.f` | **1차 Ogden + von Mises/변형 요소삭제** (논문 정렬, 모델 17) |
| `vumat_cohesive.f` | 사용자 이중선형 CZM (cohesive 요소용, 모델 15 옵션) |
| `vumat_skin_reg.f` / `vumat_skin_hgo.f` | 에너지정규화 / 이방성 HGO VUMAT |
| `03_needle_buckling.inp` | 니들 좌굴 임계하중(`*BUCKLE`) — 서브루틴 불필요 |
| `04_refined_path.inp` | 경로 세밀화 3층 관통 (기본 예제) |
| `17_needle_paper.inp` | **논문 정렬 Ogden 2층 순수삭제** (권장, 6.8) |
| `15_microneedle_cohesive.inp` | **cohesive 절개 + damage 이원화** (6.8) |
| `gen_needle_paper.py` / `gen_microneedle_cohesive.py` | 위 두 모델 생성기(수정은 여기서) |
| `postprocess.py` | 관통력-깊이 + 준정적성 + 삭제요소 종합 리포트 |
| `README.md` / `BUILD_AND_RUN.md` | 모델 설명 / 빌드·실행 가이드(전 모델) |

### 6.3 STEP 1 — 서브루틴 없이 sanity 체크 (좌굴)
먼저 서브루틴이 필요 없는 좌굴 해석으로 **모델·환경**을 확인합니다.
```bat
abaqus job=buck03 input=03_needle_buckling.inp interactive
```
- 마지막에 `Abaqus JOB buck03 COMPLETED` 확인.
- `buck03.dat`의 EIGENVALUE 표 → **임계 좌굴하중 P_cr**.
- **검증 실측값**: 최저 모드 **P_cr ≈ 0.219 N** (모드 1=2 쌍중복 = 원형단면
  기둥의 정상 거동).

### 6.4 STEP 2 — VUMAT 관통 해석 (핵심)
```bat
abaqus job=ref04 input=04_refined_path.inp user=vumat_skin.f double=both cpus=4 interactive
```
- **`double=both` 필수** (VUMAT 배정밀도).
- `ref04.log`에서 **VUMAT 컴파일·링크 성공** 확인 (ifort 경고 #10448은 무해).
- `ref04.sta` 마지막에 `THE ANALYSIS HAS COMPLETED SUCCESSFULLY`.
- **검증 실측**: Explicit 8토큰 체크아웃, VUMAT 컴파일 성공, 418요소 완주.

### 6.5 STEP 3 — 결과 리포트
```bat
abaqus python postprocess.py ref04.odb
```
자동 출력:
- **[1] 관통력–침투깊이**: peak 관통력·깊이, puncture(급락) 감지 →
  `ref04_fd.csv`, `ref04_fd.png`
- **[2] 준정적성**: `ALLKE/ALLIE(max)` — **<5% 양호**, >10%면 질량스케일링
  재검토 (얇은 각질층 때문에 질량 스케일링이 크게 걸릴 수 있음).
- **[3] 요소 삭제**: 삭제(=관통)된 요소 수. **0이면 "압입만" 하고
  절개 미발생** → 물성(λ_f / uf)·하강량 조정 검토.

### 6.6 STEP 4 — 공학적 판정 (삽입 성공 여부)
문헌(*Int. J. Pharm.* 2025) 기준:
> **삽입 성공 ⇔ 삽입력 F_ins < 니들 좌굴하중 P_cr**
- (6.5)의 peak 관통력 = `F_ins`
- (6.3)의 `P_cr = 0.219 N`
- `F_ins < 0.219 N` → 니들이 좌굴 전에 관통(성공). 아니면 니들 재설계.

### 6.7 Claude에게 통째로 시키기 (권장 실사용 흐름)
로컬 Claude 입력창에 한 번에:
```
microneedle_abaqus 폴더에서:
1) buck03(03_needle_buckling.inp) 실행하고 dat에서 P_cr 읽어줘.
2) ref04(04_refined_path.inp, user=vumat_skin.f, double=both) interactive 실행.
3) ref04.log 컴파일 성공여부, sta 완료여부 확인.
4) postprocess.py로 관통력-깊이·준정적성·삭제요소 리포트.
5) F_ins와 P_cr 비교해서 삽입 성공여부까지 판정해줘.
```
Claude가 각 명령을 (승인받아) 실행하고 로그를 읽어 단계별로 리포트합니다.

### 6.8 심화 — 실제 "관통(splitting)"이 되는 모델 (검증 완료)

기본 예제(6.3~6.6)는 요소 삭제로 관통을 보이지만, 실제 조직 절개·니들
접촉을 사실적으로 잡으려면 다음 두 모델을 권장합니다. **여러 차례 실패를
거쳐 확립한 레시피**이며, 특히 "요소 삭제 후 니들이 피부를 통과하는" 침식
접촉 문제를 해결했습니다.

| 모델 | 생성기 → 입력 | 특징 |
|------|------|------|
| **17** (권장) | `gen_needle_paper.py` → `17_needle_paper.inp` | 논문(Yolai 2025) 정렬: **1차 Ogden 2층 + 순수 요소삭제**(`vumat_skin_ogden.f`), 마찰 0.42 |
| **15** | `gen_microneedle_cohesive.py` → `15_microneedle_cohesive.inp` | **cohesive 절개 + damage 이원화**(코어 삭제/외부 비삭제/경계 cohesive) |

**핵심 성공 요인 5가지** (하나라도 빠지면 실패):

1. **물성 단위** — Ogden `D1`은 논문 SI값(1/Pa)을 MPa계로 환산(×1e6).
   틀리면 K가 1000배 → 관성 폭주(ALLKE≫ALLIE)·삽입력 0.
2. **침식 접촉(가장 중요)** — 피부 표면을 요소 **4면(S1~S4)** 으로 정의해
   내부 면까지 접촉 도메인에 넣어야, 삭제로 드러난 속살에 니들이 연속
   접촉(밀링식). elset만 주면 외곽만 잡혀 니들이 통과함.
   ```
   *SURFACE, TYPE=ELEMENT, NAME=SKIN_SURF
   SKIN_ALL, S1
   SKIN_ALL, S2
   SKIN_ALL, S3
   SKIN_ALL, S4
   ```
3. **삭제 국소화** — 삭제를 **응력 파단(σf)** 기준으로(끝단에만) → 광역
   크레이터·갭 방지.
4. **stabilization 금지** — `*CONTACT DAMPING`은 투과를 은폐하므로 제거.
5. **요소기반 강체 니들** — 해석적 강체보다 **discrete rigid(CAX4R+
   `*RIGID BODY`)** 가 침식 접촉에 강건.

실행(모델 17):
```bat
python gen_needle_paper.py
abaqus job=np17 input=17_needle_paper.inp user=vumat_skin_ogden.f double=both cpus=4 interactive
abaqus python postprocess.py np17.odb
```
- **성공 지표**: 진피에서 von Mises가 **파단응력(15 MPa) 근처**까지 상승
  (= 접촉 유지), `ALLKE/ALLIE<10%`, 삽입력(RF2) 비영.
- 자세한 모델 목록·튜닝은 `BUILD_AND_RUN.md` §5 참조.

---

## 7. 자주 겪는 문제 & 해결 (실전 트러블슈팅)

아래는 **이 프로젝트를 세팅하며 실제로 겪은** 문제들입니다.

| 증상 | 원인 | 해결 |
|------|------|------|
| `'claude' 인식되지 않습니다` | `.local\bin`이 PATH에 없음 | 3.2 PATH 영구 등록 후 터미널 재시작 |
| `cd C:\...\홍 길동\...` 오류(위치 매개변수) | 경로 **공백** | 경로를 **따옴표**로 감싸기 |
| 화면이 `^[[35m...`로 깨짐 | 구형 콘솔이 ANSI 미지원 | **Windows Terminal** 사용 (3.3) |
| 입력창에 붙여넣기 안됨 | 콘솔 붙여넣기 단축키 차이 | **우클릭**(구형) / **Ctrl+Shift+V**(신형) |
| 자연어 쳤더니 `명령 인식 안됨` | **PowerShell에 입력**함(Claude 밖) | `PS >` 없는 **Claude 입력창**에 입력 (5.2) |
| bash에서 `abaqus` 못 찾음 | `abaqus.bat`을 bash가 못 잡음 | `cmd //c "abaqus ..."` 또는 PowerShell (5.4) |
| job이 순식간에 끝나고 결과 없음 | **백그라운드 제출** | 명령 끝에 **`interactive`** 추가 |
| `postprocess`가 RF/U 이력 못 찾음 | 잡 미완료/중단 | `interactive`로 완주 후 다시 후처리 |
| `*CONTACT PROPERTY ASSIGNMENT CAN ONLY REFERENCE SURFACE INTERACTIONS` | `*SURFACE INTERACTION`이 **스텝 안**에 있음 | 첫 `*STEP` **앞(모델 데이터)** 으로 이동 |
| Explicit 잡이 라이선스로 막힘 | Foundation/Standard만 보유 | **Abaqus/Explicit** 토큰 확보 (`abaqus licensing ru`) |
| `PERCENT CHNG MASS`가 큼(수백%) | 얇은 요소로 질량 스케일링 큼 | `ALLKE/ALLIE<5~10%` 확인, 안되면 목표 dt·메쉬 조정 |
| 컴파일은 되는데 결과 이상/발산 | `double=both` 누락 | 반드시 `double=both` 지정 |
| **삽입력 ≈ 0, `ALLKE/ALLIE` 수천%** | **물성 단위 오류**(특히 Ogden `D1`을 SI `1/Pa`로 MPa계에 입력 → K가 1000배) | 단위계로 환산: `D1[1/MPa]=D1[1/Pa]×1e6`. 예 1.03e-7→**0.103** |
| **요소 삭제 후 니들이 피부 속으로 통과**(접촉 소실) | `*SURFACE, TYPE=ELEMENT`에 elset만 주면 **자유(외곽)면만** 생성 → 삭제로 드러날 **내부 면이 접촉 표면에 없음** | 요소 **4면 전부 명시**: `elset, S1`/`S2`/`S3`/`S4` → 내부면 접촉 도메인 사전 등록(밀링식 침식 접촉) |
| 삭제가 니들보다 **넓게** 일어나 갭 발생 | 변형률 기준이 너무 낮아 광역 조기 삭제 | 삭제를 **응력 파단(σf) 기준으로 국소화**(끝단에만) |
| `*CONTACT DAMPING`을 켰더니 투과가 그대로 굳음 | stabilization이 **투과 상태를 "안정"으로 오인** | 투과 디버깅 중에는 **contact damping 제거**(원인 은폐 방지) |
| `KINEMATICCOUPLING ... NOT AVAILABLE IN Abaqus/Explicit` | `*KINEMATIC COUPLING`은 **Standard 전용** | Explicit은 `*COUPLING`(노드기반 표면)+`*KINEMATIC` |

> **오류 진단의 왕도**: 실행이 막히면 **`job.dat`의 `***ERROR` 줄**을
> 먼저 보세요. 정확한 원인과 줄이 거기 있습니다. (위 표의 SURFACE
> INTERACTION 오류도 `.dat`가 정확히 짚어줬습니다.)

---

## 8. 서브루틴(VUMAT) 작성·디버깅을 Claude에게 시키기

### 8.1 VUMAT 기본 규칙 (Claude가 지켜야 할 것)
- **고정형식 `.f`** (7열부터 코드, 6열 연속행), `include 'vaba_param.inc'`.
- 응력은 **동회전(co-rotational) 좌표계**로 반환 → 등방성은 신축텐서 `U`로
  `B=U·U` 계산이 편함.
- 상태변수: `*DEPVAR, DELETE=n` 으로 요소 삭제 변수 지정(예: STATEV(1)).
- 실행은 `user=xxx.f double=both`.

### 8.2 Claude 활용 팁
- **작성**: "축대칭/3D VUMAT로 Neo-Hookean+주신축비 손상 삭제 구현해줘.
  PROPS는 C10,D1,lam_d,lam_f." 처럼 **물성식·상태변수·삭제기준을 명시**.
- **디버깅**: 컴파일 오류가 나면 `ref04.log`의 ifort 메시지를 Claude에게
  그대로 주고 "이 줄 고쳐줘"라고 하면 됩니다.
- **검증**: "단일요소 단축인장으로 손상 끄고 Neo-Hookean 해석해랑 응력
  비교해줘"처럼 **검증 케이스**를 시키면 신뢰도가 올라갑니다.

---

## 9. 부록

### 9.1 명령어 치트시트
```bat
REM 환경/검증
abaqus info=system
abaqus verify -user_explicit
abaqus licensing ru

REM 실행 (서브루틴 없음 / 있음)
abaqus job=buck03 input=03_needle_buckling.inp interactive
abaqus job=ref04  input=04_refined_path.inp user=vumat_skin.f double=both cpus=4 interactive

REM 후처리
abaqus python postprocess.py ref04.odb
```
```powershell
REM Claude 로컬 세션
cd "C:\경로\프로젝트"
claude
```

### 9.2 결과 파일 빠른 안내
| 확장자 | 무엇 | 언제 보나 |
|---|---|---|
| `.log` | 컴파일/실행 로그 | 서브루틴 컴파일 성공여부 |
| `.dat` | 입력검증·결과 | **`***ERROR` 진단**, 좌굴 고유값 |
| `.sta` | 증분·에너지 진행 | 완료여부·준정적성·질량변화 |
| `.msg` | 경고/에러 상세 | 접촉·수렴·삭제 경고 |
| `.odb` | 결과 데이터베이스 | 후처리/시각화 |

### 9.3 더 읽을거리 (이 저장소 안)
- `README.md` — 물리 모델·구성식·전체 모델 설명
- `BUILD_AND_RUN.md` — Windows/Linux 빌드·실행 상세
- `ANALYSIS_PLAN.md` — 문헌 기반 해석 방안
- `03_needle_buckling.inp` / `04_refined_path.inp` — 실행용 입력파일

---

## 부록 A. VUMAT ↔ Abaqus 프로세스 마인드맵

포트란 사용자 서브루틴(VUMAT)이 Abaqus/Explicit 풀이 과정에 어떻게
참여하는지를 한눈에 정리한 그림입니다. 입력 준비 → 컴파일·링크 →
초기화 → **증분 루프(응력 계산)** → **손상·요소삭제(관통)** →
안정성·시간 → 출력·후처리의 흐름을 보여줍니다.

@@SVG:mindmap_vumat.html@@

> 핵심은 **④ 증분 루프 ↔ ⑤ 손상·요소삭제**입니다. Abaqus는 매 증분마다
> 각 요소블록의 변형정보를 VUMAT에 넘기고, VUMAT은 동회전 좌표계에서
> 응력을 계산해 돌려줍니다. 손상변수가 임계에 도달하면 `STATEV(1)=0` →
> `*DEPVAR, DELETE=1` 이 요소를 삭제해 관통(절개)이 진행되고, 전역 접촉이
> 새로 노출된 표면을 인식합니다.

---

### 부탁 / 피드백
이 매뉴얼대로 따라 하다 막히는 지점이 있으면, **그 화면(캡처)과
`job.dat`/`.log`/`.sta`** 를 로컬 Claude에게 그대로 주면서 물어보세요.
대부분 원인이 로그에 그대로 적혀 있습니다.
