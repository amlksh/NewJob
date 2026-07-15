# ======================================================================
#  gh_repo.ps1 — GitHub 저장소 자동 생성·연결 (Phase 3)
#
#  프로젝트 폴더를 GitHub 저장소로 만들고 push 한다. gh CLI 필요.
#
#  사용:
#    pwsh -File gh_repo.ps1 -Repo owner/name -Path C:\...\project
#    옵션: -Visibility private|public   -Push:$false(생성만)
# ======================================================================
param(
  [Parameter(Mandatory)][string]$Repo,
  [string]$Path = ".",
  [ValidateSet("private", "public")][string]$Visibility = "private",
  [bool]$Push = $true
)

function Fail($m) { Write-Host "[ERR] $m" -ForegroundColor Red; exit 1 }

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  Fail "gh(GitHub CLI) 없음 → winget install GitHub.cli 후 gh auth login"
}
gh auth status 2>$null
if ($LASTEXITCODE -ne 0) { Fail "gh 인증 안됨 → gh auth login" }

Set-Location $Path
if (-not (Test-Path ".git")) {
  git init | Out-Null
  git add -A | Out-Null
  git commit -m "chore: initial commit" | Out-Null
}

# 원격 없으면 repo 생성(+push)
$hasRemote = (git remote) -contains "origin"
if (-not $hasRemote) {
  $src = if ($Push) { "--source=. --push" } else { "--source=." }
  Write-Host "gh repo create $Repo --$Visibility $src"
  Invoke-Expression "gh repo create $Repo --$Visibility $src --remote=origin"
  if ($LASTEXITCODE -ne 0) { Fail "repo 생성 실패" }
} else {
  Write-Host "origin 이미 존재 → push만"
  if ($Push) { git push -u origin HEAD }
}
Write-Host "[OK] $Repo 준비 완료" -ForegroundColor Green
