"""规格文档集索引同步器。

`docs/spec/README.md` 里的「篇幅」列和「事实底稿日期」是**快照**, 文档一改就会失配。
本工具从**实际文件**重新生成这两处, 让索引不撒谎。

用法:
    python tools/specreview/sync_index.py          # 写入
    python tools/specreview/sync_index.py --check  # 只检查, 有失配则返回 1

被同步的字段:
  - 索引表每一行的「N 行」   <- 实际行数
  - 事实底稿那一行的「N 行」
  - 顶部「事实底稿日期」    <- 底稿文件 mtime
  - 顶部「对应仓库 HEAD」   <- 当前 HEAD 短 SHA (标注会随提交推进变化)
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from common import BASELINE, SPEC

README = SPEC / "README.md"
REPO = SPEC.parents[1]

# 索引表的一行: | 01 | [`xx.md`](xx.md) | 描述 | 389 行 |
ROW_RE = re.compile(r"^(\|\s*(?:--|\d+|—)\s*\|\s*\[`([^`]+\.md)`\]\([^)]+\)\s*\|.*\|\s*)"
                    r"(\d+)\s*行(\s*\|)\s*$")


def baseline_date() -> str:
    """事实底稿的日期 —— 取**入库 commit 的日期**, 而不是工作区 mtime。

    mtime 会因为 checkout / touch 漂移, commit 日期才是事实底稿真正被固定的时刻。
    """
    r = subprocess.run(
        ["git", "-C", str(REPO), "log", "-1", "--format=%cd", "--date=short",
         "--", str(BASELINE)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    d = r.stdout.strip()
    if d:
        return d
    if BASELINE.exists():
        return datetime.fromtimestamp(BASELINE.stat().st_mtime).strftime("%Y-%m-%d")
    return ""


def line_count(p: Path) -> int:
    return len(p.read_text(encoding="utf-8").splitlines())


def sync_rows(t: str) -> str:
    out = []
    for line in t.splitlines():
        m = ROW_RE.match(line)
        if m:
            p = SPEC / m.group(2)
            if p.exists():
                line = f"{m.group(1)}{line_count(p)} 行{m.group(4)}"
        out.append(line)
    return "\n".join(out) + "\n"


def main() -> int:
    check_only = "--check" in sys.argv
    t = README.read_text(encoding="utf-8")
    orig = t

    t = sync_rows(t)

    d = baseline_date()
    if d:
        t = re.sub(r"事实底稿日期：\*\*\d{4}-\d{2}-\d{2}\*\*",
                   f"事实底稿日期：**{d}**", t)

    # 刻意**不**同步仓库 HEAD 的短 SHA: 它每次提交都会变, 钉进索引只会制造
    # 「刚提交完 --check 就失败」的假告警。索引里改成用命令查询的表述。

    if t == orig:
        print("[OK  ] 索引已是最新, 无需改动")
        return 0
    if check_only:
        print("[FAIL] 索引与实际文件不一致, 跑 sync_index.py 更新")
        return 1
    README.write_text(t, encoding="utf-8")
    print(f"[OK  ] 索引已同步: 篇幅列 / 底稿日期 {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
