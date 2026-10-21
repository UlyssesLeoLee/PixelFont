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


def _sig(arr: np.ndarray) -> tuple[int, int, int]:
    """字形结构签名: (字腔数, 竖笔画数, 横笔画数)。"""
    return (_holes(arr), _col_runs(arr), _row_runs(arr))


def _row_runs(a: np.ndarray) -> int:
    ink = a > 0
    h, w = ink.shape
    n = 0
    for y in range(h):
        prev = False
        for x in range(w):
            cur = bool(ink[y, x])
            if cur and not prev:
                n += 1
            prev = cur
    return n


def _col_runs(a: np.ndarray) -> int:
    ink = a > 0
    h, w = ink.shape
    n = 0
    for x in range(w):
        prev = False
        for y in range(h):
            cur = bool(ink[y, x])
            if cur and not prev:
                n += 1
            prev = cur
    return n


def _crop(a: np.ndarray) -> np.ndarray | None:
    ys, xs = np.nonzero(a)
    if len(xs) == 0:
        return None
    return a[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def main() -> int:
    ap = argparse.ArgumentParser(description="推导 ideo 路由名单")
    ap.add_argument("--min-ref-votes", type=int, default=2, help="几套参考字体说该有腔才采信")
    ap.add_argument(
        "--all-covered",
        action="store_true",
        help="方案 B: 非汉字源覆盖的汉字全部改走非汉字源 (不要求字腔塌陷)",
    )
    ap.add_argument(
        "--per-char",
        action="store_true",
        help="逐字选源: 对每个汉字, 选结构签名更贴近参考字体的那个源 (推荐)",
    )
    ap.add_argument(
        "--hole-weight",
        type=float,
        default=1.0,
        help="逐字选源距离函数里字腔项的权重 (默认 1)。字腔是拓扑量, 不受字宽影响;"
        "横/竖笔画分段数受参考字体的分辨率与字宽影响, 天然有偏",
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

    if args.per_char:
        # 逐字选源: 拿参考字体的结构签名中位数当裁判, 每个字选更贴近的那个源。
        # 与"只切塌陷的字"相比, 它不预设"哪个源更好", 而是逐字比。
        ref_sig: dict[int, tuple[int, int, int]] = {}
        for ch, _cat in hanzi:
            cp = ord(ch)
            rs = []
            for name in REFS_12PX:
                b = refs[name].get(cp)
                if b is not None:
                    rs.append(_sig(b))
            if rs:
                ref_sig[cp] = tuple(int(np.median([r[i] for r in rs])) for i in range(3))

        def dist(s, t):
            w = args.hole_weight
            return w * abs(s[0] - t[0]) + abs(s[1] - t[1]) + abs(s[2] - t[2])

        def _holes_of(img):
            a = _crop(np.array(img, dtype=np.uint8) > 0)
            return None if a is None else _holes(a)

        # 字腔硬约束: 参考字体说这个字该有腔, 而某个候选源渲染出 0 腔 (整字白块),
        # 而另一个候选源有腔 —— 那就**必须**选有腔的那个, 不管笔画数差多少。
        # 理由: 0 腔是**可见的硬错误**(整个字渲染成一块白块), 笔画数差只是风格差异。
        # 实测: 不加这条约束时, 「粔」U+7CD5 被判给 SimHei (0 腔, 白块),
        #       加了之后改判 MS Gothic (3 腔), 字腔保住了。
        def pick(s_id, s_mg, ref):
            cands = [(s_id, "ideo"), (s_mg, "alt")]
            if ref[0] >= 1:
                keep = [c for c in cands if c[0] is not None and c[0][0] >= 1]
                if keep:
                    cands = keep
            cands = [c for c in cands if c[0] is not None]
            if not cands:
                return None
            return min(cands, key=lambda c: dist(c[0], ref))

        n_switch = 0
        n_keep = 0
        d_now = []
        d_new = []
        for ch, _cat in hanzi:
            cp = ord(ch)
            if cp not in ref_sig:
                continue
            a_id = _crop(np.array(stack.ideo.glyph(ch), dtype=np.uint8) > 0)
            if a_id is None:
                continue
            s_id = _sig(a_id)
            d_id = dist(s_id, ref_sig[cp])
            d_now.append(d_id)
            s_mg = None
            if cp in non_ideo_cps:
                a_mg = _crop(np.array(stack.non_ideo.glyph(ch), dtype=np.uint8) > 0)
                if a_mg is not None:
                    s_mg = _sig(a_mg)
            d_mg = dist(s_mg, ref_sig[cp]) if s_mg is not None else None
            best = pick(s_id, s_mg, ref_sig[cp])
            if best is None:
                n_keep += 1
                d_new.append(d_id)
                continue
            s_best, src = best
            d_best = dist(s_best, ref_sig[cp])
            if src == "alt":
                n_switch += 1
                d_new.append(d_best)
                why = (
                    f"MS Gothic 签名 {list(s_mg)} 比 SimHei {list(s_id)} "
                    f"更贴近参考 {list(ref_sig[cp])} (距离 {d_mg} < {d_id})"
                    if d_mg < d_id
                    else (
                        f"字腔硬约束: 参考该字有 {ref_sig[cp][0]} 腔, SimHei 渲染出 0 腔"
                        f" (整字白块), 改用 MS Gothic 的 {s_mg[0]} 腔"
                    )
                )
                route[f"U+{cp:04X}"] = {
                    "reason": "逐字选源: " + why,
                    "sig_ideo": list(s_id),
                    "sig_alt": list(s_mg),
                    "sig_ref": list(ref_sig[cp]),
                }
            else:
                n_keep += 1
                d_new.append(d_best)
        print()
        print(f"逐字选源: 切 {n_switch}, 保持 SimHei {n_keep}")
        print(
            "  与参考的结构距离: 现状均值 %.2f -> 选源后 %.2f; 完全吻合 %d -> %d"
            % (
                float(np.mean(d_now)),
                float(np.mean(d_new)),
                sum(1 for d in d_now if d == 0),
                sum(1 for d in d_new if d == 0),
            )
        )
        doc = {
        "tool": "derive_ideo_route",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "per_char",
        "hole_weight": args.hole_weight,
        "criterion": {
            "mode": "per_char",
            "1": "对每个汉字, 分别用 SimHei 与 MS Gothic 渲染, 取结构签名 (字腔数, 竖笔画数, 横笔画数)",
            "2": "参考字体的结构签名取 3 套 12px 参考 (Ark/Fusion/Zpix) 的中位数, 作为裁判",
            "3": "MS Gothic 的签名更贴近裁判时切源, 否则保持 SimHei (逐字比较, 不预设哪个源更好)",
            "4": f"距离 = {args.hole_weight:g}×|字腔差| + |竖笔差| + |横笔差|"
                  " (字腔是拓扑量, 不受字宽/分辨率影响, 故给更高权重)",
            "5": "字腔硬约束: 参考该字有腔而 SimHei 渲染出 0 腔 (整字白块) 时, "
                  "必须切到有腔的源, 不看笔画数差 (0 腔是可见硬错误, 笔画差只是风格差异)",
        },
        "ref_votes_12px": list(REFS_12PX),
        "stats": {
            "switched": n_switch,
            "kept_simhei": n_keep,
            "dist_mean_before": round(float(np.mean(d_now)), 3),
            "dist_mean_after": round(float(np.mean(d_new)), 3),
            "exact_before": sum(1 for d in d_now if d == 0),
            "exact_after": sum(1 for d in d_new if d == 0),
        },
        "count": len(route),
        "route": dict(sorted(route.items())),
    }
        if args.check:
            cur, cur_mode, cur_w = cs.load_ideo_route()
            cur_cps = {f"U+{cp:04X}" for cp in cur}
            new_cps = set(route)
            add = sorted(new_cps - cur_cps)
            rem = sorted(cur_cps - new_cps)
            print(
                f"现有 {len(cur_cps)} 个 (mode={cur_mode}, hole_weight={cur_w:g}), "
                f"推导出 {len(new_cps)} 个 (mode=per_char, hole_weight={args.hole_weight:g})"
            )
            if cur_mode != "per_char":
                print(f"  ⚠ 模式不一致: 现有 {cur_mode} -> 推导 per_char")
            if abs(cur_w - args.hole_weight) > 1e-9:
                print(f"  ⚠ 字腔权重不一致: 现有 {cur_w:g} -> 推导 {args.hole_weight:g}")
            if add:
                print(f"  新增 {len(add)}:", " ".join(add))
            if rem:
                print(f"  应移除 {len(rem)}:", " ".join(rem))
            if not add and not rem and cur_mode == "per_char":
                print("  ✔ 名单与推导结果一致")
                return 0
            return 1
        op = Path(args.out)
        op.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"推导完成: {len(route)} 个码位 -> {op}")
        return 0

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
        cur, cur_mode, _cur_w = cs.load_ideo_route()
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
