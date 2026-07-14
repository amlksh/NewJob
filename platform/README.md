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

## 1) 원클릭 셋업

```bat
REM 대화형 (프로젝트명·모드 물어봄)
setup.bat

REM 인자 지정 (모드: code | collab | chatbot)
setup.bat microneedle code

REM 미리보기(변경 없음) / 툴 최신화
setup.bat microneedle code -DryRun
setup.bat -Update
```
하는 일(멱등·로그·롤백):
1. **사전점검** OS·권한·디스크
2. **툴 설치**(winget): Git·PowerShell7·Windows Terminal·Python·Claude Code
3. **PATH** `.local\bin` 등록
4. **Git/GitHub** 전역설정·`gh` 인증 확인
5. **Abaqus 검증** `verify -user_explicit`·라이선스 토큰
6. **프로젝트 스캐폴딩** 폴더·CLAUDE.md·.gitignore·서브루틴 템플릿·`.claude/settings.json`·도구 복사·git init
7. **셀프체크 리포트**(HTML) 자동 생성·열기

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

---

### 검증 상태
- `inp_lint.py`·`report.py` 는 이 저장소에서 실제 테스트 완료(정상/오류 검출,
  보고서 렌더링 확인).
- `bootstrap.ps1`·`setup.bat` 는 **Windows에서 실행 검증 필요**(작성 환경에
  PowerShell/winget 부재). 첫 실행은 `-DryRun` 으로 미리보기 권장.
