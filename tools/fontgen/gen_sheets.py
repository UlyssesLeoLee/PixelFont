"""生成候选设计方向的规格样张。

候选表是被 coverage.py 的实测结果逼出来的:
    MS Gothic / MS Mincho / Meiryo / Yu Gothic / BIZ UDMincho  -> 简体仅 56.5% (缺 国/戏/币/买…)
    SimSun / SimHei / Microsoft YaHei                          -> 中日英 100%
像素字体没有回退机制, 所以"源字体覆盖"是设计决策的第一约束, 不是实现细节。
双源栈 (汉字走 SimHei, 假名/拉丁走 MS Gothic) 用来保住 80 年代的拉丁观感。

覆盖的决策轴: 网格 (8/10/12/16) x 骨架 (黑体/宋体) x 描边 (细/粗) x 源策略 (单源/双源)。
全部走同一管线, 只有这些参数不同 —— 差异一定来自设计本身。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image  # noqa: E402

from bitfont import BitmapFont, ScriptStack, measure_density  # noqa: E402
from coverage import cmap_for  # noqa: E402
from sheet import ALL_SAMPLE_CHARS, Candidate, render  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "preview"

MSGOTHIC = r"C:\Windows\Fonts\msgothic.ttc"
SIMSUN = r"C:\Windows\Fonts\simsun.ttc"
SIMHEI = r"C:\Windows\Fonts\simhei.ttf"

FULL = "简中 100% · 日本語 100% · ASCII 100%"


def build() -> list[tuple[Candidate, int, int]]:
    gothic12 = BitmapFont(path=MSGOTHIC, index=0, px=12)
    simhei12 = BitmapFont(path=SIMHEI, index=0, px=12)
    specs = [
        Candidate(
            id="A",
            name="12px 黑体 · 硬边",
            tagline="单源 · 等宽 1px 描边 · 最接近 DOS/PC-98 汉字游戏默认字",
            accent=(127, 209, 255),
            font=simhei12,
            coverage=FULL,
            notes=[
                "方笔黑体, 笔画粗细恒为 1 格, 三款黑体里最\"机器\"的一种",
                "单源保证汉字与假名字重统一; 代价是拉丁字母偏现代, 少一分 80 年代味",
            ],
        ),
        Candidate(
            id="B",
            name="12px 双源 · PC-98 混血",
            tagline="汉字=SimHei 12 + 假名/拉丁=MS Gothic 12 · 拉丁观感最正",
            accent=(96, 226, 255),
            font=ScriptStack(ideo=simhei12, non_ideo=gothic12),
            coverage=FULL + " (双源)",
            notes=[
                "MS Gothic 的 6px 拉丁正是 PC-98 / 日文游戏的原生点阵, 换成它一眼回到 80 年代",
                "双源意味着汉字与拉丁的字面大小、字重不完全一致 —— 这是本款唯一要接受的取舍",
            ],
        ),
        Candidate(
            id="C",
            name="12px 横细竖粗宋体",
            tagline="单源 · \"枫叶镇 / 红色警戒\"那一代的记忆点",
            accent=(255, 209, 102),
            font=BitmapFont(path=SIMSUN, index=0, px=12),
            coverage=FULL,
            notes=[
                "宋体骨架带来横竖对比, 12px 下辨识度最高, 情绪最接近国产老游戏",
                "偏\"怀旧国产\"而非街机; 密集横画在极小字号会粘连",
            ],
        ),
        Candidate(
            id="D",
            name="16px 宋体 · 大网格",
            tagline="单源 · 16x16, 国产游戏汉字主流 (传奇/奇迹MU 时代)",
            accent=(255, 158, 92),
            font=BitmapFont(path=SIMSUN, index=0, px=16),
            coverage=FULL,
            notes=[
                "格子大一倍, 承载量宽裕, 长句正文不累眼",
                "若目标是 PC 对话框/剧情文本, 这一款的空间最舒服",
            ],
        ),
        Candidate(
            id="E",
            name="16px 黑体 · 最粗仍可用",
            tagline="单源 · 已实测: 16px 格子放不下 2px 描边, 黑体本体的粗度就是上限",
            accent=(255, 122, 122),
            font=BitmapFont(path=SIMHEI, index=0, px=16),
            coverage=FULL,
            notes=[
                "实测证据: 对「語」做 1px 膨胀, 墨量 29% -> 76%, 所有字腔闭合, 字变成白块",
                "16/20/24px 三个网格都试过, 结论一致 —— 汉字的粗壮感只能靠更大格子, 不能靠更粗描边",
            ],
        ),
        Candidate(
            id="F",
            name="10px 紧凑黑体",
            tagline="单源 · 比 12 省 17% 空间 · UI 密集场景的折中",
            accent=(142, 245, 192),
            font=BitmapFont(path=SIMHEI, index=0, px=10),
            coverage=FULL,
            notes=[
                "汉字点阵的下限附近: 常用字仍可辨, 密笔画开始明显受损",
                "建议作为 12px 的补充字重, 而不是替代",
            ],
        ),
        Candidate(
            id="G",
            name="8px 极简 · FC/NES",
            tagline="双源 · 汉字=SimHei 8 / 假名拉丁=MS Gothic 8 · 汉字已到网格物理极限",
            accent=(247, 161, 255),
            font=ScriptStack(
                ideo=BitmapFont(path=SIMHEI, index=0, px=8),
                non_ideo=BitmapFont(path=MSGOTHIC, index=0, px=8),
            ),
            coverage=FULL + " (双源)",
            notes=[
                "⚠ 诚实提示: 8x8 装不下汉字, 密笔画字 (語/撃) 基本是色块 —— 格子数的物理极限, 不是渲染 bug",
                "拉丁与数字在 8px 反而最漂亮。若确定要走 NES 风, 汉字需单独手绘简化字库",
            ],
        ),
        Candidate(
            id="H",
            name="24px 黑体 · 标题大字",
            tagline="单源 · 街机标题 / HUD 分数 / 对话框大字, 靠格子大而不是描边粗",
            accent=(120, 255, 214),
            font=BitmapFont(path=SIMHEI, index=0, px=24),
            coverage=FULL,
            notes=[
                "同样 1px 描边, 但格子够大, 墨量反而比 16px 低 —— 这就是\"大字更清楚\"的原因",
                "作为正文字号偏奢侈, 但做标题/回合数/胜负播报极对味",
            ],
        ),
    ]
    scales = {
        "A": (8, 4),
        "B": (8, 4),
        "C": (8, 4),
        "D": (7, 4),
        "E": (7, 4),
        "F": (10, 5),
        "G": (12, 6),
        "H": (5, 3),
    }
    return [(c, *scales[c.id]) for c in specs]


def gate_no_tofu(cand: Candidate) -> None:
    """缺字门禁: 样张里出现的每一个字符, 其路由到的源字体都必须真的有这个字形。

    像素字体没有回退 —— 缺一个字就是一块豆腐。所以这一条不过, 样张就是废的。
    """
    font = cand.font
    missing: list[str] = []
    for ch in ALL_SAMPLE_CHARS:
        if ch.isspace():
            continue
        src = font._pick(ch) if isinstance(font, ScriptStack) else font
        cps = cmap_for(src.path, src.index)
        if ord(ch) not in cps:
            missing.append(f"{ch}(U+{ord(ch):04X})@{src.name}")
    if missing:
        raise SystemExit(f"[{cand.id}] 缺字门禁未通过 -> {' '.join(missing)}")


def gate_metrics(cand: Candidate) -> None:
    """双源栈的两个源必须共用同一基线, 否则假名会比汉字高一格。"""
    font = cand.font
    if not isinstance(font, ScriptStack):
        return
    a, b = font.ideo.metrics, font.non_ideo.metrics
    if (a.ascent, a.descent) != (b.ascent, b.descent):
        raise SystemExit(
            f"[{cand.id}] 基线不一致: 汉字源 {a.ascent}/{a.descent} vs "
            f"拉丁源 {b.ascent}/{b.descent} —— 混排会错行"
        )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    slugs = {
        "A": "A_simshei12_gothic",
        "B": "B_dualsrc12_pc98",
        "C": "C_simsun12_song",
        "D": "D_simsun16_song",
        "E": "E_simhei16_gothic",
        "F": "F_simhei10_compact",
        "G": "G_gothic8_fc",
        "H": "H_simhei24_display",
    }
    for cand, sb, sc in build():
        gate_no_tofu(cand)
        gate_metrics(cand)
        cand.density = measure_density(cand.font)
        m = cand.font.metrics
        flag = "  ⚠ 墨量过高, 密笔画字已糊" if cand.density > 0.60 else ""
        print(
            f"[{cand.id}] {cand.font.name}  cell={m.cell_w}x{m.cell_h} half={m.half_w} "
            f"density={cand.density:.0%}{flag}"
        )
        p = render(cand, OUT / f"{slugs[cand.id]}.png", sb, sc)
        with Image.open(p) as im:
            print(f"     -> {p.name} {im.size}  ({p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()

