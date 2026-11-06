"""Small 'where does this piece go' diagram (front view). Usage: python3 piece_locator.py <out.pdf>"""
import sys, math, os
os.environ.setdefault('NO_LINING', '1')
from shapely.geometry import Polygon, LineString
from shapely.ops import split
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color, black, white
import make_pattern as m
CM = m.CM
def outline(pc):
    pts = []
    for e in pc['edges']: pts += e['pts'] if not pts else e['pts'][1:]
    return Polygon(pts).buffer(0)
def ext(pts, L=6):
    (x0, y0), (x1, y1) = pts[0], pts[1]; d = math.hypot(x1-x0, y1-y0); a = (x0-(x1-x0)/d*L, y0-(y1-y0)/d*L)
    (x0, y0), (x1, y1) = pts[-1], pts[-2]; d = math.hypot(x1-x0, y1-y0); b = (x0-(x1-x0)/d*L, y0-(y1-y0)/d*L)
    return LineString([a] + list(pts) + [b])
def cut(p, l): return sorted([g for g in split(p, l).geoms if g.area > 1], key=lambda g: g.centroid.x)
FA, FB = outline(m.FA), outline(m.FB)
centre, side = cut(FA, ext(m.prin_c))
c_up, c_rest = sorted(cut(centre, LineString(m.L1)), key=lambda g: g.centroid.y)
c_mid, c_low = sorted(cut(c_rest, LineString(m.L2)), key=lambda g: g.centroid.y)
s_up, s_low = sorted(cut(side, LineString(m.L1)), key=lambda g: g.centroid.y)
W, H = 12*CM, 23*CM
c = canvas.Canvas(sys.argv[1], pagesize=(W, H))
s = 0.15; ox, oy = 5.2*CM, H - 1.7*CM
RED = Color(.7, .2, .1)
def P(x, y): return ox + x*s*CM, oy - y*s*CM
def draw(g, fill, lw=.8):
    p = c.beginPath()
    for i, (x, y) in enumerate(g.exterior.coords):
        X, Y = P(x, y); p.moveTo(X, Y) if i == 0 else p.lineTo(X, Y)
    p.close(); c.setLineWidth(lw); c.setStrokeColor(black); c.setFillColor(fill); c.drawPath(p, stroke=1, fill=1)
for g, nm in ((c_up, '1-1'), (c_mid, '1-2'), (c_low, '1-3'), (s_up, '1-4'), (FB, '2')):
    draw(g, Color(.95, .94, .91)); X, Y = P(g.centroid.x, g.centroid.y)
    c.setFillColor(Color(.4, .4, .4)); c.setFont('KR', 10); c.drawCentredString(X, Y, nm)
draw(s_low, Color(.86, .35, .2, .55), 1.8)
X, Y = P(s_low.centroid.x, s_low.centroid.y); c.setFillColor(black); c.setFont('KR', 13); c.drawCentredString(X, Y - 4, '1-5')
def badge(X, Y, n):
    c.setFillColor(RED); c.circle(X, Y, 7, stroke=0, fill=1); c.setFillColor(white); c.setFont('KR', 9); c.drawCentredString(X, Y - 3.2, n)
for (x, y), n in (((17.5, 35.6), '1'), ((24.6, 58), '2'), ((18, 82.5), '3'), ((10.4, 60), '4')): badge(*P(x, y), n)
c.setFillColor(black); c.setFont('KR', 12); c.drawString(.6*CM, H - .8*CM, '1-5 앞 옆판 하단 — 앞에서 본 위치')
items = [('1', '윗선 (빨간 점선)', '→ 1-4 앞 옆판 상단의 아랫선. 가운데 너치 1개 맞춤'),
         ('2', '바깥 직선 (옆선)', '→ 3 뒤판 왼쪽의 옆선. 허리 너치 2개 맞춤'),
         ('3', '아랫선', '→ 밑단. 시접 2cm 접어 마무리'),
         ('4', '안쪽 곡선 (프린세스선)', '→ 1-2 + 1-3 (앞 중심판) 바깥 곡선. 허리 너치 2개 맞춤')]
y = 5.6*CM
for n, a, t in items:
    badge(.9*CM, y + 3, n)
    c.setFillColor(black); c.setFont('KR', 9.5); c.drawString(1.35*CM, y, a)
    c.setFont('KR', 8.5); c.setFillColor(Color(.3, .3, .3)); c.drawString(1.35*CM, y - 12, t)
    y -= 1.1*CM
c.setFont('KR', 8); c.setFillColor(Color(.45, .45, .45)); c.drawString(.6*CM, .4*CM, '착용자 왼쪽(소매가 달리는 쪽) 앞판 아래 부분 · 그림 오른쪽 = 소매 쪽')
c.save()
