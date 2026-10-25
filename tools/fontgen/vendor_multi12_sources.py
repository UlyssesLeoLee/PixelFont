"""把 Multi 12 的 4 个 Fusion 生产源裁剪到各自负责的码位, 作为**生产源**入库。

为什么生产源必须入库 (与 `vendor_fusion_pixel.py` 同一条理由):
    参考字体只用于**校验**, 不参与构建, 所以不入库;
    生产源参与构建, 不入库就等于「构建依赖这台机器上恰好下载过某个字体」,
    换台机器构建不出同一个结果。

**Multi 12 与当前家族的关键差别**: 当前家族的生产源有 SimHei / MS Gothic
(微软专有), 所以成品 `dist/` 不入库; Multi 12 的生产源**全部是宽松许可**
(Fusion = OFL-1.1 + 本仓库原创手绘 4 字形), 所以成品可以入库存放、
用户可自由分发。

裁剪口径: 每个源只保留**路由表分配给它**的码位 (不是全部 31,392) ——
fusion_ja 只留 17,544 个, fusion_ko 只留 11,172 个, 依此类推。

用法:
    python tools/fontgen/vendor_multi12_sources.py           # 生成 + 验证
    python tools/fontgen/vendor_multi12_sources.py --check   # 只验证已入库的裁剪版

验证做两件事 (缺一不可):
    1. 裁剪前后**逐像素一致** (同一码位渲染出完全相同的位图)
    2. 裁剪版的 cmap 覆盖 == 原字体 cmap ∩ 该源负责的码位
       —— 少了就是裁剪把字弄丢了; 多了就是裁剪没生效。
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "fontgen"))

from fontTools.subset import Options, Subsetter  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

import route_multi12 as rm  # noqa: E402
from bitfont import BitmapFont  # noqa: E402

VENDOR_DIR = ROOT / "vendor" / "multi12"
LICENSES = VENDOR_DIR / "LICENSES"
FULL_LICENSES = ROOT / "third_party" / "ref_fonts" / "fusion-pixel-12px" / "LICENSES"

#: 需要裁剪的 Fusion 变体 (手绘源不入库 —— 它本来就是本仓库的数据文件)
FUSION_KEYS = ("fusion_latin", "fusion_ko", "fusion_ja", "fusion_zh_hans")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def subset_path(key: str) -> Path:
    """入库的裁剪版路径。名字由**原始下载**的文件名派生 —— 裁剪版是原始的派生物。"""
    name = rm.origin_path(key).name.replace(".ttf", "-subset.ttf")
    return VENDOR_DIR / name


def assigned_cps() -> dict[str, list[int]]:
    route = rm.build_route()
    out: dict[str, list[int]] = {k: [] for k in FUSION_KEYS}
    for cp, s in route.items():
        if s in out:
            out[s].append(cp)
    return {k: sorted(v) for k, v in out.items()}


def build_subset(key: str, cps: list[int]) -> None:
    src = rm.origin_path(key)
    if not src.exists():
        raise SystemExit(f"缺少原始下载: {src}\n先跑 tools/fontgen/fetch_ref_fonts.py")
    dst = subset_path(key)
    f = TTFont(str(src), fontNumber=0)
    opts = Options()
    opts.name_IDs = ["*"]
    opts.layout_features = []
    opts.glyph_names = False
    sub = Subsetter(options=opts)
    sub.populate(unicodes=cps)
    sub.subset(f)
    f.save(str(dst))
    print(f"  {key:<14} {len(cps):>6} 码位 -> {dst.name} ({dst.stat().st_size} 字节)")


def verify() -> int:
    """两层验证, 缺一不可:

    1. **裁剪版 cmap == 路由分配给该源的码位集合** —— 不依赖原始下载, 任何机器都能查。
       少了 = 裁剪把字弄丢了; 多了 = 裁剪没生效。
    2. **裁剪前后逐像素一致** —— 需要原始下载, 没有就显式 SKIP (不是「通过」)。

    第 2 层在缺原始下载的机器上无法执行, 此时必须**说清楚没验**,
    不能让「SKIP」看起来像「通过」。
    """
    bad = 0
    skipped = 0
    assigned = assigned_cps()
    print("=== 逐源验证 ===")
    for key in FUSION_KEYS:
        src = rm.origin_path(key)
        sub = subset_path(key)
        if not sub.exists():
            print(f"[FAIL] {key}: 缺少裁剪版 {sub}")
            bad += 1
            continue

        want = set(assigned[key])
        f_sub = TTFont(str(sub), fontNumber=0, lazy=True)
        sub_cps = set(f_sub.getBestCmap())
        f_sub.close()

        if sub_cps != want:
            print(f"[FAIL] {key}: 裁剪版 cmap 与路由分配不符 "
                  f"(多 {len(sub_cps - want)} / 少 {len(want - sub_cps)})")
            bad += 1
            continue

        if not src.exists():
            skipped += 1
            print(f"[SKIP] {key}: cmap 覆盖 {len(sub_cps)} 码位 ✓, "
                  f"但缺原始下载, **逐像素对照未做** ({src})")
            continue

        f_src = TTFont(str(src), fontNumber=0, lazy=True)
        src_cps = set(f_src.getBestCmap())
        f_src.close()

        missing = want - src_cps
        if missing:
            print(f"[FAIL] {key}: 原字体缺少 {len(missing)} 个该源的码位 "
                  f"({', '.join('U+%04X' % c for c in sorted(missing)[:6])})")
            bad += 1

        bf_src = BitmapFont(path=str(src), index=0, px=12, cell_ascent=11, cell_descent=2)
        bf_sub = BitmapFont(path=str(sub), index=0, px=12, cell_ascent=11, cell_descent=2)
        diff = 0
        n = 0
        for cp in sorted(want):
            ch = chr(cp)
            a = bf_src.glyph(ch)
            b = bf_sub.glyph(ch)
            n += 1
            if a.size != b.size or bytes(a.tobytes()) != bytes(b.tobytes()):
                diff += 1
        print(f"[{'OK  ' if diff == 0 else 'FAIL'}] {key:<14} 逐像素对照 {n} 个字形, "
              f"不一致 {diff} 个  sha256={sha256(sub)[:16]}…")
        if diff:
            bad += 1
    if skipped:
        print(f"  注意: {skipped} 个源**未做**逐像素对照 (缺 third_party 原始下载) —— "
              f"该层结论待验证, 验证方法: python tools/fontgen/fetch_ref_fonts.py "
              f"后重跑本脚本")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description="裁剪并验证 Multi 12 的 Fusion 生产源")
    ap.add_argument("--check", action="store_true", help="只验证, 不重新裁剪")
    args = ap.parse_args()

    # 重新裁剪需要**原始下载**; `--check` 只核对入库的裁剪版, 不需要原始。
    if args.check:
        rm.require_sources()
    else:
        rm.require_origins()
    assigned = assigned_cps()

    if not args.check:
        VENDOR_DIR.mkdir(parents=True, exist_ok=True)
        LICENSES.mkdir(parents=True, exist_ok=True)
        print("=== 裁剪 ===")
        for key in FUSION_KEYS:
            build_subset(key, assigned[key])
        if FULL_LICENSES.exists():
            for name, dst in (
                ("ark-pixel/OFL.txt", "ark-pixel-OFL.txt"),
                ("cubic-11/OFL.txt", "cubic-11-OFL.txt"),
                ("galmuri/LICENSE.txt", "galmuri-LICENSE.txt"),
            ):
                shutil.copyfile(FULL_LICENSES / name, LICENSES / dst)
            print("  许可证: Ark Pixel / Cubic 11 / Galmuri 三份 (随附 Fusion 的上游许可)")
        # Fusion 自己的 OFL (整包许可)
        fus_ofl = rm.FUS / "OFL.txt"
        if fus_ofl.exists():
            shutil.copyfile(fus_ofl, LICENSES / "fusion-pixel-OFL.txt")
            print("  许可证: fusion-pixel-OFL.txt")

    print()
    bad = verify()
    print()
    if bad:
        print(f"[FAIL] {bad} 项未过")
        return 1
    print("[OK  ] 全部生产源裁剪版验证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
