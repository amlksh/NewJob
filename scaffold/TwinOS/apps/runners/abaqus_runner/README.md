# abaqus_runner

해석 서버 상주 Runner 데몬 (01 문서 §4, Spec §5 dtos.tooljob/v1).
- Redis 큐(tooljob.abaqus.v1) BRPOP → 입력 다운로드/검증 → abaqus 실행 → .sta 파싱 → MinIO 업로드
- outbound-only, LLM 호출 금지, heartbeat 30s (동결 항목 F3)
Sprint 1 범위: 초소형 INP 1건의 무인 실행 (WBS 1.4).
