#!/usr/bin/env python3
"""제도 검토: 꿰맨 뒤 선이 매끄럽게 이어지는지(각도), 노치가 짝끼리 맞는지.

두 조각을 이어 꿰매면, 이음점에서 두 조각의 안쪽 각도 합이 180°일 때
진동둘레·목둘레·밑단이 꺾이지 않고 매끄럽게 이어진다.

사용법: python3 review_draft.py 100
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_trench as G  # noqa: E402


def direction(pts, at_start, d=0.6):
    """선의 끝점에서 선 안쪽으로 d cm 들어간 방향 (단위 벡터)."""
    seq = pts if at_start else list(reversed(pts))
    p0 = seq[0]
    acc = 0
    for i in range(1, len(seq)):
        acc += math.dist(seq[i - 1], seq[i])
        if acc >= d:
            q = seq[i]
            break
    else:
        q = seq[-1]
    v = (q[0] - p0[0], q[1] - p0[1])
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def angle(u, v):
    return math.degrees(math.acos(max(-1, min(1, u[0] * v[0] + u[1] * v[1]))))


def pos_along(pts, frac_len):
    """선 시작에서 frac_len cm 떨어진 점."""
    acc = 0
    for i in range(1, len(pts)):
        seg = math.dist(pts[i - 1], pts[i])
        if acc + seg >= frac_len:
            t = (frac_len - acc) / seg
            return (pts[i - 1][0] + t * (pts[i][0] - pts[i - 1][0]), pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1]))
        acc += seg
    return pts[-1]


def dist_along(pts, target):
    """선 시작부터 target 점(가장 가까운 위치)까지의 길이."""
    best, bi, acc_at = 1e9, 0, 0
    acc = 0
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        seg = math.dist(a, b)
        for k in range(11):
            t = k / 10
            q = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            d = math.dist(q, target)
            if d < best:
                best, acc_at = d, acc + t * seg
        acc += seg
    return acc_at, best


def main(size):
    pieces, info = G.draft(size)
    S = info["seams"]
    rows = []

    def junction(name, a1, a2, b1, b2, target=180, tol=8):
        """조각 A의 두 선(a1,a2)과 조각 B의 두 선(b1,b2)이 만나는 점의 안쪽 각 합."""
        ang = angle(*a1) + angle(*b1) if b1 else angle(*a1)
        ok = abs(ang - target) <= tol
        rows.append((name, ang, target, tol, ok))

    # 어깨점: 앞(어깨선, 진동) + 뒤(어깨선, 진동)
    fs, bs = S["front_shoulder"], S["back_shoulder"]
    fa, ba = S["front_arm"], S["back_arm"]
    junction("어깨점: 진동둘레가 꺾이지 않음",
             (direction(fs, False), direction(fa, True)), None,
             (direction(bs, False), direction(ba, True)), None)
    # 옆목점: 목둘레
    fn, bn = S["front_neck"], S["back_neck"]
    junction("옆목점: 목둘레가 꺾이지 않음",
             (direction(fs, True), direction(fn, True)), None,
             (direction(bs, True), direction(bn, False)), None)
    # 겨드랑이: 진동 + 옆선
    fsd, bsd = S["front_side"], S["back_side"]
    junction("겨드랑이: 진동둘레 밑이 꺾이지 않음",
             (direction(fa, False), direction(fsd, True)), None,
             (direction(ba, False), direction(bsd, True)), None)
    # 밑단 옆선 모서리
    fh, bh = S["front_hem"], S["back_hem"]
    junction("옆선 밑단: 밑단선이 꺾이지 않음",
             (direction(fsd, False), direction(list(reversed(fh)), True)), None,
             (direction(bsd, False), direction(bh, True)), None)
    # 뒤중심 목점: 뒤중심선과 목둘레가 직각 (좌우 뒤판이 만나 매끈)
    junction("뒤중심 목점: 직각", (direction(bn, True), (0, 1)), None, None, None, target=90, tol=3)
    # 소매: 윗소매/밑소매 솔기가 소매산에서 만나는 점
    cap = S["cap"]
    tf, tb = S["top_front"], S["top_back"]
    uf, ub = S["under_front"], S["under_back"]
    # 소매산 방향: 앞솔기 점에서 윗소매 쪽은 +x, 밑소매 쪽은 -x
    def cap_dirs(pt):
        i = min(range(len(cap)), key=lambda k: math.dist(cap[k], pt))
        fwd = direction(cap[i:], True)
        back = direction(list(reversed(cap[:i + 1])), True)
        return fwd, back
    f_fwd, f_back = cap_dirs(tf[0])
    junction("소매 앞솔기 위: 소매산이 꺾이지 않음",
             (direction(tf, True), f_fwd), None, (direction(uf, True), f_back), None)
    b_fwd, b_back = cap_dirs(tb[0])
    junction("소매 뒷솔기 위: 소매산이 꺾이지 않음",
             (direction(tb, True), b_back), None, (direction(ub, True), b_fwd), None)
    tw, uw = S["top_wrist"], S["under_wrist"]          # 윗: 앞→뒤, 밑: 앞(돌린 쪽)→뒤
    ufr = S["under_front_rot"]                          # 밑소매 앞솔기 (실제 조각 위치)
    junction("소매 앞솔기 밑단: 밑단이 꺾이지 않음",
             (direction(tf, False), direction(tw, True)), None,
             (direction(ufr, False), direction(uw, True)), None)
    junction("소매 뒷솔기 밑단: 밑단이 꺾이지 않음",
             (direction(tb, False), direction(tw, False)), None,
             (direction(ub, False), direction(uw, False)), None)

    # 노치 짝 맞춤
    notch = []
    # 앞 진동 노치(f_mid)는 겨드랑이에서 몇 cm? 소매 앞쪽 노치도 같은 거리에 있어야 함 (소매산 오그림 고려)
    notch.append(("앞 진동 노치: 겨드랑이에서", info["arm_notch_from_side"]["front"]))
    notch.append(("뒤 진동 노치: 겨드랑이에서", info["arm_notch_from_side"]["back1"]))
    # 소매산 오그림 배분: 어깨점 노치 기준 앞/뒤
    arcs = info["sleeve_notch_arcs"]
    cap_len = G.plen(cap)
    ease_f = arcs["shoulder"] - G.plen(fa)
    ease_b = (cap_len - arcs["shoulder"]) - G.plen(ba)
    nrows = [("소매산 앞쪽 오그림 (어깨점 노치~겨드랑이, 앞 진동 대비)", ease_f, 0.8, 2.0),
             ("소매산 뒤쪽 오그림 (어깨점 노치~겨드랑이, 뒤 진동 대비)", ease_b, 1.0, 2.2)]
    # 진동 노치 ↔ 소매 노치: 겨드랑이에서 같은 거리 (+ 그 구간 오그림 0~1cm)
    fromside = info["arm_notch_from_side"]
    nrows.append(("앞 노치: 소매 쪽 − 진동 쪽 거리", arcs["front"] - fromside["front"], 0.0, 1.0))
    nrows.append(("뒤 노치1: 소매 쪽 − 진동 쪽 거리", (cap_len - arcs["back1"]) - fromside["back1"], 0.0, 1.0))
    nrows.append(("뒤 노치2: 소매 쪽 − 진동 쪽 거리", (cap_len - arcs["back2"]) - fromside["back2"], 0.0, 1.0))
    # 노치가 실제로 소매 조각 위에 찍혀 있는지
    keys = [p.key for p in pieces]
    top, under = pieces[keys.index("topsleeve")], pieces[keys.index("undersleeve")]
    from shapely.geometry import LineString, Point
    on = lambda p, q: LineString(p.outline + [p.outline[0]]).distance(Point(q)) < 0.05
    nall = [n for n in top.notches + under.notches if n[1] <= info["CH"] + 0.01]   # 소매산 노치만 (팔꿈치 제외)
    nrows.append(("소매 노치가 모두 소매 외곽선 위에 있음 (개수 5)", float(sum(on(top, q) or on(under, q) for q in nall)), 5, 5))
    # 칼라 끝 = 노치(ce): 칼라밴드 길이 = 뒤목 + 앞목 + CF~노치
    neck_total = G.plen(bn) + G.plen(fn) + G.plen(S["neck_ext"])
    nrows.append(("칼라밴드 길이 − 목둘레선(뒤중심~칼라 끝)", G.plen(S["stand_bot"]) - neck_total, -0.3, 0.3))
    # 겉칼라 스프링: 바깥선이 아랫선보다 길어야 어깨 쪽에 납작하게 얹힘
    nrows.append(("겉칼라 스프링 (바깥선 − 아랫선)", G.plen(S["fall_outer"]) - G.plen(S["fall_bot"]), 1.5, 3.0))
    nrows.append(("겉칼라 아랫선 − 칼라밴드 윗선", G.plen(S["fall_bot"]) - G.plen(S["stand_top"]), 0.0, 0.5))
    # 칼라밴드 어깨 노치 = 뒤목 길이
    stand = pieces[[p.key for p in pieces].index("stand")]
    nrows.append(("칼라밴드 어깨 노치 위치 − 뒤목 길이", stand.notches[0][0] - G.plen(bn), -0.3, 0.3))
    # 칼라밴드 윗선 노치 ↔ 겉칼라 노치: 각 선 시작(뒤중심)에서의 비율이 같아야 함
    col = pieces[[p.key for p in pieces].index("collar")]
    st_top, f_bot = S["stand_top"], S["fall_bot"]
    r1 = dist_along(st_top, stand.notches[1])[0] / G.plen(st_top)
    r2 = dist_along(f_bot, col.notches[0])[0] / G.plen(f_bot)
    nrows.append(("칼라밴드 윗선 노치 ↔ 겉칼라 노치 위치 (비율 차 ×100)", (r1 - r2) * 100, -1.0, 1.0))

    # 단추 위치
    Wh, DB = info["Wh"], info["DB"]
    front = pieces[[p.key for p in pieces].index("front")]
    closure = [(x - Wh, y) for x, y, rr in front.dots if rr > 1.0]          # 앞여밈 단추만 (견장 단추 제외)
    rows_ = {}
    for x, y in closure:
        rows_.setdefault(round(y, 3), []).append(x)
    # 행마다 단추 2개, 앞중심 기준 좌우 대칭, 모든 행이 같은 x 위치 → 가장 큰 어긋남(cm)
    worst = 0.0 if len(rows_) == 5 and all(len(v) == 2 for v in rows_.values()) else 99.0
    ref = sorted(next(iter(rows_.values())))
    for v in rows_.values():
        v = sorted(v)
        worst = max(worst, abs(v[0] + v[1]), abs(v[0] - ref[0]), abs(v[1] - ref[1]))
    xs = sorted(x for x, _ in closure)
    edge_gap = DB - max(xs)
    btn_rows = [("단추 5행 × 2열: 행마다 좌우 대칭이고 모든 행이 같은 위치 (어긋남 cm)", worst, 0, 0.01),
                ("바깥 단추 ~ 앞단 거리 (단추 지름 2.3cm 기준 2.5~4cm)", edge_gap, 2.5, 4.0)]

    print(f"## 사이즈 {size} 제도 검토\n")
    print("| 이음점 | 각도 합 | 목표 | 판정 |\n|---|---|---|---|")
    for name, ang, target, tol, ok in rows:
        print(f"| {name} | {ang:.1f}° | {target}±{tol}° | {'통과' if ok else '**확인 필요**'} |")
    print("\n| 맞춤 | 값 | 범위 | 판정 |\n|---|---|---|---|")
    for name, v, lo, hi in nrows + btn_rows:
        print(f"| {name} | {v:+.2f} | {lo}~{hi} | {'통과' if lo <= v <= hi else '**확인 필요**'} |")
    for name, v in notch:
        print(f"- {name} {v:.1f}cm")
    allok = all(r[4] for r in rows) and all(lo <= v <= hi for _, v, lo, hi in nrows + btn_rows)
    print(f"\n결과: {'모두 통과' if allok else '확인 필요 항목 있음'}")
    return allok


if __name__ == "__main__":
    ok = all([main(s) for s in (sys.argv[1:] or ["100"])])
    sys.exit(0 if ok else 1)
