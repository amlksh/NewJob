@echo off
REM ======================================================================
REM  setup.bat  —  Abaqus x Claude 작업환경 원클릭 셋업 진입점 (Windows)
REM
REM  사용:
REM    setup.bat                         (대화형: 프로젝트명/모드 물어봄)
REM    setup.bat MyProject code          (프로젝트명, 모드 지정)
REM    setup.bat MyProject code -DryRun  (미리보기, 실제 변경 없음)
REM    setup.bat -Update                 (설치된 툴 최신화)
REM
REM  하는 일: 툴 설치(Git/PowerShell7/Claude/Python/Terminal) → PATH →
REM           Git/GitHub → Abaqus 연동검증 → 프로젝트 스캐폴딩 →
REM           Claude 프로파일 → 셀프체크 리포트
REM ======================================================================
setlocal
set "HERE=%~dp0"

REM PowerShell 7(pwsh)이 있으면 우선, 없으면 Windows PowerShell로
where pwsh >nul 2>nul
if %errorlevel%==0 (
  set "PS=pwsh"
) else (
  set "PS=powershell"
)

echo.
echo === Abaqus x Claude 셋업 시작 (%PS%) ===
echo.

%PS% -NoProfile -ExecutionPolicy Bypass -File "%HERE%bootstrap.ps1" %*

echo.
echo === 종료코드 %errorlevel% ===
endlocal
