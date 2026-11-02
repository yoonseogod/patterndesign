"""Render the dress pattern to an A4 PDF: overview (1:6) + info + full-size tiled pages."""
import math
from shapely.geometry import Polygon, LineString, Point
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import Color, black, white
from reportlab.pdfbase.pdfmetrics import stringWidth
import make_pattern as m
from make_pattern import CM, pieces, plen, at

GREY = Color(.45, .45, .45)
LIGHT = Color(.80, .80, .80)
QUILT = Color(.86, .82, .74)
RED = Color(.78, .16, .10)
PAPER_W, PAPER_H = A4
MARGIN = 1.0                       # cm
TILE_W, TILE_H = 21.0 - 2*MARGIN, 29.7 - 2*MARGIN   # 19 x 27.7 cm
COLS = 8
CANVAS_W = COLS*TILE_W
DIM = Color(.08, .30, .66)

# ------------------------------------------------------------- automatic layout (canvas cm, y down)
from shapely.geometry import box as _box
from shapely.affinity import translate as _tr
TEST_SQ = (1.0, 1.0)
TITLE_AT = (8.0, 1.0)
GAP = 0.8
def auto_layout():
    placed = [_box(TEST_SQ[0]-GAP, TEST_SQ[1]-GAP, TEST_SQ[0]+5+GAP, TEST_SQ[1]+5+GAP),
              _box(TITLE_AT[0]-GAP, 0, TITLE_AT[0]+44, TITLE_AT[1]+6.5)]
    order = sorted(pieces, key=lambda p: -(p['bbox'][3]-p['bbox'][1])*(p['bbox'][2]-p['bbox'][0]))
    for pc in order:
        P0 = Polygon(pc['cut']).buffer(GAP/2).simplify(.1)
        b = P0.bounds; w, h = b[2]-b[0], b[3]-b[1]
        done = False
        for y in [i*0.5 for i in range(0, 600)]:
            for x in [i*0.5 for i in range(0, int((CANVAS_W-w)/0.5)+1)]:
                bb = (x, y, x+w, y+h)
                cand = None
                for q in placed:
                    qb = q.bounds
                    if qb[0] < bb[2] and qb[2] > bb[0] and qb[1] < bb[3] and qb[3] > bb[1]:
                        if cand is None: cand = _tr(P0, x-b[0], y-b[1])
                        if cand.intersects(q): break
                else:
                    pc['off'] = (x-b[0]+0, y-b[1]+0)
                    placed.append(cand if cand is not None else _tr(P0, x-b[0], y-b[1]))
                    done = True; break
            if done: break
        assert done, pc['name']
    return max(q.bounds[3] for q in placed)
CONTENT_H = auto_layout()
ROWS = math.ceil((CONTENT_H+0.5)/TILE_H)
CANVAS_H = ROWS*TILE_H
ROWNAMES = 'ABCDEFGH'

# ------------------------------------------------------------- drawing primitives
class View:
    """maps canvas cm (y down) to page points"""
    def __init__(self, c, x0, y0, s, px, py):
        self.c, self.x0, self.y0, self.s, self.px, self.py = c, x0, y0, s, px, py
    def p(self, x, y):
        return (self.px + (x-self.x0)*self.s*CM, self.py - (y-self.y0)*self.s*CM)

def poly(v, pts, off, closed=False, width=.6, color=black, dash=None):
    c = v.c
    c.setLineWidth(width); c.setStrokeColor(color)
    c.setDash(list(dash)) if dash else c.setDash()
    path = c.beginPath()
    for i, (x, y) in enumerate(pts):
        X, Y = v.p(x+off[0], y+off[1])
        path.moveTo(X, Y) if i == 0 else path.lineTo(X, Y)
    if closed: path.close()
    c.drawPath(path, stroke=1, fill=0)
    c.setDash()

def text_c(v, x, y, lines, size, off, color=black, font='KR'):
    c = v.c; c.setFillColor(color)
    X, Y = v.p(x+off[0], y+off[1])
    lh = size*1.25
    top = Y + lh*(len(lines)-1)/2 - size*.35
    for i, t in enumerate(lines):
        sz = size*(1.0 if i == 0 else .78)
        c.setFont(font, sz); c.drawCentredString(X, top - i*lh, t)

def arrow_head(v, a, b, off, size_cm):
    ang = math.atan2(b[1]-a[1], b[0]-a[0])
    pts = [b, (b[0]-size_cm*math.cos(ang-.35), b[1]-size_cm*math.sin(ang-.35)),
           (b[0]-size_cm*math.cos(ang+.35), b[1]-size_cm*math.sin(ang+.35))]
    c = v.c; c.setFillColor(black)
    path = c.beginPath()
    for i, (x, y) in enumerate(pts):
        X, Y = v.p(x+off[0], y+off[1]); path.moveTo(X, Y) if i == 0 else path.lineTo(X, Y)
    path.close(); c.drawPath(path, stroke=0, fill=1)

def clip_lines(P, pts):
    g = P.intersection(LineString(pts))
    return [list(q.coords) for q in getattr(g, 'geoms', [g]) if q.geom_type == 'LineString' and not q.is_empty]

def text_rot(v, x, y, t, size, off, ang, color=DIM):
    c = v.c; X, Y = v.p(x+off[0], y+off[1])
    c.saveState(); c.translate(X, Y); c.rotate(ang); c.setFillColor(color); c.setFont('KR', size)
    c.drawCentredString(0, -size*.35, t); c.restoreState()

def fmt(L): return f'{L:.1f}'

def auto_grain(pc, P):
    from shapely.ops import polylabel
    lab = polylabel(P, .2)
    pc['labelpt'] = (lab.x, lab.y)
    for dx in (4.5, -4.5, 6.5, -6.5, 3, -3, 0):
        g = P.buffer(-1.2).intersection(LineString([(lab.x+dx, -500), (lab.x+dx, 500)]))
        if g.is_empty or g.geom_type != 'LineString' or g.length < 10: continue
        y0, y1 = g.bounds[1], g.bounds[3]; m_ = (y0+y1)/2; hl = min(g.length*.36, 22)
        return ((lab.x+dx, m_-hl), (lab.x+dx, m_+hl))
    return None

def draw_piece(v, pc, detail=True, font=1.0):
    off = pc['off']
    seam = pc['seam']
    P = Polygon(seam)
    Pin = P.buffer(1e-3)
    sw = 1.0 if detail else .5
    sgn = -1 if m.signed_area(seam) > 0 else 1
    if pc.get('grain') == 'auto': pc['grain'] = auto_grain(pc, P)
    # quilting lattice
    if pc.get('quilt') and detail:
        Pq = P.buffer(-.3); L = 200
        for k in range(-40, 41):
            for sg in (1, -1):
                x0 = k*6.0
                for seg in clip_lines(Pq, [(x0-L, -sg*L), (x0+L, sg*L)]):
                    poly(v, seg, off, width=.35, color=QUILT, dash=(4, 3))
    if any(e['sa'] > 0 for e in pc['edges']):
        poly(v, seam, off, closed=True, width=.5*sw, color=GREY, dash=(3, 2))
    poly(v, pc['cut'], off, closed=True, width=1.0*sw)
    # panel seams (new patchwork seams) drawn slightly heavier dashed in red
    for e in pc['edges']:
        if e.get('n') == 'panel':
            poly(v, e['pts'], off, width=.9*sw, color=RED, dash=(5, 2))
    for mk in pc['marks']:
        for seg in clip_lines(Pin, mk): poly(v, seg, off, width=.6*sw)
    for d in pc['dashed']:
        for seg in clip_lines(Pin, d): poly(v, seg, off, width=.6*sw, dash=(8, 2, 1, 2))
    # measurement guide lines (BL / WL / HL / CF ...)
    for name, gl in pc.get('guides', []):
        for seg in clip_lines(Pin, gl):
            L = LineString(seg).length
            if L < 2: continue
            poly(v, seg, off, width=.5*sw, color=DIM, dash=(8, 2, 1, 2))
            if detail:
                (x0, y0), (x1, y1) = seg[0], seg[-1]
                ang = math.degrees(math.atan2(-(y1-y0), x1-x0))
                if ang > 90: ang -= 180
                if ang <= -90: ang += 180
                mx, my = x0+(x1-x0)*.22, y0+(y1-y0)*.22
                if name in ('CF', 'CB'): my = y0 + L*.18
                text_rot(v, mx + (0.45 if abs(ang) > 45 else 0), my - (0.45 if abs(ang) <= 45 else 0),
                         f'{name} {fmt(L)}', 7.5*font, off, ang)
    if detail:
        for (x, y), t in pc.get('dartlabels', []):
            if P.contains(LineString([(x-1, y), (x+1, y)]).centroid):
                text_rot(v, x, y, t, 7.5*font, off, 0)
    if pc.get('foldline'):
        e = pc['edges'][-1]['pts']
        poly(v, e, off, width=1.6*sw, color=black, dash=(8, 2, 1, 2))
        mid = ((e[0][0]+e[-1][0])/2, (e[0][1]+e[-1][1])/2)
        if detail: text_c(v, mid[0]+1.6, mid[1]-6, ['대칭선'], 9*font, off)
    for k, cpt, ang in pc['applique']:
        T = Polygon(m.tri_at(k, cpt, ang))
        if not T.intersects(P): continue
        for seg in clip_lines(Pin, list(T.exterior.coords)):
            poly(v, seg, off, width=.8*sw, color=RED, dash=(3, 2))
        if detail and P.contains(T.centroid):
            text_c(v, T.centroid.x, T.centroid.y, ['7'+k], 7*font, off, color=RED)
    if pc.get('tri'):
        poly(v, pc['seam'], off, closed=True, width=1.0*sw, color=RED)
    if pc['grain']:
        a, b = pc['grain']
        poly(v, [a, b], off, width=.8*sw)
        hs = 1.0 if detail else 1.6
        arrow_head(v, a, b, off, hs); arrow_head(v, b, a, off, hs)
    # notches (absolute points; drawn on whichever edge they lie on)
    for pt, cnt in pc['notches']:
        best = None
        for e in pc['edges']:
            ls = LineString(e['pts']); d = ls.distance(Point(pt))
            if d < 1e-3 and (best is None or d < best[0]): best = (d, e, ls.project(Point(pt)))
        if best is None or cnt == 0: continue
        _, e, dist = best; pts = e['pts']; Lt = plen(pts); L = max(e['sa'], .6)
        for j in range(cnt):
            dd = min(max(dist + (j-(cnt-1)/2)*.5, .01), Lt-.01)
            p = at(pts, dd); q = at(pts, min(dd+.05, Lt)); r = at(pts, max(dd-.05, 0))
            tx, ty = q[0]-r[0], q[1]-r[1]; n = math.hypot(tx, ty); tx, ty = tx/n, ty/n
            nx, ny = (-ty, tx) if sgn > 0 else (ty, -tx)
            poly(v, [(p[0]-nx*.25, p[1]-ny*.25), (p[0]+nx*L, p[1]+ny*L)], off, width=1.0*sw)
    # edge lengths (finished seam-line lengths) along every edge
    if detail:
        for e in pc['edges']:
            pts = e['pts']; L = plen(pts)
            if L < 2.5 or e.get('n') == 'fold': continue
            mp = at(pts, L/2); q = at(pts, min(L/2+.3, L)); r = at(pts, max(L/2-.3, 0))
            tx, ty = q[0]-r[0], q[1]-r[1]; n = math.hypot(tx, ty); tx, ty = tx/n, ty/n
            nx, ny = (ty, -tx) if sgn > 0 else (-ty, tx)        # inward normal
            ang = math.degrees(math.atan2(-ty, tx))
            if ang > 90: ang -= 180
            if ang <= -90: ang += 180
            size = 7.5 if not pc.get('tri') else 6.5
            text_rot(v, mp[0]+nx*.75, mp[1]+ny*.75, fmt(L), size*font, off, ang)
    # labels
    if pc.get('autolabel'):
        x, y = pc['labelpt']
        lines = [t for t in pc['label'] if t]
        text_c(v, x, y, lines, 12*font, off)
    for (x, y), lines in pc['texts']:
        big = len(lines) > 1 and not pc.get('tri')
        text_c(v, x, y, lines, (13 if big else 9)*font, off)

# ------------------------------------------------------------- page 1: overview / assembly map
def page_overview(c):
    W, H = landscape(A4)
    c.setPageSize((W, H))
    s = next(1/k for k in (6, 7, 8, 9, 10) if CANVAS_W/k*CM <= W-2.4*CM and CANVAS_H/k*CM <= H-4.4*CM)
    SC = round(1/s)
    px, py = (W - CANVAS_W*s*CM)/2, H - 2.6*CM
    v = View(c, 0, 0, s, px, py)
    c.setFont('KR', 15); c.setFillColor(black)
    c.drawString(1.6*CM, H-1.35*CM, '비대칭 퀼팅 스레드 드레스 — 패턴 전체도 / 조립 지도')
    c.setFont('KR', 8.5); c.setFillColor(GREY)
    c.drawString(1.6*CM, H-1.95*CM, f'축척 1:{SC}  ·  사이즈 55 (165/84)  ·  회색 칸 = A4 실물 크기 페이지 번호 (빈 칸은 인쇄하지 않음)')
    # tiles
    used = used_tiles()
    for r in range(ROWS):
        for col in range(COLS):
            x0, y0 = col*TILE_W, r*TILE_H
            X, Y = v.p(x0, y0)
            if (r, col) in used:
                c.setFillColor(Color(.95, .95, .95)); c.setStrokeColor(LIGHT); c.setLineWidth(.6)
                c.rect(X, Y-TILE_H*s*CM, TILE_W*s*CM, TILE_H*s*CM, stroke=1, fill=1)
                c.setFillColor(Color(.62, .62, .62)); c.setFont('Helvetica-Bold', 11)
                c.drawString(X+3, Y-12, tile_name(r, col))
            else:
                c.setStrokeColor(LIGHT); c.setDash(2, 2); c.setLineWidth(.4)
                c.rect(X, Y-TILE_H*s*CM, TILE_W*s*CM, TILE_H*s*CM, stroke=1, fill=0); c.setDash()
    for pc in pieces:
        draw_piece(v, pc, detail=False, font=.55)
    # scale bar
    X, Y = v.p(0, CANVAS_H+1.6)
    c.setStrokeColor(black); c.setLineWidth(.8)
    c.line(X, Y, X+10*s*CM, Y); c.line(X, Y-3, X, Y+3); c.line(X+10*s*CM, Y-3, X+10*s*CM, Y+3)
    c.setFont('KR', 7.5); c.setFillColor(black); c.drawString(X+10*s*CM+5, Y-2.5, f'10 cm (1:{SC})')
    # legend
    lx = X + 3.4*CM
    def leg(i, label, **kw):
        xx = lx + i*3.35*CM
        c.setStrokeColor(kw.get('color', black)); c.setLineWidth(kw.get('w', .9))
        c.setDash(list(kw["dash"])) if "dash" in kw else c.setDash()
        c.line(xx, Y, xx+0.9*CM, Y); c.setDash()
        c.setFillColor(black); c.setFont('KR', 7.5); c.drawString(xx+1.05*CM, Y-2.5, label)
    leg(0, '재단선 (시접 포함)')
    leg(1, '완성선', color=GREY, dash=(3, 2), w=.6)
    leg(2, '중심선 / 대칭선', dash=(8, 2, 1, 2))
    leg(3, '아플리케 위치', color=RED, dash=(3, 2))
    leg(4, '패널 연결선', color=RED, dash=(5, 2), w=1.2)
    leg(5, '치수선', color=DIM, dash=(8, 2, 1, 2))

def used_tiles():
    from shapely.geometry import box
    out = set()
    shapes = [Polygon([(x+pc['off'][0], y+pc['off'][1]) for x, y in pc['cut']]) for pc in pieces]
    shapes.append(box(TEST_SQ[0], TEST_SQ[1], TEST_SQ[0]+5, TEST_SQ[1]+5))
    for r in range(ROWS):
        for col in range(COLS):
            b = box(col*TILE_W, r*TILE_H, (col+1)*TILE_W, (r+1)*TILE_H)
            if any(s.intersects(b) for s in shapes): out.add((r, col))
    return out

def tile_name(r, col): return f'{ROWNAMES[r]}{col+1}'

# ------------------------------------------------------------- page 2: info
def page_info(c):
    W, H = A4
    c.setPageSize((W, H))
    x = 1.8*CM; y = H - 2.0*CM
    def h(t, size=12.5, gap=.75):
        nonlocal y
        y -= gap*CM; c.setFont('KR', size); c.setFillColor(black); c.drawString(x, y, t); y -= .25*CM
        c.setStrokeColor(LIGHT); c.setLineWidth(.6); c.line(x, y, W-x, y); y -= .15*CM
    def p(t, size=8.6, indent=0, color=black):
        nonlocal y
        y -= size*1.55; c.setFont('KR', size); c.setFillColor(color); c.drawString(x+indent, y, t)
    def table(rows, widths, size=8.4):
        nonlocal y
        for i, row in enumerate(rows):
            y -= size*1.75
            if i == 0:
                c.setFillColor(Color(.94, .94, .94)); c.rect(x, y-3, sum(widths)*CM, size*1.6, stroke=0, fill=1)
            xx = x
            for t, w in zip(row, widths):
                c.setFillColor(black); c.setFont('KR', size); c.drawString(xx+3, y+1, t); xx += w*CM
    c.setFont('KR', 17); c.drawString(x, y, '비대칭 퀼팅 스레드 드레스')
    c.setFont('KR', 9); c.setFillColor(GREY)
    c.drawString(x, y-.55*CM, '원숄더 · 퀼팅 패널 + 실(얀) 메쉬 패널 · 체크 울 숄더 드레이프 · 올리브 니트 원슬리브 · 레드 삼각 아플리케')
    y -= .6*CM
    h('1. 사이즈 (한국 55 / 165-84)')
    table([['부위', '신체 치수', '패턴 완성 치수', '여유분'],
           ['가슴둘레', '84', '92', '+8 (퀼팅 두께 포함)'],
           ['허리둘레', '66', '70', '+4'],
           ['엉덩이둘레', '92', '96', '+4'],
           ['등길이', '38', '38', ''],
           ['드레스 길이 (CB)', '', '80 (허리선 아래 40)', '밑단 비대칭: 오른쪽 길고 왼쪽 짧음'],
           ['소매길이 / 손목', '', f'{m.SL} / {m.M["wrist"]}', f'소매산 {m.cap:.1f}, 이세 {m.cap_len-m.AH:.1f}cm']],
          [3.6, 2.6, 4.4, 6.8])
    h('2. 재단 목록  (모든 패턴은 겉면 기준 — 원단 겉면을 위로 하고 1장씩 재단, 뒤집지 말 것)')
    table([['번호', '패턴', '원단', '수량', '비고'],
           ['1-1~1-5', '앞판 A 패널 5장', '아이보리 퀼팅 (면 + 솜 + 면)', '각 1', '패치워크로 연결, 아플리케 위치'],
           ['2', '앞판 B', '아이보리 거즈 또는 튤 (베이스)', '1', '위에 실 장식'],
           ['3', '뒤판 왼쪽', '아이보리 퀼팅', '1', 'CB 콘솔지퍼'],
           ['4', '뒤판 오른쪽', '아이보리 퀼팅', '1', 'CB 콘솔지퍼'],
           ['5', '소매 (착용자 왼쪽)', '올리브 울 니트', '1', ''],
           ['6', '어깨 드레이프', '그린 체크 울', '1', '반쪽 패턴 → 대칭 전개, 바이어스'],
           ['7a/7b/7c', '삼각 아플리케', '레드 울 펠트', '1/2/1', '시접 없음'],
           ['-', '네크라인 바이어스', '레드 또는 아이보리', '1', f'폭 4cm x {math.ceil(m.neck_total+4)}cm']],
          [1.8, 3.4, 5.2, 1.4, 5.6])
    p('치수 표기: 파란 숫자 = 각 선의 완성선 길이(cm) · BL/WL/HL/CF 선의 숫자 = 그 조각의 해당 위치 너비(다트 포함)', indent=0)
    p('시접: 기본 1cm · 밑단 2cm · CB(지퍼) 2cm · 소매단 2.5cm · 네크라인 0 (바이어스로 감쌈) — 패턴에 포함되어 있음', indent=0)
    p('부자재: 콘솔지퍼 45cm 1개, 실 장식용 얀(레드·오렌지·머스터드·아이보리) 다량, 레드 지그재그 스티치용 실', indent=0)
    h('3. 봉제 순서')
    steps = ['① 퀼팅 원단에 패턴을 놓고 재단 (점선 격자 = 6cm 다이아 퀼팅 가이드). 다트를 박는다 (패널선을 지나는 다트는 패널 연결 후 이어 박기).',
             '② 앞판 A 패널 연결: A-1+A-2 → A-4+A-5 → 위·중·아래(A-3) 순서로 빨간 점선(패널선)끼리 너치 맞춰 봉제.',
             '   이어진 앞판 A에 삼각 아플리케(7a·7b·7c)를 올리고 레드 실 지그재그 새틴 스티치로 고정.',
             '③ 앞판 B 베이스에 얀을 루프/크로셰 메쉬로 손바느질 고정, 일부는 밑단 아래로 길게(바닥까지) 늘어뜨림.',
             '④ 앞판 A + B 스타일선 연결 (BP·허리 너치 맞춤) → 솔기 위 레드 지그재그 장식 스티치.',
             '⑤ 뒤판 CB에 콘솔지퍼(너치까지) 달고 아래는 박음. 왼쪽 어깨선 · 양 옆선 봉제.',
             '⑥ 네크라인(앞 오른쪽 옆선 → 왼쪽 어깨 → 뒤 → 오른쪽 옆선) 바이어스로 감싸 처리. 오른쪽 윗선은 본 1~2개 권장.',
             '⑦ 소매: 소매산 이세 처리 후 왼쪽 진동에 달기 (앞 너치 1개, 뒤 너치 2개, SP 맞춤).',
             '⑧ 드레이프: 양 끝 셔링 10cm로 줄여 앞·뒤 진동 솔기 위에 고정, SP 너치를 어깨점에 맞추고 주름을 잡아 손바느질.',
             '⑨ 밑단 2cm 접어 마무리 → 밑단 레드 지그재그 스티치.']
    for t in steps: p(t, size=8.4)
    h('4. 인쇄 · 조립 방법')
    for t in ['- 3페이지부터 실물 크기 A4입니다. 인쇄 시 반드시 "실제 크기 / 100%" 선택 (페이지 맞춤 해제).',
              '- A1 페이지의 5cm × 5cm 테스트 사각형을 자로 확인한 뒤 나머지를 인쇄하세요.',
              '- 각 페이지의 오른쪽 · 아래 여백을 회색 테두리선에서 잘라내고, 옆 페이지 테두리선에 맞춰 붙입니다.',
              f'- 페이지 번호(A1~{ROWNAMES[ROWS-1]}{COLS})와 가장자리의 ◆ 표시를 1페이지 조립 지도에 맞춰 배치합니다.',
              '- 이 패턴은 디자인 이미지를 바탕으로 한 시작용 패턴입니다 — 광목 가봉(토일) 후 핏을 조정하세요.']:
        p(t, size=8.4)

# ------------------------------------------------------------- tile pages
def page_tile(c, r, col, used):
    W, H = A4
    c.setPageSize((W, H))
    x0, y0 = col*TILE_W, r*TILE_H
    px, py = MARGIN*CM, H - MARGIN*CM
    v = View(c, x0, y0, 1.0, px, py)
    name = tile_name(r, col)
    # watermark
    c.setFillColor(Color(.93, .93, .93)); c.setFont('Helvetica-Bold', 120)
    c.drawCentredString(W/2, H/2-40, name)
    c.saveState()
    pth = c.beginPath(); pth.rect(px, py-TILE_H*CM, TILE_W*CM, TILE_H*CM); c.clipPath(pth, stroke=0, fill=0)
    for pc in pieces:
        b = pc['bbox']; ox, oy = pc['off']
        if b[2]+ox < x0 or b[0]+ox > x0+TILE_W or b[3]+oy < y0 or b[1]+oy > y0+TILE_H: continue
        draw_piece(v, pc, detail=True)
    # test square + title block on canvas
    tx, ty = TEST_SQ
    X, Y = v.p(tx, ty)
    c.setStrokeColor(black); c.setLineWidth(.8); c.rect(X, Y-5*CM, 5*CM, 5*CM)
    c.setFont('KR', 8); c.setFillColor(black)
    c.drawCentredString(X+2.5*CM, Y-2.4*CM, '5cm × 5cm')
    c.drawCentredString(X+2.5*CM, Y-2.9*CM, '테스트 사각형')
    X, Y = v.p(*TITLE_AT)
    c.setFont('KR', 13); c.drawString(X, Y-14, '비대칭 퀼팅 스레드 드레스')
    c.setFont('KR', 9); c.setFillColor(GREY)
    for i, t in enumerate(['사이즈 55 (165/84) · 실물 크기 1:1',
                           '시접 포함: 기본 1 · 밑단 2 · CB 2 · 소매단 2.5 · 네크라인 0',
                           '너치: 앞 1개 / 뒤 2개   ↕ = 식서(올) 방향']):
        c.drawString(X, Y-32-i*13, t)
    c.restoreState()
    # border + labels
    c.setStrokeColor(GREY); c.setLineWidth(.4); c.rect(px, py-TILE_H*CM, TILE_W*CM, TILE_H*CM)
    c.setFont('Helvetica-Bold', 10); c.setFillColor(black)
    c.drawString(px+4, py-13, name)
    c.setFont('KR', 6.5); c.setFillColor(GREY)
    c.drawString(px, 0.45*CM, f'{name}  ·  행 {ROWNAMES[r]} / 열 {col+1}  ·  100% 실제 크기로 인쇄  ·  오른쪽·아래 여백을 테두리선에서 잘라 붙이기')
    # neighbour markers (diamonds on edges)
    def diamond(X, Y, label, ha):
        c.setFillColor(black)
        pth = c.beginPath(); pth.moveTo(X, Y+5); pth.lineTo(X+5, Y); pth.lineTo(X, Y-5); pth.lineTo(X-5, Y); pth.close()
        c.drawPath(pth, stroke=0, fill=1)
        c.setFont('Helvetica-Bold', 7)
        if ha == 'r': c.drawRightString(X-7, Y-2.5, label)
        elif ha == 'l': c.drawString(X+7, Y-2.5, label)
        else: c.drawCentredString(X, Y+(8 if ha == 'u' else -14), label)
    if col < COLS-1: diamond(px+TILE_W*CM, py-TILE_H*CM/2, tile_name(r, col+1), 'r')
    if col > 0: diamond(px, py-TILE_H*CM/2, tile_name(r, col-1), 'l')
    if r < ROWS-1: diamond(px+TILE_W*CM/2, py-TILE_H*CM, tile_name(r+1, col), 'u')
    if r > 0: diamond(px+TILE_W*CM/2, py, tile_name(r-1, col), 'd')

def build(path):
    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle('비대칭 퀼팅 스레드 드레스 패턴 (A4)')
    page_overview(c); c.showPage()
    page_info(c); c.showPage()
    used = used_tiles()
    for r in range(ROWS):
        for col in range(COLS):
            if (r, col) in used:
                page_tile(c, r, col, used); c.showPage()
    c.save()
    return len(used)

if __name__ == '__main__':
    n = build('dress_pattern_A4.pdf')
    print('tiles', n)
