# TwinOS

**AI 기반 Digital Twin Operating System (DTOS)** — CAE·FMU·MBSE·V&V·보고서 업무를 Digital Twin Plugin 기반으로 오케스트레이션하는 플랫폼.

> 브랜드 규칙: 내부 코드명 **TwinOS**(저장소·코드), 기술 문서 정식 명칭 **DTOS**. 코드 식별자(`urn:dtos:`, `dtos.task-api/v1` 등)는 소문자 `dtos` 유지.

## 현재 상태

- **Interface Specification v1.0**: `docs/design/11-*.md` (사람용) + `contracts/` (기계가독, **단일 진실**) — 리뷰 후 baseline 동결 예정 ([ADR-0001](docs/adr/0001-interface-specification-v1-baseline.md))
- **Sprint 1 목표**: [Walking Skeleton](docs/sprint1-walking-skeleton.md) — Task 생성 → Orchestrator → FMH Plugin → Runner → Abaqus 실행 → ODB 추출 → HIC 계산 → 1페이지 Report → Human Approval의 end-to-end 1회 실동작

## 저장소 구조

```
contracts/     Interface Spec v1.0 JSON Schema + golden examples (CI가 강제)
sdk/           Plugin SDK: TwinAgent 베이스, 계약 Pydantic 모델
plugins/       Digital Twin Plugin (1차 구성 단위)
  fmh_twin/    ★ MVP: manifest, agent, fmh_impact 워크플로우, 게이트, KPI
apps/          orchestrator · gateway · web · runners/abaqus_runner
services/      report (도메인 공통 공용 서비스)
libs/          cae_toolkit(HIC 계산 등 도구 공통 로직) · core
tests/         contracts 검증(golden examples·manifest·workflow·gate) + 단위 테스트
docs/design/   설계 문서 00~11 (원본: NewJob 저장소에서 이관)
docs/adr/      Architecture Decision Records (동결 항목 변경 절차)
infra/         docker-compose (postgres/redis/minio)
```

## 시작하기

```bash
make install      # pip install -e ".[dev]"
make contracts    # Interface Spec 계약 검증 (golden examples + manifest/workflow/gate)
make test         # 전체 테스트
make up           # 로컬 인프라 (postgres/redis/minio)
```

## 개발 규칙

1. **계약 우선**: 컴포넌트 간 메시지는 `contracts/` 스키마를 준수해야 한다. 스키마 변경은 golden example 갱신을 동반하고, 파괴적 변경은 ADR + v2 신설로만.
2. **브랜치**: `main`(보호, 릴리스) ← `develop`(통합) ← 짧은 feature 브랜치 PR.
3. **Architecture Freeze**: 동결 항목 F1~F8(`docs/design/10-*.md` §2)의 변경은 ADR 필수.
4. Runner는 결정적 실행기 — LLM 호출 금지. LLM 산출물은 Quality Gate 뒤에서만 실행계 진입.

## 설계 문서

`docs/design/` 의 00(검토 총평)부터 11(Interface Spec)까지가 본 저장소의 설계 기준이다. 로드맵: MVP(FMH Digital Twin, ~M3) → Pilot(diabetes_twin, ~M6) → Platform(~M12) → Physical AI(M12+).
