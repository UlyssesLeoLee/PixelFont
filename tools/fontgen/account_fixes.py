"""lane 标记的异常里, 有多少已经被 ideo 路由修复。

lane 复核的是**修复前**的对照图, 所以它的结论要重新对一次账:
    · 落在路由名单里的 -> 已被修复 (字改用 MS Gothic 原生点阵)
    · 不在名单里的      -> 仍然存在, 属于局部塌陷或 12px 固有极限
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, "tools/fontgen")
import charset as cs

route, mode, hole_weight = cs.load_ideo_route()
route_cps = {f"U+{cp:04X}" for cp in route}
print(f"路由模式 {mode} (字腔权重 {hole_weight:g}), {len(route_cps)} 个码位")

agg = Path("reports/glyphcmp_review/summary.json")
if not agg.exists():
    print("缺少 summary.json, 先跑 aggregate_glyphcmp_review.py", file=sys.stderr)
    sys.exit(2)
d = json.loads(agg.read_text(encoding="utf-8"))

rows = []
for key in ("degraded", "unsure_list"):
    for x in d.get(key, []):
        rows.append((key, x["cp"], x.get("char", ""), x.get("confidence", "")))

SRC_NAME = {"ideo": "SimHei", "non_ideo": "MS Gothic", "fusion": "Fusion Pixel"}


def current_source(cp: str) -> str:
    """这个码位当前走哪个源。"""
    rec = route.get(int(cp[2:], 16))
    if rec is None:
        return "SimHei"
    if isinstance(rec, dict):
        return SRC_NAME.get(str(rec.get("source", "non_ideo")), str(rec.get("source")))
    return "MS Gothic"


out = []
out.append(f"消费 lane 产物: {d['inputs']['lanes_found']} 个, 复核字数 {d['inputs']['chars_reviewed']}")
out.append(f"标记总数: 确认劣化 {len(d['degraded'])} + 存疑 {len(d['unsure_list'])} = {len(rows)}")
out.append("")
out.append("注意: 这一轮目视复核是**修复之后**做的, 所以标出来的字就是**仍然有问题**的字。")
out.append("下表给出每个字当前走的源 —— 若当前源的签名明显比别的源差, 就是可修的。")
out.append("")
out.append("=== 仍然存在, 按当前源分组 ===")
by_src: dict[str, list] = {}
for key, cp, ch, conf in rows:
    by_src.setdefault(current_source(cp), []).append((key, cp, ch, conf))
for src in sorted(by_src, key=lambda s: -len(by_src[s])):
    out.append(f"--- 当前源: {src} ({len(by_src[src])} 个) ---")
    for key, cp, ch, conf in by_src[src]:
        out.append(f"  {cp} {ch}  ({'确认劣化' if key == 'degraded' else '存疑'}, 置信度 {conf})")
    out.append("")

# 这批"仍然存在"的字里, 有多少在参考字体下也画不出对应的腔 -> 固有极限
screen = json.loads(Path("reports/glyphcmp_screen.json").read_text(encoding="utf-8"))
by_cp = {x["cp"]: x for x in screen["findings"]}
out.append("=== 仍然存在的字, 现在的硬检查怎么说 ===")
for key, cp, ch, conf in rows:
    f = by_cp.get(cp)
    if f:
        out.append(f"  {cp} {ch}  -> {f['id']}/{f.get('severity','-')}  {f['detail'][:80]}")
    else:
        out.append(f"  {cp} {ch}  -> 硬检查未命中 (局部塌陷, 自动判据无能为力)")

Path("reports/glyphcmp_review/fix_accounting.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
