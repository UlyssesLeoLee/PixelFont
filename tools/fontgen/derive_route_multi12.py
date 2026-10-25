"""Multi 12 字形路由名单 —— 推导、逐条渲染验证、导出可 diff 的快照。

用法:
    python tools/fontgen/derive_route_multi12.py            # 推导 + 验证 + 打印
    python tools/fontgen/derive_route_multi12.py --write    # 同时写出 JSON 快照

产出的快照 `tools/fontgen/route_multi12.json` 是**可重算的**：
规则在 `route_multi12.py` 里, 快照只是它的一次性展开, 用来 diff 与抽查。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import charset_multi12 as m12  # noqa: E402
import route_multi12 as rm  # noqa: E402
from bitfont import BitmapFont  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tools" / "fontgen" / "route_multi12.json"

CELL_H = 13
FULL, HALF = 12, 6


def _font(key: str):
    """取该源的字体对象。

    读的是**入库的裁剪版** (`vendor/multi12/`) —— 也就是构建真正用的那份,
    这样门禁验的就是要出货的东西, 而不是本机恰好下载的原始版。
    """
    if key == "handdrawn":
        from handdrawn import HanddrawnFont

        return HanddrawnFont()
    return BitmapFont(path=str(rm.source_path(key)), index=0, px=12,
                      cell_ascent=11, cell_descent=2)


def main() -> int:
    rm.require_sources()
    route = rm.build_route()
    layers = rm.layer_of()
    chars = {ord(c) for c, _ in m12.build_charset_multi12()}

    print("=" * 74)
    print("PixelFont Multi 12 —— 字形路由名单推导 (全开源路线)")
    print("=" * 74)

    bad: list[str] = []
    warnings: list[str] = []

    # ---- 门禁 1: 覆盖 ----
    if set(route) != chars:
        miss = sorted(chars - set(route))
        extra = sorted(set(route) - chars)
        bad.append(f"路由与字符集不一致: 缺 {len(miss)} / 多 {len(extra)}")
    print(f"\n[1] 覆盖: {len(route)} 个码位 (字符集 {len(chars)}) "
          f"{'OK' if set(route) == chars else 'FAIL'}")

    # ---- 门禁 2: 源集合 ----
    counts = Counter(route.values())
    unknown = set(counts) - set(rm.SOURCES)
    if unknown:
        bad.append(f"出现未登记的源: {sorted(unknown)}")
    print(f"[2] 源集合: {dict(counts)} {'OK' if not unknown else 'FAIL'}")

    # ---- 门禁 3: handdrawn 恰好 4 个缺口 ----
    got_hd = {cp for cp, s in route.items() if s == "handdrawn"}
    if got_hd != rm.GAPS:
        bad.append(f"handdrawn 名单不对: {sorted(hex(c) for c in got_hd)}")
    print(f"[3] handdrawn = {len(got_hd)} 个 (期望 4: € ≠ ≤ ≥) "
          f"{'OK' if got_hd == rm.GAPS else 'FAIL'}")
    from handdrawn import check as hd_check
    hd_problems = hd_check()
    if hd_problems:
        bad.append(f"手绘字形自检未过: {hd_problems}")
    print(f"    手绘字形自检 (画布/宽度/墨迹): {'OK' if not hd_problems else 'FAIL'}")

    # ---- 门禁 4/5: 语系计数 ----
    if counts.get("fusion_ko", 0) != 11172:
        bad.append(f"fusion_ko = {counts.get('fusion_ko')} (期望 11172)")
    shared = rm._cjk_shared()
    got_zh = {cp for cp, s in route.items() if s == "fusion_zh_hans"}
    if got_zh != shared:
        bad.append(f"fusion_zh_hans 名单 != 中日共享 2,078 (差 {len(got_zh ^ shared)})")
    print(f"[4] fusion_ko = {counts.get('fusion_ko', 0)} (期望 11,172) "
          f"{'OK' if counts.get('fusion_ko', 0) == 11172 else 'FAIL'}")
    print(f"[5] fusion_zh_hans = {counts.get('fusion_zh_hans', 0)} (期望 2,078 = 中日共享) "
          f"{'OK' if got_zh == shared else 'FAIL'}")

    # ---- 门禁 6/7: 逐条渲染 ----
    print(f"\n[6/7] 逐条渲染 ({len(route)} 个码位) ...")
    blank: list[int] = []
    blank_ok: list[int] = []
    badw: list[tuple[int, int]] = []
    adv_hist: Counter = Counter()
    ink_hist: Counter = Counter()
    glyphs: dict[int, "BitmapFont"] = {}
    for key in rm.SOURCES:
        assigned = [cp for cp, s in route.items() if s == key]
        if not assigned:
            continue
        bf = _font(key)
        for cp in assigned:
            ch = chr(cp)
            g = bf.glyph(ch)
            raw = g.tobytes()
            if not any(raw):
                # 空白字符本来就该没有墨迹 (U+0020 空格 / U+00A0 NBSP / U+3000 全角空格)
                if ch.isspace():
                    blank_ok.append(cp)
                else:
                    blank.append(cp)
            if g.width not in (FULL, HALF):
                badw.append((cp, g.width))
            if g.height != CELL_H:
                badw.append((cp, f"高 {g.height}"))
            adv_hist[g.width] += 1
            # 墨迹必须落在 cell 内 (画布尺寸就是 cell 尺寸, 越界即溢出)
            ink_hist[sum(1 for y in range(g.height) for x in range(g.width)
                         if g.load()[x, y])] += 1
        glyphs[key] = bf
    if blank:
        bad.append(f"{len(blank)} 个码位渲染成空字形: "
                   + ", ".join(f"U+{c:04X}" for c in blank[:10]))
    if badw:
        bad.append(f"{len(badw)} 个码位的字形尺寸不合网格: {badw[:5]}")
    print(f"     空字形(应为空白字符) {len(blank_ok)} / 非空白却空 {len(blank)}  "
          f"尺寸不合 {len(badw)}  "
          f"{'OK' if not blank and not badw else 'FAIL'}")
    print(f"     advance 分布: {dict(sorted(adv_hist.items()))}")

    # ---- 门禁 8: U+005C 不得画成 ¥ ----
    bf_latin = glyphs["fusion_latin"]
    bs = bf_latin.glyph("\\").tobytes()
    yen = bf_latin.glyph("¥").tobytes()
    if bs == yen:
        bad.append("U+005C 与 U+00A5 逐像素相同 —— 反斜杠被画成了 Yen 符号")
    print(f"[8] U+005C ≠ U+00A5 (反斜杠没被画成 ¥): "
          f"{'OK' if bs != yen else 'FAIL'}")

    # ---- 门禁 9: 缺口前提没变 ----
    # 前提 = 「任何 Fusion 变体都不覆盖这 4 个码位」。这必须查**原始全字集版**的 cmap:
    # 入库的裁剪版只含路由分配给它的码位, 缺口当然不在里面, 查它证明不了任何事。
    # 原始下载不在 (`third_party/` 不入库) 时, 这一条**无法独立复核** ——
    # 必须显式说「没验」, 不能让它变成一个看起来在通过的假门禁。
    fusion_all: set[int] = set()
    scanned = 0
    for v in ("latin", "ko", "ja", "zh_hans", "zh_hant", "zh_hk", "zh_tw"):
        p = m12.FUS / f"fusion-pixel-12px-monospaced-{v}.ttf"
        if p.exists():
            fusion_all |= m12._cmap(p)
            scanned += 1
    covered = rm.GAPS & fusion_all
    if covered:
        bad.append(f"缺口前提变了: {sorted(hex(c) for c in covered)} 现在被 Fusion 覆盖")
        print("[9] 4 个缺口仍不被任何 Fusion 变体覆盖: FAIL")
    elif scanned == 0:
        warnings.append(
            "门禁 9 的前提未独立复核: third_party 原始下载不可用, "
            "无法证明「Fusion 不覆盖这 4 个码位」")
        print("[9] 4 个缺口仍不被任何 Fusion 变体覆盖: **未复核** "
              "(缺 third_party 原始下载) —— 见下方警告")
    else:
        print(f"[9] 4 个缺口仍不被任何 Fusion 变体覆盖 "
              f"(已扫 {scanned} 个变体): OK")

    # ---- 门禁 10: 全开源 ----
    licenses = {rm.source_license(k) for k in counts}
    if licenses - {"OFL-1.1"}:
        bad.append(f"出现非 OFL-1.1 的源: {sorted(licenses - {'OFL-1.1'})}")
    print(f"[10] 全部源均为 OFL-1.1: "
          f"{'OK' if not licenses - {'OFL-1.1'} else 'FAIL'}  {sorted(licenses)}")

    # ---- 汇总 ----
    print()
    print("=== 源分布 (按码位) ===")
    for key, n in counts.most_common():
        path, lic, desc = rm.SOURCES[key]
        print(f"  {key:<14}{n:>7}  {lic:<9} {desc}")
    print(f"  {'TOTAL':<14}{sum(counts.values()):>7}")

    print("\n=== 按层 × 源 ===")
    per = Counter((layers.get(cp, "?"), s) for cp, s in route.items())
    for (layer, src), n in sorted(per.items()):
        print(f"  {layer:<34} {src:<14}{n:>7}")

    print()
    if warnings:
        print("=== 警告 (不阻塞, 但结论未独立复核) ===")
        for w in warnings:
            print(f"  [WARN] {w}")
        print()

    if bad:
        print("=" * 74)
        print(f"门禁未过 ({len(bad)} 条):")
        for b in bad:
            print(f"  [FAIL] {b}")
        print("=" * 74)
        return 1

    print("=" * 74)
    print("门禁 10/10 PASS" + (f" (另有 {len(warnings)} 条警告)" if warnings else ""))
    print("=" * 74)

    if "--write" in sys.argv:
        snapshot = {
            "tool": "derive_route_multi12",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "policy": "全开源路线 (全部 OFL-1.1) —— 2026-10-24 拍板",
            "rule_module": "tools/fontgen/route_multi12.py",
            "build_inputs": "全部在入库路径上 (vendor/multi12/); 构建不读 third_party",
            "sources": {
                k: {
                    "build_path": str(v[0].relative_to(ROOT)) if ROOT in v[0].parents
                    else str(v[0]),
                    "origin_path": str(rm.origin_path(k).relative_to(ROOT))
                    if k in rm.ORIGINS and ROOT in rm.origin_path(k).parents
                    else (str(rm.origin_path(k)) if k in rm.ORIGINS else None),
                    "license": v[1],
                    "role": v[2],
                }
                for k, v in rm.SOURCES.items()
            },
            "layer_tags": dict(m12.LAYER_TAGS),
            "stats": {
                "total": len(route),
                "per_source": dict(counts),
                "shared_cjk_zh_hans": len(shared),
                "gaps": sorted(rm.GAPS),
            },
            "route": {f"U+{cp:04X}": s for cp, s in sorted(route.items())},
            "layer": {f"U+{cp:04X}": layers.get(cp, "?") for cp in sorted(route)},
        }
        OUT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"快照已写出: {OUT.relative_to(ROOT)}  "
              f"({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
