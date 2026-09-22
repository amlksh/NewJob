# data/

**이 디렉터리의 데이터 파일은 git 에 커밋하지 않는다** (`.gitignore` 로 제외).
재배포 조건이 확인되지 않은 공개 데이터셋과 환자 데이터가 섞이는 곳이다.

## Grand Challenge (무릎 하중 계측 데이터)

P1 검증 Case 의 비교기준. 계측형 무릎 임플란트 환자의 마커·GRF·EMG·경골 접촉력과
임플란트 형상이 공개되어 있다.

- 출처: https://simtk.org/projects/kneeloads
- 인용: Fregly BJ et al. *Grand challenge competition to predict in vivo knee loads.*
  J Orthop Res. 2012;30(4):503-513.
- 취득: SimTK 계정으로 로그인 후 다운로드. 다운로드 시 이용 약관에 동의하게 되므로
  **조건을 읽고 `docs/license_register.md` 를 채운 뒤** 사용할 것.

배치 예 (`configs/cases/kneeloads_example.yaml` 기준):

```
data/kneeloads/
  static.trc              정적 trial
  gait_trial.trc          보행 마커
  gait_trial_grf.mot      지면반력
  measured_contact.sto    계측 접촉력 (검증 비교용 — 튜닝에 쓰지 말 것)
```

## 주의

- **검증용과 튜닝용 trial 을 분리한다.** 배정은 `docs/vv/traceability.md` 에 기록한다.
- 환자 데이터는 비식별 상태로만 다룬다. 식별정보가 포함된 파일을 이 디렉터리에 두지 않는다.
- GRF 파일의 열 이름 규칙은 데이터셋마다 다르다.
  `configs/templates/external_loads.xml` 의 `force_identifier` 등을 실제 열 이름에 맞출 것.
- 마커 이름도 데이터셋마다 다르다. 모델 마커셋과 대응이 안 되면 파이프라인이 해석 전에 멈춘다.
  `configs/cases/*.yaml` 의 `required_markers` 를 채워 두면 조기에 잡힌다.
