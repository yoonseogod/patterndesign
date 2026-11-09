# 남성 더블브레스티드 트렌치코트 패턴 (A4 분할 인쇄)

클래식 트렌치코트(더블 여밈, 건 플랩, 뒤 스톰실드, 견장, 소매 스트랩, 벨트) 남성 패턴입니다.
실제 크기(1:1)로 A4에 나눠 인쇄해 붙여 쓰도록 만들었습니다.

**기본 파일은 시접 없는 완성선 패턴**이고, 각 선 안쪽에 빨간 글자로 시접 폭을 적어 두었습니다
(기본 1cm, 옆선·뒤중심 1.5cm, 몸판·소매 밑단 4cm, 골선은 시접 없음).
시접이 포함된 버전은 `_withSA` 파일입니다.

심지 붙이는 곳(패턴에 주황 빗금으로 표시): 칼라, 칼라 스탠드(칼라밴드), 앞 안단 전체, 윗소매·밑소매 밑단 5cm.

| 사이즈 | 가슴둘레 | 키 | 완성 가슴둘레 | 옷길이 | A4 파일 | 복사실용 1장 (폭 76cm) |
|---|---|---|---|---|---|---|
| 95  | 94  | 170 | 118 | 98  | `pdf/trench_men_95_A4.pdf`  | `pdf/trench_men_95_fullsize.pdf` |
| 100 | 98  | 175 | 122 | 101 | `pdf/trench_men_100_A4.pdf` | `pdf/trench_men_100_fullsize.pdf` |
| 105 | 102 | 180 | 126 | 104 | `pdf/trench_men_105_A4.pdf` | `pdf/trench_men_105_fullsize.pdf` |
| 110 | 106 | 185 | 130 | 107 | `pdf/trench_men_110_A4.pdf` | `pdf/trench_men_110_fullsize.pdf` |

## 인쇄 방법
1. 인쇄 설정에서 **실제 크기(100%)** 선택, '페이지에 맞춤' 끄기.
2. 1쪽만 먼저 인쇄해 10cm 시험 사각형을 자로 확인.
3. 2쪽 배치도를 보고 A1, B1 … 순서로 이어 붙이기 (빈 칸은 인쇄 안 함).
4. 각 장의 회색 테두리선에서 왼쪽·위쪽 여백을 잘라 이웃 장에 겹쳐 붙이기.

복사실용 1장 PDF는 폭 76cm라 A0 폭(84cm)이나 36인치 롤 용지에 그대로 출력할 수 있습니다.
뒤트임 길이는 모든 사이즈에서 38cm로 같습니다.

## 다시 만들기 / 치수 바꾸기
`generate_trench.py`의 `SIZES` 표를 수정한 뒤 실행합니다.

```bash
pip install reportlab shapely matplotlib numpy pdfplumber pillow
python3 generate_trench.py          # 전체 사이즈
python3 generate_trench.py 100      # 100만
python3 generate_trench.py --sa     # 시접 포함 버전 (_withSA)
python3 verify_fit.py 100           # 봉제선·여유분 검증 + 3D 그림 (verify/)
python3 audit_pdf.py 100 [--sa]     # PDF 검사: 실제 크기, 이어 붙이기, 글자 겹침·시접 표기 누락 등 17항목
python3 review_draft.py 100         # 제도 검토: 이음점 각도, 소매·진동 노치 맞춤, 오그림 배분
python3 checklist.py [100]          # 전체 체크리스트 130항목 (verify/checklist_*.md)
python3 mutation_test.py [100]      # 검사 도구 시험: 결함 23개를 심어 모두 잡는지 확인
python3 review_grading.py           # 사이즈 간 검토: 치수 증가 간격, 겹쳐 보기 (verify/grading_nest.png)
```

폰트: 나눔고딕 (SIL Open Font License).
