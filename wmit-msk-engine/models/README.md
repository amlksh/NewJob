# models/

모델 파일을 두는 곳. **git 에 커밋하기 전에 `docs/license_register.md` 를 채운다.**

OpenSim API 는 Apache 2.0 이지만 모델·예제·플러그인은 각자 라이선스를 유지한다.
파일 헤더 주석과 동봉된 라이선스 파일을 직접 확인할 것.

## 배치 예

```
models/
  rajagopal/
    Rajagopal2015.osim
    Geometry/            메시 파일
    LICENSE              반드시 함께 보관
```

## 주의

- `configs/cases/*.yaml` 의 `model_file` 이 여기를 가리킨다.
- 모델을 교체하면 마커셋·body 이름·관절 이름이 달라진다.
  `external_loads.xml` 의 `applied_to_body`, `jr_setup.xml` 의 `joint_names`·`express_in_frame` 을 함께 고칠 것.
- 모델 변경은 결과 수치를 바꾸므로 V&V 활동 재수행 대상이다.
