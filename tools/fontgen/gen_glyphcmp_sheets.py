"""生成字形对照 PNG —— 供子代理逐字目视复核"我方画的到底是不是这个字"。

为什么用图而不是 ASCII 艺术:
    ASCII 点阵每字要 ~1KB 文字 (4140 字 = 4MB, 28 个子代理各读 50KB 才够);
    PNG 一格放得下"大号标注 + 三列点阵", 一张 128 字的图才 ~1.4k token。
    4140 字全量对照 = 33 张图, 这才叫"逐一比对"。

每格结构:
    ┌─────────────────────────┐
    │  仿  U+4F60              │  ← 用平滑字体(微软雅黑)渲染的标准字形 + 码位
    │  ##.##   ##.##   ....#   │  ← 我方 / Ark Pixel 12px / Unifont 16x16
    │  ...                      │
    └─────────────────────────┘
    标注字形给"标准答案", 三列点阵给"实测", 复核者只需回答:
    **我方那一列, 画的是不是标注的那个字?**
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))

import charset as cs  # noqa: E402
import verify_identity as vi  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LABEL_FONT = r"C:\Windows\Fonts\msyh.ttc"
LABEL_FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"


def render_sheet(
    entries: list[tuple[int, str, str, str]],
    ref_names: list[str],
    refs_by_name: dict[str, dict[int, "object"]],
    ours: dict[int, "object"],
    cols: int,
    rows: int,
    scale: int,
    out_path: Path,
) -> dict:
    """渲染一张对照表。entries = [(cp, char, category, label)]"""
    import numpy as np

    n_cols = 1 + len(ref_names)  # 我方 + 各参考
    glyph_w = 12 * scale
    gap = 2 * scale
    header_h = 26
    label_h = 30
    cell_w = n_cols * (glyph_w + gap)
    cell_h = label_h + 13 * scale + 4
    W = cols * cell_w
    H = header_h + rows * cell_h
    sheet = Image.new("RGB", (W, H), (18, 20, 26))
    d = ImageDraw.Draw(sheet)
    f_lab = ImageFont.truetype(LABEL_FONT, 20)
    f_code = ImageFont.truetype(LABEL_FONT, 12)
    f_head = ImageFont.truetype(LABEL_FONT_BOLD, 15)

    short = {
        "ark-pixel-zh_hans": "Ark",
        "ark-pixel-ja": "Ark",
        "fusion-pixel-zh_hans": "Fus",
        "fusion-pixel-ja": "Fus",
        "zpix": "Zpix",
        "unifont-16": "Uni",
    }
    heads = ["我方", *[short.get(n, n) for n in ref_names]]
    for c, h in enumerate(heads):
        d.text((c * (glyph_w + gap) + 2, 4), h, font=f_head, fill=(140, 200, 255))
    d.line([(0, header_h - 2), (W, header_h - 2)], fill=(70, 90, 130), width=2)

    for i, (cp, ch, cat, _label) in enumerate(entries):
        cx = (i % cols) * cell_w
        cy = header_h + (i // cols) * cell_h
        d.rectangle([cx, cy, cx + cell_w - 1, cy + cell_h - 1], outline=(45, 52, 70))
        # 标准字形标注 (平滑字体, 不是点阵) —— 复核者的"标准答案"
        d.text((cx + 4, cy + 3), ch, font=f_lab, fill=(255, 236, 200))
        d.text((cx + 30, cy + 9), f"U+{cp:04X}", font=f_code, fill=(120, 130, 150))
        # 三列点阵
        base_y = cy + label_h
        arrs = [ours.get(cp)] + [refs_by_name[n].get(cp) for n in ref_names]
        for c, arr in enumerate(arrs):
            ox = cx + 2 + c * (glyph_w + gap)
            if arr is None:
                d.text((ox, base_y + 4), "缺", font=f_code, fill=(200, 90, 90))
                continue
            a = np.asarray(arr, dtype=np.uint8) * 255
            im = Image.fromarray(a, mode="L").resize(
                (arr.shape[1] * scale, arr.shape[0] * scale), Image.NEAREST
            )
            sheet.paste(im.convert("RGB"), (ox, base_y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return {
        "sheet": out_path.name,
        "chars": [f"U+{cp:04X}" for cp, _, _, _ in entries],
        "count": len(entries),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="生成字形对照 PNG")
    ap.add_argument("--refs", default="ark-pixel-zh_hans,unifont-16", help="参考字体, 逗号分隔")
    ap.add_argument("--cats", default="", help="类别: ascii,punct,kana,hanzi")
    ap.add_argument("--slice", dest="slice_", default="", help="切片 如 0:1000")
    ap.add_argument(
        "--chars",
        default="",
        help="定点选择: 十六进制码位列表, 如 91CF,7F6E,53E0 (优先于 --cats/--slice)",
    )
    ap.add_argument("--outdir", required=True, help="PNG 输出目录")
    ap.add_argument("--index", default="", help="索引 JSON 输出路径")
    ap.add_argument("--cols", type=int, default=16)
    ap.add_argument("--rows", type=int, default=8)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--prefix", default="glyphcmp")
    args = ap.parse_args()

    items = cs.build_charset()
    stack = cs.build_stack()
    cats = [c.strip() for c in args.cats.split(",") if c.strip()]
    sel = [(ch, cat) for ch, cat in items if (not cats or cat in cats)]
    if args.slice_:
        a, _, b = args.slice_.partition(":")
        sel = sel[int(a) if a else 0 : int(b) if b else len(sel)]
    if args.chars:
        # 定点选择: 保留 --cats 过滤后的类别信息, 但只保留指定码位
        want = {int(tok, 16) for tok in args.chars.replace("U+", "").split(",") if tok.strip()}
        cat_of = {ord(ch): cat for ch, cat in sel}
        sel = [(chr(cp), cat_of.get(cp, "?")) for cp in sorted(want) if cp in cat_of]
        missing = want - set(cat_of)
        if missing:
            print(f"⚠ 字符集里没有这些码位: {' '.join(f'U+{c:04X}' for c in sorted(missing))}", file=sys.stderr)
    if not sel:
        print("选择为空", file=sys.stderr)
        return 2

    ref_names = [r.strip() for r in args.refs.split(",") if r.strip()]
    refs_by_name: dict[str, dict] = {}
    for name in ref_names:
        if name not in vi.REFS:
            print(f"未知参考字体 {name}", file=sys.stderr)
            return 2
        meta = vi.REFS[name]
        p = vi.REFDIR / meta["path"]
        if not p.exists():
            print(f"参考字体缺失: {p}", file=sys.stderr)
            return 2
        from fontTools.ttLib import TTFont

        tt = TTFont(str(p), fontNumber=0)
        refs_by_name[name], fails = vi.ref_glyphs(p, meta["ppem"], sorted(tt.getBestCmap().keys()))
        print(f"参考字体 {name}: {len(refs_by_name[name])} 字形 (失败 {fails})")

    ours = vi.our_glyphs(stack, sel)
    outdir = Path(args.outdir)
    per = args.cols * args.rows
    index = {
        "tool": "gen_glyphcmp_sheets",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "refs": ref_names,
        "cols": args.cols,
        "rows": args.rows,
        "per_sheet": per,
        "sheets": [],
    }
    for i in range(0, len(sel), per):
        chunk = sel[i : i + per]
        entries = [(ord(ch), ch, cat, ch) for ch, cat in chunk]
        p = outdir / f"{args.prefix}_{i // per:03d}.png"
        info = render_sheet(entries, ref_names, refs_by_name, ours, args.cols, args.rows, args.scale, p)
        index["sheets"].append(info)
        print(f"  {p.name}: {info['count']} 字")

    if args.index:
        Path(args.index).parent.mkdir(parents=True, exist_ok=True)
        Path(args.index).write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"索引: {args.index}  ({len(index['sheets'])} 张)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
