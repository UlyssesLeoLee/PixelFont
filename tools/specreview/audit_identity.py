"""对抗式审核 · R1 身份反查。

不看文档「说了什么」, 直接问仓库「有没有这个东西」:
  - 文档引用的仓库路径是否真实存在
  - 文档引用的 API (module.func / Class.method) 是否真的存在
  - 文档引用的 commit / tag 是否真实存在

判据来源: 仓库自身的文件树与 git 对象库, 不引入外部量具。
"""
from __future__ import annotations

import re
import subprocess
import sys

from common import ALL_DOCS, REPO, report

# 文档里常见的路径写法 -> 仓库实际路径
PATH_RE = re.compile(
    r"`((?:tools|docs|reports|vendor|dist|third_party)/[A-Za-z0-9_./-]+"
    r"(?:\.(?:py|md|json|txt|ttf|png|bdf|map|yaml|yml))?)`"
)
API_RE = re.compile(r"`?([a-z_]+)\.([A-Za-z_][A-Za-z0-9_]*)\(\)`?")
CLASS_API_RE = re.compile(r"`([A-Z][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\(\)`?")

MODMAP = {
    "charset": "tools/fontgen/charset.py",
    "bitfont": "tools/fontgen/bitfont.py",
    "build_font": "tools/fontgen/build_font.py",
    "verify_all": "tools/fontgen/verify_all.py",
    "verify_gdi": "tools/fontgen/verify_gdi.py",
    "verify_identity": "tools/fontgen/verify_identity.py",
    "verify_products": "tools/fontgen/verify_products.py",
    "verify_bitmap": "tools/fontgen/verify_bitmap.py",
    "regress": "tools/fontgen/regress.py",
    "regress_all": "tools/fontgen/regress_all.py",
    "compare_refs": "tools/fontgen/compare_refs.py",
    "derive_ideo_route": "tools/fontgen/derive_ideo_route.py",
    "route_rule": "tools/fontgen/route_rule.py",
    "vendor_fusion_pixel": "tools/fontgen/vendor_fusion_pixel.py",
    "coverage": "tools/fontgen/coverage.py",
    "fetch_ref_fonts": "tools/fontgen/fetch_ref_fonts.py",
    "charset_multi12": "tools/fontgen/charset_multi12.py",
    "adversarial_review": "tools/fontgen/adversarial_review.py",
    "apply_review_fixes": "tools/fontgen/apply_review_fixes.py",
    "account_fixes": "tools/fontgen/account_fixes.py",
    "calibrate_detector": "tools/fontgen/calibrate_detector.py",
    "aggregate_glyphcmp_review": "tools/fontgen/aggregate_glyphcmp_review.py",
    "make_demo": "tools/fontgen/make_demo.py",
    "sheet": "tools/fontgen/sheet.py",
    "gen_sheets": "tools/fontgen/gen_sheets.py",
    "gen_glyphcmp_sheets": "tools/fontgen/gen_glyphcmp_sheets.py",
    "explain_route": "tools/fontgen/explain_route.py",
}


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()


# 入库目录: 引用它们等于承诺「读者 clone 下来就有这个文件」
TRACKED_PREFIXES = ("tools/", "docs/", "reports/", "vendor/")
# 不入库目录: 构建产物 / 只用于校验的第三方参考字体
UNTRACKED_PREFIXES = ("dist/", "third_party/")


def tracked(rel: str) -> bool:
    """是否**在版本库里** —— 用 git ls-files 而不是文件系统存在性。

    文件系统存在性会把「本机恰好构建过」误判成「仓库里有」;
    仓库政策是 dist/ 不入库, 所以这一条必须是入库性检查。
    """
    r = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", rel],
                       capture_output=True)
    return r.returncode == 0


def path_ok(rel: str) -> tuple[bool, str]:
    """返回 (是否通过, 说明)。"""
    if rel.startswith(TRACKED_PREFIXES):
        if tracked(rel):
            return True, ""
        if (REPO / rel).exists():
            return False, f"{rel} (存在于工作区但未入库)"
        return False, f"{rel} (仓库里没有这个文件)"
    if rel.startswith(UNTRACKED_PREFIXES):
        if (REPO / rel).exists():
            return True, ""
        return True, f"{rel} (构建产物/第三方, 按仓库政策不入库, 本地未构建)"  # 记为说明, 不算缺陷
    if (REPO / rel).exists():
        return True, ""
    return False, rel


def commit_exists(sha: str) -> bool:
    """git cat-file -e 成功时**没有任何输出**, 必须看返回码而不是 stdout。"""
    return subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-e", sha + "^{commit}"],
        capture_output=True,
    ).returncode == 0


def main() -> int:
    findings: list[tuple[str, str, str]] = []

    src: dict[str, str] = {}
    for mod, rel in MODMAP.items():
        p = REPO / rel
        src[mod] = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    all_src = "\n".join(src.values())

    for doc in ALL_DOCS:
        t = doc.read_text(encoding="utf-8")
        name = doc.name

        # --- R1a: 仓库路径存在性 ---
        for p in sorted(set(PATH_RE.findall(t))):
            p = p.rstrip(".,;)")
            ok, detail = path_ok(p)
            if not ok:
                findings.append((name, "路径不存在", detail))

        # --- R1b: API 存在性 ---
        for mod, fn in set(API_RE.findall(t)):
            if mod not in MODMAP or not src[mod]:
                continue
            if f"def {fn}(" not in src[mod] and f"class {fn}" not in src[mod]:
                findings.append((name, "API 不存在", f"{mod}.{fn}()"))
        for cls, meth in set(CLASS_API_RE.findall(t)):
            if f"class {cls}" not in all_src:
                findings.append((name, "类不存在", cls))
            elif f"def {meth}(" not in all_src:
                findings.append((name, "方法不存在", f"{cls}.{meth}()"))

        # --- R1c: commit / tag 存在性 ---
        for sha in set(re.findall(r"`([0-9a-f]{7,40})`", t)):
            if not commit_exists(sha):
                findings.append((name, "commit 不存在", sha))
        for tag in set(re.findall(r"`(v\d+\.\d+\.\d+)`", t)):
            if not git("tag", "-l", tag):
                findings.append((name, "tag 不存在", tag))

    n = report("R1 身份反查: 文档引用 vs 仓库实况", findings)
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
