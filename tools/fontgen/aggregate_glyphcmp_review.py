"""汇总目视复核 lane 的结论 —— 出一张总表 + 汇总数字。

为什么要单独一个汇总器:
    4 条 lane 各写各的 md/json。人要看"到底有多少身份错误"时, 得自己翻 4 个文件。
    汇总器必须**报出消费了多少输入** —— 没读到 lane 产物不能显示成 0 错误。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser(description="汇总字形目视复核结论")
    ap.add_argument("--review", default="reports/glyphcmp_review", help="lane 产物目录")
    ap.add_argument("--out", default="reports/glyphcmp_review/summary.json", help="汇总输出")
    ap.add_argument("--md", default="", help="汇总 markdown 输出")
    args = ap.parse_args()

    rd = Path(args.review)
    files = sorted(rd.glob("lane*.json"))
    if not files:
        print(f"没有 lane 产物: {rd} —— 不能汇总成 0 错误 (没测到 ≠ 没问题)", file=sys.stderr)
        return 2

    lanes = []
    findings = []
    unsure = []
    total_chars = 0
    for p in files:
        d = json.loads(p.read_text(encoding="utf-8"))
        n = d.get("chars_reviewed", 0)
        total_chars += n
        f = d.get("findings", [])
        u = d.get("unsure", [])
        lanes.append(
            {
                "lane": d.get("lane", p.stem),
                "file": p.name,
                "chars_reviewed": n,
                "sheets": d.get("sheets", []),
                "confirmed": len(f),
                "unsure": len(u),
                "identity": d.get("summary", {}).get("identity", 0),
            }
        )
        for x in f:
            findings.append({**x, "lane": d.get("lane", p.stem)})
        for x in u:
            unsure.append({**x, "lane": d.get("lane", p.stem)})

    identity = [x for x in findings + unsure if x.get("kind") == "IDENTITY"]
    degraded = [x for x in findings if x.get("kind") == "DEGRADED"]

    out = {
        "tool": "aggregate_glyphcmp_review",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "review_dir": str(rd),
            "lane_files": [p.name for p in files],
            "lanes_found": len(lanes),
            "chars_reviewed": total_chars,
        },
        "summary": {
            "identity_errors": len(identity),
            "degraded_confirmed": len(degraded),
            "unsure": len(unsure),
        },
        "lanes": lanes,
        "identity_findings": identity,
        "degraded": sorted(degraded, key=lambda x: x["cp"]),
        "unsure_list": sorted(unsure, key=lambda x: x["cp"]),
    }
    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"汇总: {op}")
    print(f"  消费 lane 产物 {len(lanes)} 个, 复核字数合计 {total_chars}")
    for l in lanes:
        print(
            f"    lane{l['lane']}: {l['chars_reviewed']} 字  身份错误 {l['identity']}  "
            f"确认劣化 {l['confirmed']}  存疑 {l['unsure']}"
        )
    print(f"  合计: 身份错误 {len(identity)}  确认劣化 {len(degraded)}  存疑 {len(unsure)}")

    if args.md:
        L = [
            "# 字形目视复核 · 汇总",
            "",
            f"- 生成时间: {out['generated_at']}",
            f"- 消费 lane 产物: {len(lanes)} 个 (共 {total_chars} 字)",
            "",
            "| lane | 复核字数 | 身份错误 | 确认劣化 | 存疑 |",
            "|---|---|---|---|---|",
        ]
        for l in lanes:
            L.append(
                f"| lane{l['lane']} | {l['chars_reviewed']} | {l['identity']} | {l['confirmed']} | {l['unsure']} |"
            )
        L += [
            f"| **合计** | **{total_chars}** | **{len(identity)}** | **{len(degraded)}** | **{len(unsure)}** |",
            "",
        ]
        if identity:
            L += ["## 身份错误（画的不是这个字）", ""]
            for x in identity:
                L.append(f"- `{x['cp']}` {x.get('char','')} — {x.get('reason','')}")
            L.append("")
        if degraded:
            L += ["## 确认结构劣化", "", "| 码位 | 字符 | 理由 | 置信度 |", "|---|---|---|---|"]
            for x in degraded:
                L.append(
                    f"| `{x['cp']}` | {x.get('char','')} | {x.get('reason','')} | {x.get('confidence','')} |"
                )
            L.append("")
        if unsure:
            L += ["## 存疑", "", "| 码位 | 字符 | 理由 | 置信度 |", "|---|---|---|---|"]
            for x in unsure:
                L.append(
                    f"| `{x['cp']}` | {x.get('char','')} | {x.get('reason','')} | {x.get('confidence','')} |"
                )
            L.append("")
        Path(args.md).write_text("\n".join(L) + "\n", encoding="utf-8")
        print(f"  markdown: {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
