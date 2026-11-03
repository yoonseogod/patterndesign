"""Asymmetric quilted thread dress - pattern generator (size 55, KR 165/84).
All geometry in cm, y axis points DOWN (drafting convention)."""
import math
from shapely.geometry import LineString, Polygon, Point
from shapely.ops import substring
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import Color, black, white

pdfmetrics.registerFont(TTFont('KR', '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', subfontIndex=0))
CM = 28.3464567

# ---------------------------------------------------------------- curves
def cr(pts, n=24):
    """Catmull-Rom spline through pts."""
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i-1], P[i], P[i+1], P[i+2]
        for k in range(n):
            t = k / n
            t2, t3 = t*t, t*t*t
            out.append(tuple(0.5*((2*p1[j]) + (-p0[j]+p2[j])*t + (2*p0[j]-5*p1[j]+4*p2[j]-p3[j])*t2
                                  + (-p0[j]+3*p1[j]-3*p2[j]+p3[j])*t3) for j in (0, 1)))
    out.append(tuple(pts[-1]))
    return out

def bez(p0, c1, c2, p1, n=40):
    out = []
    for k in range(n+1):
        t = k/n; u = 1-t
        out.append(tuple(u**3*p0[j] + 3*u*u*t*c1[j] + 3*u*t*t*c2[j] + t**3*p1[j] for j in (0, 1)))
    return out


def _unit(v):
    n = math.hypot(*v); return (v[0]/n, v[1]/n)
def square_end(pts, at_start, seam_dir, blend=4.0):
    """Re-shape the first/last `blend` cm of a curve so it meets the adjoining seam at 90 deg."""
    if not at_start:
        return list(reversed(square_end(list(reversed(pts)), True, seam_dir, blend)))
    p0 = pts[0]; L = plen(pts); blend = min(blend, L*.4)
    q = at(pts, blend); q2 = at(pts, blend+.3)
    sd = _unit(seam_dir)
    perp = (-sd[1], sd[0])
    if perp[0]*(q[0]-p0[0]) + perp[1]*(q[1]-p0[1]) < 0: perp = (-perp[0], -perp[1])
    tq = _unit((q2[0]-q[0], q2[1]-q[1])); k = blend/3
    head = bez(p0, (p0[0]+perp[0]*k, p0[1]+perp[1]*k), (q[0]-tq[0]*k, q[1]-tq[1]*k), q, 20)
    tail = list(substring(LineString(pts), blend, L).coords)
    return head + tail[1:]
def sdir(pts, at_start=True):
    a, b = (pts[0], pts[3]) if at_start else (pts[-1], pts[-4])
    return (b[0]-a[0], b[1]-a[1])

def line(a, b, n=2):
    return [(a[0]+(b[0]-a[0])*k/(n-1), a[1]+(b[1]-a[1])*k/(n-1)) for k in range(n)]

def plen(pts): return LineString(pts).length
def at(pts, d):
    p = LineString(pts).interpolate(d); return (p.x, p.y)
def rev(p): return list(reversed(p))
def mirror(pts): return [(-x, y) for x, y in pts]

def split_at_x(pts, x0):
    """split polyline at first crossing of x=x0"""
    for i in range(len(pts)-1):
        a, b = pts[i], pts[i+1]
        if (a[0]-x0)*(b[0]-x0) <= 0 and a[0] != b[0]:
            t = (x0-a[0])/(b[0]-a[0]); p = (x0, a[1]+t*(b[1]-a[1]))
            return pts[:i+1]+[p], [p]+pts[i+1:]
    raise ValueError

# ---------------------------------------------------------------- measurements
M = dict(B=84, W=66, H=92, back_len=38, waist_hip=18, sleeve=62, wrist=22)

# ---------------------------------------------------------------- front (full, x>0 = wearer's LEFT)
SNP_F = (7.0, 0.0)
SP_F = (SNP_F[0]+12.5*math.cos(math.radians(22)), 12.5*math.sin(math.radians(22)))
UA_F = (23.5, 21.0)
W_F, HIP_F = (21.5, 42.0), (24.5, 60.0)
BP = (9.0, 26.0)
def hem_f(x):
    return 87 + (x+25)/19*3 if x <= -6 else 90 - (x+6)/31*11
HEMSIDE = 25.0

front_arm = cr([SP_F, (17.3, 10), (17.0, 14), (18.3, 18), (20.5, 20.4), UA_F])
front_arm = square_end(front_arm, True, (SNP_F[0]-SP_F[0], SNP_F[1]-SP_F[1]), 3.5)
TOP_R = (-23.5, 22.5)                 # right side top (one-shoulder edge)
neck_f = cr([TOP_R, (-16, 20.2), (-8, 16.6), (0, 11.6), (4.5, 6.0), SNP_F], 30)
neck_fB, neck_fA = split_at_x(neck_f, -7.5)
T = neck_fA[0]

def side_seam(top, w, hip, hem):
    return line(top, w, 12)[:-1] + cr([w, (w[0]+1.1*(1 if w[0]>0 else -1), w[1]+6),
                                         (hip[0]-0.6*(1 if w[0]>0 else -1), hip[1]-6), hip, hem])
side_L = side_seam(UA_F, W_F, HIP_F, (HEMSIDE, hem_f(HEMSIDE)))
side_R = side_seam(TOP_R, (-21.5, 42), (-24.5, 60), (-HEMSIDE, hem_f(-HEMSIDE)))

HB = (-10.5, hem_f(-10.5))
BPR = (-9.0, 26.0)
style_up = cr([(-9, 30), BPR, (-8.4, 21), T], 20)[20:]   # BP -> T
def style_lower(leg_x):
    return cr([HB, (-9.8, 68), (-9, 56), (leg_x, 42), (-8.7 if leg_x > -9 else -9.3, 31), BPR], 20)
style_A = style_lower(-7.25) + style_up[1:]      # HB -> T
style_B = style_lower(-10.75) + style_up[1:]

hem_A = cr([(HEMSIDE, hem_f(HEMSIDE)), (20.5, 79.3), (8, 84.6), (-6, 90)]) + [HB]
hem_B = cr([HB, (-20.5, 87.1), (-HEMSIDE, hem_f(-HEMSIDE))])

def side_dart(side, top_dist, tipx):
    a = at(side, top_dist); b = at(side, top_dist+3)
    return [a, (tipx, 26.6), b]

pieces = []
def piece(name, edges, **kw):
    d = dict(name=name, edges=edges, marks=[], texts=[], grain=None, notches=[], dashed=[], quilt=False, applique=[], guides=[], dartlabels=[])
    d.update(kw); pieces.append(d); return d

# Front A: T -> SNP -> SP -> UA -> side -> hem -> style -> T
FA = piece('1  앞판 A', [
    dict(pts=neck_fA, sa=0, n='neck'),
    dict(pts=line(SNP_F, SP_F), sa=1),
    dict(pts=front_arm, sa=1, n='arm'),   # SP->UA
    dict(pts=side_L, sa=1),
    dict(pts=hem_A, sa=2),
    dict(pts=style_A, sa=1),
], quilt=True)
FA['marks'] = [side_dart(side_L, 5, 11.5),
               [(9-1.75, 42), (9, 28), (9+1.75, 42), (9, 56), (9-1.75, 42)]]
FA['dashed'] = [[(0, 11.6), (0, 90)]]
FA['grain'] = ((3.5, 35), (3.5, 72))
FA['texts'] = [((12.5, 47), ['1  앞판 A', '아이보리 퀼팅 x1', '(겉면 위로, 1장)']),
               ((0.6, 84), ['CF'])]
FA['applique'] = [('a', (-3.4, 23.5), 200), ('b', (-4.6, 50), 180), ('b', (-3.2, 72), 15), ('c', (14, 70), 0)]

FB = piece('2  앞판 B', [
    dict(pts=neck_fB, sa=0, n='neck'),      # TOP_R -> T
    dict(pts=rev(style_B), sa=1),           # T -> HB
    dict(pts=hem_B, sa=2),                  # HB -> right hem
    dict(pts=rev(side_R), sa=1),            # -> TOP_R
])
FB['marks'] = [side_dart(rev(rev(side_R)), 4, -11.5)]
FB['grain'] = ((-12.8, 34), (-12.8, 76))
FB['texts'] = [((-17.5, 50), ['2  앞판 B', '거즈/튤 베이스 x1', '+ 실 장식 손바느질'])]

# ---------------------------------------------------------------- back
SNP_B = (7.3, 0.0)
SP_B = (SNP_B[0]+12.5*math.cos(math.radians(18)), 12.5*math.sin(math.radians(18)))   # = front shoulder (quilting cannot be eased)
UA_B = (22.5, 21.0)
back_arm = cr([SP_B, (18.6, 9.5), (18.4, 14), (19.4, 18.2), (20.8, 20.4), UA_B])
def hem_b(x): return 80 - x/24*4
CBN = 15.0
neck_bL = bez((0, CBN), (3.5, CBN), (6.2, 6), SNP_B)
neck_bR = bez((0, CBN), (-6, CBN), (-17, 22.2), (-22.5, 22.5))
side_bL = side_seam(UA_B, (20.5, 39), (23.5, 57), (24, hem_b(24)))
back_arm = square_end(back_arm, True, (SNP_B[0]-SP_B[0], SNP_B[1]-SP_B[1]), 3.5)
back_arm = square_end(back_arm, False, sdir(side_bL), 4.0)
side_bR = side_seam((-22.5, 22.5), (-20.5, 39), (-23.5, 57), (-24, hem_b(-24)))

BL = piece('3  뒤판 왼쪽', [
    dict(pts=line((0, CBN), (0, hem_b(0))), sa=2, n='cb'),
    dict(pts=cr([(0, 80), (10, 78.35), (19.5, 76.25), (24, 76)]), sa=2),
    dict(pts=rev(side_bL), sa=1),
    dict(pts=back_arm, sa=1, n='arm'),   # UA? -> no: back_arm SP->UA ; we need UA->SP
    dict(pts=line(SP_B, SNP_B), sa=1),
    dict(pts=rev(neck_bL), sa=0, n='neck'),
])
BL['edges'][3]['pts'] = rev(back_arm)
BL['marks'] = [[(10-1.75, 39.6), (10, 22), (10+1.75, 39.6), (10, 55), (10-1.75, 39.6)]]
BL['grain'] = ((5, 30), (5, 68))
BL['texts'] = [((15.5, 62), ['3  뒤판 왼쪽', '퀼팅 x1', '(겉면 위로)']),
               ((1.6, 46), ['CB'])]
BL['quilt'] = True

BR = piece('4  뒤판 오른쪽', [
    dict(pts=neck_bR, sa=0, n='neck'),
    dict(pts=side_bR, sa=1),
    dict(pts=cr([(-24, 84), (-19.5, 83.75), (-10, 81.65), (0, 80)]), sa=2),
    dict(pts=line((0, hem_b(0)), (0, CBN)), sa=2, n='cb'),
])
BR['marks'] = [[(-10-1.75, 39.6), (-10, 22), (-10+1.75, 39.6), (-10, 55), (-10-1.75, 39.6)]]
BR['grain'] = ((-5, 32), (-5, 70))
BR['texts'] = [((-15.5, 62), ['4  뒤판 오른쪽', '퀼팅 x1', '(겉면 위로)']), ((-2.6, 46), ['CB'])]
BR['quilt'] = True

# zipper stop notch on both CB
ZIP_END = 58.0

# ---------------------------------------------------------------- sleeve (wearer's left only)
FAH, BAH = plen(front_arm), plen(back_arm)
AH = FAH + BAH
cap = round(AH/3, 1)
def sleeve_build(cap):
    bwF = math.sqrt((FAH-0.3)**2 - cap**2)
    bwB = math.sqrt((BAH+0.3)**2 - cap**2)
    top = (0, 0); F0 = (bwF, cap); B0 = (-bwB, cap)
    def along(p0, p1, f, off):
        x = p0[0]+(p1[0]-p0[0])*f; y = p0[1]+(p1[1]-p0[1])*f
        L = math.hypot(p1[0]-p0[0], p1[1]-p0[1]); nx, ny = (p1[1]-p0[1])/L, -(p1[0]-p0[0])/L
        # normal pointing away from sleeve centre (upwards/outwards)
        cx, cy = 0, cap
        if (x+nx-cx)**2+(y+ny-cy)**2 < (x-cx)**2+(y-cy)**2: nx, ny = -nx, -ny
        return (x+nx*off, y+ny*off)
    pts = [B0, along(B0, top, .25, -0.4), along(B0, top, .5, 0.4), along(B0, top, .78, 0.8),
           (-1.8, 0.1), top, (1.8, 0.1), along(F0, top, .78, 0.8), along(F0, top, .5, 0.0),
           along(F0, top, .25, -1.2), F0]
    return cr(pts, 20), bwF, bwB
capc, bwF, bwB = sleeve_build(cap)
capc = square_end(capc, True, (-M['wrist']/2-(-bwB), M['sleeve']-cap), 4.5)     # back underarm
capc = square_end(capc, False, (M['wrist']/2-bwF, M['sleeve']-cap), 4.5)       # front underarm
cap_len = plen(capc)
WR = M['wrist']/2
SL = M['sleeve']
SLV = piece('5  소매', [
    dict(pts=capc, sa=1, n='cap'),                     # back bicep -> front bicep
    dict(pts=line((bwF, cap), (WR, SL)), sa=1),
    dict(pts=line((WR, SL), (-WR, SL)), sa=2.5),
    dict(pts=line((-WR, SL), (-bwB, cap)), sa=1),
])
SLV['dashed'] = [[(-bwB, cap), (bwF, cap)], [(-(bwB+WR)/2, 34), ((bwF+WR)/2, 34)]]
SLV['grain'] = ((0, 8), (0, 54))
SLV['texts'] = [((6.2, 24), ['5  소매 (왼쪽만)', '올리브 니트 x1']), ((5.5, cap-0.6), ['F →']),
                ((-6.5, cap-0.6), ['← B']), ((6, 33.4), ['EL'])]

# ---------------------------------------------------------------- plaid drape (bias) - HALF pattern, mirror at centre
DR_L, DR_E = 72, 20
dr_top = cr([(36, -9), (54, -6.5), (DR_L, 0)])
dr_bot = cr([(DR_L, DR_E), (54, 23.5), (36, 25)])
DRP = piece('6  어깨 드레이프', [
    dict(pts=dr_top, sa=1), dict(pts=line((DR_L, 0), (DR_L, DR_E)), sa=1),
    dict(pts=dr_bot, sa=1), dict(pts=line((36, 25), (36, -9)), sa=0, n='fold'),
])
DRP['grain'] = ((39, 10), (49, 0))
DRP['texts'] = [((52.5, 12.5), ['6  어깨 드레이프 (반쪽)', '체크 울 x1 · 바이어스', '중심선 기준 대칭 전개']),
                ((DR_L-3.6, 10), ['셔링', '→10cm']), ((38.2, 21.6), ['SP'])]
DRP['marks'] = [[(DR_L-1.2, 1.5), (DR_L-1.2, DR_E-1.5)]]
DRP['foldline'] = True

# ---------------------------------------------------------------- applique triangles (no SA)
TRI = {'a': [(0, 0), (9, 0), (4.5, -7.8)], 'b': [(0, 0), (12, 0), (6, -9)], 'c': [(0, 0), (14, 0), (0, -10)]}
def tri_at(k, c, ang):
    pts = TRI[k]; cx = sum(p[0] for p in pts)/3; cy = sum(p[1] for p in pts)/3
    a = math.radians(ang)
    return [(c[0]+(x-cx)*math.cos(a)-(y-cy)*math.sin(a), c[1]+(x-cx)*math.sin(a)+(y-cy)*math.cos(a)) for x, y in pts]
TRIS = []
for k, cnt in (('a', 1), ('b', 2), ('c', 1)):
    t = piece(f'7{k}  아플리케 {k}', [dict(pts=line(TRI[k][i], TRI[k][(i+1) % 3]), sa=0) for i in range(3)])
    t['texts'] = [((sum(p[0] for p in TRI[k])/3, sum(p[1] for p in TRI[k])/3+0.2), [f'7{k}', f'x{cnt}'])]
    t['tri'] = True
    TRIS.append(t)

# ---------------------------------------------------------------- seam allowance
def signed_area(pts):
    return 0.5*sum(pts[i][0]*pts[i+1][1]-pts[i+1][0]*pts[i][1] for i in range(len(pts)-1))

def extend(pts, L=12):
    (x0, y0), (x1, y1) = pts[0], pts[1]
    d = math.hypot(x1-x0, y1-y0); s = (x0-(x1-x0)/d*L, y0-(y1-y0)/d*L)
    (x0, y0), (x1, y1) = pts[-1], pts[-2]
    d = math.hypot(x1-x0, y1-y0); e = (x0-(x1-x0)/d*L, y0-(y1-y0)/d*L)
    return [s]+list(pts)+[e]

def compute(pc):
    seam = []
    for e in pc['edges']:
        seam += e['pts'] if not seam else e['pts'][1:]
    pc['seam'] = seam
    sgn = -1 if signed_area(seam) > 0 else 1   # outward offset sign
    offs = []
    for e in pc['edges']:
        ls = LineString(e['pts'])
        if e['sa'] == 0:
            o = ls
        else:
            o = ls.offset_curve(sgn*e['sa'], join_style='mitre', mitre_limit=4)
            if o.geom_type != 'LineString':
                o = max(o.geoms, key=lambda g: g.length)
        offs.append(LineString(extend(list(o.coords))))
    n = len(offs); P = []
    for i in range(n):
        a, b = offs[i], offs[(i+1) % n]
        corner = Point(pc['edges'][i]['pts'][-1])
        x = a.intersection(b)
        cands = []
        if not x.is_empty:
            for g in getattr(x, 'geoms', [x]):
                if g.geom_type == 'Point': cands.append(g)
        p = min(cands, key=lambda g: g.distance(corner)) if cands else Point(a.coords[-2])
        P.append(p)
    cut = []
    for i in range(n):
        o = offs[i]; d0 = o.project(P[i-1]); d1 = o.project(P[i])
        cut += list(substring(o, d0, d1).coords)
    pc['cut'] = cut
    xs = [p[0] for p in cut]; ys = [p[1] for p in cut]
    pc['bbox'] = (min(xs), min(ys), max(xs), max(ys))

# notches are stored as absolute points (survive panel splitting)
def add_notch(pc, ei, dist, cnt=1):
    pc['notches'].append((at(pc['edges'][ei]['pts'], dist), cnt))
add_notch(FA, 2, plen(front_arm)-8, 1)          # 8cm above UA
add_notch(BL, 3, plen(back_arm)-9, 2)
add_notch(SLV, 0, cap_len - 8.3, 1)              # 8.3 from front bicep
add_notch(SLV, 0, 9.3, 2)                        # 9.3 from back bicep
add_notch(SLV, 0, cap_len*(BAH/AH)+0.3, 1)       # shoulder point
add_notch(BL, 0, ZIP_END-CBN, 1); add_notch(BR, 3, (hem_b(0)-ZIP_END), 1)
add_notch(FA, 5, plen(style_A)-plen(style_up), 1)   # BP
add_notch(FB, 1, plen(style_up), 1)
add_notch(FA, 5, plen(style_A)-plen(style_up)-16, 2)
add_notch(FB, 1, plen(style_up)+16, 2)

# ---------------------------------------------------------------- measurement guides & dart labels
FA['dashed'] = []
FA['guides'] = [('BL', [(-30, 26), (40, 26)]), ('WL', [(-30, 42), (40, 42)]), ('HL', [(-30, 60), (40, 60)]),
                ('CF', [(0, -5), (0, 100)])]
FA['dartlabels'] = [((12.4, 45.5), '다트 3.5'), ((17.2, 29.6), '다트 3.0')]
FB['guides'] = [('BL', [(-30, 26), (0, 26)]), ('WL', [(-30, 42), (0, 42)]), ('HL', [(-30, 60), (0, 60)])]
FB['dartlabels'] = [((-18.5, 30.6), '다트 3.0')]
BL['guides'] = [('BL', [(0, 23), (30, 23)]), ('WL', [(0, 39.6), (30, 39.6)]), ('HL', [(0, 57), (30, 57)])]
BL['dartlabels'] = [((13.6, 43), '다트 3.5')]
BR['guides'] = [('BL', [(-30, 23), (0, 23)]), ('WL', [(-30, 39.6), (0, 39.6)]), ('HL', [(-30, 57), (0, 57)])]
BR['dartlabels'] = [((-13.6, 43), '다트 3.5')]
SLV['dashed'] = []
SLV['guides'] = [('소매통', [(-40, cap), (40, cap)]), ('EL', [(-40, 34), (40, 34)])]
SLV['texts'] = [((6.2, 24), ['5  소매 (왼쪽만)', '올리브 니트 x1', f'소매길이 {SL} · 소매산 {cap:.1f}']),
                ((5.5, cap-0.6), ['F →']), ((-6.5, cap-0.6), ['← B'])]
DRP['texts'] = [((52.5, 12.5), ['6  어깨 드레이프 (반쪽)', '체크 울 x1 · 바이어스', '중심선 기준 대칭 전개']),
                ((DR_L-3.6, 10), ['셔링', '→10cm']), ((38.2, 21.6), ['SP'])]

# ---------------------------------------------------------------- split front A into patchwork panels
def split_piece(pc, p0, p1, tag):
    segs = []
    for ei, e in enumerate(pc['edges']):
        P = e['pts']
        for i in range(len(P)-1):
            if math.dist(P[i], P[i+1]) > 1e-9: segs.append((P[i], P[i+1], e['sa'], ei))
    L = LineString([p0, p1]); hits = []
    for k, (a, b, sa, ei) in enumerate(segs):
        x = LineString([a, b]).intersection(L)
        if x.geom_type == 'Point':
            q = (x.x, x.y)
            if not any(math.dist(q, h[2]) < 1e-6 for h in hits):
                hits.append((k, math.dist(a, q), q))
    assert len(hits) == 2, (pc['name'], hits)
    (k1, _, q1), (k2, _, q2) = sorted(hits)
    def segs_between(ka, qa, kb, qb):
        out = [(qa, segs[ka][1], segs[ka][2], segs[ka][3])]
        k = (ka+1) % len(segs)
        while k != kb:
            out.append(segs[k]); k = (k+1) % len(segs)
        out.append((segs[kb][0], qb, segs[kb][2], segs[kb][3]))
        return [s for s in out if math.dist(s[0], s[1]) > 1e-6]
    def to_edges(ss, close_from, close_to):
        edges = []
        for a, b, sa, ei in ss:
            if edges and edges[-1]['_id'] == ei:
                edges[-1]['pts'].append(b)
            else:
                edges.append(dict(pts=[a, b], sa=sa, _id=ei, n=pc['edges'][ei].get('n')))
        edges.append(dict(pts=[close_from, close_to], sa=1, _id=('cut', tag), n='panel'))
        return edges
    out = []
    for ss, cf, ct in ((segs_between(k1, q1, k2, q2), q2, q1), (segs_between(k2, q2, k1, q1), q1, q2)):
        d = {k: v for k, v in pc.items() if k not in ('edges', 'seam', 'cut', 'bbox')}
        d['edges'] = to_edges(ss, cf, ct)
        d['notches'] = list(pc['notches']) + [(((q1[0]+q2[0])/2, (q1[1]+q2[1])/2), tag)]
        out.append(d)
    return out

def centroid(pc):
    pts = [p for e in pc['edges'] for p in e['pts']]
    return Polygon(pts).centroid

# ================================================================ FRONT REBUILD
# Darts are moved INTO seams (no dart is cut by a panel line):
#  - left : side bust dart -> armhole, then armhole princess line through BP absorbs both darts
#  - right: side bust dart -> style line (A/B seam) through BP
def rot(pts, c, ang):
    ca, sa_ = math.cos(ang), math.sin(ang)
    return [(c[0]+(x-c[0])*ca-(y-c[1])*sa_, c[1]+(x-c[0])*sa_+(y-c[1])*ca) for x, y in pts]
def angle_to(c, p): return math.atan2(p[1]-c[1], p[0]-c[0])
def sub(pts, d0, d1): return list(substring(LineString(pts), d0, d1).coords)

pieces.remove(FA); pieces.remove(FB)
BPL = (9.0, 26.0)
W1, W2, DT = (7.25, 42.0), (10.75, 42.0), (9.0, 56.0)
# left armhole princess point: 9cm above UA on the armhole
FAL = plen(front_arm); AP = at(front_arm, FAL-9)
arm_c = sub(front_arm, 0, FAL-9)                 # SP -> AP   (centre panel)
arm_s = sub(front_arm, FAL-9, FAL)               # AP -> UA   (side panel, rotated)
S1, S2 = at(side_L, 5), at(side_L, 8)
phiL = angle_to(BPL, S2) - angle_to(BPL, S1)
arm_s_r = rot(arm_s, BPL, phiL); UA_r = arm_s_r[-1]; AP_r = arm_s_r[0]
hem_side, hem_rest = split_at_x(hem_A, 9.5); HL = hem_side[-1]   # (25,79)->HL , HL->...->HB
prin_c = cr([AP, BPL, W1, DT, HL], 24)           # AP -> HL  (centre panel edge)
prin_s = cr([AP_r, BPL, W2, DT, HL], 24)         # AP'-> HL  (side panel edge)
side_s = side_seam(UA_r, W_F, HIP_F, (HEMSIDE, hem_f(HEMSIDE)))
arm_s_r = square_end(arm_s_r, False, sdir(side_s), 4.0)

CEN = piece('1  앞 중심판', [
    dict(pts=neck_fA, sa=0, n='neck'),            # T -> SNP
    dict(pts=line(SNP_F, SP_F), sa=1),
    dict(pts=arm_c, sa=1, n='arm'),               # SP -> AP
    dict(pts=prin_c, sa=1, n='princess'),         # AP -> HL
    dict(pts=hem_rest, sa=2),                     # HL -> HB
    dict(pts=style_A, sa=1, n='style'),           # HB -> T
], quilt=True)
SIDE = piece('1  앞 옆판', [
    dict(pts=arm_s_r, sa=1, n='arm'),             # AP' -> UA'
    dict(pts=side_s, sa=1),                       # UA' -> hem
    dict(pts=hem_side, sa=2),                     # hem side -> HL
    dict(pts=rev(prin_s), sa=1, n='princess'),    # HL -> AP'
], quilt=True)

# right: close side dart of B by rotating its top wedge about BPR -> dart goes into style line
S1r, S2r = at(side_R, 4), at(side_R, 7)
phiR = angle_to(BPR, S2r) - angle_to(BPR, S1r)
neck_B_r = rot(neck_fB, BPR, phiR)               # TOP_R' -> T'
up_B_r = rot(style_up, BPR, phiR)                # BPR -> T'
TOP_Rr = neck_B_r[0]
low_B = style_lower(-10.75)                       # HB -> BPR
side_Rn = side_seam(TOP_Rr, (-21.5, 42), (-24.5, 60), (-HEMSIDE, hem_f(-HEMSIDE)))
neck_B_r = square_end(neck_B_r, True, sdir(side_Rn), 5.0)
hem_B = square_end(hem_B, True, sdir(low_B), 4.0)
FBN = piece('2  앞판 B', [
    dict(pts=neck_B_r, sa=0, n='neck'),
    dict(pts=rev(up_B_r) + rev(low_B)[1:], sa=1, n='style'),   # T' -> BPR -> HB
    dict(pts=hem_B, sa=2),
    dict(pts=rev(side_Rn), sa=1),
])
FBN['grain'] = 'auto'; FBN['autolabel'] = True
FBN['label'] = ['2  앞판 B', '거즈/튤 베이스 x1', '+ 실 장식 손바느질']
FBN['guides'] = [('WL', [(-30, 42), (0, 42)]), ('HL', [(-30, 60), (0, 60)])]
FBN['notches'] = [(BPR, 1), (at(low_B, plen(low_B)-16), 2)]

CEN['guides'] = [('BL', [(-30, 26), (40, 26)]), ('WL', [(-30, 42), (40, 42)]),
                 ('HL', [(-30, 60), (40, 60)]), ('CF', [(0, -5), (0, 100)])]
CEN['applique'] = FA['applique']
CEN['notches'] = [(BPR, 1), (at(style_A, plen(style_A)-plen(style_up)-16), 2), (BPL, 1), (W1, 2)]
SIDE['guides'] = [('WL', [(0, 42), (40, 42)]), ('HL', [(0, 60), (40, 60)])]
SIDE['applique'] = FA['applique']
SIDE['notches'] = [(BPL, 1), (W2, 2), (at(arm_s_r, plen(arm_s_r)-8), 1)]

# ---- patchwork panel lines (no darts inside the panels any more)
L1 = ((-14, 46.5), (32, 31.5))
L2 = ((-14, 62.0), (12, 69.0))
c_up, c_rest = sorted(split_piece(CEN, *L1, 1), key=lambda p: centroid(p).y)
c_mid, c_low = sorted(split_piece(c_rest, *L2, 2), key=lambda p: centroid(p).y)
# side panel: L1 must hit the princess seam at the SAME distance from the armhole as on the centre panel
_xc = LineString(prin_c).intersection(LineString(L1))
d_c = LineString(prin_c).project(_xc)
Qs = at(prin_s, d_c)
_xs = LineString(side_s).intersection(LineString(L1)); Xs = (_xs.x, _xs.y)
_dx, _dy = Xs[0]-Qs[0], Xs[1]-Qs[1]; _n = math.hypot(_dx, _dy); _dx, _dy = _dx/_n, _dy/_n
L1s = ((Qs[0]-3*_dx, Qs[1]-3*_dy), (Xs[0]+3*_dx, Xs[1]+3*_dy))
s_up, s_low = sorted(split_piece(SIDE, *L1s, 1), key=lambda p: centroid(p).y)
pieces.remove(CEN); pieces.remove(SIDE)
FRONT_PANELS = [('1-1', '앞 중심 상단', c_up), ('1-2', '앞 중심 중단', c_mid), ('1-3', '앞 중심 하단', c_low),
                ('1-4', '앞 옆판 상단', s_up), ('1-5', '앞 옆판 하단', s_low)]
for code, nm, p in FRONT_PANELS:
    p['name'] = f'{code}  {nm}'
    p['label'] = [f'{code}  {nm}', '퀼팅 x1 (겉면 위로)']
    p['autolabel'] = True; p['grain'] = 'auto'; p['texts'] = []; p['marks'] = []; p['dartlabels'] = []
    pieces.append(p)
# ================================================================ LINING (+ boning channels)
# Lining = shell outline without the patchwork/princess/style splits (darts sewn as darts), hem 2.5cm shorter.
# The neckline is bound together with the shell, so no facing is needed.
from shapely.affinity import translate as _translate
def _outline(pc):
    pts = []
    for e in pc['edges']: pts += e['pts'] if not pts else e['pts'][1:]
    return Polygon(pts).buffer(0)
def poly_piece(name, poly, refs, default_sa=2.0, tol=0.3, **kw):
    ring = list(poly.exterior.coords)[:-1]
    segs = []
    for i in range(len(ring)):
        a, b = ring[i], ring[(i+1) % len(ring)]
        if math.dist(a, b) < 1e-6: continue
        mid = Point((a[0]+b[0])/2, (a[1]+b[1])/2)
        best = min(refs, key=lambda r: r[0].distance(mid))
        tag = (best[1], best[2], id(best[0])) if best[0].distance(mid) < tol else (default_sa, 'hem', 0)
        segs.append((a, b, tag))
    k = next(i for i in range(len(segs)) if segs[i][2] != segs[i-1][2])
    segs = segs[k:] + segs[:k]
    edges = []
    for a, b, tag in segs:
        if edges and edges[-1]['_t'] == tag: edges[-1]['pts'].append(b)
        else: edges.append(dict(pts=[a, b], sa=tag[0], n=tag[1], _t=tag))
    i = 0
    while i < len(edges):                       # absorb tiny slivers into the previous edge
        if plen(edges[i]['pts']) < 0.6 and len(edges) > 3:
            prev = edges[i-1]; prev['pts'] += edges[i]['pts'][1:]; edges.pop(i)
            nxt = edges[i % len(edges)]
            if nxt is not prev and nxt['_t'] == prev['_t']:
                prev['pts'] += nxt['pts'][1:]; edges.remove(nxt)
            continue
        i += 1
    return piece(name, edges, **kw)
def _refs(*pcs):
    return [(LineString(e['pts']), e['sa'], e.get('n')) for pc in pcs for e in pc['edges']]
def _lining(poly, hem):
    """cut the shell outline 2.5cm above its hem line (hem given left->right or right->left)"""
    h = [(x, y-2.5) for x, y in hem]
    if h[0][0] > h[-1][0]: h = h[::-1]
    h = [(h[0][0]-12, h[0][1])] + h + [(h[-1][0]+12, h[-1][1])]
    below = Polygon(h + [(h[-1][0], 300), (h[0][0], 300)])
    return poly.difference(below)
def _channel(x, y0, L=15):
    return [[(x-0.5, y0+0.5), (x-0.5, y0+L)], [(x+0.5, y0+0.5), (x+0.5, y0+L)]]
def _neck_y(curve, x):
    g = LineString(curve).intersection(LineString([(x, -50), (x, 150)])); return g.y

dartR_kite = Polygon([BPR, (-7.25, 42), (-9, 56), (-10.75, 42)])
front_lin = _lining(_outline(FA).union(_outline(FB)).union(dartR_kite).buffer(0.01).buffer(-0.01), hem_A[:-1] + [HB] + hem_B[1:])
LF = poly_piece('8  앞 안감', front_lin, _refs(FA, FB))
LF['marks'] = [side_dart(side_L, 5, 11.5), side_dart(side_R, 4, -11.5),
               [(9-1.75, 42), (9, 28), (9+1.75, 42), (9, 56), (9-1.75, 42)],
               [(-9-1.75, 42), (-9, 28), (-9+1.75, 42), (-9, 56), (-9-1.75, 42)]] \
              + _channel(-21, _neck_y(neck_f, -21)) + _channel(-15, _neck_y(neck_f, -15))
LF['guides'] = [('CF', [(0, -5), (0, 100)])]
LF['dartlabels'] = [((12.4, 45.5), '다트 3.5'), ((-12.4, 45.5), '다트 3.5'), ((17.2, 29.6), '다트 3.0'),
                    ((-17.6, 30.6), '다트 3.0'), ((-18, 30.8+8), '본 채널 15cm')]
for code, src, nm in (('9-1', BL, '뒤 안감 왼쪽'), ('9-2', BR, '뒤 안감 오른쪽')):
    lp = poly_piece(f'{code}  {nm}', _lining(_outline(src), src['edges'][1 if src is BL else 2]['pts']), _refs(src))
    lp['marks'] = list(src['marks']); lp['guides'] = []
    lp['dartlabels'] = [((13.6 if src is BL else -13.6, 43), '다트 3.5')]
    if src is BR:
        lp['marks'] += _channel(-20, _neck_y(neck_bR, -20)); lp['dartlabels'].append(((-16.5, 38), '본 채널 15cm'))
    globals()['L' + code.replace('-', '_')] = lp
for lp, lab in ((LF, ['8  앞 안감', '안감 x1 (겉면 위로)', '밑단 2.5cm 짧음']),
                (L9_1, ['9-1  뒤 안감 왼쪽', '안감 x1', '밑단 2.5cm 짧음']),
                (L9_2, ['9-2  뒤 안감 오른쪽', '안감 x1', '밑단 2.5cm 짧음'])):
    lp.update(label=lab, autolabel=True, grain='auto', texts=[])
LININGS = [LF, L9_1, L9_2]

# ---- matching notches for the toile: side-seam waist, lining armhole / zipper, drape shoulder point
_WB = (20.5, 39.0)
_side_low = dict((c, p) for c, _, p in FRONT_PANELS)['1-5']
_side_low['notches'] += [(W_F, 2)]
FBN['notches'] += [((-21.5, 42.0), 2)]
BL['notches'] += [(_WB, 2)]
BR['notches'] += [((-_WB[0], _WB[1]), 2)]
LF['notches'] += [(W_F, 2), ((-21.5, 42.0), 2), (at(front_arm, plen(front_arm)-8), 1)]
L9_1['notches'] += [(_WB, 2), ((0.0, ZIP_END), 1), (at(back_arm, plen(back_arm)-9), 2)]
L9_2['notches'] += [((-_WB[0], _WB[1]), 2), ((0.0, ZIP_END), 1)]
DRP['notches'] += [((36.0, 25.0), 1)]

pieces.sort(key=lambda p: p['name'])
FRONT_LINES = dict(princess=prin_c, style=style_A, L1=L1, L2=L2)

for pc in pieces: compute(pc)

neck_total = plen(neck_fA) + plen(neck_B_r) + plen(neck_bL) + plen(neck_bR)
AH_REAL = plen(arm_c) + plen(arm_s_r) + BAH
CAP_EASE = cap_len - AH_REAL

if __name__ == '__main__':
    print('FAH %.1f BAH %.1f AH %.1f cap %.1f caplen %.1f ease %.1f' % (FAH, BAH, AH, cap, cap_len, cap_len-AH))
    print('bwF %.1f bwB %.1f bicep %.1f' % (bwF, bwB, bwF+bwB))
    print('neckline total %.1f' % neck_total)
    print('style A len %.1f B len %.1f' % (plen(style_A), plen(style_B)))
    print('side L front %.1f back %.1f' % (plen(side_L)-3, plen(side_bL)))
    print('side R front %.1f back %.1f' % (plen(side_R)-3, plen(side_bR)))
    for pc in pieces:
        b = pc['bbox']; print(pc['name'], 'w %.1f h %.1f' % (b[2]-b[0], b[3]-b[1]), [round(v, 1) for v in b])
