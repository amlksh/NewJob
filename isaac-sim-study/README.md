# Isaac Sim 학습 노트

NVIDIA Isaac Sim을 처음부터 공부하기 위한 한국어 가이드 모음입니다.
설치 → 튜토리얼 → USD 구조 → ROS2 구조 순서로 따라가도록 구성했습니다.

> ⚠️ **중요**: Isaac Sim은 **NVIDIA RTX GPU(RT Core 탑재, VRAM 16GB 이상 권장)**가 필수입니다.
> 이 가이드를 작성한 원격 컨테이너에는 GPU가 없어 실제 설치/실행은 본인의 RTX PC에서 진행해야 합니다.
> 아래 문서는 그 PC에서 그대로 따라 할 수 있도록 작성되었습니다.

## 기준 버전
- **Isaac Sim 5.1.0** (현재 stable, 2026년 6월 기준. 6.0.0 문서도 공개되어 있음)
- **Python 3.11** (Isaac Sim 5.x)
- **ROS 2 Humble** (권장)
- **OS**: Ubuntu 22.04 / Windows 10·11

## 목차

| # | 문서 | 내용 |
|---|------|------|
| 01 | [설치 가이드](docs/01-installation.md) | 시스템 요구사항, Workstation/Pip/Container 설치 |
| 02 | [튜토리얼 시작하기](docs/02-tutorials.md) | UI 둘러보기, 첫 씬, 추천 학습 순서 |
| 03 | [USD 구조 이해](docs/03-usd-structure.md) | Stage, Prim, Property, Layer, Composition |
| 04 | [ROS 2 구조 이해](docs/04-ros2-structure.md) | ROS 2 Bridge, OmniGraph, Action Graph |
| 05 | [학습 로드맵](docs/05-roadmap.md) | 4주 단계별 학습 계획 + 체크리스트 |
| 06 | [Physical AI PoC 전략](docs/06-physical-ai-poc-strategy.md) | 조립 라인 이상감지·대응 에이전트 · 6개월 PoC · 포지셔닝 |
| 07 | [Replicator 합성 데이터](docs/07-replicator-synthetic-data.md) | 합성 데이터 생성(PoC의 심장) + Anomalib 연결 |
| 08 | [이상탐지 모델 학습](docs/08-anomaly-model-training.md) | Anomalib로 이상탐지 학습·추론 (M3) |
| 09 | [대응 에이전트](docs/09-response-agent.md) | 감지→판단→대응 루프 완성 (M4) |

## 보고/발표 산출물
| 파일 | 용도 |
|------|------|
| `Isaac_Sim_Physical_AI_가이드.docx` | 기술 가이드 통합본(9개 챕터, 실무용) |
| `보고용-요약.md` / `Isaac_Sim_PoC_보고서.docx` | 임원 보고서(2페이지) |
| `VPK_PhysicalAI_PoC_발표자료.pptx` | 발표용 슬라이드(9장, VPK/PLM기술팀 김성훈) |
| `assets/demo_flow.png` | 데모 시나리오 다이어그램 |
| `demo/index.html` | 웹 브라우저 컨셉 데모(단일 파일, 더블클릭 실행) |

## 빠른 시작 (요약)

1. RTX GPU / 드라이버 / Ubuntu 22.04 준비 → [01 설치](docs/01-installation.md)
2. Isaac Sim 실행 후 GUI와 기본 튜토리얼 → [02 튜토리얼](docs/02-tutorials.md)
3. 씬이 USD로 어떻게 표현되는지 이해 → [03 USD](docs/03-usd-structure.md)
4. ROS 2와 연결해서 로봇 제어 → [04 ROS 2](docs/04-ros2-structure.md)

## 공식 자료 (북마크 권장)
- 공식 문서: https://docs.isaacsim.omniverse.nvidia.com/
- GitHub: https://github.com/isaac-sim/IsaacSim
- Isaac Lab(강화학습): https://isaac-sim.github.io/IsaacLab/
- USD 공식: https://openusd.org/
