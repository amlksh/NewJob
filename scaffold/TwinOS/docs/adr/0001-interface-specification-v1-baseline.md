# 0001. Interface Specification v1.0 Baseline 동결

상태: proposed (리뷰 통과 시 accepted로 전환하고 `interface-spec/v1.0.0` 태깅)
날짜: 2026-07-05

## 맥락
설계 문서(00~09)는 계약의 존재와 역할을 정의했으나, 다수 개발자의 동시 작업에는
필드 단위 스키마·상태 기계·에러 의미의 단일 기준이 필요하다.

## 결정
`docs/design/11-DTOS-Interface-Specification-v1.0.md`와 `contracts/`의 JSON Schema를
v1.0 Baseline으로 동결한다(Architecture Freeze F1). 문서와 스키마가 다르면 스키마가
우선한다. 이후 변경은 Spec §1.6 버전 규칙을 따르고, 파괴적 변경은 새 ADR + v2 신설로만
가능하다.

## 대안과 기각 사유
- 문서만 동결(스키마 없음): CI 강제 불가, 구현체 간 해석 차이 방지 못함 → 기각.
- 전면 자유 변경: 병렬 개발 시 통합 비용 폭증 → 기각.

## 영향
task-api/v1, twin-agent/v1, tooljob/v1, workflow v1, gate v1, manifest v1 — 전 컴포넌트.

## 마이그레이션
해당 없음 (최초 baseline).
