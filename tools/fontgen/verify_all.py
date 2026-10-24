"""一条命令复核全部结论 —— 生产源自检 → 构建 → 回归 → 硬检查 → 名单自检 → 对抗审核 → Windows 兼容。

为什么要有这个:
    现在这些结论分散在几个脚本里 (vendor_fusion_pixel / build_font / regress_all /
    compare_refs / derive_ideo_route --check / adversarial_review / verify_gdi),
    每次要复核一遍就得记住跑哪个、顺序是什么、参数怎么写 —— 少跑一个, 结论就少一块,
    而且**少跑的那块没人会发现**。

    这个脚本把链路串起来, 并且**每一步都报出它实际消费了什么**:
    跑失败就明确说哪一步失败, 跑成功就把关键数字打出来。

用法:
    python tools/fontgen/verify_all.py
    python tools/fontgen/verify_all.py --skip-vendor   # 跳过生产源自检 (省时间)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
TOOLS = ROOT / "tools" / "fontgen"

STEPS: list[tuple[str, list[str], str]] = [
    (
        "生产源自检 (Fusion Pixel 裁剪版: 逐像素一致 + cmap 覆盖)",
        [str(TOOLS / "vendor_fusion_pixel.py"), "--check"],
        "生产源",
    ),
    (
        "构建 (含缺字门禁 + 路由名单门禁)",
        [str(TOOLS / "build_font.py")],
        "构建",
    ),
    (
        "全量回归 (4161 字分批: 产物与源位图逐像素一致)",
        [str(TOOLS / "regress_all.py")],
        "回归",
    ),
    (
        "字形硬检查 (参考集 Zpix + Unifont, 与生产源独立)",
        [
            str(TOOLS / "compare_refs.py"),
            "--screen-only",
            "--refs",
            "zpix,unifont-16",
            "--json",
            "reports/glyphcmp_screen.json",
        ],
        "硬检查",
    ),
    (
        "产物与源同步 (独立读 dist/ 与当前源逐字比对, 不靠构建脚本自证)",
        [str(TOOLS / "verify_products.py")],
        "产物同步",
    ),
    (
        "路由名单自检 (按名单自述的输入重新推导, 与入库名单比对)",
        [
            str(TOOLS / "derive_ideo_route.py"),
            "--per-char",
            "--hole-weight",
            "4",
            "--check",
        ],
        "名单",
    ),
    (
        "对抗式审核 (三轮: 身份反查 / 部件级结构 / 链条; 阈值按对照集标定)",
        [str(TOOLS / "adversarial_review.py")],
        "对抗审核",
    ),
    (
        "Windows 兼容性 (GDI 字体选择 + 栅格化逐像素比对, 非 Windows 自动跳过)",
        [str(TOOLS / "verify_gdi.py")],
        "Windows兼容",
    ),
]


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(
        [PY, *cmd], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ap = argparse.ArgumentParser(description="一条命令复核全部结论")
    ap.add_argument("--skip-vendor", action="store_true", help="跳过生产源自检 (慢)")
    args = ap.parse_args()

    results: list[dict] = []
    failed = 0
    for i, (label, cmd, tag) in enumerate(STEPS, 1):
        if args.skip_vendor and tag == "生产源":
            print(f"== {i}/{len(STEPS)} {label} —— 跳过")
            results.append({"step": tag, "label": label, "status": "SKIPPED"})
            continue
        if tag == "名单":
            # 名单自述了它是用什么输入推出来的 (可能含目视复核驱动的强制覆盖),
            # 自检必须用**同一份输入**重推, 否则会误报"名单与推导结果不一致"。
            rp = ROOT / "tools" / "fontgen" / "ideo_route.json"
            if rp.exists():
                rd = json.loads(rp.read_text(encoding="utf-8"))
                fr = (rd.get("inputs") or {}).get("force_from_review")
                if fr:
                    cmd = cmd + ["--force-from-review", fr]
                    print(f"   (按名单自述的输入补上 --force-from-review {fr})")
        print(f"== {i}/{len(STEPS)} {label} ==")
        rc, out = run(cmd)
        tail = "\n".join(out.strip().splitlines()[-14:])
        if tail:
            print(tail)
        ok = rc == 0
        if not ok:
            failed += 1
        results.append(
            {"step": tag, "label": label, "status": "PASS" if ok else "FAIL", "returncode": rc}
        )
        print(f"   -> {'PASS' if ok else 'FAIL'} (exit {rc})\n")

    # ---- 关键数字 ----
    numbers: dict[str, object] = {}
    rp = ROOT / "reports" / "all_batches.json"
    if rp.exists():
        d = json.loads(rp.read_text(encoding="utf-8"))
        numbers["回归"] = {
            "覆盖字数": d["inputs"]["chars_checked"],
            "批数": d["inputs"]["batches"],
            "error": d["summary"]["errors"],
            "warn": d["summary"]["warnings"],
            "判定": d["summary"]["verdict"],
        }
    sp = ROOT / "reports" / "glyphcmp_screen.json"
    if sp.exists():
        d = json.loads(sp.read_text(encoding="utf-8"))
        numbers["硬检查"] = {
            "参考集": list(d["inputs"]["refs"].keys()),
            "命中": d["summary"]["findings"],
            "按判据": d["summary"]["by_id"],
            "按级别": d["summary"]["by_severity"],
        }
    ap_ = ROOT / "reports" / "glyphcmp_review" / "summary.json"
    if ap_.exists():
        d = json.loads(ap_.read_text(encoding="utf-8"))
        numbers["目视复核"] = {
            "消费 lane 产物": d["inputs"]["lanes_found"],
            "复核字数": d["inputs"]["chars_reviewed"],
            "身份错误": d["summary"]["identity_errors"],
            "确认劣化": d["summary"]["degraded_confirmed"],
            "存疑": d["summary"]["unsure"],
        }
    ad_ = ROOT / "reports" / "adversarial" / "summary.json"
    if ad_.exists():
        d = json.loads(ad_.read_text(encoding="utf-8"))
        numbers["对抗审核"] = {
            "三轮": {k: v["findings"] for k, v in d["rounds"].items()},
            "待裁决": d["verdict"].get("flagged_open", 0),
            "已裁决非缺陷": d["verdict"].get("adjudicated_not_defect", 0),
            "确认缺陷": d["verdict"].get("defect", 0),
        }
    gd_ = ROOT / "reports" / "gdi_compat.json"
    if gd_.exists():
        d = json.loads(gd_.read_text(encoding="utf-8"))
        rs = d.get("raster_summary", {})
        numbers["Windows兼容"] = {
            "判定": d.get("verdict"),
            "charset选择": {
                str(k): (v.get("picked") if v.get("ok") else f"未选中本字体({v.get('picked')})")
                for k, v in d.get("selection", {}).items()
            },
            "全字符集栅格化": {
                "扫描码位": rs.get("scanned"),
                "12ppem逐格一致": rs.get("shape_match_12"),
                "24ppem逐格一致": rs.get("shape_match_24"),
                "抗锯齿像素": rs.get("aa_pixels_default_total"),
            },
        }

    print("=" * 60)
    print("复核结果")
    print("=" * 60)
    for r in results:
        print(f"  {r['status']:<8} {r['label']}")
    print()
    for k, v in numbers.items():
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)}")
    verdict = "PASS" if failed == 0 else "FAIL"
    print()
    print(f"总体判定: {verdict}" + ("" if failed == 0 else f" ({failed} 步失败)"))

    outp = ROOT / "reports" / "verify_all.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(
        json.dumps(
            {"steps": results, "numbers": numbers, "verdict": verdict},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"报告: {outp}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
