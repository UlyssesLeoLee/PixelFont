"""构建成品: BDF 位图字体 + TTF(像素轮廓) + PNG 图集。

三种格式来自同一份 1-bit 字形位图数据, 所以它们必然一致 —— 但"必然一致"不等于
"验证过一致", 所以本文件末尾有 verify_* 函数, 把三个成品全部读回来与源位图逐像素对比。

TTF 的做法: 每段连续的墨迹水平游程 → 一个矩形轮廓, UPM=768 且 1 像素 = 64 单位。
这样在 12px 下缩放比正好是 1/64, 每个像素落在整数点上, 且不写 hinting 指令,
所以不需要靠渲染器的 grid-fitting 去凑对齐。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image, ImageDraw  # noqa: E402

from bitfont import BitmapFont, ScriptStack  # noqa: E402
from charset import build_charset, build_stack, gate_full_coverage, gate_ideo_route  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "dist"
FONT_NAME = "PixelFont PC98 12"
PS_NAME = "PixelFontPC98-12"
UPM = 768  # 12 px * 64: 1 像素 = 64 单位。

# 字体头时间戳 (Mac 纪元秒)。钉死它, 同一份源码每次构建出的 TTF 字节完全一致;
# 需要换时间戳时设 SOURCE_DATE_EPOCH 环境变量 (reproducible-builds.org 约定)。
# 实测: 不钉死的话, 两次构建只有 head 表的 created/modified 不同, 其余表逐字节一致。
# 这个值对应 2026-10-21 (C4 路由落地之日)。
FONT_TIMESTAMP = 3875422459
# 为什么是 768 而不是好读的 1200: ppem=12 时缩放比 = 12/UPM。UPM=1200 会让
# 12/1200 = 0.01 在 16.16 定点里被截成 655 (精确值 655.36), 每个像素实际只有
# 0.99945 设备像素高, 栅格化时部分行塌陷、部分行重复。UPM=768 时 12*65536/768
# = 1024 整除, 1 像素 = 64 单位 = 恰好 1 设备像素, 缩放全程无误差。


# ---------------------------------------------------------------- 字形数据


@dataclass
class GlyphData:
    ch: str
    category: str
    width: int  # cell 宽 (全角 12 / 半角 6)
    height: int  # 13
    advance: int
    rows: list[list[int]]  # 0/1, len == height

    def ink_bbox(self, ascent: int) -> tuple[int, int, int, int]:
        """返回 (w, h, xoff, yoff); BDF 的 BBX 用。yoff 以基线为 0, 向下为正。"""
        xs = [x for y in range(self.height) for x in range(self.width) if self.rows[y][x]]
        ys = [y for y in range(self.height) for x in range(self.width) if self.rows[y][x]]
        if not xs:
            return (0, 0, 0, 0)
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        return (x1 - x0 + 1, y1 - y0 + 1, x0, y0 - ascent)


def collect_glyphs(stack: ScriptStack, items: list[tuple[str, str]]) -> list[GlyphData]:
    m = stack.metrics
    out: list[GlyphData] = []
    for ch, cat in items:
        g = stack.glyph(ch)
        w, h = g.width, g.height
        px = g.load()
        rows = [[1 if px[x, y] > 0 else 0 for x in range(w)] for y in range(h)]
        if w != m.half_w and w != m.cell_w:
            raise SystemExit(f"glyph '{ch}' cell 宽异常: {w} (期望 {m.half_w} 或 {m.cell_w})")
        if h != m.cell_h:
            raise SystemExit(f"glyph '{ch}' cell 高异常: {h} (期望 {m.cell_h})")
        out.append(GlyphData(ch, cat, w, h, w, rows))
    return out


# ---------------------------------------------------------------- BDF


def _bdf_row_bytes(row: list[int]) -> bytes:
    pad = (-len(row)) % 8
    bits = row + [0] * pad
    val = 0
    for b in bits:
        val = (val << 1) | b
    n = len(bits) // 8
    return val.to_bytes(n, "big")


XLFD = "-PF-PixelFontPC98-Medium-R-Normal--12-1200-72-72-c-1000-ISO10646-1"


def write_bdf(glyphs: list[GlyphData], ascent: int, descent: int, path: Path,
              xlfd: str = XLFD) -> Path:
    lines: list[str] = [
        "STARTFONT 2.1",
        f"FONT {xlfd}",
        f"SIZE 12 72 72",
        f"FONTBOUNDINGBOX 12 {ascent + descent} 0 -{descent}",
        "STARTPROPERTIES 5",
        "FONT_ASCENT " + str(ascent),
        "FONT_DESCENT " + str(descent),
        'CHARSET_REGISTRY "ISO10646"',
        'CHARSET_ENCODING "UTF-8"',
        "ENDPROPERTIES",
        f"CHARS {len(glyphs)}",
    ]
    for g in glyphs:
        cp = ord(g.ch)
        w, h, xoff, yoff = g.ink_bbox(ascent)
        lines += [
            f"STARTCHAR uni{cp:04X}",
            f"ENCODING {cp}",
            f"SWIDTH {round(1000 * g.advance / 12)} 0",
            f"DWIDTH {g.advance} 0",
            f"BBX {w} {h} {xoff} {yoff}",
        ]
        if w:
            lines.append("BITMAP")
            y0 = min(
                y for y in range(g.height) for x in range(g.width) if g.rows[y][x]
            )
            # 关键: 所有行必须按 BBX 的全局 x0 切片, 不能按各行自己的最小 x。
            # 窄标点 (" # $ %) 每行的墨迹起点都不同, 按行对齐会让整行相对 BBX 错位,
            # 而中日汉字几乎都占满宽度, 于是这类 bug 在汉字上完全看不出来。
            nbytes = (w + 7) // 8
            zero_row = "0" * (nbytes * 2)
            for y in range(y0, y0 + h):
                row_slice = g.rows[y][xoff : xoff + w]
                if not any(row_slice):
                    # 包围盒内部允许存在整行空白 (上下分离的部件之间), 空行也要占位输出
                    lines.append(zero_row)
                    continue
                lines.append(_bdf_row_bytes(row_slice).hex().upper())
            lines.append("ENDCHAR")
        else:
            # 零墨迹字形 (如空格): BBX 0 0 0 0 + 空 BITMAP 段, 字符块只需要**一个**
            # ENDCHAR。多写一个会让 STARTCHAR/ENDCHAR 配对失衡, 严格解析器直接报错。
            lines += ["BITMAP", "ENDCHAR"]
    lines.append("ENDFONT")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_bdf_map(glyphs: list[GlyphData], ascent: int, descent: int, path: Path,
                  xlfd: str = XLFD) -> Path:
    lines = [
        "STARTMAP 2.1",
        f"FONT {xlfd}",
        f"SIZE 12 72 72",
        f"FONTBOUNDINGBOX 12 {ascent + descent} 0 -{descent}",
        "STARTPROPERTIES 3",
        'CHARSET_REGISTRY "ISO10646"',
        'CHARSET_ENCODING "UTF-8"',
        "ENDPROPERTIES",
    ]
    for g in glyphs:
        cp = ord(g.ch)
        lines += [f"STARTCHAR uni{cp:04X}", f"ENCODING {cp}", "ENDCHAR"]
    lines.append("ENDFONT")
    lines.append("ENDMAP")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------- TTF


def write_ttf(
    glyphs: list[GlyphData],
    ascent: int,
    descent: int,
    path: Path,
    family_name: str = FONT_NAME,
    ps_name: str = PS_NAME,
    copyright_text: str = "PixelFont project. Licensed under AGPL-3.0.",
    license_text: str | None = None,
    code_page_range1: int = (1 << 0) | (1 << 17) | (1 << 18),
) -> Path:
    """写 TTF。

    `family_name` / `ps_name` / 许可文本 / 代码页位可覆盖 —— 同一个家族要出第二个
    字体 (`PixelFont Multi 12`) 时复用这里的全部轮廓逻辑, 只换名表、许可与元数据。

    `code_page_range1` 的位号依 OpenType OS/2 规范 (1.9.1) 的 ulCodePageRange 表:
    bit0=1252 ANSI, bit17=932 日文, bit18=936 简体中文, **bit19=949 韩文**。
    Multi 12 覆盖 11,172 个谚文音节, 必须把 bit19 打开 ——
    否则 GDI 在 lfCharSet=HANGEUL 下**根本不会考虑本字体** (实测枚举到 0 族),
    韩文正文会被回退到系统字体。
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.tables import _g_a_s_p as gasp_mod

    # 注意除数是 em 宽度 (cell_w), 不是 cell 高。
    # TTF 的 em 方框是正方形 12x12, 第 13 行位于基线以下 (负 y), 这是合法轮廓位置,
    # 而且必须这样: 若按 cell 高 13 去除, 在 ppem=12 下缩放比变成 12/13, 每个像素
    # 落在 0.923 个设备像素上 —— 整副字都会糊, 而这种糊在"字体能打开"时完全看不出来。
    cell_w = max(g.width for g in glyphs)
    if UPM % cell_w:
        raise SystemExit(
            f"UPM {UPM} 无法被 em 宽 {cell_w} 整除, 像素会错位。请选 UPM = k * {cell_w}"
        )
    px = UPM // cell_w  # 1 像素 = 多少单位

    order = [".notdef"] + [f"u{ord(g.ch):04X}" for g in glyphs]
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order)

    cmap = {ord(g.ch): f"u{ord(g.ch):04X}" for g in glyphs}
    fb.setupCharacterMap(cmap)

    glyf: dict[str, object] = {}

    # .notdef: 空心方框, 让缺字在游戏里肉眼可见。
    # 上沿到基线上方 ascent 处, 下沿伸到基线下方 descent 处 —— 不要从 y=0 起画,
    # 那会让缺字框比真实字面高一截, 排版时明显错位。
    pen = TTGlyphPen(None)
    x0, y0, x1, y1 = 0, -descent * px, cell_w * px, ascent * px
    for ring in (
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
        [(x0 + px, y0 + px), (x0 + px, y1 - px), (x1 - px, y1 - px), (x1 - px, y0 + px)],
    ):
        pen.moveTo(ring[0])
        for pt in ring[1:]:
            pen.lineTo(pt)
        pen.closePath()
    glyf[".notdef"] = pen.glyph()

    for g in glyphs:
        pen = TTGlyphPen(None)
        runs: list[tuple[int, int, int]] = []
        for y in range(g.height):
            run_start = None
            for x in range(g.width + 1):
                on = g.rows[y][x] if x < g.width else 0
                if on and run_start is None:
                    run_start = x
                elif not on and run_start is not None:
                    runs.append((run_start, x, y))
                    run_start = None
        for x0, x1, y0, y1 in _merge_vertical_runs(runs):
            _emit_rect(pen, x0, y0, x1, y1, ascent, px)
        glyf[f"u{ord(g.ch):04X}"] = pen.glyph()

    fb.setupGlyf(glyf)

    metrics = {".notdef": (cell_w * px, 0)}
    for g in glyphs:
        # hmtx 的 lsb 必须等于 glyf 的 xMin (墨迹左边缘), 不能一律填 0。
        # 墨迹不从 x=0 开始的窄字形 ( ! ' ( ) , 等) 会被渲染器整体左移,
        # 表现为字形错位 1-3 像素 —— 而汉字几乎都占满宽度, 这个问题在汉字上看不出来。
        xs = [x for y in range(g.height) for x in range(g.width) if g.rows[y][x]]
        lsb = (min(xs) if xs else 0) * px
        metrics[f"u{ord(g.ch):04X}"] = (g.advance * px, lsb)
    fb.setupHorizontalMetrics(metrics)

    a, d = ascent * px, descent * px
    fb.setupHorizontalHeader(ascent=a, descent=-d, lineGap=0)
    fb.setupOS2(
        sTypoAscender=a,
        sTypoDescender=-d,
        sTypoLineGap=0,
        usWinAscent=a,
        usWinDescent=d,
        sxHeight=round(6 * px),
        sCapHeight=round(8 * px),
        usWeightClass=400,
        usWidthClass=5,  # 固定宽度: 像素字必须是等宽, 否则会破坏网格
        fsType=0,  # 可自由安装
        fsSelection=0x0040,  # REGULAR 位。缺这一位 Word 不认它是常规体 (对照: SimSun/MS Gothic/Arial 都是 0x0040)
        achVendID="PXLF",
        # 代码页位 = Windows 字体映射器在某个 charset 请求下**能不能选中本字体**。
        # 位号依 OpenType OS/2 规范 (1.9.1) 的 ulCodePageRange 表: bit0=1252 ANSI,
        # bit17=932 日文, bit18=936 简体中文。
        # 旧值 (1<<16)|(1<<17) 实际是 874 泰语 + 932 日文 —— 既没有 1252 也没有 936,
        # 而且泰语是我们根本没有的。后果实测过 (见 docs/word-compat.md):
        # GDI 在 lfCharSet=ANSI 时把本字体替换成 Arial, 在 GB2312 时替换成宋体。
        ulCodePageRange1=code_page_range1,  # 1252 + 932 + 936 (+ 949 由调用方决定)
        # ulUnicodeRange* 不手写: 不给这四个字段时 fontTools 会按 cmap 的实际覆盖
        # 自动重算 (O_S_2f_2.recalcUnicodeRanges)。手写曾虚报 拉丁扩展-A/B、
        # 拉丁扩展附加、希腊扩展 —— 系统于是把希腊/西里尔/拉丁扩展文本路由到本字体,
        # 渲染成豆腐块; 同时又漏报了 CJK/假名/通用标点区段, 导致系统跳过本字体去做回退。
    )
    fb.setupNameTable(
        {
            "familyName": family_name,
            "styleName": "Regular",
            "uniqueFontIdentifier": f"{family_name};1.000",
            "fullName": family_name,
            "psName": ps_name,
            "version": "Version 1.000",
            "copyright": copyright_text,
            "licenseDescription": license_text or (
                "Retro 8-bit style tri-lingual bitmap font (Simplified Chinese / "
                "Japanese / Latin). Licensed under the GNU AGPL-3.0."
            ),
        }
    )
    fb.setupPost(keepGlyphNames=False)
    fb.setupMaxp()
    # setupMaxp() 只写默认值 (numGlyphs/maxPoints/maxContours 全为 0), 不会从 glyf 重算。
    # 复杂汉字的像素矩形数量轻松上百, 不重算的话 maxPoints 失真, 某些渲染器会因此拒绝加载。
    fb.font["maxp"].recalc(fb.font)

    # gasp: 所有字号都取 0 —— 单色栅格化, 且**不做**网格拟合。
    #
    # 旧值只在 12ppem 取 0, 其余字号走 GRIDFIT|DOGRAY。对像素字来说这两个标志
    # 都是反的: DOGRAY 请求灰度抗锯齿 (会把像素字糊成灰边), GRIDFIT 会让栅格化器
    # 启用 autohinter (FreeType 下实测把 1px 竖画吸附撑粗, "中" 多出横杠)。
    # 改成全字号 0 之后: 12 的整数倍 ppem (9/18/27/36pt @96dpi) 轮廓按整数倍缩放,
    # 与设计位图逐像素一致; 其余字号至少是硬边, 不会糊成灰。
    #
    # 实测边界 (别夸大): 本机 GDI 内存 DC 上, 新旧 gasp 在 12/14/15/16/18/21/24/36ppem
    # 的渲染结果**完全相同** (都是纯单色, 抗锯齿像素恒为 0)。也就是说本机 GDI
    # 不因 gasp 表改变行为, 这一改动的收益在 GDI 上**不可观测**; 它的作用是让声明
    # 与像素字的设计意图一致, 并覆盖会照做 gasp 的渲染器。
    gasp = gasp_mod.table__g_a_s_p()
    gasp.version = 0
    gasp.gaspRange = {
        0xFFFF: 0,  # 全字号: 单色 + 不网格拟合
    }
    fb.font["gasp"] = gasp

    # 时间戳钉死 —— 否则同一份源码每次构建出的 TTF 字节都不一样,
    # "可复现"就无从谈起 (实测: 两次构建只有 head 表的 created/modified 不同,
    # 其余所有表逐字节一致)。
    # 优先用 SOURCE_DATE_EPOCH (reproducible-builds.org 约定), 否则用固定常量。
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", FONT_TIMESTAMP))
    fb.font["head"].created = epoch
    fb.font["head"].modified = epoch

    fb.save(str(path))
    return path


def _merge_vertical_runs(runs: list[tuple[int, int, int]]) -> list[tuple[int, int, int, int]]:
    """把 x 范围相同、y 范围上下相邻的水平游程合并成**一个**矩形。

    为什么必须合 (2026-10-24 实测, 见 docs/word-compat.md §7.6):
        逐行逐段各发一个矩形时, 同一条竖笔画会被拆成一串 1x1 的小方块。
        栅格化时每个矩形**独立**吸附到输出像素网格 —— 缩放倍数不是整数时
        (如 18ppem = 1.5 倍), 1.5px 的方块有的落进 1 格、有的整个落空,
        于是笔画断成虚线, 墨迹量也比理论值偏细 43%。
        合并成一个大矩形后, 整条竖笔画是一个连续轮廓, 吸附后仍然连续。

    为什么不影响整数倍字号:
        合并的正是**上下相邻且 x 范围相同**的两段, 像素并集完全不变 ——
        所以 12/24/36ppem 下逐格精确性不受影响 (实测 12483/12483 一致)。
        轮廓总数还从 107209 降到 73933 (-31%), TTF 体积 -28.6%。

    同向矩形用 non-zero 环绕规则填充, 合并后可能与别的矩形局部重叠,
    但重叠区域本来就是墨迹, 并集不变 —— 不会挖空, 也不会多出像素。
    """
    groups: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for x0, x1, y in runs:
        groups.setdefault((x0, x1), []).append((y, y + 1))
    merged: list[tuple[int, int, int, int]] = []
    for (x0, x1), spans in groups.items():
        spans.sort()
        cur_y0, cur_y1 = spans[0]
        for y0, y1 in spans[1:]:
            if y0 <= cur_y1:
                cur_y1 = max(cur_y1, y1)
            else:
                merged.append((x0, x1, cur_y0, cur_y1))
                cur_y0, cur_y1 = y0, y1
        merged.append((x0, x1, cur_y0, cur_y1))
    return merged


def _emit_rect(pen, x0: int, y0: int, x1: int, y1: int, ascent: int, px: int) -> None:
    """把一段水平游程变成一个矩形轮廓 (TrueType 坐标系, y 向上)。

    所有矩形取同一绕向 —— TrueType 用 non-zero 环绕规则填充, 同向的互不重叠
    矩形才会全部实心。这条如果写反, FreeType 会把它们挖空。
    """
    left, right = x0 * px, x1 * px
    top = (ascent - y0) * px  # 像素行 y 顶边在基线之上的高度
    bottom = (ascent - y1) * px
    pen.moveTo((left, bottom))
    pen.lineTo((right, bottom))
    pen.lineTo((right, top))
    pen.lineTo((left, top))
    pen.closePath()


# ---------------------------------------------------------------- PNG 图集


def write_atlas(
    glyphs: list[GlyphData],
    ascent: int,
    descent: int,
    columns: int,
    outdir: Path,
    ps_name: str = PS_NAME,
    font_name: str = FONT_NAME,
) -> tuple[Path, Path]:
    cell_w = max(g.width for g in glyphs)
    cell_h = ascent + descent
    rows_n = (len(glyphs) + columns - 1) // columns
    W, H = columns * cell_w, rows_n * cell_h
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    meta: list[list[int]] = []
    for i, g in enumerate(glyphs):
        cx, cy = (i % columns) * cell_w, (i // columns) * cell_h
        px = g.rows
        for y in range(cell_h):
            row = px[y]
            for x in range(g.width):
                if row[x]:
                    img.putpixel((cx + x, cy + y), (255, 255, 255, 255))
        # isWide 必须由**实际 advance** 决定, 不能由"字符分类"决定:
        # 半角片假名 (U+FF61-FF9F) 和半角标点的 advance 是 6, 但只要分类不是 ascii
        # 就会被标成全角 —— 引擎按图集推进就会整体错位。
        meta.append([ord(g.ch), cx, cy, g.advance, 1 if g.advance == cell_w else 0])
    png = outdir / f"{ps_name}-atlas.png"
    img.save(png)

    data = {
        "name": font_name,
        "postScriptName": ps_name,
        "cell": {"w": cell_w, "h": cell_h},
        "baseline": ascent,
        "descent": descent,
        "columns": columns,
        "rows": rows_n,
        "size": {"w": W, "h": H},
        "inkColor": "白色 + alpha, 便于在引擎内染色",
        "latinAnchor": "left",
        "glyphCount": len(glyphs),
        # [codepoint, x, y, advance, isWide]
        "glyphs": meta,
    }
    js = outdir / f"{ps_name}-atlas.json"
    js.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return png, js


# ---------------------------------------------------------------- 样张


def write_specimen(glyphs: list[GlyphData], ascent: int, descent: int, path: Path) -> Path:
    """成品字形样张 (从位图数据直接渲染, 1:1 + ×4)。"""
    by_cp = {ord(g.ch): g for g in glyphs}
    cell_h = ascent + descent

    def render_line(text: str, spacing: int = 1) -> Image.Image:
        # 依 cmap 规则推进: 半角占 6px, 全角占 12px
        total = 1
        for ch in text:
            g = by_cp.get(ord(ch))
            total += (g.advance if g else 6) + spacing
        img = Image.new("L", (total, cell_h), 0)
        x = 1
        for ch in text:
            g = by_cp.get(ord(ch))
            if g is None:
                continue
            for y in range(g.height):
                for xx in range(g.width):
                    if g.rows[y][xx]:
                        img.putpixel((x + xx, y), 255)
            x += g.advance + spacing
        return img

    lines_1x = [
        "中文 开始游戏 生命100 金币250",
        "日本語 ゲーム開始 ライフ100",
        "English PLAYER1 SCORE001200",
        "0123456789 !?#%&@ ABCdefg",
    ]
    blocks: list[Image.Image] = []
    for t in lines_1x:
        m = render_line(t)
        big = m.resize((m.width * 4, m.height * 4), Image.NEAREST)
        blocks.append(big)
    gap = 10
    W = max(b.width for b in blocks) + 20
    H = sum(b.height for b in blocks) + gap * (len(blocks) - 1) + 20
    canvas = Image.new("RGB", (W, H), (18, 21, 29))
    y = 10
    for b in blocks:
        col = Image.new("RGB", b.size, (242, 237, 227))
        canvas.paste(col, (10, y), b)
        y += b.height + gap
    canvas.save(path)
    return path


# ---------------------------------------------------------------- 验证


def verify_bdf(glyphs: list[GlyphData], ascent: int, descent: int, path: Path) -> None:
    """把 BDF 重新解析回位图, 与源数据逐像素比对。"""
    cell_w = max(g.width for g in glyphs)
    cell_h = ascent + descent
    text = path.read_text(encoding="utf-8").splitlines()
    parsed: dict[int, tuple[int, int, int, list[list[int]]]] = {}
    i = 0
    cur = None
    while i < len(text):
        ln = text[i].strip()
        if ln.startswith("ENCODING "):
            cur = int(ln.split()[1])
        elif ln == "BITMAP" and cur is not None:
            w, h, xoff, yoff = (int(v) for v in text[i - 1].split()[1:5])
            ytop = ascent + yoff
            rows: list[list[int]] = [[0] * cell_w for _ in range(cell_h)]
            nbytes = (w + 7) // 8
            for k in range(h):
                hexs = text[i + 1 + k].strip()
                val = int(hexs, 16) if hexs else 0
                bits = [
                    (val >> (nbytes * 8 - 1 - b)) & 1 for b in range(nbytes * 8)
                ]  # MSB 优先, 跨字节连续展开
                for b in range(w):
                    if bits[b]:
                        rows[ytop + k][xoff + b] = 1
            parsed[cur] = (w, h, xoff, rows)
            i += h
        i += 1
    bad = []
    for g in glyphs:
        cp = ord(g.ch)
        if cp not in parsed:
            bad.append(f"U+{cp:04X} 缺失")
            continue
        _, _, xoff, rows = parsed[cp]
        # 按字形自身宽度比对 (半角 6 列 / 全角 12 列), 不能按 cell 宽度 ——
        # 后者会让半角字形的 row[6:] 直接越界, 或者把"短行"误判成不一致。
        diff = sum(
            1
            for y in range(len(g.rows))
            for x in range(len(g.rows[y]))
            if rows[y][x] != g.rows[y][x]
        )
        if diff:
            bad.append(f"U+{cp:04X} 差 {diff} px")
        if len(bad) >= 5:
            break
    if bad:
        raise SystemExit("BDF 回读校验失败: " + "; ".join(bad))
    print(f"  BDF 回读校验: {len(glyphs)} 字形全部逐像素一致")


def verify_atlas(glyphs: list[GlyphData], ascent: int, png: Path, js: Path) -> None:
    img = Image.open(png).convert("RGBA")
    data = json.loads(js.read_text(encoding="utf-8"))
    cw, ch = data["cell"]["w"], data["cell"]["h"]
    px = img.load()
    bad = []
    for g in glyphs:
        cp = ord(g.ch)
        entry = next((m for m in data["glyphs"] if m[0] == cp), None)
        if entry is None:
            bad.append(f"U+{cp:04X} 不在图集元数据中")
            continue
        _, gx, gy, adv, _wide = entry
        for y in range(g.height):
            for x in range(g.width):
                want = 255 if g.rows[y][x] else 0
                got = px[gx + x, gy + y][3]
                if want != got:
                    bad.append(f"U+{cp:04X} @({x},{y})")
                    break
            if bad:
                break
        if len(bad) >= 5:
            break
    if bad:
        raise SystemExit("图集回读校验失败: " + "; ".join(bad))
    print(f"  PNG 图集回读校验: {len(glyphs)} 字形一致, 尺寸 {img.size}, 单元 {cw}x{ch}")


def verify_ttf(glyphs: list[GlyphData], ascent: int, descent: int, path: Path,
               need_cp: dict[int, str] | None = None) -> None:
    """从成品 TTF 的轮廓反向还原像素, 与源位图逐格比对。

    为什么不直接比"渲染出来的像素": Pillow 的 FreeType 默认带 hinting / 网格拟合,
    实测会把 1px 笔画撑成 2px 并整体偏移 1 行。那是栅格化器的行为, 不是字体文件的内容
    —— 我先验证过: 从本文件轮廓还原出的像素与源位图完全一致, 而 Pillow 渲染不一致。
    这里验证的是文件里到底存了什么: 矩形绕向、Y 轴方向、坐标缩放、cmap 映射、缺失字形。
    """
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.ttLib import TTFont

    tt = TTFont(str(path))
    upm = tt["head"].unitsPerEm
    cell_w = max(g.width for g in glyphs)
    if upm % cell_w:
        raise SystemExit(f"TTF upm={upm} 与 em 宽 {cell_w} 不整除, 像素会错位")
    px = upm // cell_w
    glyphset = tt.getGlyphSet()
    cmap = tt.getBestCmap()
    cell_h = ascent + descent

    bad: list[str] = []
    for g in glyphs:
        cp = ord(g.ch)
        name = cmap.get(cp)
        if name is None:
            bad.append(f"U+{cp:04X} cmap 缺失")
            if len(bad) >= 5:
                break
            continue
        pen = DecomposingRecordingPen(glyphset[name])
        glyphset[name].draw(pen)
        cell = [[0] * cell_w for _ in range(cell_h)]
        cur: list[tuple[float, float]] = []
        for op, args in pen.value:
            if op == "moveTo":
                cur = [args[0]]
            elif op == "lineTo":
                cur.append(args[0])
            elif op == "closePath":
                if len(cur) == 4:
                    xs = [p[0] for p in cur]
                    ys = [p[1] for p in cur]
                    if any(abs(v % px) > 1e-6 for v in xs + ys):
                        bad.append(f"U+{cp:04X} 坐标未落在像素网格上")
                    cx0, cx1 = int(min(xs) // px), int(max(xs) // px)
                    # TrueType y 向上, cell 行号从顶数: 行 r 上边缘 = ascent - r
                    r0, r1 = ascent - int(max(ys) // px), ascent - int(min(ys) // px)
                    for r in range(r0, r1):
                        for c in range(cx0, cx1):
                            if 0 <= r < cell_h and 0 <= c < cell_w:
                                cell[r][c] = 1
                cur = []
        diff = sum(
            1
            for r in range(cell_h)
            for c in range(len(g.rows[r]))
            if cell[r][c] != g.rows[r][c]
        )
        if diff:
            bad.append(f"U+{cp:04X} 差 {diff}px")
        if len(bad) >= 5:
            break
    if bad:
        raise SystemExit("TTF 内容校验失败: " + "; ".join(bad))
    print(f"  TTF 内容校验: {len(glyphs)} 字形轮廓全部落在像素网格上且与源位图一致")

    verify_ttf_metadata(tt, need_cp)


def verify_ttf_metadata(tt, need_cp: dict[int, str] | None = None) -> None:
    """OS/2 + gasp 的元数据不变量 —— 这几项直接决定"Word 里能不能用上本字体"。

    为什么单独拉出来: 字形轮廓对了, 不等于 Word 认得这个字体。
    实测过: 一份轮廓完全正确的 TTF, 因为 OS/2 的代码页位写错, 在 GDI 的 ANSI
    charset 请求下被替换成 Arial、在 GB2312 请求下被替换成宋体 —— 字是对的,
    字体却用不上。所以这组不变量是硬门禁, 不是注释。

    `need_cp` 让每个家族声明自己**必须**声明的代码页: Multi 12 覆盖谚文,
    就必须打开 bit19 (949 韩文), 否则 GDI 在 HANGEUL 下根本不考虑本字体。
    """
    from fontTools.ttLib.tables.O_S_2f_2 import intersectUnicodeRanges

    os2 = tt["OS/2"]

    # 1) 代码页位: 位号依 OpenType OS/2 规范 (1.9.1) 的 ulCodePageRange 表。
    need_cp = need_cp or {0: "1252 Latin1 (ANSI)", 17: "932 日文", 18: "936 简体中文"}
    miss = [f"bit{b}({n})" for b, n in need_cp.items() if not (os2.ulCodePageRange1 & (1 << b))]
    if miss:
        raise SystemExit(
            "TTF OS/2 缺代码页位: " + ", ".join(miss) + " —— Windows 字体映射器在对应 "
            "charset 下会替换本字体 (ANSI->Arial, GB2312->宋体)"
        )
    # 泰语位 (bit16 = 874) 曾经被误当成"东欧"写进来, 而字体里没有任何泰文字形。
    if os2.ulCodePageRange1 & (1 << 16):
        raise SystemExit("TTF OS/2 声明了 874 泰语代码页, 但字体里没有泰文字形 (虚报)")
    if os2.ulCodePageRange2:
        raise SystemExit(
            f"TTF OS/2 ulCodePageRange2=0x{os2.ulCodePageRange2:08X} 非零, "
            "但本字体不含这些 OEM 代码页的字符 (虚报)"
        )

    # 2) fsSelection: 必须声明 REGULAR, 且不能声明斜体。
    if not (os2.fsSelection & 0x0040):
        raise SystemExit("TTF OS/2 fsSelection 缺 REGULAR 位 (0x0040) —— Word 不认它是常规体")
    if os2.fsSelection & 0x0001:
        raise SystemExit("TTF OS/2 fsSelection 声明了 ITALIC, 但这是常规体")

    # 3) Unicode 区段位必须与 cmap 实际覆盖**完全一致**: 虚报会让系统把字体里
    #    没有的字符路由过来 -> 豆腐块; 漏报会让系统跳过本字体去做字体回退。
    cps: set[int] = set()
    for tbl in tt["cmap"].tables:
        if tbl.isUnicode():
            cps.update(tbl.cmap.keys())
    want = intersectUnicodeRanges(cps)
    got = os2.getUnicodeRanges()
    if want != got:
        raise SystemExit(
            "TTF OS/2 Unicode 区段位与 cmap 不一致: "
            f"虚报 {sorted(got - want)}, 漏报 {sorted(want - got)}"
        )

    # 4) gasp: 不允许任何字号开灰度抗锯齿 (像素字一开灰度就糊)。
    for max_ppem, behavior in tt["gasp"].gaspRange.items():
        if behavior & 0x0002:
            raise SystemExit(
                f"TTF gasp 在 <= {max_ppem}ppem 启用了灰度抗锯齿 (DOGRAY) -> 像素字会糊成灰边"
            )
        if behavior & 0x0001:
            raise SystemExit(
                f"TTF gasp 在 <= {max_ppem}ppem 启用了网格拟合 (GRIDFIT) -> "
                "autohinter 会把 1px 竖画吸附撑粗"
            )
    print(
        "  TTF 元数据校验: 代码页 1252/932/936 齐备, fsSelection=REGULAR, "
        "Unicode 区段位与 cmap 一致, gasp 全字号单色"
    )


def report_rasterizer_deviation(glyphs: list[GlyphData], ascent: int, path: Path, sample: int = 300) -> None:
    """量化渲染器在小字号下与本字体设计位图的偏差 —— 如实告知, 不是门禁。

    实测结论（Chrome + Pillow/FreeType 两个独立渲染器都验过）:
      · 24px 及以上: 偏差 0, 笔画严格 1px 宽, 锐利可用
      · 12px: 渲染器会做灰度抗锯齿 (Chrome) 或网格拟合 (Pillow/FreeType),
        1px 笔画被撑粗/发虚 —— 这是"用轮廓实现像素字"的格式固有属性,
        字体文件本身没错（轮廓内容已 4140 字全量校验通过）。

    所以追求像素精确的游戏应当用 BDF 或 PNG 图集, 两者都是逐像素校验过的。
    """
    from PIL import ImageFont

    step = max(1, len(glyphs) // sample)
    subset = glyphs[::step]
    report = []
    for size in (24, 12):
        f = ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.BASIC)
        px = size // 12
        total = worst = n = 0
        for g in subset:
            core, off = f.getmask2(g.ch, mode="1")
            w, h = core.size
            if w == 0 or h == 0:
                continue
            got = Image.frombuffer("L", (w, h), bytes(core)[: w * h])
            gp = got.load()
            diff = 0
            for y in range(g.height):
                # 掩码第 0 行对应 cell 第 off[1] 行, 所以 cell 行 y 对应掩码行 y - off[1]
                yy = y * px - off[1]
                for x in range(len(g.rows[y])):
                    want = 1 if g.rows[y][x] else 0
                    xx = x * px + off[0]
                    have = 1 if (0 <= yy < h and 0 <= xx < w and gp[xx, yy]) else 0
                    if want != have:
                        diff += 1
            total += diff
            worst = max(worst, diff)
            n += 1
        report.append(f"{size}px 平均 {total / max(1, n):.2f}px/字 (最坏 {worst})")
    print(f"  渲染器偏差抽样 {len(subset)} 字: " + " | ".join(report))
    print("    → 24px+ 精确; 12px 会被渲染器抗锯齿/网格拟合, 像素级用途请用 BDF 或图集")


# ---------------------------------------------------------------- main


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    items = build_charset()
    stack = build_stack()
    gate_full_coverage(stack, items)
    gate_ideo_route(stack, items)
    m = stack.metrics
    print(f"字符集 {len(items)} 字, 网格 {m.cell_w}x{m.cell_h}, 基线 {m.ascent}/{m.descent}")

    glyphs = collect_glyphs(stack, items)
    print(f"栅格化完成 {len(glyphs)} 字形")

    bdf = write_bdf(glyphs, m.ascent, m.descent, OUTDIR / f"{PS_NAME}.bdf")
    mp = write_bdf_map(glyphs, m.ascent, m.descent, OUTDIR / f"{PS_NAME}.bdf.map")
    ttf = write_ttf(glyphs, m.ascent, m.descent, OUTDIR / f"{PS_NAME}.ttf")
    png, js = write_atlas(glyphs, m.ascent, m.descent, columns=32, outdir=OUTDIR)
    spec = write_specimen(glyphs, m.ascent, m.descent, OUTDIR / f"{PS_NAME}-specimen.png")

    print("回读验证:")
    verify_bdf(glyphs, m.ascent, m.descent, bdf)
    verify_atlas(glyphs, m.ascent, png, js)
    verify_ttf(glyphs, m.ascent, m.descent, ttf)
    report_rasterizer_deviation(glyphs, m.ascent, ttf)

    print("产物:")
    for p in (ttf, bdf, mp, png, js, spec):
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()



