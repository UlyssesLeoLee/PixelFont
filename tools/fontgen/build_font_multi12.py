"""构建 `PixelFont Multi 12` —— 31,392 码位的多语言家族。

与当前家族 `PixelFont PC98 12` 的三点关键差别:

1. **字符集**: 4,161 → **31,392** (方案 C), 见 `charset_multi12.py` 的逐层账目。
2. **生产源全部宽松许可**: Fusion Pixel 12px (OFL-1.1) 四个变体 + 本仓库
   **原创手绘**的 4 个字形 (OFL-1.1)。当前家族有 3,053/4,161 个码位派生自
   SimHei / MS Gothic (微软专有), 所以 `dist/` 不入库; Multi 12 没有这个问题,
   成品**可以入库存放、用户可自由分发**。
3. **家族独立**: `PixelFont Multi 12` / PostScript `PixelFontMulti12`。
   现有 `PixelFont PC98 12` 一行代码都不改。

轮廓生成、竖向游程合并、OS/2 元数据、gasp、回读验证全部复用 `build_font.py`
的同一套实现 —— 两套家族必须产出**同一种**字体, 差别只在字符集、字形来源与名表。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "fontgen"))

import build_font as bf  # noqa: E402
import route_multi12 as rm  # noqa: E402
from bitfont import BitmapFont, RouteStack  # noqa: E402
from handdrawn import HanddrawnFont  # noqa: E402
from vendor_multi12_sources import subset_path  # noqa: E402

OUTDIR = ROOT / "dist"
FONT_NAME = "PixelFont Multi 12"
PS_NAME = "PixelFontMulti12"
XLFD_MULTI12 = "-PF-PixelFontMulti12-Medium-R-Normal--12-1200-72-72-c-1000-ISO10646-1"

#: OS/2 ulCodePageRange1: bit0=1252 ANSI / bit17=932 日文 / bit18=936 简体中文 /
#: **bit19=949 韩文**。Multi 12 覆盖 11,172 个谚文音节, bit19 必须打开 ——
#: 不打开的话 GDI 在 lfCharSet=HANGEUL 下**根本不会考虑本字体** (实测枚举到 0 族),
#: 韩文正文会被回退到系统字体。繁体 (950) 不设: 字符集里没有 zh_hant。
CODE_PAGE_RANGE1 = (1 << 0) | (1 << 17) | (1 << 18) | (1 << 19)

#: 必须声明的代码页位 (回读时当硬门禁查)
NEED_CP = {0: "1252 Latin1 (ANSI)", 17: "932 日文", 18: "936 简体中文",
           19: "949 韩文"}

COPYRIGHT = (
    "PixelFont Multi 12. Glyphs derived from Fusion Pixel 12px (SIL OFL 1.1); "
    "4 hand-drawn glyphs (c) 2026 UlyssesLeoLee, also SIL OFL 1.1."
)
LICENSE = (
    "12px monospaced bitmap font covering 31,392 code points "
    "(Simplified Chinese / Japanese / Korean / Latin / Greek / Cyrillic). "
    "Licensed under the SIL Open Font License 1.1."
)


def build_stack() -> RouteStack:
    """按路由表建 5 源的字形栈。生产源读**入库的裁剪版** (不读 third_party)。"""
    sources = {}
    for key in ("fusion_latin", "fusion_ko", "fusion_ja", "fusion_zh_hans"):
        p = subset_path(key)
        if not p.exists():
            raise SystemExit(
                f"缺少入库的生产源 {p}\n先跑: python tools/fontgen/vendor_multi12_sources.py"
            )
        sources[key] = BitmapFont(path=str(p), index=0, px=12, cell_ascent=11, cell_descent=2)
    sources["handdrawn"] = HanddrawnFont()
    route = rm.snapshot_route()
    return RouteStack(sources, route, primary="fusion_ja")


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rm.require_sources()

    # 快照自洽门禁: 字符集、路由、层归属、入库生产源的字形覆盖 —— 四件事一次查完。
    # 这一道门禁**不需要 third_party**, 所以干净克隆上也能跑。
    snap = rm.verify_snapshot()
    print(f"快照自洽门禁: {snap['total']} 码位 / {snap['sources']} 源 / "
          f"{snap['layers']} 层 OK")

    items = rm.snapshot_charset()
    stack = build_stack()
    m = stack.metrics
    route = rm.snapshot_route()
    from collections import Counter
    per_source = Counter(route.values())
    print(f"字符集 {len(items)} 字, 网格 {m.cell_w}x{m.cell_h}, 基线 {m.ascent}/{m.descent}")
    print("源分布: " + ", ".join(f"{k}={v}" for k, v in per_source.most_common()))

    glyphs = bf.collect_glyphs(stack, items)
    print(f"栅格化完成 {len(glyphs)} 字形")

    bdf = bf.write_bdf(glyphs, m.ascent, m.descent, OUTDIR / f"{PS_NAME}.bdf", xlfd=XLFD_MULTI12)
    mp = bf.write_bdf_map(glyphs, m.ascent, m.descent, OUTDIR / f"{PS_NAME}.bdf.map",
                          xlfd=XLFD_MULTI12)
    ttf = bf.write_ttf(glyphs, m.ascent, m.descent, OUTDIR / f"{PS_NAME}.ttf",
                       family_name=FONT_NAME, ps_name=PS_NAME,
                       copyright_text=COPYRIGHT, license_text=LICENSE,
                       code_page_range1=CODE_PAGE_RANGE1)
    png, js = bf.write_atlas(glyphs, m.ascent, m.descent, columns=64, outdir=OUTDIR,
                             ps_name=PS_NAME, font_name=FONT_NAME)
    spec = bf.write_specimen(glyphs, m.ascent, m.descent, OUTDIR / f"{PS_NAME}-specimen.png")

    print("回读验证:")
    bf.verify_bdf(glyphs, m.ascent, m.descent, bdf)
    bf.verify_atlas(glyphs, m.ascent, png, js)
    bf.verify_ttf(glyphs, m.ascent, m.descent, ttf, need_cp=NEED_CP)
    bf.report_rasterizer_deviation(glyphs, m.ascent, ttf, sample=600)

    print("产物:")
    for p in (ttf, bdf, mp, png, js, spec):
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
