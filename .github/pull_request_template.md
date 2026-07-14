## 변경 요약
<!-- 무엇을·왜 바꿨는지 한두 줄 -->

## 변경 유형
- [ ] 해석 모델(.inp) 추가/수정
- [ ] 사용자 서브루틴(.f) 추가/수정
- [ ] 자동화·후처리 스크립트
- [ ] 문서

## 체크리스트
- [ ] `python platform/inp_lint.py <바뀐 .inp>` 통과 (ERROR 0)
- [ ] `python platform/tests/selftest.py` 통과
- [ ] 서브루틴 변경 시 `abaqus verify -user_explicit` 확인
- [ ] 결과가 있으면 `platform/regression.py check` 로 회귀 확인
- [ ] CI(platform-ci) 통과

## 결과 / 검증 (선택)
<!-- peak 관통력, 준정적성(ALLKE/ALLIE), 삭제요소 수, 보고서 링크 등 -->
