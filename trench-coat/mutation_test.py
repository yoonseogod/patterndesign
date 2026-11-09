#!/usr/bin/env python3
"""검사 도구 시험: 패턴에 결함을 하나씩 일부러 심고, 검사가 잡아내는지 확인한다.

모든 결함이 잡혀야 '통과'. 하나라도 놓치면 그 검사는 그 문제를 실제로 보고 있지 않다는 뜻이다.
사용법: python3 mutation_test.py
"""
import contextlib
import copy
import io
import math
import os
import runpy
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_trench as G  # noqa: E402
import checklist as CL  # noqa: E402
import review_draft as RD  # noqa: E402
import verify_fit as VF  # noqa: E402

SIZE = sys.argv[1] if len(sys.argv) > 1 else "100"
ORIG_DRAFT = G.draft
ORIG_TILE = G.tile_page


def P(pieces, key):
    return next(p for p in pieces if p.key == key)


def rebuild(p):
    p.build_cut()


# ── 결함 목록: (이름, 결함 심기, 잡아야 할 검사 이름 일부, PDF 검사 필요 여부)
def m_ep_hole(ps, info):
    e = P(ps, "epaulette"); x, y, r = e.dots[0]; e.dots[0] = (x + 1.5, y, r)

def m_sa_label(ps, info):
    b = P(ps, "back"); b.sa_marks = [m for m in b.sa_marks if m[1] != G.SA_SIDE or m[0][0] < 1]

def m_collar_grain(ps, info):
    c = P(ps, "collar"); (a, b) = c.grain; c.grain = (a, (a[0] + 8, a[1]))

def m_sleeve_notch(ps, info):
    t = P(ps, "topsleeve"); x, y = t.notches[0]; t.notches[0] = (x + 2.0, y)

def m_front_side(ps, info):
    f = P(ps, "front"); sc = info["scye"]
    f.outline = [(x + 1.0, y) if (y > sc + 5 and x < info["sideX"] + 3) else (x, y) for x, y in f.outline]; rebuild(f)

def m_text_overlap(ps, info):
    f = P(ps, "front"); t0 = f.texts[0]; t1 = f.texts[1]; f.texts[1] = (t0[0] + 0.3, t0[1] - 0.2, t1[2], t1[3])

def m_no_fuse(ps, info):
    c = P(ps, "collar"); c.fuse = None; rebuild(c)

def m_welt(ps, info):
    w = P(ps, "welt"); w.outline = [(x * 1.06, y) for x, y in w.outline]; rebuild(w)

def m_button(ps, info):
    f = P(ps, "front"); x, y, r = f.dots[0]; f.dots[0] = (x + 1.0, y, r)

def m_roll_line(ps, info):
    f = P(ps, "front")
    f.lines = [((pts + [(pts[-1][0] - 6, pts[-1][1] - 6)]) if lab == "라펠 꺾임선" else pts, st, lab) for pts, st, lab in f.lines]

def m_notch_off(ps, info):
    s = P(ps, "stand"); x, y = s.notches[0]; s.notches[0] = (x, y - 1.0)

def m_spring(ps, info):
    S = info["seams"]; fb = S["fall_bot"]
    S["fall_outer"] = [(q[0] * 0.93, q[1]) for q in S["fall_outer"]]

def m_cap(ps, info):
    S = info["seams"]; S["cap"] = [(x, y * 0.85 + 0.15 * max(q[1] for q in S["cap"])) for x, y in S["cap"]]

def m_back_side(ps, info):
    S = info["seams"]; S["back_side"] = S["back_side"][:-1] + [(S["back_side"][-1][0], S["back_side"][-1][1] + 1.5)]

def m_shield_hem(ps, info):
    s = P(ps, "shield"); ys = max(q[1] for q in s.outline if abs(q[0]) < 1e-6)
    s.outline = [(x, y + (1.2 if (0 < x < 2.5 and y > ys - 2) else 0)) for x, y in s.outline]; rebuild(s)

def m_no_size(ps, info):
    w = P(ps, "latch"); w.texts = [(x, y, s.replace(SIZE, ""), z) for x, y, s, z in w.texts]

def m_holes(ps, info):
    f = P(ps, "facing"); f.lines = [l for l in f.lines if not (l[1] == "solid" and len(l[0]) == 2)]

def m_strap_line(ps, info):
    u = P(ps, "undersleeve"); u.lines = []

def m_hem_label(ps, info):
    t = P(ps, "topsleeve"); t.sa_marks = [(p, ("밑단 시접 3cm" if isinstance(v, str) else v)) for p, v in t.sa_marks]

def m_gun_line(ps, info):
    f = P(ps, "front")
    f.lines = [([(x, y + 1.5) for x, y in pts] if "건플랩" in lab else pts, st, lab) for pts, st, lab in f.lines]

def m_thin_sa(ps, info):
    b = P(ps, "back"); b.sa = 0.5; rebuild(b)

def m_bag_shape(ps, info):
    b = P(ps, "bag"); b.outline = [(x * 1.1, y) for x, y in b.outline]; rebuild(b)

def m_bag_facing(ps, info):
    f = P(ps, "front")
    f.lines = [([(x + 3, y) for x, y in pts] if lab == "주머니감 위치" else pts, st, lab) for pts, st, lab in f.lines]

def m_elbow(ps, info):
    t = P(ps, "topsleeve")
    t.lines = [([(x, y + 5) for x, y in pts] if lab == "팔꿈치선" else pts, st, lab) for pts, st, lab in t.lines]

def m_vent(ps, info):
    b = P(ps, "back")
    b.outline = [(x, y - 8) if (x < -4.9 and y < info["y_L"] - 1) else (x, y) for x, y in b.outline]; rebuild(b)

def m_fuse_band(ps, info):
    t = P(ps, "topsleeve"); t.fuse_poly = t.fuse_poly.buffer(0.6).intersection(t.cut)

def m_hem_mirror(ps, info):
    from shapely import affinity
    b = P(ps, "back")
    if not G.NET:                       # 시접 포함 버전 재단선만 0.4cm 밀어 밑단 시접 모서리를 어긋나게
        b.cut = affinity.translate(b.cut, 0.4, 0)

MUTATIONS = [
    ("주머니감 조각 모양이 위치선과 다름", m_bag_shape, ["주머니감 조각"], False),
    ("주머니감이 안단까지 들어감", m_bag_facing, ["안단 안쪽선"], False),
    ("팔꿈치선 5cm 아래로", m_elbow, ["팔꿈치선"], False),
    ("뒤트임이 엉덩이선 위로", m_vent, ["트임"], False),
    ("소매 심지 띠가 넓어짐", m_fuse_band, ["심지 띠"], False),
    ("시접 포함 밑단 시접 어긋남", m_hem_mirror, ["접어 올리면"], False),
    ("시접 포함 버전 뒤판 시접 0.5cm", m_thin_sa, ["시접 ≥ 1cm"], False),
    ("견장 구멍을 1.5cm 옮김", m_ep_hole, ["견장 구멍 위치"], False),
    ("뒤판 옆선 시접 표기 삭제", m_sa_label, ["시접 표기가 있음", "1.5cm 표기"], True),
    ("칼라 식서를 가로로", m_collar_grain, ["골선 조각의 식서"], True),
    ("소매 어깨 노치 2cm 이동", m_sleeve_notch, ["소매 노치"], False),
    ("앞판 옆선 1cm 밀림", m_front_side, ["실제 조각 외곽선 위"], False),
    ("앞판 글자 겹침", m_text_overlap, ["겹치지 않음", "겹치는 곳 없음"], True),
    ("칼라 심지 빠짐", m_no_fuse, ["심지 위치"], False),
    ("웰트 6% 길게", m_welt, ["웰트 길이"], False),
    ("단추 하나 1cm 이동", m_button, ["단추"], False),
    ("라펠 꺾임선이 조각 밖으로", m_roll_line, ["조각 밖으로"], False),
    ("노치가 외곽선에서 떨어짐", m_notch_off, ["노치가 외곽선 위"], False),
    ("겉칼라 스프링 줄어듦", m_spring, ["스프링"], False),
    ("소매산 낮아짐", m_cap, ["소매산"], False),
    ("뒤 옆선 1.5cm 길어짐", m_back_side, ["옆선"], False),
    ("스톰실드 밑단이 골선에서 꺾임", m_shield_hem, ["스톰실드 밑단"], False),
    ("탭에 사이즈 표기 없음", m_no_size, ["사이즈 표기"], False),
    ("안단 단춧구멍 표시 없음", m_holes, ["단춧구멍"], False),
    ("밑소매 스트랩선 없음", m_strap_line, ["스트랩 위치선"], False),
    ("소매 밑단 시접 표기 틀림", m_hem_label, ["밑단 시접 표기"], False),
    ("건 플랩 위치선 어긋남", m_gun_line, ["건 플랩 위치선"], False),
]


def failures(pdf_check):
    """현재(결함 심은) 상태에서 실패한 검사 이름들."""
    names = []
    tmp = None
    if pdf_check:
        tmp = tempfile.mkdtemp()
        G.OUT_DIR = tmp
        with contextlib.redirect_stdout(io.StringIO()):
            G.build(SIZE)
        G.OUT_DIR = os.path.join(HERE, "pdf")
        os.environ["TRENCH_PDF_DIR"] = tmp
    for cat, name, st, val in CL.new_rows(SIZE):
        if st == CL.BAD:
            names.append(name)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        RD.main(SIZE)
    names += [l for l in buf.getvalue().splitlines() if "확인 필요" in l and l.startswith("|")]
    pieces, info = G.draft(SIZE)
    seams, neck = VF.seam_checks(info)
    names += [r["name"] for r in seams if not r["ok"]]
    names += [r["name"] for r in VF.ease_checks(SIZE, info, neck) if not r["ok"]]
    if pdf_check:
        buf = io.StringIO()
        old = sys.argv
        sys.argv = ["audit_pdf.py", SIZE]
        with contextlib.redirect_stdout(buf):
            runpy.run_path(os.path.join(HERE, "audit_pdf.py"), run_name="__main__")
        sys.argv = old
        del os.environ["TRENCH_PDF_DIR"]
        names += [l for l in buf.getvalue().splitlines() if l.startswith("FAIL")]
    return names


def main():
    base = failures(True)
    print(f"결함 없는 상태에서 실패 {len(base)}건" + (": " + "; ".join(base) if base else ""))
    missed = []
    for name, fn, expect, pdf in MUTATIONS:
        def patched(size, fn=fn):
            ps, info = ORIG_DRAFT(size)
            ps, info = copy.deepcopy((ps, info))
            fn(ps, info)
            return ps, info
        G.draft = patched
        try:
            got = failures(pdf)
        finally:
            G.draft = ORIG_DRAFT
        hit = [g for g in got if any(e in g for e in expect)]
        print(f"{'잡음 ' if hit else '놓침 '} {name}: " + (hit[0][:70] if hit else f"실패 목록 {got[:3]}"))
        if not hit:
            missed.append(name)
    # 타일 어긋남 (PDF만 해당)
    def bad_tile(c, pieces, ci, ri, rows, size):
        old = G.MARGIN
        G.MARGIN = old + 0.3
        try:
            ORIG_TILE(c, pieces, ci, ri, rows, size)
        finally:
            G.MARGIN = old
    G.tile_page = bad_tile
    try:
        got = failures(True)
    finally:
        G.tile_page = ORIG_TILE
    hit = [g for g in got if "이어 붙인" in g]
    print(f"{'잡음 ' if hit else '놓침 '} A4 장 3mm 어긋남: " + (hit[0][:70] if hit else str(got[:3])))
    if not hit:
        missed.append("A4 장 어긋남")
    # 인쇄 여백 3mm (PDF만 해당)
    G.MARGIN = 0.3
    try:
        got = failures(True)
    finally:
        G.MARGIN = 1.0
    hit = [g for g in got if "5mm" in g]
    print(f"{'잡음 ' if hit else '놓침 '} 인쇄 여백 3mm: " + (hit[0][:70] if hit else str(got[:3])))
    if not hit:
        missed.append("인쇄 여백")
    print(f"\n결과: 결함 {len(MUTATIONS) + 2}개 중 {len(MUTATIONS) + 2 - len(missed)}개 잡음" +
          (f", 놓침: {missed}" if missed else ""))
    return not missed and not base


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
