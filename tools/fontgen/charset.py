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
        "blob" 是理由字符串; "per_char" 是 {"reason", "sig_ideo", "sig_alt", "sig_ref"}。
    模式决定门禁查什么: "blob" 只切整字塌陷的字; "per_char" 逐字选源; "all" 全部覆盖。
    字腔项权重是逐字选源的距离函数里字腔那一项的系数 (见 derive_ideo_route.py --hole-weight);
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


def build_stack(route: dict[int, str] | None = None) -> ScriptStack:
    """B 方向: 汉字/标点走 SimHei 12, 拉丁与假名走 MS Gothic 12。

    双源的基线必须一致 —— 这是加在这里的硬门禁, 不是运行时才发现的巧合:
    两个源的 ascent/descent 一旦不同 (换字体版本、换源字体就会发生), 假名会比
    汉字高一格, 混排整行错位, 而且这种错位在单语样张里完全看不出来。

    route: 需要改走非汉字源的码位 (见 load_ideo_route)。
    """
    if route is None:
        route, _mode, _w = load_ideo_route()
    stack = ScriptStack(
        ideo=BitmapFont(path=SIMHEI, index=0, px=12),
        non_ideo=BitmapFont(path=MSGOTHIC, index=0, px=12),
        route=set(route),
    )
    a, b = stack.ideo.metrics, stack.non_ideo.metrics
    if (a.ascent, a.descent) != (b.ascent, b.descent):
        raise SystemExit(
            f"双源基线不一致: 汉字源 {a.ascent}/{a.descent} vs 拉丁源 {b.ascent}/{b.descent} "
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
    from bitfont import count_holes, count_runs
    from coverage import cmap_for

    route, mode, hole_weight = load_ideo_route()
    non_cps = cmap_for(stack.non_ideo.path, stack.non_ideo.index)
    bad: list[str] = []
    for ch, _cat in items:
        cp = ord(ch)
        if cp not in stack.route:
            continue
        if stack.ideo.glyph(ch).width == 0:
            bad.append(f"U+{cp:04X} {ch!r} 汉字源没有字形")
            continue
        h_ideo = count_holes(stack.ideo.glyph(ch))
        h_alt = count_holes(stack.non_ideo.glyph(ch))
        if mode == "per_char":
            rec = route[cp]
            if not isinstance(rec, dict) or "sig_ideo" not in rec:
                bad.append(f"U+{cp:04X} {ch!r} 名单条目缺少签名记录 —— 请重新推导")
                continue
            if cp not in non_cps:
                bad.append(f"U+{cp:04X} {ch!r} 非汉字源已不含此字形 —— 请重新推导名单")
                continue
            cur_id = [
                h_ideo,
                count_runs(stack.ideo.glyph(ch), "col"),
                count_runs(stack.ideo.glyph(ch), "row"),
            ]
            cur_alt = [
                h_alt,
                count_runs(stack.non_ideo.glyph(ch), "col"),
                count_runs(stack.non_ideo.glyph(ch), "row"),
            ]
            if list(rec["sig_ideo"]) != cur_id or list(rec["sig_alt"]) != cur_alt:
                bad.append(
                    f"U+{cp:04X} {ch!r} 结构签名与推导时不一致 "
                    f"(记录 ideo={rec['sig_ideo']}/alt={rec['sig_alt']}, "
                    f"现 ideo={cur_id}/alt={cur_alt}) —— 源字体版本变了, 请重新推导名单"
                )
                continue
            ref = list(rec.get("sig_ref") or [])
            if len(ref) != 3:
                bad.append(f"U+{cp:04X} {ch!r} 名单条目缺少参考签名 —— 请重新推导")
                continue

            def _d(s):
                return (
                    hole_weight * abs(s[0] - ref[0])
                    + abs(s[1] - ref[1])
                    + abs(s[2] - ref[2])
                )

            # 切源理由有两种, 满足其一即成立:
            #   a) 距离: 备选源比汉字源更贴近参考
            #   b) 字腔硬约束: 参考该字有腔, 而汉字源渲染出 0 腔 (整字白块)
            ok_by_dist = _d(cur_alt) < _d(cur_id)
            ok_by_hole = ref[0] >= 1 and cur_id[0] == 0 and cur_alt[0] >= 1
            if not (ok_by_dist or ok_by_hole):
                bad.append(
                    f"U+{cp:04X} {ch!r} 切源理由已不成立 "
                    f"(alt 距离 {_d(cur_alt):g} >= ideo 距离 {_d(cur_id):g}, 参考 {ref}) —— "
                    f"请重新推导名单"
                )
            continue
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
    """
    ideo_cps = cmap_for(stack.ideo.path, stack.ideo.index)
    non_cps = cmap_for(stack.non_ideo.path, stack.non_ideo.index)
    missing: list[str] = []
    for ch, _ in items:
        cps = non_cps if stack._pick(ch) is stack.non_ideo else ideo_cps
        if ord(ch) not in cps:
            missing.append(f"{ch!r} U+{ord(ch):04X} @ {stack._pick(ch).name}")
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
