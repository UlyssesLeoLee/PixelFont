"""Multi 12 字形路由规则 —— `PixelFont Multi 12` 每个码位走哪个源。

**全开源路线**（2026-10-24 用户拍板）：成品只用宽松许可的源，
这样 TTF 可以入库存放、用户可自由分发。对照之下，当前家族 `PixelFont PC98 12`
有 3,053/4,161 个码位派生自 SimHei / MS Gothic（微软专有），所以 `dist/` 不入库。

路由规则**完全机械推导**，不靠记忆、不靠人工挑字：

  1. 4 个缺口码位 `U+20AC €` `U+2260 ≠` `U+2264 ≤` `U+2265 ≥`
     → `zpix`。任何 12px 开源字体都不覆盖这四个 (Ark / Fusion 的 cmap 里都没有),
     Zpix (MIT) 覆盖, 字形 8×9 / 8×8 / 4×9 / 4×9 px 塞得进 12×13 格,
     且它的基线 (ascent 10 / descent 2) 与 Fusion 完全一致。
  2. 谚文音节 `U+AC00`–`U+D7AF` → `fusion_ko`。
  3. 汉字 `U+4E00`–`U+9FFF`:
     - 中日共享的 2,078 字 (GB2312 一级 ∩ JIS X 0208 一级汉字) → `fusion_zh_hans`
       —— 已拍板决策 ③「中文形为主」;
     - 其余 → `fusion_ja` (JIS 独有 2,297 + 二级汉字 1,689 + GB 独有 1,677 + CJK 其余 11,576)。
  4. CJK 标点 / 假名 / 全角 (`U+3000`–`U+30FF`、`U+FF00`–`U+FFEF`) → `fusion_ja`。
  5. 通用标点 `U+2000`–`U+206F` → `fusion_ja`。
     为什么不用 latin: Fusion 的 latin 把 `‘ ’ “ ” …` 排成**半角 6px**,
     ja / zh_hans 排成**全角 12px** —— 字形相同、宽度不同。
     CJK 惯例是全角, 且与当前家族 (MS Gothic 排成 12px 全角) 一致。
  6. 其余 (ASCII / Latin-1 / Latin Ext / Greek / Cyrillic / 箭头 / 数学符号) → `fusion_latin`。

**为什么规则本身就是产物**: 这张表 100% 由上面 6 条推导, 没有任何人工判断成分,
所以存一份 31,392 条的名单文件只是冗余 —— 真正的产物是**规则**,
名单随时可以重算。`derive_route_multi12.py` 负责把它算出来、逐条渲染验证、
并导出一份可 diff 的 JSON 快照。

源的许可与出处见 `docs/reference-fonts.md`。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "fontgen"))

REF = Path(
    os.environ.get("PIXELFONT_REF_FONTS", str(ROOT / "third_party" / "ref_fonts"))
)
FUS = REF / "fusion-pixel-12px"

#: 源键 -> (路径, 许可, 一句话说明)
SOURCES: dict[str, tuple[Path, str, str]] = {
    "fusion_latin": (
        FUS / "fusion-pixel-12px-monospaced-latin.ttf",
        "OFL-1.1",
        "Latin / Latin Ext / Greek / Cyrillic / 通用西文标点",
    ),
    "fusion_ko": (
        FUS / "fusion-pixel-12px-monospaced-ko.ttf",
        "OFL-1.1",
        "谚文音节 (Hangul syllables)",
    ),
    "fusion_ja": (
        FUS / "fusion-pixel-12px-monospaced-ja.ttf",
        "OFL-1.1",
        "日文形汉字 (JIS 独有 + 二级) / 假名 / CJK 标点 / 全角",
    ),
    "fusion_zh_hans": (
        FUS / "fusion-pixel-12px-monospaced-zh_hans.ttf",
        "OFL-1.1",
        "中日共享的 2,078 汉字 —— 中文形为主 (已拍板决策 ③)",
    ),
    "zpix": (
        REF / "zpix.bin",
        "MIT",
        "4 个缺口码位 (€ ≠ ≤ ≥); 13px advance, 裁到 12px 网格",
    ),
}

#: 任何 12px 开源字体都不覆盖的码位 -> 必须走非 Fusion 源
GAPS = {0x20AC, 0x2260, 0x2264, 0x2265}

#: 已拍板决策 ③: 中日共享汉字取**中文形**
SHARED_CJK = "fusion_zh_hans"


def _ranges() -> list[tuple[int, int]]:
    return [
        (0xAC00, 0xD7AF),   # 谚文音节
        (0x4E00, 0x9FFF),   # 汉字
        (0x3000, 0x30FF),   # CJK 标点 + 假名
        (0xFF00, 0xFFEF),   # 全角形式
        (0x2000, 0x206F),   # 通用标点
    ]


def _cjk_shared() -> set[int]:
    """中日共享的 2,078 汉字: GB2312 一级 ∩ JIS X 0208 **一级**汉字。"""
    import charset_multi12 as m12

    gb = {ord(c) for c in m12.charset.gb2312_level1()}
    return gb & m12.jis_x0208_kanji()


def build_route() -> dict[int, str]:
    """返回 {码位: 源键}，覆盖 Multi 12 全部 31,392 个码位。

    判据顺序即规则优先级 —— 缺口 > 谚文 > 汉字 > CJK 标点/假名/全角 > 通用标点 > 其余。
    """
    import charset_multi12 as m12

    shared = _cjk_shared()
    out: dict[int, str] = {}
    for ch, _tag in m12.build_charset_multi12():
        cp = ord(ch)
        if cp in GAPS:
            out[cp] = "zpix"
        elif 0xAC00 <= cp <= 0xD7AF:
            out[cp] = "fusion_ko"
        elif 0x4E00 <= cp <= 0x9FFF:
            out[cp] = SHARED_CJK if cp in shared else "fusion_ja"
        elif 0x3000 <= cp <= 0x30FF or 0xFF00 <= cp <= 0xFFEF:
            out[cp] = "fusion_ja"
        elif 0x2000 <= cp <= 0x206F:
            out[cp] = "fusion_ja"
        else:
            out[cp] = "fusion_latin"
    return out


def layer_of() -> dict[int, str]:
    """{码位: 所属层名}（L0–L7），用于报告与分账。"""
    import charset_multi12 as m12

    out: dict[int, str] = {}
    for name, delta, _tag in m12.layers():
        for cp in delta:
            out[cp] = name
    return out


def source_path(key: str) -> Path:
    return SOURCES[key][0]


def source_license(key: str) -> str:
    return SOURCES[key][1]


def require_sources() -> None:
    missing = [str(p) for p, _l, _d in SOURCES.values() if not p.exists()]
    if missing:
        raise SystemExit(
            "缺少参考字体，无法确定 Multi 12 的字形来源：\n"
            + "\n".join("  " + m for m in missing)
            + "\n先运行：python tools/fontgen/fetch_ref_fonts.py"
        )
