"""独立核对: dist/ 里的成品是否与**当前源**同步 (不是靠构建脚本自证)。

为什么要有这个:
    构建脚本自己会校验"产物 == 源位图", 但那是**同一次运行内部**的自证。
    真正会出事的情况是: 路由名单改了 / 源字体换了, 但**忘了重建** ——
    此时产物还是旧的, 而构建脚本根本不会被执行, 也就不会报错。
    这个工具独立读 dist/ 里的成品, 与当前栅格化器的输出逐字比对。

方法: 读 BDF (位图字体, 每个字形就是一张位图, 逐像素可比, 不受渲染器影响),
      与当前源的墨迹外接框逐字比对。
      TTF 另做"轮廓必须落在像素网格上"的检查 (轮廓坐标是 64 单位的整数倍)。

用法:
    python tools/fontgen/verify_products.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from fontTools.ttLib import TTFont

import charset as cs

ROOT = Path(__file__).resolve().parents[2]
BDF = ROOT / "dist" / "PixelFontPC98-12.ttf".replace(".ttf", ".bdf")
TTF = ROOT / "dist" / "PixelFontPC98-12.ttf"


def read_bdf(path: Path) -> dict[int, tuple[int, int, list]]:
    """读 BDF 的字形位图。返回 码位 -> (宽, 高, 位图)。"""
    out: dict[int, tuple[int, int, list]] = {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    cp = None
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if ln.startswith("ENCODING "):
            cp = int(ln.split()[1])
        elif ln.startswith("BITMAP") and cp is not None:
            bbx = None
            for k in range(i - 1, max(i - 6, -1), -1):
                if lines[k].strip().startswith("BBX "):
                    bbx = lines[k].strip().split()
                    break
            if bbx is None:
                i += 1
                continue
            w, h = int(bbx[1]), int(bbx[2])
            nbytes = (w + 7) // 8
            rows_bits = []
            for r in range(h):
                v = int(lines[i + 1 + r].strip(), 16)
                # BDF 每行按**字节**补齐, 像素从最高位起排:
                # 像素 c = 整行整数 (nbytes*8 位) 的第 (nbytes*8-1-c) 位
                rows_bits.append([(v >> (nbytes * 8 - 1 - c)) & 1 for c in range(w)])
            out[cp] = (w, h, rows_bits)
            cp = None
        i += 1
    return out


def main() -> int:
    for p in (BDF, TTF):
        if not p.exists():
            print(f"缺少产物: {p} (先跑 build_font.py)", file=sys.stderr)
            return 2
    stack = cs.build_stack()
    items = cs.build_charset()
    bdf = read_bdf(BDF)
    bad: list[str] = []
    checked = 0
    for ch, _cat in items:
        cp = ord(ch)
        img = np.array(stack.glyph(ch), dtype=np.uint8) > 0
        ys, xs = np.nonzero(img)
        if not len(xs):
            continue
        crop = img[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
        rec = bdf.get(cp)
        if rec is None:
            bad.append(f"U+{cp:04X} {ch!r} 产物里没有这个码位")
            continue
        w, h, bits = rec
        checked += 1
        if (w, h) != (crop.shape[1], crop.shape[0]) or not (
            crop == np.array(bits, dtype=bool)
        ).all():
            bad.append(f"U+{cp:04X} {ch!r} 产物位图与当前源不一致")

    # TTF: 轮廓必须落在像素网格上 (1 像素 = 64 单位)
    tt = TTFont(str(TTF))
    px = 64
    grid_bad = 0
    for ch, _cat in items:
        cp = ord(ch)
        name = tt.getBestCmap().get(cp)
        if name is None:
            continue
        g = tt["glyf"][name]
        coords, _end, _flags = g.getCoordinates(tt["glyf"])
        for x, y in coords:
            if x % px or y % px:
                grid_bad += 1
                break

    print(f"BDF 与当前源逐字比对: {checked} 个字, 不一致 {len(bad)} 个")
    for b in bad[:20]:
        print("   " + b)
    if len(bad) > 20:
        print(f"   ... 还有 {len(bad) - 20} 个")
    print(f"TTF 轮廓落在像素网格上: {'全部通过' if grid_bad == 0 else f'{grid_bad} 个字有非网格坐标'}")
    ok = not bad and grid_bad == 0
    print("判定: " + ("产物与当前源同步" if ok else "产物与当前源**不同步** —— 需要重建"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
