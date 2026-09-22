# 라이선스 대장

새 모델·플러그인·데이터셋을 저장소에 들이기 **전에** 이 표에 행을 추가한다 (CLAUDE.md §4).

OpenSim API 자체는 Apache 2.0 이지만, [OpenSim 라이선스 문서](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53086437/License+for+OpenSim+4.0+and+Later)는
**모델·예제·플러그인이 각자의 라이선스를 유지한다**고 명시한다. 파일마다 확인이 필요하다.

이 대장은 WMIT 공동소유 계약의 Background IP / Foreground IP 구분 근거 자료가 된다.

## 소프트웨어

| 항목 | 버전 | 라이선스 | 출처 | 상업적 이용 | 확인일 | 확인자 |
| --- | --- | --- | --- | --- | --- | --- |
| OpenSim API (opensim-core) | 4.6 | Apache 2.0 | [PyPI](https://pypi.org/project/opensim/) | 가능 | 2026-09-22 | — |
| PyYAML | ≥6.0 | MIT | PyPI | 가능 | 2026-09-22 | — |

## 모델

| 항목 | 출처 | 라이선스 | 상업적 이용 | 출처 표기 의무 | 확인일 | 확인자 |
| --- | --- | --- | --- | --- | --- | --- |
| Rajagopal 2015 전신 모델 | OpenSim 배포본 | **확인 필요** | **확인 필요** | 확인 필요 | — | — |
| OpenSim-JAM / Lenhart2015 | [GitHub](https://github.com/clnsmith/opensim-jam) | **확인 필요** | **확인 필요** | 확인 필요 | — | — |

모델 파일을 `models/` 에 넣기 전에 동봉된 라이선스 파일과 헤더 주석을 읽고 위 표를 채울 것.
"확인 필요"가 남아 있는 모델로 만든 결과물은 대외 배포·납품에 쓰지 않는다.

## 데이터

| 항목 | 출처 | 이용 조건 | 재배포 | 인용 요구 | 확인일 | 확인자 |
| --- | --- | --- | --- | --- | --- | --- |
| Grand Challenge (kneeloads) | [SimTK](https://simtk.org/projects/kneeloads) | **확인 필요** (다운로드 시 약관 동의) | **금지 추정 — 확인 필요** | Fregly et al. 2012 인용 | — | — |

데이터는 `data/` 에 두고 git 에 커밋하지 않는다. 재배포 조건을 확인하기 전까지 외부 공유 금지.

## IP 구분 메모

- **Background IP**: 과제 착수 전부터 존재한 제3자 자산 — OpenSim, 공개 모델, 공개 데이터셋. 위 표가 목록이다.
- **Foreground IP**: 이 과제에서 새로 만든 것 — `src/msk_engine/` 코드, Setup XML 템플릿, 웹 계층, V&V 문서.
- 주의: Apache 2.0 등 허용적 라이선스라도 **출처 표기 의무**가 있다. 납품 산출물에 고지 파일을 포함할 것.
