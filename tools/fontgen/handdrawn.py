"""手绘字形 —— 4 个任何 12px 开源点阵字体都不覆盖的码位。

**为什么必须手绘**

这 4 个码位 `U+20AC €` `U+2260 ≠` `U+2264 ≤` `U+2265 ≥` 任何 12px 开源点阵字体
都不覆盖: Ark Pixel 与 Fusion Pixel 全部七个变体的 cmap 里都没有它们
(JIS X 0208 有 `≦ U+2266` `≧ U+2267`, 但**没有** `≤` `≥`, 更没有欧元符号)。

本来打算用 Zpix (最像素) 补这 4 个 —— 但核验上游后发现**它不能用**:

- `zpix-pixel-font` 仓库**没有 LICENSE 文件**, GitHub license API 返回 404,
  `package.json` 里也没有 license 字段;
- 上游 README 的「授权与价格」写明: 商用单产品 **USD $1000 / ￥7000**,
  教育与个人用途免费;
- 同一条 README 的版权声明明确写着 **禁止对本字体进行修改、反编译、转换、拆分**
  —— 裁剪成子集入库正是「修改 + 再分发」。

所以 `docs/reference-fonts.md` 里「Zpix = MIT」那句是**错的**, 已改正;
而裁剪 Zpix 入库这条路本身也走不通。

**结论**: 这 4 个字形由本仓库**原创手绘** —— 按 Unicode 标准几何形制画
(≤ = "<" 加下横杠, ≥ = ">" 加下横杠, ≠ = "=" 加斜杠, € = "C" 加两条横杠),
不属于任何第三方字体的复制品, 因此没有许可问题, 成品可以自由分发。

字形数据放在 `vendor/multi12/handdrawn-glyphs.txt` (字体数据 = OFL-1.1),
本模块只负责把它读成位图 —— **许可边界与代码边界分开**, 与仓库既有惯例一致
(`vendor/` 放字体数据, `tools/` 放 AGPL-3.0 的工具代码)。

**网格与度量** (与本家族其余字形同一格):

- 画布 12 × 13, 基线在第 11 行 (ascent 11 / descent 2);
- 宽度按**当前家族 `PixelFont PC98 12` 的实测值**取, 保证换家族后这 4 个
  字符的排版宽度不变: `€` 6px (与 `¥` 同类)、`≠` 12px、`≤` `≥` 6px
  (JIS 里 ≤ ≥ 是 `≦ ≧` 的半角形)。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "vendor" / "multi12" / "handdrawn-glyphs.txt"

#: 画布高 (13) 与基线行号 (11 = ascent)
CELL_H = 13
BASELINE = 11


def load() -> dict[int, tuple[int, list[str]]]:
    """读字形数据文件 -> {码位: (宽度, 13 行点阵)}。"""
    out: dict[int, tuple[int, list[str]]] = {}
    if not DATA.exists():
        raise SystemExit(f"缺少手绘字形数据: {DATA}")
    lines = DATA.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#"):
            continue
        head, _, wtxt = line.partition(" ")
        cp = int(head.strip().lstrip("U+"), 16)
        w = int(wtxt)
        rows = lines[i:i + CELL_H]
        i += CELL_H
        out[cp] = (w, rows)
    return out


GLYPHS = load()


class HanddrawnFont:
    """手绘字形的最小源实现 —— 接口与 `bitfont.BitmapFont` 一致。

    只提供字形来源需要的那几样: `glyph` / `advance` / `metrics` / `is_wide`。
    网格与基线由本模块自己定, 不依赖任何外部字体。
    """

    def __init__(self) -> None:
        from bitfont import FontMetrics

        self.name = "PixelFont handdrawn (4 glyphs)"
        self.metrics = FontMetrics(
            px=12, ascent=BASELINE, descent=CELL_H - BASELINE,
            cell_w=12, cell_h=CELL_H, half_w=6,
        )
        self._cache: dict[str, Image.Image] = {}

    def is_wide(self, ch: str) -> bool:
        """半角判定以**手绘字形自己的宽度**为准 (与 BitmapFont 同一原则)。"""
        entry = GLYPHS.get(ord(ch))
        if entry is None:
            return False
        return entry[0] > self.metrics.half_w

    def glyph(self, ch: str) -> Image.Image:
        hit = self._cache.get(ch)
        if hit is not None:
            return hit
        entry = GLYPHS.get(ord(ch))
        if entry is None:
            img = Image.new("L", (self.metrics.half_w, CELL_H), 0)
        else:
            w, rows = entry
            img = Image.new("L", (w, CELL_H), 0)
            px = img.load()
            for y, row in enumerate(rows):
                for x, c in enumerate(row):
                    if c == "#":
                        px[x, y] = 255
        self._cache[ch] = img
        return img

    def advance(self, ch: str) -> int:
        return self.glyph(ch).width

    def draw_text(self, target: Image.Image, xy: tuple[int, int], text: str,
                  spacing: int = 0) -> int:
        x, y = xy
        for ch in text:
            g = self.glyph(ch)
            target.paste(g, (x, y))
            x += g.width + spacing
        return x


def check() -> list[str]:
    """自检: 画布尺寸、基线、宽度是否自洽。返回问题列表 (空 = 通过)。"""
    problems: list[str] = []
    if not GLYPHS:
        problems.append("字形数据为空")
    for cp, (w, rows) in GLYPHS.items():
        if len(rows) != CELL_H:
            problems.append(f"U+{cp:04X}: 画布 {len(rows)} 行, 应为 {CELL_H}")
        for y, row in enumerate(rows):
            if len(row) != w:
                problems.append(f"U+{cp:04X}: 第 {y} 行宽 {len(row)}, 应为 {w}")
        if w not in (6, 12):
            problems.append(f"U+{cp:04X}: 宽度 {w} 不是 6 或 12")
        if not any("#" in r for r in rows):
            problems.append(f"U+{cp:04X}: 没有墨迹")
    return problems
