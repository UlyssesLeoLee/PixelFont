"""推导 ideo 路由名单 —— 哪些汉字该改用非汉字源 (MS Gothic) 的原生 12px 点阵。

判据 (三个条件同时成立):
    1. 汉字源 (SimHei) 渲染出来的字**一个腔都没有** —— 整字塌成白块
    2. 非汉字源 (MS Gothic) 渲染出来的字**有腔** —— 切过去能救回来
    3. 至少 --min-ref-votes 套**参考像素字体**都说这个字该有腔
       (独立第三方画的, 不经过 SimHei 这条链路)

为什么第 3 条不能省:
    只按 1+2 筛, 会把 94 个字切走, 其中 46 个参考字体明确说"这个字本来就该没有腔"
    (步/份/运/至/拜 这类结构上就没有封闭空间的字)。切过去反而与参考不一致。
    加上第 3 条后, 名单只剩参考一致认可的那些。

为什么名单存成文件而不是每次构建时现算:
    参考字体在 third_party/ 里, 不入库, 普通构建环境没有它们。
    名单是"用参考字体验证过一次的结论", 存下来供构建期使用;
    换源字体版本后用本脚本重新推导并比对 (--check 模式)。

用法:
    python tools/fontgen/derive_ideo_route.py                # 推导并写 ideo_route.json
    python tools/fontgen/derive_ideo_route.py --check        # 只比对, 不写
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from fontTools.ttLib import TTFont

import charset as cs
import verify_identity as vi
from bitfont import count_holes
from coverage import cmap_for

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "ideo_route.json"

# 参与投票的参考字体。Unifont 是 16px, 字腔天然比 12px 基准多, 单独归一类。
REFS_12PX = ("ark-pixel-zh_hans", "fusion-pixel-zh_hans", "zpix")
REFS_16PX = ("unifont-16",)


def ref_hole_counts(refs: dict[str, dict[int, np.ndarray]], cps: list[int]) -> dict[int, dict[str, int]]:
    out: dict[int, dict[str, int]] = {}
    for cp in cps:
        row = {}
        for name, g in refs.items():
            a = g.get(cp)
            if a is not None:
                row[name] = vi.holes(a) if hasattr(vi, "holes") else _holes(a)
        if row:
            out[cp] = row
    return out


def _holes(a: np.ndarray) -> int:
    """字腔数 (4 邻域)。"""
    ink = a > 0
    h, w = ink.shape
    seen = np.zeros_like(ink)
    n = 0
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0, x0] or ink[y0, x0]:
                continue
            q = [(y0, x0)]
            seen[y0, x0] = True
            touch = False
            while q:
                y, x = q.pop()
                if y == 0 or y == h - 1 or x == 0 or x == w - 1:
                    touch = True
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and not ink[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if not touch:
                n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="推导 ideo 路由名单")
    ap.add_argument("--min-ref-votes", type=int, default=2, help="几套参考字体说该有腔才采信")
    ap.add_argument(
        "--all-covered",
        action="store_true",
        help="方案 B: 非汉字源覆盖的汉字全部改走非汉字源 (不要求字腔塌陷)",
    )
    ap.add_argument("--check", action="store_true", help="只比对现有名单, 不写文件")
    ap.add_argument("--out", default=str(OUT), help="输出路径")
    args = ap.parse_args()

    items = cs.build_charset()
    hanzi = [(ch, cat) for ch, cat in items if cat == "hanzi"]
    stack = cs.build_stack(route={})  # 推导时不能带路由, 否则自己验证自己

    refs: dict[str, dict[int, np.ndarray]] = {}
    for name in (*REFS_12PX, *REFS_16PX):
        meta = vi.REFS[name]
        p = vi.REFDIR / meta["path"]
        if not p.exists():
            print(f"缺少参考字体: {p}\n先跑 tools/fontgen/fetch_ref_fonts.py", file=sys.stderr)
            return 2
        tt = TTFont(str(p), fontNumber=0)
        g, _f = vi.ref_glyphs(p, meta["ppem"], sorted(tt.getBestCmap().keys()))
        refs[name] = g
        print(f"参考 {name}: {len(g)} 个字形")

    route: dict[str, str] = {}
    skipped_no_alt = 0
    # 必须查 cmap, 不能只看渲染结果:
    # 源字体缺字时 FreeType 会画 .notdef —— 一个**空心矩形**的豆腐块,
    # 它自带 1 个"字腔", 会让"备选源能救回"这个判据把缺字也放进来。
    # (这个坑真踩过: 推导出的 95 个码位里有 39 个是 MS Gothic 根本没有的汉字。)
    non_ideo_cps = cmap_for(stack.non_ideo.path, stack.non_ideo.index)
    for ch, _cat in hanzi:
        cp = ord(ch)
        if cp not in non_ideo_cps:
            skipped_no_alt += 1
            continue
        h_ideo = count_holes(stack.ideo.glyph(ch))
        h_alt = count_holes(stack.non_ideo.glyph(ch))
        if args.all_covered:
            # 方案 B: 非汉字源覆盖的汉字全部改走非汉字源 (原生点阵), 不看字腔
            if h_alt <= 0:
                skipped_no_alt += 1
                continue
            route[f"U+{cp:04X}"] = (
                f"方案B 全覆盖: 汉字源 {h_ideo} 腔 / MS Gothic {h_alt} 腔, "
                f"改用原生点阵以贴近参考像素字体"
            )
            continue
        if h_ideo > 0:
            continue
        if h_alt <= 0:
            skipped_no_alt += 1
            continue
        votes = {}
        for name in REFS_12PX:
            b = refs[name].get(cp)
            if b is not None:
                votes[name] = _holes(b)
        if len(votes) < 2:
            continue
        n_vote = sum(1 for v in votes.values() if v > 0)
        if n_vote < args.min_ref_votes:
            continue
        detail = ", ".join(f"{n.split('-')[0]}:{v}" for n, v in sorted(votes.items()))
        route[f"U+{cp:04X}"] = f"SimHei 12px 字腔全失(0), MS Gothic 有 {h_alt} 腔, 参考判定 {detail}"

    if args.check:
        cur, cur_mode = cs.load_ideo_route()
        cur_cps = {f"U+{cp:04X}" for cp in cur}
        new_cps = set(route)
        add = sorted(new_cps - cur_cps)
        rem = sorted(cur_cps - new_cps)
        new_mode = "all" if args.all_covered else "blob"
        print(f"现有 {len(cur_cps)} 个 (mode={cur_mode}), 推导出 {len(new_cps)} 个 (mode={new_mode})")
        if cur_mode != new_mode:
            print(f"  ⚠ 模式不一致: 现有 {cur_mode} -> 推导 {new_mode}")
        if add:
            print("  新增:", " ".join(add))
        if rem:
            print("  应移除:", " ".join(rem))
        if not add and not rem and cur_mode == new_mode:
            print("  ✔ 名单与推导结果一致")
            return 0
        return 1

    doc = {
        "tool": "derive_ideo_route",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "all" if args.all_covered else "blob",
        "criterion": {
            "mode": "all" if args.all_covered else "blob",
            "1": (
                "非汉字源 (MS Gothic) 覆盖的汉字全部改走非汉字源 (原生 12px 点阵)"
                if args.all_covered
                else "汉字源 (SimHei) 渲染出的字字腔数 == 0 (整字塌成白块)"
            ),
            "2": (
                "非汉字源渲染出的字字腔数 > 0"
                if args.all_covered
                else "非汉字源 (MS Gothic) 渲染出的字字腔数 > 0 (切过去能救回来)"
            ),
            "3": (
                "不适用"
                if args.all_covered
                else f"至少 {args.min_ref_votes} 套 12px 参考字体 (Ark/Fusion/Zpix) 说该字应有字腔"
            ),
        },
        "ref_votes_12px": list(REFS_12PX),
        "count": len(route),
        "route": dict(sorted(route.items())),
    }
    op = Path(args.out)
    op.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n推导完成: {len(route)} 个码位 -> {op}")
    print(f"(汉字源无腔且备选源也无腔的 {skipped_no_alt} 个, 不在名单内)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
