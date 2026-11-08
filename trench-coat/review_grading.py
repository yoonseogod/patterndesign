#!/usr/bin/env python3
"""사이즈 간 검토: 치수가 사이즈마다 고르게 커지는지, 겹쳐 그렸을 때 선이 엇갈리지 않는지.

사용법: python3 review_grading.py   (결과 그림: verify/grading_nest.png)
"""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from shapely import affinity
from shapely.geometry import Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate_trench as G  # noqa: E402

font_manager.fontManager.addfont(os.path.join(HERE, "fonts", "NanumGothic-Regular.ttf"))
plt.rcParams["font.family"] = "NanumGothic"
plt.rcParams["axes.unicode_minus"] = False

SIZES = list(G.SIZES)
data = {s: G.draft(s) for s in SIZES}


def piece(s, key):
    return next(p for p in data[s][0] if p.key == key)


def measures(s):
    pieces, info = data[s]
    S = info["seams"]
    f, b = piece(s, "front"), piece(s, "back")
    return {
        "완성 가슴둘레": info["chest_garment"],
        "옷길이 (뒤중심)": info["y_L"] - info["cb_rise"],
        "어깨너비": 2 * info["sp_b"][0],
        "뒤 어깨길이": G.plen(S["back_shoulder"]),
        "진동둘레": info["AH"],
        "소매산 높이": info["CH"],
        "위팔둘레": info["B"],
        "소매부리": info["wW"],
        "소매길이": info["SLg"],
        "목둘레 (반, 칼라 끝까지)": info["Lc"],
        "앞판 폭": f.poly.bounds[2] - f.poly.bounds[0],
        "뒤판 폭": b.poly.bounds[2] - b.poly.bounds[0],
    }


M = {s: measures(s) for s in SIZES}
print("## 사이즈별 주요 치수 (cm)\n")
print("| 항목 | " + " | ".join(SIZES) + " | 사이즈 간 증가 | 판정 |")
print("|---|" + "---|" * len(SIZES) + "---|---|")
allok = True
for k in M[SIZES[0]]:
    vals = [M[s][k] for s in SIZES]
    steps = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
    mono = all(d > 0 for d in steps)
    even = (max(steps) - min(steps)) <= max(0.25, 0.15 * abs(sum(steps) / len(steps)))
    ok = mono and even
    allok &= ok
    print(f"| {k} | " + " | ".join(f"{v:.1f}" for v in vals) + " | " +
          ", ".join(f"+{d:.2f}" for d in steps) + f" | {'통과' if ok else '**확인 필요**'} |")

# 겹쳐 그리기: 앞판은 앞중심·목점, 뒤판은 뒤중심 목점, 소매는 소매산 꼭대기 기준
def aligned(s, key):
    p = piece(s, key)
    poly = p.poly
    info = data[s][1]
    if key == "front":
        return affinity.translate(poly, -info["Wh"], -info["fnd"])
    if key == "back":
        # 뒤트임(뒤중심 바깥 5cm)은 길이를 사이즈와 상관없이 38cm로 고정해 두어 겹침 검사에서 제외
        from shapely.geometry import box as _box
        poly = poly.intersection(_box(0, -10, 999, 999))
        return affinity.translate(poly, 0, -info["cb_rise"])
    minx, miny, maxx, maxy = poly.bounds
    return affinity.translate(poly, -(minx + maxx) / 2, -miny)

print("\n## 겹쳐 그린 선이 엇갈리지 않는지 (작은 사이즈가 큰 사이즈 안에 들어감)\n")
cross = []
for key in ("front", "back", "topsleeve", "undersleeve", "facing", "collar", "stand"):
    for i in range(len(SIZES) - 1):
        a, b = aligned(SIZES[i], key), aligned(SIZES[i + 1], key)
        out = a.difference(b.buffer(0.3)).area
        frac = out / a.area
        if frac > 0.002:
            cross.append(f"{key} {SIZES[i]}→{SIZES[i + 1]}: {frac * 100:.2f}% 바깥")
print("통과" if not cross else "**확인 필요** " + "; ".join(cross))
allok &= not cross

fig, axes = plt.subplots(1, 4, figsize=(16, 9), dpi=100)
colors = ["#1b6ca8", "#2a9d8f", "#e9a23b", "#c0392b"]
for ax, key, title in zip(axes, ("front", "back", "topsleeve", "undersleeve"), ("앞판", "뒤판", "윗소매", "밑소매")):
    for s, col in zip(SIZES, colors):
        x, y = aligned(s, key).exterior.xy
        ax.plot(x, [-v for v in y], color=col, lw=1, label=s)
    ax.set_aspect("equal"); ax.set_title(title); ax.axis("off")
axes[0].legend(title="사이즈", loc="lower left")
fig.suptitle("사이즈 겹쳐 보기 (그레이딩 네스트)")
fig.tight_layout()
os.makedirs(os.path.join(HERE, "verify"), exist_ok=True)
fig.savefig(os.path.join(HERE, "verify", "grading_nest.png"))
print(f"\n결과: {'모두 통과' if allok else '확인 필요 항목 있음'}")
sys.exit(0 if allok else 1)
