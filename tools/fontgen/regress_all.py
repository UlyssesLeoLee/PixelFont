"""全量回归聚合器 —— 一次跑完所有批次, 出一份全局判定。

与 regress.py 的分工:
    regress.py    跑**一个**批次, 出一份该批次的报告 (lane 用它)
    regress_all.py 把所有批次跑一遍, 出一份全局报告 (集成用)

聚合器额外做两件事:
    1. 合并各批次结果时按**异常 ID** 汇总, 而不是简单拼接 —— 同一个系统性缺陷
       在 42 个批次里出现 42 次, 汇总后应当看成"一个缺陷影响 42 个批次"。
    2. 判定防谎: 任一批次没测到东西 (输入为空/构建失败), 全局判定就不是 PASS。
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import build_font as bf  # noqa: E402
import charset as cs  # noqa: E402
import regress as rg  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# 全量分批方案: (label, 类别, 切片)
BATCHES = [
    ("ascii-punct", ["ascii", "punct"], None),
    ("kana", ["kana"], None),
    ("hanzi-a", ["hanzi"], (0, 1900)),
    ("hanzi-b", ["hanzi"], (1900, 3755)),
]


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports" / "all_batches.json"

    print("== 1/3 构建 ==")
    rc, log = rg.run_build(ROOT)
    if rc != 0:
        print(log[-3000:], file=sys.stderr)
        print("构建失败 —— 全局判定 BUILD_FAILED", file=sys.stderr)
        return 2
    print("构建 OK")

    items = cs.build_charset()
    stack = cs.build_stack()
    ref = rg.collect_reference(items, stack)
    art = rg.Artifacts(ROOT / "dist")

    all_anoms: list[dict] = []
    sections: list[dict] = []
    no_data: list[str] = []

    for label, cats, sl in BATCHES:
        print(f"== 2/3 批次 {label} ==")
        sel = [(ch, cat) for ch, cat in items if cat in cats]
        if sl:
            sel = sel[sl[0] : sl[1]]
        if not sel:
            no_data.append(label)
            continue
        batches = [sel[i : i + 100] for i in range(0, len(sel), 100)]
        bag, extra = rg.run_checks(art, stack, items, sel, batches, ref)
        a = [x.to_dict() for x in bag.items]
        all_anoms.extend(a)
        sections.append(
            {
                "label": label,
                "cats": cats,
                "slice": list(sl) if sl else None,
                "chars_checked": len(sel),
                "batches": len(batches),
                "errors": bag.count(rg.ERROR),
                "warnings": bag.count(rg.WARN),
                "infos": bag.count(rg.INFO),
                "anomaly_ids": dict(Counter(x["id"] for x in a)),
                "batch_stats": extra.get("batch_stats", []),
            }
        )
        print(
            f"   {label}: {len(sel)} 字 / {len(batches)} 批  "
            f"error={bag.count(rg.ERROR)} warn={bag.count(rg.WARN)} info={bag.count(rg.INFO)}"
        )

    print("== 3/3 汇总 ==")
    by_id: dict[str, list[dict]] = defaultdict(list)
    for a in all_anoms:
        by_id[a["id"]].append(a)

    errors = sum(1 for a in all_anoms if a["severity"] == rg.ERROR)
    warns = sum(1 for a in all_anoms if a["severity"] == rg.WARN)
    infos = sum(1 for a in all_anoms if a["severity"] == rg.INFO)
    checked = sum(s["chars_checked"] for s in sections)

    if no_data or not sections or checked == 0:
        verdict = "NO_DATA"
    else:
        verdict = "FAIL" if errors else "PASS"

    report = {
        "tool": "regress_all",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection": {"label": "all-batches", "cats": ["<all>"], "batch_size": 100},
        "inputs": {
            "charset_total": len(items),
            "chars_checked": checked,
            "batches": sum(s["batches"] for s in sections),
            "sections": len(sections),
            "no_data_sections": no_data,
        },
        "reference": ref,
        "sections": sections,
        "anomalies": all_anoms,
        "anomaly_by_id": {k: len(v) for k, v in sorted(by_id.items())},
        "summary": {"errors": errors, "warnings": warns, "infos": infos, "verdict": verdict},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    L = [
        "# 全量回归汇总 — PixelFont",
        "",
        f"- 生成时间: {report['generated_at']}",
        f"- 判定: **{verdict}** (error {errors} / warn {warns} / info {infos})",
        f"- 覆盖: {checked} 字 / {report['inputs']['batches']} 批 / {len(sections)} 个批次",
        f"- 字符集总量: {report['inputs']['charset_total']} 字",
        "",
        "## 分批次",
        "",
        "| 批次 | 类别 | 字数 | 批数 | error | warn | info |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in sections:
        L.append(
            f"| {s['label']} | {','.join(s['cats'])} | {s['chars_checked']} | {s['batches']} | "
            f"{s['errors']} | {s['warnings']} | {s['infos']} |"
        )
    L += ["", "## 异常汇总 (按 ID)", "", "| 异常 ID | 次数 | 级别 |", "|---|---|---|"]
    for aid, items_ in sorted(by_id.items(), key=lambda kv: -len(kv[1])):
        L.append(f"| `{aid}` | {len(items_)} | {items_[0]['severity']} |")
    if not by_id:
        L.append("| (无) | 0 | - |")
    L.append("")
    out.with_suffix(".md").write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"判定={verdict}  error={errors} warn={warns} info={infos}")
    print(f"报告: {out}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
