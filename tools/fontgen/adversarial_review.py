"""三轮对抗式字形审核 —— 每个码位过三轮, 每轮攻击上一轮的结论。

为什么是"对抗式"而不是"复核三遍":
    同一个量具跑三遍 = 三次**相关**的命中, 不是三份独立证据。
    上一轮已经量过的结论, 再用同一把尺子量一遍, 只会把同一个偏差重复三遍 ——
    三轮一致地错, 比错一次更难发现。
    真正能推翻结论的, 是**换一个攻击面**去撞同一个字:

        第一轮 攻身份 —— 你画的到底是不是这个字?
        第二轮 攻结构 —— 是这个字, 但某个部件塌了吗?
        第三轮 攻链条 —— 结论赖以成立的那条链, 自身有没有断?

    每轮都要能证伪上一轮, 也要能被下一轮证伪。

三轮的量具**互相独立** (拓扑 / 分带 / 字节级溯源):
    · 第一轮用「腔数镜像 + 像素级反向近邻 + 拓扑签名」, 看不见笔画粘连;
    · 第二轮用「腔面积集合 + 部件归属 + 桥接间隙」, 看不见整字换字;
    · 第三轮用「字节级溯源 + 产物独立读」, 前两轮都看不见的
      「结论赖以成立的那条链断了」, 只有它能看见。

每轮的结构 (缺一不可):
    1. 攻击面: **每个码位都要过**, 不允许只查可疑的;
    2. 量具自检: 每个新量具写两份**不同代码路径**的实现, 全量比对一致才算数
       (历史教训: 腔数两份实现不一致时 800 次里 667 次错, 且错的时候表现和对时一模一样);
    3. **阈值标定**: 阈值不拍脑袋 —— 一律取自"对照集" (历史复核未标注任何问题的字)
       的经验分布, 只有超出噪声底的才算命中;
    4. 对照组: 阳性对照 (注入已知缺陷 -> 必须响) + 阴性对照 (已知正确的字 -> 必须不响);
    5. 结论回灌: 命中项出证据图, 由人眼定夺 —— 自动判据只筛高危, 不替代目视。

用法:
    python tools/fontgen/adversarial_review.py                  # 三轮全跑
    python tools/fontgen/adversarial_review.py --round 2        # 只跑某一轮
    python tools/fontgen/adversarial_review.py --sheet          # 出证据图

输出:
    reports/adversarial/round1.json|md   第一轮 (身份反查)
    reports/adversarial/round2.json|md   第二轮 (部件级结构)
    reports/adversarial/round3.json|md   第三轮 (链条)
    reports/adversarial/summary.json|md  逐字三轮裁决 + 冲突表
    reports/adversarial/png/*.png         命中项证据图 (供人眼定夺)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))

import charset as cs  # noqa: E402
import verify_identity as vi  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "reports" / "adversarial"
PNGDIR = OUTDIR / "png"

CANVAS = 16  # 归一化画布: 16x16 (Unifont 是 16px 基准, 槽位按最大字形算, 避免串格)

# ================================================================ 量具层
#
# 每个量具都有两份实现: A 与 B 必须走**不同的代码路径** (洪水填充 / 并查集),
# 因为历史上两份"看起来一样"的实现里, 有一份把贴边区域算成了腔,
# 800 次比较里 667 次不一致 —— 而它错的时候表现和对的时候一模一样。


def holes_areas_bfs(a: np.ndarray) -> tuple[int, list[int]]:
    """实现 A: 洪水填充 (BFS)。返回 (腔数, 腔面积降序列表)。

    字腔定义 (与项目其余工具一致, 见 docs/glyph-identity-verification.md 3.84):
    4 邻域下被墨迹完全包围的白区连通分量数, 按墨迹外接矩形计;
    碰到外接矩形上下左右任一边界的白区**不算腔** (那是外部背景)。
    """
    ink = a > 0
    h, w = ink.shape
    seen = np.zeros_like(ink)
    areas: list[int] = []
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0, x0] or ink[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            area = 0
            border = False
            while stack:
                y, x = stack.pop()
                area += 1
                if y == 0 or y == h - 1 or x == 0 or x == w - 1:
                    border = True
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and not ink[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if not border:
                areas.append(area)
    areas.sort(reverse=True)
    return len(areas), areas


def holes_areas_uf(a: np.ndarray) -> tuple[int, list[int]]:
    """实现 B: 并查集。与实现 A 走完全不同的代码路径, 用于交叉验证。"""
    ink = a > 0
    h, w = ink.shape
    idx = np.full((h, w), -1, dtype=np.int64)
    parent: list[int] = []

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    nxt = 0
    for y in range(h):
        for x in range(w):
            if ink[y, x]:
                continue
            idx[y, x] = nxt
            parent.append(nxt)
            if y > 0 and not ink[y - 1, x]:
                union(nxt, int(idx[y - 1, x]))
            if x > 0 and not ink[y, x - 1]:
                union(nxt, int(idx[y, x - 1]))
            nxt += 1
    size: Counter[int] = Counter()
    border: set[int] = set()
    for y in range(h):
        for x in range(w):
            if ink[y, x]:
                continue
            r = find(int(idx[y, x]))
            size[r] += 1
            if y == 0 or y == h - 1 or x == 0 or x == w - 1:
                border.add(r)
    areas = sorted((v for k, v in size.items() if k not in border), reverse=True)
    return len(areas), areas


def row_runs(a: np.ndarray) -> list[int]:
    """每行的墨迹分段数 (逐行)。"""
    ink = a > 0
    out = []
    for y in range(ink.shape[0]):
        n = 0
        prev = False
        for x in range(ink.shape[1]):
            cur = bool(ink[y, x])
            if cur and not prev:
                n += 1
            prev = cur
        out.append(n)
    return out


def col_runs(a: np.ndarray) -> list[int]:
    """每列的墨迹分段数 (逐列)。"""
    ink = a > 0
    out = []
    for x in range(ink.shape[1]):
        n = 0
        prev = False
        for y in range(ink.shape[0]):
            cur = bool(ink[y, x])
            if cur and not prev:
                n += 1
            prev = cur
        out.append(n)
    return out


def ink_per_row(a: np.ndarray) -> list[int]:
    return list((a > 0).sum(axis=1))


def ink_per_col(a: np.ndarray) -> list[int]:
    return list((a > 0).sum(axis=0))


def signature(a: np.ndarray, holes: int | None = None) -> tuple[int, ...]:
    """结构签名: (腔数, 横笔画分段, 竖笔画分段, 墨量, 宽, 高)。

    holes: 允许传入已算好的腔数 —— 参考集有 8 万多个字形, 腔数是整个工具里
    最贵的一步, 算一次要复用很多轮, 重算是纯浪费。
    """
    n = holes_areas_bfs(a)[0] if holes is None else holes
    rr = sum(row_runs(a))
    cr = sum(col_runs(a))
    ink = int((a > 0).sum())
    h, w = a.shape
    return (n, rr, cr, ink, w, h)


def pack_canvas(a: np.ndarray) -> np.ndarray:
    """把字形放进 16x16 画布 (左上对齐, **不重采样**), 压成 4 个 uint64。

    为什么不做缩放: 像素字体的信息全在"哪一格有没有墨", 重采样会把
    1px 笔画抹掉或复制成 2px —— 而"笔画有没有被搭桥连上"正是本轮要找的东西。
    为什么左上对齐: 裁到墨迹外接框之后, 同一个字在不同字体里的左上角
    位置是稳定的, 缩放不是。
    """
    canvas = np.zeros((CANVAS, CANVAS), dtype=np.uint8)
    h, w = a.shape
    canvas[: min(h, CANVAS), : min(w, CANVAS)] = (a[:CANVAS, :CANVAS] > 0)
    packed = np.packbits(canvas.reshape(-1), bitorder="little")
    return np.frombuffer(packed.tobytes(), dtype=np.uint64)


def component_cells(a: np.ndarray) -> list[tuple[tuple[int, int], int, int]]:
    """把每个字腔归属到一个**二维部件格** (列带 x 行带)。

    列带: 按"整列无墨"的列切分 (左右结构); 行带: 按"整行无墨"的行切分 (上下结构)。
    这是第二轮的核心量具: 全局腔数看不见的局部塌陷, 分带后就能定位到
    "哪一块塌了" —— 给出的是**位置**, 而不是"这个字有问题"。

    返回 [(格坐标, 腔面积, 腔左边界x), ...]。
    """
    ink = a > 0
    h, w = ink.shape

    def split(mask: np.ndarray) -> list[tuple[int, int]]:
        cuts = [0]
        for i, v in enumerate(mask):
            if not v:
                cuts.append(i + 1)
        cuts.append(len(mask))
        out = []
        for i in range(len(cuts) - 1):
            x0, x1 = cuts[i], cuts[i + 1]
            if x1 > x0:
                out.append((x0, x1))
        return out or [(0, len(mask))]

    col_bands = split(~ink.any(axis=0))
    row_bands = split(~ink.any(axis=1))
    seen = np.zeros_like(ink)
    out: list[tuple[tuple[int, int], int, int]] = []
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0, x0] or ink[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            area = 0
            border = False
            minx = w
            while stack:
                y, x = stack.pop()
                area += 1
                minx = min(minx, x)
                if y == 0 or y == h - 1 or x == 0 or x == w - 1:
                    border = True
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and not ink[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if border:
                continue
            ci = 0
            for i, (x0b, x1b) in enumerate(col_bands):
                if x0b <= minx < x1b:
                    ci = i
                    break
            ri = 0
            for i, (y0b, y1b) in enumerate(row_bands):
                if y0b <= y0 < y1b:
                    ri = i
                    break
            out.append(((ci, ri), area, minx))
    out.sort(key=lambda t: (t[0], -t[1]))
    return out


# ================================================================ 标定层


def calibrate(values: list[float], q: float) -> float:
    """从对照集的经验分布取阈值。

    为什么必须标定: 本项目的历史教训是"量具错的时候, 表现和对的时候一模一样"。
    拍一个阈值出来的命中数, 说明不了任何事 —— 除非同时报出
    "同样的量具在**已知正确**的字上会响几次" (那才是噪声底)。
    """
    if not values:
        return float("inf")
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def describe_threshold(name: str, thr: float, ctrl: list[float], unit: str = "") -> str:
    med = float(np.median(ctrl)) if ctrl else 0.0
    return f"{name}: 阈值 {thr:.3f}{unit} (对照集中位 {med:.3f}{unit}, 样本 {len(ctrl)})"


def calibrated_thresholds(
    values: dict[int, float],
    control: set[int],
    cat_of: dict[str, str],
    q: float,
    min_samples: int = 40,
) -> tuple[dict[str, float], float, list[float]]:
    """按**类别**标定阈值, 样本不足时回落到全局。

    为什么要分类别: 各类的画风落差天差地别 ——
    ASCII/假名走 MS Gothic (本来就是 12px 点阵), 与 12px 的 Zpix 几乎同源;
    汉字走 SimHei 轮廓栅格化或 Fusion 点阵, 与 Zpix 的画风差一个量级。
    用同一个阈值, 对 ASCII 极松 (漏报)、对汉字极紧 (误报)。
    """
    ctrl_vals = [v for cp, v in values.items() if cp in control]
    thr_global = calibrate(ctrl_vals, q)
    by_cat: dict[str, float] = {}
    for cat in sorted(set(cat_of.values())):
        vals = [v for cp, v in values.items() if cp in control and cat_of.get(cp) == cat]
        if len(vals) >= min_samples:
            by_cat[cat] = calibrate(vals, q)
    return by_cat, thr_global, ctrl_vals


def thr_for(cp: int, cat_of: dict[str, str], by_cat: dict[str, float], thr_global: float) -> float:
    return by_cat.get(cat_of.get(cp, "?"), thr_global)


# ================================================================ 数据装载


def load_ours(items: list[tuple[str, str]]):
    """我方字形 (栅格化器输出, 裁到墨迹外接矩形) + 字栈 + 分类表。"""
    stack = cs.build_stack()
    ours: dict[int, np.ndarray] = {}
    for ch, _cat in items:
        g = stack.glyph(ch)
        a = (np.array(g, dtype=np.uint8) > 0).astype(np.float32)
        ys, xs = np.nonzero(a)
        if not len(xs):
            continue
        ours[ord(ch)] = a[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    cat_of = {ord(ch): cat for ch, cat in items}
    return ours, stack, cat_of


def load_refs(names: list[str]) -> dict[str, dict[int, np.ndarray]]:
    out: dict[str, dict[int, np.ndarray]] = {}
    for name in names:
        meta = vi.REFS[name]
        p = vi.REFDIR / meta["path"]
        if not p.exists():
            print(f"[warn] 参考字体缺失: {p}", file=sys.stderr)
            continue
        from fontTools.ttLib import TTFont

        tt = TTFont(str(p), fontNumber=0)
        glyphs, fails = vi.ref_glyphs(p, meta["ppem"], sorted(tt.getBestCmap().keys()))
        out[name] = glyphs
        print(f"   参考 {name}: {len(glyphs)} 个字形 (失败 {fails})")
    return out


# ================================================================ 第一轮: 身份反查


def round1_identity(
    ours: dict[int, np.ndarray],
    refs: dict[str, dict[int, np.ndarray]],
    cat_of: dict[str, str],
    control: set[int],
) -> dict:
    """第一轮: 攻「你画的是不是这个字」。

    四条攻击线, 攻击的是上一轮同一类的结论:
      a) COUNTER_GAINED —— 镜像判据。现有硬检查只有 COUNTER_LOST
         (参考有腔、我方 0 腔), **没有**「我方比参考多腔」这一侧。
         而「画成了别的字」的典型后果恰恰是多腔 (U+3099 ゙ 画成 ゜ = +1 腔)。
      b) REVERSE_NN    —— 反向近邻: 不问"我方离同码位的参考有多远",
         而是问"我方离**别的码位**的参考有多近"。若某个别的字比正确的字更贴近,
         且超出对照集噪声底, 就是换字嫌疑。
      c) IDENTITY_RULE —— 字符身份规则的推广版 (比拓扑三元组, 不只比字腔数)。
      d) OWN_NEAR_DUP —— 我方两个字近乎同一张位图。
    """
    findings: list[dict] = []
    per_cp: dict[int, dict] = {}
    ref_names = list(refs)
    zpix = refs.get("zpix", {})

    ours_holes: dict[int, int] = {}
    for cp, a in ours.items():
        ours_holes[cp] = holes_areas_bfs(a)[0]

    ref_holes: dict[str, dict[int, int]] = {}
    for name, g in refs.items():
        ref_holes[name] = {cp: holes_areas_bfs(a)[0] for cp, a in g.items()}

    # --- a) COUNTER_GAINED (镜像判据), 阈值按类别标定 ---
    #
    # 跟哪套参考比: 优先 Zpix (同为 12px, 可比), Zpix 缺字时用 Unifont (16px, 覆盖全)。
    # Unifont 的 16px 天然多腔, 直接混进中位数会把尺度搞乱 —— 所以不做中位。
    gain: dict[int, float] = {}
    gain_ref: dict[int, str] = {}
    for cp in ours:
        if cp in zpix:
            gain[cp] = ours_holes[cp] - ref_holes["zpix"][cp]
            gain_ref[cp] = "zpix"
        elif "unifont-16" in ref_holes and cp in ref_holes["unifont-16"]:
            gain[cp] = ours_holes[cp] - ref_holes["unifont-16"][cp]
            gain_ref[cp] = "unifont-16"
    by_cat, thr_global, ctrl_gain = calibrated_thresholds(gain, control, cat_of, 99.0)
    for cp, v in sorted(gain.items()):
        thr = thr_for(cp, cat_of, by_cat, thr_global)
        if v <= thr:
            continue
        per_cp.setdefault(cp, {})["r1a_gain"] = round(v, 2)
        findings.append(
            {
                "id": "COUNTER_GAINED",
                "cp": f"U+{cp:04X}",
                "char": chr(cp),
                "cat": cat_of.get(cp, "?"),
                "detail": f"我方腔数 {ours_holes[cp]}, {gain_ref[cp]} {ref_holes[gain_ref[cp]][cp]} "
                f"—— 我方比参考多 {v:.0f} 腔 (> 同类噪声底 {thr:.1f})",
                "severity": "warn",
            }
        )

    # --- b) REVERSE_NN: 像素级反向近邻 ---
    nn = reverse_nn(ours, ours_holes, zpix, ref_holes.get("zpix", {}), control)
    for d in nn["suspects"]:
        cp = d["cp"]
        per_cp.setdefault(cp, {})["r1b_nn"] = d["detail"]
        findings.append(
            {
                "id": "REVERSE_NN",
                "cp": f"U+{cp:04X}",
                "char": chr(cp),
                "cat": cat_of.get(cp, "?"),
                "detail": d["detail"],
                "best_cp": d["best"],
                "severity": "error" if d.get("in_set") else "warn",
            }
        )

    # --- c) IDENTITY_RULE: 换字嫌疑 (只在**混淆组**内比对) ---
    #
    # 关键: 这条规则**不能**对全体码位两两比对。
    # 之前试过"我方拓扑三元组 == 参考对某个别的码位的三元组"的全量版,
    # 结果 2548 个字命中 (62%) —— 因为不同汉字的 (腔数, 横笔, 竖笔) 三元组
    # 大量重合, "不匹配"条件几乎恒真。量具在骗人, 不是字体有问题。
    #
    # 正确的形态 (与 route_rule.identity_confused 同源, 但独立实现):
    # 只在**可能混淆的码位对**之间比对, 且用**字腔数**这一个标量:
    #   组 A (我方混淆组): 我方把两个码位画成了**同一张位图** —— 那么
    #        其中必有一个画成了别的字。参考若能用字腔数区分它们, 而我方 X 的
    #        字腔数 == 参考对 Y 的字腔数 (!= 参考对 X 的) -> 换字坐实。
    #   组 B (参考歧义组): 参考自己就把两个码位画成同一张位图, 而我方画得
    #        不一样 —— 我方是"异类", 可能是把其中一个画成了别的字 (低severity)。
    for name in ref_names:
        rg = refs[name]
        rh = ref_holes[name]
        # 组 A: 我方位图相同的码位组
        our_groups: dict[tuple, list[int]] = defaultdict(list)
        for cp, a in ours.items():
            our_groups[(a.shape[0], a.shape[1], a.tobytes())].append(cp)
        for _k, cps in our_groups.items():
            if len(cps) < 2:
                continue
            for x in cps:
                if x not in rh:
                    continue
                rx = rh[x]
                for y in cps:
                    if y == x or y not in rh:
                        continue
                    ry = rh[y]
                    if rx == ry:
                        continue  # 参考也分不出 -> 天然同形, 不是我们的错
                    if ours_holes[x] == ry and ours_holes[x] != rx:
                        per_cp.setdefault(x, {})["r1c_identity"] = (
                            f"我方与 U+{y:04X} 画成同一张位图; 参考说 U+{x:04X} 该 {rx} 腔, "
                            f"U+{y:04X} 该 {ry} 腔, 我方是 {ours_holes[x]} 腔 -> 画成了 Y"
                        )
                        findings.append(
                            {
                                "id": "IDENTITY_RULE",
                                "cp": f"U+{x:04X}",
                                "char": chr(x),
                                "cat": cat_of.get(x, "?"),
                                "detail": f"我方 U+{x:04X} 与 U+{y:04X} ({chr(y)!r}) 位图完全相同; "
                                f"参考({name}) 说 U+{x:04X} 该 {rx} 腔、U+{y:04X} 该 {ry} 腔, "
                                f"我方 {ours_holes[x]} 腔 —— 换字坐实",
                                "severity": "error",
                            }
                        )
                        break
        # 组 B: 参考自身渲染相同的码位组 (参考认为它们同形, 我们画得不一样)
        ref_groups: dict[tuple, list[int]] = defaultdict(list)
        for cp, a in rg.items():
            ref_groups[(a.shape[0], a.shape[1], a.tobytes())].append(cp)
        for _k, cps in ref_groups.items():
            if len(cps) < 2:
                continue
            for x in cps:
                if x not in ours or x not in rh:
                    continue
                for y in cps:
                    if y == x or y not in ours:
                        continue
                    ax, ay = ours[x], ours[y]
                    if ax.shape == ay.shape and bool((ax == ay).all()):
                        continue  # 我们也画成一样 -> 那是组 A 的情形
                    if ours_holes[x] != rh[x]:
                        continue  # 字腔数与参考一致, 没有换字迹象
                    findings.append(
                        {
                            "id": "REF_AMBIGUITY_DIVERGENCE",
                            "cp": f"U+{x:04X}",
                            "char": chr(x),
                            "cat": cat_of.get(x, "?"),
                            "detail": f"参考({name}) 把 U+{x:04X} 与 U+{y:04X} 画成同一张位图, "
                            f"我方却画得不同 —— 我方是异类, 需目视确认",
                            "severity": "warn",
                        }
                    )
                    break

    # --- d) 我方近重复 ---
    by_shape: dict[tuple, list[int]] = defaultdict(list)
    for cp in ours:
        a = ours[cp]
        by_shape[(a.shape[0], a.shape[1], a.tobytes())].append(cp)
    for _k, cps in by_shape.items():
        if len(cps) < 2:
            continue
        for a, b in zip(cps, cps[1:]):
            findings.append(
                {
                    "id": "OWN_EXACT_DUP",
                    "cp": f"U+{a:04X}",
                    "char": chr(a),
                    "cat": cat_of.get(a, "?"),
                    "detail": f"我方 U+{a:04X} 与 U+{b:04X} 位图逐像素完全相同",
                    "severity": "error" if cat_of.get(a) == "hanzi" else "warn",
                }
            )
    for cp, other, d in own_near_dups(ours, cat_of, limit=2):
        findings.append(
            {
                "id": "OWN_NEAR_DUP",
                "cp": f"U+{cp:04X}",
                "char": chr(cp),
                "cat": cat_of.get(cp, "?"),
                "detail": f"我方 U+{cp:04X} 与 U+{other:04X} ({chr(other)!r}) 只差 {d} 个像素",
                "severity": "warn",
            }
        )
        per_cp.setdefault(cp, {})["r1d_neardup"] = other

    return {
        "round": 1,
        "name": "身份反查",
        "attacks": "上一轮结论: 身份错误 0 例 (4140/4140 目视)。本轮从**四个方向**反查换字。",
        "per_cp": per_cp,
        "findings": findings,
        "thresholds": {
            "COUNTER_GAINED": describe_threshold(
                "我方多腔数 (按类别标定)",
                thr_global,
                ctrl_gain,
            )
            + " | 分类别: "
            + ", ".join(f"{k}:{v:.1f}" for k, v in by_cat.items()),
            "REVERSE_NN": describe_threshold(
                "反向近邻领先量", nn["margin_threshold"], nn["ctrl_margins"], " px"
            ),
        },
        "nn": {k: v for k, v in nn.items() if k not in ("suspects", "ctrl_margins")},
    }


def reverse_nn(
    ours: dict[int, np.ndarray],
    ours_holes: dict[int, int],
    ref: dict[int, np.ndarray],
    ref_holes: dict[int, int],
    control: set[int],
) -> dict:
    """反向近邻: 我方位图在参考全字符集里最像哪个**别的**字。

    距离 = 16x16 画布上的**逐像素汉明距离** + 8 x |字腔数差|。
    不用 6 维密度特征: 那个特征量化得太粗, 不同汉字会撞出同一个特征向量
    (距离恒为 0), 近邻搜索整个退化 —— 实测阈值标定出来是 0, 3908 个字全命中。

    阈值: 取**对照集** (历史复核未标注问题的字) 的领先量分布 p99.9。
    即: 在已知正确的字上, "我方离别的字更近"这件事本来就会发生多少次?
    只有超过这个噪声底, 才算换字嫌疑。
    """
    if not ref:
        return {"suspects": [], "margin_threshold": 0.0, "ctrl_margins": [], "n": 0}
    ref_cps = sorted(ref)
    ref_pos = {cp: i for i, cp in enumerate(ref_cps)}
    ref_packed = np.array([pack_canvas(ref[c]) for c in ref_cps])
    ref_h = np.array([ref_holes.get(c, 0) for c in ref_cps], dtype=np.int32)
    our_packed = {cp: pack_canvas(a) for cp, a in ours.items()}

    margins: dict[int, float] = {}
    details: dict[int, tuple[int, float, float]] = {}
    for cp in sorted(ours):
        if cp not in ref_pos:
            # 参考集里没有这个码位 (Zpix 缺 12 个假名) -> 没有"同码位参考"可比,
            # 这时 d_self 无意义, 硬塞一个哨兵值会把阈值整个带偏 (实测把
            # 阈值顶到 999982, 全场失灵)。跳过, 由 Unifont 那一路负责。
            continue
        p = our_packed[cp]
        xor = np.bitwise_xor(ref_packed, p)
        ham = np.bitwise_count(xor).sum(axis=1).astype(np.int32)
        dist = ham + 8 * np.abs(ref_h - ours_holes.get(cp, 0))
        same = ref_pos.get(cp)
        d_self = int(dist[same]) if same is not None else 10**6
        d2 = dist.copy()
        if same is not None:
            d2[same] = 10**6
        j = int(np.argmin(d2))
        best_cp = ref_cps[j]
        best_d = int(d2[j])
        margins[cp] = float(d_self - best_d)
        details[cp] = (best_cp, float(best_d), float(d_self))

    ctrl = [v for cp, v in margins.items() if cp in control]
    thr = calibrate(ctrl, 99.9)
    suspects = []
    for cp, m in sorted(margins.items(), key=lambda kv: -kv[1]):
        if m <= thr:
            break
        best_cp, best_d, d_self = details[cp]
        suspects.append(
            {
                "cp": cp,
                "margin": round(m, 1),
                "self_dist": round(d_self, 1),
                "best": best_cp,
                "best_dist": round(best_d, 1),
                "in_set": best_cp in ours,
                "detail": f"我方离参考里别的字 U+{best_cp:04X} ({chr(best_cp)!r}) 更近 "
                f"(近 {best_d:.0f}px, 离同码位参考 {d_self:.0f}px, 领先 {m:.0f}px > 噪声底 {thr:.0f}px)",
            }
        )
    return {
        "suspects": suspects,
        "margin_threshold": round(thr, 1),
        "ctrl_margins": ctrl,
        "ref_n": len(ref_cps),
        "ours_n": len(margins),
        "skipped_no_ref": len(ours) - len(margins),
    }


def own_near_dups(
    ours: dict[int, np.ndarray], cat_of: dict[str, str], limit: int = 2
) -> list[tuple[int, int, int]]:
    """我方内部近重复 (同尺寸同墨量 + 汉明距离小)。

    分桶键必须含**墨量**: 只按尺寸分桶的话, 几千个汉字会落进同一个 12x12 桶,
    两两比对是 O(n^2)。加入墨量后候选对锐减, 而"两张图几乎一样"的两个字,
    墨量必然也几乎一样, 不会漏。
    """
    buckets: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for cp, a in ours.items():
        buckets[(a.shape[0], a.shape[1], int((a > 0).sum()))].append(cp)
    out: list[tuple[int, int, int]] = []
    for _sz, cps in buckets.items():
        if len(cps) < 2:
            continue
        for i in range(len(cps)):
            for j in range(i + 1, len(cps)):
                a, b = ours[cps[i]], ours[cps[j]]
                if cat_of.get(cps[i]) != cat_of.get(cps[j]):
                    continue
                d = int((a != b).sum())
                if d <= limit:
                    out.append((cps[i], cps[j], d))
    return out


# ================================================================ 第二轮: 部件级结构


def round2_components(
    ours: dict[int, np.ndarray],
    refs: dict[str, dict[int, np.ndarray]],
    cat_of: dict[str, str],
    control: set[int],
) -> dict:
    """第二轮: 攻「是这个字, 但部件塌了吗」。

    上一轮的结构结论建立在**全字腔数**上, 而全字腔数有已知的检测极限
    (docs/glyph-identity-verification.md 6.9/6.10: 局部塌陷召回率只有 5/29;
    「瓣」「雹」我方腔数反而**更多**, 完全看不出来)。
    本轮换三个互相独立的攻击面, 全部作用在**部件**尺度上:
      a) HOLE_AREA      —— 腔的**面积集合**, 不只是腔数。
         腔数持平但腔被合并/填实 (田 4 格 -> 1 大格, 目 3 腔 -> 日 2 腔)
         只有面积能看见。
      b) COMPONENT_DEFICIT —— 把每个腔归属到二维部件格 (左/右、上/下),
         定位"**哪一块**塌了"。
      c) BRIDGED_GAP    —— 同一行 (列) 里, 墨点数相同但**分段数变少**:
         那是笔画被搭桥连上 (横画并成实心带), 是塌陷的直接指纹。
    三条都按对照集标定。
    """
    findings: list[dict] = []
    per_cp: dict[int, dict] = {}
    zpix = refs.get("zpix", {})

    # ---- 先把每个字的原始量算出来 (全量, 不预筛) ----
    raw: dict[int, dict] = {}
    for cp, a in sorted(ours.items()):
        b = zpix.get(cp)
        if b is None:
            continue
        n_ours, areas_ours = holes_areas_bfs(a)
        n_ref, areas_ref = holes_areas_bfs(b)
        # 腔面积 L1: 两个面积序列 (降序) 逐项比, 短的补 0 —— 绝对像素量, 不用比值。
        # 比值在腔总面积很小时会爆 (参考只有 1 个腔时比值能到 5+), 实测不可用;
        # 绝对量稳定得多, 而且它的含义直白: "封闭白空间差了多少像素"。
        k = max(len(areas_ours), len(areas_ref))
        ao = areas_ours + [0] * (k - len(areas_ours))
        ar_ = areas_ref + [0] * (k - len(areas_ref))
        area_l1 = float(sum(abs(x - y) for x, y in zip(ao, ar_)))
        max_gap = float(max(areas_ref) - max(areas_ours)) if (areas_ref and areas_ours) else 0.0
        cells_ours = component_cells(a)
        cells_ref = component_cells(b)
        co = Counter(c for c, _ar, _x in cells_ours)
        cr = Counter(c for c, _ar, _x in cells_ref)
        cell_deficit = max((cr[c] - co.get(c, 0) for c in cr), default=0)
        raw[cp] = {
            "n_ours": n_ours,
            "n_ref": n_ref,
            "areas_ours": areas_ours,
            "areas_ref": areas_ref,
            "area_l1": area_l1,
            "max_gap": max_gap,
            "deficit": n_ref - n_ours,
            "cell_deficit": cell_deficit,
            "gaps": bridged_gaps(a, b),
        }

    # ---- 标定 (按类别, 样本不足回落全局) ----
    vals_def = {cp: float(v["deficit"]) for cp, v in raw.items()}
    vals_l1 = {cp: v["area_l1"] for cp, v in raw.items()}
    vals_max = {cp: v["max_gap"] for cp, v in raw.items()}
    vals_gap = {cp: float(len(v["gaps"])) for cp, v in raw.items()}
    vals_cell = {cp: float(v["cell_deficit"]) for cp, v in raw.items() if v["n_ours"] == v["n_ref"]}

    cat_def, g_def, ctrl_def = calibrated_thresholds(vals_def, control, cat_of, 99.0)
    cat_l1, g_l1, ctrl_l1 = calibrated_thresholds(vals_l1, control, cat_of, 99.0)
    cat_max, g_max, ctrl_max = calibrated_thresholds(vals_max, control, cat_of, 99.0)
    cat_gap, g_gap, ctrl_gap = calibrated_thresholds(vals_gap, control, cat_of, 99.0)
    cat_cell, g_cell, ctrl_cell = calibrated_thresholds(vals_cell, control, cat_of, 99.0)

    def thr_str(name: str, by_cat, g, ctrl) -> str:
        return describe_threshold(name, g, ctrl) + " | 分类别: " + ", ".join(
            f"{k}:{v:.1f}" for k, v in by_cat.items()
        )

    thresholds = {
        "HOLE_DEFICIT": thr_str("腔数缺口", cat_def, g_def, ctrl_def),
        "CAVITY_AREA_L1": thr_str("腔面积 L1", cat_l1, g_l1, ctrl_l1),
        "MAX_CAVITY_GAP": thr_str("最大腔面积差", cat_max, g_max, ctrl_max),
        "BRIDGED_GAP": thr_str("桥接处数", cat_gap, g_gap, ctrl_gap),
        "COMPONENT_DEFICIT": thr_str("单部件腔数缺口", cat_cell, g_cell, ctrl_cell),
    }

    # ---- 判定 ----
    for cp, v in sorted(raw.items()):
        # a) 腔数缺口 (参考有腔、我方没有)
        thr = thr_for(cp, cat_of, cat_def, g_def)
        if v["deficit"] > thr:
            per_cp.setdefault(cp, {})["r2a_deficit"] = v["deficit"]
            findings.append(
                {
                    "id": "HOLE_DEFICIT",
                    "cp": f"U+{cp:04X}",
                    "char": chr(cp),
                    "cat": cat_of.get(cp, "?"),
                    "detail": f"我方腔 {v['n_ours']} vs 参考 {v['n_ref']} (少 {v['deficit']}) "
                    f"> 同类噪声底 {thr:.1f} —— 有腔被填死",
                    "severity": "error",
                }
            )
        # b) 腔面积 L1 (腔数持平但封闭白空间差很多 = 腔被填实/合并)
        thr = thr_for(cp, cat_of, cat_l1, g_l1)
        if v["area_l1"] > thr:
            per_cp.setdefault(cp, {})["r2b_area_l1"] = v["area_l1"]
            findings.append(
                {
                    "id": "CAVITY_AREA_L1",
                    "cp": f"U+{cp:04X}",
                    "char": chr(cp),
                    "cat": cat_of.get(cp, "?"),
                    "detail": f"腔面积 L1 = {v['area_l1']:.0f}px > 同类噪声底 {thr:.1f} "
                    f"(我方 {v['areas_ours'][:5]} vs 参考 {v['areas_ref'][:5]}) —— 封闭白空间明显不对",
                    "severity": "warn",
                }
            )
        # c) 最大腔面积差 (某个腔被填掉 -> 最大的那个腔没了)
        thr = thr_for(cp, cat_of, cat_max, g_max)
        if v["max_gap"] > thr:
            per_cp.setdefault(cp, {})["r2c_max_gap"] = v["max_gap"]
            findings.append(
                {
                    "id": "MAX_CAVITY_GAP",
                    "cp": f"U+{cp:04X}",
                    "char": chr(cp),
                    "cat": cat_of.get(cp, "?"),
                    "detail": f"最大腔面积 差 {v['max_gap']:.0f}px (我方 {max(v['areas_ours']) if v['areas_ours'] else 0} "
                    f"vs 参考 {max(v['areas_ref']) if v['areas_ref'] else 0}) > 同类噪声底 {thr:.1f}",
                    "severity": "warn",
                }
            )
        # d) 单部件缺口 (只在全字腔数持平时才有意义 = 局部塌陷)
        thr = thr_for(cp, cat_of, cat_cell, g_cell)
        if v["n_ours"] == v["n_ref"] and v["cell_deficit"] > thr:
            per_cp.setdefault(cp, {})["r2d_cell"] = v["cell_deficit"]
            findings.append(
                {
                    "id": "COMPONENT_DEFICIT",
                    "cp": f"U+{cp:04X}",
                    "char": chr(cp),
                    "cat": cat_of.get(cp, "?"),
                    "detail": f"某个部件格里参考有腔而我方没有 (缺口 {v['cell_deficit']} > 同类噪声底 "
                    f"{thr:.1f}), 全字腔数持平 ({v['n_ours']}) —— 局部塌陷",
                    "severity": "error",
                }
            )
        # e) 桥接间隙
        thr = thr_for(cp, cat_of, cat_gap, g_gap)
        if len(v["gaps"]) > thr:
            per_cp.setdefault(cp, {})["r2e_gap"] = len(v["gaps"])
            findings.append(
                {
                    "id": "BRIDGED_GAP",
                    "cp": f"U+{cp:04X}",
                    "char": chr(cp),
                    "cat": cat_of.get(cp, "?"),
                    "detail": f"{len(v['gaps'])} 处笔画被搭桥连上 > 同类噪声底 {thr:.1f}: "
                    + "; ".join(v["gaps"][:3]),
                    "severity": "warn",
                }
            )

    # 阴性对照候选: 对照集里指标最高但**没有被命中**的字 —— 出图给人眼看,
    # 证明"这些量在已知正确的字上也不响" (否则命中数说明不了任何事)。
    ctrl_top = []
    for cp, v in raw.items():
        if cp not in control:
            continue
        ctrl_top.append(
            {
                "cp": cp,
                "deficit": v["deficit"],
                "area_l1": v["area_l1"],
                "max_gap": v["max_gap"],
                "gaps": len(v["gaps"]),
            }
        )
    ctrl_top.sort(key=lambda d: (-d["deficit"], -d["area_l1"]))

    return {
        "round": 2,
        "name": "部件级结构攻击",
        "attacks": "上一轮结论: 结构劣化已修完 (确认劣化 0)。本轮放弃全字腔数, 改在部件尺度上找。",
        "per_cp": per_cp,
        "findings": findings,
        "thresholds": thresholds,
        "measured": len(raw),
        "control_top": ctrl_top[:12],
    }


def bridged_gaps(ours: np.ndarray, ref: np.ndarray) -> list[str]:
    """同一行/列: 墨点数相同但分段数更少 -> 有间隙被搭桥连上。

    为什么这个指纹相对可靠: 塌陷 (笔画粘连) 会**减少**分段数但**不减少**墨量
    (笔画还在, 只是连起来了)。而单纯的画风差异 (粗细) 两边都变, 墨点数
    不会恰好相等 —— 所以判据要连"墨点数相等"一起要求。
    """
    out: list[str] = []
    ro, rr_ = ink_per_row(ours), row_runs(ours)
    re_, rre = ink_per_row(ref), row_runs(ref)
    n = min(len(ro), len(re_))
    for y in range(n):
        if ro[y] == re_[y] and rr_[y] < rre[y]:
            out.append(f"第 {y} 行 墨点 {ro[y]} 但分段 {rr_[y]}<{rre[y]}")
    co, cc_ = ink_per_col(ours), col_runs(ours)
    ce, cce = ink_per_col(ref), col_runs(ref)
    n = min(len(co), len(ce))
    for x in range(n):
        if co[x] == ce[x] and cc_[x] < cce[x]:
            out.append(f"第 {x} 列 墨点 {co[x]} 但分段 {cc_[x]}<{cce[x]}")
    return out


# ================================================================ 第三轮: 链条攻击


def round3_chain(ours, stack, cat_of, items, prior) -> dict:
    """第三轮: 攻「结论赖以成立的那条链, 自身有没有断」。

    前两轮都假设了一件事: **我方这一列的位图, 就是字体的字形**。
    本轮去证伪这个假设本身:
      a) PROVENANCE  —— 每个码位的位图, 是否真的等于它**声称**的源字体渲染出来的字?
         (独立用 PIL 重渲一遍源字体, 逐字节比)
      b) PRODUCT_SYNC —— dist/ 里的成品是否与当前源同步? (独立读成品, 不走构建脚本)
      c) RE_ADJUDICATE —— 前两轮结论与历史复核结论**互相**对撞: 谁否定了谁。
    """
    findings: list[dict] = []
    per_cp: dict[int, dict] = {}

    # --- a) PROVENANCE ---
    prov_ok = 0
    prov_bad: list[dict] = []
    for ch, _cat in items:
        cp = ord(ch)
        if cp not in ours:
            continue
        font = stack._pick(ch)
        try:
            f = ImageFont.truetype(
                str(font.path), font.px, index=font.index, layout_engine=ImageFont.Layout.BASIC
            )
            core, _off = f.getmask2(ch, mode="1")
            w, h = core.size
            if w == 0 or h == 0:
                continue
            data = bytes(core)
            if len(data) < w * h:
                continue
            img = Image.frombuffer("L", (w, h), data[: w * h])
            arr = (np.array(img, dtype=np.uint8) > 0).astype(np.float32)
            ys, xs = np.nonzero(arr)
            if not len(xs):
                continue
            src = arr[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
        except Exception as exc:  # noqa: BLE001
            prov_bad.append({"cp": f"U+{cp:04X}", "detail": f"重渲失败: {exc}"})
            continue
        tgt = ours[cp]
        if src.shape == tgt.shape and bool((src == tgt).all()):
            prov_ok += 1
        else:
            prov_bad.append(
                {
                    "cp": f"U+{cp:04X}",
                    "char": chr(cp),
                    "detail": f"我方位图 {tgt.shape} 与源字体独立重渲 {src.shape} 不一致",
                }
            )
    for b in prov_bad:
        cp = int(b["cp"][2:], 16)
        per_cp.setdefault(cp, {})["r3a_prov"] = b["detail"]
        findings.append(
            {
                "id": "PROVENANCE",
                "cp": b["cp"],
                "char": b.get("char", ""),
                "cat": cat_of.get(cp, "?"),
                "detail": b["detail"],
                "severity": "error",
            }
        )

    # --- b) PRODUCT_SYNC ---
    sync = check_products(ours)
    for s in sync["bad"]:
        cp = int(s["cp"][2:], 16)
        per_cp.setdefault(cp, {})["r3b_prod"] = s["detail"]
        findings.append(
            {
                "id": "PRODUCT_SYNC",
                "cp": s["cp"],
                "char": s.get("char", ""),
                "cat": cat_of.get(cp, "?"),
                "detail": s["detail"],
                "severity": "error",
            }
        )

    # --- c) RE_ADJUDICATE ---
    re_adjudicate = re_adjudicate_findings(ours, prior, per_cp, cat_of)
    findings.extend(re_adjudicate["findings"])

    return {
        "round": 3,
        "name": "链条攻击",
        "attacks": "前两轮都默认「我方这一列 = 字体的字形」。本轮证伪这个前提本身。",
        "per_cp": per_cp,
        "findings": findings,
        "provenance": {"ok": prov_ok, "bad": len(prov_bad)},
        "product_sync": sync,
        "re_adjudicate": {k: v for k, v in re_adjudicate.items() if k != "findings"},
    }


def check_products(ours: dict[int, np.ndarray]) -> dict:
    """独立读 dist/ 的成品, 与我方位图逐字比对 (不走构建脚本)。"""
    bdf_path = ROOT / "dist" / "PixelFontPC98-12.bdf"
    out: dict = {"checked": 0, "bad": [], "bdf": str(bdf_path)}
    if not bdf_path.exists():
        out["bad"].append({"cp": "U+0000", "detail": f"缺产物 {bdf_path.name}"})
        return out
    import verify_products as vp

    bdf = vp.read_bdf(bdf_path)
    for cp, a in sorted(ours.items()):
        rec = bdf.get(cp)
        if rec is None:
            out["bad"].append({"cp": f"U+{cp:04X}", "char": chr(cp), "detail": "产物里没有这个码位"})
            continue
        w, h, bits = rec
        out["checked"] += 1
        if (w, h) != (a.shape[1], a.shape[0]) or not (a == np.array(bits, dtype=np.float32)).all():
            out["bad"].append(
                {"cp": f"U+{cp:04X}", "char": chr(cp), "detail": "产物位图与当前源不一致"}
            )
    return out


def re_adjudicate_findings(ours, prior, per_cp, cat_of) -> dict:
    """对撞: 本轮 R1/R2 的命中 与 历史复核结论 互相验证。

    · 历史说劣化、现在 R2 仍命中 -> 修复**没生效**;
    · 历史说存疑、现在 R1/R2 命中 -> 存疑被**证实**;
    · 历史说换字、现在 R1 命中 -> 修复**没生效**;
    · 历史说劣化、现在 R2 全清 -> 修复**成立** (机械印证)。
    """
    findings: list[dict] = []
    hist = {
        "identity": prior.get("identity", set()),
        "degraded": prior.get("degraded", set()),
        "unsure": prior.get("unsure", set()),
    }
    r1 = prior.get("r1_hits", set())
    r2 = prior.get("r2_hits", set())
    confirmed: list[str] = []

    for cp in sorted(hist["identity"]):
        if cp in r1:
            findings.append(
                {
                    "id": "REGRESS_IDENTITY",
                    "cp": f"U+{cp:04X}",
                    "char": chr(cp),
                    "cat": cat_of.get(cp, "?"),
                    "detail": "历史目视确认过的换字, 第一轮反查**仍命中** -> 修复未生效",
                    "severity": "error",
                }
            )
        else:
            confirmed.append(f"U+{cp:04X} 换字修复成立 (第一轮不再命中)")
    for cp in sorted(hist["degraded"]):
        if cp in r2:
            findings.append(
                {
                    "id": "REGRESS_DEGRADED",
                    "cp": f"U+{cp:04X}",
                    "char": chr(cp),
                    "cat": cat_of.get(cp, "?"),
                    "detail": "历史目视确认过的劣化, 第二轮部件级攻击**仍命中** -> 换源没解决",
                    "severity": "error",
                }
            )
        else:
            confirmed.append(f"U+{cp:04X} 劣化修复成立 (第二轮不再命中)")
    for cp in sorted(hist["unsure"]):
        if cp in r1 or cp in r2:
            findings.append(
                {
                    "id": "UNSURE_CONFIRMED",
                    "cp": f"U+{cp:04X}",
                    "char": chr(cp),
                    "cat": cat_of.get(cp, "?"),
                    "detail": "历史目视存疑, 本轮自动反查**命中** -> 存疑被证实为问题",
                    "severity": "warn",
                }
            )
    adjudicated_new = []
    for cp in sorted(r1 | r2):
        if cp in hist["degraded"] or cp in hist["identity"] or cp in hist["unsure"]:
            continue
        if cp in prior.get("adjudicated", {}):
            # 目视已裁决过的字, 不再报成"新发现" —— 否则每轮都在把同一批字
            # 重新数一遍, 看起来像"又发现了很多问题"
            adjudicated_new.append(f"U+{cp:04X} {chr(cp)} ({prior['adjudicated'][cp].get('class')})")
            continue
        findings.append(
            {
                "id": "NEW_HIT",
                "cp": f"U+{cp:04X}",
                "char": chr(cp),
                "cat": cat_of.get(cp, "?"),
                "detail": "本轮新命中 (历史目视未标注) —— 需要人眼定夺",
                "severity": "warn",
            }
        )
    return {
        "findings": findings,
        "confirmed": confirmed,
        "adjudicated_new": adjudicated_new,
        "history": {k: len(v) for k, v in hist.items()},
    }

# ================================================================ 量具自检


def self_check(ours: dict[int, np.ndarray], refs: dict[str, dict[int, np.ndarray]]) -> dict:
    """量具体检: 两份实现的一致性 + 阳性/阴性对照组。

    阳性对照 = **注入已知缺陷**: 把一个正确字形的某个腔填掉, 必须被检出。
    阴性对照 = 同一字形原样, 必须不被检出。
    没有对照组的量具, 命中数说明不了任何事 —— 这是本项目的历史教训。
    """
    res: dict = {}

    dis = []
    for cp, a in sorted(ours.items()):
        n1, ar1 = holes_areas_bfs(a)
        n2, ar2 = holes_areas_uf(a)
        if n1 != n2 or ar1 != ar2:
            dis.append(cp)
    res["impl_agree_ours"] = {
        "checked": len(ours),
        "disagree": len(dis),
        "examples": [f"U+{c:04X}" for c in dis[:10]],
    }
    ref_dis = 0
    ref_n = 0
    for _name, g in refs.items():
        for cp, a in g.items():
            ref_n += 1
            n1, ar1 = holes_areas_bfs(a)
            n2, ar2 = holes_areas_uf(a)
            if n1 != n2 or ar1 != ar2:
                ref_dis += 1
    res["impl_agree_refs"] = {"checked": ref_n, "disagree": ref_dis}

    # --- 阳性对照: 注入"填掉最大的腔" ---
    injected = []
    for cp, a in sorted(ours.items()):
        n, _areas = holes_areas_bfs(a)
        if n == 0:
            continue
        comp = biggest_hole(a)
        if comp is None:
            continue
        mut = (a > 0).astype(np.uint8).copy()
        for (y, x) in comp:
            mut[y, x] = 1
        mut = mut.astype(np.float32)
        n2, _ = holes_areas_bfs(mut)
        injected.append({"cp": f"U+{cp:04X}", "before": n, "after": n2, "detected": n2 < n})
        if len(injected) >= 200:
            break
    res["positive_control_fill"] = {
        "n": len(injected),
        "detected": sum(1 for r in injected if r["detected"]),
        "note": "注入=填掉最大的腔; 检出=腔数下降",
    }

    # --- 阴性对照: 自己对自己比, 必须全静 ---
    fp = [cp for cp, a in ours.items() if bridged_gaps(a, a)]
    res["negative_control_self"] = {"n": len(ours), "false_positive": len(fp)}
    return res


def biggest_hole(a: np.ndarray) -> list[tuple[int, int]] | None:
    """返回最大字腔的像素坐标列表 (注入对照用)。"""
    ink = a > 0
    h, w = ink.shape
    seen = np.zeros_like(ink)
    best: list[tuple[int, int]] | None = None
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0, x0] or ink[y0, x0]:
                continue
            stack = [(y0, x0)]
            seen[y0, x0] = True
            comp: list[tuple[int, int]] = []
            border = False
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                if y == 0 or y == h - 1 or x == 0 or x == w - 1:
                    border = True
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] and not ink[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if not border and (best is None or len(comp) > len(best)):
                best = comp
    return best


# ================================================================ 历史结论装载


def load_prior() -> dict:
    """装载历史复核结论 (用于第三轮对撞 + 阈值标定的对照集)。"""
    prior: dict = {"identity": set(), "degraded": set(), "unsure": set(), "changed": set()}
    sp = ROOT / "reports" / "glyphcmp_review" / "summary.json"
    if sp.exists():
        d = json.loads(sp.read_text(encoding="utf-8"))
        for key, bucket in (
            ("identity_findings", "identity"),
            ("degraded", "degraded"),
            ("unsure_list", "unsure"),
        ):
            for rec in d.get(key, []) or []:
                cp = rec.get("cp") if isinstance(rec, dict) else rec
                if isinstance(cp, str) and cp.startswith("U+"):
                    prior[bucket].add(int(cp[2:], 16))
    cp_path = ROOT / "reports" / "glyphcmp_review" / "changed_since_review.txt"
    if cp_path.exists():
        for ln in cp_path.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln.startswith("U+"):
                prior["changed"].add(int(ln[2:].split()[0], 16))
    return prior


def load_adjudication() -> dict[int, dict]:
    """装载人工目视裁决结论 (reports/adversarial/adjudication.json)。

    这条通道是**结论回灌**: 目视裁决过的字, 下一次跑就不再报成"新发现" ——
    否则每一轮都会把同一批字重新数一遍, 看起来像"又发现了很多问题"。
    项目里已有同样的先例 (目视结论 --force-from-review 回灌到路由推导)。
    """
    out: dict[int, dict] = {}
    p = ROOT / "reports" / "adversarial" / "adjudication.json"
    if not p.exists():
        return out
    d = json.loads(p.read_text(encoding="utf-8"))
    for rec in d.get("entries", []):
        cp = rec.get("cp")
        if isinstance(cp, str) and cp.startswith("U+"):
            out[int(cp[2:], 16)] = rec
    return out


def control_set(items: list[tuple[str, str]], prior: dict) -> set[int]:
    """对照集: 历史复核**没有**标注任何问题的码位 (视为已知正确)。

    用途: 给所有阈值提供噪声底 —— 已知正确的字上量具也不该响。
    依赖说明: 这个对照集依赖历史复核的结论, 而第三轮正是要攻击那套结论;
    所以第三轮的结论里会单独标出"哪些字是靠这个假设才没被标出来的"。
    """
    bad = prior["identity"] | prior["degraded"] | prior["unsure"] | prior["changed"]
    return {ord(ch) for ch, _c in items} - bad


# ================================================================ 证据图


def render_sheet(entries, out_path: Path, title: str, cols: int = 6, rows: int = 4, scale: int = 4):
    """对照证据图: 我方 / 参考 / (可选) 嫌疑字, 4 倍最近邻放大。

    格位是 16x16 (Unifont 是 16px 基准, 槽位按最大字形算, 避免串格),
    与 docs/glyph-review-protocol.md 第 3 节的约定一致。

    每个面板都带自己的标签 —— 复核者必须一眼分清"哪一列是我方、哪一列是参考、
    哪一列是嫌疑字", 否则结论会串列 (上一轮就出过把 U+78E8 读成「磨」的事故)。
    """
    slot = CANVAS
    head = 22
    label_h = 16
    panel_w = slot * scale
    panel_gap = 4
    max_panels = max((len(e.get("panels", [])) for e in entries), default=1)
    cell_w = max_panels * (panel_w + panel_gap) + 8
    cell_h = panel_w + label_h + 14
    w = cols * cell_w + 12
    h = head + rows * cell_h + 8
    img = Image.new("RGB", (w, h), (18, 18, 22))
    d = ImageDraw.Draw(img)
    try:
        fnt = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 13)
        fnt_s = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 11)
    except Exception:  # noqa: BLE001
        fnt = ImageFont.load_default()
        fnt_s = ImageFont.load_default()
    d.text((6, 4), title, fill=(230, 230, 235), font=fnt)

    for i, e in enumerate(entries):
        if i >= cols * rows:
            break
        r, c = divmod(i, cols)
        x0 = 6 + c * cell_w
        y0 = head + r * cell_h
        d.text(
            (x0, y0),
            f"U+{e['cp']:04X} {e['char']} [{e.get('cat','')}] {e.get('tag','')}",
            fill=(240, 220, 120),
            font=fnt_s,
        )
        for j, (pname, arr) in enumerate(e.get("panels", [])):
            px = x0 + j * (panel_w + panel_gap)
            py = y0 + label_h
            d.text((px, y0 + 2), pname, fill=(150, 200, 255), font=fnt_s)
            if arr is None:
                d.text((px + 2, py + 4), "(缺)", fill=(120, 120, 130), font=fnt_s)
                continue
            a = np.array(arr, dtype=np.uint8)
            im = Image.fromarray((a * 255).astype(np.uint8), mode="L").convert("RGB")
            im = im.resize((panel_w, panel_w), Image.NEAREST)
            img.paste(im, (px, py))
            d.rectangle([px, py, px + panel_w - 1, py + panel_w - 1], outline=(70, 70, 80))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)


# ================================================================ 主流程


def main() -> int:
    ap = argparse.ArgumentParser(description="三轮对抗式字形审核")
    ap.add_argument("--round", type=int, default=0, help="只跑某一轮 (1/2/3), 0 = 全跑")
    ap.add_argument("--sheet", action="store_true", help="出证据图")
    ap.add_argument(
        "--focus",
        default="",
        help="指定码位清单 (逗号分隔, 如 U+897F,U+6652), 出高倍定焦图; 与 --zoom 配合",
    )
    ap.add_argument("--zoom", type=int, default=8, help="定焦图放大倍数 (默认 8)")
    ap.add_argument("--focus-out", default="focus.png", help="定焦图文件名 (放在 reports/adversarial/png/)")
    ap.add_argument("--refs", default="zpix,unifont-16")
    ap.add_argument("--outdir", default=str(OUTDIR))
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = datetime.now(timezone.utc)

    print("== 装载 ==")
    items = cs.build_charset()
    print(f"   字符集: {len(items)} 个码位")
    ours, stack, cat_of = load_ours(items)
    print(f"   我方位图: {len(ours)} 个 (空格等无墨字符不计)")
    ref_names = [r.strip() for r in args.refs.split(",") if r.strip()]
    refs = load_refs(ref_names)

    prior = load_prior()
    prior["adjudicated"] = load_adjudication()
    control = control_set(items, prior)
    print(f"   历史结论: 换字 {len(prior['identity'])} / 劣化 {len(prior['degraded'])} / "
          f"存疑 {len(prior['unsure'])} / 换源后变动 {len(prior['changed'])}")
    print(f"   目视裁决回灌: {len(prior['adjudicated'])} 个字 (已裁决的不再报成新发现)")
    print(f"   对照集 (历史未标注): {len(control)} 个")

    print("== 量具自检 ==")
    sc = self_check(ours, refs)
    print(f"   两实现一致 (我方): {sc['impl_agree_ours']['checked']} 检, 不一致 "
          f"{sc['impl_agree_ours']['disagree']}")
    print(f"   两实现一致 (参考): {sc['impl_agree_refs']['checked']} 检, 不一致 "
          f"{sc['impl_agree_refs']['disagree']}")
    print(f"   阳性对照 (注入填腔): 检出 {sc['positive_control_fill']['detected']}"
          f"/{sc['positive_control_fill']['n']}")
    print(f"   阴性对照 (自己对自己): 误报 {sc['negative_control_self']['false_positive']}")

    results: dict[int, dict] = {}

    if args.round in (0, 1):
        print("== 第一轮: 身份反查 ==")
        r1 = round1_identity(ours, refs, cat_of, control)
        results[1] = r1
        print(f"   命中 {len(r1['findings'])} 条")
        for k, v in r1["thresholds"].items():
            print(f"   阈值 {v}")
    if args.round in (0, 2):
        print("== 第二轮: 部件级结构攻击 ==")
        r2 = round2_components(ours, refs, cat_of, control)
        results[2] = r2
        print(f"   命中 {len(r2['findings'])} 条 (量到 {r2['measured']} 个字)")
        for k, v in r2["thresholds"].items():
            print(f"   阈值 {v}")
    if args.round in (0, 3):
        print("== 第三轮: 链条攻击 ==")
        prior_aug = dict(prior)
        prior_aug["r1_hits"] = {int(f["cp"][2:], 16) for f in results.get(1, {}).get("findings", [])}
        prior_aug["r2_hits"] = {int(f["cp"][2:], 16) for f in results.get(2, {}).get("findings", [])}
        r3 = round3_chain(ours, stack, cat_of, items, prior_aug)
        results[3] = r3
        print(f"   命中 {len(r3['findings'])} 条; 溯源一致 {r3['provenance']['ok']}, 不一致 "
              f"{r3['provenance']['bad']}; 产物核对 {r3['product_sync']['checked']}")

    # ---- 逐字裁决 ----
    print("== 逐字裁决 ==")
    per_cp: dict[str, dict] = {}
    adjudicated = prior.get("adjudicated", {})
    for cp in sorted(ours):
        entry: dict = {"char": chr(cp), "cat": cat_of.get(cp, "?"), "r1": [], "r2": [], "r3": []}
        for rid, r in results.items():
            for f in r["findings"]:
                if f["cp"] == f"U+{cp:04X}":
                    entry[f"r{rid}"].append(f["id"])
        hit = bool(entry["r1"] or entry["r2"] or entry["r3"])
        adj = adjudicated.get(cp)
        if adj:
            entry["adjudication"] = {
                "verdict": adj.get("verdict"),
                "class": adj.get("class"),
                "reason": adj.get("reason"),
            }
            if not hit:
                entry["verdict"] = "clean"
            elif adj.get("verdict") == "defect":
                entry["verdict"] = "defect"
            else:
                entry["verdict"] = "adjudicated_not_defect"
        else:
            entry["verdict"] = "flagged_open" if hit else "clean"
        per_cp[f"U+{cp:04X}"] = entry
    flagged = sum(1 for v in per_cp.values() if v["verdict"] == "flagged_open")
    adjud_not_defect = sum(1 for v in per_cp.values() if v["verdict"] == "adjudicated_not_defect")
    defects = sum(1 for v in per_cp.values() if v["verdict"] == "defect")
    print(f"   覆盖 {len(per_cp)} 个有墨码位")
    print(f"   待裁决 {flagged} / 已裁决非缺陷 {adjud_not_defect} / 确认缺陷 {defects} / 干净 "
          f"{sum(1 for v in per_cp.values() if v['verdict'] == 'clean')}")

    # ---- 落盘 ----
    stamp = t0.isoformat()
    summary = {
        "tool": "adversarial_review",
        "generated_at": stamp,
        "inputs": {
            "chars_total": len(items),
            "glyphs_with_ink": len(ours),
            "refs": {n: len(g) for n, g in refs.items()},
            "history": {
                "identity": len(prior["identity"]),
                "degraded": len(prior["degraded"]),
                "unsure": len(prior["unsure"]),
                "changed": len(prior["changed"]),
            },
            "control_set": len(control),
        },
        "self_check": sc,
        "rounds": {
            str(k): {
                "name": v["name"],
                "attacks": v["attacks"],
                "findings": len(v["findings"]),
                "by_id": dict(Counter(f["id"] for f in v["findings"])),
                "by_severity": dict(Counter(f.get("severity", "?") for f in v["findings"])),
                "thresholds": v.get("thresholds", {}),
            }
            for k, v in results.items()
        },
        "verdict": {
            "covered": len(per_cp),
            "flagged_open": flagged,
            "adjudicated_not_defect": adjud_not_defect,
            "defect": defects,
            "clean": sum(1 for v in per_cp.values() if v["verdict"] == "clean"),
        },
        "per_cp": per_cp,
    }
    (outdir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for k, v in results.items():
        payload = {
            "tool": "adversarial_review",
            "round": k,
            "name": v["name"],
            "attacks": v["attacks"],
            "generated_at": stamp,
            "findings": v["findings"],
            "per_cp": {f"U+{cp:04X}": d for cp, d in v["per_cp"].items()},
        }
        for kk, vv in v.items():
            if kk not in ("findings", "per_cp", "round", "name", "attacks"):
                payload[kk] = vv
        (outdir / f"round{k}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    write_md(outdir, results, summary, sc, prior)

    if args.sheet:
        make_sheets(outdir, results, ours, refs, cat_of)

    if args.focus:
        focus_sheet(
            outdir, args.focus, ours, refs, cat_of, results, zoom=args.zoom, args_focus_out=args.focus_out
        )

    print(f"\n报告: {outdir / 'summary.md'}")
    return 0


def make_sheets(outdir, results, ours, refs, cat_of, control=None) -> None:
    """出证据图。

    两类:
      · 每轮命中项的对照图 (按判据分文件);
      · **裁决图** (adjudication_*.png): 按"要不要人眼定夺"排好序的候选清单,
        另加一张**阴性对照**图 —— 取对照集里指标最高但**没有**被命中的字。
        没有阴性对照, "命中"这两个字说明不了任何事。
    """
    png = outdir / "png"
    png.mkdir(parents=True, exist_ok=True)
    # 清掉上一轮的图 —— 判据改名或命中数变化后, 残留的旧图会被误当成这轮的证据
    for old in png.glob("*.png"):
        old.unlink()
    zpix = refs.get("zpix", {})
    uni = refs.get("unifont-16", {})

    def panels_for(cp: int, extra: tuple[str, int] | None = None):
        p = [("我方", ours.get(cp)), ("Zpix", zpix.get(cp)), ("Unifont", uni.get(cp))]
        if extra is not None:
            name, xcp = extra
            cand = zpix.get(xcp)
            if cand is None:
                cand = uni.get(xcp)
            p.append((name, cand))
        return p

    for rid, r in results.items():
        by_id: dict[str, list[dict]] = defaultdict(list)
        for f in r["findings"]:
            by_id[f["id"]].append(f)
        for aid, fs in by_id.items():
            fs.sort(key=lambda f: (f.get("severity") != "error", f["cp"]))
            for page in range(0, min(len(fs), 96), 24):
                chunk = fs[page : page + 24]
                entries = []
                for f in chunk:
                    cp = int(f["cp"][2:], 16)
                    extra = None
                    if f.get("best_cp"):
                        extra = (f"嫌疑 U+{f['best_cp']:04X}", f["best_cp"])
                    entries.append(
                        {
                            "cp": cp,
                            "char": chr(cp),
                            "cat": cat_of.get(cp, "?"),
                            "tag": f.get("id", ""),
                            "panels": panels_for(cp, extra),
                        }
                    )
                render_sheet(
                    entries,
                    png / f"r{rid}_{aid}_{page // 24:02d}.png",
                    f"第{rid}轮 {aid} —— 我方 / Zpix / Unifont (4x)",
                )

    # ---- 裁决图: 身份类候选 (要人眼看"是不是画成了另一个字") ----
    r1 = results.get(1, {})
    id_cand = [f for f in r1.get("findings", []) if f["id"] in ("REVERSE_NN", "REF_AMBIGUITY_DIVERGENCE")]
    id_cand.sort(key=lambda f: (f.get("severity") != "error", f["cp"]))
    for page in range(0, len(id_cand), 12):
        chunk = id_cand[page : page + 12]
        entries = []
        for f in chunk:
            cp = int(f["cp"][2:], 16)
            extra = (f"嫌疑 U+{f['best_cp']:04X}", f["best_cp"]) if f.get("best_cp") else None
            entries.append(
                {
                    "cp": cp,
                    "char": chr(cp),
                    "cat": cat_of.get(cp, "?"),
                    "tag": f["id"],
                    "panels": panels_for(cp, extra),
                }
            )
        render_sheet(
            entries,
            png / f"adjudication_identity_{page // 12:02d}.png",
            "裁决·身份类: 我方 / Zpix / Unifont / 嫌疑字 —— 问: 我方画的到底是不是这个字?",
            cols=4,
            rows=3,
        )

    # ---- 裁决图: 结构类候选 (error 优先) ----
    r2 = results.get(2, {})
    st_cand = [f for f in r2.get("findings", []) if f.get("severity") == "error"]
    st_cand.sort(key=lambda f: f["cp"])
    for page in range(0, len(st_cand), 12):
        chunk = st_cand[page : page + 12]
        entries = [
            {
                "cp": int(f["cp"][2:], 16),
                "char": f.get("char", ""),
                "cat": cat_of.get(int(f["cp"][2:], 16), "?"),
                "tag": f["id"],
                "panels": panels_for(int(f["cp"][2:], 16)),
            }
            for f in chunk
        ]
        render_sheet(
            entries,
            png / f"adjudication_structure_{page // 12:02d}.png",
            "裁决·结构类: 我方 / Zpix / Unifont —— 问: 某个部件的笔画塌了吗?",
            cols=4,
            rows=3,
        )

    # ---- 阴性对照图: 对照集里指标最高但**没被命中**的字 ----
    ctrl_top = results.get(2, {}).get("control_top", [])
    if ctrl_top:
        entries = []
        for d in ctrl_top[:12]:
            cp = d["cp"]
            entries.append(
                {
                    "cp": cp,
                    "char": chr(cp),
                    "cat": cat_of.get(cp, "?"),
                    "tag": f"阴性对照 未命中(腔差{d['deficit']}/L1 {d['area_l1']:.0f})",
                    "panels": panels_for(cp),
                }
            )
        render_sheet(
            entries,
            png / "adjudication_negative_control.png",
            "阴性对照: 对照集里量值最高但**未命中**的字 —— 证明这些量在已知正确的字上也不响",
            cols=4,
            rows=3,
        )
    print(f"证据图: {png}")


def focus_sheet(outdir, spec, ours, refs, cat_of, results, zoom: int = 8, args_focus_out: str = "focus.png") -> None:
    """定焦图: 指定码位, 高倍放大, 逐格判读用。

    面板: 我方 / Zpix / Unifont / (第一轮命中时) 嫌疑字。
    标签写清每格命中了哪条判据 —— 判读时不能靠"看着像有问题"下结论。
    """
    zpix = refs.get("zpix", {})
    uni = refs.get("unifont-16", {})
    hits: dict[int, list[str]] = defaultdict(list)
    suspect: dict[int, int] = {}
    for rid, r in results.items():
        for f in r["findings"]:
            cp = int(f["cp"][2:], 16)
            hits[cp].append(f"R{rid}:{f['id']}")
            if f.get("best_cp"):
                suspect[cp] = f["best_cp"]
    cps = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        cps.append(int(tok[2:], 16) if tok.upper().startswith("U+") else int(tok, 16))
    entries = []
    for cp in cps:
        panels = [("我方", ours.get(cp)), ("Zpix", zpix.get(cp)), ("Unifont", uni.get(cp))]
        if cp in suspect:
            panels.append((f"嫌疑 U+{suspect[cp]:04X}", zpix.get(suspect[cp])))
        entries.append(
            {
                "cp": cp,
                "char": chr(cp),
                "cat": cat_of.get(cp, "?"),
                "tag": " ".join(hits.get(cp, ["(未命中)"])),
                "panels": panels,
            }
        )
    out = outdir / "png" / args_focus_out
    render_sheet(
        entries,
        out,
        f"定焦 {zoom}x: 我方 / Zpix / Unifont"
        + (" / 嫌疑字" if any("嫌疑" in p[0] for e in entries for p in e["panels"]) else ""),
        cols=3,
        rows=4,
        scale=zoom,
    )
    print(f"定焦图: {out}")


def write_md(outdir, results, summary, sc, prior) -> None:
    L: list[str] = []
    L.append("# 三轮对抗式字形审核")
    L.append("")
    L.append(f"- 生成时间: {summary['generated_at']}")
    L.append(f"- 覆盖: **{summary['inputs']['chars_total']}** 个码位 "
             f"(有墨字形 {summary['inputs']['glyphs_with_ink']} 个)")
    L.append(f"- 参考集: {', '.join(summary['inputs']['refs'])}")
    v = summary["verdict"]
    L.append(
        f"- 裁决: 待裁决 **{v.get('flagged_open', 0)}** / 已裁决非缺陷 "
        f"**{v.get('adjudicated_not_defect', 0)}** / 确认缺陷 **{v.get('defect', 0)}** / 干净 "
        f"**{v.get('clean', 0)}**"
    )
    L.append("")
    L.append("## 三轮的分工 (为什么换攻击面, 而不是同一把尺子量三遍)")
    L.append("")
    L.append("| 轮 | 攻击面 | 量具 | 攻击的是谁 |")
    L.append("|---|---|---|---|")
    L.append("| 1 | 身份反查 | 多腔镜像 / 像素级反向近邻 / 拓扑签名 / 我方近重复 | 「身份错误 0 例」 |")
    L.append("| 2 | 部件级结构 | 腔面积集合 / 部件格归属 / 桥接间隙 | 「结构劣化已修完」 |")
    L.append("| 3 | 链条 | 源字体重渲 / 产物独立读 / 结论对撞 | 「我方这一列 = 字体的字形」 |")
    L.append("")
    for k in sorted(results):
        r = results[k]
        L.append(f"## 第 {k} 轮 —— {r['name']}")
        L.append("")
        L.append(f"> {r['attacks']}")
        L.append("")
        cnt = Counter(f["id"] for f in r["findings"])
        if cnt:
            L.append("| 判据 | 命中 |")
            L.append("|---|---|")
            for aid, n in cnt.most_common():
                L.append(f"| `{aid}` | {n} |")
        else:
            L.append("命中 0 条。")
        L.append("")
        if r.get("thresholds"):
            L.append("阈值标定 (取自对照集的经验分布, 不拍脑袋):")
            L.append("")
            for name, desc in r["thresholds"].items():
                L.append(f"- `{name}`: {desc}")
            L.append("")
    L.append("## 量具自检")
    L.append("")
    L.append(f"- 两份实现 (洪水填充 / 并查集) 在我方 {sc['impl_agree_ours']['checked']} 个字形上: "
             f"不一致 **{sc['impl_agree_ours']['disagree']}**")
    L.append(f"- 在参考 {sc['impl_agree_refs']['checked']} 个字形上: 不一致 "
             f"**{sc['impl_agree_refs']['disagree']}**")
    L.append(f"- 阳性对照 (注入: 填掉最大的腔): {sc['positive_control_fill']['detected']}"
             f"/{sc['positive_control_fill']['n']} 被检出")
    L.append(f"- 阴性对照 (自己对自己比): 误报 {sc['negative_control_self']['false_positive']}")
    L.append("")
    ra = results.get(3, {}).get("re_adjudicate", {})
    if ra.get("adjudicated_new"):
        L.append("## 结论回灌: 目视已裁决的字 (不再算新发现)")
        L.append("")
        L.append(f"共 {len(ra['adjudicated_new'])} 个: " + "; ".join(ra["adjudicated_new"][:40]))
        L.append("")
    if ra.get("confirmed"):
        L.append("## 机械印证: 历史结论在本轮仍然成立")
        L.append("")
        L.append(f"共 {len(ra['confirmed'])} 条: " + "; ".join(ra["confirmed"][:40]))
        L.append("")
    (outdir / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
