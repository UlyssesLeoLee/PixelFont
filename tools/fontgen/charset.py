"""字符集定义 + 全集缺字门禁。

汉字集的选择理由（重要）:
    用户点的是"常用汉字 3500"。我无法可靠地凭记忆写出《通用规范汉字表》一级
    3500 字表 —— 凭记忆列字表就是编造, 而字库缺字是不可见的故障。
    所以改用 GB2312 一级汉字 3755 字: 它可以由 gb2312 编码器机械推导
    (0xB0A1-0xD7F9), 完全可复现、可验证, 且在实践中就是"最常用字"的集合。
    与 3500 常用字表有几十个字的差异, 已在交付说明里写明。

假名集覆盖: 平假名 / 片假名 / 半角片假名 / 促音与长音符 / 々〆〇ヶ。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bitfont import BitmapFont, ScriptStack  # noqa: E402
from coverage import cmap_for  # noqa: E402

SIMHEI = r"C:\Windows\Fonts\simhei.ttf"
MSGOTHIC = r"C:\Windows\Fonts\msgothic.ttc"

# 第三个生产源: Fusion Pixel 12px 简体 (OFL-1.1 + Cubic 11 OFL + Galmuri LICENSE)。
#
# 为什么是 Fusion 而不是 Ark Pixel:
#   实测 Fusion 的简体版与 Ark 的**结构**完全相同 (3605 个共有汉字逐个一致),
#   但**覆盖**多 12054 个码位 —— 它把 Ark / Cubic 11 / Galmuri 缝进同一套字重体系。
#   对我们 4140 个码位: Ark 覆盖 3990 (缺 150), **Fusion 覆盖全部 4140**。
#   而共有部分**位图逐字节相同** (实测 3989/3989) ——
#   所以换源对 3989 个字零画风变化, 却让原先没得选的 150 个字
#   (酱/誊/鳖/蛰/嘎/撬/橇 ...) 有了真正的点阵字形。
#   实测那 7 个仍未修的字, 换源后与**独立**参考 Unifont 的结构距离:
#   Fusion 30-71  vs  SimHei 56-89 / MS Gothic 76-79 —— 明显更好。
#   (Zpix 的字形是 13 宽, 放不进我们 12px 的全角格, 所以它当不了生产源。)
#
# 为什么裁剪后入库 (而不是像参考字体那样只记来源+sha256):
# 参考字体只用于**校验**, 不参与构建, 所以不入库; 生产源参与构建, 不入库就等于
# "构建依赖一台机器上恰好下载过某个字体", 换台机器构建不出同一个结果。
# 裁剪到本项目字符集后约 746 KB, 三份许可证一并入库。
ARK_DIR = Path(__file__).resolve().parents[2] / "vendor" / "fusion-pixel-12px"
ARK_TTF = ARK_DIR / "fusion-pixel-12px-monospaced-zh_hans-subset.ttf"
# 备选: 开发机上未裁剪的原始下载 (third_party/ref_fonts/, 不入库)
ARK_FALLBACK = (
    Path(__file__).resolve().parents[2]
    / "third_party"
    / "ref_fonts"
    / "fusion-pixel-12px"
    / "fusion-pixel-12px-monospaced-zh_hans.ttf"
)

# 显式排除的码位, 每一条都必须写明原因。
# 这不是"修到门禁变绿", 而是把已知的字体缺字变成写在代码里的既定事实。
EXCLUDE: dict[int, str] = {
    0x3097: "゗ — 古旧假名合字, 非 JIS 字集, MS Gothic 无此字形, 现代用途为零",
    0x3098: "゘ — 古旧假名合字, 非 JIS 字集, MS Gothic 无此字形, 现代用途为零",
}


def gb2312_level1() -> list[str]:
    """GB2312 一级汉字 (区位 16-55 区, 3755 字), 按 GB2312 码位顺序 = 拼音序。"""
    out: list[str] = []
    for hi in range(0xB0, 0xD8):
        for lo in range(0xA1, 0xFF):
            try:
                out.append(bytes((hi, lo)).decode("gb2312"))
            except UnicodeDecodeError:
                continue
    return out


def ascii_chars() -> list[str]:
    return [chr(c) for c in range(0x20, 0x7F)]


def kana_chars() -> list[str]:
    blocks = [
        range(0x3041, 0x30A0),  # 平假名
        range(0x30A0, 0x3100),  # 片假名
        range(0xFF61, 0xFFA0),  # 半角片假名
    ]
    out: list[str] = []
    for b in blocks:
        for cp in b:
            if cp in EXCLUDE:
                continue
            out.append(chr(cp))
    out += ["々", "〆", "〇", "ヶ", "ー", "～"]
    return out


def extras() -> list[str]:
    """游戏里高频但不属于三大块的符号与标点。"""
    return list("·—…、。，．！？；：（）【】「」『』《》〈〉～－＋×÷＝％＄￥＃＆＠")


def build_charset() -> list[tuple[str, str]]:
    """返回 [(字符, 分类)]，顺序即 atlas / 字体 cmap 的建议顺序。"""
    items: list[tuple[str, str]] = []
    items += [(c, "ascii") for c in ascii_chars()]
    items += [(c, "punct") for c in extras()]
    items += [(c, "kana") for c in kana_chars()]
    items += [(c, "hanzi") for c in gb2312_level1()]
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for ch, cat in items:
        if ch not in seen:
            seen.add(ch)
            out.append((ch, cat))
    return out


def load_ideo_route() -> tuple[dict[int, object], str, float]:
    """读 ideo_route.json —— 需要改用非汉字源渲染的码位名单。

    名单的判据与出处见 docs/glyph-identity-verification.md:
        SimHei 是平滑轮廓字体, 12px 下密笔画汉字的部件横画会粘连, 把「日」「目」
        这类部件的字腔整个填死, 整字渲染成一块白块; MS Gothic 的 12px 是原生
        点阵位图, 字腔是活的。对这些字改用 MS Gothic 的原生位图。

    名单存成文件而不是硬编码在代码里, 是因为它**必须能被重新推导**:
    换源字体版本后要重跑推导脚本核对, 而不是靠人肉维护一张表。

    返回 (码位 -> 名单条目, 模式, 字腔项权重)。条目内容随模式不同:
        "blob" 是理由字符串;
        "per_char" 是 {"reason", "source", "sig_ideo", "sig_alt", "sig_fusion"?, "sig_ref"}。
    模式决定门禁查什么: "blob" 只切整字塌陷的字; "per_char" 逐字选源; "all" 全部覆盖。
    字腔项权重是逐字选源的距离函数里字腔那一项的系数 (见 route_rule.HOLE_WEIGHT);
    门禁要用它复算"当初那个选择现在还成不成立"。
    """
    import json

    p = Path(__file__).parent / "ideo_route.json"
    if not p.exists():
        return {}, "blob", 1.0
    d = json.loads(p.read_text(encoding="utf-8"))
    route = {
        (int(k[2:], 16) if isinstance(k, str) and k.upper().startswith("U+") else int(k)): v
        for k, v in d.get("route", {}).items()
    }
    return route, d.get("mode", "blob"), float(d.get("hole_weight", 1.0))


def route_source_map(route: dict[int, object]) -> dict[int, str]:
    """把名单条目压成 (码位 -> 源注册表的键), 给 ScriptStack 用。

    "blob" 模式的条目是理由字符串 —— 那时一律走非汉字源。
    """
    out: dict[int, str] = {}
    for cp, rec in route.items():
        if isinstance(rec, dict):
            out[cp] = str(rec.get("source", "non_ideo"))
        else:
            out[cp] = "non_ideo"
    return out


def ark_path() -> Path:
    """第三个源的字体文件路径。

    优先用入库的裁剪版 (构建必须自包含); 开发机上没裁剪时退回原始下载。
    """
    if ARK_TTF.exists():
        return ARK_TTF
    if ARK_FALLBACK.exists():
        return ARK_FALLBACK
    raise SystemExit(
        f"缺少第三个源字体: {ARK_TTF}\n"
        f"用 tools/fontgen/vendor_ark_pixel.py 生成 (需要 third_party/ref_fonts 里的原始下载)"
    )


def build_stack(route: dict[int, object] | None = None) -> ScriptStack:
    """汉字/标点走 SimHei 12, 拉丁与假名走 MS Gothic 12, 名单里的码位走点名源。

    各源的基线必须一致 —— 这是加在这里的硬门禁, 不是运行时才发现的巧合:
    源的 ascent/descent 一旦不同 (换字体版本、换源字体就会发生), 假名会比
    汉字高一格, 混排整行错位, 而且这种错位在单语样张里完全看不出来。

    route: 名单条目 (见 load_ideo_route); None 表示按 ideo_route.json 建。
    """
    if route is None:
        route, _mode, _w = load_ideo_route()
    ideo = BitmapFont(path=SIMHEI, index=0, px=12)
    non_ideo = BitmapFont(path=MSGOTHIC, index=0, px=12)
    # Ark Pixel 的 em-box 约定不同 (ascent 10 vs 11), 但它的字形是按 12px
    # 网格设计的, 墨迹落点与 MS Gothic 一致。统一成全字体的格子几何,
    # 字形仍按源字体自己的 offset 贴 —— 详见 BitmapFont.cell_ascent 的注释。
    ark = BitmapFont(path=str(ark_path()), index=0, px=12, cell_ascent=11, cell_descent=2)
    stack = ScriptStack(
        ideo=ideo,
        non_ideo=non_ideo,
        third=ark,
        route=route_source_map(route),
    )
    a, b = ideo.metrics, non_ideo.metrics
    if (a.ascent, a.descent) != (b.ascent, b.descent):
        raise SystemExit(
            f"双源基线不一致: 汉字源 {a.ascent}/{a.descent} vs 拉丁源 {b.ascent}/{b.descent} "
            f"—— 混排会错行, 拒绝构建"
        )
    c = ark.metrics
    if (a.ascent, a.descent) != (c.ascent, c.descent):
        raise SystemExit(
            f"第三源基线不一致: 汉字源 {a.ascent}/{a.descent} vs 点阵源 {c.ascent}/{c.descent} "
            f"—— 混排会错行, 拒绝构建"
        )
    return stack


def gate_ideo_route(stack: ScriptStack, items: list[tuple[str, str]]) -> None:
    """ideo 路由名单的有效性门禁: 名单里的每一个字都必须**仍然**满足切源理由。

    模式 "blob" (只切整字塌陷的字) 的切源理由:
        汉字源渲染出来的字**一个腔都没有** (整字塌成白块),
        而非汉字源渲染出来的字**有腔**。
    模式 "all" (全覆盖) 的切源理由:
        非汉字源渲染出来的字**有腔** (否则切过去只会更糟)。
    模式 "per_char" (逐字选源) 的切源理由:
        名单里**记录了推导当时的结构签名** (字腔/竖笔/横笔)。构建期重算一遍,
        与记录不符就说明源字体版本变了 —— 切源依据已经过期, 必须重新推导。
        这一步不需要参考字体 (参考侧的签名也记在名单里)。
        签名一致还不够: 再用名单里记录的参考签名**复算一次距离比较**,
        确认"切过去确实更好"这个判断现在依然成立。

    为什么要门禁: 名单是按"当前两个源字体"推导出来的。换了 SimHei / MS Gothic 的
    版本, 某个字可能已经不再塌陷 —— 那时切过去反而会引入不必要的风格差异。
    这种事不能靠人记得回头看一眼, 所以在这里硬拦。
    """
    if not stack.route:
        return
    from coverage import cmap_for
    import route_rule as rr
    from route_rule import sig_of

    route, mode, hole_weight = load_ideo_route()
    non_cps = cmap_for(stack.non_ideo.path, stack.non_ideo.index)
    ark_cps: set[int] = set()
    if stack.third is not None:
        ark_cps = cmap_for(stack.third.path, stack.third.index)
    bad: list[str] = []
    for ch, _cat in items:
        cp = ord(ch)
        if cp not in stack.route:
            continue
        if stack.ideo.glyph(ch).width == 0:
            bad.append(f"U+{cp:04X} {ch!r} 汉字源没有字形")
            continue
        if mode == "per_char":
            rec = route[cp]
            if not isinstance(rec, dict) or "sig_ideo" not in rec:
                bad.append(f"U+{cp:04X} {ch!r} 名单条目缺少签名记录 —— 请重新推导")
                continue
            src = str(rec.get("source", "non_ideo"))
            # 候选源: 汉字源 + 点阵源。缺字的源用 None 表示 (必须查 cmap,
            # 不能靠渲染结果判断 —— 缺字时 FreeType 画 .notdef 空心豆腐块,
            # 它自带 1 个腔, 会把"缺字"误判成"能画")。
            cands: dict[str, tuple[int, int, int] | None] = {
                "ideo": sig_of(stack.ideo.glyph(ch)),
                "non_ideo": (
                    sig_of(stack.non_ideo.glyph(ch)) if cp in non_cps else None
                ),
            }
            if stack.third is not None:
                cands["fusion"] = sig_of(stack.third.glyph(ch)) if cp in ark_cps else None
            if src not in cands:
                bad.append(f"U+{cp:04X} {ch!r} 名单指定的源 {src!r} 不存在 —— 请重新推导")
                continue
            if cands[src] is None:
                bad.append(
                    f"U+{cp:04X} {ch!r} 名单指定的源 {src!r} 已不含此字形 —— 请重新推导名单"
                )
                continue
            # 1) 签名比对: 源字体版本变了就说明名单过期
            #    记录里是 None = "推导当时这个源根本没有这个字形"。
            #    现在这个源若有了字形, 是源覆盖变了 —— 不直接报错,
            #    由下面第 2 步"复算选择"来判定这个变化是否改变了结论。
            #
            #    注意签名键的映射: 名单里 MS Gothic 存的是 "sig_alt" (历史名),
            #    源注册表里的键是 "non_ideo" —— 映射错了就永远查不到那个签名,
            #    于是 MS Gothic 换版本也不会被拦 (自审时真踩到过)。
            sig_key = {"ideo": "sig_ideo", "non_ideo": "sig_alt", "fusion": "sig_fusion"}
            for k, cur in cands.items():
                if cur is None:
                    continue
                old = rec.get(sig_key.get(k, "sig_" + k))
                if old is None:
                    continue
                if list(old) != list(cur):
                    bad.append(
                        f"U+{cp:04X} {ch!r} 结构签名与推导时不一致 "
                        f"(记录 {k}={list(old)}, 现 {k}={list(cur)}) —— "
                        f"源字体版本变了, 请重新推导名单"
                    )
            if bad:
                continue
            ref = list(rec.get("sig_ref") or [])
            if len(ref) != 3:
                bad.append(f"U+{cp:04X} {ch!r} 名单条目缺少参考签名 —— 请重新推导")
                continue
            # 2) 复算选择: 用**同一条规则** (route_rule.build_pool + choose) 重算,
            #    确认当初那个选择现在依然成立。规则不在这里重写一遍 ——
            #    推导与门禁用同一份实现, 否则门禁检查的是不存在的事。
            #
            #    名单里带 "forced" 的条目 (目视复核确认劣化, 强制改源) 用的是另一条
            #    规则 (腔数封顶到参考值, 再按距离决胜) —— 门禁必须用**同一条**,
            #    否则门禁会判这些字"切源理由不成立"而拒构建。
            if rec.get("forced"):
                picked, _psig = rr.choose_forced(cands, tuple(ref), hole_weight)
            elif rec.get("identity_fix"):
                # 字符身份修正的条目: 选源规则是"我方把 X 画成了 Y, 换个能画对 X 的源",
                # 不是距离规则。门禁要复算的是这条规则的**结论**:
                #   · 所选源的字腔数必须与参照一致 (它画对了这个码位)
                #   · 且必须与另一个可用源不同 (消歧确实还在发生)
                # 这两条都是可复算的, 不需要参考字体本身。
                want = ref[0]
                got = cands[src][0] if cands.get(src) is not None else None
                others = [
                    s[0]
                    for k, s in cands.items()
                    if k != src and s is not None
                ]
                if got != want:
                    bad.append(
                        f"U+{cp:04X} {ch!r} 字符身份修正已失效 "
                        f"(所选源 {src} 的字腔数 {got} != 参照的 {want}) —— 请重新推导名单"
                    )
                elif want in others:
                    bad.append(
                        f"U+{cp:04X} {ch!r} 字符身份消歧已失效 "
                        f"(另一个源也画成 {want} 腔, 与参照一致) —— 请重新推导名单"
                    )
                continue
            else:
                pool = rr.build_pool(cands, tuple(ref))
                picked, _psig = rr.choose(pool, tuple(ref), hole_weight)
            if picked != src:
                bad.append(
                    f"U+{cp:04X} {ch!r} 切源理由已不成立 "
                    f"(按当前规则应选 {picked!r}, 名单写的是 {src!r}; "
                    f"参考 {ref}) —— 请重新推导名单"
                )
            continue
        # blob / all 模式: 老的理由
        from bitfont import count_holes

        h_ideo = count_holes(stack.ideo.glyph(ch))
        h_alt = count_holes(stack.non_ideo.glyph(ch))
        if mode == "blob" and h_ideo > 0:
            bad.append(
                f"U+{cp:04X} {ch!r} 汉字源已能渲出 {h_ideo} 个字腔, 不再塌陷 —— "
                f"切源理由已不成立, 请重新推导名单"
            )
        if h_alt <= 0:
            bad.append(
                f"U+{cp:04X} {ch!r} 非汉字源也画不出字腔 ({h_alt}) —— "
                f"切过去没用, 应从名单移除"
            )
    if bad:
        head = "\n  ".join(bad[:40])
        raise SystemExit(
            f"ideo 路由名单失效, 共 {len(bad)} 个码位:\n  {head}"
            + ("\n  ..." if len(bad) > 40 else "")
        )


def gate_full_coverage(stack: ScriptStack, items: list[tuple[str, str]]) -> None:
    """全集缺字门禁: 每一个字符, 路由到的源字体必须有该字形。

    像素字体没有回退 —— 缺一个字就是一块豆腐, 而且在大字库里几乎不可能
    靠肉眼发现。所以这里逐字符查 cmap, 有一个不过就中止构建。

    注意: 必须查**实际被路由到的那个源**的 cmap —— 有第三个源以后,
    "这个字在哪个源里"不再是"汉字源/拉丁源"二选一了。
    """
    cps_of: dict[int, set[int]] = {}
    for name, f in stack.sources.items():
        cps_of[id(f)] = cmap_for(f.path, f.index)
    missing: list[str] = []
    for ch, _ in items:
        f = stack._pick(ch)
        if ord(ch) not in cps_of[id(f)]:
            missing.append(f"{ch!r} U+{ord(ch):04X} @ {f.name}")
    if missing:
        head = "\n  ".join(missing[:40])
        raise SystemExit(
            f"缺字门禁未通过, 共 {len(missing)} 个字符缺字形:\n  {head}"
            + ("\n  ..." if len(missing) > 40 else "")
        )


def main() -> None:
    items = build_charset()
    stack = build_stack()
    m = stack.metrics
    print(f"网格 {m.cell_w}x{m.cell_h}  半角 {m.half_w}  基线 {m.ascent}/{m.descent}")
    print(f"字符总数 {len(items)}")
    for cat in ("ascii", "punct", "kana", "hanzi"):
        n = sum(1 for _, c in items if c == cat)
        print(f"  {cat:<6} {n}")
    gate_full_coverage(stack, items)
    print("缺字门禁: 通过 (全部字符在对应源字体中均有字形)")
    gate_ideo_route(stack, items)
    print(f"ideo 路由门禁: 通过 ({len(stack.route)} 个码位改走非汉字源, 切源理由均成立)")


if __name__ == "__main__":
    main()
