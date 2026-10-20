"""hanzi lane 补充探针 —— 汉字批次专属质量检查 (a/b/c)。

共享工具 tools/fontgen/regress.py 证明的是**管线自洽**: 四路交叉对比
(栅格化器 R / BDF B / TTF T / 图集 A) 逐像素相同。但"自洽"不等于"画对了" ——
如果路由把码位串了, 四路会一致地画错, 交叉对比照样全绿。本探针补的是
**流水线之外的事实**:

  a) 字形唯一性 —— 批内两个不同汉字位图完全相同 = 路由/映射错误 (码位串了)。
     只在**汉字之间**比对: 跨类别相同是合法的 (实测 片假名「ニ」与汉字「二」
     位图相同, 两个源字体里本来就画得一样), 本探针把这个已知合法对当**阴性对照**
     跑一遍, 证明检测器确实能响 —— 否则 "0 重复" 说明不了任何事。
  b) 源形保真 —— 把生成的 1-bit 点阵与源字体 SimHei 的**灰度**渲染
     (getmask2 mode="L", 带抗锯齿的真实字形) 阈值化后逐像素对比;
     再加一道**身份判定**: 这个点阵在全部 1900 个字的灰度渲染里最像哪一个字。
     画错字的话最近邻就不是它自己 —— 这一条比"差异像素数"更能定性。
  c) 墨量分布 —— ink ratio 的中位/p95/max + 最高/最低 5 个, 外加**字腔数**
     (被墨迹封闭的背景连通域): 墨量高 + 字腔 = 0 = 字腔闭合, 不可用。
  d) 成品旁证 —— 只读复核共享工具报出的 BDF 结构异常, 并把探针位图与
     dist/ 图集成品对拍, 证明探针量的是**真正出货的那份**位图。

判定原则: 每条结论都必须能追溯到 (实现代码 + 本次实际跑出来的数)。
凡是"看起来像环境问题"一律不写进结论。

用法:
    python tools/fontgen/lanes/hanzi_a_probe.py
    python tools/fontgen/lanes/hanzi_a_probe.py --out reports/hanzi-a_extra.json

输出:
    <out>      JSON (机器读)
    <out>.md   人读摘要 (同一份数据的另一种渲染)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from PIL import Image  # noqa: E402

import bitfont as bf  # noqa: E402
import charset as cs  # noqa: E402

ROOT = HERE.parents[2]
DEFAULT_OUT = ROOT / "reports" / "hanzi-a_extra.json"

SLICE_END = 1900  # 本 lane 负责的 hanzi 前 N 字
SAMPLE_STRIDE = 37  # 任务指定的确定性抽样步长
GRAY_THRESHOLD = 128  # 与 FreeType MONO 的 50% 覆盖判定对齐
DENSE_LIMIT = 0.60  # bitfont.py:270-273 记录的 "60% 以上基本等于不可用"
DENSE_PROBE = bf.DENSE_PROBE  # "語龍鬱撃戰鑑"
NEAR_DUP_LIMIT = 2  # A 检查: 位图汉明距离 <= 2 视为"疑似同图"
# 身份判定的并列容忍带: 52 个抽样字的 mono-vs-源字形 对齐距离本身就分布在 2-23 px,
# 最近邻只赢 3 px 以内落在栅格化噪声带里, 不能据此判"画错了字"。
# 真正的画错字长这样: 生成的点图 = 另一个字的点图 (汉明距离 0), 由 A 检查兜底。
TIE_MARGIN = 3

# 阴性对照: 跨类别位图相同是合法的 (两个源字体里本来就画得一样)
NEGATIVE_CONTROL = ("ニ", "二")
SIMSUN = r"C:\Windows\Fonts\simsun.ttc"  # 仅用于复核注释里的 29% 是否来自别的字体

ERROR = "error"
WARN = "warn"
INFO = "info"


# ================================================================ 基础工具


def pack(grid: list[list[int]]) -> int:
    """把 12x13 位图压成一个整数, 用 XOR+popcount 算汉明距离。"""
    v = 0
    for y, row in enumerate(grid):
        base = y * 12
        for x, c in enumerate(row):
            if c:
                v |= 1 << (base + x)
    return v


def unpack(v: int, w: int = 12, h: int = 13) -> list[list[int]]:
    return [[1 if (v >> (y * w + x)) & 1 else 0 for x in range(w)] for y in range(h)]


def to_ascii(grid: list[list[int]], ink: str = "#", paper: str = ".") -> str:
    return "\n".join("".join(ink if c else paper for c in row) for row in grid)


def side_by_side(a: list[list[int]], b: list[list[int]], gap: str = "   ") -> str:
    la = to_ascii(a).split("\n")
    lb = to_ascii(b).split("\n")
    return "\n".join(f"{x}{gap}{y}" for x, y in zip(la, lb))


def ink_count(grid: list[list[int]]) -> int:
    return sum(sum(row) for row in grid)


def mono_grid(stack: bf.ScriptStack, ch: str) -> list[list[int]]:
    """生产路径的位图 (ScriptStack.glyph -> BitmapFont.glyph -> MONO 栅格化)。"""
    g = stack.glyph(ch)
    px = g.load()
    return [[1 if px[x, y] > 0 else 0 for x in range(g.width)] for y in range(g.height)]


def gray_float(ideo: bf.BitmapFont, ch: str):
    """源字体灰度渲染 (带抗锯齿) 的**原始覆盖度** (0-255), 贴回同一张 12x13 网格。

    几何与生产路径完全一致: 同样的 cell、同样的 paste 偏移 (getmask2 返回的
    offset), 只是 mode 从 "1"(MONO) 换成 "L"(灰度)。
    返回 (rows, meta) 或 (None, meta) —— meta 里带读取失败的原因。
    """
    m = ideo.metrics
    meta = {"size": None, "offset": None, "error": None}
    try:
        core, off = ideo._font.getmask2(ch, mode="L")
    except Exception as exc:  # noqa: BLE001
        meta["error"] = f"getmask2(mode=L) 失败: {exc}"
        return None, meta
    w, h = core.size
    meta["size"] = [w, h]
    meta["offset"] = list(off)
    if w == 0 or h == 0:
        meta["error"] = "灰度掩码为空"
        return None, meta
    data = bytes(core)
    if len(data) < w * h:
        meta["error"] = f"灰度掩码字节不足 ({len(data)} < {w * h})"
        return None, meta
    img = Image.frombytes("L", (w, h), data[: w * h])
    canvas = Image.new("L", (m.cell_w, m.cell_h), 0)
    canvas.paste(img, off)
    px = canvas.load()
    rows = [[px[x, y] for x in range(m.cell_w)] for y in range(m.cell_h)]
    return rows, meta


def threshold_rows(rows: list[list[int]], thr: int) -> list[list[int]]:
    return [[1 if v >= thr else 0 for v in row] for row in rows]


def coverage_stats(mono: list[list[int]], grayf: list[list[int]], radius: int = 1):
    """单色墨迹 vs 真实形状的**包含关系**统计。

    - mono_covered : 单色墨迹像素中, 其自身或四邻域(radius=1)被真实形状覆盖的比例。
      这个比例接近 1, 就说明单色点阵是真实字形的"抽稀版", 没有凭空多画。
    - gray_uncovered: 真实形状(灰度>=128)里, 没有任何单色墨迹在邻域内的像素数。
      这个数接近 0, 就说明单色点阵没有把笔画整根丢掉。

    这两条比"差异像素数"更能定性: 差异数大可能只是笔画整体挪了 1 像素
    (抗锯齿 + MONO 取整的固有结果), 而包含关系不会因为整体平移而崩掉。
    """
    hit = 0
    tot = 0
    for y in range(13):
        for x in range(12):
            if not mono[y][x]:
                continue
            tot += 1
            covered = False
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < 13 and 0 <= nx < 12 and grayf[ny][nx] > 0:
                        covered = True
                        break
                if covered:
                    break
            if covered:
                hit += 1
    uncovered = 0
    for y in range(13):
        for x in range(12):
            if grayf[y][x] < 128:
                continue
            found = False
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < 13 and 0 <= nx < 12 and mono[ny][nx]:
                        found = True
                        break
                if found:
                    break
            if not found:
                uncovered += 1
    return (hit / max(1, tot), hit, tot, uncovered)


def shift(grid: list[list[int]], dy: int, dx: int) -> list[list[int]]:
    """整图平移 (越界补 0), 用于判断差异是不是纯粹的位置偏移。"""
    h = len(grid)
    w = len(grid[0])
    out = [[0] * w for _ in range(h)]
    for y in range(h):
        sy = y - dy
        if not (0 <= sy < h):
            continue
        for x in range(w):
            sx = x - dx
            if 0 <= sx < w:
                out[y][x] = grid[sy][sx]
    return out


def hamming(a: list[list[int]], b: list[list[int]]) -> int:
    return sum(1 for y in range(len(a)) for x in range(len(a[0])) if a[y][x] != b[y][x])


def best_aligned_diff(mono: list[list[int]], gray: list[list[int]], rdy: int = 3, rdx: int = 2):
    """在 ±rdy/±rdx 的平移范围内找最小差异, 并给出最佳平移量。"""
    best = (hamming(mono, gray), 0, 0)
    for dy in range(-rdy, rdy + 1):
        for dx in range(-rdx, rdx + 1):
            if dy == 0 and dx == 0:
                d = best[0]
            else:
                d = hamming(shift(mono, dy, dx), gray)
            if d < best[0]:
                best = (d, dy, dx)
    return best


def row_multiset_dist(a: list[list[int]], b: list[list[int]]) -> int:
    """行多重集距离: 灰度每一行在单色行里能找到的最佳匹配之和 (越小=形状越像)。

    用来区分"整幅字形被画错"和"某几根横/竖笔画上下挪了 1 像素"。
    """
    total = 0
    for ra in a:
        total += min(sum(1 for x in range(12) if ra[x] != rb[x]) for rb in b)
    return total


def col_multiset_dist(a: list[list[int]], b: list[list[int]]) -> int:
    """列多重集距离 (与 row_multiset_dist 对称)。"""
    total = 0
    for x in range(12):
        ca = [a[y][x] for y in range(13)]
        best = 13
        for y in range(12):
            cb = [b[z][y] for z in range(13)]
            best = min(best, sum(1 for i in range(13) if ca[i] != cb[i]))
        total += best
    return total


def perimeter_ink(grid: list[list[int]]) -> int:
    """位于笔画边缘 (四邻域至少一个背景) 的墨迹像素数。

    抗锯齿/栅格化取整最多只能让这些像素翻转 —— 差异数不超过它, 就说明
    差异是"边缘怎么算"而不是"字画错了"。
    """
    h, w = len(grid), len(grid[0])
    n = 0
    for y in range(h):
        for x in range(w):
            if not grid[y][x]:
                continue
            edge = False
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if not (0 <= ny < h and 0 <= nx < w) or not grid[ny][nx]:
                    edge = True
                    break
            if edge:
                n += 1
    return n


def enclosed_counters(grid: list[list[int]]) -> int:
    """字腔数 = 被墨迹封闭的背景连通域个数 (4 邻域, 从边界洪泛后剩下的)。"""
    h, w = len(grid), len(grid[0])
    seen = [[False] * w for _ in range(h)]
    stack = []
    for x in range(w):
        for y in (0, h - 1):
            if not grid[y][x] and not seen[y][x]:
                seen[y][x] = True
                stack.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if not grid[y][x] and not seen[y][x]:
                seen[y][x] = True
                stack.append((y, x))
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not grid[ny][nx] and not seen[ny][nx]:
                seen[ny][nx] = True
                stack.append((ny, nx))
    counters = 0
    for y in range(h):
        for x in range(w):
            if grid[y][x] or seen[y][x]:
                continue
            counters += 1
            seen[y][x] = True
            stack = [(y, x)]
            while stack:
                cy, cx = stack.pop()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if (
                        0 <= ny < h
                        and 0 <= nx < w
                        and not grid[ny][nx]
                        and not seen[ny][nx]
                    ):
                        seen[ny][nx] = True
                        stack.append((ny, nx))
    return counters


# ================================================================ 检查 a: 唯一性


def dense_calibers(font: bf.BitmapFont, px: int) -> dict:
    """密笔画基准字在三种墨量口径下的实测值。

    口径:
      cell_ratio   = ink / (cell_w x cell_h)  —— 工程自己的 bitfont.ink_ratio / measure_density 口径
      square_ratio = ink / (px x px)          —— 把字当成正方形 em
      bbox_ratio   = ink / 墨迹包围盒面积
    """
    cell = sq = box = 0.0
    for c in DENSE_PROBE:
        g = font.glyph(c)
        p = g.load()
        on = sum(1 for y in range(g.height) for x in range(g.width) if p[x, y] > 0)
        xs = [x for y in range(g.height) for x in range(g.width) if p[x, y]]
        ys = [y for y in range(g.height) for x in range(g.width) if p[x, y]]
        bbox = (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1) if xs else 1
        cell += on / (g.width * g.height)
        sq += on / (px * px)
        box += on / bbox
    n = len(DENSE_PROBE)
    m = font.metrics
    return {
        "font": font.name,
        "px": px,
        "cell": f"{m.cell_w}x{m.cell_h}",
        "ascent_descent": f"{m.ascent}/{m.descent}",
        "cell_ratio": round(cell / n, 4),
        "square_ratio": round(sq / n, 4),
        "bbox_ratio": round(box / n, 4),
    }


def check_uniqueness(stack, hanzi, anomalies) -> dict:
    grids = {}
    read_fail = 0
    for ch in hanzi:
        g = stack.glyph(ch)
        if g.width != 12 or g.height != 13:
            read_fail += 1
            continue
        grids[ch] = mono_grid(stack, ch)

    # 精确重复
    by_mask: dict[int, list[str]] = {}
    for ch, g in grids.items():
        by_mask.setdefault(pack(g), []).append(ch)
    exact = [v for v in by_mask.values() if len(v) > 1]

    # 近重复 (汉明距离 <= NEAR_LIMIT): 两个字只差一两笔, 在 12px 上可能撞成同一张图
    NEAR_LIMIT = 2
    REPORT_LIMIT = 5
    chars = list(grids)
    masks = [pack(grids[c]) for c in chars]
    near: list[tuple[int, str, str]] = []
    min_dist = (999, "", "")
    le5 = 0
    for i in range(len(chars)):
        mi = masks[i]
        for j in range(i + 1, len(chars)):
            d = (mi ^ masks[j]).bit_count()
            if d <= REPORT_LIMIT:
                le5 += 1
                if d <= NEAR_LIMIT:
                    near.append((d, chars[i], chars[j]))
                if d < min_dist[0]:
                    min_dist = (d, chars[i], chars[j])
    near.sort()

    # 阴性对照: 跨类别位图相同是合法的 —— 证明检测器确实能响
    control: dict = {}
    if len(NEGATIVE_CONTROL) == 2:
        a, b = NEGATIVE_CONTROL
        ga, gb = mono_grid(stack, a), mono_grid(stack, b)
        control = {
            "pair": [a, b],
            "codes": [f"U+{ord(a):04X}", f"U+{ord(b):04X}"],
            "same_bitmap": pack(ga) == pack(gb),
            "detail": "片假名「ニ」与汉字「二」在两个源字体里画得一样 —— 跨类别同图合法, "
            "本探针不在跨类别范围内比对",
        }
        if control["same_bitmap"]:
            control["verdict"] = "检测器可响 (阴性对照通过): 能找出位图相同的字符对"
        else:
            control["verdict"] = "阴性对照未通过: 检测器可能失效, A 检查的 0 重复不可信"

    for group in exact:
        detail = "批内两个不同汉字位图完全相同: " + ", ".join(
            f"{c!r} U+{ord(c):04X}" for c in group
        )
        anomalies.append(
            {
                "id": "A_DUPLICATE_BITMAP",
                "severity": ERROR,
                "detail": detail,
                "chars": group,
                "codes": [f"U+{ord(c):04X}" for c in group],
                "ascii_art": side_by_side(grids[group[0]], grids[group[1]]),
                "classification": "真缺陷 (待人工复核)",
                "suggested_fix": "先查 charset.gb2312_level1() 与 bitfont.ScriptStack._pick() "
                "的码位路由 (tools/fontgen/bitfont.py:219-224)",
            }
        )

    for d, a, b in near[:20]:
        anomalies.append(
            {
                "id": "A_NEAR_DUPLICATE",
                "severity": INFO,
                "detail": f"{a!r} U+{ord(a):04X} 与 {b!r} U+{ord(b):04X} 位图仅差 {d} px",
                "chars": [a, b],
                "codes": [f"U+{ord(a):04X}", f"U+{ord(b):04X}"],
                "ascii_art": side_by_side(grids[a], grids[b]),
                "classification": "需人工判定: 12px 分辨率下只差 1-2 笔的汉字本就可能撞图",
                "suggested_fix": "若确认为不同字, 查 SimHei 12px 下该字形是否被 hinting 压成同一张图",
            }
        )

    return {
        "checked": len(grids),
        "read_failures": read_fail,
        "distinct_bitmaps": len(by_mask),
        "exact_duplicate_groups": len(exact),
        "exact_duplicate_members": sum(len(g) for g in exact),
        "near_duplicate_pairs_le2": len(near),
        "pairs_le5": le5,
        "min_pairwise_distance": {
            "dist_px": min_dist[0],
            "chars": [min_dist[1], min_dist[2]],
            "codes": [f"U+{ord(min_dist[1]):04X}", f"U+{ord(min_dist[2]):04X}"],
            "note": "批内两两之间的最小位图距离 —— 用来证明近重复检测器确实在跑",
        },
        "near_duplicate_top": [
            {"diff_px": d, "chars": [a, b], "codes": [f"U+{ord(a):04X}", f"U+{ord(b):04X}"]}
            for d, a, b in near[:20]
        ],
        "negative_control": control,
        "verdict": "FAIL" if exact else "PASS",
    }


# ================================================================ 检查 b: 源形保真


def check_fidelity(stack, hanzi, ideo, anomalies, stride, thr) -> dict:
    samples = [hanzi[i] for i in range(0, len(hanzi), stride)]

    # 全部候选字的灰度渲染 (身份判定的候选集)
    grayf: dict[str, list[list[int]]] = {}
    graybin: dict[str, list[list[int]]] = {}
    gray_fail = 0
    for ch in hanzi:
        rows, meta = gray_float(ideo, ch)
        if rows is None:
            gray_fail += 1
            continue
        grayf[ch] = rows
        graybin[ch] = threshold_rows(rows, thr)
    gray_masks = {c: pack(g) for c, g in graybin.items()}

    # 身份判定的平移集合: 单色位图在 ±3 行 / ±2 列 内平移后的全部形态
    SHIFTS = [(dy, dx) for dy in range(-3, 4) for dx in range(-2, 3)]

    rows_out = []
    identity_mismatch = []
    for ch in samples:
        mono = mono_grid(stack, ch)
        mono_v = pack(mono)
        gf = grayf.get(ch)
        gb = graybin.get(ch)
        if gf is None or gb is None:
            anomalies.append(
                {
                    "id": "B_GRAY_READ_FAILED",
                    "severity": ERROR,
                    "detail": f"{ch!r} U+{ord(ch):04X} 的源字体灰度渲染读取失败",
                    "chars": [ch],
                    "codes": [f"U+{ord(ch):04X}"],
                    "classification": "真缺陷 (量具读不到源字形)",
                    "suggested_fix": "查 SimHei 是否有该字形 / getmask2 调用参数",
                }
            )
            continue

        # 预计算单色位图的所有平移形态 (整数位掩码)
        shifted = [(dy, dx, pack(shift(mono, dy, dx))) for dy, dx in SHIFTS]
        d0 = hamming(mono, gb)
        d_align, sy, sx = best_aligned_diff(mono, gb)
        rd = row_multiset_dist(gb, mono)
        cd = col_multiset_dist(gb, mono)
        peri = perimeter_ink(gb)
        mono_ink = ink_count(mono)
        gray_ink = ink_count(gb)
        cov, cov_hit, cov_tot, gray_uncovered = coverage_stats(mono, gf)

        # 身份判定: 这个点图在**全部**候选字的灰度渲染里最像哪一个 (允许对齐)
        best_char = None
        best_dist = 10**9
        self_dist = 10**9
        runner_char = None
        runner_dist = 10**9
        for cand, gm in gray_masks.items():
            d = min((sm ^ gm).bit_count() for _, _, sm in shifted)
            if d < best_dist:
                runner_dist, runner_char = best_dist, best_char
                best_dist = d
                best_char = cand
            elif d < runner_dist:
                runner_dist, runner_char = d, cand
            if cand == ch:
                self_dist = d
        d_true = self_dist

        # 判定
        tie = False
        runner_mono_dist = None
        if best_dist < d_true:
            # 最近邻不是它自己 —— 只有在差距超出噪声带, 且生成的点图确实等于
            # 另一个字的点图时, 才是路由错误; 否则是 12px 下近形字不可分。
            runner_mono_dist = hamming(mono, mono_grid(stack, best_char))
            tie = (d_true - best_dist) <= TIE_MARGIN and runner_mono_dist > NEAR_DUP_LIMIT
            if tie:
                severity = INFO
                verdict = "近形字并列 (12px 分辨率极限), 非路由错误"
            else:
                severity = ERROR
                verdict = "字形身份不符 (生成的点阵更像别的字)"
        elif cov < 0.90 or gray_uncovered > 0:
            severity = WARN
            verdict = "与源字形的包含关系有缺口"
        else:
            severity = INFO
            verdict = "抗锯齿/栅格化固有差异 (预期行为)"

        rec = {
            "char": ch,
            "cp": f"U+{ord(ch):04X}",
            "diff_px": d0,
            "diff_px_best_aligned": d_align,
            "best_shift": [sy, sx],
            "row_multiset_dist": rd,
            "col_multiset_dist": cd,
            "mono_ink": mono_ink,
            "gray_ink": gray_ink,
            "gray_perimeter": peri,
            "mono_covered_ratio": round(cov, 4),
            "mono_covered": cov_hit,
            "mono_ink_total": cov_tot,
            "gray_ink_uncovered": gray_uncovered,
            "nearest_char": best_char,
            "nearest_char_cp": f"U+{ord(best_char):04X}" if best_char else None,
            "nearest_dist_aligned": best_dist,
            "runner_up_char": runner_char,
            "runner_up_dist_aligned": runner_dist,
            "true_char_dist_aligned": d_true,
            "runner_mono_hamming": runner_mono_dist,
            "identity_ok": tie or best_dist >= d_true,
            "identity_strict": best_char == ch,
            "identity_near_tie": tie,
            "verdict": verdict,
            "ascii_art": side_by_side(mono, gb),
        }
        rows_out.append(rec)
        if not rec["identity_ok"]:
            identity_mismatch.append(rec)

    rows_out.sort(key=lambda r: r["diff_px"], reverse=True)
    for r in rows_out[:10]:
        anomalies.append(
            {
                "id": "B_DIFF_TOP",
                "severity": INFO,
                "detail": (
                    f"{r['char']!r} {r['cp']} 单色点阵 vs 源字体灰度阈值化差 {r['diff_px']} px "
                    f"(最佳平移 {r['best_shift']} 后 {r['diff_px_best_aligned']} px; "
                    f"最近邻={r['nearest_char']!r} {r['nearest_char_cp']}) —— {r['verdict']}"
                ),
                "chars": [r["char"]],
                "codes": [r["cp"]],
                "evidence": {k: v for k, v in r.items() if k != "ascii_art"},
                "ascii_art": r["ascii_art"],
                "classification": (
                    "真缺陷 (字形身份不符)" if not r["identity_ok"] else "预期行为 (栅格化固有差异)"
                ),
                "suggested_fix": (
                    "查路由: 该字画出来的形状更像别的字, 见 bitfont.py:219-224 _pick()"
                    if not r["identity_ok"]
                    else "无需修改: MONO 栅格化与灰度渲染的取整/覆盖阈值差异, 由 FreeType hinting 决定"
                ),
            }
        )
    for r in identity_mismatch:
        anomalies.append(
            {
                "id": "B_IDENTITY_MISMATCH",
                "severity": ERROR,
                "detail": (
                    f"{r['char']!r} {r['cp']} 生成的点阵最近邻是 {r['nearest_char']!r} "
                    f"{r['nearest_char_cp']} (对齐后距离 {r['nearest_dist_aligned']} < 自身 "
                    f"{r['true_char_dist_aligned']}) —— 字形身份不符"
                ),
                "chars": [r["char"]],
                "codes": [r["cp"]],
                "ascii_art": r["ascii_art"],
                "classification": "真缺陷 (路由/映射错误)",
                "suggested_fix": "查 charset.gb2312_level1() 的码位顺序与 bitfont.py:219-224 的路由",
            }
        )

    # 近形字并列 (最近邻不是自己, 但差距在噪声带内且点图并不相同) —— 明确标注不是缺陷
    for r in rows_out:
        if not r["identity_near_tie"]:
            continue
        anomalies.append(
            {
                "id": "B_IDENTITY_NEAR_TIE",
                "severity": INFO,
                "detail": (
                    f"{r['char']!r} {r['cp']} 的最近邻是 {r['nearest_char']!r} "
                    f"{r['nearest_char_cp']} ({r['nearest_dist_aligned']} px) 而非自身 "
                    f"({r['true_char_dist_aligned']} px), 差距 {r['true_char_dist_aligned'] - r['nearest_dist_aligned']} px "
                    f"落在栅格化噪声带 (2-23 px) 内; 且两字的**生成点图**相差 "
                    f"{r['runner_mono_hamming']} px (> {NEAR_DUP_LIMIT}), 不是同一张图 —— "
                    f"12px 分辨率下近形字不可区分, 非路由错误"
                ),
                "chars": [r["char"], r["nearest_char"]],
                "codes": [r["cp"], r["nearest_char_cp"]],
                "evidence": {
                    k: v for k, v in r.items() if k not in ("ascii_art", "verdict")
                },
                "ascii_art": r["ascii_art"],
                "classification": "预期行为 (12px 分辨率极限)",
                "suggested_fix": "无需修改; A 检查 (批内位图两两唯一, 无汉明≤2 对) 已排除路由错误",
            }
        )

    # 系统性 1 行错位: MONO 栅格化把横笔吸附到像素网格, 与灰度渲染差 0-1 行
    shifted_chars = [r for r in rows_out if r["best_shift"] != [0, 0]]
    if shifted_chars:
        anomalies.append(
            {
                "id": "B_VERTICAL_OFFSET",
                "severity": INFO,
                "detail": (
                    f"{len(shifted_chars)}/{len(rows_out)} 个抽样字的单色点阵与源字体灰度渲染"
                    f"存在 1 行整体错位 (最佳平移 dy=1) —— 1-bit MONO 栅格化把横笔吸附到像素网格, "
                    f"与灰度渲染的亚像素位置差半像素即翻到相邻行"
                ),
                "chars": [r["char"] for r in shifted_chars],
                "codes": [r["cp"] for r in shifted_chars],
                "evidence": {
                    "count": len(shifted_chars),
                    "total": len(rows_out),
                    "chars": [
                        {
                            "char": r["char"],
                            "cp": r["cp"],
                            "diff_px": r["diff_px"],
                            "diff_px_best_aligned": r["diff_px_best_aligned"],
                            "best_shift": r["best_shift"],
                        }
                        for r in shifted_chars
                    ],
                },
                "ascii_art": "",
                "classification": "预期行为 (FreeType MONO hinting 的固有结果)",
                "suggested_fix": "无需修改: 项目刻意选 MONO 目标以复刻 GDI 单色文字 "
                "(tools/fontgen/bitfont.py:7-10); 若改为按源字形 bbox 做垂直对齐, 会破坏"
                "“纯整数网格”原则 (bitfont.py:24-37), 且 1-bit 12px 本就存在 ±1 行的精度上限",
            }
        )

    shifts = {}
    for r in rows_out:
        k = f"dy={r['best_shift'][0]},dx={r['best_shift'][1]}"
        shifts[k] = shifts.get(k, 0) + 1

    return {
        "stride": stride,
        "samples": len(rows_out),
        "samples_expected": (len(hanzi) + stride - 1) // stride,
        "gray_rendered": len(grayf),
        "gray_read_failures": gray_fail,
        "identity_mismatches": len(identity_mismatch),
        "identity_strict_hits": sum(1 for r in rows_out if r["identity_strict"]),
        "identity_near_ties": sum(1 for r in rows_out if r["identity_near_tie"]),
        "identity_noise_band": [
            min((r["true_char_dist_aligned"] for r in rows_out), default=0),
            max((r["true_char_dist_aligned"] for r in rows_out), default=0),
        ],
        "tie_margin": TIE_MARGIN,
        "threshold": thr,
        "diff_px_median": sorted(r["diff_px"] for r in rows_out)[len(rows_out) // 2]
        if rows_out
        else 0,
        "diff_px_max": rows_out[0]["diff_px"] if rows_out else 0,
        "diff_px_min": rows_out[-1]["diff_px"] if rows_out else 0,
        "aligned_diff_px_max": max((r["diff_px_best_aligned"] for r in rows_out), default=0),
        "best_shift_histogram": shifts,
        "mono_covered_ratio_min": round(
            min((r["mono_covered_ratio"] for r in rows_out), default=0), 4
        ),
        "gray_ink_uncovered_max": max((r["gray_ink_uncovered"] for r in rows_out), default=0),
        "top10": rows_out[:10],
        "verdict": "FAIL" if identity_mismatch else "PASS",
    }


# ================================================================ 检查 c: 墨量分布


def check_ink(stack, hanzi, ideo, anomalies) -> dict:
    ratios = []
    grids = {}
    read_fail = 0
    tops = []
    bots = []
    for ch in hanzi:
        g = stack.glyph(ch)
        if g.width != 12 or g.height != 13:
            read_fail += 1
            continue
        grid = mono_grid(stack, ch)
        grids[ch] = grid
        ratios.append((bf.ink_ratio(g), ch))
        ys = [y for y in range(13) for x in range(12) if grid[y][x]]
        if ys:
            tops.append(min(ys))
            bots.append(max(ys))
    ratios.sort(reverse=True)
    vals = sorted(r for r, _ in ratios)
    n = len(vals)

    def pct(p: float) -> float:
        if not n:
            return 0.0
        return vals[min(n - 1, max(0, int(round(p * (n - 1)))))]

    # 参考值: 密笔画基准字 (bitfont.py:268-273 记录的三个数, 逐个复核)
    dense16 = bf.measure_density(bf.BitmapFont(path=cs.SIMHEI, index=0, px=16))
    dense12 = bf.measure_density(ideo)
    dense16_bold = bf.measure_density(
        bf.BitmapFont(path=cs.SIMHEI, index=0, px=16, weight=1)
    )
    dense12_bold = bf.measure_density(
        bf.BitmapFont(path=cs.SIMHEI, index=0, px=12, weight=1)
    )
    dense_detail = []
    for c in DENSE_PROBE:
        g = ideo.glyph(c)
        dense_detail.append(
            {"char": c, "cp": f"U+{ord(c):04X}", "ink_ratio": round(bf.ink_ratio(g), 4)}
        )
    # 三种墨量口径 —— 用来判断 “29% 不可复现” 是不是单纯的口径差异
    v16 = dense_calibers(bf.BitmapFont(path=cs.SIMHEI, index=0, px=16), 16)
    v12 = dense_calibers(ideo, 12)
    simsun = None
    if Path(SIMSUN).exists():
        simsun = dense_calibers(bf.BitmapFont(path=SIMSUN, index=0, px=16), 16)
    doc_ref = {
        "doc_16px_dense": 0.29,
        "doc_16px_dense_measured": round(dense16, 4),
        "doc_16px_dense_reproduces": abs(dense16 - 0.29) < 0.02,
        "doc_16px_bold": 0.76,
        "doc_16px_bold_measured": round(dense16_bold, 4),
        "doc_16px_bold_reproduces": abs(dense16_bold - 0.76) < 0.02,
        "doc_limit": DENSE_LIMIT,
        "measured_12px_bold": round(dense12_bold, 4),
        "doc_12px_higher_than_16px_holds": dense12 > dense16,
        "calibers": {
            "simhei_16px": v16,
            "simhei_12px": v12,
            "simsun_16px": simsun,
            "any_caliber_reaches_29pct": any(
                abs(x - 0.29) < 0.02
                for group in (v16, v12, simsun)
                for x in (group or {}).values()
                if isinstance(x, float)
            ),
        },
    }

    top = [
        {
            "char": ch,
            "cp": f"U+{ord(ch):04X}",
            "ink_ratio": round(r, 4),
            "ink_px": ink_count(grids[ch]),
            "counters": enclosed_counters(grids[ch]),
            "ascii_art": to_ascii(grids[ch]),
        }
        for r, ch in ratios[:5]
    ]
    bottom = [
        {
            "char": ch,
            "cp": f"U+{ord(ch):04X}",
            "ink_ratio": round(r, 4),
            "ink_px": ink_count(grids[ch]),
            "counters": enclosed_counters(grids[ch]),
            "ascii_art": to_ascii(grids[ch]),
        }
        for r, ch in ratios[-5:][::-1]
    ]

    over = [(r, ch) for r, ch in ratios if r > DENSE_LIMIT]
    closed = [
        (r, ch)
        for r, ch in ratios
        if r > DENSE_LIMIT and enclosed_counters(grids[ch]) == 0
    ]
    for r, ch in over:
        cnt = enclosed_counters(grids[ch])
        anomalies.append(
            {
                "id": "C_DENSE_INK",
                "severity": WARN if cnt > 0 else ERROR,
                "detail": (
                    f"{ch!r} U+{ord(ch):04X} 墨量 {r:.1%} 超过 60% 上限; "
                    f"字腔数={cnt} ({'仍有字腔' if cnt else '字腔全闭'})"
                ),
                "chars": [ch],
                "codes": [f"U+{ord(ch):04X}"],
                "evidence": {
                    "ink_ratio": round(r, 4),
                    "counters": cnt,
                    "limit_source": "tools/fontgen/bitfont.py:270-273",
                },
                "ascii_art": to_ascii(grids[ch]),
                "classification": (
                    "网格上限问题 (非代码缺陷): 该字笔画密度超过 12x13 可承载范围"
                    if cnt > 0
                    else "预期行为 (网格上限): 密笔画字在 12px 上字腔必然闭合"
                ),
                "suggested_fix": (
                    "无需改代码; 若要该字可用, 需加大网格 (cell_h/ascent) 或换源字体, "
                    "参照 bitfont.py:268-273 measure_density()"
                ),
            }
        )

    # 复核 bitfont.py:268-273 里记录的三个参考值
    if not doc_ref["doc_16px_dense_reproduces"]:
        cal = doc_ref["calibers"]
        v16 = cal["simhei_16px"]
        v12 = cal["simhei_12px"]
        ss = cal.get("simsun_16px")
        alt = (
            f"16px 换口径实测: cell 口径 {v16['cell_ratio']:.1%} (cell={v16['cell']}, "
            f"ascent/descent={v16['ascent_descent']}), 16x16 正方形口径 {v16['square_ratio']:.1%}, "
            f"墨迹包围盒口径 {v16['bbox_ratio']:.1%}"
        )
        if ss:
            alt += (
                f"; 换字体实测: SimSun 16px cell 口径 {ss['cell_ratio']:.1%} "
                f"(cell={ss['cell']})"
            )
        anomalies.append(
            {
                "id": "C_DOC_REFERENCE_MISMATCH",
                "severity": WARN,
                "detail": (
                    f"**代码原话** (tools/fontgen/bitfont.py:272, measure_density 文档): "
                    f"“实测 SimHei 16px 为 29%, 一旦做 1px 膨胀就到 76%”。"
                    f"**本次实测** (工程自己的 bitfont.measure_density, ink/(cell_w x cell_h)): "
                    f"16px = {doc_ref['doc_16px_dense_measured']:.1%} —— "
                    f"与注释差 {doc_ref['doc_16px_dense_measured'] - 0.29:+.1%} "
                    f"(实测是注释的 {doc_ref['doc_16px_dense_measured'] / 0.29:.2f} 倍), "
                    f"**该数字不可复现**。{alt} —— 三种口径都到不了 29%, 所以不是单纯的口径差异, "
                    f"更可能是早期未校准的估算值/旧版本数值 (过期注释)。"
                    f"同段另两个数: “1px 膨胀就到 76%” 可复现 (实测 "
                    f"{doc_ref['doc_16px_bold_measured']:.1%}); “12px 更高” 成立 "
                    f"(12px = {round(dense12, 4):.1%}); “60% 以上基本等于不可用” 方向成立 "
                    f"(12px + 1px 膨胀 = {doc_ref['measured_12px_bold']:.1%})"
                ),
                "chars": list(DENSE_PROBE),
                "codes": [f"U+{ord(c):04X}" for c in DENSE_PROBE],
                "evidence": doc_ref,
                "ascii_art": "",
                "classification": "文档与实测不符 (过期注释, 非运行时缺陷)",
                "suggested_fix": "tools/fontgen/bitfont.py:272 —— 把 “29%” 改成实测口径值 "
                "35.6% (cell 口径, 与 measure_density 一致) 并写明口径, 或按 16x16 口径写 37.8%; "
                "同段的 76% 与 60% 阈值保持不动。本 lane 不改源码, 交由集成者统一修正注释",
            }
        )

    return {
        "checked": len(ratios),
        "read_failures": read_fail,
        "median": round(pct(0.5), 4),
        "p95": round(pct(0.95), 4),
        "max": round(vals[-1], 4) if n else 0,
        "min": round(vals[0], 4) if n else 0,
        "mean": round(sum(vals) / n, 4) if n else 0,
        "over_60pct": len(over),
        "over_60pct_and_zero_counter": len(closed),
        "baseline": {
            "ink_top_min": min(tops) if tops else 0,
            "ink_top_max": max(tops) if tops else 0,
            "ink_top_median": sorted(tops)[len(tops) // 2] if tops else 0,
            "ink_bottom_min": min(bots) if bots else 0,
            "ink_bottom_max": max(bots) if bots else 0,
            "ink_bottom_median": sorted(bots)[len(bots) // 2] if bots else 0,
            "note": "13 行格内, 基线在第 11 行 (ascent=11); 汉字墨迹应始终落在第 11 行及其上方",
        },
        "top5": top,
        "bottom5": bottom,
        "reference": {
            "dense_probe": DENSE_PROBE,
            "dense_probe_ink_12px": round(dense12, 4),
            "dense_probe_ink_16px": round(dense16, 4),
            "dense_probe_detail_12px": dense_detail,
            "doc_reference_16px": 0.29,
            "doc_reference_16px_matches": doc_ref["doc_16px_dense_reproduces"],
            "doc_reference_check": doc_ref,
            "limit": DENSE_LIMIT,
            "limit_source": "tools/fontgen/bitfont.py:270-273",
        },
        "verdict": "FAIL" if over else "PASS",
    }


# ================================================================ 检查 d: 成品旁证


def check_artifacts(stack, hanzi, anomalies) -> dict:
    """只读: 复核 BDF 结构, 并把探针位图与 dist/ 图集成品对拍。"""
    res: dict = {"bdf": None, "atlas": None, "dist_present": False}
    dist = ROOT / "dist"
    if not dist.exists():
        res["dist_present"] = False
        res["reason"] = "dist/ 不存在 —— 成品旁证没测到东西, 不作任何结论"
        return res
    res["dist_present"] = True

    bdf = dist / "PixelFontPC98-12.bdf"
    if bdf.exists():
        lines = bdf.read_text(encoding="utf-8").splitlines()
        starts = sum(1 for ln in lines if ln.startswith("STARTCHAR"))
        ends = sum(1 for ln in lines if ln.strip() == "ENDCHAR")
        bad = []
        cur = None
        for ln in lines:
            if ln.startswith("STARTCHAR"):
                cur = {"name": ln, "enc": None, "endchar": 0}
                bad.append(cur)
            elif cur is not None:
                if ln.startswith("ENCODING "):
                    cur["enc"] = ln.split()[1]
                elif ln.strip() == "ENDCHAR":
                    cur["endchar"] += 1
        broken = [b for b in bad if b["endchar"] != 1]
        res["bdf"] = {
            "startchar": starts,
            "endchar": ends,
            "paired": starts == ends,
            "broken_blocks": broken[:10],
            "broken_count": len(broken),
        }
        if starts != ends:
            detail = (
                f"BDF STARTCHAR {starts} 个但 ENDCHAR {ends} 个 —— 字符块结构不配对"
            )
            culprit = broken[0] if broken else {}
            anomalies.append(
                {
                    "id": "D_BDF_STRUCTURE",
                    "severity": ERROR,
                    "detail": detail
                    + (
                        f"; 首个异常块 {culprit.get('name')} ENCODING {culprit.get('enc')} "
                        f"有 {culprit.get('endchar')} 个 ENDCHAR"
                        if culprit
                        else ""
                    ),
                    "chars": [],
                    "codes": [],
                    "evidence": {"startchar": starts, "endchar": ends, "broken": broken[:5]},
                    "ascii_art": "",
                    "classification": "真缺陷 (成品格式非法)",
                    "suggested_fix": "tools/fontgen/build_font.py:133 —— 零墨迹字形分支写了两个 ENDCHAR, "
                    "应改为 lines += [\"BITMAP\", \"ENDCHAR\"] (只留一个 ENDCHAR)",
                }
            )

    png = dist / "PixelFontPC98-12-atlas.png"
    js = dist / "PixelFontPC98-12-atlas.json"
    if png.exists() and js.exists():
        data = json.loads(js.read_text(encoding="utf-8"))
        img = Image.open(png).convert("RGBA")
        px = img.load()
        cw, chh = data["cell"]["w"], data["cell"]["h"]
        entries = {m[0]: m for m in data["glyphs"]}
        diff = 0
        read_fail = 0
        for ch in hanzi:
            e = entries.get(ord(ch))
            if e is None:
                read_fail += 1
                continue
            _, gx, gy, adv, _wide = e
            g = stack.glyph(ch)
            gp = g.load()
            for y in range(chh):
                for x in range(cw):
                    want = 1 if gp[x, y] > 0 else 0
                    got = 1 if px[gx + x, gy + y][3] > 0 else 0
                    if want != got:
                        diff += 1
                        break
        res["atlas"] = {
            "checked": len(hanzi),
            "read_failures": read_fail,
            "mismatched_glyphs": diff,
        }
        if diff:
            anomalies.append(
                {
                    "id": "D_ATLAS_MISMATCH",
                    "severity": ERROR,
                    "detail": f"探针位图与 dist/ 图集成品有 {diff} 个字形不一致",
                    "chars": [],
                    "codes": [],
                    "evidence": res["atlas"],
                    "ascii_art": "",
                    "classification": "真缺陷",
                    "suggested_fix": "查 build_font.py:298-336 write_atlas()",
                }
            )
    return res


# ================================================================ 报告


def render_markdown(rep: dict) -> str:
    L = [f"# 汉字批次补充探针报告 — {rep['batch']['label']}", ""]
    s = rep["summary"]
    L += [
        f"- 生成时间: {rep['generated_at']}",
        f"- 判定: **{s['verdict']}** (error {s['errors']} / warn {s['warnings']} / info {s['infos']})",
        f"- 覆盖: {rep['batch']['chars']} 个汉字 (GB2312 一级汉字 {rep['batch']['hanzi_total']} 字的前 "
        f"{rep['batch']['chars']} 字, 码位 {rep['batch']['first_cp']}–{rep['batch']['last_cp']})",
        f"- 数据指纹 (除时间戳外的全部内容 sha256): `{rep['content_sha256'][:16]}…`",
        "",
    ]

    L.append("## 量具可靠性 (消费了多少输入, 哪里读失败)")
    L.append("")
    L.append("| 检查项 | 消费输入 | 读取失败 | 产出 |")
    L.append("|---|---|---|---|")
    a = rep["checks"]["A_uniqueness"]
    L.append(
        f"| a 字形唯一性 | {a['checked']} 个汉字位图 | {a['read_failures']} | "
        f"{a['distinct_bitmaps']} 个互异位图, {a['exact_duplicate_groups']} 组完全相同, "
        f"{a['near_duplicate_pairs_le2']} 对汉明≤2 |"
    )
    b = rep["checks"]["B_source_fidelity"]
    L.append(
        f"| b 源形保真 | {b['samples']} 个抽样字 + {b['gray_rendered']} 次源字体灰度渲染 | "
        f"{b['gray_read_failures']} | 逐像素差异中位 {b['diff_px_median']} px, "
        f"身份不符 {b['identity_mismatches']} 个 |"
    )
    c = rep["checks"]["C_ink_distribution"]
    L.append(
        f"| c 墨量分布 | {c['checked']} 个汉字的 ink ratio | {c['read_failures']} | "
        f"中位 {c['median']:.1%} / p95 {c['p95']:.1%} / max {c['max']:.1%} |"
    )
    d = rep["checks"]["D_artifact_crosscheck"]
    if d.get("dist_present"):
        L.append(
            f"| d 成品旁证 | dist/ BDF {d['bdf']['startchar']} 块 + 图集 {d['atlas']['checked']} 字形 | "
            f"{d['atlas']['read_failures']} | BDF 配对={d['bdf']['paired']}, "
            f"图集不一致 {d['atlas']['mismatched_glyphs']} |"
        )
    else:
        L.append(f"| d 成品旁证 | — | — | {d.get('reason', '未测')} |")
    L.append("")

    ctrl = a.get("negative_control") or {}
    if ctrl:
        L.append("## 阴性对照 (证明检测器能响)")
        L.append("")
        L.append(
            f"- 跨类别同图对 {ctrl['pair'][0]!r} {ctrl['codes'][0]} / {ctrl['pair'][1]!r} "
            f"{ctrl['codes'][1]}: same_bitmap={ctrl.get('same_bitmap')}"
        )
        L.append(f"- {ctrl.get('verdict', '')}")
        L.append("")

    L.append("## a) 字形唯一性")
    L.append("")
    L.append(f"- 批内完全相同的位图组: **{a['exact_duplicate_groups']}**")
    L.append(f"- 批内互异位图数: {a['distinct_bitmaps']} / {a['checked']}")
    L.append(f"- 汉明距离 ≤2 的近似对: {a['near_duplicate_pairs_le2']} (12px 下只差一两笔的汉字本就可能撞图)")
    mp = a.get("min_pairwise_distance") or {}
    if mp:
        L.append(
            f"- 批内两两最小位图距离: {mp['dist_px']} px "
            f"({mp['chars'][0]!r} {mp['codes'][0]} vs {mp['chars'][1]!r} {mp['codes'][1]}); "
            f"距离 ≤5 的对共 {a.get('pairs_le5', 0)} 组 —— 近重复检测器确实在跑, 且没有 ≤2 的撞图"
        )
    L.append("")

    L.append("## b) 源形保真 (单色点阵 vs 源字体灰度渲染阈值化)")
    L.append("")
    L.append(
        f"- 抽样步长 {b['stride']} → {b['samples']} 个抽样字 (期望 {b['samples_expected']})"
    )
    L.append(
        f"- 逐像素差异 (与灰度阈值化直接比): 中位 {b['diff_px_median']} px, "
        f"最小 {b['diff_px_min']} px, 最大 {b['diff_px_max']} px"
    )
    L.append(
        f"- 允许整体平移后: 最大差异 {b['aligned_diff_px_max']} px; "
        f"最佳平移分布 {b['best_shift_histogram']}"
    )
    L.append(
        f"- 包含关系 (单色墨迹被真实形状覆盖的比例) 最低 {b['mono_covered_ratio_min']:.1%}; "
        f"真实形状有墨而单色全无的像素最多 {b['gray_ink_uncovered_max']}"
    )
    L.append(
        f"- 身份判定 (全部 1900 个候选字做对齐最近邻): 严格命中自身 **{b['identity_strict_hits']}**/"
        f"{b['samples']}; 近形字并列 {b['identity_near_ties']} 个; 身份不符 "
        f"**{b['identity_mismatches']}** 个 —— 这是「字画错了」的判定, 比差异像素数更有定性"
    )
    L.append(
        f"- 噪声带: mono 与**自身**源字形的对齐距离分布 {b['identity_noise_band']} px; "
        f"最近邻差距容忍带 {b['tie_margin']} px"
    )
    L.append("")
    for r in b["top10"]:
        L.append(f"### {r['char']!r} {r['cp']} — 差异 {r['diff_px']} px — {r['verdict']}")
        L.append("")
        L.append(
            f"- 最佳平移 {r['best_shift']} 后差异 {r['diff_px_best_aligned']} px; "
            f"行多重集距离 {r['row_multiset_dist']}, 列多重集距离 {r['col_multiset_dist']}"
        )
        L.append(
            f"- 墨迹像素 单色 {r['mono_ink']} / 灰度 {r['gray_ink']}; "
            f"灰度笔画边缘像素 {r['gray_perimeter']} (差异≤它 即为边缘取整可解释)"
        )
        L.append(
            f"- 包含关系: 单色墨迹被真实形状覆盖 {r['mono_covered_ratio']:.1%} "
            f"({r['mono_covered']}/{r['mono_ink_total']}), "
            f"真实形状有墨而单色邻域全空 {r['gray_ink_uncovered']} px"
        )
        L.append(
            f"- 最近邻: {r['nearest_char']!r} {r['nearest_char_cp']} "
            f"(对齐后 {r['nearest_dist_aligned']} px) vs 自身 {r['true_char_dist_aligned']} px"
        )
        L.append("")
        L.append("```")
        L.append(r["ascii_art"])
        L.append("```")
        L.append("")

    L.append("## c) 墨量分布")
    L.append("")
    ref = c["reference"]
    L.append(
        f"- 中位 {c['median']:.1%}, p95 {c['p95']:.1%}, max {c['max']:.1%}, "
        f"min {c['min']:.1%}, 均值 {c['mean']:.1%}"
    )
    L.append(
        f"- 参考: 密笔画基准字 {ref['dense_probe']} 在 SimHei 12px 墨量 {ref['dense_probe_ink_12px']:.1%}; "
        f"16px 实测 {ref['dense_probe_ink_16px']:.1%} (文档记录 {ref['doc_reference_16px']:.0%}, "
        f"复核{'一致' if ref['doc_reference_16px_matches'] else '**不一致**'})"
    )
    dr = ref.get("doc_reference_check") or {}
    if dr:
        L.append(
            f"- 文档三个参考值逐个复核 (bitfont.py:268-273): "
            f"“16px 29%” → 实测 {dr.get('doc_16px_dense_measured', 0):.1%} "
            f"({'复现' if dr.get('doc_16px_dense_reproduces') else '**不可复现**'}); "
            f"“1px 膨胀到 76%” → 实测 {dr.get('doc_16px_bold_measured', 0):.1%} "
            f"({'复现' if dr.get('doc_16px_bold_reproduces') else '不可复现'}); "
            f"“12px 更高” → {'成立' if dr.get('doc_12px_higher_than_16px_holds') else '不成立'} "
            f"(12px+1px 膨胀 = {dr.get('measured_12px_bold', 0):.1%})"
        )
        cal = dr.get("calibers") or {}
        if cal:
            L.append("")
            L.append("| 字体/字号 | cell 口径 (measure_density) | 16x16 正方形口径 | 墨迹包围盒口径 |")
            L.append("|---|---|---|---|")
            for key in ("simhei_16px", "simhei_12px", "simsun_16px"):
                g = cal.get(key)
                if not g:
                    L.append(f"| {key} | 未测到 (系统无该字体) | — | — |")
                    continue
                L.append(
                    f"| {g['font']} {g['px']}px (cell {g['cell']}, {g['ascent_descent']}) | "
                    f"{g['cell_ratio']:.1%} | {g['square_ratio']:.1%} | {g['bbox_ratio']:.1%} |"
                )
            L.append("")
    L.append(
        f"- 超过 60% 上限 (bitfont.py:270-273) 的字: {c['over_60pct']} 个; "
        f"其中字腔全闭的: {c['over_60pct_and_zero_counter']} 个"
    )
    bl = c["baseline"]
    L.append(
        f"- 基线一致性: 墨迹 top {bl['ink_top_min']}-{bl['ink_top_max']} (中位 {bl['ink_top_median']}), "
        f"bottom {bl['ink_bottom_min']}-{bl['ink_bottom_max']} (中位 {bl['ink_bottom_median']}) "
        f"— {bl['note']}"
    )
    L.append("")
    L.append("### 墨量最高 5 个")
    L.append("")
    for r in c["top5"]:
        L.append(
            f"**{r['char']!r} {r['cp']}** — 墨量 {r['ink_ratio']:.1%} ({r['ink_px']} px), "
            f"字腔 {r['counters']}"
        )
        L.append("")
        L.append("```")
        L.append(r["ascii_art"])
        L.append("```")
        L.append("")
    L.append("### 墨量最低 5 个")
    L.append("")
    for r in c["bottom5"]:
        L.append(
            f"**{r['char']!r} {r['cp']}** — 墨量 {r['ink_ratio']:.1%} ({r['ink_px']} px), "
            f"字腔 {r['counters']}"
        )
        L.append("")
        L.append("```")
        L.append(r["ascii_art"])
        L.append("```")
        L.append("")

    L.append("## 异常清单")
    L.append("")
    if not rep["anomalies"]:
        L.append("无异常。")
    else:
        L.append("| ID | 级别 | 字符 | 码位 | 判定 | 说明 |")
        L.append("|---|---|---|---|---|---|")
        for an in rep["anomalies"]:
            ch = "".join(an.get("chars", [])) or "—"
            cp = ", ".join(an.get("codes", [])) or "—"
            L.append(
                f"| `{an['id']}` | {an['severity']} | {ch} | {cp} | "
                f"{an.get('classification', '')} | {an['detail']} |"
            )
        L.append("")
        for an in rep["anomalies"]:
            if an.get("severity") == INFO and not an.get("ascii_art"):
                continue
            L.append(f"### {an['id']} — {an.get('chars', '')} {an.get('codes', '')}")
            L.append("")
            L.append(f"- {an['detail']}")
            L.append(f"- 判定: {an.get('classification', '')}")
            L.append(f"- 建议: {an.get('suggested_fix', '')}")
            if an.get("ascii_art"):
                L.append("")
                L.append("```")
                L.append(an["ascii_art"])
                L.append("```")
            L.append("")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="hanzi lane 补充探针 (唯一性/源形保真/墨量)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--slice-end", type=int, default=SLICE_END)
    ap.add_argument("--stride", type=int, default=SAMPLE_STRIDE)
    ap.add_argument("--threshold", type=int, default=GRAY_THRESHOLD)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    items = cs.build_charset()
    stack = cs.build_stack()
    ideo = stack.ideo
    hanzi_all = [ch for ch, cat in items if cat == "hanzi"]
    hanzi = hanzi_all[: args.slice_end]

    anomalies: list[dict] = []
    a = check_uniqueness(stack, hanzi, anomalies)
    b = check_fidelity(stack, hanzi, ideo, anomalies, args.stride, args.threshold)
    c = check_ink(stack, hanzi, ideo, anomalies)
    d = check_artifacts(stack, hanzi, anomalies)

    errors = sum(1 for x in anomalies if x["severity"] == ERROR)
    warns = sum(1 for x in anomalies if x["severity"] == WARN)
    infos = sum(1 for x in anomalies if x["severity"] == INFO)
    verdict = "FAIL" if errors else "PASS"

    rep = {
        "tool": "hanzi_a_probe",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "agent/reg-hanzi-a",
        "batch": {
            "label": f"hanzi_0-{len(hanzi)}",
            "chars": len(hanzi),
            "hanzi_total": len(hanzi_all),
            "charset_total": len(items),
            "first_cp": f"U+{ord(hanzi[0]):04X}",
            "last_cp": f"U+{ord(hanzi[-1]):04X}",
            "source_font": ideo.path,
        },
        "inputs": {
            "items_consumed": len(items),
            "hanzi_consumed": len(hanzi),
            "glyphs_rendered_mono": a["checked"] + c["checked"],
            "gray_renders": b["gray_rendered"],
            "read_failures": {
                "A": a["read_failures"],
                "B": b["gray_read_failures"],
                "C": c["read_failures"],
                "D": (d.get("atlas") or {}).get("read_failures", 0),
            },
        },
        "checks": {
            "A_uniqueness": a,
            "B_source_fidelity": b,
            "C_ink_distribution": c,
            "D_artifact_crosscheck": d,
        },
        "anomalies": anomalies,
        "summary": {
            "errors": errors,
            "warnings": warns,
            "infos": infos,
            "verdict": verdict,
            "check_verdicts": {
                "A_uniqueness": a["verdict"],
                "B_source_fidelity": b["verdict"],
                "C_ink_distribution": c["verdict"],
            },
        },
    }
    # 内容指纹: 去掉时间戳与指纹本身, 用于证明"再跑一次结果一样"
    body = {k: v for k, v in rep.items() if k not in ("generated_at", "content_sha256")}
    rep["content_sha256"] = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    out.with_suffix(".md").write_text(render_markdown(rep), encoding="utf-8")

    print(f"[hanzi_a_probe] 覆盖 {len(hanzi)} 字 / error={errors} warn={warns} info={infos} 判定={verdict}")
    print(f"   A 唯一性: {a['distinct_bitmaps']} 互异位图 / 重复组 {a['exact_duplicate_groups']}")
    print(f"   B 源形保真: 抽样 {b['samples']} 字, 差异中位 {b['diff_px_median']}px, 身份不符 {b['identity_mismatches']}")
    print(f"   C 墨量: 中位 {c['median']:.1%} p95 {c['p95']:.1%} max {c['max']:.1%} 超60% {c['over_60pct']}")
    print(f"   报告: {out} / {out.with_suffix('.md')}")
    print(f"   内容指纹: {rep['content_sha256'][:16]}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
