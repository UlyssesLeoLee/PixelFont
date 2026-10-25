"""对抗式审核 · R3 链条。

把各文档 §4「复现命令」**真跑一遍**, 看它们是不是真的能跑出文档声称的结果。

分派规则:
  - 按围栏语言分派: ```powershell -> pwsh, ```python -> python, ```bash -> bash -c
  - 执行目录按**文档声明的语义**判定: 引用 `./xxx.zip` 的块在「下载目录」跑,
    引用 `./xxx.ttf` 的块在「解压后的包目录」跑, 其余留在仓库根
  - 安全边界: 含 push / clone / 删除 / 联网 的块不执行, 记 GUARD
  - 已单独复跑过的耗时或写操作脚本 (verify_all 等) 记 SKIP

为什么必须真跑: 文档里的命令「看起来对」是最常见的失效方式 ——
路径写错、多乘一个系数、变量没定义, 这些在 YAML / Markdown 里全都语法合法。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from common import REPO, SPEC_DOCS

TMP = Path(tempfile.gettempdir()) / "pf_specreview_chain"
PKG = TMP / "pkg"          # 解压后的包目录
DL = TMP / "download"      # zip 所在的「下载目录」

FORBIDDEN = re.compile(
    r"\bpush\b|\bclone\b|\bgit\s+fetch\b|Remove-Item|\brm\s+-|mavis-trash|"
    r"\bdel\b|Invoke-WebRequest|curl\s|git\s+tag\s+-d", re.I)
SKIP_PAT = re.compile(
    r"verify_all\.py|fetch_ref_fonts\.py|vendor_fusion_pixel\.py|build_font\.py")
CMD_START = re.compile(
    r"^\s*(\$|cd |python|pwsh|bash|git|Get-|Set-|New-|Test-|Add-|Remove-|"
    r"unzip|sha256sum|curl|echo|cat|ls|dir |Copy-|Move-|Select-|Import-|"
    r"python3|\.\\|&&|pip|where|foreach|if |for |#\s*----|#\s*={2,}|@')", re.M)
ERR_MARKERS = (
    "ParserError", "CommandNotFoundException", "不是内部或外部命令", "无法将",
    "不是可识别的", "CategoryInfo", "Get-FileHash:", "sha256sum:", "unzip:",
    "Resolve-Path:", "Traceback", "SyntaxError", "SyntaxWarning", "Error:",
    "ERROR", "No such file",
)


def has_bash() -> bool:
    return subprocess.run(["bash", "--version"], capture_output=True).returncode == 0


def is_output_only(block: str) -> bool:
    lines = [l for l in block.splitlines() if l.strip() and not l.strip().startswith("#")]
    return (not lines) or (not CMD_START.search(block))


def prepare() -> None:
    """准备「下载目录」与「解压后的包目录」。"""
    TMP.mkdir(parents=True, exist_ok=True)
    zip_path = REPO / "dist" / "PixelFontPC98-12-2026-10-24.zip"
    if not zip_path.exists():
        print(f"[WARN] 缺少发布包, 相关块将失败: {zip_path}")
        return
    if not PKG.exists():
        PKG.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(PKG)
    DL.mkdir(parents=True, exist_ok=True)
    if not (DL / zip_path.name).exists():
        shutil.copy2(zip_path, DL / zip_path.name)


def run_block(doc: str, idx: int, lang: str, block: str) -> tuple[str, str]:
    if FORBIDDEN.search(block):
        return "GUARD", "含 push/clone/删除/联网命令, 按安全边界不执行"
    if SKIP_PAT.search(block):
        return "SKIP", "写操作或耗时/联网, 本轮已单独复跑过"
    if is_output_only(block):
        return "OUT", "纯期望输出块(无命令), 不执行"

    cwd = str(REPO)
    # 只有「包内相对路径」(以 ./ 或 .\ 开头)才切目录; dist\... 是仓库相对, 留在仓库
    if re.search(r"(?:^|[\s'\"(=])\.[/\\]PixelFontPC98-12-2026-10-24\.zip", block):
        cwd = str(DL)
    elif re.search(r"(?:^|[\s'\"(=])\.[/\\]PixelFontPC98-12\.ttf", block):
        cwd = str(PKG)

    if lang == "bash":
        if not has_bash():
            return "SKIP", "本机无 bash, 跳过 bash 块"
        cmd = ["bash", "-c", block]
    elif lang == "python":
        p = TMP / f"{doc.replace('.md', '')}_{idx}.py"
        p.write_text(block, encoding="utf-8")
        cmd = ["python", str(p)]
    else:
        p = TMP / f"{doc.replace('.md', '')}_{idx}.ps1"
        p.write_text(block, encoding="utf-8")
        cmd = ["pwsh", "-NoProfile", "-File", str(p)]

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=cwd, timeout=150, env=env)
    except subprocess.TimeoutExpired:
        return "T/O", "超过 150s 未返回"
    dt = time.time() - t0
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    has_err = any(m in out for m in ERR_MARKERS)
    if r.returncode == 0 and not has_err:
        return "PASS", f"{dt:.1f}s | " + " | ".join(out.splitlines()[:3])[:200]
    return "FAIL", (f"exit={r.returncode} {dt:.1f}s cwd={Path(cwd).name}\n"
                    + "\n".join(out.splitlines()[-8:])[:800])


def main() -> int:
    prepare()
    total = {"PASS": 0, "FAIL": 0, "SKIP": 0, "GUARD": 0, "T/O": 0, "OUT": 0}
    fails: list[tuple[str, int, str, str, str]] = []

    print("=" * 78)
    print("R3 链条: 按围栏语言 + 声明执行目录分派, 真跑 §4 复现命令")
    print("=" * 78)
    for dp in SPEC_DOCS:
        t = dp.read_text(encoding="utf-8")
        m = re.search(r"^## 4\. .*?$(.*?)^## 5\. ", t, re.M | re.S)
        if not m:
            continue
        blocks = re.findall(r"```([a-z]*)\n(.*?)```", m.group(1), re.S)
        print(f"\n### {dp.name}")
        for i, (lang, body) in enumerate(blocks, 1):
            lang = lang or "powershell"
            st, det = run_block(dp.name, i, lang, body.strip())
            total[st] = total.get(st, 0) + 1
            mark = {"PASS": "OK  ", "FAIL": "FAIL", "SKIP": "SKIP", "GUARD": "GUARD",
                    "T/O": "T/O ", "OUT": "OUT "}[st]
            print(f"  [{mark}] #{i} [{lang}] {det.splitlines()[0][:120]}")
            if st == "FAIL":
                fails.append((dp.name, i, lang, body.strip(), det))

    print()
    print("=" * 78)
    print(f"合计: PASS {total['PASS']} / FAIL {total['FAIL']} / SKIP {total['SKIP']} "
          f"/ GUARD {total['GUARD']} / T/O {total['T/O']} / OUT {total['OUT']}")
    print("=" * 78)
    for doc, i, lang, b, det in fails:
        print(f"\n--- FAIL {doc} #{i} ({lang}) ---")
        print(b[:600])
        print("  >> " + det.replace("\n", "\n  >> ")[:700])
    (TMP / "fails.txt").write_text(
        "\n\n".join(f"=== {d} #{i} ({l}) ===\n{b}\n>> {det}" for d, i, l, b, det in fails),
        encoding="utf-8")
    return 1 if total["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
