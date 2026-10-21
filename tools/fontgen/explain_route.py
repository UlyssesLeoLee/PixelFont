"""查某个码位在各个源下的结构签名, 与参考中位签名对比, 并说明路由为什么这么选。

用法:
    python tools/fontgen/explain_route.py 568E 642C 5B63

显示的判据必须与生产规则**完全一致** (字腔权重 4 + 字腔硬约束),
否则这个诊断工具会给出与构建结果矛盾的解释 —— 那比没有工具更糟。
"""

import sys
from pathlib import Path

sys.path.insert(0, "tools/fontgen")
import numpy as np
from fontTools.ttLib import TTFont

import charset as cs
import verify_identity as vi
from bitfont import BitmapFont, count_holes, count_runs
from coverage import cmap_for

SIMHEI = r"C:\Windows\Fonts\simhei.ttf"
MSGOTHIC = r"C:\Windows\Fonts\msgothic.ttc"
REFS_12 = ("ark-pixel-zh_hans", "fusion-pixel-zh_hans", "zpix")

fs = BitmapFont(path=SIMHEI, index=0, px=12)
fm = BitmapFont(path=MSGOTHIC, index=0, px=12)
non_cps = cmap_for(MSGOTHIC, 0)

refs = {}
for name in REFS_12:
    meta = vi.REFS[name]
    p = vi.REFDIR / meta["path"]
    tt = TTFont(str(p), fontNumber=0)
    g, _f = vi.ref_glyphs(p, meta["ppem"], sorted(tt.getBestCmap().keys()))
    refs[name] = g

route, mode, hole_weight = cs.load_ideo_route()

out = []


def sig(img):
    return (count_holes(img), count_runs(img, "col"), count_runs(img, "row"))


def dist(s, t):
    return hole_weight * abs(s[0] - t[0]) + abs(s[1] - t[1]) + abs(s[2] - t[2])


for arg in sys.argv[1:]:
    cp = int(arg, 16)
    ch = chr(cp)
    rs = []
    for name in REFS_12:
        b = refs[name].get(cp)
        if b is not None:
            rs.append(sig(b))
    if not rs:
        out.append(f"U+{cp:04X} {ch}  <参考集里没有这个字, 无法比对>")
        continue
    ref = tuple(int(np.median([r[i] for r in rs])) for i in range(3))
    si = sig(fs.glyph(ch))
    sm = sig(fm.glyph(ch)) if cp in non_cps else None

    out.append(f"U+{cp:04X} {ch}")
    out.append(f"  参考中位 (腔,竖,横) = {ref}")
    out.append(f"  SimHei                = {si}   距离 {dist(si, ref):g}")
    if sm:
        out.append(f"  MS Gothic             = {sm}   距离 {dist(sm, ref):g}")
    else:
        out.append("  MS Gothic             = (无此字)")

    # 按生产规则复算一次选择
    cands = [(si, "ideo")]
    if sm:
        cands.append((sm, "alt"))
    picked = cands
    if ref[0] >= 1:
        keep = [c for c in cands if c[0][0] >= 1]
        if keep and len(keep) < len(cands):
            out.append(
                "  (字腔硬约束生效: 排除 %s)"
                % ", ".join(
                    ("SimHei" if c[1] == "ideo" else "MS Gothic") for c in cands if c not in keep
                )
            )
            picked = keep
    best = min(picked, key=lambda c: dist(c[0], ref))
    out.append(f"  按规则应选: {'MS Gothic' if best[1] == 'alt' else 'SimHei'}")

    rec = route.get(cp)
    if rec is None:
        out.append("  名单: 未列入路由 (保持 SimHei)")
    elif isinstance(rec, dict):
        out.append(f"  名单: 已列入路由 -> {rec.get('reason', '')}")
    else:
        out.append(f"  名单: 已列入路由 ({rec})")

Path  # noqa: B018  (保持 import 结构, 便于直接运行)
print("\n".join(out))
