"""对抗式审核 · R2 部件级结构。

不看内容对不对, 只看**结构能不能立住**:
  - 表格列数一致 (只数未转义的 `|`)
  - 文档内 §x.y 引用能解析到真实章节
  - 「事实底稿 §N」能解析到仓库内底稿的真实章节
  - 相对链接目标真实存在
  - 不含机器本地路径 (不可随仓库流转的绝对路径)

修掉 v1 误报的两处:
  - 表格列数只数**未转义**的 `|` (GFM 里 `\\|` 是合法的单元格内竖线)
  - 外部文件的章节号 (§7.x 属于 word-compat.md, §13.x 属于底稿) 不当成本文引用
"""
from __future__ import annotations

import re
import sys

from common import ALL_DOCS, BASELINE, SPEC, report

# 外部文档的顶级章节号 —— 这些 §N 引用不指向本文
EXTERNAL_TOP = {"7", "13"}


def baseline_sections() -> set[str]:
    if not BASELINE.exists():
        return set()
    bt = BASELINE.read_text(encoding="utf-8")
    secs: set[str] = set()
    for m in re.finditer(r"^#{1,4}\s+([0-9]+(?:\.[0-9]+)*)", bt, re.M):
        secs.add(m.group(1))
    return secs


def main() -> int:
    findings: list[tuple[str, str, str]] = []
    base_secs = baseline_sections()
    has_base = BASELINE.exists()

    for doc in ALL_DOCS:
        t = doc.read_text(encoding="utf-8")
        name = doc.name
        lines = t.splitlines()

        # ---- 表格列数 ----
        i = 0
        while i < len(lines):
            if (lines[i].strip().startswith("|") and i + 1 < len(lines)
                    and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1])):
                from common import unescaped_pipes
                ncol = unescaped_pipes(lines[i])
                j = i + 2
                while j < len(lines) and lines[j].strip().startswith("|"):
                    got = unescaped_pipes(lines[j])
                    if got != ncol:
                        findings.append((
                            name, "表格列数不一致(竖线未转义)",
                            f"行{j + 1}: {got} vs 表头 {ncol} :: {lines[j][:110]}"))
                    j += 1
                i = j
            else:
                i += 1

        # ---- 底稿章节引用 ----
        for m in re.finditer(r"(?:事实底稿|底稿)[^§\n]{0,12}§\s*([0-9]+(?:\.[0-9]+)*)", t):
            ref = m.group(1)
            if not has_base:
                findings.append((name, "底稿文件不在仓库", "_facts-baseline.md 缺失"))
            elif ref not in base_secs:
                findings.append((name, "底稿章节不解析", f"§{ref}"))

        # ---- 机器本地路径 ----
        for m in re.finditer(r"[A-Za-z]:\\+Users\\+[^`\n|）)]*", t):
            findings.append((name, "文档含机器本地路径", m.group(0)))

        # ---- 本文 §x.y 引用 ----
        secs: set[str] = set()
        for m in re.finditer(r"^#{2,4}\s+([0-9]+(?:\.[0-9]+)*)\s", t, re.M):
            secs.add(m.group(1))
        for m in re.finditer(r"^#{2,4}\s+([0-9]+)\s*[.、]", t, re.M):
            secs.add(m.group(1))

        for ref in sorted(set(re.findall(r"本文\s*§\s*([0-9]+(?:\.[0-9]+)*)", t))):
            if ref not in secs:
                findings.append((name, "本文 §引用不解析", f"§{ref}"))
        for ref in sorted(set(re.findall(r"(?<![\d.§(])§\s*([0-9]+\.[0-9]+)(?![0-9])", t))):
            if ref.split(".")[0] in EXTERNAL_TOP:
                continue
            if ref not in secs:
                findings.append((name, "§引用不解析", f"§{ref}"))

        # ---- 相对链接目标 ----
        for link in sorted(set(re.findall(r"\]\((?!https?://)([^)#]+)", t))):
            if not (SPEC / link).resolve().exists():
                findings.append((name, "链接目标不存在", link))

    n = report("R2 部件级: 结构性问题", findings)
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
