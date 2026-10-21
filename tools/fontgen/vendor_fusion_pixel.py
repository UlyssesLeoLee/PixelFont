"""把 Fusion Pixel 12px 简体裁剪到本项目字符集, 作为**生产源**入库。

为什么是 Fusion 而不是 Ark Pixel:
    实测 Fusion 的简体版与 Ark 的**结构**完全相同 (3605 个共有汉字逐个一致),
    但**覆盖**多 12054 个码位 —— 它把 Ark / Cubic 11 / Galmuri 缝进了同一套字重体系。
    对我们 4140 个码位:
        Ark Pixel 覆盖 3990 (缺 150)
        Fusion Pixel 覆盖 **4140 (不缺)**
    而两者的共有部分**位图逐字节相同** (实测 3989/3989) ——
    所以把生产源从 Ark 换成 Fusion, 对 3989 个字**零画风变化**,
    却让原先没得选的 150 个字 (酱/誊/鳖/蛰/嘎/撬/橇 ...) 有了真正的点阵字形。
    实测那 7 个仍未修的字, 换源后与独立参考 Unifont 的结构距离:
        Fusion 30-71  vs  SimHei 56-89 / MS Gothic 76-79  —— 明显更好。
    (Zpix 的字形是 13 宽, 放不进我们 12px 的全角格, 所以它当不了生产源。)

为什么生产源必须入库:
    参考字体只用于**校验**, 不参与构建, 所以不入库;
    生产源参与构建, 不入库就等于"构建依赖这台机器上恰好下载过某个字体",
    换台机器构建不出同一个结果。

用法:
    python tools/fontgen/vendor_fusion_pixel.py           # 生成 + 验证
    python tools/fontgen/vendor_fusion_pixel.py --check   # 只验证已入库的裁剪版

验证做两件事 (缺一不可):
    1. 裁剪前后**逐像素一致** (同一码位渲染出完全相同的位图)
    2. 裁剪版的 cmap 覆盖 == 原字体 cmap ∩ 本项目字符集
       —— 少了就是裁剪把字弄丢了; 多了就是裁剪没生效。
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "fontgen"))

from fontTools.ttLib import TTFont  # noqa: E402

import charset as cs  # noqa: E402
from bitfont import BitmapFont  # noqa: E402
from coverage import cmap_for  # noqa: E402

FULL = (
    ROOT
    / "third_party"
    / "ref_fonts"
    / "fusion-pixel-12px"
    / "fusion-pixel-12px-monospaced-zh_hans.ttf"
)
VENDOR_DIR = ROOT / "vendor" / "fusion-pixel-12px"
SUBSET = VENDOR_DIR / "fusion-pixel-12px-monospaced-zh_hans-subset.ttf"
LICENSES = VENDOR_DIR / "LICENSES"
FULL_LICENSES = (
    ROOT / "third_party" / "ref_fonts" / "fusion-pixel-12px" / "LICENSES"
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
        raise SystemExit(f"缺少原始下载: {FULL}\n先跑 tools/fontgen/fetch_ref_fonts.py")
    if not FULL_LICENSES.exists():
        raise SystemExit(f"缺少许可证目录: {FULL_LICENSES}")
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    LICENSES.mkdir(parents=True, exist_ok=True)
    cps = our_cps()
    # fontTools 的 --unicodes 收的是**十六进制码位**, 不带 U+ 前缀;
    # 写成 "U+4E01" 会被静默忽略一部分, 然后那些码位退化成 .notdef ——
    # 而 .notdef 是空心豆腐框, 自带 1 个"字腔", 会把"缺字"误判成"能画"。
    uni = ",".join("%04X" % c for c in cps)
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
    for name, dst in (
        ("ark-pixel/OFL.txt", "ark-pixel-OFL.txt"),
        ("cubic-11/OFL.txt", "cubic-11-OFL.txt"),
        ("galmuri/LICENSE.txt", "galmuri-LICENSE.txt"),
    ):
        shutil.copyfile(FULL_LICENSES / name, LICENSES / dst)
    print(f"裁剪完成: {SUBSET} ({SUBSET.stat().st_size} 字节)")
    print(f"许可证:   {LICENSES} (Ark Pixel / Cubic 11 / Galmuri 三份)")


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
    if missing:
        print(
            "  本项目需要但原字体根本没有的: %d 个 (例: %s)"
            % (len(missing), " ".join("U+%04X" % c for c in missing[:8]))
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
        a = f_full.glyph(ch)
        b = f_sub.glyph(ch)
        n += 1
        if a.size != b.size or bytes(a.tobytes()) != bytes(b.tobytes()):
            diff += 1
    print(f"逐像素对照: {n} 个字形, 不一致 {diff} 个")
    if diff:
        return 1
    print("✓ 裁剪前后渲染逐像素一致")
    print(f"sha256({SUBSET.name}) = {sha256(SUBSET)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="裁剪并验证 Fusion Pixel 生产源")
    ap.add_argument("--check", action="store_true", help="只验证, 不重新裁剪")
    args = ap.parse_args()
    if not args.check:
        build_subset()
    return verify()


if __name__ == "__main__":
    sys.exit(main())
