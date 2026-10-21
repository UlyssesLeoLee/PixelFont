"""把目视复核的结论落进字体: 换源 → 重建 → 报告改了什么。

为什么要有这个脚本:
    目视是唯一能发现**部件级塌陷**的手段 (自动判据对那类缺陷召回率只有 5/29),
    但目视结论必须有一条**可复现**的路回到生产 —— 靠人肉改名单不行,
    改完也说不清到底改了哪些字、为什么改。

回路是:
    reports/glyphcmp_review/summary.json   (目视复核产物, 已入库)
        ↓  --force-from-review
    tools/fontgen/ideo_route.json           (路由名单, 重新推导, 不手改)
        ↓  构建 (含缺字门禁 + 路由名单门禁)
    dist/                                   (产物)

用法:
    python tools/fontgen/apply_review_fixes.py            # 应用并重建
    python tools/fontgen/apply_review_fixes.py --dry-run  # 只看会改什么, 不写
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "fontgen"
ROUTE = TOOLS / "ideo_route.json"
REVIEW = ROOT / "reports" / "glyphcmp_review" / "summary.json"
PY = sys.executable


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(
        cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ap = argparse.ArgumentParser(description="把目视复核结论落进字体")
    ap.add_argument("--review", default=str(REVIEW), help="目视复核汇总 summary.json")
    ap.add_argument("--dry-run", action="store_true", help="只报告会改什么, 不写文件")
    ap.add_argument("--skip-build", action="store_true", help="只重推名单, 不重建")
    args = ap.parse_args()

    rp = Path(args.review)
    if not rp.exists():
        print(f"缺少复核产物: {rp} (先跑 aggregate_glyphcmp_review.py)", file=sys.stderr)
        return 2
    rv = json.loads(rp.read_text(encoding="utf-8"))
    n_deg = len(rv.get("degraded", []))
    n_uns = len(rv.get("unsure_list", []))
    print(f"复核产物: {rp}")
    print(f"  确认劣化 {n_deg} 个, 存疑 {n_uns} 个 (只强制处理确认劣化的)")

    before = {}
    if ROUTE.exists():
        d = json.loads(ROUTE.read_text(encoding="utf-8"))
        before = {k: v for k, v in d.get("route", {}).items()}

    out_path = ROUTE if not args.dry_run else (ROOT / "reports" / "_tmp_route_forced.json")
    rc, log = run(
        [
            PY,
            str(TOOLS / "derive_ideo_route.py"),
            "--per-char",
            "--hole-weight",
            "4",
            "--force-from-review",
            str(rp),
            "--out",
            str(out_path),
        ]
    )
    if rc != 0:
        print(log[-4000:], file=sys.stderr)
        print("重新推导失败 —— 没有改任何东西", file=sys.stderr)
        return rc

    # 报告差异
    after = json.loads(out_path.read_text(encoding="utf-8")).get("route", {})
    changed = []
    for k in sorted(set(before) | set(after)):
        b = before.get(k)
        a = after.get(k)
        bsrc = b.get("source") if isinstance(b, dict) else ("non_ideo" if b else None)
        asrc = a.get("source") if isinstance(a, dict) else ("non_ideo" if a else None)
        if bsrc != asrc:
            changed.append((k, bsrc, asrc, (a or {}).get("forced", False) if isinstance(a, dict) else False))
    print()
    print(f"路由名单: {len(before)} -> {len(after)} 个码位")
    print(f"来源发生变化的: {len(changed)} 个")
    for k, b, a, forced in changed:
        tag = " (目视强制覆盖)" if forced else ""
        print(f"  {k}: {b or 'SimHei'} -> {a or 'SimHei'}{tag}")
    if args.dry_run:
        print("\n--dry-run: 没有写名单, 也没有重建")
        if out_path.exists():
            out_path.unlink()
        return 0

    # 重建 (门禁会复核名单里的每个条目)
    print()
    rc, log = run([PY, str(TOOLS / "build_font.py")])
    if rc != 0:
        print(log[-4000:], file=sys.stderr)
        print("构建失败 —— 路由门禁拦下了 (说明名单与当前源字体不一致, 需要重新推导)", file=sys.stderr)
        return rc
    print("\n".join(log.strip().splitlines()[-10:]))

    print()
    print("改完还没完: 换源后的字需要**再目视一次**才算数。")
    print("  出定点对照图: python tools/fontgen/gen_glyphcmp_sheets.py --refs zpix,unifont-16 \\")
    print("      --chars " + ",".join("%X" % int(k[2:], 16) for k, _b, _a, _f in changed) + " \\")
    print("      --cols 4 --rows 4 --scale 6 --outdir reports/glyphcmp_review/fixed --index reports/glyphcmp_review/fixed/index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
