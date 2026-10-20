"""字符集定义 + 全集缺字门禁。

汉字集的选择理由（重要）:
    用户点的是"常用汉字 3500"。我无法可靠地凭记忆写出《通用规范汉字表》一级
    3500 字表 —— 凭记忆列字表就是编造, 而字库缺字是不可见的故障。
    所以改用 GB2312 一级汉字 3755 字: 它可以由 gb2312 编码器机械推导
    (0xB0A1-0xD7F9), 完全可复现、可验证, 且在实践中就是"最常用字"的集合。
    与 3500 常用字表有几十个字的差异, 已在交付说明里写明。

假名集覆盖: 平假名 / 片假名 / 半角片假名 / 促音与长音符 / 々〆〇ヶ。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bitfont import BitmapFont, ScriptStack  # noqa: E402
from coverage import cmap_for  # noqa: E402

SIMHEI = r"C:\Windows\Fonts\simhei.ttf"
MSGOTHIC = r"C:\Windows\Fonts\msgothic.ttc"

# 显式排除的码位, 每一条都必须写明原因。
# 这不是"修到门禁变绿", 而是把已知的字体缺字变成写在代码里的既定事实。
EXCLUDE: dict[int, str] = {
    0x3097: "゗ — 古旧假名合字, 非 JIS 字集, MS Gothic 无此字形, 现代用途为零",
    0x3098: "゘ — 古旧假名合字, 非 JIS 字集, MS Gothic 无此字形, 现代用途为零",
}


def gb2312_level1() -> list[str]:
    """GB2312 一级汉字 (区位 16-55 区, 3755 字), 按 GB2312 码位顺序 = 拼音序。"""
    out: list[str] = []
    for hi in range(0xB0, 0xD8):
        for lo in range(0xA1, 0xFF):
            try:
                out.append(bytes((hi, lo)).decode("gb2312"))
            except UnicodeDecodeError:
                continue
    return out


def ascii_chars() -> list[str]:
    return [chr(c) for c in range(0x20, 0x7F)]


def kana_chars() -> list[str]:
    blocks = [
        range(0x3041, 0x30A0),  # 平假名
        range(0x30A0, 0x3100),  # 片假名
        range(0xFF61, 0xFFA0),  # 半角片假名
    ]
    out: list[str] = []
    for b in blocks:
        for cp in b:
            if cp in EXCLUDE:
                continue
            out.append(chr(cp))
    out += ["々", "〆", "〇", "ヶ", "ー", "～"]
    return out


def extras() -> list[str]:
    """游戏里高频但不属于三大块的符号与标点。"""
    return list("·—…、。，．！？；：（）【】「」『』《》〈〉～－＋×÷＝％＄￥＃＆＠")


def build_charset() -> list[tuple[str, str]]:
    """返回 [(字符, 分类)]，顺序即 atlas / 字体 cmap 的建议顺序。"""
    items: list[tuple[str, str]] = []
    items += [(c, "ascii") for c in ascii_chars()]
    items += [(c, "punct") for c in extras()]
    items += [(c, "kana") for c in kana_chars()]
    items += [(c, "hanzi") for c in gb2312_level1()]
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for ch, cat in items:
        if ch not in seen:
            seen.add(ch)
            out.append((ch, cat))
    return out


def build_stack() -> ScriptStack:
    """B 方向: 汉字/标点走 SimHei 12, 拉丁与假名走 MS Gothic 12。

    双源的基线必须一致 —— 这是加在这里的硬门禁, 不是运行时才发现的巧合:
    两个源的 ascent/descent 一旦不同 (换字体版本、换源字体就会发生), 假名会比
    汉字高一格, 混排整行错位, 而且这种错位在单语样张里完全看不出来。
    """
    stack = ScriptStack(
        ideo=BitmapFont(path=SIMHEI, index=0, px=12),
        non_ideo=BitmapFont(path=MSGOTHIC, index=0, px=12),
    )
    a, b = stack.ideo.metrics, stack.non_ideo.metrics
    if (a.ascent, a.descent) != (b.ascent, b.descent):
        raise SystemExit(
            f"双源基线不一致: 汉字源 {a.ascent}/{a.descent} vs 拉丁源 {b.ascent}/{b.descent} "
            f"—— 混排会错行, 拒绝构建"
        )
    return stack


def gate_full_coverage(stack: ScriptStack, items: list[tuple[str, str]]) -> None:
    """全集缺字门禁: 每一个字符, 路由到的源字体必须有该字形。

    像素字体没有回退 —— 缺一个字就是一块豆腐, 而且在大字库里几乎不可能
    靠肉眼发现。所以这里逐字符查 cmap, 有一个不过就中止构建。
    """
    ideo_cps = cmap_for(stack.ideo.path, stack.ideo.index)
    non_cps = cmap_for(stack.non_ideo.path, stack.non_ideo.index)
    missing: list[str] = []
    for ch, _ in items:
        cps = non_cps if stack._pick(ch) is stack.non_ideo else ideo_cps
        if ord(ch) not in cps:
            missing.append(f"{ch!r} U+{ord(ch):04X} @ {stack._pick(ch).name}")
    if missing:
        head = "\n  ".join(missing[:40])
        raise SystemExit(
            f"缺字门禁未通过, 共 {len(missing)} 个字符缺字形:\n  {head}"
            + ("\n  ..." if len(missing) > 40 else "")
        )


def main() -> None:
    items = build_charset()
    stack = build_stack()
    m = stack.metrics
    print(f"网格 {m.cell_w}x{m.cell_h}  半角 {m.half_w}  基线 {m.ascent}/{m.descent}")
    print(f"字符总数 {len(items)}")
    for cat in ("ascii", "punct", "kana", "hanzi"):
        n = sum(1 for _, c in items if c == cat)
        print(f"  {cat:<6} {n}")
    gate_full_coverage(stack, items)
    print("缺字门禁: 通过 (全部字符在对应源字体中均有字形)")


if __name__ == "__main__":
    main()
