# Abaqus × Claude 플랫폼 (Phase 1)

프로젝트명·Claude 환경을 고르면 **원클릭으로 작업환경을 셋업**하고,
Abaqus 서브루틴 해석의 **린트 → 실행 → 보고서**를 자동화하는 툴킷입니다.
(설계 배경: `../microneedle_abaqus/AUTOMATION_PLATFORM_PROPOSAL.md`)

## 구성

| 파일 | 역할 |
|------|------|
| `setup.bat` | 진입점(Windows). 대화형/인자 실행 |
| `bootstrap.ps1` | 오케스트레이터 — 툴설치·PATH·Git/GitHub·Abaqus검증·스캐폴딩·셀프체크 |
| `templates/` | CLAUDE.md·gitignore·VUMAT 스켈레톤·모드별 settings.json |
| `inp_lint.py` | **입력파일 린터** (실행 전 오류 사전 검출) |
| `report.py` | **보고서 엔진** (결과→표·SVG그래프·이미지 임베드 HTML) |
| `postprocess.py`·`odb_snapshot.py`·`md2html.py`·`gen_mindmap.py` | 후처리·이미지·문서 도구 |
| **`run_job.py`** | 잡 오케스트레이터 — 린트→실행→상태확인→진단→후처리→보고서 (Phase 2) |
| **`diagnose.py`** | 실패 로그(.dat/.msg/.log) 자동진단 (Phase 2) |
| **`doe.py`** | 파라메트릭 스터디 생성 + 케이스 비교 리포트 (Phase 2) |
| **`gen_subroutine.py`** | 서브루틴 스켈레톤 생성기(VUMAT/UMAT/UMATHT/VDLOAD/DFLUX) (Phase 2) |
| `tests/selftest.py` · `.github/workflows/ci.yml` | 자기검증 + GitHub Actions CI (Phase 2) |
| **`regression.py`** | 회귀 테스트 — 골든 기준선 대비 결과 diff (Phase 3) |
| **`optimize.py`** | 1D 자동 최적화 — 목표 지표에 파라미터 이분탐색 (Phase 3) |
| **`md2docx.py`** | Markdown→Word(.docx) 변환(라이브러리 없이 OOXML) (Phase 3) |
| **`gh_repo.ps1`** | GitHub 저장소 자동생성·push (Phase 3) |
| `templates/coupled_thermal_struct.inp` | 다물리(열-구조) 연계 스켈레톤 (Phase 3) |

## 1) 원클릭 셋업

```bat
REM 대화형 (프로젝트명·모드 물어봄)
setup.bat

REM 인자 지정 (모드: code | collab | chatbot)
setup.bat microneedle code

REM 미리보기(변경 없음) / 툴 최신화
setup.bat microneedle code -DryRun
setup.bat -Update

REM GitHub 저장소 자동생성·push (gh 인증 필요)
setup.bat microneedle code -GitHub owner/microneedle

REM 스캐폴딩 되돌리기(undo)
setup.bat microneedle -Rollback
```
> **재시도·롤백**: winget/Claude 설치·git push 등 네트워크 작업은 실패 시
> 지수 백오프(2/4/8/16s)로 최대 4회 재시도. 스캐폴딩 중 오류가 나면
> **새로 만든 프로젝트 폴더를 자동 롤백**(기존 폴더는 보존).
하는 일(멱등·로그·롤백):
1. **사전점검** OS·권한·디스크
2. **툴 설치**(winget): Git·PowerShell7·Windows Terminal·Python·Claude Code
3. **PATH** `.local\bin` 등록
4. **Git/GitHub** 전역설정·`gh` 인증 확인
5. **Abaqus 검증** `verify -user_explicit`·라이선스 토큰
6. **프로젝트 스캐폴딩** 폴더·CLAUDE.md·.gitignore·서브루틴 템플릿·`.claude/settings.json`·도구 복사·git init (실패 시 자동 롤백)
7. **(옵션) GitHub 저장소** `-GitHub owner/name` 이면 repo 생성·push
8. **셀프체크 리포트**(HTML) 자동 생성·열기

> Abaqus·Intel oneAPI·Visual Studio는 대용량·라이선스라 **탐지·검증만** 하고,
> 없으면 안내합니다(자동설치 안 함). Claude 로그인은 브라우저 대화형.

## 2) 입력파일 린트 (실행 전)

```bat
python inp_lint.py inp\model.inp
```
검출 예: `*SURFACE INTERACTION`이 `*STEP` 뒤에 있음(모델데이터 위치 오류),
`*CONTACT PROPERTY ASSIGNMENT`가 미정의 상호작용 참조, `*DEPVAR DELETE` 인덱스
초과, STEP/END STEP 불일치, `double=both`/Explicit 라이선스 리마인더.
ERROR가 있으면 종료코드 1.

## 3) 결과 보고서 자동 생성

```bat
REM 1) 해석 후처리 (관통력-깊이·준정적성·삭제요소)
abaqus python postprocess.py results\ref04.odb

REM 2) 이미지 추출
abaqus viewer noGUI=odb_snapshot.py -- results\ref04.odb

REM 3) 보고서(표지·요약·그래프·이미지·판정)
python report.py --job ref04 --dir results --project "마이크로니들 관통" \
                 --author "홍길동" --date 2026-07-14 --pcr 0.219
REM -> results\ref04_report.html
```
`--pcr`(좌굴하중)를 주면 **삽입 성공/실패 판정**(F_ins vs P_cr)까지 리포트에
표시됩니다.

## Claude 환경 모드

| 모드 | 권한 프로파일 | 용도 |
|------|--------------|------|
| `code` | abaqus/python/git/편집 허용 | 실해석·자동화 개발 |
| `collab` | code + `gh pr/issue`, force-push 차단 | 팀·PR 협업 |
| `chatbot` | 읽기 위주(쓰기·실행 차단) | 문서 Q&A·조회 |

`.claude/settings.json`으로 적용되어 반복 안전명령의 승인 피로를 줄입니다.

## 4) 엔드투엔드 오케스트레이터 (Phase 2)

한 줄로 린트→실행→진단→후처리→보고서까지:
```bat
python run_job.py --job ref04 --input 04_refined_path.inp ^
       --user vumat_skin.f --project "마이크로니들" --pcr 0.219 --images
REM 옵션: --dry-run(미리보기) --no-run(기존 odb로 후처리만) --force(린트오류 무시)
```
- 린트에서 **ERROR면 실행 전 중단**(수정 유도).
- `.sta`가 완료 아니면 **`diagnose.py` 자동 호출**로 원인·조치 제시.
- 성공 시 `postprocess`·(이미지)·`report` 자동 실행 → `<job>_report.html`.

## 5) 실패 자동진단 (Phase 2)

```bat
python diagnose.py ref04        REM ref04.dat/.msg/.log/.sta 자동탐색
```
알려진 패턴(이 프로젝트에서 실제로 겪은 것 포함)을 원인·조치로 매핑:
SURFACE INTERACTION 위치 오류, 라이선스/토큰, 컴파일·링크 오류, 요소 과도
왜곡, 증분 수렴 실패 등.

## 6) 파라메트릭 스터디(DOE) + 비교 리포트 (Phase 2)

```bat
REM 템플릿 inp의 {{C10}} {{LAMF}} 자리에 그리드값 대입해 케이스 생성
python doe.py gen --template base.inp --grid grid.csv --prefix dh --user vumat_skin.f
run_doe.bat                                  REM 케이스 일괄 해석+후처리
python doe.py agg --grid grid.csv --prefix dh   REM -> doe_comparison.html (곡선 오버레이+peak표)
```
`grid.csv` 예: `case,C10,LAMF` / `soft,0.02,2.5` / `stiff,0.05,2.0`

## 7) 서브루틴 스켈레톤 생성 (Phase 2)

```bat
python gen_subroutine.py --type vumat --name mymat --out subroutines
REM 타입: vumat | umat | umatht | vdload | dflux
```

## 8) CI / 자기검증 (Phase 2)

- `.github/workflows/ci.yml`: push/PR마다 **Python 컴파일 + 자기검증 +
  전체 .inp 린트 게이트**(ERROR 있으면 CI 실패). GitHub 러너에서 실제 동작
  (Abaqus 불필요한 정적 점검).
- `python tests/selftest.py` 로 로컬에서도 검증 가능.

## 9) 회귀 테스트 (Phase 3)

물성/버전 변경 후에도 핵심 결과가 유지되는지 자동 확인:
```bat
python regression.py save  --key ref04 --from ref04_fd.csv --extra deleted=12
python regression.py check --key ref04 --from ref04_fd.csv --tol 0.05
```
peak 관통력·깊이 등을 `regression_baseline.json` 과 허용오차로 비교(초과 시 종료코드 1).

## 10) 자동 최적화 루프 (Phase 3)

목표 지표(예: peak 관통력)에 맞춰 파라미터를 이분탐색으로 자동 조정:
```bat
python optimize.py --template base.inp --param C10 --job opt ^
       --target 0.25 --lo 0.01 --hi 0.10 --user vumat_skin.f --maxit 8
```
매 반복마다 `{{C10}}` 값을 바꿔 해석→peak 추출→구간 갱신. (지표가 param에
단조라고 가정. 브래킷 안 되면 경고 후 근사값.)

## 11) Word(.docx) 리포트 (Phase 3)

```bat
python md2docx.py ref04_report_summary.md ref04.docx
```
`python-docx` 없이 유효한 OOXML .docx 생성(헤더·문단·굵게·표·목록).
그림 포함 보고서는 HTML(`report.py`)을 브라우저에서 PDF로 저장하세요.

## 12) GitHub 저장소 자동화 (Phase 3)

```powershell
pwsh -File gh_repo.ps1 -Repo owner/name -Path C:\...\project -Visibility private
```
`gh` 로 저장소 생성·연결·push. PR 템플릿은 `.github/pull_request_template.md`
(린트/셀프테스트/회귀 체크리스트 포함).

## 13) 다물리(열-구조) 연계 스켈레톤 (Phase 3)

`templates/coupled_thermal_struct.inp` — 온도-변위 커플드 + UMATHT(열) +
UMAT/VUMAT(구조) + 이동열원 DFLUX 구조의 시작 템플릿(fire-sim 계열).
서브루틴 스켈레톤은 `gen_subroutine.py --type umatht|dflux` 로 생성.

---

### 검증 상태
- **Python 도구 전부 실제 테스트 완료**: `inp_lint`(정상/오류), `diagnose`,
  `doe`(gen/agg), `report`(렌더링), `gen_subroutine`, `run_job`(dry-run),
  `regression`(save/check), `optimize`(mock 수렴), `md2docx`(유효 .docx),
  `tests/selftest.py`(**14/14 PASS**), 전체 .inp 린트 게이트 통과.
- `bootstrap.ps1`·`setup.bat` **-DryRun 실환경 검증 완료**
  (Windows PowerShell 5.1, 2026-07-15: 전 단계 정상 출력, exit 0, FAIL=0).
  실제 설치·스캐폴딩(비-DryRun)은 첫 실행 시 셀프체크 리포트로 확인 권장.
  ※ `.ps1` 은 UTF-8 **BOM** 유지 필수(5.1 한글 파싱).
