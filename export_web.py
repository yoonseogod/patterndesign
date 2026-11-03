"""Export the dress pattern (assembled, finished seam lines) for the 3D web viewer.

Writes web/pattern.json and builds web/index.html from web/template.html.
Coordinates are cm. Front frame: x>0 = wearer's left, y down from shoulder-neck level.
Back frame: x>0 = wearer's left, CB at x=0. Sleeve frame: cap top at (0,0), x>0 = front.
"""
import json, math, os
import shapely
from shapely.geometry import Polygon, LineString, MultiPoint, Point
from shapely.ops import split
import make_pattern as m

HERE = os.path.dirname(os.path.abspath(__file__))


def outline(pc):
    pts = []
    for e in pc['edges']:
        pts += e['pts'] if not pts else e['pts'][1:]
    return Polygon(pts).buffer(0)


def ext(pts, L=6):
    (x0, y0), (x1, y1) = pts[0], pts[1]
    d = math.hypot(x1-x0, y1-y0); a = (x0-(x1-x0)/d*L, y0-(y1-y0)/d*L)
    (x0, y0), (x1, y1) = pts[-1], pts[-2]
    d = math.hypot(x1-x0, y1-y0); b = (x0-(x1-x0)/d*L, y0-(y1-y0)/d*L)
    return LineString([a] + list(pts) + [b])


def cut(poly, line):
    parts = [g for g in split(poly, line).geoms if g.area > 1]
    assert len(parts) == 2, len(parts)
    return parts


def mesh(poly, step=1.6):
    """Triangulate a polygon with interior points so it can bend smoothly in 3D."""
    poly = poly.simplify(0.05)
    ring = LineString(poly.exterior.coords)
    n = max(8, int(ring.length/step*1.6))
    pts = [ring.interpolate(i/n, normalized=True) for i in range(n)]
    x0, y0, x1, y1 = poly.bounds
    inner = poly.buffer(-step*0.45)
    y = y0
    row = 0
    while y <= y1:
        x = x0 + (step/2 if row % 2 else 0)
        while x <= x1:
            p = Point(x, y)
            if inner.contains(p): pts.append(p)
            x += step
        y += step*0.866; row += 1
    tris = shapely.delaunay_triangles(MultiPoint(pts), tolerance=0.0)
    verts, index, faces = [], {}, []
    def vid(c):
        k = (round(c[0], 4), round(c[1], 4))
        if k not in index:
            index[k] = len(verts); verts.append([round(c[0], 3), round(c[1], 3)])
        return index[k]
    shell = poly.buffer(0.02)
    for t in tris.geoms:
        if not shell.contains(t.centroid): continue
        c = list(t.exterior.coords)[:3]
        faces += [vid(c[0]), vid(c[1]), vid(c[2])]
    return dict(v=verts, f=faces, outline=[[round(x, 3), round(y, 3)] for x, y in poly.exterior.coords])


# ---------------------------------------------------------------- front, assembled (pre-dart-closing geometry)
FA, FB = outline(m.FA), outline(m.FB)
centre, side = sorted(cut(FA, ext(m.prin_c)), key=lambda p: p.centroid.x)
L1 = LineString(m.L1); L2 = LineString(m.L2)
c_up, c_rest = sorted(cut(centre, L1), key=lambda p: p.centroid.y)
c_mid, c_low = sorted(cut(c_rest, L2), key=lambda p: p.centroid.y)
s_up, s_low = sorted(cut(side, L1), key=lambda p: p.centroid.y)

pieces = []
def add(pid, name, frame, fabric, poly):
    d = mesh(poly); d.update(id=pid, name=name, frame=frame, fabric=fabric); pieces.append(d)

add('1-1', '앞 중심 상단', 'front', 'quilt', c_up)
add('1-2', '앞 중심 중단', 'front', 'quilt', c_mid)
add('1-3', '앞 중심 하단', 'front', 'quilt', c_low)
add('1-4', '앞 옆판 상단', 'front', 'quilt', s_up)
add('1-5', '앞 옆판 하단', 'front', 'quilt', s_low)
add('2', '앞판 B (실 장식 베이스)', 'front', 'gauze', FB)
add('3', '뒤판 왼쪽', 'back', 'quilt', outline(m.BL))
add('4', '뒤판 오른쪽', 'back', 'quilt', outline(m.BR))
add('5', '소매', 'sleeve', 'knit', outline(m.SLV))

def pl(line):
    return [[round(x, 3), round(y, 3)] for x, y in line]
def clip(poly, pts):
    g = poly.buffer(0.01).intersection(LineString(pts))
    return [pl(q.coords) for q in getattr(g, 'geoms', [g]) if q.geom_type == 'LineString' and q.length > 1]

seams = dict(
    front=clip(FA, m.prin_c) + clip(FA, m.style_A) + clip(FA, m.L1) + clip(centre, m.L2)
          + [pl(m.hem_A[:-1] + [m.HB]), pl(m.hem_B)],
    back=[pl(m.BL['edges'][1]['pts']), pl(m.BR['edges'][2]['pts'])],
)
applique = [pl(m.tri_at(k, c, a)) for k, c, a in m.FA['applique']]

# reference side-seam x positions per y (front / back frames) and key heights
ref = dict(
    front_side=[[0, 23.5], [21, 23.5], [42, 21.5], [60, 24.5], [92, 25.2]],
    back_side=[[0, 22.5], [21, 22.5], [39.5, 20.5], [57, 23.5], [88, 24.3]],
    front_y=[[0, 0], [21, 21], [42, 42], [60, 60]],     # front frame y at underarm / waist / hip
    back_y=[[0, 0], [21, 21], [39.5, 42], [57, 60]],    # back y -> equivalent front y
    sleeve=dict(cap=m.cap, length=m.SL, wrist=m.M['wrist'], bicep=round(m.bwF+m.bwB, 2), bwF=round(m.bwF, 2), bwB=round(m.bwB, 2)),
    meas=m.M, B_outline=pl(FB.exterior.coords),
)
data = dict(pieces=pieces, seams=seams, applique=applique, ref=ref)

os.makedirs(os.path.join(HERE, 'web'), exist_ok=True)
js = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
with open(os.path.join(HERE, 'web', 'pattern.json'), 'w') as f: f.write(js)
tpl = open(os.path.join(HERE, 'web', 'template.html'), encoding='utf-8').read()
with open(os.path.join(HERE, 'web', 'index.html'), 'w', encoding='utf-8') as f:
    f.write(tpl.replace('/*PATTERN_JSON*/null', js))
print('pieces', len(pieces), 'verts', sum(len(p['v']) for p in pieces), 'json KB', len(js)//1024)
