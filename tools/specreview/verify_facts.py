"""规格文档事实核验器。

四条判据:
  1. 每个 sha256 必须落在已知白名单里 —— 未知哈希 = 编造
  2. 每个 U+XXXX 必须落在已知码位集合里 —— 未知码位 = 编造
  3. 每份规格文档必须包含六段章节结构 + 结论先行
  4. 跨文档一致性: 关键事实的命中文档数落在区间内, 且事实底稿 100% 覆盖

白名单全部来自**实测**产物与源码推导, 不来自文档自述。
"""
from __future__ import annotations

import re
import sys

from common import (BASELINE, REQUIRED_SECTIONS, SHA_RE, CP_RE, SPEC_DOCS,
                    SUPPORT_DOCS)

# --- 已知 sha256 白名单 (来自实测) ---
KNOWN_SHA = {
    "3298ae4d9e28e7f3d5939e007df43ea82b64860922ab246fc7a4b82414f69fb1": "v1.0.0 TTF 成品",
    "96ee924e853fce5a29eda0990ed4b68efef46b74f7782b764053cb2ad150fde8": "发布包 zip",
    "fcc65bcbcd8a1a022007065e3444464916edb537bb172b6f2acdc9596de3303b": "旧版 TTF (10-23)",
    "269619d5eaa0b84bc478b550893c6f5ccaab6b0709f86ab19433ad5a8a46b2d3": "中间版 TTF (10-24早)",
    "fc910f23ff8ee2df8f2fec6f91381a60df812e3a16ce177f48528f1db6551a37": "vendor Fusion 裁剪版",
    "c3b117dcfe1ea20aebb8c2b3be709a2a604b62fd62f7c24458e3e91fa2b373bc": "sizescale png",
    "80cf703189e7a00cd73c472e4aa210b474ceec376e5e75dfffe28c9e04707a61": "merge-before-after png",
    "ae1512de69702ebfd3def3de65b73037f112431452766dc4fc8fbc404838554d": "Ark Pixel 归档",
    "c4c9e466042d76f4b37c78232b6ecd4e1f25be3a27cd0f3aacdfaf7de5bd515b": "Fusion Pixel 归档",
    "56e82b4fa83e9e7bc586da288a7eb0481f8bc1f1fa8ecc6ad952781c8c0e366a": "Ark zh_hans ttf",
    "4ae459a3bdff66bcf430f1b1cd4641a0b4433732a70c57d6a975ab058b0a88e7": "Fusion zh_hans ttf",
    "a67917d94bb597acbdf3bfe1cf97047cc3e1cdd3839d21da188e35cc0737e828": "Zpix",
    "ea39a0e614e7486490239c5759e1a0cd49e335c4b08d2fd13e313147f022": "GNU Unifont",
}

# --- 已知码位 (白名单: 出现的必须属于这些集合) ---
KNOWN_CPS: set[int] = set()
KNOWN_CPS |= set(range(0x20, 0x7F))          # ASCII
KNOWN_CPS |= {0xA0, 0xB7, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D,
              0x2026, 0x2192, 0x2260, 0x2264, 0x2265, 0x20AC, 0x2022, 0x2027,
              0xA5, 0xB0, 0xBD, 0xFF0C, 0xFF0E, 0xFF01, 0xFF1F, 0xFF3B, 0xFF3D,
              0x300C, 0x300D, 0x300E, 0x300F, 0x300A, 0x300B, 0xFF0F, 0xFF0B,
              0x00D7, 0x00F7, 0xFF1C, 0xFF1E, 0x3001, 0x3002, 0x3000, 0xFF04,
              0xFFE5, 0xFF03, 0xFF06, 0xFF20, 0xFF5E, 0xFF0B, 0x2015}
KNOWN_CPS |= set(range(0x3041, 0x30A0))     # 平假名
KNOWN_CPS |= set(range(0x30A0, 0x3100))     # 片假名
KNOWN_CPS |= set(range(0xFF61, 0xFFA0))     # 半角片假名
KNOWN_CPS |= set(range(0x0100, 0x0250))     # Latin Ext A/B
KNOWN_CPS |= set(range(0x0370, 0x0400))     # Greek
KNOWN_CPS |= set(range(0x0400, 0x0500))     # Cyrillic
KNOWN_CPS |= set(range(0xAC00, 0xD7B0))     # Hangul syllables
KNOWN_CPS |= set(range(0x4E00, 0xA000))     # CJK
KNOWN_CPS |= {0x3097, 0x3098, 0x3099, 0x309A, 0x309B, 0x309C, 0x30A0, 0x30FB,
              0x30FC, 0x30F6, 0x30FD, 0x30FE, 0x30FF, 0x3094, 0x3095, 0x3096}
KNOWN_CPS |= {0x005C, 0x007C, 0x0060, 0x005E, 0x007E}
# 文档中作为「明确不覆盖」的区间被如实列出, 也属于已知码位
KNOWN_CPS |= set(range(0x0590, 0x0600))     # Hebrew   (不覆盖)
KNOWN_CPS |= set(range(0x0600, 0x0700))     # Arabic   (不覆盖)
KNOWN_CPS |= set(range(0x0900, 0x0980))     # Devanagari(不覆盖)
KNOWN_CPS |= set(range(0x0E00, 0x0E80))     # Thai     (不覆盖)
KNOWN_CPS |= set(range(0x1100, 0x1200))     # Hangul Jamo

# --- 跨文档一致性: (标签, 正则, 命中文档数下限, 上限) ---
CHECKS = [
    ("字符集总数 4,161", r"4[,.]?161", 10, 12),
    ("多语言版 31,392", r"31[,.]?392", 8, 12),
    ("设计网格 12x13", r"12\s*[×x×*]\s*13", 8, 12),
    ("UPM 768", r"\b768\b", 6, 12),
    ("半角6/全角12 advance", r"(半角|half)[^。\n]{0,40}\b6\b", 4, 12),
    ("ascent 11 / descent 2", r"ascent\s*11|11\s*/\s*descent\s*2", 4, 12),
    ("GDI 4161/4161 逐格一致", r"4[,.]?161\s*/\s*4[,.]?161", 5, 12),
    ("抗锯齿 0", r"抗锯齿[^。\n]{0,20}\b0\b", 4, 12),
    ("12 整数倍", r"12\s*的整数倍|12\s*倍整数", 5, 12),
    ("FreeType 12px 偏差 19.00", r"19\.00", 4, 12),
    ("中日共享 2,078", r"2[,.]?078", 5, 12),
    ("字形分歧 434", r"\b434\b", 4, 12),
    ("JIS 独有 2,297", r"2[,.]?297", 4, 12),
    ("AGPL-3.0", r"AGPL-3\.0", 3, 12),
    ("OFL-1.1", r"OFL-1\.1", 3, 12),
    ("TSF 973,712 字节", r"973[,.]?712", 4, 12),
    ("轮廓 73,933", r"73[,.]?933", 3, 12),
    ("整数倍精确性 12,483", r"12[,.]?483", 3, 12),
    ("偏细 43%", r"43\s*%", 4, 12),
    ("未选 locl", r"locl", 3, 12),
    ("8 步验收", r"8\s*步|verify_all", 6, 12),
    ("韩文 11,172", r"11[,.]?172", 3, 12),
]


def check_whitelist(text: str) -> list[str]:
    problems: list[str] = []
    for h in set(SHA_RE.findall(text)):
        if h.lower() not in KNOWN_SHA:
            problems.append(f"未知 sha256: {h}")
    for c in set(CP_RE.findall(text)):
        if int(c, 16) not in KNOWN_CPS:
            problems.append(f"未知码位: U+{c.upper()}")
    return problems


def main() -> int:
    bad = 0

    print("=" * 78)
    print("判据 1-3: 白名单 + 章节结构")
    print("=" * 78)
    for doc in SPEC_DOCS + SUPPORT_DOCS:
        t = doc.read_text(encoding="utf-8")
        problems = check_whitelist(t)
        if doc in SPEC_DOCS:
            for sec in REQUIRED_SECTIONS:
                if sec not in t:
                    problems.append(f"缺章节: {sec}")
        flag = "OK  " if not problems else "FAIL"
        print(f"[{flag}] {doc.name:<42} {len(t.splitlines()):>4} 行")
        for pr in problems:
            print(f"        - {pr}")
        bad += len(problems)
    print(f"\n  文档 {len(SPEC_DOCS)} 份规格 + {len(SUPPORT_DOCS)} 份支撑, 问题 {bad} 条")

    print()
    print("=" * 78)
    print("判据 4: 跨文档一致性")
    print("=" * 78)
    texts = {d.name: d.read_text(encoding="utf-8") for d in SPEC_DOCS}
    base_text = BASELINE.read_text(encoding="utf-8") if BASELINE.exists() else ""
    bad4 = 0
    print(f"{'检查项':<28}{'命中/12':>10}  期望")
    print("-" * 62)
    base_miss: list[str] = []
    for label, pat, lo, hi in CHECKS:
        hits = [n for n, t in texts.items() if re.search(pat, t)]
        ok = lo <= len(hits) <= hi
        if not ok:
            bad4 += 1
        print(f"{label:<28}{len(hits):>10}  {lo}-{hi}  {'OK' if ok else 'FAIL'}"
              + ("" if ok else "  -> " + ", ".join(n[:12] for n in hits)))
        if base_text and not re.search(pat, base_text):
            base_miss.append(label)
    if base_text:
        if base_miss:
            bad4 += len(base_miss)
            print(f"\n[FAIL] 事实底稿缺 {len(base_miss)}/{len(CHECKS)} 项: "
                  + ", ".join(base_miss))
        else:
            print(f"\n[OK  ] 事实底稿 {len(CHECKS)}/{len(CHECKS)} 项全覆盖")
    else:
        bad4 += 1
        print("\n[FAIL] 事实底稿缺失")
    print(f"\n  一致性: {len(CHECKS) - bad4}/{len(CHECKS)} 项通过")

    total = bad + bad4
    print()
    print("=" * 78)
    print(f"事实核验: 问题合计 {total} 条")
    print("=" * 78)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
