"""Multi 12 字符集定义 —— `PixelFont Multi 12`（方案 C，31,392 码位）。

本模块是 `docs/spec/02-charset-definition.md` §2.7 的**可执行版本**：分层账目、
每一层的增量、交叉核对口径，全部在这里写成代码，而不是只写在文档里。

设计原则与 `charset.py` 保持一致：

* **机械推导优先** —— 汉字集用 GB2312 区位码区间与 Shift-JIS 双字节判定算出，
  不凭记忆列字表；字表靠记忆列就是编造。
* **每一层都是「实际字体 cmap 的交集」** —— 不是理论块大小。理论块与实际
  覆盖的差额要显式留在账目里，不能悄悄抹平。
* **总量必须能被独立口径复核** —— 逐层累加与「方案 A ∪ CJK 整块」两条路径
  必须给出同一个数，否则其中一条是错的。

依赖：参考字体（`third_party/ref_fonts/`，不入库）。抓取方式::

    python tools/fontgen/fetch_ref_fonts.py          # 下载
    python tools/fontgen/fetch_ref_fonts.py --verify  # 只校验 sha256

参考字体只用于**确定覆盖边界**（哪些码位该收），不参与字形渲染 ——
字形来源见 `charset.py` 与 `ideo_route.json`。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "fontgen"))

import charset  # noqa: E402

#: 参考字体目录。默认在仓库内（不入库，需 `fetch_ref_fonts.py` 抓取）；
#: 在 worktree 里跑时可用环境变量指向任一已抓好的副本：:
#:
#:     $env:PIXELFONT_REF_FONTS = 'E:\PixelFont\third_party\ref_fonts'
REF = Path(
    os.environ.get("PIXELFONT_REF_FONTS", str(ROOT / "third_party" / "ref_fonts"))
)
FUS = REF / "fusion-pixel-12px"

#: 方案 C 的目标码位数。任何改动导致对不上，`gate_multi12()` 直接失败。
TARGET_TOTAL = 31_392

#: 方案 A（不追加全部 CJK）的码位数，作为交叉核对口径之一。
TARGET_A = 19_816

#: 方案 C 里**不被任何 Fusion 变体覆盖**的码位 —— 它们必须走
#: MS Gothic / SimHei 路径（与 `docs/reference-fonts.md` 记载一致）。
NON_THIRD_SOURCE = {0x20AC, 0x2260, 0x2264, 0x2265}  # € ≠ ≤ ≥

#: **层名 -> 分类标签**。层名与标签的唯一定义处。
#:
#: 为什么放在代码里而不是只放在快照里: 快照是**派生物**, 规则才是产物。
#: 若层名只在快照里, 快照与代码就无从互相印证 —— 快照被改成什么, 它自己都自洽。
#: 放在代码里, 快照的层名就有了**外部基准**可对。
LAYER_TAGS: dict[str, str] = {
    "L0 当前家族": "current",
    "L1 Latin Ext A/B": "latin-ext",
    "L2 Greek": "greek",
    "L3 Cyrillic": "cyrillic",
    "L4 Hangul syllables": "hangul",
    "L5 JIS X 0208 二级汉字 + 符号/假名": "jis-l2",
    "L6 JIS X 0208 一级汉字": "jis-kanji",
    "L7 CJK 其余": "cjk-ext",
}


def layer_names() -> list[str]:
    """8 个层名 (顺序即累加顺序) —— **不需要参考字体**。"""
    return list(LAYER_TAGS)


class ReferenceFontsMissing(RuntimeError):
    """参考字体不在位 —— 无法确定覆盖边界。"""


def _require_fonts() -> None:
    need = [
        FUS / "fusion-pixel-12px-monospaced-ja.ttf",
        FUS / "fusion-pixel-12px-monospaced-ko.ttf",
        FUS / "fusion-pixel-12px-monospaced-latin.ttf",
    ]
    missing = [p for p in need if not p.exists()]
    if missing:
        raise ReferenceFontsMissing(
            "缺少参考字体，无法确定 Multi 12 的覆盖边界：\n"
            + "\n".join(f"  {p}" for p in missing)
            + "\n先运行：python tools/fontgen/fetch_ref_fonts.py"
        )


def _cmap(path: Path) -> set[int]:
    from fontTools.ttLib import TTFont

    return set(TTFont(str(path), fontNumber=0, lazy=True).getBestCmap().keys())


def _rng(a: int, b: int) -> set[int]:
    return set(range(a, b + 1))


def jis_x0208_kanji() -> set[int]:
    """JIS X 0208 第 1–2 区**一级**汉字：Shift-JIS 双字节且首字节 0x88–0x9F。

    与 `charset.gb2312_level1()` 同一套方法论 —— 靠编码判定，不靠人列。
    """
    out: set[int] = set()
    for cp in range(0x3000, 0xA000):
        try:
            b = chr(cp).encode("shift_jis")
        except UnicodeEncodeError:
            continue
        if len(b) == 2 and (0x88 <= b[0] <= 0x9F):
            out.add(cp)
    return out


def jis_x0208_level2_kanji() -> set[int]:
    """JIS X 0208 **二级**汉字：Shift-JIS 双字节且首字节 0xE0–0xEF。

    为什么必须和一级汉字分开: 首字节 0xE0–0xEF 是 JIS X 0208 的**二级汉字行**
    (第 48–84 区), 落在 U+4E00–U+9FFF 里 —— 实测这 1,980 个码位**全是汉字**。
    早先把它当成「假名/符号/全角」, 于是 L5 那一层名义上写的是「假名/符号/全角」,
    实际内容却有 1,689 个汉字, 层名与内容对不上。

    判据: 一级 = 0x88–0x9F, 二级 = 0xE0–0xEF, 符号/假名/希腊/西里尔 = 0x81–0x87。
    """
    out: set[int] = set()
    for cp in range(0x3000, 0xA000):
        try:
            b = chr(cp).encode("shift_jis")
        except UnicodeEncodeError:
            continue
        if len(b) == 2 and (0xE0 <= b[0] <= 0xEF):
            out.add(cp)
    return out


def jis_x0208_kana_punct() -> set[int]:
    """JIS X 0208 第 1–8 区符号 / 假名 / 希腊 / 西里尔：首字节 0x81–0x87。

    注意: 这里**不含**二级汉字 (那是 0xE0–0xEF, 见 `jis_x0208_level2_kanji()`),
    也不含全角形式 (U+FF00–U+FFEF 在 0x3000–0xA000 扫描范围之外, 靠首字节
    0x81–0x87 判定时需要单独扫 0xFF00 以上的区间)。
    """
    out: set[int] = set()
    for cp in range(0x3000, 0xA000):
        try:
            b = chr(cp).encode("shift_jis")
        except UnicodeEncodeError:
            continue
        if len(b) == 2 and (0x81 <= b[0] <= 0x87):
            out.add(cp)
    return out


def current_family() -> set[int]:
    """L0：`PixelFont PC98 12` 当前的 4,161 码位。"""
    return {ord(c) for c, _ in charset.build_charset()}


def layer_block_sets() -> dict[str, set[int]]:
    """每层的**候选码位集合** —— 纯编码判定，**不需要参考字体**。

    这是快照自洽门禁（`route_multi12.verify_snapshot`）的**外部基准**：
    快照说某码位属于 L6，这里说 L6 只收 Shift-JIS 首字节 0x88–0x9F 的一级汉字，
    两者对不上就是有一方错了。

    集合是「候选」而非最终成员 —— 最终成员还要 ∩ 源的覆盖，那一步需要
    `third_party/`。所以这里只用来判**方向**：快照的层归属必须是候选集的子集。
    """
    return {
        "L0 当前家族": current_family(),
        "L1 Latin Ext A/B": set(range(0x0100, 0x0250)),
        "L2 Greek": set(range(0x0370, 0x0400)),
        "L3 Cyrillic": set(range(0x0400, 0x0500)),
        "L4 Hangul syllables": set(range(0xAC00, 0xD7B0)),
        "L5 JIS X 0208 二级汉字 + 符号/假名":
            jis_x0208_level2_kanji() | jis_x0208_kana_punct(),
        "L6 JIS X 0208 一级汉字": jis_x0208_kanji(),
        "L7 CJK 其余": set(range(0x4E00, 0xA000)),
    }


def layers() -> list[tuple[str, set[int], str]]:
    """返回 [(层名, 该层码位集合, 分类标签)]，顺序即累加顺序。

    每层的码位集合是**该层引入的增量**（已扣除与前面各层的重叠），
    这样逐层加总才等于总数。集合本身仍是"该层应该覆盖的全部码位"，
    分类标签用于 `build_charset_multi12()` 打标签。
    """
    _require_fonts()
    ja = _cmap(FUS / "fusion-pixel-12px-monospaced-ja.ttf")
    ko = _cmap(FUS / "fusion-pixel-12px-monospaced-ko.ttf")
    la = _cmap(FUS / "fusion-pixel-12px-monospaced-latin.ttf")

    raw = [
        ("L0 当前家族", current_family(), "current"),
        ("L1 Latin Ext A/B", _rng(0x0100, 0x024F) & la, "latin-ext"),
        ("L2 Greek", _rng(0x0370, 0x03FF) & la, "greek"),
        ("L3 Cyrillic", _rng(0x0400, 0x04FF) & la, "cyrillic"),
        ("L4 Hangul syllables", _rng(0xAC00, 0xD7AF) & ko, "hangul"),
        # L5 的内容是**二级汉字 + 少量符号**, 不是"假名/符号/全角" ——
        # 详见 `jis_x0208_level2_kanji()` 的注释与门禁 5。
        ("L5 JIS X 0208 二级汉字 + 符号/假名",
         (jis_x0208_level2_kanji() | jis_x0208_kana_punct()) & ja, "jis-l2"),
        ("L6 JIS X 0208 一级汉字", jis_x0208_kanji() & ja, "jis-kanji"),
        ("L7 CJK 其余", _rng(0x4E00, 0x9FFF) & ja, "cjk-ext"),
    ]

    # 层名与标签必须与 `LAYER_TAGS` **逐项相同** —— 它是快照自洽门禁的外部基准,
    # 两边对不上, 门禁就失去了判别力。
    got = [(n, t) for n, _d, t in raw]
    want = list(LAYER_TAGS.items())
    if got != want:
        raise SystemExit(
            "层定义与 LAYER_TAGS 不一致 —— 两者必须逐项相同:\n"
            f"  layers()  : {got}\n  LAYER_TAGS: {want}"
        )

    # 扣掉与前面各层的重叠，得到增量
    out: list[tuple[str, set[int], str]] = []
    seen: set[int] = set()
    for name, s, tag in raw:
        delta = s - seen
        seen |= s
        out.append((name, delta, tag))
    return out


def build_charset_multi12() -> list[tuple[str, str]]:
    """返回 [(字符, 分类)]，按码位升序。分类沿用 `charset.py` 的风格并扩展。"""
    out: list[tuple[str, str]] = []
    for name, delta, tag in layers():
        for cp in sorted(delta):
            out.append((chr(cp), tag))
    out.sort(key=lambda kv: ord(kv[0]))
    return out


def ledger() -> list[tuple[str, int, int]]:
    """返回 [(层名, 增量, 累计)]，与文档 §2.7 的表一一对应。"""
    rows: list[tuple[str, int, int]] = []
    total = 0
    for name, delta, _ in layers():
        total += len(delta)
        rows.append((name, len(delta), total))
    return rows


def gate_multi12() -> None:
    """四道硬门禁。任何一条不过就抛错 —— 总量对不上时不能放行。"""
    rows = ledger()
    total = rows[-1][2]

    # 门禁 1：逐层累加必须等于目标
    if total != TARGET_TOTAL:
        raise SystemExit(
            f"字符集总量 {total} != 目标 {TARGET_TOTAL}；分层账目与文档 §2.7 不一致"
        )

    # 门禁 2：交叉核对口径 A（方案 A = 方案 C 去掉 L7 的增量）必须等于 19,816
    a_total = rows[-2][2]
    if a_total != TARGET_A:
        raise SystemExit(f"方案 A 交叉核对 {a_total} != 目标 {TARGET_A}")

    # 门禁 3：独立口径「方案 A ∪ CJK 整块」必须给出同一个总数
    _require_fonts()
    ja = _cmap(FUS / "fusion-pixel-12px-monospaced-ja.ttf")
    ko = _cmap(FUS / "fusion-pixel-12px-monospaced-ko.ttf")
    la = _cmap(FUS / "fusion-pixel-12px-monospaced-latin.ttf")
    cur = current_family()
    opt_a = (
        cur
        | (_rng(0x0100, 0x024F) & la)
        | (_rng(0x0370, 0x03FF) & la)
        | (_rng(0x0400, 0x04FF) & la)
        | (_rng(0xAC00, 0xD7AF) & ko)
        | (jis_x0208_kana_punct() & ja)
        | (jis_x0208_kanji() & ja)
    )
    cjk_all = _rng(0x4E00, 0x9FFF) & ja
    if len(opt_a | cjk_all) != TARGET_TOTAL:
        raise SystemExit(
            f"交叉口径「方案 A ∪ CJK 整块」= {len(opt_a | cjk_all)} != {TARGET_TOTAL}"
        )

    # 门禁 4：4 个不被任何 Fusion 变体覆盖的码位必须在集合里，且确实没被覆盖
    all_fusion: set[int] = set()
    for name in ("ja", "ko", "latin", "zh_hans", "zh_hant", "zh_hk", "zh_tw"):
        p = FUS / f"fusion-pixel-12px-monospaced-{name}.ttf"
        if p.exists():
            all_fusion |= _cmap(p)
    got = build_charset_multi12()
    got_cps = {ord(c) for c, _ in got}
    missing = NON_THIRD_SOURCE - got_cps
    if missing:
        raise SystemExit(f"非第三源码位缺失: {sorted(hex(c) for c in missing)}")
    wrongly_covered = NON_THIRD_SOURCE & all_fusion
    if wrongly_covered:
        raise SystemExit(
            "非第三源码位被 Fusion 覆盖了，账目前提变了: "
            f"{sorted(hex(c) for c in wrongly_covered)}"
        )

    # 排除项仍然不收
    for cp in charset.EXCLUDE:
        if cp in got_cps:
            raise SystemExit(f"排除项被收进来了: U+{cp:04X}")

    # 门禁 5: L5 的**层名必须与内容对得上**
    #
    # 为什么要专门加这一条: JIS X 0208 的首字节 0xE0–0xEF 是**二级汉字行**,
    # 落在 U+4E00–U+9FFF 里。早先把它当成"假名/符号/全角", 于是 L5 名义上写的是
    # "假名/符号/全角", 实际内容却有 1,689 个汉字 —— 总量照样对得上 (31,392),
    # 所以前三道门禁全绿, 但**层名是错的**。门禁必须盯住构成, 不能只盯总量。
    cjk_block = _rng(0x4E00, 0x9FFF)
    l5 = next(d for n, d, _ in layers() if n.startswith("L5"))
    l5_cjk = l5 & cjk_block
    l5_sym = l5 - cjk_block
    if len(l5_cjk) != 1689 or len(l5_sym) != 6:
        raise SystemExit(
            f"L5 构成变了: 汉字 {len(l5_cjk)} (期望 1689) / 符号 {len(l5_sym)} (期望 6) "
            "—— 层名或底层判定需要重新核对"
        )
    # 二级汉字集必须整体落在 CJK 块内 (这是 0xE0–0xEF 行的定义性质)
    l2 = jis_x0208_level2_kanji()
    if not l2 <= cjk_block:
        raise SystemExit(
            f"JIS X 0208 二级汉字集里有 {len(l2 - cjk_block)} 个不在 CJK 块内"
        )


def main() -> None:
    print("=== PixelFont Multi 12 字符集账目 (方案 C) ===")
    print()
    print(f"{'层':<32}{'增量':>8}{'累计':>10}")
    print("-" * 50)
    for name, delta, total in ledger():
        print(f"  {name:<30}{delta:>8}{total:>10}")
    print("-" * 50)
    print(f"  {'合计':<30}{'':>8}{ledger()[-1][2]:>10}")
    print()
    got = build_charset_multi12()
    cats: dict[str, int] = {}
    for _, cat in got:
        cats[cat] = cats.get(cat, 0) + 1
    print("=== 分类构成 ===")
    for cat, n in sorted(cats.items(), key=lambda kv: -kv[1]):
        print(f"  {cat:<14}{n:>8}")
    print(f"  {'TOTAL':<14}{len(got):>8}")
    print()
    print("=== 门禁 ===")
    gate_multi12()
    print("  5/5 PASS  (总量 / 方案A交叉 / A∪CJK交叉 / 非第三源与排除项 / L5 构成)")


if __name__ == "__main__":
    main()
