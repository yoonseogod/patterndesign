"""생성된 PDF를 독립적으로 검사한다. 사용법: python3 audit_pdf.py 100"""
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
import pdfplumber
from PIL import Image
from reportlab.pdfbase.pdfmetrics import stringWidth
from shapely.geometry import LineString, Point, Polygon
from shapely import affinity

TC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TC)
import generate_trench as G  # noqa: E402

args = [x for x in sys.argv[1:] if x != "--sa"]
SA_MODE = "--sa" in sys.argv
if SA_MODE:
    G.NET = False                       # 시접 포함 버전 검사
size = args[0] if args else "100"
sfx = "_withSA" if SA_MODE else ""
A4 = f"{TC}/pdf/trench_men_{size}_A4{sfx}.pdf"
FULL = f"{TC}/pdf/trench_men_{size}_fullsize{sfx}.pdf"
results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))


pieces, info = G.draft(size)
rows = G.layout(pieces)
used = [(ci, ri) for ri in range(rows) for ci in range(G.COLS) if G.tile_used(pieces, ci, ri)]

# 1. 실제 크기: 시험 사각형
with pdfplumber.open(A4) as pdf:
    npages = len(pdf.pages)
    p1 = pdf.pages[0]
    sq = [r for r in p1.rects if abs(r["width"] - 283.4646) < 0.05 and abs(r["height"] - 283.4646) < 0.05]
    sq5 = [r for r in p1.rects if abs(r["width"] - 141.7323) < 0.05]
    check("1쪽 10cm 시험 사각형 = 283.46pt (정확히 10cm)", len(sq) == 1,
          f"찾은 크기 {sq[0]['width']:.3f}pt" if sq else "없음")
    check("1쪽 5cm 시험 사각형", len(sq5) == 1)
    a4ok = all(abs(pg.width - 595.276) < 0.1 and abs(pg.height - 841.89) < 0.1 for pg in pdf.pages)
    check("모든 쪽이 A4 (210×297mm)", a4ok, f"{npages}쪽")
    check("쪽 수 = 안내 2 + 패턴 칸 수", npages == 2 + len(used), f"패턴 {len(used)}장")
    # 페이지 이름이 순서대로 있는지
    exp = [G.tile_name(ci, ri) for ci, ri in used]
    bad = []
    for pg, (ci, ri) in zip(pdf.pages[2:], used):
        hdr = "".join(ch["text"] for ch in pg.chars if ch["top"] < 25 and abs(ch["size"] - 7) < 0.3)
        if f"열{chr(65 + ci)}/행{ri + 1}" not in hdr.replace(" ", ""):
            bad.append(G.tile_name(ci, ri))
    names = exp if not bad else bad
    check("각 장의 칸 이름(A1, B1 …)이 배치 순서와 일치", names == exp,
          "" if not bad else f"틀린 장 {bad}")

# 2. 이어 붙이기 = 전체 1장
dpi = 50.8  # 1cm = 20px
px = 20
tmp = tempfile.mkdtemp()
# 기준 그림: A4와 같은 배치를 잘라 붙이지 않고 한 장에 그대로 그린 것
from reportlab.pdfgen import canvas as _cv
from reportlab.lib.units import cm as _cm
REF = f"{tmp}/ref.pdf"
_W, _H = G.COLS * G.TILE_W, rows * G.TILE_H
_c = _cv.Canvas(REF, pagesize=(_W * _cm, _H * _cm))
_c.translate(0, _H * _cm); _c.scale(_cm, -_cm)
G.draw_grid(_c, _W, _H)
for _p in pieces:
    G.draw_piece(_c, _p)
_c.save()
subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", REF, f"{tmp}/full"], check=True)
subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", "-f", "3", A4, f"{tmp}/t"], check=True)
full = np.array(Image.open([f"{tmp}/{f}" for f in os.listdir(tmp) if f.startswith("full")][0]).convert("L")).astype(int)
tiles = sorted(f for f in os.listdir(tmp) if f.startswith("t-"))
TW, TH = int(G.TILE_W * px), int(G.TILE_H * px)
M = int(G.MARGIN * px)
worst = 0
bad_tiles = []
for (ci, ri), f in zip(used, tiles):
    t = np.array(Image.open(f"{tmp}/{f}").convert("L")).astype(int)
    crop = t[M:M + TH, M:M + TW]
    ref = full[ri * TH:(ri + 1) * TH, ci * TW:(ci + 1) * TW]
    h, w = min(crop.shape[0], ref.shape[0]), min(crop.shape[1], ref.shape[1])
    # 1픽셀 렌더링 어긋남(글자 안티앨리어싱)은 허용: 상하좌우 1px 이동 중 가장 작은 차이
    cc = crop[3:h - 3, 3:w - 3]
    d = np.min([np.abs(cc - ref[3 + dy:h - 3 + dy, 3 + dx:w - 3 + dx])
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)], axis=0)
    if (ci, ri) == (0, 0):
        d[-int(4 * px):, :int(4 * px)] = 0  # 3cm 시험 사각형 자리
    frac = (d > 60).mean()
    worst = max(worst, frac)
    if frac > 0.002:
        bad_tiles.append((G.tile_name(ci, ri), round(frac * 100, 2)))
check("A4 장을 이어 붙인 그림 = 같은 배치를 한 장에 그린 그림 (픽셀 비교)", not bad_tiles,
      f"가장 큰 차이 {worst * 100:.3f}% 픽셀" + (f", 문제 칸 {bad_tiles}" if bad_tiles else ""))

# 3. 인쇄 안 하는 칸이 정말 비었는지
missing = []
for ri in range(rows):
    for ci in range(G.COLS):
        if (ci, ri) in used:
            continue
        reg = full[ri * TH + 6:(ri + 1) * TH - 6, ci * TW + 6:(ci + 1) * TW - 6]  # 가장자리 0.3cm: 이웃 장 선 두께
        if (reg < 200).sum() > 5:
            missing.append(G.tile_name(ci, ri))
check("인쇄 안 하는 빈 칸에 패턴 선·글자가 없음", not missing, ",".join(missing))

# 4. 조각 겹침
ov = []
for i in range(len(pieces)):
    for j in range(i + 1, len(pieces)):
        dd = pieces[i].cut.distance(pieces[j].cut)
        if dd < 1.0:
            ov.append((pieces[i].name, pieces[j].name, round(dd, 2)))
check("조각끼리 1cm 이상 떨어져 있음 (시접 그릴 자리)", not ov, str(ov))
inside = all(0 <= p.cut.bounds[0] and p.cut.bounds[2] <= G.COLS * G.TILE_W for p in pieces)
check("모든 조각이 배치 폭 안에 있음", inside)

# 5. 시접 글자
def label_rect(p, pt, label):
    line = LineString(p.outline + [p.outline[0]])
    d = line.project(Point(pt))
    a, b = line.interpolate(max(0, d - 0.5)), line.interpolate(d + 0.5)
    tx, ty = b.x - a.x, b.y - a.y
    L = math.hypot(tx, ty)
    nx, ny = -ty / L, tx / L
    base = line.interpolate(d)
    if not p.poly.contains(Point(base.x + nx * 0.3, base.y + ny * 0.3)):
        nx, ny = -nx, -ny
    ang = math.degrees(math.atan2(ty, tx))
    if ang > 90 or ang < -90:
        ang += 180
    cx, cy = base.x + nx * 0.75, base.y + ny * 0.75
    w = stringWidth(label, "KRB", 0.45 * 28.3465) / 28.3465
    r = Polygon([(-w / 2, -0.2), (w / 2, -0.2), (w / 2, 0.2), (-w / 2, 0.2)])
    r = affinity.translate(affinity.rotate(r, ang, origin=(0, 0)), cx, cy)
    return r, base, line.distance(Point(pt))

problems, nlab = [], 0
for p in pieces:
    for pt, v in p.sa_marks:
        nlab += 1
        label = v if isinstance(v, str) else f"시접 {v:g}cm"
        r, base, off = label_rect(p, pt, label)
        if off > 0.3:
            problems.append(f"{p.name}:{label} 기준점이 선에서 {off:.1f}cm 떨어짐")
        if not p.poly.buffer(-0.05).contains(r):
            problems.append(f"{p.name}:{label} 글자가 조각 밖으로 나감")
check(f"시접 글자 {nlab}개 모두 해당 선 위 기준점 + 조각 안쪽에 들어감", not problems, "; ".join(problems))

# 모든 선(모서리 사이 구간, 3cm 이상, 골선 제외)에 시접 표기가 있는지
def edges(pts, turn=35):
    pts = [q for i, q in enumerate(pts) if i == 0 or math.dist(q, pts[i - 1]) > 1e-6]
    if math.dist(pts[0], pts[-1]) < 1e-6:
        pts = pts[:-1]
    n = len(pts)
    corners = []
    for i in range(n):
        a_, b_, c_ = pts[i - 1], pts[i], pts[(i + 1) % n]
        v1 = (b_[0] - a_[0], b_[1] - a_[1]); v2 = (c_[0] - b_[0], c_[1] - b_[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        if l1 and l2:
            cosv = max(-1, min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)))
            if math.degrees(math.acos(cosv)) > turn:
                corners.append(i)
    out = []
    for k in range(len(corners)):
        i0, i1 = corners[k], corners[(k + 1) % len(corners)]
        seg = [pts[j % n] for j in range(i0, i1 + (n if i1 <= i0 else 0) + 1)]
        out.append(seg)
    return out

missing = []
small = {"epaulette", "cuffstrap", "latch", "welt", "bag", "belttip"}  # '사방 시접' 한 번 표기
for p in pieces:
    if p.key in small:
        if not p.sa_marks:
            missing.append(f"{p.name}: 표기 없음")
        continue
    for seg in edges(p.outline):
        if G.plen(seg) < 3:
            continue
        if p.fold_x is not None and all(abs(q[0] - p.fold_x) < 0.05 for q in seg):
            continue
        ls = LineString(seg)
        if not any(ls.distance(Point(pt)) < 0.1 for pt, _ in p.sa_marks):
            missing.append(f"{p.name}: {G.plen(seg):.0f}cm 선 ({seg[0][0]:.0f},{seg[0][1]:.0f})")
check("3cm 넘는 모든 선(골선 제외)에 시접 표기가 있음", not missing, "; ".join(missing))

# 꿰매는 짝끼리 시접 폭 같은지 (조각, 표기 순서)
SAv = {p.key: [v for _, v in p.sa_marks] for p in pieces}
pairs = [("어깨 앞/뒤", ("front", 0), ("back", 1)), ("옆선 앞/뒤", ("front", 2), ("back", 3)),
         ("진동/소매산(윗)", ("front", 1), ("topsleeve", 0)), ("진동/소매산(밑)", ("back", 2), ("undersleeve", 0)),
         ("소매 뒷솔기", ("topsleeve", 1), ("undersleeve", 1)), ("소매 앞솔기", ("topsleeve", 2), ("undersleeve", 2)),
         ("앞단/안단", ("front", 4), ("facing", 2)), ("라펠 위/안단", ("front", 5), ("facing", 5)),
         ("목둘레/칼라밴드", ("front", 6), ("stand", 0)), ("칼라밴드/칼라", ("stand", 1), ("collar", 0)),
         ("앞 어깨/안단 어깨", ("front", 0), ("facing", 0)), ("밑단 앞/뒤", ("front", 3), ("back", 4)),
         ("소매 밑단 윗/밑", ("topsleeve", 3), ("undersleeve", 3))]
mis = [n for n, a, b in pairs if SAv[a[0]][a[1]] != SAv[b[0]][b[1]]]
check(f"꿰매는 짝 {len(pairs)}쌍의 시접 폭이 서로 같음", not mis, ", ".join(mis))

# 복사실용 한 장짜리 PDF
with pdfplumber.open(FULL) as pdf:
    pg = pdf.pages[0]
    wcm = pg.width / 28.3465
    txt = pg.extract_text() or ""
names_ok = all(p.texts[0][2].split()[0] in txt.replace(" ", "") or p.texts[0][2].replace(" ", "") in txt.replace(" ", "")
               for p in pieces)
check("한 장짜리 PDF 폭 ≤ 84cm (A0 폭 · 36인치 롤에 들어감)", wcm <= 84.1, f"폭 {wcm:.1f}cm")
check(f"한 장짜리 PDF에 조각 {len(pieces)}개 이름이 모두 있음", names_ok)

# 6. 글자 겹침 (전체 1장 PDF의 글자 상자)
with pdfplumber.open(FULL) as pdf:
    ch = [c for c in pdf.pages[0].chars if c["text"].strip()]
boxes = [(c["x0"], c["top"], c["x1"], c["bottom"]) for c in ch]
over = 0
ex = []
for i in range(len(boxes)):
    a = boxes[i]
    for j in range(i + 2, min(len(boxes), i + 400)):
        b = boxes[j]
        ix = min(a[2], b[2]) - max(a[0], b[0])
        iy = min(a[3], b[3]) - max(a[1], b[1])
        if ix > 0 and iy > 0:
            area = ix * iy
            amin = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
            if amin > 0 and area / amin > 0.35:
                over += 1
                if len(ex) < 8:
                    ex.append(ch[i]["text"] + "/" + ch[j]["text"] + f"@({a[0] / 28.35:.0f},{a[1] / 28.35:.0f}cm)")
check("서로 다른 글자끼리 겹치는 곳 없음", over == 0, f"{over}곳 " + " ".join(ex))

print()
print(f"결과: {sum(r[1] for r in results)}/{len(results)} 통과")

# 7. 글자가 식서 화살표·내부선·단추를 가로지르지 않는지
def text_rect(x, y, s, z, bold=False):
    w = stringWidth(s, "KRB" if bold else "KR", z * 28.3465) / 28.3465
    return Polygon([(x, y - 0.75 * z), (x + w, y - 0.75 * z), (x + w, y + 0.15 * z), (x, y + 0.15 * z)])

hits = []
for p in pieces:
    rects = [(s_, text_rect(x, y, s_, z, i == 0)) for i, (x, y, s_, z) in enumerate(p.texts)]
    tx = p.texts[0][0]
    yl = max(t[1] for t in p.texts[:3] if abs(t[0] - tx) < 1e-6)
    for x, y, ln in G.cut_positions(p):
        rects.append((ln, text_rect(x, y, ln, 0.45)))
    for pt, v in p.sa_marks:
        lab = v if isinstance(v, str) else f"시접 {v:g}cm"
        rects.append((lab, label_rect(p, pt, lab)[0]))
    # 안쪽 선에 붙은 설명 글자 (draw_piece와 같은 위치·각도)
    for pts, st, lab in p.lines:
        if not lab:
            continue
        a0, b0 = pts[0], pts[1]
        ang = math.degrees(math.atan2(b0[1] - a0[1], b0[0] - a0[0]))
        if ang > 90 or ang < -90:
            ang += 180
        x0 = a0[0] + (b0[0] - a0[0]) * 0.1 + 0.3
        y0 = a0[1] + (b0[1] - a0[1]) * 0.1 - 0.25
        w = stringWidth(lab, "KR", 0.42 * 28.3465) / 28.3465
        r0 = Polygon([(0, -0.75 * 0.42), (w, -0.75 * 0.42), (w, 0.15 * 0.42), (0, 0.15 * 0.42)])
        rects.append(("선 이름 " + lab, affinity.translate(affinity.rotate(r0, ang, origin=(0, 0)), x0, y0)))
    obstacles = []
    if p.grain:
        obstacles.append(("식서", LineString(p.grain)))
    for pts, st, lab in p.lines:
        obstacles.append((lab or "선", LineString(pts)))
    for x, y, r in p.dots:
        obstacles.append(("단추", Point(x, y).buffer(r)))
    for n in p.notches:
        obstacles.append(("노치", Point(n).buffer(0.35)))
    for name, r in rects:
        for oname, o in obstacles:
            if r.buffer(-0.02).intersects(o):
                hits.append(f"{p.name}: '{name}' × {oname}")
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if rects[i][1].buffer(-0.03).intersects(rects[j][1].buffer(-0.03)):
                hits.append(f"{p.name}: '{rects[i][0]}' × '{rects[j][0]}'")
outside = [f"{p.name}: 식서" for p in pieces if p.grain and not p.poly.contains(LineString(p.grain))]
outside += [f"{p.name}: '{t[2]}'" for p in pieces for t in p.texts
            if not p.poly.buffer(0.01).contains(text_rect(t[0], t[1], t[2], t[3]))]
outside += [f"{p.name}: '{ln}'" for p in pieces for x, y, ln in G.cut_positions(p)
            if not p.poly.buffer(-0.05).contains(text_rect(x, y, ln, 0.45))]
fold_bad = [p.name for p in pieces if p.fold_x is not None and p.grain
            and abs(p.grain[0][0] - p.grain[1][0]) > 0.01]
check("골선 조각의 식서가 접는 선과 나란함", not fold_bad, ", ".join(fold_bad))
check("식서 화살표와 조각 글자가 모두 조각 안에 있음", not outside, "; ".join(outside))
check("글자가 식서·안쪽 선·단추·다른 글자와 겹치지 않음", not hits, "; ".join(hits))
print(f"결과(추가 포함): {sum(r[1] for r in results)}/{len(results)} 통과")
