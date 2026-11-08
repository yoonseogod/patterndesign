# 남성 더블브레스티드 트렌치코트 패턴 (A4 분할 인쇄)

클래식 트렌치코트(더블 여밈, 건 플랩, 뒤 스톰실드, 견장, 소매 스트랩, 벨트) 남성 패턴입니다.
실제 크기(1:1)로 A4에 나눠 인쇄해 붙여 쓰도록 만들었습니다. 시접 포함(기본 1cm, 밑단 4cm).

심지 붙이는 곳(패턴에 주황 빗금으로 표시): 칼라, 칼라 스탠드(칼라밴드), 앞 안단 전체, 윗소매·밑소매 밑단 5cm.

| 사이즈 | 가슴둘레 | 키 | 완성 가슴둘레 | 옷길이 | A4 파일 | 복사실용 1장 |
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

## 다시 만들기 / 치수 바꾸기
`generate_trench.py`의 `SIZES` 표를 수정한 뒤 실행합니다.

```bash
pip install reportlab shapely
python3 generate_trench.py          # 전체 사이즈
python3 generate_trench.py 100      # 100만
```

폰트: 나눔고딕 (SIL Open Font License).
