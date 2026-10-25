"""Multi 12 字形路由规则 —— `PixelFont Multi 12` 每个码位走哪个源。

**全开源路线**（2026-10-24 用户拍板）：成品只用宽松许可的源，
这样 TTF 可以入库存放、用户可自由分发。对照之下，当前家族 `PixelFont PC98 12`
有 3,053/4,161 个码位派生自 SimHei / MS Gothic（微软专有），所以 `dist/` 不入库。

路由规则**完全机械推导**，不靠记忆、不靠人工挑字：

  1. 4 个缺口码位 `U+20AC €` `U+2260 ≠` `U+2264 ≤` `U+2265 ≥`
     → `handdrawn`（本仓库**原创手绘**）。任何 12px 开源点阵字体都不覆盖这四个
     (Ark / Fusion 七个变体的 cmap 里都没有)；Zpix 虽覆盖，但上游许可**禁止
     修改/拆分/再分发** 且商用需付费，不能当生产源。详见 `handdrawn.py`。
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

#: **构建输入**目录 —— 生产源裁剪版, 入库。构建只读这里。
VENDOR_MULTI12 = ROOT / "vendor" / "multi12"

#: 源键 -> (构建输入路径, 许可, 一句话说明)
#:
#: 构建输入**全部在入库路径上** (`vendor/multi12/`), 干净克隆即可复现构建 ——
#: `third_party/ref_fonts/` 只是**校验用的原始下载**, 不参与构建。
#: 两者用 `ORIGINS` 区分, 不要混用。
SOURCES: dict[str, tuple[Path, str, str]] = {
    "fusion_latin": (
        VENDOR_MULTI12 / "fusion-pixel-12px-monospaced-latin-subset.ttf",
        "OFL-1.1",
        "Latin / Latin Ext / Greek / Cyrillic / 通用西文标点",
    ),
    "fusion_ko": (
        VENDOR_MULTI12 / "fusion-pixel-12px-monospaced-ko-subset.ttf",
        "OFL-1.1",
        "谚文音节 (Hangul syllables)",
    ),
    "fusion_ja": (
        VENDOR_MULTI12 / "fusion-pixel-12px-monospaced-ja-subset.ttf",
        "OFL-1.1",
        "日文形汉字 (JIS 独有 + 二级) / 假名 / CJK 标点 / 全角",
    ),
    "fusion_zh_hans": (
        VENDOR_MULTI12 / "fusion-pixel-12px-monospaced-zh_hans-subset.ttf",
        "OFL-1.1",
        "中日共享的 2,078 汉字 —— 中文形为主 (已拍板决策 ③)",
    ),
    "handdrawn": (
        VENDOR_MULTI12 / "handdrawn-glyphs.txt",
        "OFL-1.1",
        "4 个缺口码位 (€ ≠ ≤ ≥) —— 本仓库原创手绘",
    ),
}

#: 源键 -> **原始下载**路径 (`third_party/`, 不入库, 只用于校验与重新裁剪)
ORIGINS: dict[str, Path] = {
    "fusion_latin": FUS / "fusion-pixel-12px-monospaced-latin.ttf",
    "fusion_ko": FUS / "fusion-pixel-12px-monospaced-ko.ttf",
    "fusion_ja": FUS / "fusion-pixel-12px-monospaced-ja.ttf",
    "fusion_zh_hans": FUS / "fusion-pixel-12px-monospaced-zh_hans.ttf",
}

#: 任何 12px 开源字体都不覆盖的码位 -> 必须走手绘源
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
            out[cp] = "handdrawn"
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
    """**构建输入**路径 (入库的裁剪版)。构建只读这个。"""
    return SOURCES[key][0]


def origin_path(key: str) -> Path:
    """**原始下载**路径 (`third_party/`, 不入库)。只用于校验与重新裁剪。"""
    return ORIGINS[key]


def source_license(key: str) -> str:
    return SOURCES[key][1]


def require_sources() -> None:
    """门禁: **构建输入**必须齐全。这是最小可复现集合 —— 全在入库路径上。"""
    missing = [str(p) for p, _l, _d in SOURCES.values() if not p.exists()]
    if missing:
        raise SystemExit(
            "缺少 Multi 12 的生产源 (构建输入, 应已入库):\n"
            + "\n".join("  " + m for m in missing)
            + "\n重新生成: python tools/fontgen/vendor_multi12_sources.py"
        )


def require_origins() -> None:
    """门禁: **原始下载**必须齐全。只在重新裁剪 / 做逐像素对照时需要。"""
    missing = [str(p) for p in ORIGINS.values() if not p.exists()]
    if missing:
        raise SystemExit(
            "缺少参考字体的原始下载 (只用于校验与重新裁剪):\n"
            + "\n".join("  " + m for m in missing)
            + "\n先运行: python tools/fontgen/fetch_ref_fonts.py"
        )


# ---------------------------------------------------------------------------
# 快照: 构建的权威名单
# ---------------------------------------------------------------------------
#
# 为什么构建要读快照, 而不是每次重新推导:
#
#   字符集定义 = 「编码块 ∩ Fusion 各变体的全字集 cmap」。那个 cmap **只存在于
#   `third_party/` 的原始下载里** (入库的裁剪版只含路由分配给它的码位, 拿它
#   反推字符集会形成循环定义)。
#
#   于是分工变成:
#     · **推导** (`derive_route_multi12.py`) —— 需要 `third_party/`, 一次性的,
#       产出可 diff 的快照;
#     · **构建** (`build_font_multi12.py`) —— 只读**入库的**快照与**入库的**裁剪版,
#       不碰 `third_party/`, 干净克隆即可复现。
#
#   这正是「路由规则本身就是产物」的延续: 规则在代码里, 名单在快照里,
#   两者都入库。

#: 入库的路由快照
SNAPSHOT = ROOT / "tools" / "fontgen" / "route_multi12.json"

#: Multi 12 的字符集总量 (与 `charset_multi12.TARGET_TOTAL` 一致)
TARGET_TOTAL = 31_392


def load_snapshot() -> dict:
    """读**入库的**路由快照。构建的权威名单。"""
    if not SNAPSHOT.exists():
        raise SystemExit(
            f"缺少路由快照: {SNAPSHOT}\n"
            "它是构建的权威名单 (字符集 + 路由), 必须入库。\n"
            "重新生成需要 third_party 原始下载: python tools/fontgen/fetch_ref_fonts.py\n"
            "然后: python tools/fontgen/derive_route_multi12.py --write"
        )
    import json

    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _snap_cps(d: dict, key: str) -> dict[int, str]:
    return {int(k[2:], 16): v for k, v in d[key].items()}


def snapshot_route() -> dict[int, str]:
    """快照里的路由表: {码位: 源键}。"""
    return _snap_cps(load_snapshot(), "route")


def snapshot_charset() -> list[tuple[str, str]]:
    """从快照还原 [(字符, 分类)] —— **不依赖 third_party**。"""
    d = load_snapshot()
    route = _snap_cps(d, "route")
    layer = _snap_cps(d, "layer")
    tags = d.get("layer_tags") or {}
    out: list[tuple[str, str]] = []
    for cp in sorted(route):
        out.append((chr(cp), tags.get(layer.get(cp, ""), "unknown")))
    return out


def verify_snapshot() -> dict[str, int]:
    """快照自洽门禁 —— **全部不依赖 third_party**。

    抓住「快照被改坏 / 与代码脱节」的常见情形:
      1. 总量与层数对不上;
      2. 路由指向未登记的源键;
      3. 某个码位在**它被指派的源**里其实不存在 (源缺字 / 路由指错);
      4. 层归属与编码判定自相矛盾 (例如 L6 里混进了非 JIS 一级汉字的码位);
      5. 各层互相重叠 (层必须是增量)。
    """
    from fontTools.ttLib import TTFont

    d = load_snapshot()
    route = _snap_cps(d, "route")
    layer = _snap_cps(d, "layer")
    tags = d.get("layer_tags") or {}

    problems: list[str] = []

    # 1. 总量
    if len(route) != TARGET_TOTAL:
        problems.append(f"路由表 {len(route)} 条 != 目标 {TARGET_TOTAL}")
    if d.get("stats", {}).get("total") != len(route):
        problems.append("stats.total 与路由表条数不符")

    # 2. 源键
    unknown = sorted(set(route.values()) - set(SOURCES))
    if unknown:
        problems.append(f"路由指向未登记的源: {unknown}")

    # 2b. 分类标签必须齐全 (快照里的 layer_tags 是分类的唯一来源)
    missing_tag = sorted({
        layer.get(cp, "?") for cp in route
        if layer.get(cp, "?") not in tags
    })
    if missing_tag:
        problems.append(f"这些层没有登记分类标签 (layer_tags 缺项): {missing_tag}")

    # 3. 每个码位在它被指派的源里确实存在
    cmaps: dict[str, set[int]] = {}
    for key in sorted(set(route.values())):
        if key == "handdrawn":
            continue
        p = SOURCES[key][0]
        if not p.exists():
            problems.append(f"缺少入库生产源: {p}")
            continue
        f = TTFont(str(p), fontNumber=0, lazy=True)
        cmaps[key] = set(f.getBestCmap())
        f.close()
    for cp, key in sorted(route.items()):
        if key == "handdrawn":
            continue
        if key in cmaps and cp not in cmaps[key]:
            problems.append(f"U+{cp:04X} 路由到 {key}, 但该源没有这个字形")
            if len(problems) > 20:
                break

    # 4. 层归属自洽 (编码判定, 不依赖任何字体文件)
    import charset_multi12 as m12

    blocks = {
        "L1 Latin Ext A/B": lambda c: 0x0100 <= c <= 0x024F,
        "L2 Greek": lambda c: 0x0370 <= c <= 0x03FF,
        "L3 Cyrillic": lambda c: 0x0400 <= c <= 0x04FF,
        "L4 Hangul syllables": lambda c: 0xAC00 <= c <= 0xD7AF,
        "L6 JIS X 0208 一级汉字": m12.jis_x0208_kanji().__contains__,
        "L7 CJK 其余": lambda c: 0x4E00 <= c <= 0x9FFF,
    }
    l5_ok = m12.jis_x0208_level2_kanji() | m12.jis_x0208_kana_punct()
    cur = m12.current_family()
    for cp, lname in sorted(layer.items()):
        if lname == "L5 JIS X 0208 二级汉字 + 符号/假名":
            if cp not in l5_ok:
                problems.append(f"U+{cp:04X} 在 L5, 但不属于 JIS 二级汉字/符号假名")
        elif lname == "L0 当前家族":
            if cp not in cur:
                problems.append(f"U+{cp:04X} 在 L0, 但不属于当前家族字符集")
        elif lname in blocks:
            if not blocks[lname](cp):
                problems.append(f"U+{cp:04X} 在 {lname}, 但不在该层的编码块内")
        else:
            problems.append(f"U+{cp:04X} 的层名 {lname!r} 未登记")
        if len(problems) > 20:
            break

    # 5. 层必须互斥 (增量语义)
    seen: dict[int, str] = {}
    for cp, lname in layer.items():
        if cp in seen and seen[cp] != lname:
            problems.append(f"U+{cp:04X} 同时属于 {seen[cp]} 和 {lname}")

    if problems:
        head = problems[:20]
        raise SystemExit(
            "路由快照自洽门禁未过:\n"
            + "\n".join("  " + p for p in head)
            + (f"\n  ... 共 {len(problems)} 条" if len(problems) > len(head) else "")
        )

    return {
        "total": len(route),
        "sources": len(set(route.values())),
        "layers": len(set(layer.values())),
        "tags": len(tags),
    }
