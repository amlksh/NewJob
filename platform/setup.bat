@echo off
chcp 65001 >nul
REM ======================================================================
REM  setup.bat  -  Abaqus x Claude one-click setup entry (Windows)
REM
REM  Usage:
REM    setup.bat                          (interactive: ask project / mode)
REM    setup.bat MyProject code           (project name, mode)
REM    setup.bat MyProject code -DryRun   (preview, no changes)
REM    setup.bat -Update                  (upgrade installed tools)
REM    setup.bat MyProject code -GitHub owner/name   (auto-create repo + push)
REM    setup.bat MyProject -Rollback      (undo scaffolded folder)
REM
REM  Features: retry (2/4/8/16s) on network ops, auto-rollback on scaffold fail.
REM  Note: bootstrap.ps1 must stay UTF-8 with BOM (Windows PowerShell 5.1).
REM ======================================================================
setlocal
set "HERE=%~dp0"

REM Prefer PowerShell 7 (pwsh) if present, else Windows PowerShell 5.1
where pwsh >nul 2>nul
if %errorlevel%==0 (
  set "PS=pwsh"
) else (
  set "PS=powershell"
)

echo.
echo === Abaqus x Claude setup ^(%PS%^) ===
echo.

%PS% -NoProfile -ExecutionPolicy Bypass -File "%HERE%bootstrap.ps1" %*

echo.
echo === exit code %errorlevel% ===
endlocal
