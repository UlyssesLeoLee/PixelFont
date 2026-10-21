"""下载参考像素字体 (开源免费), 供字形身份校验使用。

为什么参考字体二进制不入库:
    third_party/ 在 .gitignore 里。仓库只提交"来源 + 版本 + 许可证 + sha256"清单
    (docs/reference-fonts.md), 任何人按清单都能取到同一份字节。

为什么是这四套 —— 设计谱系互相独立, 才叫"独立基准":
    · Ark Pixel   : 日系点阵, 12px, 笔画方正规整          (OFL-1.1)
    · Fusion Pixel: 缝合字体, 把 Ark/Cubic11/Galmuri 等多套点阵缝在一起, 12px (OFL-1.1)
    · Zpix 最像素 : 国产点阵, 12px, 笔画带手绘味          (MIT)
    · GNU Unifont : 16x16, 学术项目, BMP 全覆盖, 与 CJK 点阵毫无血缘 (GPL-2.0+ 字体嵌入例外)

    Fusion 是缝合产物, 不算完全独立 —— 但它缝进去的底料多数不在这一档,
    且实测它与 Ark 的判定结论高度一致 (见 docs/glyph-identity-verification.md)。

用法:
    python tools/fontgen/fetch_ref_fonts.py            # 下载并校验 sha256
    python tools/fontgen/fetch_ref_fonts.py --verify   # 只校验本地已有的文件
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "third_party" / "ref_fonts"

# (归档名, 下载 URL, sha256, 解压后的子目录 or None)
ARCHIVES = [
    (
        "ark-pixel-12px.zip",
        "https://github.com/TakWolf/ark-pixel-font/releases/download/2026.10.16/"
        "ark-pixel-font-12px-monospaced-ttf-v2026.10.16.zip",
        "ae1512de69702ebfd3def3de65b73037f112431452766dc4fc8fbc404838554d",
        "ark-pixel-12px",
    ),
    (
        "fusion-pixel-12px.zip",
        "https://github.com/TakWolf/fusion-pixel-font/releases/download/2026.10.16/"
        "fusion-pixel-font-12px-monospaced-ttf-v2026.10.16.zip",
        "c4c9e466042d76f4b37c78232b6ecd4e1f25be3a27cd0f3aacdfaf7de5bd515b",
        "fusion-pixel-12px",
    ),
]

# (落地文件名, 下载 URL, sha256)
SINGLES = [
    (
        "zpix.bin",
        "https://github.com/SolidZORO/zpix-pixel-font/releases/download/v3.3.0/zpix.ttf",
        "a67917d94bb597acbdf3bfe1cf97047cc3e1cdd3839d21da188e35cc0737e828",
    ),
    (
        "unifont-16.bin",
        "https://unifoundry.com/pub/unifont/unifont-16.0.01/font-builds/unifont-16.0.01.otf",
        "ea39a0e614e7486490239c5759e1a0cd86fd49e335c4b08d2fd13e313147f022",
    ),
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, dest: Path) -> None:
    print(f"  下载 {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "PixelFont-ref-font-fetcher"})
    with urllib.request.urlopen(req, timeout=180) as r, dest.open("wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def main() -> int:
    ap = argparse.ArgumentParser(description="下载/校验字形校验用的开源参考字体")
    ap.add_argument("--verify", action="store_true", help="只校验本地已有文件, 不下载")
    args = ap.parse_args()

    DEST.mkdir(parents=True, exist_ok=True)
    bad = 0

    for name, url, want, subdir in ARCHIVES:
        # 本地存盘时有人会把归档改名为 .bin (避免某些环境的扩展名过滤), 两种都认
        arc = DEST / name
        if not arc.exists():
            alt = DEST / (Path(name).stem + ".bin")
            if alt.exists():
                arc = alt
        if not arc.exists():
            if args.verify:
                print(f"✘ 缺失 {name}")
                bad += 1
                continue
            fetch(url, arc)
        got = sha256(arc)
        if got != want:
            print(f"✘ sha256 不符 {arc.name}: 期望 {want}, 实得 {got}")
            bad += 1
            continue
        print(f"✔ {arc.name} sha256 一致")
        target = DEST / subdir
        if not target.exists():
            with zipfile.ZipFile(arc) as z:
                z.extractall(DEST)
            print(f"  已解压 -> {subdir}/")

    for name, url, want in SINGLES:
        p = DEST / name
        if not p.exists():
            if args.verify:
                print(f"✘ 缺失 {name}")
                bad += 1
                continue
            fetch(url, p)
        got = sha256(p)
        if got != want:
            print(f"✘ sha256 不符 {name}: 期望 {want}, 实得 {got}")
            bad += 1
            continue
        print(f"✔ {name} sha256 一致")

    # 解压出来的 TTF 也要逐个核对
    for sub, expect in (
        ("ark-pixel-12px/ark-pixel-12px-monospaced-zh_hans.ttf", "56e82b4fa83e9e7bc586da288a7eb0481f8bc1f1fa8ecc6ad952781c8c0e366a"),
        ("fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans.ttf", "4ae459a3bdff66bcf430f1b1cd4641a0b4433732a70c57d6a975ab058b0a88e7"),
    ):
        p = DEST / sub
        if not p.exists():
            print(f"✘ 缺失 {sub}")
            bad += 1
            continue
        got = sha256(p)
        if got != expect:
            print(f"✘ sha256 不符 {sub}")
            bad += 1
        else:
            print(f"✔ {sub} sha256 一致")

    if bad:
        print(f"\n{bad} 项校验失败", file=sys.stderr)
        return 1
    print("\n参考字体齐备, sha256 全部一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
