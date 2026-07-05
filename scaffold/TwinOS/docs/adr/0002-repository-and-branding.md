# 0002. 저장소 및 브랜드 결정

상태: accepted
날짜: 2026-07-05

## 맥락
플랫폼 코드 저장소와 브랜드 체계 확정 필요.

## 결정
- 저장소: `TwinOS` (Private). 현재 amlksh 계정에 생성, VPK 조직 개설 시 Transfer.
- 브랜치: `main`(보호) + `develop`(통합). trunk 성격의 짧은 feature 브랜치 → develop PR.
- 브랜드: 내부 코드명 **TwinOS**, 기술 문서 정식 명칭 **AI 기반 Digital Twin Operating
  System(DTOS)**. 코드 식별자(`urn:dtos:`, `dtos.task-api` 등)는 dtos 소문자 유지.

## 대안과 기각 사유
- `v-dtos`: 제품화·정부과제·특허·외부 발표 확장성 부족 → 기각 (경영진 결정).

## 영향
저장소 구조 전체, CI 브랜치 트리거.

## 마이그레이션
설계 문서는 NewJob 저장소에서 docs/design/으로 이관(사본). 이후 단일 소스는 본 저장소.
