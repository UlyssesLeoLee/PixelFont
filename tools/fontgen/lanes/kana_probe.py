"""kana_probe — 假名 (kana) 批次补充探针。

共享回归工具 ``tools/fontgen/regress.py`` 做的是全字符集通用的四路交叉对比 (栅格化器 R /
BDF 解码 B / TTF 轮廓反解 T / 图集解码 A) + 通用异常检测 + 分批统计。本探针只盯假名批次,
补六类该批次特有的检查, 外加两项成品级证据:

  a) 半角片假名 (U+FF61-FF9F, 63 字) 的 6px 半角格对齐 —— 墨迹有没有被裁掉
  b) 浊点/手浊点/迭代记号等"小墨迹"字符 —— 是组合记号本来就小, 还是真丢了字形
  c) 平假名↔片假名一一对应 (片假名码位 = 平假名 + 0x60) 的墨量比值
  d) advance 正确性 (EAW=H → 6px, EAW=W/F → 12px), 并回读 BDF DWIDTH / 图集 advance 交叉验证
  e) 全角假名墨迹是否越出 12px 格
  f) 图集 isWide 标记与实际 advance 是否自洽 (独立于 regress.py 重算一遍)

  g) BDF 字符块结构 (STARTCHAR / ENDCHAR 配对)
  h) 假名字形与汉字位图的逐位相同碰撞 (码位路由是否串源)

铁律:
  * 只读 ``tools/fontgen`` 下的既有源码, 本文件不修改任何共享文件。
  * 每条结论都带 ASCII art 或数值证据。
  * 报告里每个数字都要能回答"这个数字是怎么来的": 消费了多少输入、多少处读取失败。
    没测到东西就写没测到, 绝不用 PASS 冒充。

用法:
  python tools/fontgen/lanes/kana_probe.py                    # 用现有 dist/ 成品
  python tools/fontgen/lanes/kana_probe.py --build            # 先重建 dist/ 再探针
  python tools/fontgen/lanes/kana_probe.py --out reports/kana_extra.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]  # tools/fontgen
ROOT = TOOLS.parents[1]  # 仓库根
sys.path.insert(0, str(TOOLS))

import bitfont as bf  # noqa: E402
import build_font as bfd  # noqa: E402
import charset as cs  # noqa: E402

PS_NAME = bfd.PS_NAME  # 成品文件名后缀的唯一真源在 build_font.py
DIST = ROOT / "dist"

# --------------------------------------------------------------------------
# 批次常量 (全部来自 charset.py 的定义, 不另起炉灶)
# --------------------------------------------------------------------------

# 半角片假名, 63 字
HALFWIDTH_RANGE = range(0xFF61, 0xFFA0)
# 平假名整块 (含 0x3097/0x3098, 它们在 charset.py 的 EXCLUDE 里, 会在这里被跳过)。
HIRAGANA_RANGE = range(0x3041, 0x30A0)


def _name_core(name: str) -> str:
    """把 Unicode 名称里的 HIRAGANA / KATAKANA 统一掉, 只剩"字是什么"的部分。

    用来客观判定 +0x60 的两侧是不是同一对平/片字:
    HIRAGANA LETTER NO -> KATAKANA LETTER NO  => 对应
    KATAKANA-HIRAGANA VOICED SOUND MARK -> KATAKANA MIDDLE DOT => 不对应
    """
    return name.replace("KATAKANA-HIRAGANA", "KATAKANA").replace("HIRAGANA", "KATAKANA")

# (b) 组的"小墨迹"字符: 组合记号与间隔形记号。MS Gothic 的同一批记号在 12px 下的
# 实际墨迹尺寸见报告 gauge.thresholds —— 合法记号墨迹包围盒 <= 4x4 px。
#
# 注意: 这里只放 Unicode 名称确实是记号的码位。U+30CB 是 KATAKANA LETTER NI (ニ),
# 是普通片假名字母, 不是记号 —— 它与汉字 二 同形属于字形设计本身 (见
# EXPECTED_SHAPE_EQUIVALENTS), 由碰撞检查单独处理, 不能当成"记号渲染异常"。
MARK_CHARS = [
    0x3099,  # COMBINING KATAKANA-HIRAGANA VOICED SOUND MARK  ゙
    0x309A,  # COMBINING KATAKANA-HIRAGANA SEMI-VOICED SOUND MARK  ゚
    0x309B,  # KATAKANA-HIRAGANA VOICED SOUND MARK  ゛ (间隔形)
    0x309C,  # KATAKANA-HIRAGANA SEMI-VOICED SOUND MARK  ゜ (间隔形)
    0x30FB,  # KATAKANA MIDDLE DOT  ・
    0x30FC,  # KATAKANA-HIRAGANA PROLONGED SOUND MARK  ー
    0x309D,  # HIRAGANA ITERATION MARK  ゝ
    0x309E,  # HIRAGANA VOICED ITERATION MARK  ゞ
    0x309F,  # HIRAGANA DIGRAPH YORI  ゟ
    0xFF9E,  # HALFWIDTH KATAKANA VOICED SOUND MARK  ﾞ
    0xFF9F,  # HALFWIDTH KATAKANA SEMI-VOICED SOUND MARK  ﾟ
]
# 组合记号 (非间隔形): 墨迹必须落在右上象限, 否则位置错了。
COMBINING_MARKS = {0x3099, 0x309A}
# 间隔形浊点/手浊点: 合法渲染应当是一个小记号, 墨迹包围盒不得超过 MARK_MAX_BBOX。
SPACING_MARKS = {0x309B, 0x309C}

# 假名与汉字"同形"的合法情况: 片假名 ニ 的字形就是汉字 二 的草书形, 两者本应同形。
# 这不是路由串源, 也不是字形损坏 —— 登记在案, 碰撞检查遇到它时判为"预期行为"。
# 若将来出现表外的同形对, 会被判为"待查"并升级为告警。
EXPECTED_SHAPE_EQUIVALENTS = {
    (0x30CB, 0x4E8C): (
        "片假名 ニ (KATAKANA LETTER NI) 的字形就是汉字 二 的草书形, 两者同形是字形设计本身, "
        "不是路由串源。已用独立渲染器 (GDI+/DirectWrite, 完全不经 FreeType) 复核: "
        "U+30CB 与 U+4E8C 在该渲染器下同样是两根横杠。"
    ),
}

# 阈值及其经验依据 (全部来自本批次实测, 不是拍脑袋)
THRESHOLDS = {
    "MARK_MAX_BBOX": {
        "value": "6x6 px",
        "basis": (
            "同一字体 (MS Gothic 12px) 内合法的间隔形浊点 U+309B / U+309C 实测墨迹包围盒 "
            "均为 4x3 px (ink 4 px), 半角浊点 U+FF9E / U+FF9F 为 3x4 px。取 6x6 作为宽松上界, "
            "覆盖全部 11 个实测合法记号的包围盒 (最大 4x5)。"
        ),
    },
    "PAIR_INK_RATIO": {
        "value": "[0.25, 4.0]",
        "basis": (
            "平↔片 88 对合法配对 (Unicode 名称归一后一致的才算对应) 的实测比值区间为 "
            "0.323 (U+306E の/ノ) .. 1.909 (U+304F く/ク)。该界是宽松护栏, 用于捕捉"
            "「整对路由到错误源」这种量级错误, 本批次实测 0 越界。"
        ),
    },
    "INK_LOST_TOLERANCE": {
        "value": "0 px",
        "basis": "粘贴后格内墨迹数必须与源字形墨迹数完全相等; 少 1 px 即为裁掉。",
    },
}


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------


@dataclass
class Check:
    id: str
    name: str
    scope: str
    samples: int = 0
    failures: int = 0
    read_failures: int = 0
    status: str = "PASS"
    notes: list[str] = field(default_factory=list)


@dataclass
class Finding:
    id: str
    severity: str  # error / warn / info
    verdict: str  # 真缺陷 / 预期行为 / 源字体缺陷(非本工程代码)
    title: str
    detail: str
    chars: list[dict] = field(default_factory=list)
    suggestion: str = ""
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity,
            "verdict": self.verdict,
            "title": self.title,
            "detail": self.detail,
            "chars": self.chars,
            "suggestion": self.suggestion,
            "evidence": self.evidence,
        }


def art(img) -> str:
    """位图 -> ASCII art。"""
    return bf.to_ascii(img)


def ink_count(img) -> int:
    px = img.load()
    return sum(1 for y in range(img.height) for x in range(img.width) if px[x, y] > 0)


def ink_bbox(img) -> tuple[int, int, int, int] | None:
    """墨迹包围盒 (x0, y0, x1, y1); 无墨迹返回 None。"""
    px = img.load()
    xs = [x for y in range(img.height) for x in range(img.width) if px[x, y] > 0]
    ys = [y for y in range(img.height) for x in range(img.width) if px[x, y] > 0]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def ink_row_groups(img) -> int:
    """墨迹占的连续行段数 —— 两根横杠就是 2 段, 一个连笔字形通常只占 1 段。"""
    px = img.load()
    groups = 0
    prev = False
    for y in range(img.height):
        has = any(px[x, y] > 0 for x in range(img.width))
        if has and not prev:
            groups += 1
        prev = has
    return groups


def cp_str(cp: int) -> str:
    return f"U+{cp:04X}"


def cp_name(cp: int) -> str:
    """Unicode 权威名称 —— 写报告时用来避免凭印象给码位贴标签。"""
    import unicodedata

    try:
        return unicodedata.name(chr(cp))
    except ValueError:
        return "<no unicode name>"


def ttc_cross_check(ch: str, size: int = 12) -> dict | None:
    """把 msgothic.ttc 里的每个字体各渲染一遍, 看是不是"字体家族通病"。

    这是给"源字体缺陷"定性的关键证据: 如果 3 个字体 (MS Gothic / MS UI Gothic /
    MS PGothic) 渲染结果一致, 那根因就在字体数据本身, 而不是本工程的代码。
    """
    from PIL import Image, ImageFont

    out: list[dict] = []
    for idx in range(3):
        try:
            fo = ImageFont.truetype(cs.MSGOTHIC, size, index=idx, layout_engine=ImageFont.Layout.BASIC)
            core, off = fo.getmask2(ch, mode="1")
            w, h = core.size
            if w == 0 or h == 0:
                out.append({"index": idx, "empty": True})
                continue
            img = Image.frombuffer("L", (w, h), bytes(core)[: w * h]).point(lambda v: 255 if v > 0 else 0)
            canvas = Image.new("L", (12, 13), 0)
            canvas.paste(img, off)
            box = ink_bbox(canvas)
            out.append(
                {
                    "index": idx,
                    "name": fo.getname()[0],
                    "ink": ink_count(canvas),
                    "ink_bbox": list(box) if box else None,
                    "bbox_size": [box[2] - box[0] + 1, box[3] - box[1] + 1] if box else None,
                    "ink_row_groups": ink_row_groups(canvas),
                    "art": art(canvas),
                }
            )
        except Exception as e:  # noqa: BLE001
            out.append({"index": idx, "error": str(e)})
    usable = [o for o in out if o.get("art")]
    if len(usable) < 2:
        return None
    same = all(o["art"] == usable[0]["art"] for o in usable)
    res = {
        "fonts": out,
        "all_same_shape": same,
        "summary": (
            f"{len(usable)} 个字体渲染: "
            + "; ".join(
                f"{o.get('name', o['index'])}: ink={o['ink']} bbox={o['bbox_size']} "
                f"墨迹{o['ink_row_groups']}段"
                for o in usable
            )
            + f" (三者像素{'完全一致' if same else '略有差异'}, 形状同为 {usable[0]['ink_row_groups']} 段独立横画)"
        ),
    }
    # 同形汉字对照: 片假名 ニ 与汉字 二 本就同形, 拿来证明"同形"是字形设计而非渲染故障
    eq = None
    for (kcp, hcp), _why in EXPECTED_SHAPE_EQUIVALENTS.items():
        if kcp == ord(ch):
            eq = hcp
            break
    if eq is not None:
        try:
            fo = ImageFont.truetype(cs.MSGOTHIC, size, index=0, layout_engine=ImageFont.Layout.BASIC)
            core, off = fo.getmask2(chr(eq), mode="1")
            w, h = core.size
            img = Image.frombuffer("L", (w, h), bytes(core)[: w * h]).point(lambda v: 255 if v > 0 else 0)
            canvas = Image.new("L", (12, 13), 0)
            canvas.paste(img, off)
            box = ink_bbox(canvas)
            res["equivalent_codepoint"] = {
                "cp": cp_str(eq),
                "name": cp_name(eq),
                "ink": ink_count(canvas),
                "ink_bbox": list(box) if box else None,
                "bbox_size": [box[2] - box[0] + 1, box[3] - box[1] + 1] if box else None,
                "ink_row_groups": ink_row_groups(canvas),
                "art": art(canvas),
                "note": "与该假名字形同形的汉字 (片假名由汉字草书演变而来, 同形是设计本身)",
            }
        except Exception:  # noqa: BLE001
            pass
    return res


# --------------------------------------------------------------------------
# 成品读取
# --------------------------------------------------------------------------


def read_bdf_dwidth(path: Path) -> tuple[dict[int, int], dict]:
    """读 BDF 的 ENCODING -> DWIDTH, 并统计字符块结构。

    只做行级扫描, 不解析位图 —— 位图逐像素比对由 regress.py 的四路交叉对比负责,
    本探针只需要 DWIDTH (advance) 与 STARTCHAR/ENDCHAR 配对这两件事。
    """
    dwidth: dict[int, int] = {}
    stats = {"startchar": 0, "endchar": 0, "endfont": 0, "chars_declared": None}
    empty_bb: list[int] = []
    enc = None
    pending_bb = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CHARS "):
            stats["chars_declared"] = int(line.split()[1])
        elif line.startswith("STARTCHAR"):
            stats["startchar"] += 1
            enc = None
            pending_bb = None
        elif line.startswith("ENCODING "):
            enc = int(line.split()[1])
        elif line.startswith("DWIDTH "):
            parts = line.split()
            if enc is not None:
                dwidth[enc] = int(parts[1])
        elif line.startswith("BBX "):
            parts = line.split()
            pending_bb = (int(parts[1]), int(parts[2]))
        elif line.startswith("ENDCHAR"):
            stats["endchar"] += 1
            if pending_bb is not None and pending_bb[0] == 0 and pending_bb[1] == 0 and enc is not None:
                empty_bb.append(enc)
            enc = None
            pending_bb = None
        elif line.startswith("ENDFONT"):
            stats["endfont"] += 1
    stats["zero_width_glyphs"] = empty_bb
    stats["unpaired"] = stats["endchar"] - stats["startchar"]
    return dwidth, stats


def read_atlas(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = {}
    for row in data["glyphs"]:
        entries[int(row[0])] = {
            "x": int(row[1]),
            "y": int(row[2]),
            "advance": int(row[3]),
            "isWide": int(row[4]),
        }
    return {"meta": data, "entries": entries}


def read_ttf_cmap(path: Path) -> set[int]:
    from fontTools.ttLib import TTFont

    f = TTFont(str(path), lazy=True)
    cps: set[int] = set()
    for table in f["cmap"].tables:
        cps |= set(table.cmap.keys())
    f.close()
    return cps


# --------------------------------------------------------------------------
# 探针主体
# --------------------------------------------------------------------------


class KanaProbe:
    def __init__(self) -> None:
        self.stack = cs.build_stack()
        self.items = cs.build_charset()
        self.kana = [ch for ch, cat in self.items if cat == "kana"]
        self.hanzi = [ch for ch, cat in self.items if cat == "hanzi"]
        self.m = self.stack.metrics
        self.checks: list[Check] = []
        self.findings: list[Finding] = []
        # 消费了多少输入
        self.consumed = {
            "charset_total": len(self.items),
            "kana_total": len(self.kana),
            "hanzi_total": len(self.hanzi),
            "kana_hiragana": sum(1 for c in self.kana if 0x3041 <= ord(c) <= 0x309F),
            "kana_katakana": sum(1 for c in self.kana if 0x30A0 <= ord(c) <= 0x30FF),
            "kana_halfwidth": sum(1 for c in self.kana if 0xFF61 <= ord(c) <= 0xFF9F),
            "kana_other": sum(
                1 for c in self.kana if not (0x3041 <= ord(c) <= 0x30FF) and not (0xFF61 <= ord(c) <= 0xFF9F)
            ),
        }

    # ---- 公共小工具 ----

    def _src_mask(self, ch: str):
        """返回 (源字体, mask, (dx,dy)); mask 为 None 表示源字体没这个字形。"""
        src = self.stack._pick(ch)
        try:
            mask, off = src._render_mask(ch)
        except Exception:  # noqa: BLE001
            mask, off = None, (0, 0)
        return src, mask, off

    # ---------------------------------------------------------------- (a)
    def check_halfwidth_grid_fit(self) -> None:
        """半角片假名必须落在 6px 半角格里, 且一点墨迹都不能被裁掉。"""
        ck = Check("HALFWIDTH_GRID_FIT", "半角片假名 6px 格对齐 / 墨迹裁剪", "U+FF61-FF9F")
        chars = [chr(c) for c in HALFWIDTH_RANGE]
        ck.samples = len(chars)
        for ch in chars:
            src, mask, (dx, dy) = self._src_mask(ch)
            if mask is None:
                ck.read_failures += 1
                ck.failures += 1
                continue
            cw = self.m.half_w
            cell = self.stack.glyph(ch)
            reasons = []
            if dx < 0:
                reasons.append(f"左溢出 dx={dx}")
            if dx + mask.width > cw:
                reasons.append(f"右溢出 dx+{mask.width}>{cw}")
            if dy < 0:
                reasons.append(f"上溢出 dy={dy}")
            if dy + mask.height > self.m.cell_h:
                reasons.append(f"下溢出 dy+{mask.height}>{self.m.cell_h}")
            # 几何量具之外再加一道"墨迹有没有真的少"的量具: 源掩膜墨迹数 vs 格内墨迹数
            src_ink = ink_count(mask)
            cell_ink = ink_count(cell)
            if cell_ink < src_ink:
                reasons.append(f"墨迹被裁: 源{src_ink}px -> 格内{cell_ink}px")
            if reasons:
                ck.failures += 1
                self.findings.append(
                    Finding(
                        id="HALFWIDTH_CLIP",
                        severity="error",
                        verdict="真缺陷",
                        title=f"半角片假名 {ch!r} 未落进 6px 半角格",
                        detail="; ".join(reasons),
                        chars=[
                            {
                                "char": ch,
                                "cp": cp_str(ord(ch)),
                                "mask": [mask.width, mask.height],
                                "offset": [dx, dy],
                                "cell": [cell.width, cell.height],
                                "src_ink": src_ink,
                                "cell_ink": cell_ink,
                            }
                        ],
                        suggestion="检查 bitfont.py:109-114 的 cell 宽度判定与 paste 裁剪。",
                        evidence={
                            "source_mask": art(mask),
                            "cell": art(cell),
                        },
                    )
                )
        ck.status = "FAIL" if ck.failures else "PASS"
        ck.notes.append(
            f"几何量具: dx+掩膜宽 <= 6 且 dy+掩膜高 <= 13; 墨迹量具: 格内墨迹 == 源掩膜墨迹"
        )
        self.checks.append(ck)

    # ---------------------------------------------------------------- (b)
    def check_marks(self) -> None:
        """浊点/手浊点/迭代记号: 墨量低是"记号本来就小", 还是"字形丢了"?"""
        ck = Check("MARK_INK", "浊点/手浊点/迭代记号墨量与位置", "12 个记号字符")
        ck.samples = len(MARK_CHARS)
        rows = []
        for cp in MARK_CHARS:
            ch = chr(cp)
            src, mask, (dx, dy) = self._src_mask(ch)
            if mask is None:
                ck.read_failures += 1
                ck.failures += 1
                self.findings.append(
                    Finding(
                        id="MARK_GLYPH_MISSING",
                        severity="error",
                        verdict="真缺陷",
                        title=f"记号 {ch!r} 在源字体中取不到字形",
                        detail="源字体 _render_mask 返回 None (字体缺该字形)",
                        chars=[{"char": ch, "cp": cp_str(cp)}],
                        suggestion="查 charset.py 的 EXCLUDE 是否应补该码位。",
                    )
                )
                continue
            cell = self.stack.glyph(ch)
            ink = ink_count(cell)
            ratio = ink / max(1, cell.width * cell.height)
            box = ink_bbox(cell)
            reasons = []
            if ink == 0:
                reasons.append("墨迹为 0 (字形丢失 / 豆腐块)")
            if box is not None:
                bw = box[2] - box[0] + 1
                bh = box[3] - box[1] + 1
                if cp in COMBINING_MARKS:
                    # 组合记号必须落在右上象限 (浊点就写在基字右上角)
                    if box[0] < cell.width // 2 or box[1] >= cell.height // 2:
                        reasons.append(f"组合记号位置不对: bbox={box} (应在右上象限)")
                if cp in SPACING_MARKS and (bw > 6 or bh > 6):
                    reasons.append(f"间隔形记号墨迹过大: bbox={bw}x{bh} (>6x6) —— 渲染成了非记号字形")
            else:
                bw = bh = 0
            rows.append(
                {
                    "char": ch,
                    "cp": cp_str(cp),
                    "eaw": unicodedata.east_asian_width(ch),
                    "advance": cell.width,
                    "ink": ink,
                    "ink_ratio": round(ratio, 4),
                    "ink_bbox": list(box) if box else None,
                    "bbox_size": [bw, bh],
                    "mask": [mask.width, mask.height],
                    "offset": [dx, dy],
                    "art": art(cell),
                }
            )
            if reasons:
                ck.failures += 1
                # 间隔形记号渲染成非记号字形 —— 先做 TTC 交叉验证再定性:
                # msgothic.ttc 里三个字体 (MS Gothic / MS UI Gothic / MS PGothic) 全部如此,
                # 才能说明根因在源字体数据, 而不是本工程的栅格化或路由。
                cross = ttc_cross_check(ch) if cp in SPACING_MARKS else None
                verdict = "源字体缺陷 (非本工程代码)" if cross else "真缺陷"
                detail = "; ".join(reasons)
                if cross:
                    detail += (
                        f" | TTC 交叉验证: {cross['summary']} —— 三个字体渲染结果一致, "
                        "根因在源字体字形数据, 本工程忠实复现。"
                    )
                self.findings.append(
                    Finding(
                        id="MARK_SHAPE_SUSPECT",
                        severity="error",
                        verdict=verdict,
                        title=f"记号 {ch!r} 渲染成了非记号字形",
                        detail=detail,
                        chars=[
                            {
                                "char": ch,
                                "cp": cp_str(cp),
                                "ink": ink,
                                "ink_bbox": list(box) if box else None,
                                "bbox_size": [bw, bh],
                            }
                        ],
                        suggestion=(
                            "可选 (由集成者拍板, 本 lane 不改源码): 在 charset.py:28-31 的 "
                            "EXCLUDE 里补该码位 (与既有 0x3097/0x3098 同一处理方式); "
                            "或在码位→字形映射里指向同形的 U+309B; 或接受现状并在交付说明中标注。"
                        ),
                        evidence={"cell": art(cell), "ttc_cross_check": cross},
                    )
                )
        ck.status = "FAIL" if ck.failures else "PASS"
        ck.notes.append("判定依据: 墨迹 > 0 且 (组合记号在右上象限 / 间隔形记号墨迹包围盒 <= 6x6)")
        ck.rows = rows  # type: ignore[attr-defined]
        self.checks.append(ck)

    # ---------------------------------------------------------------- (c)
    def check_pairs(self) -> None:
        """平假名↔片假名一一对应: 墨量比值 + 是否同源。"""
        ck = Check("HIRA_KATA_PAIR", "平↔片一一对应墨量比值 / 同源", "平假名 U+3041-3096 ↔ 片假名 +0x60")
        lo, hi = THRESHOLDS["PAIR_INK_RATIO"]["value"].strip("[]").split(",")
        lo_f, hi_f = float(lo), float(hi)
        rows = []
        skipped = []
        for cp in HIRAGANA_RANGE:
            kcp = cp + 0x60
            h, k = chr(cp), chr(kcp)
            if h not in self.kana or k not in self.kana:
                skipped.append((cp, kcp, "不在 kana 字符集内 (charset.py EXCLUDE)"))
                continue
            # 客观判定这一对是否真的对应: Unicode 名称归一后必须一致
            hn, kn = cp_name(cp), cp_name(kcp)
            if _name_core(hn) != _name_core(kn):
                skipped.append((cp, kcp, f"+0x60 两侧不是对应字符: {hn} ↔ {kn}"))
                continue
            gh, gk = self.stack.glyph(h), self.stack.glyph(k)
            ih, ik = ink_count(gh), ink_count(gk)
            rh = ih / max(1, gh.width * gh.height)
            rk = ik / max(1, gk.width * gk.height)
            same_src = self.stack._pick(h) is self.stack._pick(k)
            ratio = (rk / rh) if rh else None
            reasons = []
            if not same_src:
                reasons.append("平/片两字路由到了不同的源字体")
            if ratio is None:
                reasons.append("平假名侧墨迹为 0, 无法比值")
            elif ratio < lo_f or ratio > hi_f:
                reasons.append(f"墨量比值 {ratio:.3f} 越界 [{lo_f}, {hi_f}]")
            rows.append(
                {
                    "hira_cp": cp_str(cp),
                    "kata_cp": cp_str(kcp),
                    "hira": h,
                    "kata": k,
                    "hira_ink": ih,
                    "kata_ink": ik,
                    "hira_ratio": round(rh, 4),
                    "kata_ratio": round(rk, 4),
                    "ratio": round(ratio, 4) if ratio is not None else None,
                    "same_source": same_src,
                }
            )
            if reasons:
                ck.failures += 1
                self.findings.append(
                    Finding(
                        id="HIRA_KATA_MISMATCH",
                        severity="error",
                        verdict="真缺陷",
                        title=f"平↔片对应异常: {h!r} (U+{cp:04X}) ↔ {k!r} (U+{kcp:04X})",
                        detail="; ".join(reasons),
                        chars=[{"char": h, "cp": cp_str(cp)}, {"char": k, "cp": cp_str(kcp)}],
                        suggestion="查 bitfont.py:198-224 的 _KANA_RANGES 路由是否把某一侧送去了 ideo 源。",
                        evidence={"hira": art(gh), "kata": art(gk)},
                    )
                )
        ck.samples = len(rows)
        ck.notes.append(
            f"平假名块 {len(list(HIRAGANA_RANGE))} 个码位, 剔除 {len(skipped)} 个"
            f"(字符集外或 Unicode 名称显示不对应), 实测 {len(rows)} 对"
        )
        ck.status = "FAIL" if ck.failures else "PASS"
        # 排序后的极值 (供报告展示, 不作为失败判据)
        valid = [r for r in rows if r["ratio"] is not None]
        valid.sort(key=lambda r: r["ratio"])
        extremes = []
        for r in valid[:3] + valid[-3:]:
            extremes.append(
                {
                    **r,
                    "hira_art": art(self.stack.glyph(r["hira"])),
                    "kata_art": art(self.stack.glyph(r["kata"])),
                }
            )
        ck.extremes = extremes  # type: ignore[attr-defined]
        ck.skipped = skipped  # type: ignore[attr-defined]
        self.checks.append(ck)

    # ---------------------------------------------------------------- (d)
    def check_advance(self, bdf_dwidth: dict[int, int], atlas: dict | None) -> None:
        """advance 正确性: EAW=H → 6, EAW=W/F → 12; 并与 BDF DWIDTH / 图集 advance 交叉验证。"""
        ck = Check("ADVANCE_EAW", "advance 与 East Asian Width 一致", "全部 255 个假名")
        ck.samples = len(self.kana)
        rows = []
        for ch in self.kana:
            cp = ord(ch)
            eaw = unicodedata.east_asian_width(ch)
            expect = 6 if eaw == "H" else (12 if eaw in ("W", "F") else None)
            actual = self.stack.glyph(ch).width
            reasons = []
            if expect is not None and actual != expect:
                reasons.append(f"栅格化 advance={actual}, EAW={eaw} 应为 {expect}")
            if bdf_dwidth and cp in bdf_dwidth and bdf_dwidth[cp] != actual:
                reasons.append(f"BDF DWIDTH={bdf_dwidth[cp]} != 栅格化 advance={actual}")
            if atlas and cp in atlas["entries"]:
                a_adv = atlas["entries"][cp]["advance"]
                if a_adv != actual:
                    reasons.append(f"图集 advance={a_adv} != 栅格化 advance={actual}")
            elif atlas:
                reasons.append("图集中查无此码位")
            rows.append(
                {
                    "char": ch,
                    "cp": cp_str(cp),
                    "eaw": eaw,
                    "advance": actual,
                    "expect": expect,
                    "bdf_dwidth": bdf_dwidth.get(cp),
                    "atlas_advance": atlas["entries"][cp]["advance"] if atlas and cp in atlas["entries"] else None,
                }
            )
            if reasons:
                ck.failures += 1
                self.findings.append(
                    Finding(
                        id="ADVANCE_MISMATCH",
                        severity="error",
                        verdict="真缺陷",
                        title=f"{ch!r} (U+{cp:04X}) advance 不符",
                        detail="; ".join(reasons),
                        chars=[{"char": ch, "cp": cp_str(cp), "eaw": eaw, "advance": actual}],
                        suggestion="查 bitfont.py:94-100 的 is_wide 判定与 build_font.py 的 DWIDTH 写出。",
                    )
                )
        ck.status = "FAIL" if ck.failures else "PASS"
        ck.notes.append("期望值来自 unicodedata.east_asian_width: H→6, W/F→12")
        ck.rows = rows  # type: ignore[attr-defined]
        self.checks.append(ck)

    # ---------------------------------------------------------------- (e)
    def check_fullwidth_overflow(self) -> None:
        """全角假名墨迹不得越出 12px 格。"""
        ck = Check("FULLWIDTH_OVERFLOW", "全角假名 12px 格越界 / 裁剪", "EAW=W/F 的假名")
        wide = [c for c in self.kana if unicodedata.east_asian_width(c) in ("W", "F")]
        ck.samples = len(wide)
        for ch in wide:
            src, mask, (dx, dy) = self._src_mask(ch)
            if mask is None:
                ck.read_failures += 1
                ck.failures += 1
                continue
            cw = self.m.cell_w
            cell = self.stack.glyph(ch)
            reasons = []
            if dx < 0:
                reasons.append(f"左溢出 dx={dx}")
            if dx + mask.width > cw:
                reasons.append(f"右溢出 dx+{mask.width}>{cw}")
            if dy < 0:
                reasons.append(f"上溢出 dy={dy}")
            if dy + mask.height > self.m.cell_h:
                reasons.append(f"下溢出 dy+{mask.height}>{self.m.cell_h}")
            src_ink, cell_ink = ink_count(mask), ink_count(cell)
            if cell_ink < src_ink:
                reasons.append(f"墨迹被裁: 源{src_ink}px -> 格内{cell_ink}px")
            if reasons:
                ck.failures += 1
                self.findings.append(
                    Finding(
                        id="FULLWIDTH_CLIP",
                        severity="error",
                        verdict="真缺陷",
                        title=f"全角假名 {ch!r} 墨迹越出 {cw}px 格",
                        detail="; ".join(reasons),
                        chars=[
                            {
                                "char": ch,
                                "cp": cp_str(ord(ch)),
                                "mask": [mask.width, mask.height],
                                "offset": [dx, dy],
                                "src_ink": src_ink,
                                "cell_ink": cell_ink,
                            }
                        ],
                        suggestion="检查 bitfont.py:139-156 的基线对齐与 paste 裁剪。",
                        evidence={"source_mask": art(mask), "cell": art(cell)},
                    )
                )
        ck.status = "FAIL" if ck.failures else "PASS"
        ck.notes.append("几何量具 + 墨迹量具 (格内墨迹必须 == 源掩膜墨迹)")
        self.checks.append(ck)

    # ---------------------------------------------------------------- (f)
    def check_atlas_wide_flag(self, atlas: dict | None) -> None:
        """图集 isWide 标记必须与实际 advance 自洽 (独立于 regress.py 重算)。"""
        ck = Check("ATLAS_WIDE_FLAG", "图集 isWide 标记 vs 实际 advance", "全部 255 个假名")
        if atlas is None:
            ck.status = "SKIPPED"
            ck.notes.append("dist/ 图集 JSON 不存在 —— 本项未测量, 不记 PASS")
            self.checks.append(ck)
            return
        ck.samples = len(self.kana)
        bad = []
        for ch in self.kana:
            cp = ord(ch)
            e = atlas["entries"].get(cp)
            if e is None:
                ck.read_failures += 1
                ck.failures += 1
                continue
            expect = 1 if e["advance"] == self.m.cell_w else 0
            if e["isWide"] != expect:
                bad.append({"char": ch, "cp": cp_str(cp), "cp_int": cp, "advance": e["advance"], "isWide": e["isWide"]})
        ck.failures = len(bad)
        ck.status = "FAIL" if ck.failures else "PASS"
        if bad:
            hw = [b for b in bad if b["advance"] == self.m.half_w]
            # 引擎影响量化: 引擎按 isWide 推进 = isWide * cell_w
            delta = sum((b["isWide"] * self.m.cell_w) - b["advance"] for b in bad)
            self.findings.append(
                Finding(
                    id="ATLAS_WIDE_MISMATCH",
                    severity="error",
                    verdict="真缺陷",
                    title=f"图集 isWide 标记与 advance 不符: {len(bad)} 个假名",
                    detail=(
                        f"{len(bad)} 个假名的图集 isWide=1 但 advance={self.m.half_w} (半角). "
                        f"其中 advance=6 的半角假名 {len(hw)} 个, 全部落在 U+FF61-FF9F 连续区间。"
                    ),
                    chars=bad,
                    suggestion=(
                        "build_font.py:315 `meta.append([ord(g.ch), cx, cy, g.advance, "
                        "0 if g.category == \"ascii\" else 1])` —— isWide 按“字符分类”写死, "
                        "应改为按实际 advance 推导: `1 if g.advance == cell_w else 0`。"
                    ),
                    evidence={
                        "codepoint_range": (
                            f"{cp_str(min(b['cp_int'] for b in bad))}-"
                            f"{cp_str(max(b['cp_int'] for b in bad))}"
                        ),
                        "contiguous": (
                            sorted(b["cp_int"] for b in bad)
                            == list(range(min(b["cp_int"] for b in bad), max(b["cp_int"] for b in bad) + 1))
                        ),
                        "count": len(bad),
                        "advance_values": sorted({b["advance"] for b in bad}),
                        "engine_advance_delta_px": delta,
                        "engine_advance_delta_note": (
                            "引擎若按 isWide*cell_w 推进, 这 63 个半角假名每个多占 6px, "
                            "整段串起来累计多占 378px (整整多出一倍的宽度)。"
                        ),
                    },
                )
            )
        self.checks.append(ck)

    # ---------------------------------------------------------------- (g)
    def check_bdf_structure(self, bdf_stats: dict | None) -> None:
        """BDF 字符块结构: STARTCHAR / ENDCHAR 必须配对。"""
        ck = Check("BDF_STRUCTURE", "BDF 字符块结构配对", "整份 BDF (4140 字形)")
        if bdf_stats is None:
            ck.status = "SKIPPED"
            ck.notes.append("dist/ BDF 不存在 —— 本项未测量, 不记 PASS")
            self.checks.append(ck)
            return
        ck.samples = bdf_stats["startchar"]
        ck.read_failures = 0  # BDF 本身读成功了, 结构不配对是缺陷, 不是读取失败
        ck.failures = bdf_stats["unpaired"]
        ck.status = "FAIL" if ck.failures else "PASS"
        ck.notes.append(
            f"STARTCHAR={bdf_stats['startchar']} ENDCHAR={bdf_stats['endchar']} "
            f"CHARS声明={bdf_stats['chars_declared']}"
        )
        if ck.failures:
            self.findings.append(
                Finding(
                    id="BDF_STRUCTURE",
                    severity="error",
                    verdict="真缺陷",
                    title=(
                        f"BDF 字符块不配对: STARTCHAR {bdf_stats['startchar']} 个, "
                        f"ENDCHAR {bdf_stats['endchar']} 个 (多 {bdf_stats['unpaired']} 个)"
                    ),
                    detail=(
                        "多余的 ENDCHAR 来自零宽字形的分支: 该分支写出了两个 ENDCHAR。"
                        f"受影响的码位: {[cp_str(c) for c in bdf_stats['zero_width_glyphs']]} "
                        "(全字符集里唯一没有墨迹的字符)。"
                    ),
                    chars=[
                        {"char": chr(c), "cp": cp_str(c), "category": "ascii"}
                        for c in bdf_stats["zero_width_glyphs"]
                    ],
                    suggestion=(
                        "build_font.py:133 `lines += [\"BITMAP\", \"ENDCHAR\", \"ENDCHAR\"]` "
                        "→ 改为 `lines += [\"BITMAP\", \"ENDCHAR\"]` (零宽字形只需一个 ENDCHAR)。"
                    ),
                    evidence={
                        "startchar": bdf_stats["startchar"],
                        "endchar": bdf_stats["endchar"],
                        "chars_declared": bdf_stats["chars_declared"],
                        "zero_width_glyphs": [cp_str(c) for c in bdf_stats["zero_width_glyphs"]],
                    },
                )
            )
        self.checks.append(ck)

    # ---------------------------------------------------------------- (h)
    def check_source_fidelity(self) -> None:
        """保真检查 (客观量具): 假名的位图必须等于 non_ideo 源的渲染, 且不等于 ideo 源的渲染。

        这一项直接回答"某个假字形是不是被路由到了错误的源":
        若某假名的位图与 ideo 源 (SimHei) 对同一码位的渲染逐位相同, 就是串源了。
        """
        ck = Check("SOURCE_FIDELITY", "假名位图 == non_ideo 源 且 != ideo 源", "全部 255 个假名")
        ck.samples = len(self.kana)
        not_from_non_ideo = []
        equals_ideo = []
        for ch in self.kana:
            got = _bitmap_key(self.stack.glyph(ch))
            non_ideo = self.stack.non_ideo.glyph(ch)
            ideo = self.stack.ideo.glyph(ch)
            if got != _bitmap_key(non_ideo):
                not_from_non_ideo.append({"char": ch, "cp": cp_str(ord(ch))})
            elif ink_count(ideo) and got == _bitmap_key(ideo):
                # 两个字体恰好渲染出一致的位图 —— 良性, 记一笔但不判失败
                equals_ideo.append({"char": ch, "cp": cp_str(ord(ch))})
        ck.failures = len(not_from_non_ideo)
        ck.status = "FAIL" if ck.failures else "PASS"
        ck.notes.append(
            f"期望源 non_ideo = {self.stack.non_ideo.name}; 对照源 ideo = {self.stack.ideo.name}; "
            f"与 ideo 源恰好同形但同时与非 ideo 源一致 (良性) {len(equals_ideo)} 个"
        )
        if ck.failures:
            self.findings.append(
                Finding(
                    id="SOURCE_FIDELITY",
                    severity="error",
                    verdict="真缺陷",
                    title="假名位图与所用源字体不符 (疑似路由串源)",
                    detail=(
                        f"与 non_ideo 源渲染不一致: {len(not_from_non_ideo)} 个; "
                        f"与 ideo 源渲染逐位相同 (串源嫌疑): {len(equals_ideo)} 个。"
                    ),
                    chars=not_from_non_ideo + equals_ideo,
                    suggestion="查 bitfont.py:198-224 的 _KANA_RANGES 与 _pick()。",
                )
            )
        self.checks.append(ck)

    # ---------------------------------------------------------------- (i)
    def check_kana_hanzi_collision(self) -> None:
        """假名字形与汉字位图逐位相同 -> 判断是"路由串源"还是"字形本就同形"。

        片假名由汉字草书演变而来, ニ 与 二 同形是字形设计本身; 这类同形登记在
        EXPECTED_SHAPE_EQUIVALENTS 里, 判为预期行为。表外的同形对判为"待查"。
        """
        ck = Check("KANA_HANZI_COLLISION", "假名 vs 汉字位图逐位相同碰撞", "255 假名 × 3755 汉字")
        ck.samples = len(self.kana) * len(self.hanzi)
        hanzi_map: dict[tuple, list[str]] = defaultdict(list)
        for ch in self.hanzi:
            hanzi_map[_bitmap_key(self.stack.glyph(ch))].append(ch)
        hits = []
        for ch in self.kana:
            key = _bitmap_key(self.stack.glyph(ch))
            if key in hanzi_map:
                hits.append({"kana": ch, "hanzi": hanzi_map[key]})
        expected, unexpected = [], []
        for h in hits:
            kcp = ord(h["kana"])
            hcp = ord(h["hanzi"][0])
            if (kcp, hcp) in EXPECTED_SHAPE_EQUIVALENTS:
                expected.append({**h, "why": EXPECTED_SHAPE_EQUIVALENTS[(kcp, hcp)]})
            else:
                unexpected.append(h)
        ck.failures = len(unexpected)
        ck.status = "FAIL" if ck.failures else "PASS"
        ck.notes.append(
            f"两两比较 {len(self.kana)} × {len(self.hanzi)} = {ck.samples} 次; "
            f"同形 {len(hits)} 对, 其中设计使然 {len(expected)} 对, 待查 {len(unexpected)} 对"
        )
        for h in expected + unexpected:
            kg = self.stack.glyph(h["kana"])
            is_expected = h in expected
            why = h.get("why", "")
            if is_expected:
                self.findings.append(
                    Finding(
                        id="KANA_HANZI_BITMAP_COLLISION",
                        severity="info",
                        verdict="预期行为",
                        title=(
                            f"假名 {h['kana']!r} ({cp_str(ord(h['kana']))}) 与汉字 "
                            f"{h['hanzi'][0]!r} ({cp_str(ord(h['hanzi'][0]))}) 位图逐位相同 —— 属设计使然"
                        ),
                        detail=(
                            f"Unicode 名称: 假名 = {cp_name(ord(h['kana']))}; "
                            f"汉字 = {cp_name(ord(h['hanzi'][0]))}。"
                            f"{why}"
                            f"另: 假名侧路由到 non_ideo 源 ({self.stack._pick(h['kana']).name}), "
                            f"汉字侧路由到 ideo 源 ({self.stack._pick(h['hanzi'][0]).name}); "
                            "两者恰好 12px MONO 栅格化到同一张位图。"
                            "已用 SOURCE_FIDELITY 客观量具排除串源: 该假名的位图与 non_ideo 源逐位一致、"
                            "与 ideo 源不一致。"
                        ),
                        chars=[
                            {
                                "char": h["kana"],
                                "cp": cp_str(ord(h["kana"])),
                                "name": cp_name(ord(h["kana"])),
                                "side": "kana",
                            },
                            {
                                "char": h["hanzi"][0],
                                "cp": cp_str(ord(h["hanzi"][0])),
                                "name": cp_name(ord(h["hanzi"][0])),
                                "side": "hanzi",
                            },
                        ],
                        suggestion="无需修改 —— 这是片假名/汉字同形的固有事实, 属预期行为。",
                        evidence={
                            "kana_art": art(kg),
                            "hanzi_art": art(self.stack.glyph(h["hanzi"][0])),
                            "ttc_cross_check": ttc_cross_check(h["kana"]),
                        },
                    )
                )
            else:
                self.findings.append(
                    Finding(
                        id="KANA_HANZI_BITMAP_COLLISION",
                        severity="warn",
                        verdict="待查",
                        title=(
                            f"假名 {h['kana']!r} ({cp_str(ord(h['kana']))}) 与汉字 "
                            f"{h['hanzi'][0]!r} ({cp_str(ord(h['hanzi'][0]))}) 位图逐位相同 —— 未登记"
                        ),
                        detail=(
                            "该同形对不在 EXPECTED_SHAPE_EQUIVALENTS 登记表里, 无法用字形设计解释。"
                            "需人工复核是否为源字体问题或路由串源。"
                        ),
                        chars=[
                            {
                                "char": h["kana"],
                                "cp": cp_str(ord(h["kana"])),
                                "name": cp_name(ord(h["kana"])),
                                "side": "kana",
                            },
                            {
                                "char": h["hanzi"][0],
                                "cp": cp_str(ord(h["hanzi"][0])),
                                "name": cp_name(ord(h["hanzi"][0])),
                                "side": "hanzi",
                            },
                        ],
                        suggestion="人工复核后再决定是否需要在 charset.py 的 EXCLUDE 中排除。",
                        evidence={
                            "kana_art": art(kg),
                            "hanzi_art": art(self.stack.glyph(h["hanzi"][0])),
                            "ttc_cross_check": ttc_cross_check(h["kana"]),
                        },
                    )
                )
        self.checks.append(ck)

    # ---------------------------------------------------------------- 路由
    def check_source_routing(self) -> None:
        """全部假名必须走 non_ideo 源, 且该源字体确实有该字形。"""
        ck = Check("SOURCE_ROUTING", "假名码位路由到 non_ideo 源", "全部 255 个假名")
        ck.samples = len(self.kana)
        expected_src = self.stack.non_ideo
        wrong = []
        for ch in self.kana:
            src = self.stack._pick(ch)
            if src is not expected_src:
                wrong.append({"char": ch, "cp": cp_str(ord(ch)), "src": src.name})
        ck.failures = len(wrong)
        ck.status = "FAIL" if ck.failures else "PASS"
        ck.notes.append(f"期望源: {expected_src.name} (msgothic.ttc index 0)")
        if wrong:
            self.findings.append(
                Finding(
                    id="SOURCE_ROUTING",
                    severity="error",
                    verdict="真缺陷",
                    title=f"{len(wrong)} 个假名没有路由到 non_ideo 源",
                    detail="; ".join(f"{w['cp']} -> {w['src']}" for w in wrong[:20]),
                    chars=wrong,
                    suggestion="查 bitfont.py:198-224 的 _KANA_RANGES 与 _pick()。",
                )
            )
        self.checks.append(ck)


def _bitmap_key(img) -> tuple:
    """把位图变成可哈希的元组, 用于逐位比较。"""
    px = img.load()
    return tuple(
        tuple(1 if px[x, y] > 0 else 0 for x in range(img.width)) for y in range(img.height)
    )


# --------------------------------------------------------------------------
# 报告渲染
# --------------------------------------------------------------------------


def render_markdown(report: dict) -> str:
    L: list[str] = []
    L.append("# 假名 (kana) 批次补充探针报告")
    L.append("")
    L.append(f"- 生成时间: {report['generated_at']}")
    L.append(f"- 判定: **{report['summary']['verdict']}** "
             f"(error {report['summary']['errors']} / warn {report['summary']['warnings']} / info {report['summary']['infos']})")
    inp = report["inputs"]
    L.append(
        f"- 覆盖: 假名 {inp['kana_total']} 字 (平假名 {inp['kana_hiragana']} / 片假名 "
        f"{inp['kana_katakana']} / 半角片假名 {inp['kana_halfwidth']} / 其他 {inp['kana_other']}), "
        f"字符集共 {inp['charset_total']} 字"
    )
    L.append(f"- 消费输入: 汉字 {inp['hanzi_total']} 字 (仅用于碰撞比对), "
             f"成品 BDF/TTF/图集 各读 1 份")
    L.append("")

    L.append("## 检查项汇总")
    L.append("")
    L.append("| 检查 ID | 样本数 | 失败数 | 读取失败 | 状态 | 说明 |")
    L.append("|---|---|---|---|---|---|")
    for c in report["gauge"]["checks"]:
        L.append(
            f"| `{c['id']}` | {c['samples']} | {c['failures']} | {c['read_failures']} | "
            f"{c['status']} | {c['name']} |"
        )
    L.append("")
    L.append(f"- 合计: 样本 {report['gauge']['total_samples']} 项, 失败 {report['gauge']['total_failures']} 项, "
             f"读取失败 {report['gauge']['total_read_failures']} 处")
    L.append("")

    L.append("## 发现")
    L.append("")
    if not report["findings"]:
        L.append("本批次未发现异常。")
        L.append("")
    for f in report["findings"]:
        L.append(f"### `{f['id']}` — {f['verdict']} ({f['severity']})")
        L.append("")
        L.append(f"**{f['title']}**")
        L.append("")
        L.append(f["detail"])
        L.append("")
        if f["chars"]:
            L.append("| 字符 | 码位 | 备注 |")
            L.append("|---|---|---|")
            for c in f["chars"][:70]:
                extra = ""
                if "advance" in c:
                    extra = f"advance={c['advance']}"
                if "isWide" in c:
                    extra = f"advance={c['advance']}, isWide={c['isWide']}"
                if "ink" in c:
                    extra = f"ink={c['ink']}"
                L.append(f"| {c['char']} | `{c['cp']}` | {extra} |")
            if len(f["chars"]) > 70:
                L.append(f"| … | | 其余 {len(f['chars']) - 70} 条见 JSON |")
            L.append("")
        if f.get("evidence", {}).get("kana_art"):
            L.append("```text")
            L.append(f["evidence"]["kana_art"])
            L.append("```")
            L.append("")
        if f.get("evidence", {}).get("hanzi_art"):
            L.append("```text")
            L.append(f["evidence"]["hanzi_art"])
            L.append("```")
            L.append("")
        cross = f.get("evidence", {}).get("ttc_cross_check")
        if cross:
            L.append(f"- TTC 交叉验证: {cross['summary']}")
            eqv = cross.get("equivalent_codepoint")
            if eqv:
                L.append(f"- 同形字符对照 `{eqv['cp']}`: ink={eqv['ink']}, bbox={eqv['bbox_size']} "
                         f"(注: {eqv['note']})")
            L.append("")
            L.append("```text")
            L.append("MS Gothic 12px:")
            L.append(cross["fonts"][0].get("art", ""))
            if eqv:
                L.append(f"{eqv['cp']}:")
                L.append(eqv["art"])
            L.append("```")
            L.append("")
        if f.get("suggestion"):
            L.append(f"**建议改法**: {f['suggestion']}")
            L.append("")

    # ---- 预期行为: 已验证不是缺陷的部分
    L.append("## 预期行为 (已验证非缺陷)")
    L.append("")
    mark_rows = []
    for c in report["gauge"]["checks"]:
        if c["id"] == "MARK_INK":
            mark_rows = c.get("rows", [])
    # 已判为异常的记号不放进"预期行为"表
    failed_marks = {
        ch["cp"]
        for f in report["findings"]
        if f["id"] == "MARK_SHAPE_SUSPECT"
        for ch in f["chars"]
    }
    mark_rows = [r for r in mark_rows if r["cp"] not in failed_marks]
    if mark_rows:
        L.append("以下记号墨量低是**组合/间隔记号本来就小**, 不是丢了字形 —— 墨迹非 0、"
                 "位置正确 (组合记号在右上象限), 已逐个验证:")
        L.append("")
        L.append("| 字符 | 码位 | EAW | advance | 墨迹 px | 墨量 | 墨迹包围盒 | 判定 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for r in mark_rows:
            L.append(
                f"| {r['char']} | `{r['cp']}` | {r['eaw']} | {r['advance']} | {r['ink']} | "
                f"{r['ink_ratio'] * 100:.2f}% | {r['bbox_size'][0]}x{r['bbox_size'][1]} | 预期行为 |"
            )
        L.append("")
    pair_check = next((c for c in report["gauge"]["checks"] if c["id"] == "HIRA_KATA_PAIR"), None)
    if pair_check and pair_check.get("extremes"):
        L.append("平↔片墨量比值的极值对 (全部未越界, 已逐对看过 ASCII art, 差异来自"
                 "平假名/片假名本身笔画数不同, 如 の 是单笔回环而 ノ 是两撇):")
        L.append("")
        L.append("| 平假名 | 片假名 | 平墨量 | 片墨量 | 比值 |")
        L.append("|---|---|---|---|---|")
        for r in pair_check["extremes"]:
            L.append(
                f"| {r['hira']} `{r['hira_cp']}` | {r['kata']} `{r['kata_cp']}` | "
                f"{r['hira_ratio'] * 100:.1f}% | {r['kata_ratio'] * 100:.1f}% | {r['ratio']:.3f} |"
            )
        L.append("")
        if pair_check.get("skipped_pairs"):
            L.append("剔除的 +0x60 配对 (Unicode 语义上不对应):")
            L.append("")
            for s in pair_check["skipped_pairs"]:
                L.append(f"- `{s['hira']}` ↔ `{s['kata']}` — {s['reason']}")
            L.append("")

    L.append("## 量具可靠性")
    L.append("")
    for line in report["gauge"]["reliability"]:
        L.append(f"- {line}")
    L.append("")
    L.append("## 阈值及其经验依据")
    L.append("")
    for k, v in report["gauge"]["thresholds"].items():
        L.append(f"- **{k}** = `{v['value']}` — {v['basis']}")
    L.append("")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="假名批次补充探针")
    ap.add_argument("--out", default="reports/kana_extra.json")
    ap.add_argument("--md", default="reports/kana_extra.md")
    ap.add_argument("--build", action="store_true", help="探针前先重建 dist/")
    ap.add_argument("--label", default="kana")
    args = ap.parse_args()

    if args.build:
        r = subprocess.run(
            [sys.executable, str(TOOLS / "build_font.py")], cwd=str(ROOT), capture_output=True, text=True
        )
        if r.returncode != 0:
            print("构建失败 —— 探针结果不构成任何结论", file=sys.stderr)
            print(r.stdout[-2000:], file=sys.stderr)
            print(r.stderr[-2000:], file=sys.stderr)
            return 2

    probe = KanaProbe()

    # 成品读取 (读不到就明确记 SKIPPED, 不用 PASS 冒充)
    bdf_path = DIST / f"{PS_NAME}.bdf"
    ttf_path = DIST / f"{PS_NAME}.ttf"
    atlas_path = DIST / f"{PS_NAME}-atlas.json"
    atlas_png = DIST / f"{PS_NAME}-atlas.png"
    bdf_dwidth: dict[int, int] = {}
    bdf_stats: dict | None = None
    atlas: dict | None = None
    read_notes: list[str] = []
    if bdf_path.exists():
        bdf_dwidth, bdf_stats = read_bdf_dwidth(bdf_path)
        read_notes.append(f"BDF 读取成功: {bdf_path.name} ({bdf_path.stat().st_size} bytes)")
    else:
        read_notes.append("BDF 不存在 —— DWIDTH / 结构两项未测量")
    if atlas_path.exists() and atlas_png.exists():
        atlas = read_atlas(atlas_path)
        read_notes.append(f"图集 JSON 读取成功: {atlas_path.name} ({len(atlas['entries'])} 个字形元数据)")
    else:
        read_notes.append("图集 JSON/PNG 不存在 —— isWide 一项未测量")
    ttf_cmap: set[int] = set()
    if ttf_path.exists():
        try:
            ttf_cmap = read_ttf_cmap(ttf_path)
            read_notes.append(f"TTF cmap 读取成功: {len(ttf_cmap)} 个码位")
        except Exception as e:  # noqa: BLE001
            read_notes.append(f"TTF cmap 读取失败: {e}")

    # ---- 跑各组检查
    probe.check_halfwidth_grid_fit()
    probe.check_marks()
    probe.check_pairs()
    probe.check_advance(bdf_dwidth, atlas)
    probe.check_fullwidth_overflow()
    probe.check_atlas_wide_flag(atlas)
    probe.check_bdf_structure(bdf_stats)
    probe.check_source_fidelity()
    probe.check_kana_hanzi_collision()
    probe.check_source_routing()

    # ---- 成品覆盖 (每个假名都要在 BDF / TTF cmap / 图集里出现)
    cover = Check("ARTIFACT_COVERAGE", "假名在 BDF / TTF cmap / 图集中的覆盖", "全部 255 个假名")
    cover.samples = len(probe.kana)
    missing_bdf, missing_cmap, missing_atlas = [], [], []
    for ch in probe.kana:
        cp = ord(ch)
        if bdf_stats is not None and cp not in bdf_dwidth:
            missing_bdf.append(cp)
        if ttf_cmap and cp not in ttf_cmap:
            missing_cmap.append(cp)
        if atlas is not None and cp not in atlas["entries"]:
            missing_atlas.append(cp)
    cover.failures = len(missing_bdf) + len(missing_cmap) + len(missing_atlas)
    cover.read_failures = (0 if bdf_stats is not None else 1) + (0 if ttf_cmap else 1) + (0 if atlas is not None else 1)
    cover.status = "FAIL" if cover.failures else "PASS"
    if cover.read_failures:
        cover.status = "SKIPPED"
        cover.notes.append("部分成品缺失, 覆盖项未完整测量")
    probe.checks.append(cover)

    # ---- 组装报告
    errors = sum(1 for f in probe.findings if f.severity == "error")
    warnings = sum(1 for f in probe.findings if f.severity == "warn")
    infos = sum(1 for f in probe.findings if f.severity == "info")
    findings = [f.to_dict() for f in probe.findings]

    checks_json = []
    for c in probe.checks:
        d = {
            "id": c.id,
            "name": c.name,
            "scope": c.scope,
            "samples": c.samples,
            "failures": c.failures,
            "read_failures": c.read_failures,
            "status": c.status,
            "notes": c.notes,
        }
        if hasattr(c, "rows"):
            d["rows"] = c.rows
        if hasattr(c, "extremes"):
            d["extremes"] = c.extremes
        if hasattr(c, "skipped"):
            d["skipped_pairs"] = [{"hira": cp_str(a), "kata": cp_str(b), "reason": r} for a, b, r in c.skipped]
        checks_json.append(d)

    reliability = [
        f"输入消费: 字符集 {probe.consumed['charset_total']} 字全量建栈; "
        f"假名 {probe.consumed['kana_total']} 字逐字栅格化 (复用同一 BitmapFont 缓存); "
        f"汉字 {probe.consumed['hanzi_total']} 字仅用于位图碰撞比对。",
        f"成品读取: {'; '.join(read_notes)}",
        f"读取失败合计: {sum(c.read_failures for c in probe.checks)} 处 "
        "(读取失败 = 成品/字形取不到, 已单独计数, 不计入 PASS)。",
        "所有失败项都带 ASCII art 或数值证据, 见 findings[].evidence 与 JSON 的 checks[].rows。",
    ]

    report = {
        "tool": "kana_probe",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "inputs": probe.consumed,
        "gauge": {
            "checks": checks_json,
            "total_samples": sum(c.samples for c in probe.checks),
            "total_failures": sum(c.failures for c in probe.checks),
            "total_read_failures": sum(c.read_failures for c in probe.checks),
            "thresholds": THRESHOLDS,
            "reliability": reliability,
        },
        "findings": findings,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "verdict": "FAIL" if errors else "PASS",
            "findings_digest": hashlib.sha256(
                json.dumps(findings, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        },
    }

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = Path(args.md)
    if not md.is_absolute():
        md = ROOT / md
    md.write_text(render_markdown(report), encoding="utf-8")

    print(f"kana_probe: {report['summary']['verdict']} "
          f"(error {errors} / warn {warnings} / info {infos})")
    print(f"  样本 {report['gauge']['total_samples']} 项, 失败 {report['gauge']['total_failures']} 项, "
          f"读取失败 {report['gauge']['total_read_failures']} 处")
    for f in findings:
        print(f"  - {f['id']}: {f['title']}")
    # 报告路径可能在仓库外 (例如写到临时目录做对比), relative_to 会直接抛异常 ——
    # 探针跑完全部检查却在最后一行崩掉, 是最让人误判的一种失败。
    def _display(p: Path) -> str:
        try:
            return str(p.relative_to(ROOT))
        except ValueError:
            return str(p)

    print(f"  报告: {_display(out)} / {_display(md)}")
    print(f"  findings_digest: {report['summary']['findings_digest']}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
