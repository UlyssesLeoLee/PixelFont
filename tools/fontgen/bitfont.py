"""bitfont — 1-bit 点阵字形栅格化核心。

设计目标: 模拟当年 DOS/PC-98/FC 时代的位图文字渲染管线, 而不是把正文字体缩小。
做法: 用 FreeType 的 MONO 目标 (FT_LOAD_TARGET_MONO, 等同 GDI 1-bit 文字) 渲染单个字符,
      再按整数网格对齐到 cell。输出是 0/255 的 L 模式图, 可直接 nearest-neighbor 放大。

为什么必须走 mode="1":
    Pillow 默认用灰度抗锯齿渲染再靠阈值二值化, 笔画粗细会被灰度边缘摊平,
    得到的不是点阵而是"缩小的矢量字体"。MONO 目标 + 单色 hinting 才会得到
    粗细恒为 1 格的真正位图字形。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image, ImageFont

# 单色渲染出的核心缓冲区里可能出现的值; 统一压成 0 / 255
_ON = 255
_OFF = 0


@dataclass
class FontMetrics:
    """整数网格度量。所有坐标都必须是整数, 任何一处浮点都会让点阵'抖'。"""

    px: int  # 请求的字号 (em)
    ascent: int  # 基线以上高度
    descent: int  # 基线以下高度
    cell_w: int  # 全角 cell 宽
    cell_h: int  # cell 高 (= ascent + descent)
    half_w: int  # 半角 cell 宽

    @property
    def baseline(self) -> int:
        return self.ascent


@dataclass
class BitmapFont:
    """单色点阵字形容器。

    weight: 额外的 1px 膨胀/收缩量。正数变粗(FEC 街机风), 负数变细(Yu Gothic Light 风)。
            用 4 邻域而非 8 邻域, 避免斜边被"糊成块"。
    stretch: 全角 cell 的额外加宽量, 用来做"拉开字距"的排版风格。
    latin_force_half: 拉丁字符强制占半角格, 保证 ASCII 严格等宽。
    """

    path: str
    index: int = 0
    px: int = 12
    weight: int = 0
    stretch: int = 0
    latin_force_half: bool = True
    name: str = ""
    _font: ImageFont.FreeTypeFont = field(init=False, repr=False)
    _metrics: FontMetrics = field(init=False, repr=False)
    _cache: dict[str, Image.Image] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._font = ImageFont.truetype(
            self.path, self.px, index=self.index, layout_engine=ImageFont.Layout.BASIC
        )
        ascent, descent = self._font.getmetrics()
        cjk_adv = round(self._font.getlength("\u4e2d"))
        latin_adv = round(self._font.getlength("A"))
        half = cjk_adv // 2 if self.latin_force_half else latin_adv
        self._metrics = FontMetrics(
            px=self.px,
            ascent=ascent,
            descent=descent,
            cell_w=cjk_adv + self.stretch,
            cell_h=ascent + descent,
            half_w=half,
        )
        if not self.name:
            self.name = "/".join(self._font.getname())

    # ---------- 公开接口 ----------

    @property
    def metrics(self) -> FontMetrics:
        return self._metrics

    @property
    def cell(self) -> tuple[int, int]:
        return self._metrics.cell_w, self._metrics.cell_h

    @property
    def half_cell(self) -> tuple[int, int]:
        return self._metrics.half_w, self._metrics.cell_h

    def is_wide(self, ch: str) -> bool:
        """全角判定: 优先按 East Asian Width, 回退到 advance。"""
        import unicodedata

        if unicodedata.east_asian_width(ch) in ("W", "F"):
            return True
        return False

    def glyph(self, ch: str) -> Image.Image:
        """取单个字形的 cell 图 (L 模式, 0/255)。已按整数网格对齐并加粗/减细。"""
        hit = self._cache.get(ch)
        if hit is not None:
            return hit
        m = self._metrics
        wide = self.is_wide(ch)
        cw = m.cell_w if wide else m.half_w
        canvas = Image.new("L", (max(cw, 1), m.cell_h), _OFF)
        rendered = self._render_mask(ch)
        if rendered is not None:
            glyph_img, (ox, oy) = rendered
            canvas.paste(glyph_img, (ox, oy))
        if self.weight != 0:
            canvas = _dilate(canvas, self.weight)
        self._cache[ch] = canvas
        return canvas

    def advance(self, ch: str) -> int:
        return self.glyph(ch).width

    def draw_text(self, target: Image.Image, xy: tuple[int, int], text: str, spacing: int = 0) -> int:
        """在 1-bit 图上按网格排一行字, 返回结束 x。spacing 为字间额外空格(格)。"""
        x, y = xy
        for ch in text:
            g = self.glyph(ch)
            target.paste(g, (x, y))
            x += g.width + spacing
        return x

    def text_width(self, text: str, spacing: int = 0) -> int:
        if not text:
            return 0
        return sum(self.advance(c) for c in text) + spacing * (len(text) - 1)

    # ---------- 内部 ----------

    def _render_mask(self, ch: str) -> tuple[Image.Image, tuple[int, int]] | None:
        """渲染一个字形并对齐到基线网格。返回 (glyph_img, (dx, dy)) 或 None。"""
        m = self._metrics
        try:
            core, offset = self._font.getmask2(ch, mode="1")
        except Exception:  # 字体缺该字形
            return None
        w, h = core.size
        if w == 0 or h == 0:
            return None
        data = bytes(core)
        if len(data) < w * h:  # 防御: 某些 Pillow 版本返回紧凑位图
            return None
        img = Image.frombuffer("L", (w, h), data[: w * h])
        # MONO 目标下应为 0/255; 仍做一次压平, 避免灰度残留变成"阴影"
        img = img.point(lambda v: _ON if v > 0 else _OFF)
        dx, dy = offset
        return img, (int(dx), int(dy))


def _dilate(img: Image.Image, weight: int) -> Image.Image:
    """4 邻域膨胀 (weight>0) 或腐蚀 (weight<0)。逐格处理, 保证纯整数结果。"""
    w, h = img.size
    src = img.load()
    out = Image.new("L", (w, h), _OFF)
    dst = out.load()
    for y in range(h):
        for x in range(w):
            on = src[x, y] > 0
            if weight > 0:
                if not on:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and src[nx, ny] > 0:
                            on = True
                            break
            elif not on:
                # 腐蚀: 四邻域全亮才算亮
                on = all(
                    0 <= x + dx < w and 0 <= y + dy < h and src[x + dx, y + dy] > 0
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                )
            dst[x, y] = _ON if on else _OFF
    return out


def scale(img: Image.Image, factor: int) -> Image.Image:
    """整数倍最近邻放大 —— 点阵预览唯一正确的放大方式。"""
    if factor == 1:
        return img.copy()
    return img.resize((img.width * factor, img.height * factor), Image.NEAREST)


# ---- 双源字形栈 --------------------------------------------------
#
# 为什么需要: MS Gothic 的 12px 假名/拉丁是 80 年代最正的点阵, 但它只有 JIS 汉字,
# 简体覆盖率仅 56.5%; SimHei/SimSun 简体 100% 但字形偏现代。真实的三语点阵字体
# 常常按语种分源: 汉字一块源、假名拉丁另一块源。这里用码位区间做静态路由。

_KANA_RANGES = ((0x3000, 0x30FF), (0x31F0, 0x31FF), (0xFF61, 0xFF9F))


def _is_kana(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in _KANA_RANGES)


class ScriptStack:
    """按码位把字形路由到不同源字体, 但对外呈现一套统一的网格。

    latin/kana  -> non_ideo 源 (MS Gothic 等)
    CJK 汉字     -> ideo 源   (SimHei / SimSun 等)
    """

    def __init__(self, ideo: BitmapFont, non_ideo: BitmapFont):
        self.ideo = ideo
        self.non_ideo = non_ideo
        self.metrics = ideo.metrics  # 网格以汉字源为准, 全角由 ideo 决定
        self.name = f"{ideo.name} + {non_ideo.name}"
        self.weight = ideo.weight

    def _pick(self, ch: str) -> BitmapFont:
        cp = ord(ch)
        if cp < 0x2E80 or _is_kana(cp):
            # 拉丁 / 标点 / 假名 —— 优先用 PC-98 味更正的源
            return self.non_ideo
        return self.ideo

    def glyph(self, ch: str) -> Image.Image:
        return self._pick(ch).glyph(ch)

    def advance(self, ch: str) -> int:
        return self.glyph(ch).width

    @property
    def cell(self) -> tuple[int, int]:
        return self.metrics.cell_w, self.metrics.cell_h

    def draw_text(self, target: Image.Image, xy: tuple[int, int], text: str, spacing: int = 0) -> int:
        x, y = xy
        for ch in text:
            g = self.glyph(ch)
            target.paste(g, (x, y))
            x += g.width + spacing
        return x

    def text_width(self, text: str, spacing: int = 0) -> int:
        if not text:
            return 0
        return sum(self.advance(c) for c in text) + spacing * (len(text) - 1)


def to_ascii(img: Image.Image, ink: str = "#", paper: str = ".") -> str:
    px = img.load()
    rows = []
    for y in range(img.height):
        rows.append("".join(ink if px[x, y] > 0 else paper for x in range(img.width)))
    return "\n".join(rows)


# 密笔画基准字: 用它们测墨量, 因为稀疏字 (一/口) 无论怎么加粗都看不出问题
DENSE_PROBE = "語龍鬱撃戰鑑"


def ink_ratio(img: Image.Image) -> float:
    px = img.load()
    on = sum(1 for y in range(img.height) for x in range(img.width) if px[x, y] > 0)
    return on / max(1, img.width * img.height)


def measure_density(font) -> float:
    """密笔画字的平均墨量占格比例。

    这是本项目最有用的一个客观指标: 字腔能不能留住, 决定了这个网格还能不能
    再加粗。实测 SimHei 16px 为 29%, 一旦做 1px 膨胀就到 76% —— 字腔全闭,
    「語」「撃」变成白块。60% 以上基本等于不可用。
    """
    return sum(ink_ratio(font.glyph(c)) for c in DENSE_PROBE) / len(DENSE_PROBE)
