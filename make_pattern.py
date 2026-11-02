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

hem_A = [(HEMSIDE, hem_f(HEMSIDE)), (-6, 90), HB]
hem_B = [HB, (-HEMSIDE, hem_f(-HEMSIDE))]

def side_dart(side, top_dist, tipx):
    a = at(side, top_dist); b = at(side, top_dist+3)
    return [a, (tipx, 26.6), b]

pieces = []
def piece(name, edges, **kw):
    d = dict(name=name, edges=edges, marks=[], texts=[], grain=None, notches=[], dashed=[], quilt=False, applique=[])
    d.update(kw); pieces.append(d); return d

# Front A: T -> SNP -> SP -> UA -> side -> hem -> style -> T
FA = piece('1  앞판 A', [
    dict(pts=neck_fA, sa=0, n='neck'),
    dict(pts=line(SNP_F, SP_F), sa=1),
    dict(pts=rev(front_arm), sa=1, n='arm'),   # SP->UA
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
SP_B = (SNP_B[0]+13*math.cos(math.radians(18)), 13*math.sin(math.radians(18)))
UA_B = (22.5, 21.0)
back_arm = cr([SP_B, (18.6, 9.5), (18.4, 14), (19.4, 18.2), (20.8, 20.4), UA_B])
def hem_b(x): return 80 - x/24*4
CBN = 15.0
neck_bL = bez((0, CBN), (3.5, CBN), (6.2, 6), SNP_B)
neck_bR = bez((0, CBN), (-6, CBN), (-17, 22.2), (-22.5, 22.5))
side_bL = side_seam(UA_B, (20.5, 39), (23.5, 57), (24, hem_b(24)))
side_bR = side_seam((-22.5, 22.5), (-20.5, 39), (-23.5, 57), (-24, hem_b(-24)))

BL = piece('3  뒤판 왼쪽', [
    dict(pts=line((0, CBN), (0, hem_b(0))), sa=2, n='cb'),
    dict(pts=line((0, hem_b(0)), (24, hem_b(24))), sa=2),
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
    dict(pts=line((-24, hem_b(-24)), (0, hem_b(0))), sa=2),
    dict(pts=line((0, hem_b(0)), (0, CBN)), sa=2, n='cb'),
])
BR['marks'] = [[(-10-1.75, 39.6), (-10, 25), (-10+1.75, 39.6), (-10, 55), (-10-1.75, 39.6)]]
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
    pts = [B0, along(B0, top, .25, -0.4), along(B0, top, .5, 0.7), along(B0, top, .78, 1.7),
           (-1.8, 0.1), top, (1.8, 0.1), along(F0, top, .78, 1.7), along(F0, top, .5, 0.3),
           along(F0, top, .25, -1.2), F0]
    return cr(pts, 20), bwF, bwB
capc, bwF, bwB = sleeve_build(cap)
cap_len = plen(capc)
WR = M['wrist']/2
SL = M['sleeve']
SLV = piece('5  소매', [
    dict(pts=capc, sa=1, n='cap'),                     # back bicep -> front bicep
    dict(pts=line((bwF, cap), (WR+0.6, SL)), sa=1),
    dict(pts=line((WR+0.6, SL), (-WR-0.6+0, SL)), sa=2.5),
    dict(pts=line((-WR-0.6, SL), (-bwB, cap)), sa=1),
])
SLV['dashed'] = [[(-bwB, cap), (bwF, cap)], [(-(bwB+WR)/2-0.6, 34), ((bwF+WR)/2+0.6, 34)]]
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

for pc in pieces: compute(pc)

# notches: (piece, edge index, distance from edge start, count)
def add_notch(pc, ei, dist, cnt=1):
    pc['notches'].append((ei, dist, cnt))
add_notch(FA, 2, plen(front_arm)-8, 1)          # SP->UA ; 8cm from UA
add_notch(BL, 3, plen(back_arm)-9, 2)
add_notch(SLV, 0, cap_len-(FAH and 0) - 8.3, 1)  # from front bicep 8.3
add_notch(SLV, 0, 9.3, 2)                        # from back bicep
add_notch(SLV, 0, cap_len*(BAH/AH)+0.3, 1)       # top / shoulder point
add_notch(BL, 0, ZIP_END-CBN, 1); add_notch(BR, 3, (hem_b(0)-ZIP_END), 1)
add_notch(FA, 5, plen(style_A)-plen(style_up)+0, 1)   # BP match
add_notch(FB, 1, plen(style_up), 1)
add_notch(FA, 0, 0.0001, 0); 
add_notch(FA, 5, plen(style_A)-plen(style_up)-16, 2)  # waist-ish match
add_notch(FB, 1, plen(style_up)+16, 2)

neck_total = plen(neck_f) + plen(neck_bL) + plen(neck_bR)

if __name__ == '__main__':
    print('FAH %.1f BAH %.1f AH %.1f cap %.1f caplen %.1f ease %.1f' % (FAH, BAH, AH, cap, cap_len, cap_len-AH))
    print('bwF %.1f bwB %.1f bicep %.1f' % (bwF, bwB, bwF+bwB))
    print('neckline total %.1f' % neck_total)
    print('style A len %.1f B len %.1f' % (plen(style_A), plen(style_B)))
    print('side L front %.1f back %.1f' % (plen(side_L)-3, plen(side_bL)))
    print('side R front %.1f back %.1f' % (plen(side_R)-3, plen(side_bR)))
    for pc in pieces:
        b = pc['bbox']; print(pc['name'], 'w %.1f h %.1f' % (b[2]-b[0], b[3]-b[1]), [round(v, 1) for v in b])
