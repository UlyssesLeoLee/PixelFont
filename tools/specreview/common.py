"""规格文档集审核工具 · 公共定义。

审核对象:
  - SPEC_DOCS   : `docs/spec/NN-*.md` 共 12 份规格文档 (受六段章节结构约束)
  - SUPPORT_DOCS: `docs/spec/README.md` 索引 + `docs/spec/_*.md` 事实底稿 / 审核报告
                   (受白名单约束, 不强制六段章节结构)

设计原则 (与仓库既有门禁一致):
  - 只用**仓库内可追溯**的判据: 路径 / API / commit / sha256 / 码位
  - 一切"看起来合理"都不算数, 必须能落到一个可执行的检查
  - 核不实的写「待验证」+ 验证方法, 禁止编数字
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs" / "spec"

# 12 份规格文档: 文件名以两位数字开头
SPEC_DOCS = sorted(p for p in SPEC.glob("[0-9][0-9]-*.md"))
# 索引 + 下划线开头的支撑文件
SUPPORT_DOCS = sorted(
    p for p in SPEC.glob("*.md")
    if not re.match(r"^[0-9]{2}-", p.name)
)
ALL_DOCS = SPEC_DOCS + SUPPORT_DOCS

BASELINE = SPEC / "_facts-baseline.md"

REQUIRED_SECTIONS = [
    "## 结论先行",
    "## 1. 范围与目的",
    "## 2. 正文",
    "## 3. 验收判据",
    "## 4. 复现命令",
    "## 5. 已知边界与待办",
]

SHA_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")
CP_RE = re.compile(r"\bU\+([0-9A-Fa-f]{4,6})\b")


def unescaped_pipes(line: str) -> int:
    """数未转义的 `|`; GFM 里 `\\|` 是合法的单元格内竖线, 不计入列数。"""
    n = i = 0
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line):
            i += 2
            continue
        if line[i] == "|":
            n += 1
        i += 1
    return n


def report(title: str, findings: list[tuple[str, str, str]]) -> int:
    """按文档聚合打印发现, 返回条数。"""
    print("=" * 78)
    print(title)
    print("=" * 78)
    if not findings:
        print("  0 条")
    else:
        by_doc: dict[str, list[tuple[str, str]]] = {}
        for doc, kind, detail in findings:
            by_doc.setdefault(doc, []).append((kind, detail))
        for doc in sorted(by_doc):
            print(f"\n  {doc}")
            for kind, detail in sorted(set(by_doc[doc])):
                print(f"     [{kind}] {detail}")
    print(f"\n  合计 {len(findings)} 条")
    return len(findings)
