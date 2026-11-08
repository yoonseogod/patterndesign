#!/usr/bin/env python3
"""트렌치코트 패턴 검증.

1) 가상 봉제: 서로 꿰매는 선의 길이를 비교한다.
2) 3D 여유분 모델: 표준 인체(타원 단면을 쌓은 마네킹)에 패턴 둘레를 입혀
   부위별 여유분과 간격을 계산하고 그림으로 그린다.

천의 처짐·주름까지 계산하는 물리 시뮬레이션은 아니다. 그건 CLO 3D 같은
의상 시뮬레이터가 필요하다.

사용법: python3 verify_fit.py 100
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from generate_trench import SIZES, draft, plen  # noqa: E402

font_manager.fontManager.addfont(os.path.join(HERE, "fonts", "NanumGothic-Regular.ttf"))
font_manager.fontManager.addfont(os.path.join(HERE, "fonts", "NanumGothic-Bold.ttf"))
plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

# 사이즈별 표준 인체 (가슴 기준, 한국 남성 평균 비율로 추정)
def body_for(size):
    m = SIZES[size]
    C = m["chest"]
    return dict(chest=C, waist=C - 14, hip=C, neck=m["neck"], bicep=0.25 * C + 6.5,
                elbow=0.2 * C + 6.4, wrist=0.1 * C + 7.2, shoulder=C * 0.46,
                arm=m["sleeve"], height=m["height"], armpit_depth=0.215 * C,
                nape_waist=m["nape_waist"])


def seam_checks(info):
    S = info["seams"]
    L = lambda k: plen(S[k])
    neck_line = L("back_neck") + L("front_neck") + L("neck_ext")
    under_wrist = math.dist(S["under_wrist"][0], S["under_wrist"][1])
    rows = [
        # 이름, A, B, 목표 차이(A-B) 범위, 설명
        ("어깨선 (뒤 − 앞)", L("back_shoulder"), L("front_shoulder"), (0.3, 1.0), "뒤 어깨에 오그림 여유 0.3~1cm"),
        ("옆선 (뒤 − 앞)", L("back_side"), L("front_side"), (-0.3, 0.3), "같아야 함"),
        ("소매산 − 진동둘레", L("cap"), L("back_arm") + L("front_arm"), (2.0, 4.0), "코트 소매산 여유 2~4cm"),
        ("소매 앞솔기 (윗 − 밑)", L("top_front"), L("under_front"), (0.0, 0.8), "윗소매 팔꿈치 여유 0~0.8cm"),
        ("소매 뒷솔기 (윗 − 밑)", L("top_back"), L("under_back"), (-0.3, 1.0), "윗소매 팔꿈치 여유 0~1cm"),
        ("칼라밴드 아랫선 − 목둘레선", L("stand_bot"), neck_line, (-0.5, 0.5), "같아야 함"),
        ("칼라 아랫선 − 칼라밴드 윗선", L("fall_bot"), L("stand_top"), (-0.5, 0.8), "같거나 칼라가 약간 김"),
        ("안단 앞단 − 앞판 앞단", L("facing_edge"), L("front_edge"), (-0.1, 0.1), "같아야 함"),
        ("소매 밑단 (윗+밑) − 설계값", L("top_wrist") + under_wrist, info["wW"], (-0.3, 0.3), "설계 둘레와 같아야 함"),
    ]
    out = []
    for name, a, b, (lo, hi), note in rows:
        d = a - b
        out.append(dict(name=name, a=a, b=b, d=d, ok=lo <= d <= hi, rng=(lo, hi), note=note))
    return out, neck_line


def x_at_y(pts, y):
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if (a[1] - y) * (b[1] - y) <= 0 and a[1] != b[1]:
            t = (y - a[1]) / (b[1] - a[1])
            return a[0] + t * (b[0] - a[0])
    return None


def garment_circ(info, y):
    """패턴에서 높이 y(옆목점 기준 cm)의 완성 둘레."""
    S = info["seams"]
    xb = x_at_y(S["back_side"], y)
    xf = x_at_y(S["front_side"], y)
    if xb is None or xf is None:
        return None
    return 2 * (xb + (info["Wh"] - xf))


def ease_checks(size, info, neck_line):
    b = body_for(size)
    S = info["seams"]
    y_scye = info["scye"]
    chest_g = garment_circ(info, y_scye + 0.01)
    waist_g = garment_circ(info, info["y_w"])
    hip_g = garment_circ(info, info["y_h"])
    hem_g = garment_circ(info, info["y_L"] - 1.5)
    shoulder_g = 2 * info["sp_b"][0]
    rows = [
        ("가슴둘레", b["chest"], chest_g, (16, 26), "트렌치코트 일반 16~26cm (버버리 켄싱턴 약 10~12)"),
        ("허리둘레 (벨트로 조임)", b["waist"], waist_g, (20, 40), "벨트로 조이는 디자인이라 넉넉해도 됨"),
        ("엉덩이둘레", b["hip"], hip_g, (14, 30), "앉고 걸을 여유"),
        ("밑단둘레 (무릎 위)", 95, hem_g, (30, 60), "보폭 여유 (뒤트임 별도)"),
        ("목둘레 (앞중심까지)", b["neck"], 2 * (neck_line - plen(S["neck_ext"])), (6, 11),
         "재킷 위에 입는 코트 6~11cm"),
        ("어깨너비", b["shoulder"], shoulder_g, (0.5, 4), "패드 포함 코트 0.5~4cm"),
        ("위팔둘레", b["bicep"], info["B"], (6, 12), "재킷 위에 입을 여유"),
        ("소매부리", b["wrist"], info["wW"], (12, 22), "손이 빠지고 재킷 소매가 들어갈 여유"),
        ("진동깊이 (옆목점→겨드랑이)", b["armpit_depth"], y_scye, (3, 7), "코트는 몸보다 3~7cm 깊게"),
        ("소매길이 (어깨점→손목)", b["arm"], info["SLg"], (3.0, 5.5), "패드·소매산 부풀림 + 손목을 덮는 길이"),
    ]
    out = []
    for name, body, g, (lo, hi), note in rows:
        e = g - body
        out.append(dict(name=name, body=body, g=g, e=e, ok=lo <= e <= hi, rng=(lo, hi), note=note))
    return out


# ── 3D 모델 ──────────────────────────────────────────────────────────────

def ellipse_perim(a, b):
    h = ((a - b) / (a + b)) ** 2
    return math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))


def axes_for(circ, ratio):
    """둘레와 가로/세로 비율로 타원 반지름."""
    lo, hi = 1, 60
    for _ in range(50):
        bb = (lo + hi) / 2
        if ellipse_perim(bb * ratio, bb) < circ:
            lo = bb
        else:
            hi = bb
    return bb * ratio, bb


def offset_to(a, b, circ):
    """몸 타원을 균일하게 키워 둘레 circ가 되는 간격 d."""
    lo, hi = 0, 40
    for _ in range(50):
        d = (lo + hi) / 2
        if ellipse_perim(a + d, b + d) < circ:
            lo = d
        else:
            hi = d
    return d


def body_sections(size):
    """(높이, 둘레, 가로/세로 비) — 바닥에서 cm."""
    b = body_for(size)
    H = b["height"]
    nape = H * 0.857
    return nape, [
        (H * 0.06, 34 * 2, 1.9),      # 발목 (두 다리)
        (H * 0.28, 38 * 2 + 8, 1.9),  # 무릎
        (H * 0.40, 95, 1.55),         # 허벅지
        (H * 0.48, b["hip"], 1.32),
        (H * 0.56, b["hip"] - 6, 1.3),
        (nape - b["nape_waist"], b["waist"], 1.25),
        (nape - b["nape_waist"] + 10, b["waist"] + 7, 1.3),
        (nape - b["armpit_depth"] + 2, b["chest"], 1.38),
        (nape - 8, b["chest"] + 4, 1.75),     # 어깨 아래 (삼각근)
        (nape - 4, b["shoulder"] * 2.2, 2.6),  # 어깨
        (nape + 1, b["neck"], 1.1),
        (nape + 10, b["neck"], 1.1),
        (nape + 14, 56, 1.15),        # 머리
        (nape + 22, 58, 1.2),
        (nape + 27, 30, 1.2),
    ]


def render_3d(size, info, path):
    nape, secs = body_sections(size)
    b = body_for(size)
    th = np.linspace(0, 2 * np.pi, 72)
    fig = plt.figure(figsize=(15, 9), dpi=110)
    garment_y = np.arange(info["scye"] + 0.5, info["y_L"] - 1.5, 1.0)

    def body_at(h):
        hs = [s[0] for s in secs]
        cs = [s[1] for s in secs]
        rs = [s[2] for s in secs]
        return np.interp(h, hs, cs), np.interp(h, hs, rs)

    # 몸 표면
    hs = np.linspace(secs[0][0], secs[-1][0], 80)
    X, Y, Z = [], [], []
    for h in hs:
        c, r = body_at(h)
        a, bb = axes_for(c, r)
        X.append(a * np.cos(th)); Y.append(bb * np.sin(th)); Z.append(np.full_like(th, h))
    X, Y, Z = map(np.array, (X, Y, Z))

    # 옷 표면 (가슴선~밑단: 패턴 둘레로)
    GX, GY, GZ, gaps = [], [], [], []
    for y in garment_y:
        h = nape + info["cb_rise"] - y
        g = garment_circ(info, y)
        c, r = body_at(h)
        a, bb = axes_for(c, r)
        d = offset_to(a, bb, g)
        gaps.append((h, d, g, c))
        GX.append((a + d) * np.cos(th)); GY.append((bb + d) * np.sin(th)); GZ.append(np.full_like(th, h))
    # 어깨~가슴: 어깨 너비와 가슴 둘레를 이어서
    top_h = nape + info["cb_rise"] - info["scye"]
    sh_w = info["sp_b"][0]
    for h in np.linspace(top_h, nape - 2, 10):
        t = (h - top_h) / (nape - 2 - top_h)
        a0, b0 = GX[0][0], GY[0][18]
        a = (1 - t) * a0 + t * (sh_w + 0.5)
        bb = (1 - t) * b0 + t * 10.5
        GX.insert(0, a * np.cos(th)); GY.insert(0, bb * np.sin(th)); GZ.insert(0, np.full_like(th, h))
    GX, GY, GZ = map(np.array, (GX, GY, GZ))

    # 소매 (팔을 22° 벌린 원통)
    def arm_tube(side, scale_circs, color, alpha, ax):
        sh = np.array([side * (b["shoulder"] / 2 - 2), 0, nape - 5])
        ang = math.radians(10)
        dirv = np.array([side * math.sin(ang), 0, -math.cos(ang)])
        L = b["arm"] + 3
        u = np.linspace(0, 1, 30)
        circs = np.interp(u, [0, 0.12, 0.5, 1], scale_circs)
        n1 = np.array([math.cos(ang), 0, side * math.sin(ang)]) * side
        n2 = np.array([0, 1, 0])
        P = [sh + dirv * L * uu + (c / (2 * np.pi)) * (np.outer(np.cos(th), n1) + np.outer(np.sin(th), n2))
             for uu, c in zip(u, circs)]
        P = np.array(P)
        ax.plot_surface(P[:, :, 0], P[:, :, 1], P[:, :, 2], color=color, alpha=alpha, linewidth=0, shade=True)

    views = [(0, -90, "정면"), (0, 0, "옆면"), (18, -55, "사선")]
    for i, (el, az, title) in enumerate(views):
        ax = fig.add_axes([0.0 + i * 0.235, 0.02, 0.26, 0.9], projection="3d")
        ax.plot_surface(X, Y, Z, color="#c9b9a6", alpha=1.0, linewidth=0, shade=True)
        ax.plot_surface(GX, GY, GZ, color="#b8945a", alpha=0.45, linewidth=0, shade=True)
        for s in (-1, 1):
            arm_tube(s, [b["bicep"] + 4, b["bicep"], b["elbow"], b["wrist"]], "#c9b9a6", 1.0, ax)
            arm_tube(s, [info["AH"] * 0.9, info["B"], info["B"] * 0.85, info["wW"]], "#b8945a", 0.35, ax)
        ax.view_init(elev=el, azim=az)
        ax.set_box_aspect((1, 0.6, 2.2), zoom=1.2)
        ax.set_xlim(-45, 45); ax.set_ylim(-27, 27); ax.set_zlim(0, b["height"])
        ax.set_axis_off()
        ax.set_title(title, fontsize=12)

    ax = fig.add_axes([0.76, 0.1, 0.21, 0.78])
    hh = [g[0] for g in gaps]
    ax.plot([g[1] for g in gaps], hh, color="#8a5a1f", lw=2, label="몸과 옷 사이 간격")
    ax.set_xlabel("간격 (cm, 평균)")
    ax.set_ylabel("바닥에서 높이 (cm)")
    for lab, h in (("가슴", nape + info["cb_rise"] - info["scye"]), ("허리(벨트)", nape + info["cb_rise"] - info["y_w"]),
                   ("엉덩이", nape + info["cb_rise"] - info["y_h"]), ("밑단", nape + info["cb_rise"] - info["y_L"])):
        ax.axhline(h, color="#bbb", lw=0.8, ls="--")
        ax.text(ax.get_xlim()[1] if False else 0.2, h + 0.8, lab, fontsize=9, color="#555")
    ax.set_xlim(0, max(g[1] for g in gaps) * 1.3)
    ax.grid(alpha=0.3)
    ax.set_title("높이별 여유 간격", fontsize=12)
    fig.suptitle(f"트렌치코트 {size} — 표준 인체(키 {b['height']}, 가슴 {b['chest']}) 착용 여유 모델", fontsize=14)
    fig.savefig(path)
    plt.close(fig)


def main(size):
    pieces, info = draft(size)
    seams, neck_line = seam_checks(info)
    eases = ease_checks(size, info, neck_line)
    out_dir = os.path.join(HERE, "verify")
    os.makedirs(out_dir, exist_ok=True)
    img = os.path.join(out_dir, f"fit3d_{size}.png")
    render_3d(size, info, img)
    lines = [f"# 트렌치코트 {size} 검증 결과", "", "## 1. 가상 봉제 (꿰매는 선 길이 비교)", "",
             "| 봉제선 | A | B | 차이 | 목표 | 판정 |", "|---|---|---|---|---|---|"]
    for r in seams:
        lines.append(f"| {r['name']} | {r['a']:.1f} | {r['b']:.1f} | {r['d']:+.1f} | "
                     f"{r['rng'][0]:+.1f}~{r['rng'][1]:+.1f} ({r['note']}) | {'통과' if r['ok'] else '**확인 필요**'} |")
    lines += ["", "## 2. 인체 대비 여유분", "", "| 부위 | 인체 | 옷 | 여유 | 권장 | 판정 |", "|---|---|---|---|---|---|"]
    for r in eases:
        lines.append(f"| {r['name']} | {r['body']:.1f} | {r['g']:.1f} | {r['e']:+.1f} | "
                     f"{r['rng'][0]}~{r['rng'][1]} ({r['note']}) | {'통과' if r['ok'] else '**확인 필요**'} |")
    lines += ["", f"![3D]({os.path.basename(img)})", ""]
    md = os.path.join(out_dir, f"report_{size}.md")
    open(md, "w").write("\n".join(lines))
    print("\n".join(lines))
    return seams, eases


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["100"]):
        main(s)
