# FMH 템플릿 (자산 이식 위치)

기존 사내 FMH 자동화 자산(WBS 1.5)을 이식하는 디렉터리다:

- `headform_position.inp.j2` — 헤드폼 포지셔닝
- `impact_case.inp.j2` — 충돌 케이스 조립
- `report_fmvss201.docx.j2` — FMVSS 201U 보고서 양식

실제 INP 템플릿은 사내 자산이므로 별도 절차로 반입한다. 반입 시
`param_schema`(schemas/)와 함께 등록하고 사람 검증(validated_by) 후 사용한다.
