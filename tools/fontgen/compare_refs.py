"""字形对照表生成器 —— 用开源像素字体做"并排目视比对"的尺子。

为什么要做这个 (以及为什么不能全自动):
    跨字体的**自动形状相似度**实测做不了逐字身份判定:
        特征          ascii 命中率   kana 命中率   hanzi 命中率
        3x3+5x5 密度      52.1%          37.5%          7.5%
        8x8 密度          25.5%          26.7%          0.8%
        16x16 原始像素    41.5%          35.0%          3.3%
        IoU 精排          53.2%          25.0%          4.2%
    汉字这一档的候选池有两万多个, 而不同汉字的密度分布彼此高度相似,
    逐像素又会被画风差异淹没 —— 指标分辨力不够, 拿它判身份是在制造假结论。

    但**并排目视**是可靠的: 同一个字, 不管谁画的, 骨架结构一致;
    画错了字, 结构一眼就不对。所以这里的分工是:
        · 自动化: 做**与指标无关**的硬检查 (位图完全相同 / 覆盖率 / 结构离群 / 字腔丢失)
        · 目视比对: 生成并排对照表, 由子代理逐批复核"我们画的到底是不是这个字"

对照表格式: 每个字一段, 我方与各参考字体并排, 供逐字核对。

【判据的取舍 —— 每条都要能回答"这个数怎么来的"】
    · EXACT_COLLIDE  我们的位图与参考字体的**另一个**码位逐像素相同 → 硬错误
    · COUNTER_LOST   参考字体的这个字有字腔, 我们一个都没有 (字腔全被填死)
                     → 硬错误。这是唯一被实测证明有分辨力的结构判据:
                       3 套独立参考一致认定的 105 个零腔字, 目视确认全是白块
    · STRUCTURE_OUTLIER  竖/横笔画数与参考差得离谱 (z-score 离群) → 告警
    · STYLE_DIFF     墨量差异 → **只记录不下判定**。
                       曾经的"平均墨量"判据是错的: 它比的是不同包围盒面积下的
                       均值, 我们的 '!' 是 10x1 框里 8 墨 (均值 0.80),
                       Ark 的 '!' 是 8x6 框里 7 墨 (均值 0.15), 差 +0.65 ——
                       纯属面积伪影, 却让 128 个字全部误报。
                       换成"墨量像素数相对差"后误报数一样高 (十/个/火/巾/％/*),
                       证明**墨量对身份判定没有分辨力**, 只能当描述性指标。
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

import charset as cs  # noqa: E402
import verify_identity as vi  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def row_runs(a: np.ndarray) -> int:
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


def col_runs(a: np.ndarray) -> int:
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


def block(a: np.ndarray, ink: str = "#", paper: str = ".") -> list[str]:
    return ["".join(ink if v else paper for v in row) for row in a]


def holes(a: np.ndarray) -> int:
    """字腔数: 被墨迹完全包围的白区连通分量数 (4 邻域)。

    为什么这个指标比"平均墨量"可靠:
        墨量是**面积**的函数, 包围盒一大就摊薄, 分辨不出"笔画粘连";
        字腔是**拓扑**的 —— 腔还在就是还在, 填死了就是 0, 与面积无关。
        实测: 3 套独立参考一致认定"该有腔"的字里, 我们零腔的有 105 个,
        目视确认全是白块 (量/置/叠/膏/舅/亮/亭/停...)。
    """
    ink = a > 0
    h, w = ink.shape
    seen = np.zeros_like(ink)
    n = 0
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0, x0] or ink[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            touch_border = False
            while stack:
                y, x = stack.pop()
                if y == 0 or y == h - 1 or x == 0 or x == w - 1:
                    touch_border = True
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and not ink[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if not touch_border:
                n += 1
    return n


def side_by_side_blocks(
    ours: np.ndarray, refs: list[tuple[str, np.ndarray | None]], gap: int = 3
) -> list[str]:
    """并排渲染: 我方 + 各参考字体, 顶部带标签行。"""
    blocks = [("我方", ours)] + [(name, None if r is None else r) for name, r in refs]
    rendered = []
    for name, arr in blocks:
        if arr is None:
            rendered.append((name, ["(缺)"]))
        else:
            rendered.append((name, block(arr)))
    h = max(len(b) for _, b in rendered)
    head = "  ".join(f"{name:<{max(6, len(b[0]) if b else 6)}}" for name, b in rendered)
    lines = [head]
    for i in range(h):
        parts = []
        for name, b in rendered:
            parts.append(b[i] if i < len(b) else " " * len(b[0]))
        lines.append((" " * gap).join(parts))
    return lines


def holes_of_glyph(img) -> int:
    """给 BitmapFont 的 cell 图算字腔数 (裁到墨迹外接矩形后统计)。"""
    a = (np.array(img, dtype=np.uint8) > 0).astype(np.float32)
    ys, xs = np.nonzero(a)
    if len(xs) == 0:
        return 0
    return holes(a[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1])


def _same_bytes(a, b) -> bool:
    """两个参考位图是否完全相同 (形状与尺寸都相同)。"""
    if a is None or b is None:
        return False
    return a.shape == b.shape and a.tobytes() == b.tobytes()


def cat_of_chars() -> list[tuple[str, str]]:
    """字符集及其分类 —— 判定"两个汉字画成同一个"时要靠分类。"""
    import charset as cs

    return cs.build_charset()


def screen(
    ours: dict[int, np.ndarray],
    refs_by_name: dict[str, dict[int, np.ndarray]],
    alt_holes: dict[int, int] | None = None,
) -> dict:
    """与指标无关的硬检查 + 结构离群筛查。

    alt_holes: 可选的"备选源"字腔数 (码位 -> 字腔数)。用于区分
        「换个源就能救回来」和「12px 网格下谁都救不回来」——
        前者是缺陷, 后者是网格的固有极限, 不该混在同一个告警列表里。
    """
    findings: list[dict] = []
    coverage: dict[str, list[int]] = {}

    for name, refs in refs_by_name.items():
        missing = sorted(cp for cp in ours if cp not in refs)
        coverage[name] = [f"U+{c:04X}" for c in missing]
        # 位图完全相同 (同一分辨率下才有意义)
        index: dict[tuple, list[int]] = defaultdict(list)
        for cp, arr in refs.items():
            index[(arr.shape[0], arr.shape[1], arr.tobytes())].append(cp)
        for cp, arr in ours.items():
            others = [c for c in index.get((arr.shape[0], arr.shape[1], arr.tobytes()), []) if c != cp]
            if others:
                # 严重度: 撞上的那个码位**在不在我们的字符集里**。
                #   不在 -> 那是 Unicode 里的同形异义码位 (组合记号之间、带圈点与句点
                #           的不同码位), 12px 下必然画成一样, 我们也没渲染它,
                #           不影响我们的任何输出 -> 只记录 (warn)。
                #   在   -> 我们确实把两个码位画成了同一个, 可能真出错了 (error);
                #           但更常见的成因是标点本就该同形 (如 ' 与 ,), 所以
                #           真正的"我方撞车"由下面 OWN_COLLIDE 单独判。
                in_set = [c for c in others if c in ours]
                findings.append(
                    {
                        "id": "EXACT_COLLIDE",
                        "severity": "error" if in_set else "warn",
                        "ref": name,
                        "cp": f"U+{cp:04X}",
                        "char": chr(cp),
                        "detail": "与参考字体的 "
                        + ", ".join(f"U+{c:04X} {chr(c)!r}" for c in others[:4])
                        + " 逐像素完全相同"
                        + (
                            " —— 该码位不在我们的字符集里, 属同形异义码位, 不影响输出"
                            if not in_set
                            else " —— 该码位也在我们的字符集里, 见 OWN_COLLIDE"
                        ),
                    }
                )

    # ---- OWN_COLLIDE: 我们自己把两个码位画成了同一个 ----
    #
    # 这才是"身份错误"该有的判据: 与参考的撞车可能只是 Unicode 的同形异义码位,
    # 但**我们自己的**两个码位画成同一个, 意味着其中一个字被画错了。
    # 实测: 标点里有一批天然同形 ( ' 与 , 、 . 与 · ), 汉字里出现即为硬错误。
    own_index: dict[tuple, list[int]] = defaultdict(list)
    for cp, arr in ours.items():
        own_index[(arr.shape[0], arr.shape[1], arr.tobytes())].append(cp)
    cat_of: dict[int, str] = {}
    for ch, cat in cat_of_chars():
        cat_of[ord(ch)] = cat
    for _key, cps in own_index.items():
        if len(cps) < 2:
            continue
        for a, b in zip(cps, cps[1:]):
            pair_cats = {cat_of.get(a, "?"), cat_of.get(b, "?")}
            hanzi = pair_cats == {"hanzi"}
            findings.append(
                {
                    "id": "OWN_COLLIDE",
                    "severity": "error" if hanzi else "warn",
                    "ref": "ours",
                    "cp": f"U+{a:04X}",
                    "char": chr(a),
                    "detail": f"我方 U+{a:04X} {chr(a)!r} 与 U+{b:04X} {chr(b)!r} "
                    f"渲染成完全相同的位图"
                    + (
                        " —— 两个汉字画成同一个, 是身份错误"
                        if hanzi
                        else " —— 标点/符号天然同形, 12px 下必然一致"
                    ),
                }
            )

    # ---- COUNTER_LOST: 参考有字腔, 我们一个都没有 (跨参考取共识) ----
    # 只在 >=2 套参考都说"该有腔"时才报 —— 单套参考的判断可能只是画风差异。
    our_holes = {cp: holes(a) for cp, a in ours.items()}
    ref_holes: dict[str, dict[int, int]] = {
        name: {cp: holes(a) for cp, a in refs.items()} for name, refs in refs_by_name.items()
    }
    ref_names = list(refs_by_name)
    counter_lost = []
    for cp in ours:
        if our_holes[cp] != 0:
            continue
        votes = []
        for name in ref_names:
            h = ref_holes[name].get(cp)
            if h is not None:
                votes.append((name, h))
        if len(votes) < 2:
            continue
        say_has = [n for n, h in votes if h > 0]
        if len(say_has) < 2:
            continue
        counter_lost.append((cp, votes))
    for cp, votes in counter_lost:
        alt = (alt_holes or {}).get(cp)
        # 严重度按**独立参考的中位腔数**分档:
        #   中位 >= 2  -> 结构性白块 (字里有日/目/田 这类必须封闭的部件),
        #                  我方 0 腔 = 整字塌了, 是硬错误 (error)
        #   中位 == 1  -> 1 像素级的边缘差异。实测这一档全都不是缺陷:
        #                  逐字出图目视复核过 (埃/驰/邓/饿/颈/涟/氢/趋/疡/幼/舆/狱/制),
        #                  汉字全部清晰可辨, 差别只是一个封闭空间的取舍
        #                  (Zpix 把「舆」的「田」闭上了, 我们没闭) —— 12px 的边缘差异
        #
        # 为什么用中位而不是取最大: Unifont 是 16px, 天然有更多封闭空间
        # (实测它与 12px 参考的结构距离均值 28), 取最大会把
        # "Unifont 说 2 腔、Zpix 说 1 腔" 误判成结构性白块。
        ref_med = float(np.median([h for _n, h in votes]))
        if ref_med >= 2:
            sev = "error"
        else:
            sev = "warn"
        if alt is None:
            extra = " (该码位无备选源)"
        elif alt > 0:
            extra = f", 备选源可救回 (字腔 {alt})"
        else:
            extra = ", 备选源同样无腔 —— 12px 网格的固有极限"
        findings.append(
            {
                "id": "COUNTER_LOST",
                "severity": sev,
                "ref": "+".join(n.split("-")[0] for n, h in votes if h > 0),
                "cp": f"U+{cp:04X}",
                "char": chr(cp),
                "detail": "我方字腔数 0, 但参考字体的字腔数为 "
                + ", ".join(f"{n.split('-')[0]}:{h}" for n, h in votes)
                + (
                    " —— 字腔被笔画填死 (该字在我们这儿渲染成白块)"
                    if sev == "error"
                    else " —— 参考中位腔数只有 1, 属 12px 下的边缘取舍, 非结构性白块"
                )
                + extra,
            }
        )

    # ---- STRUCTURE_OUTLIER: 横/竖笔画数与参考差得离谱 ----
    #
    # 为什么用**绝对阈值**而不是 z-score:
    #   z-score 的尺度 (MAD) 会随总体分布集中而收紧。字体变好 -> 分布变集中 ->
    #   MAD 变小 -> 同样 6 倍标准差对应的**绝对**偏差门槛跟着收紧 ->
    #   离群数不降反升。实测: 换成逐字选源后, 绝对阈值 |差|>=12 的汉字从 204 降到 63,
    #   而 z-score 判据的命中数却从 17 涨到 151 —— 那是量具在骗人, 不是字体变差。
    #   跨版本比较必须用绝对量, 所以这里固定阈值 12。
    #   12 的来由: 被填死的字比参考少 20 多个竖笔分段 (量 -28 / 舅 -24 / 暴 -22),
    #   正常字只差 1-3 个; 12 落在两者之间, 且覆盖全部已确认的塌陷字。
    STROKE_DELTA_THRESHOLD = 12
    for name, refs in refs_by_name.items():
        if name == "unifont-16":
            continue  # 16px 基准与 12px 的笔画数天然不同, 不参与离群判定
        d_row, d_col = [], []
        for cp, a in ours.items():
            b = refs.get(cp)
            if b is None:
                continue
            d_row.append((cp, row_runs(a) - row_runs(b)))
            d_col.append((cp, col_runs(a) - col_runs(b)))
        for label, arr in (("横笔画数", d_row), ("竖笔画数", d_col)):
            if not arr:
                continue
            for cp, v in arr:
                if abs(v) >= STROKE_DELTA_THRESHOLD:
                    findings.append(
                        {
                            "id": "STRUCTURE_OUTLIER",
                            "severity": "warn",
                            "ref": name,
                            "cp": f"U+{cp:04X}",
                            "char": chr(cp),
                            "detail": f"{label}与参考相差 {v:+.0f} (绝对阈值 {STROKE_DELTA_THRESHOLD})",
                        }
                    )

    # ---- STYLE_DIFF: 墨量差异 —— 只记录, 不下判定 (见模块 docstring 的实测结论) ----
    style = []
    for name, refs in refs_by_name.items():
        for cp, a in ours.items():
            b = refs.get(cp)
            if b is None:
                continue
            ia, ib = int(a.sum()), int(b.sum())
            if ia == 0 or ib == 0:
                continue
            rel = (ia - ib) / max(ia, ib)
            if abs(rel) >= 0.5:
                style.append(
                    {
                        "ref": name,
                        "cp": f"U+{cp:04X}",
                        "char": chr(cp),
                        "rel": rel,
                        "ink_ours": ia,
                        "ink_ref": ib,
                    }
                )
    return {
        "findings": findings,
        "coverage": coverage,
        "style_diffs": style,
        "counter_holes": {
            "ours_mean": round(float(np.mean(list(our_holes.values()))), 3) if our_holes else 0.0,
            "ref_mean": {
                n: round(float(np.mean(list(ref_holes[n].values()))), 3)
                for n in ref_names
                if ref_holes[n]
            },
            "counter_lost_count": len(counter_lost),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="生成字形对照表 (开源像素字体做目视比对尺子)")
    ap.add_argument(
        "--refs",
        default="zpix,unifont-16",
        help="参考字体, 逗号分隔。默认用**与生产源独立**的两套: Zpix (MIT) + Unifont (GPL)。"
        "不要用 ark-pixel-zh_hans —— Ark 现在是生产源, 拿它当基准等于自己和自己比",
    )
    ap.add_argument("--cats", default="", help="类别: ascii,punct,kana,hanzi")
    ap.add_argument("--slice", dest="slice_", default="", help="切片 如 0:150")
    ap.add_argument("--out", default="", help="对照表输出路径 (md); --screen-only 时不需要")
    ap.add_argument("--json", default="", help="自动化检查结果输出路径")
    ap.add_argument("--label", default="")
    ap.add_argument("--screen-only", action="store_true", help="只跑自动化硬检查, 不生成对照表")
    args = ap.parse_args()

    out = Path(args.out)
    if not args.screen_only and not args.out:
        print("需要 --out (对照表输出路径); 只跑硬检查请加 --screen-only", file=sys.stderr)
        return 2
    if not args.screen_only:
        out.parent.mkdir(parents=True, exist_ok=True)

    items = cs.build_charset()
    stack = cs.build_stack()
    cats = [c.strip() for c in args.cats.split(",") if c.strip()]
    sel = [(ch, cat) for ch, cat in items if (not cats or cat in cats)]
    if args.slice_:
        a, _, b = args.slice_.partition(":")
        sel = sel[int(a) if a else 0 : int(b) if b else len(sel)]
    if not sel:
        print("选择为空 —— 没有可测字符", file=sys.stderr)
        return 2

    ref_names = [r.strip() for r in args.refs.split(",") if r.strip()]
    refs_by_name: dict[str, dict[int, np.ndarray]] = {}
    for name in ref_names:
        if name not in vi.REFS:
            print(f"未知参考字体 {name}", file=sys.stderr)
            return 2
        meta = vi.REFS[name]
        p = vi.REFDIR / meta["path"]
        if not p.exists():
            print(f"参考字体缺失: {p}", file=sys.stderr)
            return 2
        from fontTools.ttLib import TTFont

        tt = TTFont(str(p), fontNumber=0)
        refs_by_name[name], fails = vi.ref_glyphs(p, meta["ppem"], sorted(tt.getBestCmap().keys()))
        print(f"参考字体 {name}: {len(refs_by_name[name])} 个字形 (读取失败 {fails})")

    ours = vi.our_glyphs(stack, sel)
    # 备选源 (非汉字源, 即 MS Gothic) 能救回多少个丢腔的字 ——
    # 用来把"换个源就能修"和"12px 网格的固有极限"分开。
    # 必须查 cmap: 缺字时 FreeType 画 .notdef (空心矩形豆腐块), 它自带 1 个"字腔",
    # 会把根本没有这个字的码位也误判成"能救回"。
    from coverage import cmap_for

    non_ideo_cps = cmap_for(stack.non_ideo.path, stack.non_ideo.index)
    alt_holes: dict[int, int] = {}
    for ch, _cat in sel:
        cp = ord(ch)
        if stack._pick(ch) is not stack.ideo:
            continue
        if cp not in non_ideo_cps:
            continue
        alt_holes[cp] = holes_of_glyph(stack.non_ideo.glyph(ch))
    scr = screen(ours, refs_by_name, alt_holes)
    by_cp: dict[str, list[dict]] = defaultdict(list)
    for f in scr["findings"]:
        by_cp[f["cp"]].append(f)

    if args.screen_only:
        if args.json:
            jp = Path(args.json)
            jp.parent.mkdir(parents=True, exist_ok=True)
            jp.write_text(
                json.dumps(
                    {
                        "tool": "compare_refs_screen",
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "selection": {"cats": cats or ["<all>"], "slice": args.slice_, "label": args.label},
                        "inputs": {
                            "chars_selected": len(sel),
                            "ours_glyphs": len(ours),
                            "refs": {n: len(refs_by_name[n]) for n in ref_names},
                        },
                        "findings": scr["findings"],
                        "coverage": scr["coverage"],
                        "counter_holes": scr["counter_holes"],
                        "style_diffs": scr["style_diffs"],
                        "summary": {
                            "findings": len(scr["findings"]),
                            "by_id": dict(Counter(f["id"] for f in scr["findings"])),
                            "by_severity": dict(Counter(f.get("severity", "?") for f in scr["findings"])),
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        print(f"硬检查: 覆盖 {len(sel)} 字符, 命中 {len(scr['findings'])} 条")
        for aid, n in Counter(f["id"] for f in scr["findings"]).most_common():
            print(f"   {aid}: {n}")
        for name, miss in scr["coverage"].items():
            print(f"   覆盖缺口 {name}: {len(miss)}")
        print(f"   字腔: 我方均值 {scr['counter_holes']['ours_mean']}  参考 {scr['counter_holes']['ref_mean']}")
        return 0

    L = [
        f"# 字形对照表 — {args.label or ','.join(cats) or 'all'}",
        "",
        f"- 生成时间: {datetime.now(timezone.utc).isoformat()}",
        f"- 覆盖: {len(sel)} 个字符 (我方有字形 {len(ours)} 个)",
        f"- 参考字体: {', '.join(f'{n} ({vi.REFS[n]['license']}, {vi.REFS[n]['ppem']}px)' for n in ref_names)}",
        f"- 自动化硬检查命中: {len(scr['findings'])} 条 (见文末清单)",
        f"- 字腔数均值: 我方 {scr['counter_holes']['ours_mean']} / "
        + " / ".join(f"{k} {v}" for k, v in scr["counter_holes"]["ref_mean"].items()),
        "",
        "核对方法: 每一段左边是我方 12px 点阵, 右边是各参考字体的同一字符。"
        "**若我方那一列画的不是这个字, 就是缺陷** —— 参考字体的同字骨架是可辨认的。",
        "",
    ]
    for ch, cat in sel:
        cp = ord(ch)
        a = ours.get(cp)
        if a is None:
            L += [f"### U+{cp:04X} {ch!r} ({cat})", "", "**我方无字形 (空白)**", ""]
            continue
        refs = [(n, refs_by_name[n].get(cp)) for n in ref_names]
        L += [f"### U+{cp:04X} {ch!r} ({cat})", ""]
        L += ["```"]
        L += side_by_side_blocks(a, refs)
        L += ["```", ""]
        for f in by_cp.get(f"U+{cp:04X}", []):
            L.append(f"> ⚠ {f['ref']}: {f['detail']}")
        if by_cp.get(f"U+{cp:04X}"):
            L.append("")

    L += ["## 自动化硬检查清单", ""]
    if not scr["findings"]:
        L.append("(无)")
    else:
        L += ["| 检查 | 级别 | 参考字体 | 码位 | 字符 | 说明 |", "|---|---|---|---|---|---|"]
        for f in scr["findings"][:200]:
            L.append(
                f"| `{f['id']}` | {f.get('severity','-')} | {f['ref']} | {f['cp']} | {f.get('char','')} | {f['detail']} |"
            )
    L += ["", "## 覆盖率缺口 (参考字体没有这个码位)", ""]
    for name, miss in scr["coverage"].items():
        L.append(f"- **{name}**: 缺 {len(miss)} 个 {' '.join(miss[:40])}")
    L += ["", f"## 墨量差异 (仅记录, 不作判定 —— 实测该指标对身份无分辨力)", ""]
    if not scr["style_diffs"]:
        L.append("(无)")
    else:
        L += ["| 参考字体 | 码位 | 字符 | 相对差 | 我方墨量 | 参考墨量 |", "|---|---|---|---|---|---|"]
        for s in scr["style_diffs"][:200]:
            L.append(
                f"| {s['ref']} | {s['cp']} | {s.get('char','')} | {s['rel']:+.2f} | {s['ink_ours']} | {s['ink_ref']} |"
            )
    L.append("")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")

    if args.json:
        jp = Path(args.json)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(
            json.dumps(
                {
                    "tool": "compare_refs",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "selection": {"cats": cats or ["<all>"], "slice": args.slice_, "label": args.label},
                    "inputs": {
                        "chars_selected": len(sel),
                        "ours_glyphs": len(ours),
                        "refs": {n: len(refs_by_name[n]) for n in ref_names},
                    },
                    "findings": scr["findings"],
                    "coverage": scr["coverage"],
                    "counter_holes": scr["counter_holes"],
                    "style_diffs": scr["style_diffs"],
                    "summary": {
                        "findings": len(scr["findings"]),
                        "by_id": dict(Counter(f["id"] for f in scr["findings"])),
                        "by_severity": dict(Counter(f.get("severity", "?") for f in scr["findings"])),
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    print(f"对照表: {out}  ({len(sel)} 字符, 硬检查 {len(scr['findings'])} 条)")
    for aid, n in Counter(f["id"] for f in scr["findings"]).most_common():
        print(f"   {aid}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
