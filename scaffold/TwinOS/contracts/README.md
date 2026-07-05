# contracts/ — DTOS Interface Specification v1.0 (기계가독 사본)

**단일 진실은 이 디렉터리다** (10 문서 §4). `docs/design/11-DTOS-Interface-Specification-v1.0.md`가
사람용 명세이고, 여기의 JSON Schema가 CI를 구속한다.

- `<contract>/<ver>/<name>.schema.json` — JSON Schema (draft 2020-12, `$id: twinos://contracts/...`)
- `examples/<contract>/<ver>/<name>/*.json` — golden examples (tests/contracts가 자동 검증)

## 변경 규칙 (Spec §1.6, Architecture Freeze F1)
- 하위호환(필드 추가 등) = minor. 파괴적 변경 = v2 디렉터리 신설 + ADR 필수.
- 스키마 변경 PR에는 golden example 추가/갱신이 포함되어야 한다.
