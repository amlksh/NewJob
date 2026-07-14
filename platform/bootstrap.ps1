# ======================================================================
#  bootstrap.ps1 — Abaqus x Claude 환경 셋업 오케스트레이터
#
#  setup.bat 이 호출. 멱등(여러 번 실행해도 안전) · 전 단계 로그 ·
#  -DryRun 미리보기 · -Update 최신화 · 최종 셀프체크 HTML 리포트.
#
#  주의: Abaqus/Intel oneAPI/VS 는 대용량·라이선스라 "탐지·검증"만 하고,
#        없으면 담당자에게 안내합니다(자동설치하지 않음).
# ======================================================================
param(
  [string]$Project = "",
  [ValidateSet("code", "collab", "chatbot", "")]
  [string]$Mode = "",
  [string]$Root = "$env:USERPROFILE\ClaudeAbaqus",
  [string]$GitHubUser = "",
  [switch]$DryRun,
  [switch]$Update,
  [switch]$SkipTools
)

$ErrorActionPreference = "Continue"
$script:Results = @()
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $PSScriptRoot "setup_$stamp.log"

function Log($msg, $level = "INFO") {
  $line = "[{0}] {1} {2}" -f (Get-Date -Format "HH:mm:ss"), $level, $msg
  $color = @{ INFO = "Gray"; STEP = "Cyan"; OK = "Green"; WARN = "Yellow"; ERR = "Red" }[$level]
  if (-not $color) { $color = "Gray" }
  Write-Host $line -ForegroundColor $color
  Add-Content -Path $LogFile -Value $line
}
function Rec($name, $status, $detail = "") {
  $script:Results += [pscustomobject]@{ Name = $name; Status = $status; Detail = $detail }
  $lvl = @{ OK = "OK"; WARN = "WARN"; FAIL = "ERR"; SKIP = "WARN" }[$status]
  if (-not $lvl) { $lvl = "INFO" }
  Log ("{0} : {1} {2}" -f $name, $status, $detail) $lvl
}
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Act($desc, [scriptblock]$sb) {
  if ($DryRun) { Log "[DRY-RUN] $desc" "WARN"; return $true }
  Log $desc
  try { & $sb; return $true } catch { Log "실패: $($_.Exception.Message)" "ERR"; return $false }
}

# ---------- 대화형 입력 ----------
if (-not $Project) { $Project = Read-Host "프로젝트명 (예: microneedle)" }
if (-not $Project) { $Project = "AbaqusProject" }
if (-not $Mode) {
  Write-Host "Claude 환경 모드: [1] code  [2] collab  [3] chatbot"
  $m = Read-Host "선택 (1/2/3, 기본 1)"
  $Mode = @{ "1" = "code"; "2" = "collab"; "3" = "chatbot" }[$m]
  if (-not $Mode) { $Mode = "code" }
}
Log "프로젝트=$Project  모드=$Mode  Root=$Root  DryRun=$DryRun  Update=$Update" "STEP"

# ================= 00 사전점검 =================
Log "== 00 사전점검 ==" "STEP"
Rec "OS" "OK" ([System.Environment]::OSVersion.VersionString)
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Rec "관리자권한" $(if ($admin) { "OK" } else { "WARN" }) $(if ($admin) { "" } else { "일부 설치는 관리자 필요" })
try {
  $drive = (Get-Item $env:USERPROFILE).PSDrive
  $freeGB = [math]::Round($drive.Free / 1GB, 1)
  Rec "디스크여유" $(if ($freeGB -gt 5) { "OK" } else { "WARN" }) "$freeGB GB"
} catch { Rec "디스크여유" "WARN" "확인불가" }

# ================= 10 툴 설치/최신화 =================
if (-not $SkipTools) {
  Log "== 10 툴 설치 ==" "STEP"
  function Ensure-Tool($id, $cmd, $label) {
    if ((Have $cmd) -and (-not $Update)) { Rec $label "OK" "이미 설치됨"; return }
    if (-not (Have winget)) { Rec $label "SKIP" "winget 없음 → 수동설치 필요"; return }
    $verb = if ($Update) { "upgrade" } else { "install" }
    $ok = Act "winget $verb $id" { winget $verb --id $id -e --accept-source-agreements --accept-package-agreements | Out-Null }
    Rec $label $(if ($ok) { "OK" } else { "FAIL" }) "winget $verb"
  }
  Ensure-Tool "Git.Git" "git" "Git"
  Ensure-Tool "Microsoft.PowerShell" "pwsh" "PowerShell 7"
  Ensure-Tool "Microsoft.WindowsTerminal" "wt" "Windows Terminal"
  Ensure-Tool "Python.Python.3.12" "python" "Python"
  # Claude Code: winget 우선, 실패 시 공식 설치 스크립트
  if ((Have claude) -and (-not $Update)) {
    Rec "Claude Code" "OK" "이미 설치됨"
  } else {
    $ok = Act "Claude Code 설치" { irm https://claude.ai/install.ps1 | iex }
    Rec "Claude Code" $(if ($ok) { "OK" } else { "FAIL" }) ""
  }
} else { Log "툴 설치 건너뜀(-SkipTools)" "WARN" }

# ================= PATH 등록 =================
$localbin = Join-Path $env:USERPROFILE ".local\bin"
if (Test-Path $localbin) {
  $userpath = [Environment]::GetEnvironmentVariable("Path", "User")
  if ($userpath -notlike "*$localbin*") {
    Act "PATH에 $localbin 추가" {
      [Environment]::SetEnvironmentVariable("Path", "$userpath;$localbin", "User")
    } | Out-Null
    Rec "PATH(.local\bin)" "OK" "추가됨(새 터미널부터 적용)"
  } else { Rec "PATH(.local\bin)" "OK" "이미 등록" }
  $env:Path = "$env:Path;$localbin"
}

# ================= 20 Git / GitHub =================
Log "== 20 Git/GitHub ==" "STEP"
if (Have git) {
  Act "Git 전역 설정" {
    git config --global core.longpaths true | Out-Null
    git config --global core.autocrlf true | Out-Null
    git config --global init.defaultBranch main | Out-Null
  } | Out-Null
  $uname = git config --global user.name
  if (-not $uname) { Rec "Git user.name" "WARN" "미설정 → git config --global user.name '이름'" }
  else { Rec "Git user.name" "OK" $uname }
  Rec "Git" "OK" (git --version)
} else { Rec "Git" "FAIL" "git 없음" }

if (Have gh) {
  gh auth status 2>$null
  Rec "GitHub 인증(gh)" $(if ($LASTEXITCODE -eq 0) { "OK" } else { "WARN" }) $(if ($LASTEXITCODE -eq 0) { "" } else { "gh auth login 필요" })
} else { Rec "GitHub CLI(gh)" "SKIP" "선택 설치(gh) 권장" }

# ================= 40 Abaqus 연동 검증 =================
Log "== 40 Abaqus 검증 ==" "STEP"
if (Have abaqus) {
  Rec "abaqus 명령" "OK" ""
  if (-not $DryRun) {
    try {
      $vs = (abaqus verify -user_explicit 2>&1 | Out-String)
      $pass = $vs -match "PASS"
      Rec "verify -user_explicit" $(if ($pass) { "OK" } else { "WARN" }) $(if ($pass) { "PASS" } else { "출력 확인 필요" })
    } catch { Rec "verify -user_explicit" "WARN" "실행 실패" }
    try {
      $lic = (abaqus licensing ru 2>&1 | Out-String)
      $hasExp = $lic -match "Explicit"
      Rec "Explicit 라이선스" $(if ($hasExp) { "OK" } else { "WARN" }) $(if ($hasExp) { "토큰 확인됨" } else { "Explicit 토큰 확인 필요" })
    } catch { Rec "라이선스" "WARN" "확인불가" }
  } else { Rec "Abaqus 검증" "SKIP" "DryRun" }
} else { Rec "abaqus 명령" "WARN" "PATH에 abaqus 없음 → Abaqus 설치/환경 확인" }

# ================= 50 프로젝트 스캐폴딩 =================
Log "== 50 프로젝트 스캐폴딩 ==" "STEP"
$proj = Join-Path $Root $Project
$tpl = Join-Path $PSScriptRoot "templates"
foreach ($d in @("inp", "subroutines", "scripts", "results", "reports", "docs", ".claude")) {
  $p = Join-Path $proj $d
  if (-not (Test-Path $p)) { Act "폴더 생성 $d" { New-Item -ItemType Directory -Force -Path $p | Out-Null } | Out-Null }
}
function Copy-Tpl($src, $dst, $replace = $true) {
  if (Test-Path $dst) { return }
  if (-not (Test-Path $src)) { return }
  if ($DryRun) { Log "[DRY-RUN] 템플릿 $dst"; return }
  $c = Get-Content -Raw $src
  if ($replace) { $c = $c -replace "\{\{PROJECT\}\}", $Project }
  Set-Content -Path $dst -Value $c -Encoding UTF8
}
Copy-Tpl (Join-Path $tpl "CLAUDE.md.tmpl") (Join-Path $proj "CLAUDE.md")
Copy-Tpl (Join-Path $tpl "gitignore.tmpl") (Join-Path $proj ".gitignore") $false
Copy-Tpl (Join-Path $tpl "vumat_skeleton.f") (Join-Path $proj "subroutines\vumat_skeleton.f") $false
Copy-Tpl (Join-Path $tpl "settings.$Mode.json") (Join-Path $proj ".claude\settings.json") $false
# 재사용 파이썬 도구 복사
foreach ($f in @("inp_lint.py", "report.py", "postprocess.py", "odb_snapshot.py", "md2html.py")) {
  $s = Join-Path $PSScriptRoot $f
  if (Test-Path $s) { Copy-Tpl $s (Join-Path $proj "scripts\$f") $false }
}
if (-not (Test-Path (Join-Path $proj "README.md"))) {
  Copy-Tpl (Join-Path $tpl "CLAUDE.md.tmpl") (Join-Path $proj "README.md")
}
Rec "스캐폴딩" "OK" $proj

# git init
if ((Have git) -and (-not (Test-Path (Join-Path $proj ".git")))) {
  Act "git init + 첫 커밋" {
    Push-Location $proj
    git init | Out-Null
    git add -A | Out-Null
    git commit -m "chore: scaffold $Project ($Mode) via bootstrap" | Out-Null
    Pop-Location
  } | Out-Null
  Rec "git init" "OK" ""
}

# ================= 90 셀프체크 리포트 =================
Log "== 90 셀프체크 ==" "STEP"
$rows = ""
foreach ($r in $script:Results) {
  $badge = @{ OK = "#16a34a"; WARN = "#d97706"; FAIL = "#dc2626"; SKIP = "#64748b" }[$r.Status]
  if (-not $badge) { $badge = "#64748b" }
  $rows += "<tr><td>$($r.Name)</td><td style='color:#fff;background:$badge;text-align:center;border-radius:4px'>$($r.Status)</td><td>$($r.Detail)</td></tr>"
}
$nfail = ($script:Results | Where-Object { $_.Status -eq "FAIL" }).Count
$nwarn = ($script:Results | Where-Object { $_.Status -in @("WARN", "SKIP") }).Count
$html = @"
<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>셋업 셀프체크 - $Project</title>
<style>body{font-family:Segoe UI,Malgun Gothic,sans-serif;max-width:820px;margin:24px auto;padding:0 16px}
h1{border-bottom:3px solid #2b6cb0;padding-bottom:8px}table{border-collapse:collapse;width:100%}
td{border:1px solid #e2e8f0;padding:8px 10px}th{background:#eef3fa;border:1px solid #e2e8f0;padding:8px}
.sum{padding:10px 14px;border-radius:8px;margin:12px 0;font-weight:600}</style></head><body>
<h1>셋업 셀프체크 — $Project ($Mode)</h1>
<div class="sum" style="background:$(if($nfail){'#fdeaea'}else{'#e9f9ee'})">
FAIL $nfail · WARN/SKIP $nwarn · $(Get-Date -Format 'yyyy-MM-dd HH:mm')</div>
<table><tr><th>항목</th><th>상태</th><th>상세</th></tr>$rows</table>
<p style="color:#555;font-size:14px">로그: $LogFile</p></body></html>
"@
$repDir = Join-Path $proj "reports"
if (-not (Test-Path $repDir)) { New-Item -ItemType Directory -Force -Path $repDir | Out-Null }
$repPath = Join-Path $repDir "setup_selfcheck.html"
if (-not $DryRun) { Set-Content -Path $repPath -Value $html -Encoding UTF8 }
Log "셀프체크 리포트: $repPath" "OK"

Write-Host ""
Log "완료. FAIL=$nfail WARN/SKIP=$nwarn  →  $repPath" $(if ($nfail) { "ERR" } else { "OK" })
if (-not $DryRun -and (Test-Path $repPath)) { Start-Process $repPath }
exit $(if ($nfail) { 1 } else { 0 })
