"""sheet — 候选设计方向的规格样张渲染。

每个候选都用完全相同的内容与排版渲染, 保证横向可比。样张里刻意包含三种视角:
  1. 大字样 (整数倍最近邻放大)  -> 看骨架与笔画设计
  2. 三语实测文案              -> 看真实排版密度与可读性
  3. 1:1 真实尺寸 + 模拟小屏    -> 看实际字号下的辨识度

放大切片用最近邻 (NEAREST), 任何双线性插值都会把点阵糊掉, 那不是点阵了。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from bitfont import BitmapFont  # noqa: E402

# ---- 复古但不影响判读的配色 ----
BG = (14, 16, 22)
PANEL = (21, 25, 34)
PANEL_INNER = (28, 33, 44)  # 面板内的内容底色, 与 PANEL 拉开以便看出裁切边界
PANEL_EDGE = (46, 54, 72)
INK = (242, 237, 227)  # 墨色: 微暖白, 接近老 CRT 磷光
INK_DIM = (128, 138, 155)
CAPTION = (150, 162, 182)
SCREEN_BG = (8, 10, 14)
AMBER = (255, 196, 110)  # 模拟小屏的琥珀磷光

LABEL_FONT = r"C:\Windows\Fonts\msyh.ttc"
LABEL_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
LABEL_INDEX = 0


@dataclass
class Candidate:
    id: str
    name: str
    tagline: str
    accent: tuple[int, int, int]
    font: object  # BitmapFont 或 ScriptStack —— 两者接口一致
    coverage: str = ""
    density: float = 0.0  # 密笔画字墨量, 由 gen_sheets 实测填入
    notes: list[str] = field(default_factory=list)


def label_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(LABEL_BOLD if bold else LABEL_FONT, size, index=LABEL_INDEX)


def text_mask(font: BitmapFont, text: str, spacing: int = 1) -> Image.Image:
    w = max(font.text_width(text, spacing) + 2, 1)
    h = font.metrics.cell_h
    canvas = Image.new("L", (w, h), 0)
    font.draw_text(canvas, (1, 0), text, spacing)
    return canvas


def paste_mask(canvas: Image.Image, mask: Image.Image, pos: tuple[int, int], color=INK) -> None:
    if mask.width == 0 or mask.height == 0:
        return
    solid = Image.new("RGB", mask.size, color)
    canvas.paste(solid, pos, mask)


def scale_mask(mask: Image.Image, k: int) -> Image.Image:
    if k <= 1:
        return mask
    return mask.resize((mask.width * k, mask.height * k), Image.NEAREST)


def scanline(img: Image.Image, strength: int = 46, period: int = 2) -> Image.Image:
    """极轻的 CRT 扫描线。保留为工具函数, 但样张默认不用 —— 逐行减暗会让点阵
    的 1px 笔画忽明忽暗, 反而干扰字形判读。"""
    out = img.copy()
    px = out.load()
    for y in range(0, out.height, period):
        for x in range(out.width):
            r, g, b = px[x, y]
            px[x, y] = (max(0, r - strength), max(0, g - strength), max(0, b - strength))
    return out


# ---------------------------------------------------------------- 画布


class Sheet:
    WIDTH = 1500
    PAD = 40

    def __init__(self, cand: Candidate):
        self.c = cand
        self.h = 700  # 会动态增长
        self.img = Image.new("RGB", (self.WIDTH, self.h), BG)
        self.d = ImageDraw.Draw(self.img)
        self.y = 0

    def _ensure(self, need: int) -> None:
        if self.y + need <= self.h:
            return
        new_h = self.h
        while self.y + need > new_h:
            new_h += 240
        grown = Image.new("RGB", (self.WIDTH, new_h), BG)
        grown.paste(self.img, (0, 0))
        self.img = grown
        self.h = new_h
        self.d = ImageDraw.Draw(self.img)

    def x(self) -> int:
        return self.PAD

    def right(self) -> int:
        return self.WIDTH - self.PAD

    def gap(self, n: int) -> None:
        self._ensure(n)
        self.y += n

    def caption(self, label: str) -> None:
        self._ensure(34)
        f = label_font(19)
        self.d.text((self.x(), self.y), label, font=f, fill=CAPTION)
        self.y += 30

    def panel(self, inner: Image.Image, pad: int = 18, bg=PANEL) -> int:
        """把一段图贴进带边框的面板, 返回面板高度。

        刻意在这里硬失败: 之前版本把超宽内容直接裁掉, 样张"看起来正常"但右侧
        少了一整列字形 —— 静默裁切比报错危险得多。
        """
        avail = self.WIDTH - self.PAD * 2 - pad * 2
        if inner.width > avail:
            raise ValueError(
                f"panel content {inner.width}px > available {avail}px "
                f"(candidate {self.c.id}); 缩短文案或降低放大倍数, 绝不静默裁切"
            )
        self._ensure(inner.height + pad * 2)
        x0, y0 = self.x(), self.y
        x1, y1 = x0 + inner.width + pad * 2, y0 + inner.height + pad * 2
        self.d.rectangle([x0, y0, x1, y1], fill=bg, outline=PANEL_EDGE)
        self.img.paste(inner, (x0 + pad, y0 + pad))
        self.y = y1 + 22
        return y1 - y0

    def header(self) -> None:
        self._ensure(150)
        c = self.c
        self.d.rectangle([0, 0, self.WIDTH, 8], fill=c.accent)
        self.d.text((self.x(), 34), c.id, font=label_font(46, bold=True), fill=c.accent)
        self.d.text((self.x() + 74, 38), c.name, font=label_font(40, bold=True), fill=INK)
        self.d.text((self.x(), 92), c.tagline, font=label_font(21), fill=INK_DIM)
        m = c.font.metrics
        spec = (
            f"网格 {m.cell_w}x{m.cell_h}px   半角 {m.half_w}px   基线 {m.ascent}/{m.descent}   "
            f"密笔画墨量 {c.density:.0%}   描边 {c.font.weight:+d}   {c.coverage}"
        )
        self.d.text((self.x(), 124), spec, font=label_font(18), fill=CAPTION)
        self.d.text((self.x(), 150), f"来源 {c.font.name}", font=label_font(17), fill=(96, 105, 122))
        self.y = 192

    def notes(self) -> None:
        f = label_font(18)
        for i, n in enumerate(self.c.notes):
            self._ensure(28)
            self.d.text((self.x(), self.y), f"— {n}", font=f, fill=INK_DIM)
            self.y += 26
        self.y += 6

    def finish(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        out = self.img.crop((0, 0, self.WIDTH, self.y + 16))
        out.save(path, "PNG")
        return path


# ---------------------------------------------------------------- 内容


# ---------------------------------------------------------------- 样张内容
#
# 提成模块常量是为了让 gen_sheets 的缺字门禁能检查"与实际渲染完全相同"的字符集。
# 门禁只喂一部分文本 = 门禁在说谎。

BIG_ROWS = [  # (文本, 字间距)
    ("中日語漢字画面攻撃", 2),
    ("あアカヲンソツ", 2),
    ("ABCDEFGHIJ abcdefghij", 1),
    ("0123456789 !?#%&@", 1),
]
COPY_LINES = [
    "中文 开始游戏 生命100 金币250",
    "日本語 ゲーム開始 ライフ100",
    "English PLAYER1 SCORE001200",
]
NATIVE_TEXT = "中文 ABC 012"
SCREEN_TEXT = "生命100 金币250"
ALL_SAMPLE_CHARS = "".join(
    [t for t, _ in BIG_ROWS] + COPY_LINES + [NATIVE_TEXT, SCREEN_TEXT]
)


def block_big_samples(font, scale: int) -> Image.Image:
    # 不再把 "汉字"/"Latin" 之类标签混进点阵行里: 标签本身也被点阵化,
    # 既挤占宽度又干扰对字形密度的判断。标签交给上面的 caption。
    masks = [scale_mask(text_mask(font, t, sp), scale) for t, sp in BIG_ROWS]
    gap = 6 * scale
    w = max(m.width for m in masks)
    h = sum(m.height for m in masks) + gap * (len(masks) - 1)
    canvas = Image.new("RGB", (w, h), PANEL_INNER)
    y = 0
    for m in masks:
        paste_mask(canvas, m, (0, y))
        y += m.height + gap
    return canvas


def block_copy(font, scale: int) -> Image.Image:
    masks = [scale_mask(text_mask(font, t, 1), scale) for t in COPY_LINES]
    gap = 5 * scale
    w = max(m.width for m in masks)
    h = sum(m.height for m in masks) + gap * (len(masks) - 1)
    canvas = Image.new("RGB", (w, h), PANEL_INNER)
    y = 0
    for m in masks:
        paste_mask(canvas, m, (0, y))
        y += m.height + gap
    return canvas


def block_native(font) -> Image.Image:
    """左: 1:1 真实像素。中: 同段文字放大对照 (倍率随字号自适应, 否则 24px 会撑爆版面)。
    右: 琥珀色模拟小屏。"""
    m1 = text_mask(font, NATIVE_TEXT, 1)
    mult = max(1, min(6, 460 // max(1, m1.width)))
    m2 = scale_mask(m1, mult)
    sm = scale_mask(text_mask(font, SCREEN_TEXT, 1), 2)

    label_h = 24
    gap = 36
    screen_pad = 14
    w = m1.width + gap + m2.width + gap + sm.width + screen_pad * 2 + 24
    h = max(m1.height, m2.height, sm.height + screen_pad * 2) + label_h + 14
    canvas = Image.new("RGB", (w, h), PANEL_INNER)
    d = ImageDraw.Draw(canvas)
    f = label_font(15)
    x = 12
    top = label_h + 8
    d.text((x, 3), "1:1 实际尺寸", font=f, fill=CAPTION)
    paste_mask(canvas, m1, (x, top))
    x += m1.width + gap
    d.text((x, 3), f"×{mult} 对照", font=f, fill=CAPTION)
    paste_mask(canvas, m2, (x, top))
    x += m2.width + gap
    # 模拟小屏: 深底 + 琥珀磷光, 比扫描线更接近真实 CRT, 也不会糊成黑条
    sx, sy = x, top
    sw, sh = sm.width + screen_pad * 2, sm.height + screen_pad * 2
    d.rectangle([sx - 4, sy - 4, sx + sw + 3, sy + sh + 3], fill=SCREEN_BG)
    paste_mask(canvas, sm, (sx + screen_pad, sy + screen_pad), AMBER)
    d.text((sx, 3), "×2 模拟小屏", font=f, fill=CAPTION)
    return canvas


def render(cand: Candidate, out: Path, scale_big: int, scale_copy: int) -> Path:
    s = Sheet(cand)
    s.header()
    s.notes()

    s.caption("① 字形大样 — 骨架、笔画、疏密")
    s.panel(block_big_samples(cand.font, scale_big))

    s.caption("② 三语实测文案")
    s.panel(block_copy(cand.font, scale_copy))

    s.caption("③ 实际字号辨识度")
    s.panel(block_native(cand.font))

    s.gap(4)
    return s.finish(out)
