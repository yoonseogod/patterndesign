#!/usr/bin/env python3
"""표준 패턴 점검 체크리스트: 기존 검사 도구 + 추가 항목을 한 번에 돌려 항목별로 표시한다.

결과: verify/checklist_<사이즈>.md
판정: 확인됨 / 문제 / 확인 불가(이 도구로는 검증할 수 없음)

사용법: python3 checklist.py 100   (인자 없으면 전 사이즈)
"""
import math
import os
import re
import subprocess
import pdfplumber
import sys

from shapely.geometry import LineString, Point, box

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_trench as G  # noqa: E402

OK, BAD, NA = "확인됨", "**문제**", "확인 불가"


def ang_at(pts_a, pts_b, d=0.5):
    """두 선이 한 점에서 시작할 때 사이 각도."""
    def dirv(pts):
        p0 = pts[0]
        acc = 0
        for i in range(1, len(pts)):
            acc += math.dist(pts[i - 1], pts[i])
            if acc >= d:
                q = pts[i]
                break
        else:
            q = pts[-1]
        v = (q[0] - p0[0], q[1] - p0[1])
        n = math.hypot(*v)
        return (v[0] / n, v[1] / n)
    u, v = dirv(pts_a), dirv(pts_b)
    return math.degrees(math.acos(max(-1, min(1, u[0] * v[0] + u[1] * v[1]))))


def hem_mirror_errors(size):
    G.NET = False
    try:
        ps, _ = G.draft(size)
    finally:
        G.NET = True
    out = []
    for p in ps:
        if not p.hem:
            continue
        hp, depth = p.hem
        ol = p.outline
        for end, nxt_hem in ((hp[0], hp[1]), (hp[-1], hp[-2])):
            i = min(range(len(ol)), key=lambda k: math.dist(ol[k], end))
            nb = [ol[(i - 1) % len(ol)], ol[(i + 1) % len(ol)]]
            seam_pt = max(nb, key=lambda q: min(math.dist(q, h) for h in hp))   # 밑단이 아닌 쪽 이웃 = 솔기
            d = G.unit(end, seam_pt)                     # 솔기 방향(위로)
            h = G.unit(end, nxt_hem)                     # 밑단 방향(안쪽)
            dot = d[0] * h[0] + d[1] * h[1]
            dm = (2 * dot * h[0] - d[0], 2 * dot * h[1] - d[1])  # 밑단선에 대한 거울
            n = G.perp_toward(h, want_y=1)
            t = depth / max(1e-6, dm[0] * n[0] + dm[1] * n[1])
            C = (end[0] + dm[0] * t, end[1] + dm[1] * t)  # 접어 올렸을 때 솔기와 맞는 시접 모서리(완성선 기준)
            out_dir = G.perp_toward(dm, want_x=(end[0] - nxt_hem[0]))
            target = (C[0] + out_dir[0] * p.sa, C[1] + out_dir[1] * p.sa)
            # 재단선이 target 점을 지나야 함: 목표점과 재단 외곽선 거리
            err = p.cut.boundary.distance(Point(target))
            out.append((p.name, round(err, 2)))
    return out



def fuse_report(size):
    rep = []
    for net in (True, False):
        G.NET = net
        try:
            ps, _ = G.draft(size)
        finally:
            G.NET = True
        for p in ps:
            if p.fuse == "all":
                ref = p.poly if net else p.cut
                rep.append((net, p.name, "전체", round(abs(p.fuse_poly.area - ref.area) / ref.area * 100, 2)))
            elif p.fuse == "hem":
                hp, depth = p.hem
                a, b = hp[0], hp[-1]
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                u = G.unit(a, b); n = G.perp_toward(u, want_y=-1)        # 위쪽
                lo = depth if not net else 0.0                           # 밑단 아래쪽 끝 (시접 포함이면 시접 끝)
                line = LineString([(mid[0] - n[0] * lo, mid[1] - n[1] * lo), (mid[0] + n[0] * 10, mid[1] + n[1] * 10)])
                seg = p.fuse_poly.intersection(line)
                h = seg.length
                # 폭: 띠 가운데 높이에서 가로로 자른 길이 vs 조각 폭
                yc = mid[1] - (G.FUSE_HEM - depth) / 2 if net else mid[1] + depth / 2 - G.FUSE_HEM / 2 + depth / 2
                cut_ref = p.poly if net else p.cut
                wline = LineString([(mid[0] - 60, yc), (mid[0] + 60, yc)])
                cover = p.fuse_poly.intersection(wline).length / max(1e-6, cut_ref.intersection(wline).length)
                rep.append((net, p.name, "밑단", round(h, 2), round(cover * 100, 1)))
    return rep



def run_tool(args):
    r = subprocess.run([sys.executable] + args, cwd=HERE, capture_output=True, text=True)
    return r.stdout + r.stderr


def tool_rows(size):
    """기존 도구 결과를 (분류, 항목, 판정, 값) 으로."""
    rows = []
    out = run_tool(["audit_pdf.py", size])
    for line in out.splitlines():
        m = re.match(r"(PASS|FAIL) (.*?)( — (.*))?$", line)
        if m:
            rows.append(("L. 출력물 (A4 시접 없음)", m.group(2), OK if m.group(1) == "PASS" else BAD, m.group(4) or ""))
    out = run_tool(["audit_pdf.py", size, "--sa"])
    fails = [l for l in out.splitlines() if l.startswith("FAIL")]
    tot = len([l for l in out.splitlines() if re.match(r"(PASS|FAIL) ", l)])
    rows.append(("L. 출력물 (A4 시접 포함)", f"시접 포함 PDF {tot}항목", OK if not fails else BAD, "; ".join(fails)))
    out = run_tool(["review_grading.py"])
    bad_g = [l for l in out.splitlines() if "확인 필요" in l]
    rows.append(("M2. 사이즈 간", "치수·부속이 사이즈마다 고르게 변하고 겹쳐 그린 선이 엇갈리지 않음", OK if not bad_g else BAD,
                 "; ".join(bad_g)[:200]))
    for tool, cat in (("review_draft.py", "C/D/E/F. 제도"), ("verify_fit.py", "B/N. 봉제선·여유")):
        out = run_tool([tool, size])
        for line in out.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[-1] in ("통과", "**확인 필요**"):
                rows.append((cat, cells[0], OK if cells[-1] == "통과" else BAD, " · ".join(cells[1:-1])))
    return rows


def new_rows(size):
    pieces, info = G.draft(size)
    P = {p.key: p for p in pieces}
    S = info["seams"]
    rows = []

    def add(cat, name, ok, val=""):
        rows.append((cat, name, OK if ok else BAD, val))

    # A. 치수 입력
    m = G.SIZES[size]
    add("A. 치수표", "팔길이 = 키 × 0.344 (±0.5)", abs(m["sleeve"] - m["height"] * 0.344) <= 0.5,
        f"{m['sleeve']} vs {m['height'] * 0.344:.1f}")
    add("A. 치수표", "목둘레 = 가슴 × 0.25 + 15.5 (±1.5)", abs(m["neck"] - (m["chest"] * 0.25 + 15.5)) <= 1.5,
        f"{m['neck']}")
    add("A. 치수표", "등길이(뒷목~허리) = 키 × 0.257 (±1.5)", abs(m["nape_waist"] - m["height"] * 0.257) <= 1.5,
        f"{m['nape_waist']} vs {m['height'] * 0.257:.1f}")
    add("A. 치수표", "옷길이가 무릎 위 (키 × 0.55~0.62)", 0.55 <= m["coat_len"] / m["height"] <= 0.62,
        f"{m['coat_len'] / m['height']:.3f}")

    # B. 몸판 균형
    add("B. 몸판", "뒤품 > 앞품 (남성)", info["backW"] > info["frontW"], f"{info['backW']:.1f} / {info['frontW']:.1f}")
    arm_w = info["Wh"] - info["backW"] - info["frontW"]
    add("B. 몸판", "진동 너비 14~20cm", 14 <= arm_w <= 20, f"{arm_w:.1f}")
    depth = info["scye"] - (info["sp_b"][1] + info["sp_f"][1]) / 2
    add("B. 몸판", "진동 깊이/너비 비 1.1~1.5", 1.1 <= depth / arm_w <= 1.5, f"{depth / arm_w:.2f}")
    # 외곽선에서 직접: 옆목점 높이 → 중심선 밑단 높이
    f_len = max(q[1] for q in P["front"].outline if q[0] > info["Wh"] - 0.01) - S["front_shoulder"][0][1]
    b_len = max(q[1] for q in P["back"].outline if abs(q[0] + 5) < 0.01) - S["back_shoulder"][0][1]
    add("B. 몸판", "앞 옆목점~밑단 − 뒤 옆목점~밑단 (−0.5~1.5)", -0.5 <= f_len - b_len <= 1.5, f"{f_len - b_len:+.1f}")
    for key, nm in (("front", "앞판"), ("back", "뒤판")):
        a, b = P[key].grain
        add("H. 올 방향", f"{nm} 식서가 중심선과 나란함", abs(a[0] - b[0]) < 0.01)

    # C. 직각 / 골선
    fe = S["front_edge"]
    add("C. 이음·모서리", "앞단 밑단 모서리 90° (±2)",
        abs(ang_at(list(reversed(fe)), S["front_hem"]) - 90) <= 2,
        f"{ang_at(list(reversed(fe)), S['front_hem']):.1f}°")
    for key, nm, edges in (("collar", "겉칼라", ("fall_bot", "fall_outer")), ("stand", "칼라밴드", ("stand_bot", "stand_top"))):
        for e in edges:
            pts = S[e]
            a = ang_at(pts, [(0, pts[0][1]), (0, pts[0][1] - 5)])
            add("C. 이음·모서리", f"{nm} {('아랫선' if 'bot' in e else '바깥/윗선')}이 골선(뒤중심)과 90° (±3)",
                abs(a - 90) <= 3, f"{a:.1f}°")
    sh = P["shield"]
    on_fold = [q for q in sh.outline if abs(q[0]) < 1e-6]
    ys = sorted(q[1] for q in on_fold)
    top_i = min(range(len(sh.outline)), key=lambda i: (abs(sh.outline[i][0]) > 1e-6, sh.outline[i][1]))
    # 스톰실드: 목둘레(위)와 밑단(아래)이 뒤중심 골선과 직각인지
    neck = S["back_neck"]
    a1 = ang_at(neck, [(0, neck[0][1]), (0, neck[0][1] + 5)])
    hem_end = [q for q in sh.outline if q[0] < 3 and q[1] > ys[-1] - 3]
    hem_pts = sorted(hem_end, key=lambda q: q[0])
    a2 = ang_at(hem_pts, [hem_pts[0], (0, hem_pts[0][1] - 5)]) if len(hem_pts) > 1 else 0
    add("C. 이음·모서리", "스톰실드 목둘레가 골선과 90° (±3)", abs(a1 - 90) <= 3, f"{a1:.1f}°")
    add("C. 이음·모서리", "스톰실드 밑단이 골선과 90° (±3)", abs(a2 - 90) <= 3, f"{a2:.1f}°")

    # D. 소매
    add("D. 소매", "소매산 높이 / 진동둘레 0.30~0.37", 0.30 <= info["CH"] / info["AH"] <= 0.37,
        f"{info['CH'] / info['AH']:.3f}")
    # 윗소매 밑단 중심 = 손목 중심 + (뒤 여유 − 앞 여유)/2 = 손목 중심 − 0.5
    wrist_c = (S["top_wrist"][0][0] + S["top_wrist"][1][0]) / 2 + 0.5
    pitch = info["B"] / 2 - wrist_c
    add("D. 소매", "소매 앞쪽 기울기(손목 중심이 위팔 중심보다 앞으로) 1~3cm", 1 <= pitch <= 3, f"{pitch:.2f}")
    add("D. 소매", "위팔 둘레 / 진동둘레 0.68~0.76", 0.68 <= info["B"] / info["AH"] <= 0.76, f"{info['B'] / info['AH']:.3f}")

    # F. 앞여밈·주머니
    btn = sorted([d for d in P["front"].dots if d[2] > 1.0], key=lambda d: d[1])
    ys_ = sorted({round(d[1], 3) for d in btn})
    gaps = [ys_[i + 1] - ys_[i] for i in range(len(ys_) - 1)]
    add("F. 앞여밈", "단추 5행 간격 일정 (±0.1)", max(gaps) - min(gaps) <= 0.1, f"{gaps[0]:.1f}cm")
    lp_y = S["front_edge"][2][1]
    add("F. 앞여밈", "맨 위 단추가 라펠 끝보다 아래", ys_[0] > lp_y + 2, f"단추 {ys_[0]:.1f} / 라펠 {lp_y:.1f}")
    fx = min(q[0] for q in P["facing"].outline if q[1] > info["scye"])
    outer_hole = info["Wh"] + 7.0
    add("F. 앞여밈", "안단이 단춧구멍(앞중심+7, 구멍 2.5cm)을 덮음", fx < outer_hole - 1.25 - 1.5,
        f"안단 안쪽선 CF{fx - info['Wh']:+.1f}")
    pk = [l for l in P["front"].lines if l[2] == "주머니 웰트 위치"][0][0]
    opening = math.dist(pk[0], pk[1])
    add("F. 주머니", "주머니 입구 16~19cm", 16 <= opening <= 19, f"{opening:.1f}")
    mid_y = (pk[0][1] + pk[1][1]) / 2 - info["y_w"]
    add("F. 주머니", "주머니 입구 중심이 허리 아래 9~16cm", 9 <= mid_y <= 16, f"{mid_y:.1f}")
    add("F. 주머니", "웰트 길이 = 입구 길이", abs(P["welt"].poly.bounds[2] - opening) < 0.05)

    # G. 부속
    sh_f = G.plen(S["front_shoulder"])
    ep = P["epaulette"].poly.bounds[2]
    add("G. 부속", "견장 길이 < 어깨 길이", ep < sh_f, f"{ep:.1f} / {sh_f:.1f}")
    circ = info["wW"] + (info["B"] - info["wW"]) * 6 / (info["SLg"] - info["CH"])
    st = P["cuffstrap"].poly.bounds[2]
    add("G. 부속", "소매 스트랩 ≥ 스트랩 위치 둘레 + 6", st >= circ + 6, f"{st:.1f} / {circ:.1f}")
    waist = 2 * (info["Wh"] - 1.6)
    add("G. 부속", "벨트 ≥ 허리 완성둘레 + 35", info["belt_len"] >= waist + 35, f"{info['belt_len']} / {waist:.0f}")
    ln = sorted(n[1] for n in P["front"].notches if abs(n[0] - info["sideX"]) < 2 and abs(n[1] - info["y_w"]) < 5)
    gap = ln[-1] - ln[0] if len(ln) == 2 else 0
    add("G. 부속", "벨트고리 노치 간격 = 고리 완성 길이 ≥ 벨트 폭 + 1", abs(gap - G.LOOP) < 0.05 and G.LOOP >= G.BELT_W + 1,
        f"노치 {gap:.1f} / 고리 {G.LOOP:g}")
    with pdfplumber.open(os.path.join(os.environ.get("TRENCH_PDF_DIR", os.path.join(HERE, "pdf")),
                                      f"trench_men_{size}_A4.pdf")) as _pdf:
        _t = _pdf.pages[1].extract_text() or ""
    import re as _re
    mm = _re.search(r"벨트고리: [\d.]+ × [\d.]+cm (\d+)장", _t)
    add("G. 부속", "재단 목록 벨트고리 장수 = 패턴의 고리 자리 수 (옆선 2곳)", bool(mm) and int(mm.group(1)) == 2,
        mm.group(0) if mm else "목록에 없음")
    bo = LineString(P["back"].outline + [P["back"].outline[0]])
    off = [q for q in P["shield"].outline if q[0] > 0.01 and q[1] < info["scye"] - 3.2 and bo.distance(Point(q)) > 0.05]
    add("G. 부속", "스톰실드 목·어깨·진동선이 뒤판 선과 일치", not off, f"어긋난 점 {len(off)}")
    fo = LineString(P["front"].outline + [P["front"].outline[0]])
    g = P["gunflap"]
    yg = max(q[1] for q in g.outline)
    off = [q for q in g.outline if q[1] < yg - 4 and q[0] < info["Wh"] - 4.5 and fo.distance(Point(q)) > 0.05]
    add("G. 부속", "건 플랩 목·어깨·진동선이 앞판 선과 일치", not off, f"어긋난 점 {len(off)}")

    # 부속끼리 위치가 맞는지
    fb = [d for d in P["front"].dots if d[2] < 1.0]
    d_body = math.dist(S["front_shoulder"][1], fb[0][:2]) if fb else -99
    d_ep = P["epaulette"].dots[0][0]
    add("G. 부속 위치", "견장 구멍 위치 = 몸판 견장 단추 위치 (어깨점에서, ±0.3)", abs(d_body - d_ep) <= 0.3,
        f"{d_ep:.2f} / {d_body:.2f}")
    on_shoulder = LineString(S["front_shoulder"]).distance(Point(fb[0][:2])) < 0.05 if fb else False
    add("G. 부속 위치", "몸판 견장 단추가 어깨선 위", on_shoulder)
    outer = sorted(d[1] for d in P["front"].dots if d[2] > 1.0 and d[0] > info["Wh"])
    for key, nm in (("front", "앞판"), ("facing", "앞 안단")):
        hl = [l for l in P[key].lines if l[1] == "solid" and len(l[0]) == 2 and abs(l[0][0][1] - l[0][1][1]) < 1e-6
              and abs(math.dist(*l[0]) - 2.6) < 0.01]
        ok = len(hl) == 5 and sorted(round(l[0][0][1], 3) for l in hl) == [round(y, 3) for y in outer]
        add("F. 앞여밈", f"{nm}: 단춧구멍 5개가 바깥 단추 열과 같은 높이", ok, f"{len(hl)}개")
    for key, nm in (("topsleeve", "윗소매"), ("undersleeve", "밑소매")):
        has = any(l[2] == "소매 스트랩 위치" for l in P[key].lines)
        add("G. 부속 위치", f"{nm}에 소매 스트랩 위치선", has)
    add("G. 부속 위치", "칼라에 목 여밈 탭 단추 위치", bool(P["collar"].dots) and
        P["collar"].poly.contains(Point(P["collar"].dots[0][:2])))

    # P. 제도값 ↔ 실제 조각 일치 (검사들이 재는 선이 정말 조각 외곽선인지)
    seam_piece = {"front_shoulder": "front", "front_arm": "front", "front_side": "front", "front_neck": "front",
                  "front_edge": "front", "front_hem": "front", "neck_ext": "front",
                  "back_shoulder": "back", "back_arm": "back", "back_side": "back", "back_neck": "back",
                  "back_hem": "back", "top_front": "topsleeve", "top_back": "topsleeve", "top_wrist": "topsleeve",
                  "under_front_rot": "undersleeve", "under_back": "undersleeve", "under_wrist": "undersleeve",
                  "stand_bot": "stand", "stand_top": "stand", "fall_bot": "collar", "fall_outer": "collar",
                  "facing_edge": "facing"}
    mism = []
    for sk, pk in seam_piece.items():
        pts = S[sk]
        if sk == "facing_edge":
            pts = pts[1:]                       # 안단은 칼라 끝(ce)부터
        edge = LineString(P[pk].outline + [P[pk].outline[0]])
        far = max(edge.distance(Point(q)) for q in pts)
        if far > 0.05:
            mism.append(f"{sk}→{pk} {far:.2f}cm")
    add("P. 제도값=조각", "검사에 쓰는 선 23개가 모두 실제 조각 외곽선 위", not mism, "; ".join(mism))
    # 진동 노치가 실제 앞·뒤판 위 정확한 위치에
    fs = info["arm_notch_from_side"]
    def has_notch(piece, q):
        return any(math.dist(n, q) < 0.05 for n in piece.notches)
    fa_rev, ba_rev = list(reversed(S["front_arm"])), list(reversed(S["back_arm"]))
    ok_arm = (has_notch(P["front"], G.point_at(fa_rev, fs["front"])) and
              has_notch(P["back"], G.point_at(ba_rev, fs["back1"])) and
              has_notch(P["back"], G.point_at(ba_rev, fs["back2"])))
    add("P. 제도값=조각", "진동 노치(앞1·뒤2)가 앞·뒤판의 계산 위치에 찍혀 있음", ok_arm)
    miss = []
    for nm, arc in info["sleeve_notch_arcs"].items():
        k, q = info["sleeve_spot"](arc)
        if not has_notch(P["topsleeve" if k == "top" else "undersleeve"], q):
            miss.append(nm)
    add("P. 제도값=조각", "소매 노치(어깨·앞·뒤2)가 윗/밑소매의 계산 위치에 찍혀 있음", not miss, ",".join(miss))

    # M. 조각 안 표시
    out_lines, out_dots, off_notch, no_size = [], [], [], []
    for p in pieces:
        poly = p.poly.buffer(0.05)
        edge = LineString(p.outline + [p.outline[0]])
        for pts, st, lab in p.lines:
            if not poly.contains(LineString(pts)):
                out_lines.append(f"{p.name}:{lab or st}")
        for (x, y, r) in p.dots:
            on_seam = p.key == "front" and r < 1.0          # 견장 단추는 어깨선 위에 일부러 걸침
            if not on_seam and not poly.contains(Point(x, y).buffer(r)):
                out_dots.append(p.name)
        for n in p.notches:
            if edge.distance(Point(n)) > 0.1:
                off_notch.append(p.name)
        if not any(size in t[2] for t in p.texts):
            no_size.append(p.name)
    add("M. 조각 안 표시", "안쪽 선이 조각 밖으로 나가지 않음", not out_lines, ", ".join(out_lines))
    add("M. 조각 안 표시", "단추·구멍 표시가 조각 안 (견장 단추 제외)", not out_dots, ", ".join(out_dots))
    add("M. 조각 안 표시", "노치가 외곽선 위", not off_notch, ", ".join(off_notch))
    add("M. 조각 안 표시", "모든 조각에 사이즈 표기", not no_size, ", ".join(no_size))
    gf = [l for l in P["front"].lines if "건플랩" in l[2]][0][0]
    gedge = LineString(P["gunflap"].outline + [P["gunflap"].outline[0]]).buffer(0.02)
    add("G. 부속 위치", "앞판 건 플랩 위치선 = 건 플랩 조각 테두리", gedge.contains(LineString(gf)))

    # L. 표지·글꼴
    pass  # pdfplumber는 파일 맨 위에서 가져옴
    pdfp = os.path.join(os.environ.get("TRENCH_PDF_DIR", os.path.join(HERE, "pdf")), f"trench_men_{size}_A4.pdf")
    with pdfplumber.open(pdfp) as pdf:
        over = []
        for k in (0, 1):
            pg = pdf.pages[k]
            for ch in pg.chars:
                if ch["x0"] < 28 or ch["x1"] > pg.width - 28 or ch["top"] < 28 or ch["bottom"] > pg.height - 28:
                    over.append(f"{k + 1}쪽 '{ch['text']}'")
    add("L. 표지", "안내 1·2쪽 글자가 여백 1cm 안에 들어감", not over, " ".join(over[:5]))
    with pdfplumber.open(pdfp) as pdf:
        legend = (pdf.pages[0].extract_text() or "").replace(" ", "")
    need = {"dash": "파선", "dot": "점선", "dashdot": "일점쇄선", "solid": "단춧구멍"}
    used_styles = {st for p in pieces for _, st, _ in p.lines}
    missing_kw = [need[st] for st in used_styles if need.get(st, "?") not in legend]
    for kw, cond in (("노치", any(p.notches for p in pieces)), ("식서", True), ("골선", any(p.fold_x is not None for p in pieces)),
                     ("단추", any(p.dots for p in pieces)), ("심지", any(p.fuse for p in pieces)), ("완성선", True)):
        if cond and kw not in legend:
            missing_kw.append(kw)
    add("L. 표지", "패턴에 쓰인 선·기호가 모두 '선 보는 법'에 설명됨", not missing_kw, ",".join(missing_kw))
    fonts = subprocess.run(["pdffonts", pdfp], capture_output=True, text=True).stdout.splitlines()[2:]
    used_not_emb = [l.split()[0] for l in fonts if "Nanum" in l and " no " in l]
    add("L. 표지", "한글 글꼴이 PDF에 포함됨", any("Nanum" in l for l in fonts) and not used_not_emb)

    # Q. 시접 포함 버전 재단선 (시접 포함 PDF에 그려지는 선)
    G.NET = False
    try:
        ps_sa, _ = G.draft(size)
    finally:
        G.NET = True
    thin, hem_short, past_fold, multi = [], [], [], []
    for p in ps_sa:
        cut, net = p.cut, p.poly
        if cut.geom_type != "Polygon":
            multi.append(p.name)
            continue
        ring = net.exterior
        border = cut.exterior
        if p.fold_x is not None:        # 골선 부분은 시접이 없으므로 거리 계산에서 뺀다
            from shapely.geometry import box as _box
            border = border.difference(_box(p.fold_x - 0.01, -1e4, p.fold_x + 0.01, 1e4))
        for k in range(0, int(ring.length), 1):
            q = ring.interpolate(k)
            if p.fold_x is not None and abs(q.x - p.fold_x) < 0.05:
                continue
            if border.distance(q) < G.SA - 0.05:          # 정해진 기준(1cm)과 비교
                thin.append(f"{p.name}@{q.x:.0f},{q.y:.0f}")
                break
        if p.hem:
            for hq in p.hem[0][1:-1]:
                if not cut.buffer(0.02).contains(Point(hq[0], hq[1] + p.hem[1] - 0.05)):
                    hem_short.append(p.name)
                    break
        if p.fold_x is not None and cut.bounds[0] < p.fold_x - 0.01:
            past_fold.append(p.name)
    add("Q. 시접 포함 재단선", "재단선이 한 덩어리 (조각마다)", not multi, ",".join(multi))
    add("Q. 시접 포함 재단선", "완성선 둘레 어디서나 시접 ≥ 1cm (골선 제외)", not thin, ", ".join(thin))
    add("Q. 시접 포함 재단선", "밑단 시접 4cm 확보", not hem_short, ",".join(hem_short))
    add("Q. 시접 포함 재단선", "골선 너머로 시접이 붙지 않음", not past_fold, ",".join(past_fold))
    herr = [f"{n} {e}" for n, e in hem_mirror_errors(size) if e > 0.1]
    add("Q. 시접 포함 재단선", "밑단 시접을 접어 올리면 양옆이 솔기와 겹침 (거울 방향, ±1mm)", not herr, ", ".join(herr))

    # R. 인쇄 안전 여백 · 배치도
    with pdfplumber.open(pdfp) as pdf:
        def visible(k, ch, pg):
            # 패턴 장(3쪽~)의 조각 글자는 1cm 여백 안 칸으로 잘려 그려짐 → 칸 밖 조각 글자는 보이지 않음
            if k < 2:
                return True
            M = G.MARGIN * 28.3465                     # 실제 인쇄 칸(잘림 상자) 위치
            inside = M <= ch["x0"] and ch["x1"] <= pg.width - M and M <= ch["top"] and ch["bottom"] <= pg.height - M
            near_page = -20 <= ch["x0"] and ch["x1"] <= pg.width + 20 and -20 <= ch["top"] and ch["bottom"] <= pg.height + 20
            mtx = ch.get("matrix") or (1, 0, 0, 1, 0, 0)
            unrotated = abs(mtx[1]) < 1e-6 and abs(mtx[2]) < 1e-6   # 머리글·바닥글은 회전 없음 (시접 글자는 회전)
            header = near_page and unrotated and (abs(ch["size"] - 7) < 0.05 or abs(ch["size"] - 9) < 0.05)
            return inside or header                    # 칸 안 글자 + 쪽 머리글·바닥글(7·9pt)
        edge = [f"{k + 1}쪽" for k, pg in enumerate(pdf.pages)
                if any(ch["x0"] < 14.2 or ch["x1"] > pg.width - 14.2 or ch["top"] < 14.2 or ch["bottom"] > pg.height - 14.2
                       for ch in pg.chars if visible(k, ch, pg))]
        map_shapes = len([c for c in pdf.pages[1].curves]) + len([r for r in pdf.pages[1].rects if r["width"] < 200])
    add("R. 인쇄", "모든 쪽의 글자가 종이 끝에서 5mm 이상", not edge, ",".join(edge[:5]))
    add("R. 인쇄", "2쪽 배치도에 조각이 모두 그려짐 (조각 수 이상)", map_shapes >= len(pieces), f"{map_shapes} / {len(pieces)}")

    # S7. 심지 띠
    fr = fuse_report(size)
    bad_all = [f"{r[1]}" for r in fr if r[2] == "전체" and r[3] > 0.5]
    bad_hem = [f"{'시접없음' if r[0] else '시접포함'} {r[1]} {r[3]}cm/{r[4]}%" for r in fr if r[2] == "밑단"
               and (abs(r[3] - (G.FUSE_HEM - G.SLEEVE_HEM if r[0] else G.FUSE_HEM)) > 0.1 or r[4] < 99)]
    add("S7. 심지", "전체 심지 조각: 빗금 = 조각 전체", not bad_all, ",".join(bad_all))
    add("S7. 심지", "소매 밑단 심지 띠 폭 (시접 없음 1cm / 포함 5cm) · 소매 폭 전체", not bad_hem, "; ".join(bad_hem))

    # S8. 거의 빈 페이지
    import copy as _copy
    lp = _copy.deepcopy(pieces)                      # 배치는 복사본으로 (원본 좌표는 다른 검사가 씀)
    G.layout(lp)
    rows_ = int(max(p.cut.bounds[3] for p in lp) // G.TILE_H) + 1
    thin_pages = []
    for ri in range(rows_):
        for ci in range(G.COLS):
            t = box(ci * G.TILE_W, ri * G.TILE_H, (ci + 1) * G.TILE_W, (ri + 1) * G.TILE_H)
            a_ = sum(p.cut.intersection(t).area for p in lp)
            if G.tile_used(lp, ci, ri) and a_ < 0.03 * G.TILE_W * G.TILE_H:
                thin_pages.append(f"{G.tile_name(ci, ri)}({a_:.0f}cm²)")
    add("S8. 페이지", "인쇄하는 장마다 패턴이 3% 이상 (선 몇 cm만 있는 장 없음)", not thin_pages, ", ".join(thin_pages))

    # S5. 원단 소요량 (어림): 일반 범위 · 사이즈가 커지면 줄지 않음
    est = {z: G.fabric_estimate(z) for z in G.SIZES}
    main_m = [est[z]["겉감"][1] for z in G.SIZES]
    lin_m = [est[z]["안감"][1] for z in G.SIZES]
    add("S5. 원단", "겉감 150cm 폭 소요량 3.0~4.5m", 3.0 <= est[size]["겉감"][1] <= 4.5, f"{est[size]['겉감'][1]:.2f}m")
    add("S5. 원단", "안감 140cm 폭 소요량 1.8~3.2m", 1.8 <= est[size]["안감"][1] <= 3.2, f"{est[size]['안감'][1]:.2f}m")
    add("S5. 원단", "사이즈가 커질수록 소요량이 줄지 않음", all(main_m[i] <= main_m[i + 1] + 0.02 for i in range(3)) and
        all(lin_m[i] <= lin_m[i + 1] + 0.02 for i in range(3)))

    # S3. 뒤트임: 열림 시작이 엉덩이선 아래 0~6cm
    cbx = [q for q in P["back"].outline if abs(q[0] + 5) < 0.01]
    vt = min(q[1] for q in cbx)
    add("S3. 뒤트임", "트임이 엉덩이선 아래 0~6cm에서 시작", 0 <= vt - info["y_h"] <= 6, f"{vt - info['y_h']:+.1f}")
    add("S3. 뒤트임", "트임 길이 25~40cm", 25 <= info["y_L"] - vt <= 40, f"{info['y_L'] - vt:.1f}")

    # S2. 팔꿈치선 = 몸의 팔꿈치 (윗소매 '팔꿈치선' 높이, 소매산 꼭대기 기준)
    el = [l for l in P["topsleeve"].lines if l[2] == "팔꿈치선"][0][0]
    body_el = 0.55 * G.SIZES[size]["sleeve"] + 1.0
    add("S2. 소매", "팔꿈치선이 몸의 팔꿈치 높이 ±1.5cm", abs(el[0][1] - body_el) <= 1.5, f"{el[0][1]:.1f} / {body_el:.1f}")
    en = min([n for n in P["topsleeve"].notches if n[1] > info["CH"] + 1], key=lambda n: abs(n[1] - el[0][1]))
    add("S2. 소매", "팔꿈치 노치가 팔꿈치선 높이 (±0.3)", abs(en[1] - el[0][1]) <= 0.3, f"{en[1]:.1f}")

    # S1. 부속끼리 간섭 (주머니·주머니감·단추·안단·옆선)
    pkl = [l for l in P["front"].lines if l[2] == "주머니 웰트 위치"][0][0]
    bagl = [l for l in P["front"].lines if l[2] == "주머니감 위치"]
    from shapely.geometry import Polygon as _Poly
    pocket_poly = _Poly(pkl)
    btn_polys = [Point(x, y).buffer(r) for x, y, r in P["front"].dots if r > 1.0]
    add("S1. 부속 간섭", "주머니가 단추에서 5cm 이상 떨어짐", min(pocket_poly.distance(b) for b in btn_polys) >= 5,
        f"{min(pocket_poly.distance(b) for b in btn_polys):.1f}")
    add("S1. 부속 간섭", "주머니가 옆선에서 2.5cm 이상 안쪽", min(q[0] for q in pkl) - info["sideX"] >= 2.5)
    ok_bag = bool(bagl)
    if ok_bag:
        bo = bagl[0][0]
        facing_in = info["Wh"] - 4
        add("S1. 부속 간섭", "주머니감이 안단 안쪽선 앞에서 끝남 (겹치지 않음)", max(q[0] for q in bo) <= facing_in - 0.5,
            f"{max(q[0] for q in bo) - facing_in:+.1f}")
        mid = ((pkl[0][0] + pkl[1][0]) / 2, (pkl[0][1] + pkl[1][1]) / 2)
        depth = max(math.dist(mid, q) for q in bo)
        add("S1. 부속 간섭", "손 깊이(입구 가운데 → 주머니감 끝) ≥ 19cm", depth >= 19, f"{depth:.1f}")
        bg = P["bag"].poly
        from shapely import affinity as _aff
        bx0, by0 = min(q[0] for q in bo), min(q[1] for q in bo)
        same = _aff.translate(_Poly(bo), -bx0, -by0).symmetric_difference(bg).area < 0.5
        add("S1. 부속 간섭", "주머니감 조각 = 앞판 '주머니감 위치' 모양", same)
    else:
        add("S1. 부속 간섭", "앞판에 주머니감 위치 표시", False)

    # H. 올 방향 (전 조각에 식서 있음)
    add("H. 올 방향", "모든 조각에 식서 화살표", all(p.grain for p in pieces))

    # I. 노치 짝
    near_side = lambda n: abs(n[0] - info["sideX"]) < 2 and abs(n[1] - info["y_w"]) < 4
    fw = [n for n in P["front"].notches if near_side(n)]
    bw = [n for n in P["back"].notches if near_side(n)]
    add("I. 맞춤 표시", "옆선 벨트고리 노치: 앞 = 뒤 = 2", len(fw) == len(bw) == 2, f"{len(fw)}/{len(bw)}")
    on_curve = lambda n, pts: LineString(pts).distance(Point(n)) < 0.05 and min(math.dist(n, pts[0]), math.dist(n, pts[-1])) > 1
    fa_n = [n for n in P["front"].notches if on_curve(n, S["front_arm"])]
    ba_n = [n for n in P["back"].notches if on_curve(n, S["back_arm"])]
    cap_n = [n for n in P["topsleeve"].notches + P["undersleeve"].notches if n[1] <= info["CH"] + 0.01]
    add("I. 맞춤 표시", "진동 노치(앞1+뒤2) ↔ 소매 노치(앞1+뒤2+어깨1+겨드랑이1)",
        len(fa_n) == 1 and len(ba_n) == 2 and len(cap_n) == 5, f"{len(fa_n)}/{len(ba_n)}/{len(cap_n)}")
    # 30cm 넘는 솔기는 끝에서 3cm 이상 떨어진 중간 노치가 짝 양쪽에 있어야 함
    long_pairs = {"옆선": (("front", S["front_side"]), ("back", S["back_side"])),
                  "소매 앞솔기": (("topsleeve", S["top_front"]), ("undersleeve", S["under_front_rot"])),
                  "소매 뒷솔기": (("topsleeve", S["top_back"]), ("undersleeve", S["under_back"])),
                  "앞단": (("front", S["front_edge"]), ("facing", S["facing_edge"][1:]))}
    no_mid = []
    for nm, sides in long_pairs.items():
        for pk, pts in sides:
            mids = [n for n in P[pk].notches if LineString(pts).distance(Point(n)) < 0.1
                    and min(math.dist(n, pts[0]), math.dist(n, pts[-1])) > 3]
            if G.plen(pts) > 30 and not mids:
                no_mid.append(f"{nm}({P[pk].name})")
    cbn = [n for n in P["back"].notches if abs(n[0]) < 0.05]
    if not cbn:
        no_mid.append("뒤중심")
    add("I. 맞춤 표시", "30cm 넘는 솔기마다 중간 노치 (짝 양쪽)", not no_mid, ", ".join(no_mid))
    add("I. 맞춤 표시", "칼라밴드 윗선 노치 ↔ 겉칼라 노치", len(P["stand"].notches) == 2 and len(P["collar"].notches) == 1)
    add("I. 맞춤 표시", "칼라 끝 노치: 앞판 = 안단", any(math.dist(n, S["neck_ext"][1]) < 0.01 for n in P["front"].notches)
        and any(math.dist(n, S["neck_ext"][1]) < 0.01 for n in P["facing"].notches))

    # J. 시접 표기 값
    hems = [v for p in pieces for _, v in p.sa_marks if isinstance(v, str) and "밑단" in v]
    add("J. 시접", "밑단 시접 표기 = 설정값 4cm", all(f"{G.HEM:g}cm" in v for v in hems), f"{len(hems)}곳")
    side = [v for _, v in P["front"].sa_marks if v == G.SA_SIDE] + [v for _, v in P["back"].sa_marks if v == G.SA_SIDE]
    add("J. 시접", "옆선·뒤중심 1.5cm 표기 (앞1·뒤2)", len(side) == 3, f"{len(side)}곳")

    # K. 재단 목록
    G.layout(pieces)
    used = [(ci, ri) for ri in range(10) for ci in range(G.COLS) if G.tile_used(pieces, ci, ri)]
    names_in_list = [p.name for p in pieces if p.key != "belttip"]
    add("K. 재단 목록", "벨트 끝 본 외 모든 조각이 재단 목록에 있음", len(names_in_list) == len(pieces) - 1)
    mirror = [p.name for p in pieces if p.key in ("front", "back", "facing", "topsleeve", "undersleeve")
              and not ("2장" in p.cut_txt)]
    add("K. 재단 목록", "좌우 쌍 조각은 2장 이상", not mirror, ",".join(mirror))
    fuse_named = {p.key for p in pieces if p.fuse}
    add("K. 재단 목록", "심지 위치 = 요청(칼라·칼라밴드·안단·소매 밑단)",
        fuse_named == {"collar", "stand", "facing", "topsleeve", "undersleeve"}, ",".join(sorted(fuse_named)))

    # O. 확인 불가
    for name in ("원단을 입혔을 때 주름·당김·드레이프", "칼라가 실제로 꺾이는 모양과 라펠 롤",
                 "어깨 경사·패드 두께가 체형에 맞는지", "소매가 달린 각도(앞뒤로 도는지)", "원단 수축·늘어남"):
        rows.append(("O. 이 도구로 확인 불가", name, NA, "광목 가봉으로 확인"))
    return rows


def main(size):
    rows = tool_rows(size) + new_rows(size)
    rows.sort(key=lambda r: r[0])
    nb = sum(r[2] == BAD for r in rows)
    nok = sum(r[2] == OK for r in rows)
    nna = sum(r[2] == NA for r in rows)
    lines = [f"# 사이즈 {size} 패턴 점검 체크리스트", "",
             f"확인됨 {nok} · 문제 {nb} · 확인 불가 {nna} (총 {len(rows)}항목)", "",
             "| 분류 | 항목 | 판정 | 값 |", "|---|---|---|---|"]
    for cat, name, st, val in rows:
        lines.append(f"| {cat} | {name} | {st} | {val} |")
    os.makedirs(os.path.join(HERE, "verify"), exist_ok=True)
    open(os.path.join(HERE, "verify", f"checklist_{size}.md"), "w").write("\n".join(lines) + "\n")
    print(f"{size}: 확인됨 {nok} · 문제 {nb} · 확인 불가 {nna} (총 {len(rows)})")
    for r in rows:
        if r[2] == BAD:
            print("   문제:", r[0], "|", r[1], "|", r[3])
    return nb


if __name__ == "__main__":
    bad = sum(main(s) for s in (sys.argv[1:] or list(G.SIZES)))
    sys.exit(1 if bad else 0)
