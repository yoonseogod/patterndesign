"""A4 yarn placement guide for front panel B (thread decoration). Output: thread_guide_A4.pdf"""
import os, math, random
os.environ.setdefault('NO_LINING', '1')
from shapely.geometry import Polygon, LineString, box
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import Color, black
import make_pattern as m
from make_pattern import CM

W, H = A4
S = 1/4                                   # diagram scale 1:4
B = Polygon(m.FBN['seam'])
x0, y0, x1, y1 = B.bounds
OX, OY = 2.6*CM, H - 3.0*CM                # page position of pattern point (x0, y0)
def P(x, y): return OX + (x - x0)*S*CM, OY - (y - y0)*S*CM

GREY = Color(.45, .45, .45); RED = Color(.70, .21, .12)
ZONES = [  # (name, y from, y to, fill)
    ('Z1 뭉치 · 루프 (빽빽)', 0, 36, Color(.86, .42, .22, .30)),
    ('Z2 크로셰 그물 (칸 2~3cm)', 36, 66, Color(.85, .64, .25, .25)),
    ('Z3 성긴 그물 + 늘어진 실 고정', 66, 99, Color(.92, .83, .55, .30)),
]
YARN = [('러스트 레드', .35, Color(.70, .21, .12)), ('오렌지', .25, Color(.85, .40, .16)),
        ('머스터드 · 오커', .20, Color(.80, .60, .20)), ('아이보리 · 크림', .12, Color(.93, .89, .80)),
        ('다크 브라운 · 올리브', .08, Color(.33, .27, .16))]

def path(c, pts, close=False):
    p = c.beginPath()
    for i, (x, y) in enumerate(pts):
        X, Y = P(x, y); p.moveTo(X, Y) if i == 0 else p.lineTo(X, Y)
    if close: p.close()
    return p

def main(out):
    c = canvas.Canvas(out, pagesize=A4)
    c.setTitle('앞판 B 실 배치도')
    c.setFont('KR', 16); c.drawString(1.8*CM, H - 1.5*CM, '앞판 B 실(스레드) 배치도')
    c.setFont('KR', 8.5); c.setFillColor(GREY)
    c.drawString(1.8*CM, H - 2.1*CM, f'축척 1:4 · 완성선 기준 · 사이즈 55 밀착 · 앞판 B 완성 높이 {y1 - y0:.0f}cm, 폭 {x1 - x0:.0f}cm')
    # zones
    for name, a, b, col in ZONES:
        z = B.intersection(box(-99, a, 99, b))
        if z.is_empty: continue
        c.setFillColor(col); c.setStrokeColor(col)
        for g in getattr(z, 'geoms', [z]):
            c.drawPath(path(c, list(g.exterior.coords), True), stroke=0, fill=1)
    # spill-over band onto the quilted centre panel (like the photo)
    style = [e for e in m.FBN['edges'] if e.get('n') == 'style'][0]['pts']
    band = LineString(style).buffer(3.0, single_sided=False).intersection(box(-99, 17, 99, 34)).difference(B)
    c.setDash(3, 2); c.setStrokeColor(RED); c.setFillColor(Color(.86, .42, .22, .12)); c.setLineWidth(.7)
    for g in getattr(band, 'geoms', [band]):
        if g.geom_type == 'Polygon': c.drawPath(path(c, list(g.exterior.coords), True), stroke=1, fill=1)
    c.setDash()
    # outline
    c.setStrokeColor(black); c.setLineWidth(1.1)
    c.drawPath(path(c, list(B.exterior.coords), True), stroke=1, fill=0)
    # anchors for hanging strands
    rnd = random.Random(4)
    hem = m.FBN['edges'][2]['pts']
    anchors = [m.at(hem, d) for d in [i*1.6 + 0.8 for i in range(int(m.plen(hem)/1.6))]]
    anchors += [(x - 0.8, y) for x, y in (m.at(style, d) for d in range(40, int(m.plen(style)) - 2, 4))]
    while len(anchors) < 52:
        x, y = x0 + rnd.random()*(x1 - x0), 66 + rnd.random()*(y1 - 66)
        if B.buffer(-1).contains(LineString([(x, y), (x+.01, y)])): anchors.append((x, y))
    # hanging strands below the hem (schematic)
    c.setLineWidth(.5)
    for i, (ax, ay) in enumerate(anchors[:len(anchors)]):
        col = YARN[i % len(YARN)][2]; c.setStrokeColor(col)
        if ay < y1 - 4: continue
        pts = [(ax, ay)] + [(ax + math.sin(k*.9 + i)*0.8, ay + k*2.6) for k in range(1, 7)]
        c.drawPath(path(c, pts), stroke=1, fill=0)
    c.setFillColor(RED)
    for ax, ay in anchors:
        X, Y = P(ax, ay); c.circle(X, Y, 1.6, stroke=0, fill=1)
    X, Y = P(x0, y1 + 19); c.setFillColor(GREY); c.setFont('KR', 7.5)
    c.drawString(X, Y, '↓ 바닥까지 + 15~30cm')
    # zone labels on the diagram
    c.setFillColor(black); c.setFont('KR', 7.5)
    for name, a, b, col in ZONES:
        X, Y = P(x0 + 0.6, (a + max(a, y0) + min(b, y1)) / 2 if a == 0 else (a + min(b, y1)) / 2)
        c.drawString(X, Y, name.split(' ')[0])
    X, Y = P(-9.4, 36.5); c.setFillColor(RED); c.drawString(X, Y, '← 퀼팅 쪽 넘침 3cm')
    # scale bar
    X, Y = P(x0, y1 + 26); c.setStrokeColor(black); c.setLineWidth(.8)
    c.line(X, Y, X + 10*S*CM, Y); c.setFont('KR', 7); c.setFillColor(black); c.drawString(X + 10*S*CM + 4, Y - 2.5, '10cm')

    # ---- right column: recipe
    tx, ty = 9.2*CM, H - 3.2*CM
    def head(t):
        nonlocal ty
        ty -= .55*CM; c.setFont('KR', 11); c.setFillColor(black); c.drawString(tx, ty, t); ty -= .15*CM
    def line(t, size=8.3, color=black, ind=0):
        nonlocal ty
        ty -= size*1.55; c.setFont('KR', size); c.setFillColor(color); c.drawString(tx + ind, ty, t)
    head('구역 (위 → 아래)')
    for name, a, b, col in ZONES:
        c.setFillColor(col); c.rect(tx, ty - 13, 10, 10, stroke=0, fill=1)
        line(name, ind=14)
    line('빨간 점 = 늘어진 실 고정점 (앵커)', ind=0, color=RED)
    head('색 배합')
    bx = tx
    for nm, r, col in YARN:
        c.setFillColor(col); c.rect(bx, ty - 14, r*9.5*CM, 9, stroke=0, fill=1); bx += r*9.5*CM
    ty -= 12
    for nm, r, col in YARN: line(f'{nm} {int(r*100)}%', size=7.8, ind=4)
    head('실 굵기 섞기')
    for t in ['굵은 울(5mm 이상) 30% · 중간 면사 50% · 가는 실·자수실 20%',
              '일부는 실을 풀어 보풀·꼬임을 살리면 사진 느낌에 가까워요']: line(t, size=7.8)
    head('작업 순서')
    steps = ['① 베이스: 앞판 B 거즈/튤 2겹, Z1 뒷면에 얇은 접착심(무게 지지)',
             '② Z2·Z3 그물은 B를 붙이기 전 평평한 상태에서 작업',
             '   사슬뜨기 그물을 깔고 칸 모서리마다 손바느질로 고정(카우칭)',
             '③ 앞 중심판과 B 연결 후 바디에 입힌 상태에서 나머지 작업',
             '④ Z1: 2~4cm 루프를 겹겹이 + 팝콘·매듭, 3cm마다 고정',
             '   스타일선을 넘어 퀼팅 쪽으로 3cm까지 덮기(지그재그 일부 보이게)',
             '⑤ 앵커 1곳에 3~4가닥을 라크스헤드 매듭으로 고정',
             '   베이스 2겹 + 솔기 시접을 함께 관통해 무게 분산',
             '⑥ 길이: (앵커 → 바닥) + 15~30cm를 무작위로, 바디 위에서 자르기',
             '   1/3 정도만 바닥에 고이게 → 사진처럼 흘러내리는 실루엣']
    for t in steps: line(t, size=7.8)
    head('분량 (대략)')
    for t in [f'늘어진 실: 앵커 {len(anchors)}곳 × 3~4가닥 ≈ 170가닥 × 평균 0.9m ≈ 150m',
              '그물 · 뭉치 · 루프 ≈ 100~120m  →  합계 약 250~300m (색별로 위 비율대로)']:
        line(t, size=7.8)
    head('팁')
    for t in ['바디에 입혀 정면·측면을 번갈아 보며 위쪽 뭉치 부피를 조절하세요',
              '무거운 굵은 실은 위쪽(Z1)에, 가는 실은 아래쪽으로 갈수록 많이',
              '3D 뷰어의 "실 장식" 레이어가 같은 배치로 만들어져 있어요']:
        line(t, size=7.8, color=GREY)
    c.showPage(); c.save()
    print('anchors', len(anchors))

if __name__ == '__main__':
    main(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'thread_guide_A4.pdf'))
