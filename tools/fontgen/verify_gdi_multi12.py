"""Multi 12 的 GDI 兼容门禁 —— 验的是**用户能不能在 Word 里用**。

与 `verify_gdi.py` 的差别只有两处, 其余量具全部复用:
  1. 字体是 `PixelFont Multi 12` (31,392 码位), 不是 `PixelFont PC98 12`;
  2. **语系期望反过来**: Multi 12 覆盖谚文 (U+AC00-U+D7AF), 所以
     `lfCharSet=HANGEUL` 时**必须选中本字体**; 而繁体 (BIG5) 不在字符集内,
     必须**选不中** —— 选中反而是虚报。

三条判据 (分层, 因为对系统设置的敏感度不同):
  a) 墨迹外框尺寸一致 —— 与抗锯齿无关, 任何系统上都必须成立 (硬门禁)
  b) 墨迹集合逐格一致 —— 强制单色渲染 (NONANTIALIASED) 时必须成立 (硬门禁)
  c) DEFAULT 质量下的抗锯齿像素数 —— 只是报告, 不是判据

用法:
    python tools/fontgen/verify_gdi_multi12.py
    python tools/fontgen/verify_gdi_multi12.py --ttf <回下载的 ttf 路径>
退出码 0 = 全过
"""

from __future__ import annotations

import argparse
import ctypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "fontgen"))

import verify_gdi as vg  # noqa: E402
from verify_products import read_bdf  # noqa: E402

#: 产物路径**从构建模块派生**, 不在这里写死 —— 写死过一次, 改名就漂了。
from build_font_multi12 import FONT_NAME, PS_NAME  # noqa: E402

TTF = ROOT / "dist" / f"{PS_NAME}.ttf"
BDF = ROOT / "dist" / f"{PS_NAME}.bdf"


def bdf_path_of(ttf: Path) -> Path:
    """由 TTF 路径推导同名 BDF 路径 (回下载验证用)。"""
    return ttf.with_suffix(".bdf")


#: Multi 12 覆盖到的代码页 -> 必须能选中的 charset
MUST_SELECT = {
    vg.CS_ANSI: "ANSI (西文)",
    vg.CS_DEFAULT: "DEFAULT",
    vg.CS_GB2312: "GB2312 (简体中文)",
    vg.CS_SHIFTJIS: "SHIFTJIS (日文)",
    vg.CS_HANGEUL: "HANGEUL (韩文) —— Multi 12 新增覆盖",
}
#: Multi 12 没覆盖的代码页 -> 必须**选不中**
MUST_NOT_SELECT = {
    vg.CS_BIG5: "BIG5 (繁体中文)",
}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="PixelFont Multi 12 的 GDI 兼容门禁")
    ap.add_argument("--ttf", default=None,
                    help="要验证的 TTF 路径 (默认 dist/ 里的)。"
                         "发布流程用它验证**回下载回来的**那份")
    ap.add_argument("--bdf", default=None,
                    help="对应的 BDF 路径 (默认与 --ttf 同名)")
    args = ap.parse_args()

    ttf = Path(args.ttf) if args.ttf else TTF
    bdf_path = Path(args.bdf) if args.bdf else (
        bdf_path_of(ttf) if args.ttf else BDF)

    if not ttf.exists():
        raise SystemExit(f"找不到成品字体: {ttf}\n先跑 tools/fontgen/build_font_multi12.py")
    if not bdf_path.exists():
        raise SystemExit(f"找不到 BDF: {bdf_path}")

    vg._bind()
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    bdf = read_bdf(bdf_path)

    print("== 0. 注册字体 ==")
    n = gdi32.AddFontResourceExW(str(ttf), vg.FR_PRIVATE, None)
    print(f"  {ttf}")
    print(f"  AddFontResourceExW -> {n}")
    if n == 0:
        raise SystemExit("GDI 拒绝注册该字体")

    print("=" * 74)
    print(f"{FONT_NAME} —— GDI 兼容门禁")
    print("=" * 74)

    print("\n== 1. 各 charset 下的字体选择 ==")
    failures: list[str] = []
    for cs, label in MUST_SELECT.items():
        face = vg.pick(gdi32, user32, cs, name=FONT_NAME)
        ok = face == FONT_NAME
        print(f"  [{'OK ' if ok else 'FAIL'}] lfCharSet={cs:<4} {label:<28} 选中={face!r}")
        if not ok:
            failures.append(f"charset {label} 选中了 {face!r} 而不是本字体")
    for cs, label in MUST_NOT_SELECT.items():
        face = vg.pick(gdi32, user32, cs, name=FONT_NAME)
        ok = face != FONT_NAME
        print(f"  [{'OK ' if ok else 'FAIL'}] lfCharSet={cs:<4} {label:<28} 选中={face!r} "
              f"(该语系不在字符集内, 选不中才对)")
        if not ok:
            failures.append(f"charset {label} 选中了本字体, 但字体没有该语系字形 (虚报)")

    print("\n== 2. EnumFontFamiliesEx 枚举 ==")
    for cs, label in MUST_SELECT.items():
        hit, cnt = vg.enum_has(gdi32, user32, cs, name=FONT_NAME)
        print(f"  [{'OK ' if hit else 'FAIL'}] lfCharSet={cs:<4} {label:<28} "
              f"枚举 {cnt} 族, 含本族={hit}")
        if not hit:
            failures.append(f"charset {label} 的字体枚举里没有本族")

    print("\n== 3. GDI 栅格化 vs 设计位图 (全字符集, 不抽样) ==")
    cv = vg.GdiCanvas(gdi32, user32, name=FONT_NAME)
    n12_box = n12_shape = n24_box = n24_shape = 0
    aa_total = 0
    scanned = 0
    try:
        for cp in sorted(bdf):
            w, h, bmp = bdf[cp]
            want = vg.design_cells(bmp)
            ch = chr(cp)
            mono12, _ = cv.render(ch, 12, 3)      # NONANTIALIASED
            _, aa = cv.render(ch, 12, 0)           # DEFAULT
            mono24, _ = cv.render(ch, 24, 3)
            aa_total += aa
            scanned += 1
            box_ok = vg.box_of(want) == vg.box_of(mono12)
            shape_ok = vg.normalize(want) == vg.normalize(mono12)
            exp24 = vg.scale_cells(want, 2)
            box24_ok = vg.box_of(exp24) == vg.box_of(mono24)
            shape24_ok = vg.normalize(exp24) == vg.normalize(mono24)
            n12_box += box_ok
            n12_shape += shape_ok
            n24_box += box24_ok
            n24_shape += shape24_ok
            if not (box_ok and shape_ok and box24_ok and shape24_ok):
                failures.append(f"U+{cp:04X} 栅格化与设计位图不一致")
    finally:
        cv.close()

    print(f"  扫描 {scanned} 个码位 x (12ppem + 24ppem)")
    print(f"  12ppem 墨迹外框一致      : {n12_box} / {scanned}")
    print(f"  12ppem 墨迹集合逐格一致  : {n12_shape} / {scanned}")
    print(f"  24ppem 墨迹外框一致      : {n24_box} / {scanned}")
    print(f"  24ppem 墨迹集合逐格一致  : {n24_shape} / {scanned}")
    print(f"  DEFAULT 质量下抗锯齿像素 : {aa_total}")

    print()
    print("=" * 74)
    if failures:
        print(f"门禁未过 ({len(failures)} 条):")
        for f in failures[:40]:
            print(f"  [FAIL] {f}")
        if len(failures) > 40:
            print(f"  ... 还有 {len(failures) - 40} 条")
        print("=" * 74)
        return 1
    print("门禁全过: 字体可被 GDI 选中, 全字符集 12ppem/24ppem 逐格一致")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
