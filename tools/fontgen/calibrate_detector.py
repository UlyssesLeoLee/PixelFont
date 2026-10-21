"""量具自检: 自动化硬检查对目视复核标定集的召回率/误报率。

为什么要有这个工具:
    自动化硬检查 (compare_refs.py) 与目视复核 (reports/glyphcmp_review/lane*.json)
    是两个独立来源的判定。把它们对起来, 才能知道自动判据**能测到什么、测不到什么**。

    实测结论 (本工具复算):
        · EXACT_COLLIDE  —— 能测 (逐像素撞车, 性质上与目视判据无关)
        · COUNTER_LOST   —— 只能测"整字塌成白块"(我方字腔 0 而参考 > 0)
        · 局部塌陷       —— **测不到**。目视判为 DEGRADED 的「瓣」「雹」,
                           我方字腔数反而比参考**还多** (7 vs 5 / 6 vs 2),
                           任何基于腔数的阈值都抓不住它们。

    所以正确的分工是: 自动判据做**漏网之鱼的高危筛查**, 目视复核做**最终判定**。
    报告里必须写明这个检测极限, 不能让人误以为自动检查已经覆盖了全部缺陷。

用法:
    python tools/fontgen/calibrate_detector.py \
        --screen reports/glyphcmp_screen.json \
        --review reports/glyphcmp_review \
        --out reports/glyphcmp_calibration.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_labels(review_dir: Path) -> tuple[dict, dict, list[str]]:
    """读目视复核产物 -> (确认异常, 存疑, 每个 lane 复核了多少字)"""
    confirmed: dict[str, dict] = {}
    unsure: dict[str, dict] = {}
    per_lane: list[str] = []
    for p in sorted(review_dir.glob("lane*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        per_lane.append(f"{p.stem}: {d.get('chars_reviewed', 0)} 字")
        for f in d.get("findings", []):
            confirmed[f["cp"]] = {**f, "lane": p.stem}
        for f in d.get("unsure", []):
            unsure[f["cp"]] = {**f, "lane": p.stem}
    return confirmed, unsure, per_lane


def main() -> int:
    ap = argparse.ArgumentParser(description="自动化硬检查 vs 目视复核的交叉标定")
    ap.add_argument("--screen", default="reports/glyphcmp_screen.json", help="compare_refs.py 的 screen 输出")
    ap.add_argument("--review", default="reports/glyphcmp_review", help="目视复核产物目录")
    ap.add_argument("--out", default="", help="标定结果 JSON 输出路径")
    args = ap.parse_args()

    sp = Path(args.screen)
    if not sp.exists():
        print(f"缺少 screen 结果: {sp} (先跑 compare_refs.py --screen-only)", file=sys.stderr)
        return 2
    screen = json.loads(sp.read_text(encoding="utf-8"))
    rd = Path(args.review)
    if not rd.exists():
        print(f"缺少目视复核目录: {rd}", file=sys.stderr)
        return 2

    confirmed, unsure, per_lane = load_labels(rd)
    auto = {x["cp"]: x for x in screen["findings"]}

    reviewed = 0
    for p in sorted(rd.glob("lane*.json")):
        reviewed += json.loads(p.read_text(encoding="utf-8")).get("chars_reviewed", 0)

    def hit(cp: str) -> list[str]:
        f = auto.get(cp)
        return [f["id"]] if f else []

    rows_conf = []
    for cp, v in sorted(confirmed.items()):
        ids = hit(cp)
        rows_conf.append({"cp": cp, "char": v.get("char", ""), "auto": ids, "caught": bool(ids)})
    rows_uns = []
    for cp, v in sorted(unsure.items()):
        ids = hit(cp)
        rows_uns.append({"cp": cp, "char": v.get("char", ""), "auto": ids, "caught": bool(ids)})

    caught = sum(1 for r in rows_conf if r["caught"])
    caught_u = sum(1 for r in rows_uns if r["caught"])

    # 假阳性: 自动报了但目视没标的 (目视只覆盖了一部分区间, 这里只能算"落在复核区间内却没被标")
    auto_cps = set(auto)
    label_cps = set(confirmed) | set(unsure)
    in_scope = auto_cps & label_cps
    fp = sorted(c for c in in_scope if c not in label_cps)

    out = {
        "tool": "calibrate_detector",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "screen_json": str(sp),
            "review_dir": str(rd),
            "lanes": per_lane,
            "chars_reviewed": reviewed,
            "screen_findings": len(screen["findings"]),
        },
        "recall": {
            "confirmed_degraded": {
                "total": len(rows_conf),
                "caught": caught,
                "missed": len(rows_conf) - caught,
                "missed_list": [r["cp"] for r in rows_conf if not r["caught"]],
            },
            "unsure": {
                "total": len(rows_uns),
                "caught": caught_u,
                "missed": len(rows_uns) - caught_u,
            },
        },
        "by_check": {},
        "rows": {"confirmed": rows_conf, "unsure": rows_uns},
        "unlabelled_auto_findings": fp,
        "limitations": [
            "自动判据对'整字塌成白块'可靠 (COUNTER_LOST: 我方字腔 0 而参考 > 0)",
            "自动判据对'局部塌陷'不可靠 —— 目视判 DEGRADED 的「瓣」「雹」我方腔数反比参考多",
            "腔数/方块类指标与分辨率强相关, 只能做候选排序, 不能直接下判定",
            "最终判定仍以目视复核为准; 自动检查的职责是筛出高危, 不是替代目视",
        ],
    }

    for r in rows_conf + rows_uns:
        for i in r["auto"]:
            b = out["by_check"].setdefault(i, {"confirmed": 0, "unsure": 0})
            b["confirmed" if r in rows_conf else "unsure"] += 1

    js = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(js, encoding="utf-8")
        print(f"标定结果: {op}")
    else:
        print(js)
    print(
        f"\n召回率: 确认 DEGRADED {caught}/{len(rows_conf)}  存疑 {caught_u}/{len(rows_uns)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
