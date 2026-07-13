# 마이크로니들 피부 관통 FE 해석 방안 (문헌 기반)

앞서 구성한 VUMAT 예제(`vumat_skin.f` + `microneedle_penetration.inp`)를
출발점으로, 제시된 참고문헌의 방법론을 반영한 단계별 해석 전략을 정리합니다.

> **서지 확인 메모**
> 아래 참고문헌 중 두 편은 원문 서지를 직접 확인했습니다.
> - [2]의 정확한 제목은 *"Insights into the mechanics of solid conical
>   microneedle array insertion into skin **using the finite element
>   method**"* (Shu et al., *Acta Biomaterialia*, **135**, 403–413, 2021)
>   입니다. 사용자 목록의 제목에서 "using the finite element method"가
>   누락되어 있어 인용 시 보완이 필요합니다.
> - [5] *"A method to predict insertion of dissolvable microneedles:
>   No need to fabricate microneedles"* (*Int. J. Pharm.*, 2025)도
>   확인했습니다.
> 나머지 문헌은 원문 대조를 완료하지 못했으므로, 인용 전 DOI로
> 최종 확인하시길 권합니다.

---

## 1. 참고문헌 → 모델링 반영 매핑

| # | 문헌(주제) | 핵심 기여 | 본 해석에의 반영 |
|---|-----------|-----------|-----------------|
| 1 | Computational simulation of MN penetration (AJME) | 임상용 관통 시뮬레이션, 초탄성 피부 | 초탄성 기반 관통 프레임 |
| 2 | Shu et al., *Acta Biomater.* 2021 (원뿔 어레이 삽입 역학, FEM) | **3D 다층·이방성·사전인장(pre-stress) 피부**, 어레이 상호작용, 베이스플레이트 효과 | 다층+이방성+사전인장 도입, 어레이 확장 |
| 3 | Numerical simulation of MN insertion (CMBBE) | 파괴 기준(failure criterion) 모사 | 손상/삭제 기준 정식화 |
| 4 | Mechanics of dissolving MN insertion (FE+실험, JAP) | 용해성 니들 변형 + 실험 대조 | 니들 변형체화, 실험 검증 절차 |
| 5 | *"No need to fabricate MN"* (*Int. J. Pharm.* 2025) | **좌굴(buckling) 파괴력 vs 삽입력** 비교로 삽입 성공 예측(제작 전) | 니들 좌굴/파손 판정 추가 |
| 6 | 형상·삽입속도 최적화 | 기하/속도 파라미터 스터디 | DOE 파라메트릭 스윕 |
| 7 | Computational modelling of MN insertion (학위논문) | 종합 FE 절차 | 워크플로 정합성 검증 |

---

## 2. 단계별 해석 전략 (Phased Approach)

관통 시뮬레이션은 **접촉 + 대변형 + 재료 파단 + 요소 삭제**가 결합된
고난도 비선형 문제입니다. 한 번에 최종 모델로 가지 말고 단계적으로
신뢰도를 쌓는 것을 권장합니다.

### Phase 0 — 재료 검증 (단일 요소)
- VUMAT을 단일 요소(CAX4R/C3D8R) 단축 인장·압축으로 검증.
- 손상 비활성(λ_d 크게)에서 Neo-Hookean 해석해와 응력 일치 확인.
- 목적: 구성식/응력 성분 순서/에너지 업데이트 정합성 확보.

### Phase 1 — 압입(indentation) 단계 (파단 전)
- 문헌 [2],[6]의 관점: **관통 이전 압입 단계**에서 피부 변형·니들력
  관계가 관통 개시를 지배.
- 손상을 끄고(또는 λ_f 매우 크게) 니들을 접촉·압입만 시켜
  힘–변위 곡선의 **선형→비선형 천이**를 확인.
- 어레이의 경우 니들 간격(pitch)이 skin strain에 미치는 영향 검토.

### Phase 2 — 관통(puncture) 단계 (파단 + 요소 삭제)
- 손상/삭제 활성화. 힘–깊이 곡선의 **peak 직후 급락** = 관통 개시.
- 전역 접촉으로 침식면 재노출 처리(현재 `.inp` 구성).
- 관통력, 관통 깊이, 관통 효율(penetration efficiency) 산출.

### Phase 3 — 파라메트릭·최적화 스터디
- 문헌 [5],[6]: 니들 형상(첨두 반경, 원뿔각, 종횡비), 삽입속도,
  사전인장, 어레이 간격을 인자로 DOE 스윕.
- 니들을 **변형체**로 두고 **좌굴 파괴력 vs 삽입력**을 비교하여
  "삽입 성공 여부"를 제작 전에 판정([5]의 핵심 아이디어).

---

## 3. 문헌 반영 핵심 개선 항목

### 3.1 피부 모델 고도화 — 문헌 [2] 반영
현재 예제는 단층·등방성입니다. 문헌 [2]는 아래 3가지를 강조합니다.

1. **다층(multi-layer)**: 각질층(stratum corneum, 딱딱·박막) / 표피 /
   진피(dermis, 무름·두꺼움)를 별도 `*SOLID SECTION`·물성으로 분리.
   각질층 파단이 관통 개시를 지배하므로 층별 λ_f 분리가 중요.
2. **이방성(anisotropic)**: 진피의 콜라겐 섬유 방향성.
   Abaqus 내장 `*ANISOTROPIC HYPERELASTIC, HOLZAPFEL`(HGO) 또는
   VUMAT에 HGO 항 추가로 구현.
3. **사전인장(pre-tension/pre-stress)**: in-vivo 피부의 장력.
   `*INITIAL CONDITIONS, TYPE=STRESS` 또는 사전 스텝의 변위로 부여.
   → 문헌 결과: 0→10% 사전인장 시 관통력 약 13%↓, 관통효율 약 15%↓.

### 3.2 니들 파손(좌굴) 판정 — 문헌 [5] 반영
- 니들을 **변형체(deformable)** 로 모델링(예: PLA/PVP 용해성 니들 물성).
- 삽입력이 임계 좌굴력을 초과하면 니들이 먼저 좌굴/파손 → 삽입 실패.
- Abaqus에서 니들에 `*STATIC` 좌굴(Buckle) 또는 Explicit 대변형으로
  좌굴 후 거동을 확인하고, 삽입력 곡선과 비교.
- 판정식: `F_insertion(geometry, skin) < F_buckling(needle)` 이면 관통 성공.

### 3.3 파괴 기준 정식화 — 문헌 [3] 반영
현재 VUMAT은 **최대 주신축비** 기준입니다. 대안/개선:
- 최대 주응력 / von Mises / 정수압을 병용한 복합 기준.
- **파단에너지(energy-based) 손상**으로 정규화하여 메시 의존성 완화
  (VUMAT의 `charLength` 활용, 파단에너지 Gf 입력).
- 층별로 서로 다른 파단 임계값 지정.

### 3.4 준정적성 및 수치 안정화
- 연조직은 매우 무르므로 Explicit 안정 증분이 작음 → **질량 스케일링**
  (`*FIXED MASS SCALING`)으로 계산시간 확보, 단 `ALLKE ≪ ALLIE`(5~10%)
  로 준정적성 확인.
- 삽입속도가 물리적으로 중요하면([6]) 율의존(점탄성) 항을 추가하고
  실제 속도를 부여(질량 스케일링 남용 금지).

---

## 4. 검증(Validation) 절차 — 문헌 [4],[5] 반영

1. **힘–변위 실험 대조**: 삽입력–깊이 곡선의 peak(관통 개시)과
   기울기를 문헌/자체 실험과 비교.
2. **관통 깊이/효율**: 삭제된 요소로 정의되는 관통 채널 깊이 대 실험.
3. **메시 수렴성**: 관통 경로 요소크기를 절반씩 줄이며 peak force 수렴 확인.
4. **파라미터 민감도**: (C10, λ_d, λ_f, 마찰계수, 사전인장)에 대한 감도.

---

## 5. 현재 예제 대비 확장 로드맵

| 항목 | 현재 예제 | 문헌 기반 목표 |
|------|-----------|----------------|
| 차원 | 2D 축대칭 | 단일 니들 검증 후 3D 어레이([2]) |
| 피부 | 단층·등방성 Neo-Hookean | 다층·이방성(HGO)·사전인장([2]) |
| 니들 | 해석적 강체 | 변형체 + 좌굴 판정([5]) |
| 파단 | 최대 주신축비 | 에너지기반·복합기준·층별([3]) |
| 하중 | 단일 속도 압입 | 속도/형상/간격 DOE([6]) |
| 검증 | 힘–깊이 곡선 | 실험 대조·수렴성([4],[5]) |

**권장 진행 순서**: Phase 0(재료검증) → Phase 1(단일 니들 압입) →
Phase 2(관통·삭제) → 3D 다층·이방성 확장 → 니들 변형체+좌굴 →
파라메트릭 최적화 → 실험 검증.

---

## 6. 참고문헌 (확인된 서지)

- Shu, W.; Heimark, H.; Bertollo, N.; Tobin, D.J.; O'Cearbhaill, E.D.;
  Ní Annaidh, A. *Insights into the mechanics of solid conical microneedle
  array insertion into skin using the finite element method.*
  **Acta Biomaterialia** 135 (2021) 403–413.
  https://www.sciencedirect.com/science/article/pii/S174270612100578X
- *A method to predict insertion of dissolvable microneedles: No need to
  fabricate microneedles.* **International Journal of Pharmaceutics** (2025).
  https://www.sciencedirect.com/science/article/abs/pii/S0378517325005368

> 그 외 문헌(AJME, CMBBE, JAP, USC 학위논문 등)은 사용자 제공 목록 기준이며,
> 원문 서지·링크는 DOI로 최종 확인 후 인용하시기 바랍니다.
