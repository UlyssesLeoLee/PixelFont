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
    # --- PixelFont Multi 12 家族 (multi12-v1.0.0) ---
    "d28e0fb5134415319a9a42f19a706463c9fddc8a992f76729bab7f9ff5131913": "multi12 TTF 成品",
    "6eab85eaecb1dee433dc7f40e43f554ab9023d81475d96c554ae9ff903012fd9": "multi12 发布包 zip",
    "af4baf59f7f8f88640d30a18928cd5335fa6265210c6776f279755ea4b6bb51a": "multi12 BDF",
    "b8ed55582d072201604a6eadb60c130d781371853c0265fe46c1f8e18cdbb357": "multi12 bdf.map",
    "6df3bfce5e24ca135d94f7d12ba836f352908c2df4627752c8d43021c1ee63ca": "multi12 图集 PNG",
    "5c662ce6b85ebf47ebf24a7c2b0f0b44e92c801223d94b3543f9b8712579a97a": "multi12 图集 JSON",
    "c9d93ff4e4efeae4c0c61bb5e96342584ac77d8e0475755566a1bf0b75931a25": "multi12 样张 PNG",
    "93f370b4b2e2971217c490e287d7fa8742f9a49e829d6982b54a9e752570a8e4": "multi12 发布级 SHA256SUMS (v1.0.0)",
    "729c3d457c3ab331b50bc330ee129dd592e82b98bd9360d73d711c8a1c0efb78": "multi12 发布包 zip (v1.0.1)",
    "ce75495e82fbe77e17afb4e9cb330bd9c376a8ce2a2e6c02b8bf940b8a24afdc": "multi12 发布级 SHA256SUMS (v1.0.1)",
    "983af89b36518a85ee5205b6cad1de232dbc2852b536c50ff2956bf74db3b5a4": "multi12 OFL 全文",
    "d9cd278dd5752273154bf26aa9e5f30d3b7a8582bceab830f48f7f822be46b38": "vendor multi12 ja 裁剪版",
    "83a14eacdbfa07718698969a6630681ec423caf3fac1c0f668f72fea0818d3a9": "vendor multi12 ko 裁剪版",
    "a63c7eab7ca519d6b2aba0ef825d87f5ccb110801b61fa51b02277559c5264cf": "vendor multi12 zh_hans 裁剪版",
    "26f7d76c6d6be40ec47659286486f21fb5da328b22b89867717505f1beecb69d": "vendor multi12 latin 裁剪版",
    "745dc5dd0b9b7b2f2b5e8af4829ca7d9b8ee88c68d3f2fb0c6181843bc0a4cc1": "multi12 手绘字形数据",
    "bc518cf64b8032c07690f33cc270c35c179255a6ac8efa7c165ebae7e8f76a63": "Fusion Pixel OFL 全文",
    "3ab41567e68e3988ba1ef16dd2644eca95ca5648ea12e7d46e6287fc0bbe5aee": "Ark Pixel OFL 全文",
    "2b6e5938e5cffa0b9e183bd05f8c363e174e7ebed1a0556e2855fd1707fa2188": "Cubic 11 OFL 全文",
    "86a3ee9495f942f0243f18c103da9faca27adb88142613edb8bb852e56c892c1": "Galmuri LICENSE 全文",
    "04b7da50afa9395023c620db459602ea7fd23d49a7e9167e4eb1a60e48e2c2f9": "multi12 路由快照",
    # --- PixelFont Multi 12 家族 (multi12-v1.1.0) ---
    # 2026-10-25: 接入 ZLabs 简体补源, 字符集 31,392 -> 31,753 (纯新增)。
    # 裁剪版哈希全部变了 —— 差异只在 head 表的 `modified` 一个字段,
    # 因为当时裁剪器没关掉时间戳重算 (已修, 见 vendor_multi12_sources.py)。
    "b844d8c1f92114acfcb2745dcff6c1c13711bb6853b372d6bab6b8137bf87c15": "multi12 TTF 成品 (v1.1.0)",
    "64b6f8518eeddc1af50e1364e3389fd8d07f059156d46253fb3f0f6c68dddb76": "multi12 BDF (v1.1.0)",
    "6ab373e4bf976f0bcd8c2cdd5f73be6010371f3aba200a6f7f443d629d0f7b31": "multi12 bdf.map (v1.1.0)",
    "6012edab6e61bd11ef680b40b69e51faa07b8a57d01b609ab053ab681ea1a9bc": "multi12 图集 PNG (v1.1.0)",
    "37bec853390fa093e92173ee1dd1a1a175c91f346aacfae56ae937bcd3b8cb08": "multi12 图集 JSON (v1.1.0)",
    "68fc526c9566aee4b3c76eecce9a5eccdd15495ee1337cbeb5a46e2fdb44c7ac": "multi12 发布包 zip (v1.1.0)",
    "445e3f3e24f252f2099fb5980fc204b61bf058244f9e869b35017ca5078d2797": "multi12 发布级 SHA256SUMS (v1.1.0)",
    "18b74da7a733340ead037e30eaa63ff5c4cb58e02add5df77a5b2f1d79e98e87": "multi12 OFL 全文 (v1.1.0, 含全部上游版权声明)",
    "3eac69c9c43c1a4822c09b85bf9e1ac83099fe1da157cadbf9ad6adda2f7b152": "vendor multi12 ja 裁剪版 (v1.1.0)",
    "fdb0c7df9acee449c59f6614051589d770cb96596d3ece0facf6fcea190e03ac": "vendor multi12 ko 裁剪版 (v1.1.0)",
    "67d36dce34b9d9b2e5ba12dfec3f8613bb61e6a5e1e7216d3364c7ae68558680": "vendor multi12 zh_hans 裁剪版 (v1.1.0)",
    "e475a74809b25d9c8ad322e4281ca04e342fbe5642c4ee4799105fa678cfad73": "vendor multi12 latin 裁剪版 (v1.1.0)",
    "1daf313ed9b2aa0697de3f3828d2c01f585e6972c0e515f15a16fa0ce10da679": "vendor multi12 zlabs_cn 裁剪版 (v1.1.0)",
    "c4bf6069b8e5e31dc42c81f310afbc322c2cbc843ceba6c871358f9f1aaae033": "ZLabs Pixel 12px CN 原始下载",
    "1b4d4877cb561c1800e3a2eacdbcd024760d20971656cec042d434ae9ee33c1d": "ZLabs Pixel OFL 全文",
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
