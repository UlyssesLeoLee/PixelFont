"""Multi 12 字符集定义 —— `PixelFont Multi 12`（方案 C，31,753 码位）。

本模块是 `docs/spec/02-charset-definition.md` §2.7 的**可执行版本**：分层账目、
每一层的增量、交叉核对口径，全部在这里写成代码，而不是只写在文档里。

**「全量」是门禁, 不是口号**（2026-10-25 用户指令「确保日语字和中文简体都是全量」）:

* 简体中文全量 = **GB2312 全部 6,763 个汉字**（区位 16–87 区）；
* 日文全量 = **JIS X 0208 全部 6,355 个汉字 + 200 个符号/假名**。

两个口径都由**编码器机械判定**（`gb2312` / `shift_jis` 编解码），不凭记忆列字表 ——
字表靠记忆列就是编造。`gate_multi12()` 的门禁 6 / 门禁 7 把这两个口径钉成硬门禁。

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

#: ZLabs Pixel 12px —— **简体补源** (OFL-1.1, 保留字体名 "Z工坊/ZLabs")。
#:
#: 为什么需要它: Fusion Pixel 的七个变体都**没有** GB2312 二级汉字里的一部分
#: 生僻字 (实测缺 128 个, 例如 劐 唣 垡 墚 墼 娈 媵 嫠 嬷 尜 峁 嵴 …),
#: 而 Ark Pixel 的七个变体同样缺这 128 个 —— 也就是说 **12px 开源点阵里
#: 只有 ZLabs 覆盖 GB2312 全部 6,763 个汉字**。
#:
#: 它与 Fusion 的网格是**同构**的 (实测: 两者 ascent=10 / descent=2,
#: CJK advance=12px / 拉丁 advance=6px, 墨迹都落在第 0..11 行), 所以可以
#: 直接拼进同一个家族而不错基线。
ZL = REF / "zlabs-pixel-12px"
ZL_CN = ZL / "ZLabsPixel_12px_M_CN.ttf"

#: 方案 C 的目标码位数。任何改动导致对不上，`gate_multi12()` 直接失败。
TARGET_TOTAL = 31_753

#: 方案 A（不追加全部 CJK）的码位数，作为交叉核对口径之一。
TARGET_A = 19_816

#: 这 4 个码位的字形由**本仓库原创手绘**提供（`handdrawn.py`）。
#:
#: 历史: 最初引入本家族时, **任何** 12px 开源点阵字体都不覆盖它们, 所以只能手绘。
#: 现状 (2026-10-25 接入 ZLabs 后): Fusion 的七个变体仍然不覆盖它们, 但
#: ZLabs Pixel 12px CN **覆盖**了 —— 我们**仍然保留手绘字形**, 因为
#: v1.0.0 / v1.0.1 已经发布了这 4 个字形的位图, 换字形等于对已发布码位
#: 做视觉不兼容的改动 (版本规则见 `docs/spec/11` §2.10)。
#:
#: 所以这里的断言是「Fusion 不覆盖它们」, **不是**「没有第三方源覆盖它们」——
#: 后者已经不成立了, 继续那样写就是一条假前提。
HANDDRAWN_CPS = {0x20AC, 0x2260, 0x2264, 0x2265}  # € ≠ ≤ ≥

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
        ZL_CN,
    ]
    missing = [p for p in need if not p.exists()]
    if missing:
        raise ReferenceFontsMissing(
            "缺少参考字体，无法确定 Multi 12 的覆盖边界：\n"
            + "\n".join(f"  {p}" for p in missing)
            + "\n先运行：python tools/fontgen/fetch_ref_fonts.py"
        )


def gb2312_hanzi() -> set[int]:
    """GB2312 双字节区能编码的**全部**汉字（区位 16–87 区，6,763 字）。

    这就是「简体中文全量」的口径。判据是**编码器**而不是记忆:
    `bytes((hi, lo)).decode("gb2312")` 能解出来的就是 GB2312 的字。

    为什么不用「通用规范汉字表 8,105 字」当口径: 那张表无法由编码器推导,
    只能靠人列 —— 一旦列错, 覆盖率就成了编的数字。GB2312 是**机械可复现**的,
    而且它本来就是「简体中文」在编码层面的标准集合。
    """
    out: set[int] = set()
    for hi in range(0xB0, 0xF8):      # 区 16–87
        for lo in range(0xA1, 0xFF):  # 位 1–94
            try:
                cp = ord(bytes((hi, lo)).decode("gb2312"))
            except UnicodeDecodeError:
                continue
            if 0x4E00 <= cp <= 0x9FFF:
                out.add(cp)
    return out


def jis_x0208_all() -> set[int]:
    """JIS X 0208 的**全部**汉字（一级 + 二级）—— 「日文全量」的口径。

    为什么要单独一个函数: 它只被「全量」门禁用, 不参与分层定义。
    这样故障注入自测可以单独替换它 —— 若它也参与分层, 一改就会把
    字符集本身改掉, 门禁 1（总量）会先炸, 门禁 7 就永远测不到。
    """
    return jis_x0208_kanji() | jis_x0208_level2_kanji()


def coverage_gaps(got_cps: set[int]) -> list[str]:
    """「简日全量」两个口径的缺口描述（空 = 全量）。

    抽成独立函数是为了**能被故障注入自测** —— 藏在 `gate_multi12()` 里的
    检查等于没有测试覆盖。
    """
    bad: list[str] = []
    gb = gb2312_hanzi()
    gb_miss = sorted(gb - got_cps)
    if gb_miss:
        bad.append(f"简体中文不全量: GB2312 {len(gb)} 个汉字缺 {len(gb_miss)} 个 "
                   f"(如 U+{gb_miss[0]:04X} {chr(gb_miss[0])}) —— "
                   "补源或改口径, 不要在文档里写「全量」")
    jis_all = jis_x0208_all()
    jp_miss = sorted(jis_all - got_cps)
    if jp_miss:
        bad.append(f"日文不全量: JIS X 0208 {len(jis_all)} 个汉字缺 {len(jp_miss)} 个 "
                   f"(如 U+{jp_miss[0]:04X} {chr(jp_miss[0])})")
    kana_miss = sorted(jis_x0208_kana_punct() - got_cps)
    if kana_miss:
        bad.append(f"日文不全量: JIS X 0208 符号/假名缺 {len(kana_miss)} 个 "
                   f"(如 U+{kana_miss[0]:04X})")
    return bad


def cjk_source_cmaps() -> dict[str, set[int]]:
    """CJK 层各源的 cmap —— **字符集判定与路由判定共用同一份事实**。

    `fusion_ja` 覆盖 JIS 汉字/假名, `zlabs_cn` 补上 Fusion 完全缺失的简体汉字
    (含 GB2312 二级罕用字 128 个)。两者的**并集**就是 CJK 层的可用边界。
    """
    return {
        "fusion_ja": _cmap(FUS / "fusion-pixel-12px-monospaced-ja.ttf"),
        "zlabs_cn": _cmap(ZL_CN),
    }


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

    # CJK 层的可用边界 = **各可用源的并集**, 不是某一个源的覆盖。
    #
    # 以前只用 `ja`: Fusion 的 ja 变体覆盖 JIS 汉字与假名, 但**缺** GB2312 二级
    # 罕用字 128 个 —— 于是「简体中文全量」差 128 个字。补上 `zlabs_cn` 之后,
    # CJK 块的可选边界扩到两者并集, 两个「全量」口径才都成立。
    #
    # 用**并集**而不是「特判那 128 个」: 特判会让层定义出现一个只为修一个
    # 数字而存在的特例; 并集是统一规则 —— 「一个码位只要有任何一个可用源
    # 提供字形, 就收进来」。
    cjk_cover = ja | _cmap(ZL_CN)

    raw = [
        ("L0 当前家族", current_family(), "current"),
        ("L1 Latin Ext A/B", _rng(0x0100, 0x024F) & la, "latin-ext"),
        ("L2 Greek", _rng(0x0370, 0x03FF) & la, "greek"),
        ("L3 Cyrillic", _rng(0x0400, 0x04FF) & la, "cyrillic"),
        ("L4 Hangul syllables", _rng(0xAC00, 0xD7AF) & ko, "hangul"),
        # L5 的内容是**二级汉字 + 少量符号**, 不是"假名/符号/全角" ——
        # 详见 `jis_x0208_level2_kanji()` 的注释与门禁 5。
        ("L5 JIS X 0208 二级汉字 + 符号/假名",
         (jis_x0208_level2_kanji() | jis_x0208_kana_punct()) & cjk_cover, "jis-l2"),
        ("L6 JIS X 0208 一级汉字", jis_x0208_kanji() & cjk_cover, "jis-kanji"),
        ("L7 CJK 其余", _rng(0x4E00, 0x9FFF) & cjk_cover, "cjk-ext"),
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
    """七道硬门禁。任何一条不过就抛错 —— 总量对不上时不能放行。"""
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
    cjk_cover = ja | _cmap(ZL_CN)
    cur = current_family()
    opt_a = (
        cur
        | (_rng(0x0100, 0x024F) & la)
        | (_rng(0x0370, 0x03FF) & la)
        | (_rng(0x0400, 0x04FF) & la)
        | (_rng(0xAC00, 0xD7AF) & ko)
        | (jis_x0208_kana_punct() & cjk_cover)
        | (jis_x0208_kanji() & cjk_cover)
    )
    cjk_all = _rng(0x4E00, 0x9FFF) & cjk_cover
    if len(opt_a | cjk_all) != TARGET_TOTAL:
        raise SystemExit(
            f"交叉口径「方案 A ∪ CJK 整块」= {len(opt_a | cjk_all)} != {TARGET_TOTAL}"
        )

    # 门禁 4：4 个手绘码位必须在集合里，且 Fusion 仍然不覆盖它们
    all_fusion: set[int] = set()
    for name in ("ja", "ko", "latin", "zh_hans", "zh_hant", "zh_hk", "zh_tw"):
        p = FUS / f"fusion-pixel-12px-monospaced-{name}.ttf"
        if p.exists():
            all_fusion |= _cmap(p)
    got = build_charset_multi12()
    got_cps = {ord(c) for c, _ in got}
    missing = HANDDRAWN_CPS - got_cps
    if missing:
        raise SystemExit(f"手绘码位缺失: {sorted(hex(c) for c in missing)}")
    wrongly_covered = HANDDRAWN_CPS & all_fusion
    if wrongly_covered:
        raise SystemExit(
            "手绘码位被 Fusion 覆盖了，账目前提变了: "
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

    # ---- 门禁 6: 简体中文全量 = GB2312 全部 6,763 个汉字 ----
    #
    # 这条门禁就是用户 2026-10-25 那句「确保……中文简体……都是全量」的**可执行版**。
    # 口径由 `gb2312_hanzi()` 机械推导 (编码器判定), 不用任何字表。
    #
    # ---- 门禁 7: 日文全量 = JIS X 0208 全部 6,355 汉字 + 200 符号/假名 ----
    gaps = coverage_gaps(got_cps)
    if gaps:
        raise SystemExit("\n".join(gaps))


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
    print("  7/7 PASS  (总量 / 方案A交叉 / A∪CJK交叉 / 手绘码位与排除项 / L5 构成 / "
          "简体全量 GB2312 / 日文全量 JIS X 0208)")
    print()
    print("=== 全量口径实测 ===")
    got_set = {ord(c) for c, _ in got}
    gb = gb2312_hanzi()
    jis_all = jis_x0208_all()
    print(f"  简体中文 GB2312   {len(gb & got_set)}/{len(gb)}  "
          f"= {100 * len(gb & got_set) / len(gb):.2f}%")
    print(f"  日文 JIS X 0208 汉字 {len(jis_all & got_set)}/{len(jis_all)}  "
          f"= {100 * len(jis_all & got_set) / len(jis_all):.2f}%")
    kana = jis_x0208_kana_punct()
    print(f"  日文 JIS X 0208 符号/假名 {len(kana & got_set)}/{len(kana)}  "
          f"= {100 * len(kana & got_set) / len(kana):.2f}%")


if __name__ == "__main__":
    main()
