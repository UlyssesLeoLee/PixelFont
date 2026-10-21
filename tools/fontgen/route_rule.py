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
FALLBACK = "ark"


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


def choose_forced(
    cands: dict[str, tuple[int, int, int] | None],
    ref: tuple[int, int, int],
    w: float = HOLE_WEIGHT,
) -> tuple[str | None, tuple[int, int, int] | None]:
    """强制选源 (目视复核确认劣化时用): 腔数**封顶到参考值**后取最大的, 再按距离决胜。

    为什么不能直接用 choose: 裁判是 Ark 主导的 (median(Ark, Fusion, Zpix)),
    所以"离裁判最近的"对被判给 Ark 的字等于"总是选 Ark" —— 循环论证。
    而"腔最多的"也不对: 腔比参考**多**是错不是好 (「瓣」「雹」我方腔数反比参考多),
    所以超出参考的那部分不能算分。封顶后再按距离决胜, 既不循环, 也不奖励过度。

    调用方: 推导脚本 (目视结论作为输入) 与构建门禁 (复算这条规则) 共用本函数。
    """
    avail = [(name, s) for name, s in cands.items() if s is not None]
    if not avail:
        return None, None
    ref_h = ref[0]

    def _score(s: tuple[int, int, int]) -> tuple[int, float]:
        return (min(s[0], ref_h), -dist(s, ref, w))

    return max(avail, key=lambda c: _score(c[1]))


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
