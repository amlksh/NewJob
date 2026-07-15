# Abaqus × Claude 자동화 플랫폼 — 기능 검토 및 제안서

> **비전**: 사용자가 **프로젝트명**과 **Claude 환경(챗봇 / 협업 / 코드)** 을
> 고르면, Abaqus–서브루틴 연계 해석·자동화·**보고서 자동생성**이 바로
> 가능한 작업공간이 만들어지고, **GitHub·PowerShell·툴 업데이트 등 환경
> 셋업까지 배치파일 한 번**으로 끝나는 시스템.

이 문서는 그 시스템을 만들기 위해 **추가로 필요한 기능**을 검토·제안합니다.
우선순위: **P0**(최소기능·필수) / **P1**(핵심 확장) / **P2**(고도화).

---

## 1. 사용자 플로우 (목표 경험)

```
[실행] setup.bat
   │
   ├─ (대화형) 프로젝트명 입력  ─────────────┐
   ├─ (대화형) Claude 환경 선택               │  chatbot / collab / code
   │                                          │
   ├─ 1) 환경 점검·자동설치 (Git/PS7/Claude/Python/WT)
   ├─ 2) GitHub 연결 (repo 생성·인증)
   ├─ 3) Abaqus·컴파일러 연동 검증
   ├─ 4) 프로젝트 스캐폴딩 (폴더·템플릿·CLAUDE.md)
   ├─ 5) Claude 환경 프로파일 적용 (권한/훅/MCP)
   └─ 6) 셀프체크 리포트 (무엇이 OK/누락)
   ▼
[준비완료] → 해석 실행·자동화·보고서 생성 사용
```

---

## 2. 추가 제안 기능 (카테고리별)

### A. 원클릭 환경 부트스트랩 (배치/PowerShell)
| # | 기능 | 우선 |
|---|------|:--:|
| A1 | **사전점검**: OS 버전·관리자권한·디스크·네트워크 정책 확인 | P0 |
| A2 | **툴 자동설치**(winget): Git, **PowerShell 7**, Windows Terminal, Python, Claude Code CLI | P0 |
| A3 | **PATH 자동등록**(`.local\bin` 등) + 터미널 VT 활성화 | P0 |
| A4 | **멱등성**: 여러 번 실행해도 안전(이미 있으면 스킵) | P0 |
| A5 | **로그 + 실패 롤백/재시도**(지수 백오프), `--dry-run` 모드 | P1 |
| A6 | **버전 업데이트 모드**: 설치된 툴 최신화(`winget upgrade`, `pip`, `gh`) | P1 |
| A7 | **환경 드리프트 감지**: Abaqus 재설치로 컴파일러 주입이 사라졌는지 등 점검·재적용 | P2 |

### B. GitHub 연동
| # | 기능 | 우선 |
|---|------|:--:|
| B1 | Git 전역 config(user, credential manager, `core.longpaths`, autocrlf) | P0 |
| B2 | **인증**: `gh auth login` 또는 SSH 키 생성·등록 | P0 |
| B3 | 프로젝트 **repo 자동 생성**·초기 push, 브랜치 전략 세팅 | P1 |
| B4 | **PR 템플릿·CODEOWNERS·라벨** 배치 | P1 |
| B5 | **GitHub Actions CI**: inp 린트/스모크 잡(가능하면 셀프호스트 러너로 실제 해석) | P2 |

### C. Claude 환경 프로파일 (챗봇/협업/코드)
| # | 기능 | 우선 |
|---|------|:--:|
| C1 | **code 모드**: `settings.json`(권한 allowlist: `abaqus*`,`python*`,`git*`), 훅, MCP(github) 연결 | P0 |
| C2 | **collab 모드**: PR 리뷰 훅, CI 연동, 팀 규칙(CLAUDE.md), 리뷰 체크리스트 | P1 |
| C3 | **chatbot 모드**: 프로젝트 문서/이론/매뉴얼을 지식베이스로 묶어 Q&A(로컬 문서 인덱스) | P1 |
| C4 | 모드별 **자동승인 세트**(반복 안전명령) → 승인 피로 감소 | P0 |
| C5 | **hooks**: 커밋 전 inp 린트, 잡 완료 시 알림/리포트 자동생성 | P1 |

### D. Abaqus–서브루틴 연계·자동화
| # | 기능 | 우선 |
|---|------|:--:|
| D1 | **잡 실행 래퍼**: `verify` → 컴파일 → 실행 → 상태폴링(.sta) → 완료판정 → 요약 | P0 |
| D2 | **에러 자동진단**: `.dat`/`.msg` 파싱 → 알려진 오류 패턴 매칭 → 수정 제안 (예: *SURFACE INTERACTION 위치, double=both 누락) | P0 |
| D3 | **라이선스 인지 스케줄러**: `licensing ru` 확인 후 토큰 가능할 때 실행/대기 | P1 |
| D4 | **파라메트릭/DOE**: 물성·형상·메쉬 스윕 일반화(현 `convergence_study` 확장) | P1 |
| D5 | **배치 큐**: 다중 잡 순차/병렬, 실패 격리, 재시작(restart) | P1 |
| D6 | **서브루틴 스켈레톤 생성기**: VUMAT/UMAT/UMATHT/DFLUX/VDLOAD 템플릿 + 단위계·상태변수 | P1 |
| D7 | **열-구조 등 다물리 연계** 템플릿(예: UMATHT+VUMAT) | P2 |

### E. 보고서 자동화
| # | 기능 | 우선 |
|---|------|:--:|
| E1 | 결과 수집→표·그래프→**템플릿 리포트**(HTML/PDF) 자동 생성(현 `postprocess`+`md2html` 확장) | P0 |
| E2 | **이미지 자동추출** 일반화(현 `odb_snapshot`: 임의 변수/뷰/스텝/애니메이션 GIF) | P0 |
| E3 | **리포트 템플릿**: 표지·요약·물성·메쉬·결과·검증·결론 + 로고/작성자/버전 | P1 |
| E4 | **비교 리포트**(케이스 A vs B, 수렴성, 실험 대조) | P1 |
| E5 | PPTX/DOCX 출력, 다이어그램/마인드맵 자동첨부(현 `gen_mindmap`) | P2 |

### F. 품질·검증·거버넌스
| # | 기능 | 우선 |
|---|------|:--:|
| F1 | **입력파일 린터**: 우리가 겪은 규칙(*SURFACE INTERACTION 모델데이터, DEPVAR/DELETE, double=both)을 사전 점검 | P0 |
| F2 | **서브루틴 단위테스트**: 단일요소 vs 해석해 자동 비교 | P1 |
| F3 | **회귀테스트**: 골든 결과 저장·diff(물성/버전 바뀌어도 안전) | P1 |
| F4 | **준정적성/에너지 밸런스 게이트**(현 postprocess의 ALLKE/ALLIE 판정을 합격/불합격 기준으로) | P1 |

### G. 안전·신뢰성 (배치 개발 필수 원칙)
- **관리자권한 필요 항목 분리**(자동설치 vs 안내), 실패해도 이어가기
- **비밀정보 안전저장**: 토큰은 Windows Credential Manager/`gh` 사용(평문 금지)
- **네트워크 정책 인지**: 사내 프록시/오프라인 환경에서의 대체 경로
- **모든 단계 로깅** + 최종 **셀프체크 표**(OK/누락/조치)

---

## 3. 제안 배치 아키텍처 (모듈식)

```
setup.bat                     ← 진입점(관리자 권한 요청, PS7 없으면 5.1로 부트스트랩)
 └ bootstrap.ps1 -Project <name> -Mode <code|collab|chatbot> [-Update] [-DryRun]
     ├ 00_preflight.ps1       OS·권한·디스크·네트워크
     ├ 10_tools.ps1           winget: git, pwsh7, terminal, python, claude
     ├ 20_git_github.ps1      git config, gh auth, repo 생성/연결
     ├ 30_claude_profile.ps1  settings.json/훅/MCP/권한 (모드별)
     ├ 40_abaqus_verify.ps1   info=system, verify -user_*, licensing ru
     ├ 50_scaffold.ps1        프로젝트 폴더·템플릿·CLAUDE.md·.gitignore
     └ 90_selfcheck.ps1       최종 점검 리포트(HTML)
```
**설계 원칙**: 각 모듈 **멱등**, 실패 시 **명확한 메시지+건너뛰기**, 전 과정
로그(`setup_YYYYMMDD.log`), `-DryRun`으로 미리보기, `-Update`로 유지보수.

---

## 4. 자동화가 "안 되는/조심할" 항목 (정직한 한계)

| 항목 | 이유 | 대안 |
|------|------|------|
| **Intel oneAPI + Visual Studio 설치** | 대용량·라이선스·관리자, 무인설치 취약 | **탐지 + 설치 안내**(자동설치는 옵션) |
| **Abaqus 본체·라이선스 서버** | 사내 배포·라이선스 정책 | **탐지·검증만**, 없으면 담당자 안내 |
| **Claude 로그인** | 브라우저 대화형 인증 | 배치는 여기서 잠깐 멈춰 안내 |
| **컴파일러 드라이버 주입 복원** | 사이트별 상이 | 드리프트 감지 후 **재적용 스크립트 제공** |

> 즉 배치는 "**되는 건 자동, 안 되는 건 정확히 탐지·안내**"가 원칙입니다.

---

## 5. 단계별 로드맵

- **Phase 1 (P0, 1차 목표)** — `setup.bat` + `bootstrap.ps1`(A1~A4, B1~B2, C1/C4,
  D1~D2, E1~E2, F1) + 프로젝트 스캐폴딩. **"원클릭 셋업→해석→기본 리포트"** 완성.
- **Phase 2 (P1)** — GitHub repo/CI, 파라메트릭/DOE, 배치 큐, 리포트 템플릿,
  단위/회귀 테스트, chatbot·collab 모드.
- **Phase 3 (P2)** — 다물리 연계, PPTX/DOCX, Actions 셀프호스트 실제 해석,
  드리프트 자동복원, 최적화 루프.

---

## 6. 이미 만든 자산 재사용 (바로 편입 가능)

| 기존 산출물 | 플랫폼에서의 역할 |
|-------------|-------------------|
| `postprocess.py` | E1 리포트 코어(힘-깊이·준정적성·삭제) |
| `odb_snapshot.py` | E2 이미지 자동추출 |
| `gen_mindmap.py`·`md2html.py` | E5 다이어그램·HTML 리포트 |
| `convergence_study.py` | D4 파라메트릭 스터디 |
| `BUILD_AND_RUN.md`·`USER_MANUAL` | C3 챗봇 지식베이스 |
| VUMAT `.f`들(Neo-Hooke/HGO/**Ogden**/**cohesive**) | D6 서브루틴 템플릿 라이브러리 |
| **모델 17**(Ogden 순수삭제)·**15**(cohesive+damage) | D 검증된 관통 해석 레퍼런스 |
| (경험) *SURFACE INTERACTION 오류 | F1 린터 규칙 R1 |
| (경험) *KINEMATIC COUPLING@Explicit | F1 린터 규칙 R5 |
| **(경험) 침식접촉 실패 5종**(단위·내부면·삭제국소화·stabilization·해석적강체) | **F1 린터/체크리스트 규칙**(관통 해석 성공요인) |

---

## 7. 권고

**Phase 1의 `setup.bat` + `bootstrap.ps1`(멱등·로그·셀프체크)** 부터 만드는 것을
권합니다. 실제로 이번 세션에서 겪은 **PATH·터미널·라이선스·입력파일 오류**가
그대로 자동점검 항목이 되므로, 초기 버전만으로도 온보딩 시간이 크게 줄어듭니다.

> 다음 단계로 어떤 걸 만들지 알려주시면 (예: **P0 부트스트랩 배치 초안**,
> **입력파일 린터**, **리포트 템플릿 엔진**) 바로 구현에 들어가겠습니다.
