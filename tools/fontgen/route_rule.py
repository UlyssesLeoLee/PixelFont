"""路由选源规则 —— **推导脚本与构建门禁共用同一份实现**。

为什么必须共用:
    推导时用一套判据挑源, 门禁再用另一套判据复核"当初那个选择还成不成立",
    两套判据一旦漂移, 门禁就是在检查一件不存在的事 ——
    门禁会一直报"切源理由不成立", 而真实原因���判据自己改过。
    同理, 诊断工具 (explain_route.py) 也必须用这个模块,
    否则它给出的解释会和构建结果打架。

判据 (两���, 依次):
    1. 字腔硬约束: 参考字体的这个字有腔 (ref_holes >= 1), 而某个候选源渲染出
       0 腔 (整字塌成白块), 而另一个候选源有腔 —— **必须**选有腔的那个,
       不看笔画数差多少。
       理由: 0 腔是**可见的硬错误**, 笔画数差只是画风差异。
    2. 距离: 距离 = w×|字腔差| + |竖笔差| + |横笔差|, 取最小。
       w = 4 (标定得出): 字腔是**拓扑量**, 不受字宽与分辨率影响;
       横/竖笔画分段数对参考字体的分辨率与字宽天然有偏, 故权重低于字腔。
       但笔画分段数**不能删** —— 纯字腔优先会丢掉羹/霍这类
       "腔数本来就对、塌的是笔画"的字 (实测确认劣化从 20/21 掉到 18/21)。

距离的量必须是**绝对量**:
    z-score 的尺度 (MAD) 会随分布集中而收紧, 字体变好 -> 分布变集中 ->
    MAD 变小 -> 同样倍数标准差对应的绝对偏差门槛跟着收紧 -> 离群数不降反升。
    实测: 换成逐字选源后绝对阈值 |差|>=12 的汉字从 204 降到 63,
    而 z-score 判据的命中数却从 17 涨到 151 —— 那是量具在骗人。
"""

from __future__ import annotations

HOLE_WEIGHT = 4.0

# 双源: 主力来源。兜底源只在双源都画不出时才参与竞争。
PRIMARY = ("ideo", "non_ideo")
FALLBACK = "fusion"


def need_fallback(
    cands: dict[str, tuple[int, int, int] | None],
    ref: tuple[int, int, int],
) -> bool:
    """要不要让兜底源 (Ark Pixel) 参与竞争。

    两种情形:
        a) non_ideo 根本没有这个字形 —— MS Gothic 是 JIS 汉字的点阵,
           简体专有字一个都没有; 那就只剩 SimHei 的平滑轮廓可用,
           而它在 12px 下会把整字糊成白块 (实测 24 个汉字)。
        b) 两个源都渲染出 0 腔 (整字白块) 而参考说该字有腔。

    为什么不是"三个源全程竞争": 那会让 Ark Pixel 接管 3440 个汉字 (92%),
    字体画风整体从"SimHei 栅格化 + PC-98 点阵"变成"现代中文像素字体为主"。
    实测 C4 规则已做到 汉字白块 0 / 确认劣化 29/29 全覆盖, 剩下 2440 个字
    没有必要动。
    """
    ideo = cands.get("ideo")
    non = cands.get("non_ideo")
    if non is None:
        return True
    if ref[0] >= 1 and ideo is not None and ideo[0] == 0 and non[0] == 0:
        return True
    return False


def build_pool(
    cands: dict[str, tuple[int, int, int] | None],
    ref: tuple[int, int, int],
) -> dict[str, tuple[int, int, int] | None]:
    """按 C4 规则挑出**参与竞争**的候选源。

    推导脚本与构建门禁都必须走这里 —— 门禁要用**同一条**规则复算
    "当初那个选择现在还成不成立", 两边规则漂移的话, 门禁检查的就是
    一件不存在的事。
    """
    pool: dict[str, tuple[int, int, int] | None] = {k: cands.get(k) for k in PRIMARY}
    if need_fallback(pool, ref):
        pool[FALLBACK] = cands.get(FALLBACK)
    return pool


def sig_of(img) -> tuple[int, int, int] | None:
    """字形结构签名: (字腔数, 竖笔画分段数, 横笔画分段数)。

    字腔 = 4 邻域下被墨迹完全包围的白区连通分量数, 按墨迹**外接矩形**计;
    任何碰到外接矩形上下左右任一边界的白区**不算腔** (那是外部背景)。

    这个定义必须各工具一致 —— 2026-10-21 曾因为两个实现对"贴边区域"的
    处理不同, 800 次比较里 667 次不一致, 差点把一份错的腔数表当成证据。
    """
    from bitfont import count_holes, count_runs

    holes = count_holes(img)
    col = count_runs(img, "col")
    row = count_runs(img, "row")
    return (holes, col, row)


def dist(s: tuple[int, int, int], t: tuple[int, int, int], w: float = HOLE_WEIGHT) -> float:
    """结构距离。w 是字腔项的权重 (见模块文档)。"""
    return w * abs(s[0] - t[0]) + abs(s[1] - t[1]) + abs(s[2] - t[2])


def identity_confused(
    our_holes: int,
    ref_holes_x: int | None,
    ref_holes_y: int | None,
) -> bool:
    """我方是不是把码位 X 画成了另一个码位 Y?

    三个条件都要满足, 否则不动:
      1. 参照字体对 X 与 Y 的**字腔数不同** —— 参照能区分这两个码位。
         (如果参照也画成同一个, 那就是该尺寸下天然同形, 不是我们的错。)
      2. 我方 X 的字腔数 == 参照对 **Y** 的字腔数 —— 说明我方画出来的是 Y 那一侧。
      3. 我方 X 的字腔数 != 参照对 X 的字腔数 —— 参照说 X 不是这样。

    实例: U+3099 ゙(浊点) 与 U+309C ゜(半浊点) —— MS Gothic 把两个都画成 3x3 的圈,
    参照说 ゙ 该是 0 腔(两撇)而 ゜ 是 1 腔(圈)。我方 ゙ 是 1 腔 == 参照的 ゜
    -> 我方把浊点画成了半浊点, 属于**画错了字符**, 必须换源。

    为什么要这条: 距离判据在这类情形上完全失效 —— 画错的字符与对的字符
    结构上就是同一个, 距离自然也是 0。
    """
    if ref_holes_x is None or ref_holes_y is None:
        return False
    if ref_holes_x == ref_holes_y:
        return False
    return our_holes == ref_holes_y and our_holes != ref_holes_x


def choose_forced(
    cands: dict[str, tuple[int, int, int] | None],
    ref: tuple[int, int, int],
    w: float = HOLE_WEIGHT,
) -> tuple[str | None, tuple[int, int, int] | None]:
    """强制选源 (目视复核确认劣化时用): 取离参照**最近**的可用源, 但不许选白块源。

    硬约束照旧: 参照说有腔, 而某个源渲染出 0 腔 (整字白块) 时, 不能选它。

    为什么不用"腔数封顶后取最大"那个排序:
        腔比参照**多**是错不是好 (「瓣」「雹」我方腔数反比参照多), 而按腔数排序
        会把"只差 1 个腔、但离参照更远"的源选上。
        实例「嘎」U+560E: MS Gothic 腔 4 离参照 31, SimHei 腔 3 离参照 30 ——
        两个源都画不好「戛」的「自」(Zpix 才画得出), 换过去只是把"一样差"变成
        "略微更远", 那就不该换。

    参照是 Ark 主导的 (median(Ark, Fusion, Zpix)), 所以"离参照最近"对被判给 Ark 的字
    等于"总是选 Ark" —— 这一条靠**独立参考 Zpix 复核**兜底:
        实测被强制换源的字里, Zpix 独立认可 Ark 腔数的有 7 个, 其余 6 个虽然
        腔数不同, 但 Ark 离 Zpix 仍然更近 (例:「嗓」Ark 13 vs SimHei 34)。

    调用方: 推导脚本 (目视结论作为输入) 与构建门禁 (复算这条规则) 共用本函数。
    """
    avail = [(name, s) for name, s in cands.items() if s is not None]
    if not avail:
        return None, None
    if ref[0] >= 1:
        keep = [c for c in avail if c[1][0] >= 1]
        if keep:
            avail = keep
    return min(avail, key=lambda c: dist(c[1], ref, w))


def choose(
    cands: dict[str, tuple[int, int, int] | None],
    ref: tuple[int, int, int],
    w: float = HOLE_WEIGHT,
) -> tuple[str | None, tuple[int, int, int] | None]:
    """按规则挑源。返回 (源名, 签名); 无可用候选时返回 (None, None)。

    cands: 源名 -> 该源渲染这个字的签名; None 表示"这个源没有这个字形"
            (调用方必须**先查 cmap**, 不能靠渲染结果判断 ——
             缺字时 FreeType 画 .notdef 空心豆腐块, 自带 1 个腔,
             会把"缺字"误判成"能画"。
    tie-break: 距离相同时按 cands 的插入顺序取第一个 (调用方把汉字源放最前,
             即"平手时保持原样", 不引入不必要的风格差异)。
    """
    avail = [(name, s) for name, s in cands.items() if s is not None]
    if not avail:
        return None, None
    if ref[0] >= 1:
        keep = [c for c in avail if c[1][0] >= 1]
        if keep:
            avail = keep
    best = min(avail, key=lambda c: dist(c[1], ref, w))
    return best
