#!/usr/bin/env python3
"""남성 더블브레스티드 트렌치코트 패턴 생성기.

치수표(사이즈 95~110)를 바탕으로 원형을 제도하고, 실제 크기(1:1) 패턴을
A4 용지에 나눠 인쇄할 수 있는 PDF로 만듭니다. 복사실 출력용 한 장짜리 PDF도
함께 만듭니다.

사용법:
    python3 generate_trench.py            # 모든 사이즈
    python3 generate_trench.py 100 105    # 원하는 사이즈만
"""
import math
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "pdf")

pdfmetrics.registerFont(TTFont("KR", os.path.join(HERE, "fonts", "NanumGothic-Regular.ttf")))
pdfmetrics.registerFont(TTFont("KRB", os.path.join(HERE, "fonts", "NanumGothic-Bold.ttf")))

# ── 치수표 (신체 치수, cm) ────────────────────────────────────────────────
SIZES = {
    "95":  dict(chest=94,  height=170, neck=39, nape_waist=44.0, coat_len=98,  sleeve=62.0),
    "100": dict(chest=98,  height=175, neck=40, nape_waist=45.0, coat_len=101, sleeve=63.5),
    "105": dict(chest=102, height=180, neck=41, nape_waist=46.0, coat_len=104, sleeve=65.0),
    "110": dict(chest=106, height=185, neck=42, nape_waist=47.0, coat_len=107, sleeve=66.5),
}

SA = 1.0        # 기본 시접
SA_SIDE = 1.5   # 옆선 · 뒤중심 (맞음새 조정분)
NET = True      # True: 시접 없는 완성선 패턴 (시접 폭은 글자로 표기), --sa 로 시접 포함 버전
HEM = 4.0       # 몸판 밑단 시접
SLEEVE_HEM = 4.0
FUSE_HEM = 5.0  # 소매 밑단 심지 폭

# ── 기하 도우미 ───────────────────────────────────────────────────────────

def bez(p0, p1, p2, p3, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n
        a = (1 - t) ** 3
        b = 3 * (1 - t) ** 2 * t
        c = 3 * (1 - t) * t ** 2
        d = t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def catmull(points, n=16):
    """점들을 부드럽게 지나는 곡선."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for j in range(n):
            t = j / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t +
                                    (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 +
                                    (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in (0, 1)))
    out.append(points[-1])
    return out


def plen(pts):
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def join(*segs):
    out = []
    for s in segs:
        for p in s:
            if not out or math.dist(out[-1], p) > 1e-6:
                out.append(p)
    return out


def cut_until(pts, pred):
    """pred(점)이 처음 참이 될 때까지의 구간(교점 보간 포함)."""
    out = [pts[0]]
    for i in range(1, len(pts)):
        if pred(pts[i]):
            out.append(pts[i])
            return out, i
        out.append(pts[i])
    return out, len(pts) - 1


def sub_by_x(pts, x0, x1):
    """x에 대해 단조인 곡선에서 x0~x1 구간."""
    def interp(x):
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
                t = (x - a[0]) / (b[0] - a[0])
                return (x, a[1] + t * (b[1] - a[1]))
        return min(pts, key=lambda p: abs(p[0] - x))
    inner = [p for p in pts if x0 < p[0] < x1]
    return [interp(x0)] + inner + [interp(x1)]


def y_at_x(pts, x):
    return sub_by_x(pts, x, x)[0][1]


def rot(p, c, ang):
    s, co = math.sin(ang), math.cos(ang)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * co - y * s, c[1] + x * s + y * co)


def point_at(pts, dist):
    """선 시작에서 dist cm 떨어진 점."""
    acc = 0
    for i in range(1, len(pts)):
        seg = math.dist(pts[i - 1], pts[i])
        if seg and acc + seg >= dist:
            t = (dist - acc) / seg
            return (pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0]), pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1]))
        acc += seg
    return pts[-1]


def perp_toward(u, want_x=None, want_y=None):
    """단위벡터 u에 수직이면서 원하는 쪽(x 또는 y 부호)을 향하는 단위벡터."""
    n = (-u[1], u[0])
    if (want_x is not None and n[0] * want_x < 0) or (want_y is not None and n[1] * want_y < 0):
        n = (-n[0], -n[1])
    return n


def unit(a, b):
    d = math.dist(a, b)
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def side_and_hem(pts, toward_x, hem_to_x, y_L, run=12.0):
    """옆선과, 옆선에 직각으로 시작해 수평으로 이어지는 밑단.
    pts: 옆선 기준점(위→아래, 마지막이 밑단), toward_x: 밑단이 향하는 x 부호."""
    side = catmull(pts)
    t = unit(side[-3], side[-1])
    h = run * abs(t[0] / t[1]) / 2
    end = (pts[-1][0] - t[0] / t[1] * h, y_L - h)
    side = catmull(pts[:-1] + [end])
    t = unit(side[-3], side[-1])
    n = perp_toward(t, want_x=toward_x)
    c = end
    hem = join(bez(c, (c[0] + n[0] * 4, c[1] + n[1] * 4), (c[0] + toward_x * (run - 4), y_L),
                   (c[0] + toward_x * run, y_L)), [(hem_to_x, y_L)])
    return side, hem


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# ── 패턴 조각 ─────────────────────────────────────────────────────────────

class Piece:
    def __init__(self, key, name, cut, outline, sa=SA, fold_x=None, hem=None,
                 grain=None, lines=(), dots=(), notches=(), texts=(), fold_label=None, fuse=None):
        self.key, self.name, self.cut_txt = key, name, cut
        self.outline = outline
        self.sa = sa
        self.fold_x = fold_x          # 이 x 좌표가 골선(시접 없음)
        self.hem = hem                # (밑단 점들, 밑단 시접)
        self.grain = grain            # ((x,y),(x,y))
        self.lines = list(lines)      # (점들, 스타일, 라벨)
        self.dots = list(dots)        # (x, y, 반지름)
        self.notches = list(notches)  # (x, y)
        self.texts = list(texts)      # (x, y, 문자열, 크기)
        self.fold_label = fold_label
        self.fuse = fuse              # 심지: "all" = 조각 전체, "hem" = 밑단 5cm
        self.sa_marks = []            # (점, 시접 cm 또는 문자열) — 선 안쪽에 시접 폭 표기
        self.build_cut()

    def build_cut(self):
        poly = Polygon(self.outline).buffer(0)
        cut = poly.buffer(self.sa, join_style=2, mitre_limit=2.5) if (self.sa > 0 and not NET) else poly
        if self.hem and not NET:
            hp, depth = self.hem
            s = self.sa
            a, b = hp[0], hp[-1]
            strip = Polygon([(a[0] - s * (1 if a[0] < b[0] else -1), a[1])] + list(hp) +
                            [(b[0] + s * (1 if a[0] < b[0] else -1), b[1]),
                             (b[0] + s * (1 if a[0] < b[0] else -1), b[1] + depth)] +
                            [(p[0], p[1] + depth) for p in reversed(hp)] +
                            [(a[0] - s * (1 if a[0] < b[0] else -1), a[1] + depth)]).buffer(0)
            cut = unary_union([cut, strip])
        if self.fold_x is not None:
            minx, miny, maxx, maxy = cut.bounds
            cut = cut.intersection(box(self.fold_x, miny - 1, maxx + 1, maxy + 1))
        self.poly = poly
        self.cut = cut
        self.cut_pts = list(cut.exterior.coords)
        self.fuse_poly = None
        if self.fuse == "all":
            self.fuse_poly = cut
        elif self.fuse == "hem" and self.hem:
            hp, depth = self.hem
            up = FUSE_HEM - depth      # 밑단 시접 끝에서 위로 5cm
            band = Polygon([(p[0], p[1] - up) for p in hp] +
                           [(p[0], p[1] + depth + 0.01) for p in reversed(hp)]).buffer(self.sa + 0.5, join_style=2)
            band = band.intersection(box(-1e4, min(p[1] for p in hp) - up, 1e4, 1e4))
            self.fuse_poly = band.intersection(cut)

    def bounds(self):
        return self.cut.bounds

    def moved(self, dx, dy):
        T = lambda p: (p[0] + dx, p[1] + dy)
        self.outline = [T(p) for p in self.outline]
        if self.hem:
            self.hem = ([T(p) for p in self.hem[0]], self.hem[1])
        if self.fold_x is not None:
            self.fold_x += dx
        if self.grain:
            self.grain = (T(self.grain[0]), T(self.grain[1]))
        self.lines = [([T(p) for p in pts], st, lab) for pts, st, lab in self.lines]
        self.dots = [(x + dx, y + dy, r) for x, y, r in self.dots]
        self.notches = [T(p) for p in self.notches]
        self.texts = [(x + dx, y + dy, s, z) for x, y, s, z in self.texts]
        self.sa_marks = [((p[0] + dx, p[1] + dy), v) for p, v in self.sa_marks]
        self.build_cut()
        return self


def strap(length, w_root, w_tip, point):
    """끝이 뾰족한 스트랩 (뿌리 쪽 x=0)."""
    return [(0, 0), (length - point, (w_root - w_tip) / 2), (length, w_root / 2),
            (length - point, w_root - (w_root - w_tip) / 2), (0, w_root)]


def draft(size):
    m = SIZES[size]
    C, N = m["chest"], m["neck"]
    piece_list = []

    # 몸판 원형 (반쪽, y는 아래로 증가, 옆목점 높이 = 0)
    Wh = C / 2 + 12                 # 반 가슴둘레 + 여유 12 (총 24)
    scye = C / 10 + 17.0            # 진동깊이
    backW = C / 8 + 9.5             # 뒤 품
    frontW = C / 8 + 10.5           # 앞 품
    sideX = backW + (Wh - backW - frontW) * 0.5
    bnw = N / 5 + 1.2               # 뒤 목너비
    fnw = bnw - 0.3
    fnd = N / 5 + 2.5               # 앞 목깊이
    cb_rise = 2.2                    # 뒷목 깊이
    y_w = cb_rise + m["nape_waist"] + 2
    y_h = y_w + 20
    y_L = cb_rise + m["coat_len"]
    DB = 10.0                        # 더블 여밈분
    pad = 0.8                        # 어깨패드 분
    flare = 3.0

    # 뒤판
    sh_ext = 0.105 * C - 8.5        # 뒤품선 밖으로 나가는 어깨 (사이즈 100 ≈ 1.8)
    sp_b = (backW + sh_ext, (backW + sh_ext - bnw) * math.tan(math.radians(19)) - pad)
    sh_len_b = math.dist((bnw, 0), sp_b)
    ub_sh = unit((bnw, 0), sp_b)                         # 옆목점 → 어깨점
    nb_up = perp_toward(ub_sh, want_y=-1)               # 어깨선에 수직, 위쪽
    # 목둘레: 뒤중심에서 수평으로 출발, 옆목점에는 어깨선과 직각으로 도착
    back_neck = bez((0, cb_rise), (bnw * 0.6, cb_rise), (bnw - nb_up[0] * 2.5, -nb_up[1] * 2.5), (bnw, 0))
    b_mid = (backW, sp_b[1] + (scye - sp_b[1]) * 0.6)
    nb_dn = perp_toward(ub_sh, want_y=1)                # 어깨점에서 진동 방향 (어깨선과 직각)
    back_arm1 = bez(sp_b, (sp_b[0] + nb_dn[0] * 3, sp_b[1] + nb_dn[1] * 3), (backW, b_mid[1] - 4), b_mid)
    back_arm = join(back_arm1,
                    bez(b_mid, (backW, b_mid[1] + 0.55 * (scye - b_mid[1])),
                        (backW + 0.4 * (sideX - backW), scye), (sideX, scye)))
    vent_top = y_L - 38
    back_side, back_hem = side_and_hem([(sideX, scye), (sideX - 0.8, y_w), (sideX - 0.2, y_h), (sideX + flare, y_L)],
                                       -1, -5, y_L)
    back_cb = [(-5, y_L), (-5, vent_top), (0, vent_top - 5), (0, cb_rise)]
    back_outline = join(back_neck, back_arm, back_side, back_hem, back_cb)
    piece_list.append(Piece(
        "back", "뒤판", "겉감 2장 · 안감 2장 (좌우 대칭)", back_outline, hem=(list(reversed(back_hem)), HEM),
        grain=((12, 30), (12, 80)),
        lines=[([(0, y_w), (sideX - 0.8, y_w)], "dash", "허리선"),
               ([(0, y_h), (sideX - 0.2, y_h)], "dash", "엉덩이선"),
               ([(0, vent_top - 5), (0, y_L)], "dot", "뒤중심 (트임 꺾임선)")],
        notches=[b_mid, point_at(back_arm, plen(back_arm1) + 1.2), (sideX - 0.8, y_w - 2.5), (sideX - 0.8, y_w + 2.5)],
        texts=[(5, y_w - 12, "뒤판 BACK", 1.4), (5, y_w - 9.5, f"사이즈 {size}", 0.9),
               (sideX - 6, y_w + 4, "벨트고리 위치", 0.5)]))

    # 앞판 (앞중심 x = Wh)
    f_snp = (Wh - fnw, 0)
    a = math.radians(22)
    sh_len_f = sh_len_b - 0.6
    sp_f = (f_snp[0] - sh_len_f * math.cos(a), sh_len_f * math.sin(a) - pad)
    uf_sh = unit(f_snp, sp_f)
    nf_in = perp_toward(uf_sh, want_y=1)                # 옆목점에서 목둘레 방향 (어깨선과 직각)
    # 뒤 목둘레가 어깨선과 약 97°로 만나므로, 앞은 약 84°로 맞춰 합이 180°에 가깝게
    c6, s6 = math.cos(math.radians(6)), math.sin(math.radians(6))
    nk = (nf_in[0] * c6 + uf_sh[0] * s6, nf_in[1] * c6 + uf_sh[1] * s6)
    front_neck = bez(f_snp, (f_snp[0] + nk[0] * fnd * 0.55, f_snp[1] + nk[1] * fnd * 0.55),
                     (Wh - fnw * 0.45, fnd), (Wh, fnd))
    f_mid = (Wh - frontW, sp_f[1] + (scye - sp_f[1]) * 0.55)
    front_arm1 = bez(sp_f, (sp_f[0] + nf_in[0] * 3, sp_f[1] + nf_in[1] * 3), (f_mid[0], f_mid[1] - 4), f_mid)
    front_arm_out = join(front_arm1,
                         bez(f_mid, (f_mid[0], f_mid[1] + 0.5 * (scye - f_mid[1])),
                             (sideX + 0.55 * (f_mid[0] - sideX), scye), (sideX, scye)))
    front_side, fh = side_and_hem([(sideX, scye), (sideX + 0.8, y_w), (sideX + 0.2, y_h), (sideX - flare, y_L)],
                                  1, Wh + DB, y_L)
    ce = (Wh + 2.5, fnd + 0.2)       # 칼라 끝점 (노치)
    lp = (Wh + DB, fnd - 2.0)        # 라펠 끝
    front_edge = [(Wh, fnd), ce, lp, (Wh + DB, y_L)]
    front_hem = list(reversed(fh))
    # 둘레: 옆목점 → 어깨 → 진동 → 옆선 → 밑단 → 앞단 → 목둘레
    front_outline = join([f_snp, sp_f], front_arm_out, front_side, list(reversed(front_hem)),
                         list(reversed(front_edge)), list(reversed(front_neck)))
    rows_y = [fnd + 3 + i * ((y_w + 8) - (fnd + 3)) / 4 for i in range(5)]
    btn = [(Wh + s * 7.0, y, 1.15) for y in rows_y for s in (-1, 1)]
    pa, pb = (sideX + 3.5, y_w + 5), (sideX + 7.5, y_w + 22)
    d = math.dist(pa, pb)
    nx, ny = (pb[1] - pa[1]) / d * -1, (pb[0] - pa[0]) / d
    pocket = [pa, pb, (pb[0] - nx * 4.5 * -1, pb[1] + ny * 0), pa]
    perp = (-(pb[1] - pa[1]) / d, (pb[0] - pa[0]) / d)  # 왼쪽 법선
    if perp[0] < 0:
        perp = (-perp[0], -perp[1])
    pocket = [pa, pb, (pb[0] + perp[0] * 4.5, pb[1] + perp[1] * 4.5),
              (pa[0] + perp[0] * 4.5, pa[1] + perp[1] * 4.5), pa]
    yg = sp_f[1] + 14
    gun_line_pts = [(Wh - 4, yg + 2), (Wh - 4, fnd)]
    piece_list.append(Piece(
        "front", "앞판", "겉감 2장 · 안감 2장 (좌우 대칭)", front_outline, hem=(list(reversed(front_hem)), HEM),
        grain=((Wh - 6, 32), (Wh - 6, 88)),
        lines=[([(Wh, fnd), (Wh, y_L)], "dashdot", "앞중심 CF"),
               ([(sideX + 0.8, y_w), (Wh + DB, y_w)], "dash", "허리선"),
               ([(sideX + 0.2, y_h), (Wh + DB, y_h)], "dash", "엉덩이선"),
               ([(f_snp[0] + 1.2, 1.0), (Wh + DB, rows_y[1] + 3)], "dot", "라펠 꺾임선"),
               (pocket, "solid", "주머니 웰트 위치"),
               ([(sp_f[0] + 1, yg + 0.5), (Wh - 4, yg + 2)] + gun_line_pts[1:], "dot", "건플랩 위치 (오른쪽)")],
        dots=btn,
        notches=[f_mid, ce, (sideX + 0.8, y_w - 2.5), (sideX + 0.8, y_w + 2.5)],
        texts=[(sideX + 3, y_w - 14, "앞판 FRONT", 1.4), (sideX + 3, y_w - 11.5, f"사이즈 {size}", 0.9),
               (Wh + 1, rows_y[4] + 5, "단추 5행 × 2열", 0.55),
               (sideX + 3, y_w + 27, "주머니 웰트", 0.55)]))

    # 앞 안단
    sh_dir = ((sp_f[0] - f_snp[0]) / sh_len_f, (sp_f[1] - f_snp[1]) / sh_len_f)
    q = (f_snp[0] + sh_dir[0] * 4, f_snp[1] + sh_dir[1] * 4)
    inner = bez((Wh - 4, scye), (Wh - 4, scye - 8), (q[0] + 0.5, q[1] + 6), q)
    facing_outline = join([q, f_snp], front_neck, front_edge[1:], [(Wh + DB, y_L), (Wh - 4, y_L)], inner)
    piece_list.append(Piece(
        "facing", "앞 안단", "겉감 2장 + 심지 2장 (전체)", facing_outline, fuse="all",
        hem=([(Wh - 4, y_L), (Wh + DB, y_L)], HEM), grain=((Wh + 8.6, y_w + 12), (Wh + 8.6, y_L - 8)),
        lines=[([(Wh, fnd), (Wh, y_L)], "dashdot", "CF")],
        dots=[(x, y, r) for x, y, r in btn if x > Wh - 4.5],
        notches=[ce],
        texts=[(Wh + 0.5, y_w + 14, "앞 안단", 1.1), (Wh + 0.5, y_w + 16, "FACING", 0.6),
               (Wh + 0.5, y_w + 17.7, f"사이즈 {size}", 0.6)]))

    # 건 플랩 (오른쪽 앞)
    arm_part, _ = cut_until(front_arm_out, lambda p: p[1] >= yg)
    g1 = arm_part[-1]
    neck_pts = [p for p in front_neck if p[0] <= Wh - 3]
    gun_outline = join([f_snp, sp_f], arm_part, [(g1[0] + 8, yg + 3.0), (Wh - 4, yg + 2)],
                       [(Wh - 3.2, (yg + 2 + neck_pts[-1][1]) / 2)], list(reversed(neck_pts)))
    piece_list.append(Piece(
        "gunflap", "건 플랩", "겉감 2장 (오른쪽 1벌)", gun_outline,
        grain=((Wh - 6.5, y_at_x(front_neck, Wh - 6.5) + 1.5), (Wh - 6.5, yg - 0.5)),
        texts=[(sp_f[0] + 4.5, yg - 5, "건 플랩 GUN FLAP", 0.8), (sp_f[0] + 4.5, yg - 3.6, f"사이즈 {size}", 0.55)]))

    # 뒤 스톰실드 (골선)
    sh_y = scye - 3
    bs_arm, _ = cut_until(back_arm, lambda p: p[1] >= sh_y)
    h1 = (bs_arm[-1][0] + 0.8, bs_arm[-1][1])
    shield_hem = catmull([h1, (h1[0] * 0.5, sh_y + 2.2), (0, sh_y + 3)])
    shield_outline = join(back_neck, [(bnw, 0), sp_b], bs_arm, [h1], shield_hem, [(0, cb_rise)])
    piece_list.append(Piece(
        "shield", "뒤 스톰실드", "겉감 2장 (골선)", shield_outline, fold_x=0,
        grain=((14, 5), (14, sh_y - 1)), fold_label="뒤중심 골선 FOLD",
        texts=[(3, sh_y - 9, "뒤 스톰실드", 1.0), (3, sh_y - 7.3, "STORM SHIELD", 0.55),
               (3, sh_y - 6, f"사이즈 {size}", 0.55)]))

    # 소매 (2장 소매)
    AH = plen(front_arm_out) + plen(back_arm)
    B = 0.2 * C + 20
    wW = 0.22 * C + 13
    SLg = m["sleeve"] + 3
    xt = B * 0.52

    def cap(CH):
        return join(bez((0, CH), (0.18 * B, CH * 0.98), (xt - 0.22 * B, 0), (xt, 0)),
                    bez((xt, 0), (xt + 0.22 * B, 0), (B - 0.2 * B, CH * 0.85), (B, CH)))
    lo, hi = 8, 26
    for _ in range(40):
        mid = (lo + hi) / 2
        if plen(cap(mid)) < AH + 3.0:
            lo = mid
        else:
            hi = mid
    CH = (lo + hi) / 2
    capc = cap(CH)
    xc = B / 2 - 2
    fq, bq = B * 0.25, B * 0.75
    wf, wb = xc - wW * 0.25, xc + wW * 0.25
    ef, eb = 2.5, 1.5
    y_e = CH + (SLg - CH) * 0.45
    tf0 = (fq - ef, y_at_x(capc, fq - ef))
    tb0 = (bq + eb, y_at_x(capc, bq + eb))
    tf1, tb1 = (wf - ef, SLg), (wb + eb, SLg)
    front_seam = catmull([tf0, (lerp(tf0, tf1, (y_e - tf0[1]) / (SLg - tf0[1]))[0] + 1.0, y_e), tf1])
    under_f0, under_f1 = (wf - ef, SLg), (xc - wW / 2, SLg)
    v1 = (xc + wW / 2 - B, SLg - CH)
    v2 = (xc - wW / 2, SLg - CH)
    ang = math.atan2(v1[1], v1[0]) - math.atan2(v2[1], v2[0])

    # 소매 노치: 진동둘레 노치와 같은 위치 (소매산 오그림을 앞 45% · 뒤 55%로 나눠 비례 배분)
    cap_len = plen(capc)
    fa_len, ba_len = plen(front_arm_out), plen(back_arm)
    ease_tot = cap_len - (fa_len + ba_len)
    ease_f, ease_b = ease_tot * 0.45, ease_tot * 0.55
    s_shoulder = fa_len + ease_f
    s_front = (fa_len - plen(front_arm1)) * (fa_len + ease_f) / fa_len
    s_back1 = cap_len - (ba_len - plen(back_arm1)) * (ba_len + ease_b) / ba_len
    s_back2 = cap_len - (ba_len - plen(back_arm1) - 1.2) * (ba_len + ease_b) / ba_len

    def sleeve_spot(sv):
        q = point_at(capc, sv)
        if fq - ef <= q[0] <= bq + eb:
            return "top", q
        if q[0] < fq - ef:
            return "under", rot((q[0] + B, q[1]), (B, CH), ang)
        return "under", q
    sl_notch = {"top": [], "under": [(B, CH)]}          # 밑소매 겨드랑이 = 옆선 위치
    for sv in (s_shoulder, s_front, s_back1, s_back2):
        k_, q_ = sleeve_spot(sv)
        sl_notch[k_].append(q_)
    p_sh = point_at(capc, s_shoulder)
    elbow_b = lerp(tb0, tb1, (y_e - tb0[1]) / (SLg - tb0[1]))
    top_outline = join(sub_by_x(capc, fq - ef, bq + eb), [tb0, tb1], [tf1], list(reversed(front_seam)))
    top_hem = [tf1, tb1]
    gx = (tf0[0] + tb0[0]) / 2 + 1
    piece_list.append(Piece(
        "topsleeve", "윗소매", "겉감 2장 · 안감 2장 · 밑단 심지 5cm", top_outline, hem=(top_hem, SLEEVE_HEM), fuse="hem",
        grain=((gx, CH + 4), (gx, SLg - 8)),
        lines=[([(tf0[0] + 1, y_e), (tb0[0] - 0.5, y_e)], "dash", "팔꿈치선"),
               ([(tf1[0], SLg - 6), (tb1[0], SLg - 6)], "dot", "소매 스트랩 위치")],
        notches=sl_notch["top"] + [elbow_b],
        texts=[(tf0[0] + 2.5, CH + 12, "윗소매", 1.2), (tf0[0] + 2.5, CH + 14, "TOP SLEEVE", 0.6),
               (tf0[0] + 2.5, CH + 15.7, f"사이즈 {size}", 0.6),
               (p_sh[0] - 1, p_sh[1] + 2.2, "어깨점", 0.5)]))

    # 밑소매: 소매 양쪽 겨드랑이 부분을 겨드랑이점에서 돌려 이어 붙이고, 밑단은 한 직선으로
    tr = lambda p: rot((p[0] + B, p[1]), (B, CH), ang)
    cap_back = sub_by_x(capc, bq + eb, B)                 # tb0 → 겨드랑이
    cap_front = [tr(p) for p in sub_by_x(capc, 0, fq - ef)]  # 겨드랑이 → 앞솔기 위
    hem_r, hem_l = (wb + eb, SLg), tr(under_f0)
    under_outline = join(cap_back, cap_front, [hem_l, hem_r], [tb0])
    under_poly = Polygon(under_outline)
    ub = under_poly.bounds
    piece_list.append(Piece(
        "undersleeve", "밑소매", "겉감 2장 · 안감 2장 · 밑단 심지 5cm", under_outline, fuse="hem",
        hem=([hem_r, hem_l] if hem_r[0] < hem_l[0] else [hem_l, hem_r], SLEEVE_HEM),
        grain=(((ub[0] + ub[2]) / 2, CH + 6), ((ub[0] + ub[2]) / 2, SLg - 8)),
        notches=sl_notch["under"] + [elbow_b],
        texts=[(ub[0] + 3, CH + 14, "밑소매", 1.1), (ub[0] + 3, CH + 16, "UNDER SLEEVE", 0.55),
               (ub[0] + 3, CH + 17.5, f"사이즈 {size}", 0.55)]))

    # 칼라
    Lc = plen(back_neck) + plen(front_neck) + math.dist((Wh, fnd), ce)
    stand_bot = catmull([(0, 0), (Lc * 0.5, -0.15), (Lc, -1.2)])
    stand_top = catmull([(0, -4.0), (Lc * 0.5, -3.95), (Lc - 0.5, -4.1)])
    stand_outline = join(stand_bot, [(Lc + 0.3, -2.6)], list(reversed(stand_top)))
    piece_list.append(Piece(
        "stand", "칼라 스탠드", "겉감 2장 + 심지 2장 (골선)", stand_outline, fold_x=0, fuse="all",
        grain=((Lc * 0.62, -2.1), (Lc - 2.5, -2.1)), fold_label="CB 골선",
        notches=[(plen(back_neck), y_at_x(stand_bot, plen(back_neck)))],
        texts=[(2.2, -2.4, f"칼라 스탠드 STAND · {size}", 0.5)]))
    fall_bot = catmull([(0, 0), (Lc * 0.5, 0.3), (Lc - 0.3, 1.5)])
    fall_top = catmull([(0, -7.5), (Lc * 0.6, -7.7), (Lc + 3.0, -8.6)])
    fall_outline = join(fall_bot, list(reversed(fall_top)))
    piece_list.append(Piece(
        "collar", "칼라", "겉감 2장 + 심지 2장 (골선)", fall_outline, fold_x=0, fuse="all",
        grain=((2, -1.7), (Lc - 4, -1.7)), fold_label="CB 골선",
        notches=[(plen(back_neck), y_at_x(fall_bot, plen(back_neck)))],
        texts=[(4, -5.6, "칼라 COLLAR", 0.8), (4, -4.2, f"사이즈 {size}", 0.55)]))

    # 작은 조각들
    epa = strap(sh_len_f - 1.5, 5.0, 4.0, 2.2)
    piece_list.append(Piece("epaulette", "견장", "겉감 4장 (2벌)", epa, grain=((1, 2.5), (sh_len_f - 5, 2.5)),
                            dots=[(sh_len_f - 4.5, 2.5, 0.8)],
                            texts=[(1, 1.2, "견장 EPAULETTE", 0.5), (1, 4.3, f"사이즈 {size}", 0.45)]))
    sl_strap_len = wW + 4
    piece_list.append(Piece("cuffstrap", "소매 스트랩", "겉감 4장 (2벌)", strap(sl_strap_len, 4.0, 4.0, 2.0),
                            grain=((2, 2), (sl_strap_len - 6, 2)),
                            texts=[(3, 1.3, "소매 스트랩 SLEEVE STRAP", 0.5), (3, 3.3, f"사이즈 {size}", 0.45)]))
    latch = [(0, 2.5), (2, 0), (14, 0), (16, 2.5), (14, 5), (2, 5)]
    piece_list.append(Piece("latch", "목 여밈 탭", "겉감 2장", latch, grain=((3, 2.5), (13, 2.5)),
                            dots=[(3.5, 2.5, 0.7), (12.5, 2.5, 0.7)],
                            texts=[(5, 1.6, "목 여밈 탭", 0.5), (5, 4.0, size, 0.45)]))
    welt = [(0, 0), (18, 0), (18, 9), (0, 9)]
    piece_list.append(Piece("welt", "주머니 웰트", "겉감 2장", welt, grain=((15, 1), (15, 8)),
                            lines=[([(0, 4.5), (18, 4.5)], "dot", "접는 선")],
                            texts=[(1.5, 2.8, "주머니 웰트 WELT", 0.6), (1.5, 7.2, f"사이즈 {size}", 0.5)]))
    bag = join([(0, 0), (20, 0)], bez((20, 0), (20, 22), (20, 30), (12, 30)), bez((12, 30), (2, 30), (0, 26), (0, 18)))
    piece_list.append(Piece("bag", "주머니감", "안감 또는 스레키 4장", bag, grain=((10, 3), (10, 26)),
                            texts=[(2, 9, "주머니감 POCKET BAG", 0.7), (2, 11, f"사이즈 {size}", 0.55)]))
    belt_tip = strap(25, 5.0, 5.0, 3.0)
    piece_list.append(Piece("belttip", "벨트 끝 본", "본 (재단 안내 참조)", belt_tip,
                            grain=((2, 2.5), (18, 2.5)),
                            texts=[(1.5, 1.4, "벨트 끝 본 — 벨트 끝 모양을 옮겨 그리세요", 0.45),
                                   (1.5, 4.1, "완성 폭 5cm", 0.45)]))

    # 시접 폭 표기 (선 위의 한 점 → 그 선 안쪽에 글자)
    mid = lambda pts: pts[len(pts) // 2]
    marks = {
        "back": [(mid(back_neck), SA), (lerp((bnw, 0), sp_b, 0.5), SA), (mid(back_arm), SA),
                 (mid(back_side), SA_SIDE), (((sideX + flare - 5) / 2, y_L), f"밑단 시접 {HEM:g}cm"),
                 ((-5, (vent_top + y_L) / 2), SA), ((0, (cb_rise + vent_top - 5) / 2), SA_SIDE)],
        "front": [(lerp(f_snp, sp_f, 0.5), SA), (mid(front_arm_out), SA), (mid(front_side), SA_SIDE),
                  (((Wh + DB + sideX - flare) / 2, y_L), f"밑단 시접 {HEM:g}cm"),
                  ((Wh + DB, (lp[1] + y_L) / 2), SA), (lerp(ce, lp, 0.5), SA), (mid(front_neck), SA)],
        "facing": [(lerp(q, f_snp, 0.5), SA), (mid(front_neck), SA), ((Wh + DB, (lp[1] + y_L) / 2 + 15), SA),
                   ((Wh + DB / 2 - 2, y_L), f"밑단 시접 {HEM:g}cm"), ((Wh - 4, scye + 12), SA),
                   (lerp(ce, lp, 0.5), SA)],
        "gunflap": [(lerp(f_snp, sp_f, 0.5), SA), (mid(arm_part), SA), (lerp(g1, (g1[0] + 8, yg + 3.0), 0.5), SA),
                    (((g1[0] + 8 + Wh - 4) / 2, yg + 2.5), SA), (mid(neck_pts), SA)],
        "shield": [(mid(back_neck), SA), (lerp((bnw, 0), sp_b, 0.5), SA), (mid(bs_arm), SA), (mid(shield_hem), SA)],
        "topsleeve": [((fq + 2, y_at_x(capc, fq + 2)), SA), (lerp(tb0, tb1, 0.5), SA), (front_seam[len(front_seam) // 4], SA),
                      (lerp(tf1, tb1, 0.5), f"밑단 시접 {SLEEVE_HEM:g}cm")],
        "undersleeve": [(mid(sub_by_x(capc, bq + eb, B)), SA), (lerp(tb0, (wb + eb, SLg), 0.5), SA),
                        (rot(lerp((fq - ef + B, y_at_x(capc, fq - ef)), (wf - ef + B, SLg), 0.5), (B, CH), ang), SA),
                        (lerp(hem_r, hem_l, 0.5), f"밑단 시접 {SLEEVE_HEM:g}cm")],
        "stand": [(mid(stand_bot), SA), (mid(stand_top), SA), ((Lc + 0.25, -2.4), SA)],
        "collar": [(mid(fall_bot), SA), (mid(fall_top), SA), (lerp((Lc - 0.3, 1.5), (Lc + 3.0, -8.6), 0.5), SA)],
        "epaulette": [(((sh_len_f - 1.5) * 0.6, 0.3), "사방 시접 1cm")],
        "cuffstrap": [((sl_strap_len / 2, 0), "사방 시접 1cm")],
        "latch": [((8, 0), "사방 1cm")],
        "welt": [((9, 9), "사방 시접 1cm")],
        "bag": [((10, 0), "사방 시접 1cm")],
        "belttip": [((11, 5), "사방 시접 1cm")],
    }
    for p in piece_list:
        p.sa_marks = marks.get(p.key, [])

    info = dict(Wh=Wh, scye=scye, AH=AH, CH=CH, B=B, wW=wW, SLg=SLg, Lc=Lc,
                chest_garment=4 * Wh / 2 * 1, length=m["coat_len"],
                belt_len=round(2 * (Wh - 1.6) * 2 / 2 + 45))
    info["chest_garment"] = 2 * Wh
    # 가상 봉제 검사용: 서로 꿰매는 선들
    info["seams"] = dict(
        back_neck=back_neck, front_neck=front_neck, neck_ext=[(Wh, fnd), ce],
        back_shoulder=[(bnw, 0), sp_b], front_shoulder=[f_snp, sp_f],
        back_arm=back_arm, front_arm=front_arm_out, back_side=back_side, front_side=front_side,
        cap=capc, back_hem=back_hem, front_hem=front_hem, front_edge=front_edge,
        top_front=front_seam, top_back=[tb0, tb1],
        under_front=[tf0, (wf - ef, SLg)], under_back=[tb0, (wb + eb, SLg)],
        stand_bot=stand_bot, stand_top=stand_top, fall_bot=fall_bot,
        facing_edge=front_edge, shield_neck=back_neck,
        top_wrist=[tf1, tb1], under_wrist=[hem_l, hem_r], under_front_rot=[tr(tf0), hem_l],
    )
    info.update(dict(sleeve_notch_arcs=dict(shoulder=s_shoulder, front=s_front, back1=s_back1, back2=s_back2),
                     arm_notch_from_side=dict(front=fa_len - plen(front_arm1), back1=ba_len - plen(back_arm1),
                                              back2=ba_len - plen(back_arm1) - 1.2),
                     sp_b=sp_b, sp_f=sp_f, sideX=sideX, y_w=y_w, y_h=y_h, y_L=y_L, cb_rise=cb_rise,
                     fnd=fnd, bnw=bnw, fnw=fnw, DB=DB, backW=backW, frontW=frontW, pad=pad))
    info["belt_len"] = round(2 * (2 * (Wh - 1.6)) / 2 + 45)
    return piece_list, info


# ── 배치 ─────────────────────────────────────────────────────────────────

TILE_W, TILE_H = 19.0, 27.7     # A4 인쇄 영역 (여백 1cm)
MARGIN = 1.0
COLS = 5
GAP = 2.0


def _profiles(p, step):
    """조각을 step 폭의 세로 띠로 나눠, 띠마다 위·아래 끝 (조각 bounds 기준)."""
    shape = p.cut.buffer(GAP / 2)
    minx, miny, maxx, maxy = shape.bounds
    k = int(math.ceil((maxx - minx) / step))
    top, bot = [], []
    for j in range(k):
        col = shape.intersection(box(minx + j * step, miny - 1, minx + (j + 1) * step, maxy + 1))
        if col.is_empty:
            top.append(1e9); bot.append(-1e9)
        else:
            top.append(col.bounds[1] - miny); bot.append(col.bounds[3] - miny)
    return minx, miny, top, bot


def _pack(pieces, cols, keyf, step=0.5):
    """윤곽 스카이라인 배치: 조각의 실제 윗선 모양대로 아래 조각 위에 끼워 넣는다."""
    import numpy as np
    n = int(cols * TILE_W / step)
    sky = np.zeros(n)
    offsets = {}
    for p in sorted(pieces, key=keyf):
        minx, miny, top, bot = _profiles(p, step)
        top, bot = np.array(top), np.array(bot)
        k = len(top)
        if k > n:
            return None
        valid = top < 1e8
        best = None
        for i in range(0, n - k + 1):
            y = max(0.0, float(np.max(sky[i:i + k][valid] - top[valid])))
            if best is None or y < best[0] - 1e-9:
                best = (y, i)
        y, i = best
        offsets[id(p)] = (i * step - minx, y - miny)
        seg = sky[i:i + k]
        sky[i:i + k] = np.where(valid, np.maximum(seg, y + bot), seg)
    rows = math.ceil((float(sky.max()) + GAP / 2) / TILE_H)
    return offsets, rows


def layout(pieces, col_options=(4, 5, 6)):
    """여러 배치(열 수 4~6 × 정렬 순서 4가지)를 시험해 인쇄할 A4 장수가 가장 적은 것을 고른다."""
    global COLS
    from shapely import affinity
    area = lambda p: -(p.bounds()[2] - p.bounds()[0]) * (p.bounds()[3] - p.bounds()[1])
    keys = [area, lambda p: -(p.bounds()[3] - p.bounds()[1]), lambda p: -(p.bounds()[2] - p.bounds()[0]),
            lambda p: -p.cut.area]
    best = None
    for cols in col_options:
        for keyf in keys:
            r = _pack(pieces, cols, keyf)
            if r is None:
                continue
            offsets, rows = r
            moved = [affinity.translate(p.cut, *offsets[id(p)]) for p in pieces]
            used = 0
            slivers = 0
            for ri in range(rows):
                for ci in range(cols):
                    t = box(ci * TILE_W, ri * TILE_H, (ci + 1) * TILE_W, (ri + 1) * TILE_H)
                    a = sum(m.intersection(t).area for m in moved)
                    if a > 0:
                        used += 1
                        slivers += a < 0.03 * TILE_W * TILE_H
            score = (used, slivers, rows)
            if best is None or score < best[0]:
                best = (score, cols, offsets, rows)
    _, COLS, offsets, rows = best
    for p in pieces:
        p.moved(*offsets[id(p)])
    return rows


# ── 그리기 ────────────────────────────────────────────────────────────────

def poly_path(c, pts, close=True):
    p = c.beginPath()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if close:
        p.close()
    return p


def text(c, x, y, s, size, font="KR", angle=0, anchor="left"):
    c.saveState()
    c.translate(x, y)
    c.scale(1 / cm, -1 / cm)
    if angle:
        c.rotate(-angle)
    c.setFont(font, size * cm)
    if anchor == "center":
        c.drawCentredString(0, 0, s)
    else:
        c.drawString(0, 0, s)
    c.restoreState()


def lw(c, pt):
    c.setLineWidth(pt / cm)


def arrow_line(c, a, b, head=0.8):
    c.line(a[0], a[1], b[0], b[1])
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for e, base in ((b, ang), (a, ang + math.pi)):
        for s in (-1, 1):
            q = (e[0] - head * math.cos(base + s * 0.4), e[1] - head * math.sin(base + s * 0.4))
            c.line(e[0], e[1], q[0], q[1])


def fuse_label_spot(p, g):
    """'심지' 글자 자리: 테두리·시접 글자·조각 글자·식서선에서 가장 먼 점."""
    avoid = [LineString(p.outline + [p.outline[0]])]
    line = avoid[0]
    for pt, _ in p.sa_marks:
        b = line.interpolate(line.project(Point(pt)))
        avoid.append(Point(b.x, b.y).buffer(2.4))
    for x, y, s_, z in p.texts:
        avoid.append(LineString([(x, y), (x + len(s_) * z * 0.7, y)]).buffer(z))
    for x, y, z in [(t[0], t[1], 0.45) for t in p.texts[:1]]:
        avoid.append(LineString([(x, y + 1.5), (x + 12, y + 1.5)]).buffer(0.6))  # 재단 줄
    if p.grain:
        avoid.append(LineString(p.grain).buffer(0.4))
    minx, miny, maxx, maxy = g.bounds
    for shrink in (0.6, 0.3, 0.1):
        inner = g.buffer(-shrink)
        best, spot = -1, None
        y = miny + 0.1
        while y < maxy:
            x = minx + 0.2
            while x < maxx:
                q = Point(x, y)
                if inner.contains(q):
                    d = min(a.distance(q) for a in avoid[1:]) if len(avoid) > 1 else 9
                    if d > best:
                        best, spot = d, (x, y)
                x += 0.4
            y += 0.2
        if spot:
            return spot
    return g.representative_point().coords[0]


def draw_fuse(c, p):
    """심지 붙이는 곳: 주황 빗금."""
    geoms = getattr(p.fuse_poly, "geoms", [p.fuse_poly])
    minx, miny, maxx, maxy = p.fuse_poly.bounds
    for g in geoms:
        if g.geom_type != "Polygon" or g.area < 0.5:
            continue
        c.saveState()
        c.clipPath(poly_path(c, list(g.exterior.coords)), stroke=0, fill=0)
        c.setStrokeColorRGB(0.93, 0.55, 0.2)
        lw(c, 0.5)
        k = minx - (maxy - miny)
        while k < maxx:
            c.line(k, maxy, k + (maxy - miny), miny)
            k += 0.7
        c.restoreState()
        gx, gy = fuse_label_spot(p, g)
        c.setFillColorRGB(1, 1, 1)
        c.rect(gx - 0.9, gy - 0.45, 1.8, 0.6, stroke=0, fill=1)
        c.setFillColorRGB(0.8, 0.4, 0.1)
        text(c, gx, gy, "심지", 0.45, "KRB", anchor="center")


def draw_sa_marks(c, p):
    """완성선 안쪽에 '시접 1cm' 같은 글자를 선 방향으로 적는다."""
    line = LineString(p.outline + [p.outline[0]])
    for pt, v in p.sa_marks:
        label = v if isinstance(v, str) else f"시접 {v:g}cm"
        d = line.project(Point(pt))
        a, b = line.interpolate(max(0, d - 0.5)), line.interpolate(d + 0.5)
        tx, ty = b.x - a.x, b.y - a.y
        L = math.hypot(tx, ty) or 1
        nx, ny = -ty / L, tx / L
        base = line.interpolate(d)
        if not p.poly.contains(Point(base.x + nx * 0.3, base.y + ny * 0.3)):
            nx, ny = -nx, -ny
        ang = math.degrees(math.atan2(ty, tx))
        if ang > 90 or ang < -90:
            ang += 180
        # 글자 가운데를 선 안쪽 0.75cm에 두고, 기준선은 글자 높이 절반만큼 아래로
        r = math.radians(ang)
        down = (-math.sin(r), math.cos(r))
        x = base.x + nx * 0.75 + down[0] * 0.16
        y = base.y + ny * 0.75 + down[1] * 0.16
        c.setFillColorRGB(0.75, 0.1, 0.1)
        text(c, x, y, label, 0.45, "KRB", angle=ang, anchor="center")


def cut_lines(p):
    """'재단: …' 안내. 6cm보다 길면 ' · ' 에서 줄을 나눈다."""
    s_ = f"재단: {p.cut_txt}"
    if stringWidth(s_, "KR", 0.45 * cm) / cm <= 6:
        return [s_]
    return s_.split(" · ")


def text_box(x, y, s_, z, font="KR"):
    w = stringWidth(s_, font, z * cm) / cm
    return Polygon([(x, y - 0.75 * z), (x + w, y - 0.75 * z), (x + w, y + 0.15 * z), (x, y + 0.15 * z)])


def sa_label_box(p, pt, label):
    line = LineString(p.outline + [p.outline[0]])
    d = line.project(Point(pt))
    a, b = line.interpolate(max(0, d - 0.5)), line.interpolate(d + 0.5)
    tx, ty = b.x - a.x, b.y - a.y
    L = math.hypot(tx, ty) or 1
    nx, ny = -ty / L, tx / L
    base = line.interpolate(d)
    if not p.poly.contains(Point(base.x + nx * 0.3, base.y + ny * 0.3)):
        nx, ny = -nx, -ny
    ang = math.degrees(math.atan2(ty, tx))
    if ang > 90 or ang < -90:
        ang += 180
    w = stringWidth(label, "KRB", 0.45 * cm) / cm
    from shapely import affinity
    r = Polygon([(-w / 2, -0.2), (w / 2, -0.2), (w / 2, 0.2), (-w / 2, 0.2)])
    return affinity.translate(affinity.rotate(r, ang, origin=(0, 0)), base.x + nx * 0.75, base.y + ny * 0.75)


def cut_positions(p):
    """'재단' 줄 자리: 아래 → 마지막 줄 오른쪽 → 제목 위 순서로, 조각 안 빈자리를 찾는다."""
    tx = p.texts[0][0]
    block = [t for t in p.texts[:3] if abs(t[0] - tx) < 1e-6]
    last = max(block, key=lambda t: t[1])
    first = p.texts[0]
    lines = cut_lines(p)
    one = " ".join(lines)
    obst = [text_box(x, y, s_, z, "KRB" if i == 0 else "KR") for i, (x, y, s_, z) in enumerate(p.texts)]
    obst += [sa_label_box(p, pt, v if isinstance(v, str) else f"시접 {v:g}cm") for pt, v in p.sa_marks]
    if p.grain:
        obst.append(LineString(p.grain).buffer(0.15))
    obst += [LineString(pts) for pts, _, _ in p.lines]
    obst += [Point(x, y).buffer(r) for x, y, r in p.dots]
    obst += [Point(n).buffer(0.45) for n in p.notches]
    inner = p.poly.buffer(-0.15)
    lastw = stringWidth(last[2], "KR", last[3] * cm) / cm
    cands = [[(tx, last[1] + 0.8 + i * 0.65, ln) for i, ln in enumerate(lines)],
             [(tx + lastw + 0.5, last[1], one)],
             [(tx, first[1] - first[3] * 0.9 - 0.25 - (len(lines) - 1 - i) * 0.65, ln) for i, ln in enumerate(lines)]]
    for cand in cands:
        boxes = [text_box(x, y, ln, 0.45) for x, y, ln in cand]
        if all(inner.contains(b) for b in boxes) and not any(b.intersects(o) for b in boxes for o in obst):
            return cand
    return cands[0]


def draw_piece(c, p):
    # 재단선
    c.setFillColorRGB(0.965, 0.955, 0.93)
    c.setStrokeColorRGB(0, 0, 0)
    lw(c, 1.0)
    c.drawPath(poly_path(c, p.cut_pts), stroke=1, fill=1)
    if p.fuse_poly is not None and not p.fuse_poly.is_empty:
        draw_fuse(c, p)
    # 완성선 (시접 포함 버전에서만 점선으로 따로)
    if not NET:
        c.setStrokeColorRGB(0.25, 0.25, 0.25)
        lw(c, 0.5)
        c.setDash([0.3, 0.2])
        c.drawPath(poly_path(c, p.outline), stroke=1, fill=0)
        c.setDash([])
    if NET:
        draw_sa_marks(c, p)
    # 골선
    if p.fold_x is not None:
        miny, maxy = p.cut.bounds[1], p.cut.bounds[3]
        c.setStrokeColorRGB(0.6, 0.1, 0.1)
        lw(c, 2.0)
        c.line(p.fold_x, miny, p.fold_x, maxy)
        lw(c, 0.6)
        mid = (miny + maxy) / 2
        span = min(8, (maxy - miny) * 0.35)
        for yy in (mid - span, mid + span):
            c.line(p.fold_x, yy, p.fold_x + 1.5, yy)
        c.line(p.fold_x + 1.5, mid - span, p.fold_x + 1.5, mid + span)
        c.setFillColorRGB(0.6, 0.1, 0.1)
        text(c, p.fold_x + 0.35, mid - span - 0.4, p.fold_label or "골선", 0.45, "KRB")
    # 내부선
    styles = {"dash": [0.6, 0.3], "dot": [0.12, 0.25], "dashdot": [0.8, 0.25, 0.15, 0.25], "solid": []}
    for pts, st, lab in p.lines:
        c.setStrokeColorRGB(0.15, 0.3, 0.55)
        lw(c, 0.6)
        c.setDash(styles[st])
        c.drawPath(poly_path(c, pts, close=False), stroke=1, fill=0)
        c.setDash([])
        if lab:
            c.setFillColorRGB(0.15, 0.3, 0.55)
            a, b = pts[0], pts[1]
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            if ang > 90 or ang < -90:
                ang += 180
            text(c, a[0] + (b[0] - a[0]) * 0.1 + 0.3, a[1] + (b[1] - a[1]) * 0.1 - 0.25, lab, 0.42, angle=ang)
    # 단추
    c.setStrokeColorRGB(0, 0, 0)
    lw(c, 0.6)
    for x, y, r in p.dots:
        c.circle(x, y, r, stroke=1, fill=0)
        c.line(x - 0.4, y, x + 0.4, y)
        c.line(x, y - 0.4, x, y + 0.4)
    # 노치 (완성선에서 바깥쪽으로)
    lw(c, 1.0)
    for n in p.notches:
        line = LineString(p.outline + [p.outline[0]])
        d = line.project(Point(n))
        a, b = line.interpolate(max(0, d - 0.3)), line.interpolate(d + 0.3)
        tx, ty = b.x - a.x, b.y - a.y
        L = math.hypot(tx, ty) or 1
        nx, ny = -ty / L, tx / L
        base = line.interpolate(d)
        if p.poly.contains(Point(base.x + nx * 0.3, base.y + ny * 0.3)):
            nx, ny = -nx, -ny
        out = 0.6 if NET else p.sa + 0.05
        c.line(base.x - nx * 0.3, base.y - ny * 0.3, base.x + nx * out, base.y + ny * out)
    # 식서
    if p.grain:
        c.setStrokeColorRGB(0, 0, 0)
        lw(c, 0.7)
        arrow_line(c, p.grain[0], p.grain[1])
    # 글자
    c.setFillColorRGB(0, 0, 0)
    for i, (x, y, s, z) in enumerate(p.texts):
        text(c, x, y, s, z, "KRB" if i == 0 else "KR")
    tx = p.texts[0][0]
    block = [t for t in p.texts[:3] if abs(t[0] - tx) < 1e-6]
    y_last = max(t[1] for t in block)
    for x, y, ln in cut_positions(p):
        text(c, x, y, ln, 0.45)


def draw_grid(c, W, H):
    c.setStrokeColorRGB(0.86, 0.88, 0.9)
    lw(c, 0.3)
    x = 0
    while x <= W:
        c.line(x, 0, x, H)
        x += 5
    y = 0
    while y <= H:
        c.line(0, y, W, y)
        y += 5


def tile_used(pieces, ci, ri):
    t = box(ci * TILE_W, ri * TILE_H, (ci + 1) * TILE_W, (ri + 1) * TILE_H)
    # 가장자리에 선만 닿는 칸(면적 0)은 이웃 장에 이미 그려지므로 인쇄하지 않는다
    return any(p.cut.intersection(t).area > 0.05 for p in pieces)


def tile_name(ci, ri):
    return f"{chr(65 + ci)}{ri + 1}"


def test_square(c, x, y, s, label):
    """페이지 좌표(pt) 기준 시험 사각형."""
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.8)
    c.rect(x, y, s * cm, s * cm)
    c.setFont("KRB", 9)
    c.drawCentredString(x + s * cm / 2, y + s * cm / 2 + 4, label)
    c.setFont("KR", 7)
    c.drawCentredString(x + s * cm / 2, y + s * cm / 2 - 8, "자로 재어 확인")


def cover_page(c, size, info, pieces, rows, used):
    PW, PH = A4
    m = SIZES[size]
    c.setFillColorRGB(0, 0, 0)
    c.setFont("KRB", 20)
    c.drawString(1.5 * cm, PH - 2.3 * cm, "남성 더블브레스티드 트렌치코트")
    c.setFont("KR", 11)
    c.drawString(1.5 * cm, PH - 3.1 * cm, f"사이즈 {size}  ·  A4 분할 인쇄 패턴 (실제 크기 1:1)  ·  " + ("시접 미포함 (시접 폭은 각 선에 표기)" if NET else "시접 포함"))
    y = PH - 4.2 * cm
    c.setFont("KRB", 10)
    c.drawString(1.5 * cm, y, "기준 신체 치수")
    c.setFont("KR", 9)
    rows_t = [f"가슴둘레 {m['chest']}cm · 키 {m['height']}cm · 목둘레 {m['neck']}cm",
              f"뒷목점~허리 {m['nape_waist']}cm · 소매길이 {m['sleeve']}cm",
              f"완성 치수: 가슴둘레 {info['chest_garment']:.0f}cm · 옷길이 {info['length']}cm · "
              f"소매길이 {info['SLg']:.1f}cm"]
    for i, s in enumerate(rows_t):
        c.drawString(1.5 * cm, y - (i + 1) * 13, s)
    y -= 4 * 13 + 6
    c.setFont("KRB", 10)
    c.drawString(1.5 * cm, y, "인쇄 · 붙이기 방법")
    c.setFont("KR", 8.6)
    steps = ["1. 인쇄 설정에서 '실제 크기(100%)'를 선택하세요. '페이지에 맞춤'은 끄세요.",
             "2. 먼저 이 페이지만 인쇄해 아래 10cm 시험 사각형을 자로 재어 확인하세요.",
             f"3. 패턴 페이지는 2쪽 배치도의 글자 칸(A1, B1 …)만 들어 있어요. 총 {len(used)}장.",
             "4. 각 장의 회색 테두리선을 기준으로 왼쪽·위쪽 여백을 잘라내고,",
             "    왼쪽 장과 위쪽 장의 테두리선에 맞춰 겹쳐 테이프로 붙이세요.",
             "5. 테두리 가운데 마름모 표시와 5cm 격자선이 이어지는지 확인하면 정확하게 맞출 수 있어요."]
    for i, s in enumerate(steps):
        c.drawString(1.5 * cm, y - (i + 1) * 12.5, s)
    y -= (len(steps) + 1) * 12.5 + 4
    c.setFont("KRB", 10)
    c.drawString(1.5 * cm, y, "선 보는 법")
    c.setFont("KR", 8.6)
    legend = [("굵은 실선 = 완성선(박음선). 시접은 직접 그려 주세요 — 빨간 글자가 그 선의 시접 폭"
               if NET else "굵은 실선 = 재단선 (시접 포함: 기본 1cm, 몸판·소매 밑단 4cm)"),
              ("시접: 기본 1cm · 옆선·뒤중심 1.5cm · 몸판·소매 밑단 4cm · 골선은 시접 없음" if NET
               else "점선 = 완성선(박음선)"),
              "짧은 눈금 = 맞춤 표시(노치) · 양방향 화살표 = 식서(올) 방향",
              "빨간 굵은 선 = 골선 (원단을 접어서 재단, 시접 없음) · 원 = 단추 위치",
              "주황 빗금 = 심지 붙이는 곳: 칼라 · 칼라 스탠드 · 앞 안단(전체), 윗소매 · 밑소매(밑단 5cm)"]
    if NET:
        legend.append("  (소매 밑단 심지 5cm = 밑단 시접 4cm + 완성선 위 1cm. 패턴엔 완성선 위 1cm만 빗금)")
    for i, s in enumerate(legend):
        c.drawString(1.5 * cm, y - (i + 1) * 12.5, s)
    test_square(c, 1.5 * cm, 1.5 * cm, 10, "10 × 10 cm")
    test_square(c, 12.5 * cm, 1.5 * cm, 5, "5 × 5 cm")
    c.showPage()
    y = PH - 2.0 * cm
    c.setFillColorRGB(0, 0, 0)
    c.setFont("KRB", 10)
    c.drawString(1.5 * cm, y, "재단 목록")
    c.setFont("KR", 8.2)
    items = [f"{p.name}: {p.cut_txt}" for p in pieces if p.key != "belttip"]
    items += [f"벨트: {info['belt_len']} × 12cm 직사각형 1장 (시접 1cm 포함 치수, 반 접어 완성 폭 5cm, 끝은 '벨트 끝 본')",
              "벨트고리: 6 × 6cm 4장 (시접 포함, 허리 옆선용)  ·  소매 버클 2개, 벨트 버클 1개",
              "단추: 앞 2.3cm 10개 (패턴 표시) + 안쪽 여밈 단추 1개, 1.6cm 4개 (견장 2 · 목 여밈 탭 2)",
              "안감: 앞판·뒤판·윗소매·밑소매 본 사용 (안단 폭만큼 앞판 안감 제외, 뒤중심 주름 2cm 추가)"]
    for i, s in enumerate(items):
        c.drawString(1.5 * cm, y - (i + 1) * 11.5, s)
    # 배치도
    y -= (len(items) + 2) * 11.5
    mw = 9.0 * cm
    sc0 = mw / (COLS * TILE_W)
    mw = min(mw, (y - 2.5 * cm) / (rows * TILE_H * sc0) * mw)
    mx, my = (PW - mw) / 2, y
    sc = mw / (COLS * TILE_W)
    c.setFont("KRB", 10)
    c.drawString(mx, my + 4, "페이지 배치도")
    top = my - 8
    c.saveState()
    c.translate(mx, top)
    c.scale(sc, -sc)
    for ri in range(rows):
        for ci in range(COLS):
            x0, y0 = ci * TILE_W, ri * TILE_H
            if (ci, ri) in used:
                c.setFillColorRGB(1, 1, 1)
            else:
                c.setFillColorRGB(0.9, 0.9, 0.9)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.setLineWidth(0.5 / sc)
            c.rect(x0, y0, TILE_W, TILE_H, stroke=1, fill=1)
    for p in pieces:
        c.setStrokeColorRGB(0, 0, 0)
        c.setFillColorRGB(0.93, 0.9, 0.82)
        c.setLineWidth(0.5 / sc)
        c.drawPath(poly_path(c, p.cut_pts), stroke=1, fill=1)
    c.restoreState()
    c.setFillColorRGB(0.2, 0.3, 0.6)
    for (ci, ri) in used:
        c.setFont("KRB", 7)
        c.drawCentredString(mx + (ci + 0.5) * TILE_W * sc, top - (ri + 0.5) * TILE_H * sc - 2, tile_name(ci, ri))
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont("KR", 7)
    c.drawString(mx, top - rows * TILE_H * sc - 12, "회색 칸은 비어 있어 인쇄하지 않아요.")
    c.showPage()


def tile_page(c, pieces, ci, ri, rows, size):
    PW, PH = A4
    c.saveState()
    c.translate(MARGIN * cm - ci * TILE_W * cm, PH - MARGIN * cm + ri * TILE_H * cm)
    c.scale(cm, -cm)
    x0, y0 = ci * TILE_W, ri * TILE_H
    clip = c.beginPath()
    clip.rect(x0, y0, TILE_W, TILE_H)
    c.clipPath(clip, stroke=0, fill=0)
    draw_grid(c, COLS * TILE_W, rows * TILE_H)
    t = box(x0, y0, x0 + TILE_W, y0 + TILE_H)
    for p in pieces:
        if p.cut.intersects(t):
            draw_piece(c, p)
    c.restoreState()
    # 테두리 & 맞춤 표시 (페이지 좌표)
    L, B = MARGIN * cm, PH - MARGIN * cm - TILE_H * cm
    W, H = TILE_W * cm, TILE_H * cm
    c.setStrokeColorRGB(0.55, 0.55, 0.55)
    c.setLineWidth(0.5)
    c.rect(L, B, W, H)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    for (x, y) in ((L + W / 2, B + H), (L + W / 2, B), (L, B + H / 2), (L + W, B + H / 2)):
        p = c.beginPath()
        p.moveTo(x, y + 6); p.lineTo(x + 6, y); p.lineTo(x, y - 6); p.lineTo(x - 6, y); p.close()
        c.drawPath(p, stroke=0, fill=1)
    name = tile_name(ci, ri)
    c.setFont("KRB", 9)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(L, PH - MARGIN * cm + 6, f"{name}")
    c.setFont("KR", 7)
    c.drawRightString(L + W, PH - MARGIN * cm + 6, f"트렌치코트 {size} · 열 {chr(65 + ci)} / 행 {ri + 1} · 실제 크기로 인쇄")
    nb = []
    if ci > 0: nb.append(f"왼쪽 {tile_name(ci - 1, ri)}")
    if ri > 0: nb.append(f"위 {tile_name(ci, ri - 1)}")
    if ci < COLS - 1: nb.append(f"오른쪽 {tile_name(ci + 1, ri)}")
    if ri < rows - 1: nb.append(f"아래 {tile_name(ci, ri + 1)}")
    c.drawString(L, MARGIN * cm - 12, "  ".join(nb))
    if ci == 0 and ri == 0:
        c.setFillColorRGB(1, 1, 1)
        c.rect(L + 0.5 * cm, B + 0.5 * cm, 3 * cm, 3 * cm, stroke=0, fill=1)
        c.setFillColorRGB(0, 0, 0)
        test_square(c, L + 0.5 * cm, B + 0.5 * cm, 3, "3cm")
    c.showPage()


def build(size):
    pieces, info = draft(size)
    rows = layout(pieces)
    used = [(ci, ri) for ri in range(rows) for ci in range(COLS) if tile_used(pieces, ci, ri)]
    os.makedirs(OUT_DIR, exist_ok=True)

    sfx = "" if NET else "_withSA"
    path = os.path.join(OUT_DIR, f"trench_men_{size}_A4{sfx}.pdf")
    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle(f"남성 트렌치코트 패턴 {size} (A4)")
    cover_page(c, size, info, pieces, rows, used)
    for ci, ri in used:
        tile_page(c, pieces, ci, ri, rows, size)
    c.save()

    # 복사실용 한 장짜리: 대형 출력 용지(A0 폭 84cm, 36인치 롤 91cm)에 들어가게 폭 76cm(4열)로 따로 배치
    a4_cols, a4_rows = COLS, rows
    pieces, info = draft(size)
    rows = layout(pieces, col_options=(4,))
    W, H = COLS * TILE_W, rows * TILE_H
    full = os.path.join(OUT_DIR, f"trench_men_{size}_fullsize{sfx}.pdf")
    c = canvas.Canvas(full, pagesize=(W * cm, H * cm))
    c.setTitle(f"남성 트렌치코트 패턴 {size} (전체 1장)")
    c.saveState()
    c.translate(0, H * cm)
    c.scale(cm, -cm)
    draw_grid(c, W, H)
    for p in pieces:
        draw_piece(c, p)
    c.restoreState()
    c.save()
    print(f"{size}: A4 {len(used) + 2}쪽 (안내 2쪽 포함) · 한 장짜리 {W:.0f}×{H:.0f}cm · "
          f"진동둘레 {info['AH']:.1f} · 소매산 {info['CH']:.1f} · 칼라길이 {info['Lc']:.1f}")
    return path


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--sa" in args:
        NET = False
        args.remove("--sa")
    for s in (args or list(SIZES)):
        build(s)
