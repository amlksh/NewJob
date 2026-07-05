# NewJob

작업용 저장소.

## V-DTOS (VPK Digital Twin Operating System) 시스템 설계 문서

「AI 기반 Digital Twin Operating System(DTOS) 개발 계획서」 검토 결과 및 구현 가능한 시스템 설계안.
플랫폼 브랜드명: **V-DTOS** — VPK Digital Twin Operating System.

| 문서 | 내용 |
|---|---|
| [00-검토의견-총평](docs/00-검토의견-총평.md) | 계획서 검토 총평, 현실성 보완 항목 7건과 대안 |
| [01-시스템-아키텍처](docs/01-시스템-아키텍처.md) | 전체 아키텍처, 배포 토폴로지, Runner 설계, 데이터 스키마, KPI 집계 |
| [02-오케스트레이터-워크플로우-설계](docs/02-오케스트레이터-워크플로우-설계.md) | AI Orchestrator 설계, Task Plan/Workflow 스키마, HITL, 실패 복구, 데이터 흐름 |
| [03-Agent-API-명세](docs/03-Agent-API-명세.md) | 공통 Agent 계약 + Orchestrator/CAE/FMU/MBSE/V&V/Report Agent별 범위·API |
| [04-MVP-범위-기술스택](docs/04-MVP-범위-기술스택.md) | MVP 필수/후속 기능 구분, 기술 스택 확정안, 모노레포 구조 |
| [05-WBS-개발일정](docs/05-WBS-개발일정.md) | 12개월 WBS(주 단위), 단계별 산출물, 마일스톤, 인력 배치 |
| [06-PhysicalAI-확장설계](docs/06-PhysicalAI-확장설계.md) | Isaac Sim/Omniverse/ROS2 확장 구조 및 단계적 도입 계획 |
| [07-V-DTOS-Reference-Architecture](docs/07-V-DTOS-Reference-Architecture.md) | 3~5년 장기 참조 아키텍처: Asset/Agent Registry, Simulation Graph, Twin Versioning, Plugin SDK, Connector 표준, Physical AI Horizon 전략 |
| [08-FMH-DigitalTwin-Plugin-설계](docs/08-FMH-DigitalTwin-Plugin-설계.md) | **MVP 확정 대상**: FMH Digital Twin Plugin — Twin 중심 재정의, TwinAgent 표준 인터페이스(`prepare/run/validate/report`), `fmh_impact` 워크플로우, FMH KPI, 자산 Lineage 연계 |
| [09-Learning-and-Evolution](docs/09-Learning-and-Evolution.md) | 학습·진화 체계: 4개 학습 루프(지식/템플릿/프롬프트/대리모델), 승격 게이트, 승인 위임 단계화, 단계별 가동 로드맵 |
| [10-Architecture-Freeze-실행-우선순위](docs/10-Architecture-Freeze-실행-우선순위.md) | 실행 우선순위 검토(Walking Skeleton 제안), Architecture Freeze 동결 목록(F1~F8) + ADR 절차, Repo 초기 구조 |
| [11-V-DTOS-Interface-Specification-v1.0](docs/11-V-DTOS-Interface-Specification-v1.0.md) | ⭐ **인터페이스 명세 v1.0(Draft)**: 8개 계약(task-api, twin-agent, tooljob, Artifact/URN, Workflow, Gate, 외부 API, Manifest), 상태 기계, 에러 모델, 버전 규칙, 적합성 테스트 |
