"""打包 `PixelFont Multi 12` 的发布件 —— **可复现**（同样的输入产出同样的字节）。

用法:
    python tools/fontgen/package_multi12.py --version v1.1.0 --date 2026-10-25

产出 (全部在 `dist/`):
    OFL.txt                                  许可证全文 + 全部版权声明
    PixelFontMulti-12-<version>.zip          发布包
    PixelFontMulti-12-SHA256SUMS.txt         Release 附件用的校验和清单

zip 内 7 项: ttf / bdf / 图集 / 样张 / 安装与使用说明.md / OFL.txt / SHA256SUMS.txt。

**为什么要有这个脚本** (2026-10-25): 前两次发布 (v1.0.0 / v1.0.1) 的打包是
临时脚本做的, 没入库 —— 意味着「发布包长什么样」这件事**无法复现**, 也没法
在干净克隆上核对。发布流程的每一步都该是可重跑的。

**为什么 zip 的时间戳是固定的**: 条目时间戳跟着发布日中午走, 于是同样的产物
在不同日子打出来的 zip 字节不同 —— 核对 sha256 时会误判「资产变了」。
固定时间戳让「资产是否变化」只取决于内容。

**许可证为什么改过**: v1.0.0 / v1.0.1 的包 `OFL.txt` 只有**手绘字形**的版权声明,
漏了 Fusion Pixel 12px 的 —— 成品 TTF 的字形大量派生自 Fusion, OFL-1.1 要求
随字体分发附上版权声明。接入 ZLabs 之后这个缺口更明显 (三个上游), 所以 v1.1.0
起 `OFL.txt` 列出**全部**版权声明与保留字体名, 再附一份 OFL-1.1 全文
(三个上游是同一个许可版本, 全文只需一份)。
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
VENDOR_LICENSES = ROOT / "vendor" / "multi12" / "LICENSES"

PS_NAME = "PixelFontMulti-12"

#: zip 内条目的固定时间戳 = 发布日的**本地正午**。
#:
#: 为什么是正午而不是午夜: 午夜在负时区会折到前一天, 条目日期会跟发布日对不上。
NOON = (12, 0, 0)

#: 随包的 4 个成品 (zip 内) + 说明
ZIP_ITEMS = (
    ("ttf", f"{PS_NAME}.ttf"),
    ("bdf", f"{PS_NAME}.bdf"),
    ("atlas", f"{PS_NAME}-atlas.png"),
    ("specimen", f"{PS_NAME}-specimen.png"),
)

#: zip 内的用户说明 —— 仓库里的展开版
INSTALL_DOC = "安装与使用说明.md"
INSTALL_DOC_SRC = ROOT / "docs" / "install-multi12.md"

#: Release 附件 (zip 本身 + 4 个单独件)
ATTACH_ITEMS = (
    ("zip", None),          # 发布包本体, 名字在打包时确定
    ("ttf", f"{PS_NAME}.ttf"),
    ("atlas", f"{PS_NAME}-atlas.png"),
    ("specimen", f"{PS_NAME}-specimen.png"),
    ("ofl", "OFL.txt"),
)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ofl_body() -> str:
    """取 OFL-1.1 全文 (从「SIL OPEN FONT LICENSE Version 1.1」那行开始)。"""
    text = (VENDOR_LICENSES / "fusion-pixel-OFL.txt").read_text(encoding="utf-8")
    marker = "SIL OPEN FONT LICENSE Version 1.1"
    i = text.index(marker)
    # 回退到它上面那行分隔线, 让全文从分隔线开始
    start = text.rindex("---", 0, i)
    return text[start:].rstrip() + "\n"


def build_ofl() -> str:
    """生成 `OFL.txt`: 全部版权声明 + OFL-1.1 全文。"""
    head = """PixelFont Multi 12
==================

This font is a derivative work assembled from several SIL Open Font License
Version 1.1 fonts, plus original artwork created for the PixelFont project.

Every copyright notice and Reserved Font Name that applies to this derivative
work is listed below. This derivative work does NOT use any Reserved Font Name.

  1. PixelFont Multi 12 hand-drawn glyphs (U+20AC, U+2260, U+2264, U+2265)
     Original artwork created for the PixelFont project.
     Copyright (c) 2026 UlyssesLeoLee

  2. Fusion Pixel 12px -- glyph source for the Latin, Korean, Japanese and
     Chinese forms used by this font.
     https://github.com/TakWolf/fusion-pixel-font
     Copyright (c) 2022, TakWolf (https://takwolf.com).
     Fusion Pixel itself bundles Ark Pixel, Cubic 11 and Galmuri; their notices
     are kept verbatim in the source repository under
     vendor/multi12/LICENSES/.

  3. ZLabs Pixel 12px -- glyph source for the Simplified Chinese forms that
     Fusion Pixel does not cover (GB2312 level-2 rare characters etc.).
     Copyright (c) 2023-2025, Astro_2539 (https://github.com/Astro-2539),
     with Reserved Font Name "Z工坊/ZLabs".

"""
    return head + _ofl_body()


def _zip_info(name: str, date: tuple[int, int, int]) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(date[0], date[1], date[2]) + NOON)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3          # Unix —— 固定住, 免得跨平台打包字节不同
    info.external_attr = 0o644 << 16
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="打包 PixelFont Multi 12 发布件")
    ap.add_argument("--version", required=True, help="发布版本, 例如 v1.1.0")
    ap.add_argument("--date", required=True, help="发布日 YYYY-MM-DD")
    args = ap.parse_args()

    y, m, d = (int(x) for x in args.date.split("-"))
    date = (y, m, d)

    DIST.mkdir(parents=True, exist_ok=True)

    # ---- 1. 许可证 ----
    ofl_path = DIST / "OFL.txt"
    ofl_path.write_text(build_ofl(), encoding="utf-8")

    # ---- 2. 暂存目录: zip 里的每一项 ----
    stage = DIST / "_stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for key, name in ZIP_ITEMS:
        src = DIST / name
        if not src.exists():
            raise SystemExit(f"缺少构建产物: {src}\n先跑: python tools/fontgen/build_font_multi12.py")
        shutil.copyfile(src, stage / name)
    shutil.copyfile(INSTALL_DOC_SRC, stage / INSTALL_DOC)
    shutil.copyfile(ofl_path, stage / "OFL.txt")

    # ---- 3. zip 内的 SHA256SUMS (不含 zip 本身 —— 它还没生成) ----
    inner_names = [name for _k, name in ZIP_ITEMS] + [INSTALL_DOC, "OFL.txt"]
    lines = []
    for name in inner_names:
        lines.append(f"{sha256(stage / name)}  {name}")
    (stage / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- 4. 打包 ----
    zip_name = f"{PS_NAME}-{args.version}.zip"
    zip_path = DIST / zip_name
    entries = inner_names + ["SHA256SUMS.txt"]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in entries:
            z.writestr(_zip_info(name, date), (stage / name).read_bytes())

    # ---- 5. Release 附件用的 SHA256SUMS (含 zip 本身) ----
    outer = []
    for key, name in ATTACH_ITEMS:
        if key == "zip":
            outer.append(f"{sha256(zip_path)}  {zip_name}")
        elif key == "ofl":
            outer.append(f"{sha256(DIST / 'OFL.txt')}  OFL.txt")
        else:
            outer.append(f"{sha256(DIST / name)}  {name}")
    sums_path = DIST / f"{PS_NAME}-SHA256SUMS.txt"
    sums_path.write_text("\n".join(outer) + "\n", encoding="utf-8")

    shutil.rmtree(stage, ignore_errors=True)

    # ---- 6. 报告 ----
    print("=== 发布件 ===")
    print(f"  {zip_name}")
    print(f"    {zip_path.stat().st_size} 字节  sha256={sha256(zip_path)}")
    print("    zip 内:")
    with zipfile.ZipFile(zip_path) as z:
        for i in z.infolist():
            print(f"      {i.filename:<28} {i.file_size:>9}  {i.date_time}")
    print()
    print(f"  OFL.txt  {ofl_path.stat().st_size} 字节  sha256={sha256(ofl_path)}")
    print(f"  {sums_path.name}  {sums_path.stat().st_size} 字节  sha256={sha256(sums_path)}")
    print()
    print("=== Release 附件 (6 个) ===")
    for key, name in ATTACH_ITEMS:
        n = zip_name if key == "zip" else ("OFL.txt" if key == "ofl" else name)
        p = DIST / n
        print(f"  {n:<40} {p.stat().st_size:>9}  {sha256(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
