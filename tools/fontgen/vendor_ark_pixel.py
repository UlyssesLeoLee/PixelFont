"""把 Ark Pixel 12px 简体裁剪到本项目字符集, 作为**生产源**入库。

为什么参考字体不入库、这个要入库:
    参考字体只用于**校验**, 不参与构建, 所以只记来源/版本/许可证/sha256。
    而生产源必须入库 —— 否则构建依赖"某台机器上恰好装了/下载了某个字体",
    换台机器就构建不出同一个结果, 也就谈不上"可复现"。
    Ark Pixel 是 OFL-1.1, 允许再分发 (须附许可证), 裁剪后约 730 KB。

用法:
    python tools/fontgen/vendor_ark_pixel.py            # 生成 + 验证
    python tools/fontgen/vendor_ark_pixel.py --check    # 只验证已入库的裁剪版

验证做两件事 (缺一不可):
    1. 裁剪前后**逐像素一致** (同一码位渲染出完全相同的位图)
    2. 裁剪版的 cmap 覆盖 = 原字体 cmap 覆盖 ∩ 本项目字符集
       —— 少了就是裁剪把字弄丢了; 多了就是裁剪没生效。
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from fontTools.ttLib import TTFont

import charset as cs
from bitfont import BitmapFont
from coverage import cmap_for

ROOT = Path(__file__).resolve().parents[2]
FULL = (
    ROOT
    / "third_party"
    / "ref_fonts"
    / "ark-pixel-12px"
    / "ark-pixel-12px-monospaced-zh_hans.ttf"
)
VENDOR_DIR = ROOT / "vendor" / "ark-pixel-12px"
SUBSET = VENDOR_DIR / "ark-pixel-12px-monospaced-zh_hans-subset.ttf"
LICENSE = VENDOR_DIR / "OFL.txt"
LICENSE_SRC = (
    ROOT / "third_party" / "ref_fonts" / "ark-pixel-12px" / "OFL.txt"
)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def our_cps() -> list[int]:
    return [ord(ch) for ch, _cat in cs.build_charset()]


def build_subset() -> None:
    if not FULL.exists():
        raise SystemExit(
            f"缺少原始下载: {FULL}\n先跑 tools/fontgen/fetch_ref_fonts.py"
        )
    if not LICENSE_SRC.exists():
        raise SystemExit(f"缺少许可证: {LICENSE_SRC}")
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    cps = our_cps()
    # fontTools 的 --unicodes 收的是**十六进制码位**, 不带 U+ 前缀;
    # 写成 "U+4E01" 会被静默忽略一部分, 然后那些码位退化成 .notdef ——
    # 而 .notdef 是空心豆腐框, 自带 1 个"字腔", 正是本项目反复踩的那个坑。
    uni = ",".join("%04X" % c for c in cps)
    import subprocess

    cmd = [
        sys.executable,
        "-m",
        "fontTools.subset",
        str(FULL),
        f"--unicodes={uni}",
        f"--output-file={SUBSET}",
        "--layout-features=",
        "--name-IDs=*",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"裁剪失败:\n{r.stdout}\n{r.stderr}")
    shutil.copyfile(LICENSE_SRC, LICENSE)
    print(f"裁剪完成: {SUBSET} ({SUBSET.stat().st_size} 字节)")
    print(f"许可证:   {LICENSE}")


def verify() -> int:
    if not SUBSET.exists():
        print(f"缺少裁剪版: {SUBSET}", file=sys.stderr)
        return 2
    if not FULL.exists():
        print(f"缺少原始下载 (无法做逐像素对照): {FULL}", file=sys.stderr)
        return 2
    full_cps = cmap_for(str(FULL), 0)
    sub_cps = cmap_for(str(SUBSET), 0)
    want = set(our_cps())
    missing = sorted(want - set(full_cps))
    expect_sub = set(full_cps) & want
    print(f"原字体覆盖本项目字符集: {len(set(full_cps) & want)} / {len(want)}")
    print(f"  本项目需要但 Ark 根本没有的: {len(missing)} 个")
    if missing:
        print(
            "    例: "
            + " ".join("U+%04X" % c for c in missing[:12])
            + (" ..." if len(missing) > 12 else "")
        )
    if set(sub_cps) != expect_sub:
        print(
            f"✗ 裁剪版 cmap 与期望不符: 多 {sorted(set(sub_cps) - expect_sub)[:8]} "
            f"少 {sorted(expect_sub - set(sub_cps))[:8]}"
        )
        return 1
    print("✓ 裁剪版 cmap = 原字体 cmap ∩ 本项目字符集")

    f_full = BitmapFont(path=str(FULL), index=0, px=12, cell_ascent=11, cell_descent=2)
    f_sub = BitmapFont(path=str(SUBSET), index=0, px=12, cell_ascent=11, cell_descent=2)
    diff = 0
    n = 0
    for cp in sorted(expect_sub):
        ch = chr(cp)
        a = np.array(f_full.glyph(ch), dtype=np.uint8)
        b = np.array(f_sub.glyph(ch), dtype=np.uint8)
        n += 1
        if a.shape != b.shape or not (a == b).all():
            diff += 1
    print(f"逐像素对照: {n} 个字形, 不一致 {diff} 个")
    if diff:
        return 1
    print("✓ 裁剪前后渲染逐像素一致")
    print(f"sha256({SUBSET.name}) = {sha256(SUBSET)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="裁剪并验证 Ark Pixel 生产源")
    ap.add_argument("--check", action="store_true", help="只验证, 不重新裁剪")
    args = ap.parse_args()
    if not args.check:
        build_subset()
    return verify()


if __name__ == "__main__":
    sys.exit(main())
