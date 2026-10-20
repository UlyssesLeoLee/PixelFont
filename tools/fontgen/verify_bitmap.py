"""栅格化正确性验证 —— 把点阵直接打印成 ASCII 艺术, 肉眼确认不是垃圾。

这个脚本的价值在于: 我可以在生成任何 PNG 之前, 先确认 (1) MONO 渲染真的在起作用,
(2) 字形没有错位/竖切, (3) 拉丁基线一致, (4) 全角格被填满。
"""

from __future__ import annotations

import sys

sys.path.insert(0, r"E:\PixelFont\tools\fontgen")

from bitfont import BitmapFont, to_ascii  # noqa: E402

CANDIDATES = [
    ("MSGothic-12 (PC-98)", dict(path=r"C:\Windows\Fonts\msgothic.ttc", index=0, px=12)),
    ("MSMincho-12", dict(path=r"C:\Windows\Fonts\msmincho.ttc", index=0, px=12)),
    ("SimSun-12 (枫叶镇)", dict(path=r"C:\Windows\Fonts\simsun.ttc", index=0, px=12)),
    ("MSMincho-16", dict(path=r"C:\Windows\Fonts\msmincho.ttc", index=0, px=16)),
]

SAMPLE = "中あA"


def show(label: str, cfg: dict) -> None:
    f = BitmapFont(**cfg)
    m = f.metrics
    print("=" * 78)
    print(f"{label}  name={f.name}")
    print(f"  px={m.px} cell={m.cell_w}x{m.cell_h} half={m.half_w} asc={m.ascent} desc={m.descent}")
    # 多字并排, 检查基线与格宽对齐
    strip = Image_strip(f, SAMPLE)
    for i, ch in enumerate(SAMPLE):
        g = f.glyph(ch)
        print(f"  -- '{ch}' {g.width}x{g.height} ink_cols={_ink(g)}")
    print(strip)


def Image_strip(font: BitmapFont, text: str) -> str:
    from PIL import Image

    w = font.text_width(text, spacing=1) + 2
    h = font.metrics.cell_h
    canvas = Image.new("L", (w, h), 0)
    font.draw_text(canvas, (1, 0), text, spacing=1)
    return to_ascii(canvas)


def _ink(img) -> tuple[int, int]:
    px = img.load()
    xs = [x for y in range(img.height) for x in range(img.width) if px[x, y] > 0]
    ys = [y for y in range(img.height) for x in range(img.width) if px[x, y] > 0]
    if not xs:
        return (0, 0)
    return (min(xs), max(xs))


if __name__ == "__main__":
    for label, cfg in CANDIDATES:
        try:
            show(label, cfg)
        except Exception as e:  # noqa: BLE001
            print("=" * 78)
            print(label, "FAILED:", type(e).__name__, e)
