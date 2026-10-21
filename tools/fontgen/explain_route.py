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
import route_rule as rr
import verify_identity as vi
from bitfont import BitmapFont, count_holes, count_runs
from coverage import cmap_for

SIMHEI = r"C:\Windows\Fonts\simhei.ttf"
MSGOTHIC = r"C:\Windows\Fonts\msgothic.ttc"
REFS_12 = ("ark-pixel-zh_hans", "fusion-pixel-zh_hans", "zpix")

fs = BitmapFont(path=SIMHEI, index=0, px=12)
fm = BitmapFont(path=MSGOTHIC, index=0, px=12)
non_cps = cmap_for(MSGOTHIC, 0)
ark = BitmapFont(path=str(cs.ark_path()), index=0, px=12, cell_ascent=11, cell_descent=2)
ark_cps = cmap_for(str(cs.ark_path()), 0)

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
    sa = sig(ark.glyph(ch)) if cp in ark_cps else None
    if sa:
        out.append(f"  Ark Pixel             = {sa}   距离 {dist(sa, ref):g}")
    else:
        out.append("  Ark Pixel             = (无此字)")

    # 按**生产规则**复算一次选择。
    # 规则必须来自 route_rule (推导脚本与构建门禁共用同一份实现) ——
    # 这里自己写一遍的话, 工具给出的解释会和构建结果打架。
    cands = {
        "ideo": si,
        "non_ideo": sm,
        "ark": sa,
    }
    pool = rr.build_pool(cands, tuple(ref))
    picked, psig = rr.choose(pool, tuple(ref), hole_weight)
    if "ark" in pool and "ark" not in ():
        out.append("  (候选池: MS Gothic 缺此字形 -> 第三个像素源 Ark Pixel 参与竞争)")
    out.append(
        "  按规则应选: "
        + {"ideo": "SimHei", "non_ideo": "MS Gothic", "ark": "Ark Pixel"}.get(picked or "", "无")
    )

    rec = route.get(cp)
    if rec is None:
        out.append("  名单: 未列入路由 (保持 SimHei)")
    elif isinstance(rec, dict):
        out.append(f"  名单: 已列入路由 -> {rec.get('reason', '')}")
    else:
        out.append(f"  名单: 已列入路由 ({rec})")

Path  # noqa: B018  (保持 import 结构, 便于直接运行)
print("\n".join(out))
