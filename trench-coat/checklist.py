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
import sys

from shapely.geometry import LineString, Point

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
    import re as _re
    src = open(os.path.join(HERE, "generate_trench.py")).read()
    mm = _re.search(r"벨트고리: (\d+) × (\d+)cm", src)
    loop_len = int(mm.group(2)) - 2 * G.SA if mm else 0
    add("G. 부속", "벨트고리 완성 길이 ≥ 벨트 폭(5) + 1 (재단 목록에서 읽음)", loop_len >= 6, f"{loop_len:g}cm")
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
    import pdfplumber
    pdfp = os.path.join(HERE, "pdf", f"trench_men_{size}_A4.pdf")
    with pdfplumber.open(pdfp) as pdf:
        over = []
        for k in (0, 1):
            pg = pdf.pages[k]
            for ch in pg.chars:
                if ch["x0"] < 28 or ch["x1"] > pg.width - 28 or ch["top"] < 28 or ch["bottom"] > pg.height - 28:
                    over.append(f"{k + 1}쪽 '{ch['text']}'")
    add("L. 표지", "안내 1·2쪽 글자가 여백 1cm 안에 들어감", not over, " ".join(over[:5]))
    fonts = subprocess.run(["pdffonts", pdfp], capture_output=True, text=True).stdout.splitlines()[2:]
    used_not_emb = [l.split()[0] for l in fonts if "Nanum" in l and " no " in l]
    add("L. 표지", "한글 글꼴이 PDF에 포함됨", any("Nanum" in l for l in fonts) and not used_not_emb)

    # H. 올 방향 (전 조각에 식서 있음)
    add("H. 올 방향", "모든 조각에 식서 화살표", all(p.grain for p in pieces))

    # I. 노치 짝
    fw = [n for n in P["front"].notches if abs(n[1] - info["y_w"]) < 3]
    bw = [n for n in P["back"].notches if abs(n[1] - info["y_w"]) < 3]
    add("I. 맞춤 표시", "옆선 벨트고리 노치: 앞 = 뒤 = 2", len(fw) == len(bw) == 2, f"{len(fw)}/{len(bw)}")
    add("I. 맞춤 표시", "진동 노치(앞1+뒤2) ↔ 소매 노치(앞1+뒤2+어깨1+겨드랑이1)",
        len(P["front"].notches) - 2 - 1 == 1 and len(P["back"].notches) - 2 == 2 and
        len(P["topsleeve"].notches) + len(P["undersleeve"].notches) - 2 == 5)
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
