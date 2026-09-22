# poc/jam — OpenSim-JAM 호환성 시험

**격리 구역.** 여기의 코드는 `src/msk_engine/` 파이프라인에 섞지 않는다 (CLAUDE.md §2).

## 목적

OpenSim-JAM(Lenhart2015 모델, COMAK 알고리즘)이 OpenSim 4.6 에서 동작하는지 확인한다.
그 결과로 ADR-0002(1차 Reference 모델)를 확정한다.

JAM 은 인대(Blankevoort1991Ligament)와 연골 접촉(Smith2018ArticularContactForce)을 제공해
관절반력을 넘어 인대력·접촉압까지 산출한다. 다만 **별도 포크 기반**이라 본체 버전과의
호환성이 보장되지 않는다.

- 저장소: https://github.com/clnsmith/opensim-jam
- 관련 문헌: Lenhart et al. 2015; Smith et al. 2018 (COMAK)

## 시험 항목

- [ ] 4.6 환경에서 JAM 플러그인 빌드 또는 로드 성공 여부
- [ ] Lenhart2015 모델을 4.6 API 로 읽을 수 있는지
- [ ] COMAK 실행 시간 (1 gait cycle 기준) — 웹 서비스로 감당 가능한 수준인지
- [ ] 4.5 에서 제거된 API(`get_GeometryPath()` 등) 의존 여부

## 판단 기준

위 항목이 모두 통과하고 실행 시간이 허용 범위여야 1차 포함을 검토한다.
하나라도 실패하면 Rajagopal 계열로 1차를 확정하고 JAM 은 2차 고도화로 넘긴다.

결과는 ADR-0002 에 기록한다.
