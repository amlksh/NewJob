#!/usr/bin/env bash
# TwinOS 저장소 초기화 스크립트
# 사전 조건: GitHub(또는 GitLab)에 빈 Private 저장소 TwinOS 생성 완료
# 사용법: ./scripts/bootstrap_repo.sh <remote-url>
set -euo pipefail

REMOTE_URL="${1:?usage: bootstrap_repo.sh <remote-url>}"
cd "$(dirname "$0")/.."

git init -b main
git add -A
git commit -m "TwinOS 초기 스캐폴드: contracts(Interface Spec v1.0) + CI 계약 검증 + fmh_twin plugin + SDK"
git remote add origin "$REMOTE_URL"
git push -u origin main
git checkout -b develop
git push -u origin develop
echo "완료: main + develop 푸시됨. GitHub에서 main 브랜치 보호 규칙을 설정하세요."
