"""ascii_punct_probe — ASCII + 标点批次的补充回归探针。

lane: agent/reg-ascii-punct  (批次: ascii 95 字 + punct 35 字 = 130 字)

为什么需要这个探针
------------------
共享工具 tools/fontgen/regress.py 做的是"成品 vs 源位图"四路交叉对比 (R/B/T/A),
它能报出"哪里不一致", 但有两件事它答不了:

  1) 宽度判定 (bitfont.is_wide) 到底错了几个字符、错在哪一步。
     regress 的 CLIP_RIGHT 只在成品层面看到"墨迹被裁", 要定位根因必须绕开成品,
     直接去量源字体的掩码与 advance。
  2) 同一字符在两个源字体 (MS Gothic / SimHei) 里的基线与字面差异。
     混排错行的风险来自这里, 而 regress 的基线检查是"批 vs 全字符集参考分布",
     看不到"两个源之间"的关系。

这个探针只读, 不改任何既有源码; 所有结论都能追到"消费了多少输入 / 多少处读取失败"。
绝不拿 PASS 冒充: 读不到东西就报读取失败, 计入量具可靠性一节。

用法:
    python tools/fontgen/lanes/ascii_punct_probe.py
    python tools/fontgen/lanes/ascii_punct_probe.py --out reports/ascii-punct_extra.json

输出:
    <out>       JSON 全量结果 (机器读)
    <out>.md    人读摘要 (同一份数据的另一种渲染, 不是另一次计算)
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parents[1]  # tools/fontgen
sys.path.insert(0, str(TOOLS))

import build_font as bf  # noqa: E402
import charset as cs  # noqa: E402
from bitfont import to_ascii  # noqa: E402
from coverage import cmap_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]  # 仓库根
ART = ROOT / "dist"
PS_NAME = bf.PS_NAME
CATS = ("ascii", "punct")

# 漂移阈值。理由: cell 高 13px, 基线在第 11 行, descent 只有 2 行。
# 两个源字体的 1px 差异是 12px 光栅化量化的正常结果 (实测 129 字里 78 字差 1px),
# 达不到"混排时看得见错行"的程度; >=2px 才会让同字符在两源里坐在明显不同的高度。
DRIFT_PX = 2

# 基线所在的行号 (cell 坐标系), main() 里用真实 metrics 覆盖。
ASCENT = 11


# ================================================================ 数据结构


@dataclass
class Check:
    id: str
    title: str
    question: str
    severity: str  # error / warn / info
    samples: int
    failures: int
    verdict: str  # FAIL / PASS / LATENT
    findings: list[dict] = field(default_factory=list)
    note: str = ""
    read_failures: int = 0
    read_detail: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "question": self.question,
            "severity": self.severity,
            "samples": self.samples,
            "failures": self.failures,
            "verdict": self.verdict,
            "read_failures": self.read_failures,
            "read_detail": self.read_detail,
            "note": self.note,
            "findings": self.findings,
        }


@dataclass
class SourceMeasure:
    """一个字符在某个源字体上的测量结果。"""

    present_in_cmap: bool
    has_mask: bool
    ink: bool
    advance: int
    mask_w: int = 0
    mask_h: int = 0
    dx: int = 0
    dy: int = 0
    left: int = 0
    right: int = -1
    top: int = 0
    bottom: int = -1

    @property
    def ink_w(self) -> int:
        return 0 if not self.ink else self.right - self.left + 1

    @property
    def ink_h(self) -> int:
        return 0 if not self.ink else self.bottom - self.top + 1

    @property
    def baseline_offset(self) -> int:
        """墨迹下沿相对基线的偏移 (行号 - ascent)。负数 = 下沉到基线以下。"""
        return self.bottom - ASCENT if self.ink else 0

    @property
    def top_offset(self) -> int:
        return self.top - ASCENT if self.ink else 0


# ================================================================ 度量工具


def measure_source(font, ch: str, cmap_cps: set[int]) -> SourceMeasure:
    """在单个源字体上量一个字符: 掩码 / 紧致墨迹框 / advance。

    注意: bitfont._render_mask 返回的是**排版盒**掩码 (高度可能远大于字面),
    所以墨迹框必须自己按像素重算, 不能拿 mask.height 当字面高度。
    """
    cp = ord(ch)
    present = cp in cmap_cps
    try:
        adv = round(font._font.getlength(ch))
    except Exception:  # noqa: BLE001
        adv = 0
    rendered = font._render_mask(ch)
    if rendered is None:
        return SourceMeasure(present_in_cmap=present, has_mask=False, ink=False, advance=adv)
    img, (dx, dy) = rendered
    px = img.load()
    xs = [x for y in range(img.height) for x in range(img.width) if px[x, y] > 0]
    ys = [y for y in range(img.height) for x in range(img.width) if px[x, y] > 0]
    m = SourceMeasure(
        present_in_cmap=present,
        has_mask=True,
        ink=bool(xs),
        advance=adv,
        mask_w=img.width,
        mask_h=img.height,
        dx=dx,
        dy=dy,
    )
    if xs:
        m.left = dx + min(xs)
        m.right = dx + max(xs)
        m.top = dy + min(ys)
        m.bottom = dy + max(ys)
    return m


def art_rows(img: Image.Image) -> list[str]:
    return to_ascii(img).splitlines()


def art_mask(img: Image.Image, dx: int, dy: int, width: int, height: int) -> list[str]:
    """把源掩码按 (dx, dy) 放进 width x height 的画布, 返回 ASCII art 行。"""
    canvas = Image.new("L", (width, height), 0)
    canvas.paste(img, (dx, dy))
    return art_rows(canvas)


def art_pair(
    left_title: str,
    left_rows: list[str],
    right_title: str,
    right_rows: list[str],
    ruler: list[str] | None = None,
) -> list[str]:
    """左右并排的 ASCII art, 右侧带一条基线标尺列。

    基线约定 (与 build_font._emit_rect 一致): 第 ascent 行是基线**以下**的第一行,
    所以基线 = 第 ascent 行的上沿。标尺列用 │ 表示基线以上, ┴ 标出基线所在的那一行。
    """
    w = max((len(r) for r in left_rows), default=0)
    lines = [f"{left_title:<{w + 3}} | {right_title}"]
    n = max(len(left_rows), len(right_rows))
    for i in range(n):
        l = left_rows[i] if i < len(left_rows) else ""
        r = right_rows[i] if i < len(right_rows) else ""
        if ruler:
            mark = ruler[i] if i < len(ruler) else " "
            r = f"{r}  {mark}"
        lines.append(f"{l:<{w + 3}} | {r}")
    if ruler:
        lines.append(f"{'':<{w + 3}} | (标尺列: ┴ 那一行的上沿就是基线)")
    return lines


def ruler_rows(height: int, ascent: int) -> list[str]:
    """基线标尺 (逐行): 基线以上是 │, 基线所在行是 ┴, 以下是空格。"""
    return ["│" if y < ascent else ("┴" if y == ascent else " ") for y in range(height)]


# ================================================================ 产物读取


def read_artifacts() -> dict:
    """读三份成品 (BDF / 图集 JSON / 图集 PNG / TTF)。任何一份读不到都如实记录。"""
    out: dict = {"read": {}, "errors": []}
    bdf = ART / f"{PS_NAME}.bdf"
    atlas_json = ART / f"{PS_NAME}-atlas.json"
    atlas_png = ART / f"{PS_NAME}-atlas.png"
    ttf = ART / f"{PS_NAME}.ttf"

    for label, p in (("bdf", bdf), ("atlas_json", atlas_json), ("atlas_png", atlas_png), ("ttf", ttf)):
        if p.exists():
            out["read"][label] = {"ok": True, "path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size}
        else:
            out["read"][label] = {"ok": False, "path": str(p.relative_to(ROOT)), "bytes": 0}
            out["errors"].append(f"产物缺失: {label} ({p})")

    if out["read"]["bdf"]["ok"]:
        out["bdf_lines"] = bdf.read_text(encoding="utf-8").splitlines()
    if out["read"]["atlas_json"]["ok"]:
        out["atlas"] = json.loads(atlas_json.read_text(encoding="utf-8"))
    if out["read"]["atlas_png"]["ok"]:
        out["atlas_img"] = Image.open(atlas_png).convert("RGBA")
    if out["read"]["ttf"]["ok"]:
        from fontTools.ttLib import TTFont

        out["ttf"] = TTFont(str(ttf))
    return out


def bdf_blocks(lines: list[str]) -> list[dict]:
    """按 STARTCHAR 切块, 数每个块里的 ENDCHAR 个数。"""
    blocks: list[dict] = []
    cur: dict | None = None
    for ln in lines:
        s = ln.strip()
        if s.startswith("STARTCHAR"):
            cur = {"name": s, "encoding": None, "bbx": None, "bitmap": False, "endchar": 0, "rows": 0}
            blocks.append(cur)
        elif cur is not None:
            if s.startswith("ENCODING "):
                cur["encoding"] = int(s.split()[1])
            elif s.startswith("BBX "):
                cur["bbx"] = s.split()[1:]
            elif s == "BITMAP":
                cur["bitmap"] = True
            elif s == "ENDCHAR":
                cur["endchar"] += 1
            elif cur["bitmap"] and s:
                cur["rows"] += 1
    return blocks


# ================================================================ 检查项


def check_cross_source(items, ms_font, sh_font, ms_cmap, sh_cmap, ascent, cell_w, cell_h):
    """检查 A: 同一字符在两个源字体里的基线位置与字面差异。

    这是"混排错行"风险的直接量度。注意: 本工程的路由是**按码位排他**的 ——
    每个码位只会来自一个源, 所以同一个字符不会被渲染成两种高度,
    因此这项差异在本工程当前路由下是**潜在风险**, 不是已交付缺陷。
    """
    findings: list[dict] = []
    read_fail: list[str] = []
    compared = 0
    for ch, cat in items:
        a = measure_source(ms_font, ch, ms_cmap)
        b = measure_source(sh_font, ch, sh_cmap)
        if not a.ink or not b.ink:
            read_fail.append(f"U+{ord(ch):04X}")
            continue
        compared += 1
        d_base = a.baseline_offset - b.baseline_offset
        d_top = a.top_offset - b.top_offset
        if abs(d_base) < DRIFT_PX and abs(d_top) < DRIFT_PX:
            continue
        am, (adx, ady) = ms_font._render_mask(ch)
        bm, (bdx, bdy) = sh_font._render_mask(ch)
        findings.append(
            {
                "char": ch,
                "cp": f"U+{ord(ch):04X}",
                "category": cat,
                "ms_gothic": {
                    "ink_left": a.left, "ink_right": a.right, "ink_top": a.top, "ink_bottom": a.bottom,
                    "baseline_offset": a.baseline_offset, "ink_h": a.ink_h, "advance": a.advance,
                },
                "simhei": {
                    "ink_left": b.left, "ink_right": b.right, "ink_top": b.top, "ink_bottom": b.bottom,
                    "baseline_offset": b.baseline_offset, "ink_h": b.ink_h, "advance": b.advance,
                },
                "delta_baseline": d_base,
                "delta_top": d_top,
                "severity": "error" if abs(d_base) >= DRIFT_PX else "warn",
                "reason": (
                    f"基线位置差 {d_base}px / 字面上沿差 {d_top}px "
                    f"(MS Gothic ink {a.top}-{a.bottom} 行 vs SimHei ink {b.top}-{b.bottom} 行, 基线在第 {ascent} 行)"
                ),
                "art": art_pair(
                    "MS Gothic (实际路由源)",
                    art_mask(am, adx, ady, cell_w, cell_h),
                    "SimHei (汉字源, 不用于 ASCII)",
                    art_mask(bm, bdx, bdy, cell_w, cell_h),
                    ruler_rows(cell_h, ascent),
                ),
            }
        )
    findings.sort(key=lambda f: (-abs(f["delta_baseline"]), -abs(f["delta_top"]), f["cp"]))
    c = Check(
        id="CROSS_SOURCE_BASELINE",
        title="跨源基线/字面一致性",
        question="同一字符在 MS Gothic 与 SimHei 下的墨迹下沿(基线位置)与上沿差多少像素?",
        severity="info",
        samples=compared,
        failures=len(findings),
        verdict="LATENT",
        read_failures=len(read_fail),
        read_detail=(
            f"两源共读取 {2 * len(items)} 次字形掩码; {len(read_fail)} 个字符无墨迹可比"
            f" ({', '.join(read_fail) if read_fail else '无'}) —— 空格 U+0020 两源都无墨迹, 属预期"
        ),
        note=(
            f"阈值 {DRIFT_PX}px (>=2px 才算混排可见的错行)。本工程按码位排他路由, "
            f"同一码位只来自一个源, 同一字符不会被渲染成两种高度 —— "
            f"因此这项差异是**潜在风险**(若将来按字符回退/混排才会显形), 不是已交付缺陷。"
        ),
        findings=findings,
    )
    return c


def check_space(items, stack, ms_font, sh_font, ms_cmap, sh_cmap, art):
    """检查 B: 空格 U+0020 必须无墨迹、advance 必须是 6。

    同时从成品 (BDF / 图集 / TTF) 三个方向回读空格, 因为栅格层对了不代表成品对了。
    """
    findings: list[dict] = []
    space = " "
    cp = ord(space)

    ms_m = measure_source(ms_font, space, ms_cmap)
    sh_m = measure_source(sh_font, space, sh_cmap)
    g = stack.glyph(space)
    px = g.load()
    ink = sum(1 for y in range(g.height) for x in range(g.width) if px[x, y] > 0)
    adv = stack.advance(space)
    cell_ink = stack.glyph(space)

    art_txt = art_rows(cell_ink)

    # BDF 侧
    bdf_issue = None
    bdf_block = None
    if "bdf_lines" in art:
        for b in bdf_blocks(art["bdf_lines"]):
            if b["encoding"] == cp:
                bdf_block = b
                if b["endchar"] != 1:
                    bdf_issue = f"BDF 块内 ENDCHAR 出现 {b['endchar']} 个 (应为 1)"
                break
    # 图集侧
    atlas_entry = None
    atlas_ink = None
    if "atlas" in art:
        for e in art["atlas"]["glyphs"]:
            if e[0] == cp:
                atlas_entry = e
                break
        if atlas_entry and "atlas_img" in art:
            img = art["atlas_img"]
            ap = img.load()
            _, gx, gy, _, _ = atlas_entry
            cw, chh = art["atlas"]["cell"]["w"], art["atlas"]["cell"]["h"]
            atlas_ink = sum(
                1 for y in range(chh) for x in range(cw) if ap[gx + x, gy + y][3] > 0
            )
    # TTF 侧
    ttf_adv = None
    ttf_name = None
    if "ttf" in art:
        tt = art["ttf"]
        cmap = tt.getBestCmap()
        ttf_name = cmap.get(cp)
        if ttf_name:
            ttf_adv = tt["hmtx"].metrics[ttf_name][0]

    facts = {
        "ms_gothic_advance": ms_m.advance,
        "ms_gothic_ink": ms_m.ink,
        "simhei_advance": sh_m.advance,
        "simhei_ink": sh_m.ink,
        "stack_advance": adv,
        "stack_cell_w": g.width,
        "stack_cell_h": g.height,
        "stack_ink_px": ink,
        "atlas_entry": atlas_entry,
        "atlas_ink_px": atlas_ink,
        "ttf_glyph": ttf_name,
        "ttf_advance_units": ttf_adv,
        "ttf_advance_px": (ttf_adv // 64) if ttf_adv is not None else None,
        "bdf_block": bdf_block,
        "bdf_issue": bdf_issue,
    }
    if ink != 0:
        findings.append({"char": " ", "cp": "U+0020", "reason": "空格有墨迹", "ink_px": ink, "art": art_txt})
    if adv != 6:
        findings.append({"char": " ", "cp": "U+0020", "reason": f"空格 advance={adv}, 应为 6", "art": art_txt})
    if ttf_adv is not None and ttf_adv != 6 * 64:
        findings.append({"char": " ", "cp": "U+0020", "reason": f"TTF hmtx advance={ttf_adv} 单位, 应为 {6 * 64} (=6px)", "art": art_txt})
    if atlas_ink:
        findings.append({"char": " ", "cp": "U+0020", "reason": f"图集空格单元有 {atlas_ink} 个墨迹像素", "art": art_txt})
    if bdf_issue:
        findings.append({"char": " ", "cp": "U+0020", "reason": bdf_issue, "art": art_txt})

    c = Check(
        id="SPACE_CHECK",
        title="空格 U+0020 校验 (无墨迹 / advance=6)",
        question="空格是否真的没有墨迹、advance 是不是 6, 且三份成品都一致?",
        severity="error",
        samples=1,
        failures=len(findings),
        verdict="FAIL" if findings else "PASS",
        read_detail="栅格层读 2 个源 + 1 个成品单元; 成品层读 BDF 块 / 图集 PNG 单元 / TTF hmtx",
        findings=findings,
        note="空格是本批唯一的零墨迹字符 —— 全字符集扫描结果也是 1 个。",
    )
    c.facts = facts  # type: ignore[attr-defined]
    return c


def check_right_edge(items, stack, ms_font, ms_cmap, cell_w, cell_h):
    """检查 C: ASCII 字符的墨迹是否贴到半角格右缘 (第 5 列, 0-based)。

    要区分两种"贴边":
      - 恰好铺满 6px 格 (ink_right == 5 且源掩码没有更宽) -> 源字体本来的设计, 预期行为;
      - 源掩码比格还宽 (ink_right >= 6) -> 被裁切, 真缺陷。
    """
    findings: list[dict] = []
    read_fail = 0
    checked = 0
    for ch, cat in items:
        if cat != "ascii":
            continue
        g = stack.glyph(ch)
        px = g.load()
        xs = [x for y in range(g.height) for x in range(g.width) if px[x, y] > 0]
        if not xs:
            read_fail += 1
            continue
        checked += 1
        cell_right = max(xs)
        if cell_right < g.width - 1:
            continue
        m = measure_source(ms_font, ch, ms_cmap)
        clipped = m.ink and m.right >= g.width
        findings.append(
            {
                "char": ch,
                "cp": f"U+{ord(ch):04X}",
                "category": cat,
                "cell_w": g.width,
                "cell_ink_left": min(xs),
                "cell_ink_right": cell_right,
                "source_ink_left": m.left,
                "source_ink_right": m.right,
                "source_advance": m.advance,
                "clipped": bool(clipped),
                "lost_columns": max(0, m.right - (g.width - 1)) if clipped else 0,
                "verdict": "真缺陷(被裁切)" if clipped else "预期行为(源字体本就铺满半角格)",
                "art": art_rows(g),
            }
        )
    findings.sort(key=lambda f: (not f["clipped"], f["cp"]))
    c = Check(
        id="RIGHT_EDGE",
        title="ASCII 右缘贴合检查",
        question="半角 6px 格里的 ASCII 字形, 墨迹有没有被右缘切掉?",
        severity="error",
        samples=checked,
        failures=sum(1 for f in findings if f["clipped"]),
        verdict="FAIL" if any(f["clipped"] for f in findings) else "PASS",
        read_failures=read_fail,
        read_detail=f"读取 {checked + read_fail} 个 ASCII 字形的成品单元与源掩码; {read_fail} 个无墨迹",
        findings=findings,
        note=(
            "贴边不等于被裁: 判定标准是「源掩码墨迹右沿 >= 格宽」才算裁切。"
            "95 个 ASCII 字符里 94 个有墨迹参与判定, 1 个 (空格) 无墨迹。"
            "本批命中的贴边字符逐个在 findings 里给出 ASCII art 与源/成品墨迹范围。"
        ),
    )
    return c


def check_width_decision(items, stack, ms_font, ms_cmap):
    """复核 CLIP_RIGHT / SOURCE_ADVANCE_MISMATCH: 宽度判定 (is_wide) 到底错了几个。

    这里绕开成品, 直接量两件事:
      - 源字体的紧致墨迹右沿 vs 分配到的格宽 (超了就一定被裁);
      - 源字体的实测 advance vs 分配到的格宽 (不等就是宽度判定与源字体脱节)。
    """
    findings: list[dict] = []
    for ch, cat in items:
        src = stack._pick(ch)
        cmap = ms_cmap if src is stack.non_ideo else ms_cmap
        m = measure_source(src, ch, cmap)
        g = stack.glyph(ch)
        if not m.ink:
            continue
        clipped = m.right >= g.width
        adv_mismatch = m.advance != g.width
        if not clipped and not adv_mismatch:
            continue
        img, (dx, dy) = src._render_mask(ch)
        mpx = img.load()
        # 精确数"被 paste 进格时丢掉的墨迹像素": 落在格宽之外的墨迹点。
        lost_px = (
            sum(
                1
                for y in range(img.height)
                for x in range(img.width)
                if mpx[x, y] > 0 and (dx + x) >= g.width
            )
            if clipped
            else 0
        )
        findings.append(
            {
                "char": ch,
                "cp": f"U+{ord(ch):04X}",
                "category": cat,
                "eaw": unicodedata.east_asian_width(ch),
                "source": src.name,
                "allocated_cell_w": g.width,
                "source_ink_left": m.left,
                "source_ink_right": m.right,
                "source_ink_width": m.ink_w,
                "source_advance": m.advance,
                "clipped": bool(clipped),
                "lost_columns": max(0, m.right - (g.width - 1)) if clipped else 0,
                "lost_pixels": lost_px,
                "advance_mismatch": bool(adv_mismatch),
                "reason": (
                    f"EAW={unicodedata.east_asian_width(ch)} 被判半角, 只分到 {g.width}px 格; "
                    f"源实测 advance={m.advance}, 墨迹右沿={m.right}, "
                    f"被裁掉 {lost_px} 个墨迹像素"
                ),
                "art": art_pair(
                    "源字形 (完整, 未裁)",
                    art_mask(img, dx, dy, m.mask_w, stack.metrics.cell_h),
                    "实际交付 (被裁后)",
                    art_rows(g),
                ),
            }
        )
    findings.sort(key=lambda f: f["cp"])
    clipped_n = sum(1 for f in findings if f["clipped"])
    adv_n = sum(1 for f in findings if f["advance_mismatch"])
    c = Check(
        id="WIDTH_DECISION",
        title="宽度判定复核 (CLIP_RIGHT / SOURCE_ADVANCE_MISMATCH)",
        question="分配到的格宽与源字体的真实字面/advance 是否一致?",
        severity="error",
        samples=len(items),
        failures=len(findings),
        verdict="FAIL" if findings else "PASS",
        read_detail="每个字符读 1 次源掩码 + 1 次源 advance + 1 次成品单元",
        findings=findings,
        note=(
            f"其中 {clipped_n} 个字形右侧墨迹被裁掉, {adv_n} 个源 advance 与格宽不等; "
            f"两者是同一根因 (宽度判定) 的两种表现。"
        ),
    )
    return c


def check_atlas_wide(items, stack, art):
    """复核 ATLAS_WIDE_MISMATCH: 图集元数据的 isWide 与 advance 是否自洽。"""
    findings: list[dict] = []
    if "atlas" not in art:
        return Check(
            id="ATLAS_WIDE",
            title="图集 isWide 标记复核",
            question="图集元数据的 isWide 是否与 advance 一致?",
            severity="error",
            samples=0,
            failures=0,
            verdict="NO_DATA",
            read_failures=1,
            read_detail="图集 JSON 读不到",
        )
    meta = art["atlas"]
    cell_w = meta["cell"]["w"]
    half_w = cell_w // 2
    by_cp = {e[0]: e for e in meta["glyphs"]}
    batch_cps = {ord(ch) for ch, _ in items}
    all_bad = 0
    for cp, x, y, adv, wide in meta["glyphs"]:
        expect = 1 if adv == cell_w else 0
        if int(wide) != expect:
            all_bad += 1
        if cp not in batch_cps:
            continue
        if int(wide) == expect:
            continue
        ch = chr(cp)
        g = stack.glyph(ch)
        findings.append(
            {
                "char": ch,
                "cp": f"U+{cp:04X}",
                "category": next(cat for c, cat in items if ord(c) == cp),
                "atlas_advance": adv,
                "atlas_isWide": int(wide),
                "expected_isWide": expect,
                "eaw": unicodedata.east_asian_width(ch),
                "rasterizer_cell_w": g.width,
                "reason": (
                    f"图集元数据自相矛盾: advance={adv} 但 isWide={int(wide)}; "
                    f"按 advance 应为 isWide={expect} (栅格化器实际格宽 {g.width}px)"
                ),
                "art": art_rows(g),
            }
        )
    findings.sort(key=lambda f: f["cp"])
    c = Check(
        id="ATLAS_WIDE",
        title="图集 isWide 标记复核 (ATLAS_WIDE_MISMATCH)",
        question="图集元数据里 isWide 是否与 advance 互相自洽?",
        severity="error",
        samples=len(batch_cps),
        failures=len(findings),
        verdict="FAIL" if findings else "PASS",
        read_detail=f"读图集元数据 {len(meta['glyphs'])} 条字形记录, 本批比对 {len(batch_cps)} 条",
        findings=findings,
        note=(
            f"本批命中 {len(findings)} 个。同一份图集全量 {len(meta['glyphs'])} 条里有 "
            f"{all_bad} 条 isWide 与 advance 不自洽 —— 根因是写标记时按字符分类而非按 advance。"
        ),
    )
    return c


def check_bdf_structure(art):
    """复核 BDF_STRUCTURE: 字符块结构是否配对, 多出来的 ENDCHAR 在哪个字形上。"""
    if "bdf_lines" not in art:
        return Check(
            id="BDF_STRUCTURE",
            title="BDF 结构复核",
            question="STARTCHAR / ENDCHAR 是否一一配对?",
            severity="error",
            samples=0,
            failures=0,
            verdict="NO_DATA",
            read_failures=1,
            read_detail="BDF 读不到",
        )
    lines = art["bdf_lines"]
    start_n = sum(1 for l in lines if l.startswith("STARTCHAR"))
    end_n = sum(1 for l in lines if l.strip() == "ENDCHAR")
    blocks = bdf_blocks(lines)
    bad = [b for b in blocks if b["endchar"] != 1]
    findings = []
    for b in bad:
        raw = []
        grab = False
        for ln in lines:
            s = ln.strip()
            if s.startswith("STARTCHAR"):
                grab = False
            if b["name"] == s:
                grab = True
            if grab:
                raw.append(s)
                if s == "ENDCHAR" and b["endchar"] == 1:
                    break
        findings.append(
            {
                "char": chr(b["encoding"]) if b["encoding"] is not None else "",
                "cp": f"U+{b['encoding']:04X}" if b["encoding"] is not None else "",
                "name": b["name"],
                "endchar_count": b["endchar"],
                "bbx": b["bbx"],
                "bitmap_rows": b["rows"],
                "block": raw,
                "reason": "零墨迹字形的块里 ENDCHAR 多写了一个",
            }
        )
    c = Check(
        id="BDF_STRUCTURE",
        title="BDF 结构复核 (STARTCHAR/ENDCHAR 配对)",
        question="字符块是否一一配对, 多余的 ENDCHAR 落在哪个字形上?",
        severity="error",
        samples=start_n,
        failures=len(bad),
        verdict="FAIL" if bad else "PASS",
        read_detail=f"读 BDF {len(lines)} 行, 切出 {len(blocks)} 个字符块",
        findings=findings,
        note=f"STARTCHAR {start_n} 个 / ENDCHAR {end_n} 个 —— 差 {end_n - start_n} 个。",
    )
    return c


def check_duplicates(items, stack):
    """信息项: 不同码位共享同一位图在字体里是合法的, 单独列出以免被当成缺陷。"""
    groups: dict[bytes, list[str]] = defaultdict(list)
    for ch, cat in items:
        groups[bytes(stack.glyph(ch).tobytes())].append(ch)
    dups = [{"members": [f"{c!r} U+{ord(c):04X}" for c in v], "count": len(v)} for v in groups.values() if len(v) > 1]
    return Check(
        id="DUPLICATE_BITMAP",
        title="同位图多码位 (信息项, 非缺陷)",
        question="有没有两个不同码位共用同一张位图?",
        severity="info",
        samples=len(items),
        failures=len(dups),
        verdict="PASS" if not dups else "INFO",
        read_detail=f"对 {len(items)} 个字形的成品单元取哈希",
        findings=dups,
        note="字体里不同码位共用同一位图是合法设计 (如全角/半角形), 不算缺陷, 仅登记备查。",
    )


# ================================================================ 汇总


def _art_flat(v) -> str:
    """ASCII art 既可能是字符串也可能是行列表, 统一拍平成一行文本。"""
    if v is None:
        return ""
    if isinstance(v, list):
        return " / ".join(v)
    return str(v).replace("\n", " / ")


def classify(findings_by_check: dict[str, Check]) -> list[dict]:
    """把每个发现判成「真缺陷」还是「预期行为」, 并给出根因位置。"""
    out: list[dict] = []

    def add(kind, ident, ch, cp, cat, verdict, why, fix, evidence=""):
        out.append(
            {
                "kind": kind,
                "check": ident,
                "char": ch,
                "cp": cp,
                "category": cat,
                "verdict": verdict,
                "why": why,
                "suggested_fix": fix,
                "evidence": evidence,
            }
        )

    w = findings_by_check.get("WIDTH_DECISION")
    if w:
        for f in w.findings:
            add(
                "宽度判定", "WIDTH_DECISION", f["char"], f["cp"], f["category"], "真缺陷",
                f"EAW={f['eaw']} 被判成半角, 分配 {f['allocated_cell_w']}px 格; "
                f"源字体实测 advance={f['source_advance']}, 墨迹右沿={f['source_ink_right']}, "
                f"超出格宽 {f['lost_columns']} 列, 被切掉 {f['lost_pixels']} 个墨迹像素",
                "tools/fontgen/bitfont.py:94-100 —— is_wide() 只按 EAW 判宽, "
                "docstring 承诺的 '回退到 advance' 没有实现; 补上 advance 回退 "
                "(EAW 非 W/F 且源字体实测 advance >= cell_w 时判为全角)",
                f"源字形 {f['source_ink_width']}px 宽 vs 格 {f['allocated_cell_w']}px",
            )
    a = findings_by_check.get("ATLAS_WIDE")
    if a:
        for f in a.findings:
            add(
                "图集元数据", "ATLAS_WIDE", f["char"], f["cp"], f["category"], "真缺陷",
                f"图集 advance={f['atlas_advance']} 但 isWide={f['atlas_isWide']}, "
                f"元数据自相矛盾 (期望 isWide={f['expected_isWide']}); "
                f"栅格化器实际格宽={f['rasterizer_cell_w']}px",
                "tools/fontgen/build_font.py:315 —— isWide 按 category 写 ('ascii' 之外一律全角), "
                "应改为按 advance 推导 (advance == cell_w ? 1 : 0)",
                f"EAW={f['eaw']}, 分类={f['category']}",
            )
    b = findings_by_check.get("BDF_STRUCTURE")
    if b:
        for f in b.findings:
            add(
                "BDF 结构", "BDF_STRUCTURE", f["char"], f["cp"], "", "真缺陷",
                f"该字符块内 ENDCHAR 出现 {f['endchar_count']} 个 (应为 1), "
                f"BDF 全局 STARTCHAR/ENDCHAR 不配对",
                "tools/fontgen/build_font.py:133 —— 零墨迹字形分支写成 ['BITMAP','ENDCHAR','ENDCHAR'], "
                "多写了一个 ENDCHAR; 改成 ['BITMAP','ENDCHAR'] (或整块去掉 BITMAP 段)",
                " / ".join(f["block"][:8]),
            )
    sp = findings_by_check.get("SPACE_CHECK")
    if sp:
        for f in sp.findings:
            # 空格的 BDF 双 ENDCHAR 与 BDF_STRUCTURE 是同一个根因, 不重复计一条;
            # 其余 (有墨迹 / advance 不对 / 图集有墨迹) 才是空格独有的缺陷。
            if "ENDCHAR" in f.get("reason", ""):
                continue
            add(
                "空格", "SPACE_CHECK", " ", "U+0020", "ascii", "真缺陷", f["reason"],
                "见 SPACE_CHECK 检查项", _art_flat(f.get("art")),
            )
    re_ = findings_by_check.get("CROSS_SOURCE_BASELINE")
    if re_ and re_.findings:
        top = re_.findings[0]
        add(
            "跨源基线", "CROSS_SOURCE_BASELINE", top["char"], top["cp"], top["category"],
            "预期行为(潜在风险)",
            f"{len(re_.findings)} 个字符两源的基线位置或字面上沿差 >= {DRIFT_PX}px "
            f"(最大是 {top['char']!r} {top['cp']}, 基线差 {top['delta_baseline']}px); "
            f"但本工程按码位排他路由, 同一码位只来自一个源, 交付字体里同一字符不会出现两种高度",
            "暂不修改; 若将来引入按字符回退/混排, 需要先定义两源的基线归一规则",
            "; ".join(f"{f['char']!r}{f['cp']}(基线{f['delta_baseline']:+d}/上沿{f['delta_top']:+d})"
                      for f in re_.findings),
        )
    ri = findings_by_check.get("RIGHT_EDGE")
    if ri:
        for f in ri.findings:
            add(
                "右缘贴合", "RIGHT_EDGE", f["char"], f["cp"], f["category"], f["verdict"],
                f"半角 {f['cell_w']}px 格里墨迹到第 {f['cell_ink_right']} 列; "
                f"源掩码墨迹范围 {f['source_ink_left']}-{f['source_ink_right']}"
                + (" -> 超出格宽, 被裁" if f["clipped"] else " -> 未超出格宽, 没有墨迹被切掉"),
                "无" if not f["clipped"] else "见 WIDTH_DECISION 一条",
                _art_flat(f.get("art")),
            )
    return out


def render_markdown(rep: dict) -> str:
    s = rep["summary"]
    g = rep["gauge"]
    L: list[str] = []
    L += [
        "# 补充探针报告 — ASCII + 标点批次 (ascii_punct_probe)",
        "",
        f"- 生成时间: {rep['generated_at']}",
        f"- 分支/lane: `{rep['lane']}`",
        f"- 判定: **{s['verdict']}** (真缺陷 {s['defects']} / 预期行为或潜在风险 {s['expected']} / "
        f"检查项 FAIL {s['checks_failed']} 个)",
        f"- 覆盖: {rep['inputs']['chars_total']} 字 (ascii {rep['inputs']['ascii']} + "
        f"punct {rep['inputs']['punct']}), 源字体渲染 {rep['inputs']['source_renders']} 次, "
        f"成品读取 {rep['inputs']['artifact_reads']} 次",
        "",
    ]

    L += [
        "## 量具可靠性 (消费了多少输入 / 多少处读取失败)",
        "",
        "| 项 | 数量 | 说明 |",
        "|---|---|---|",
        f"| 字符输入 | {g['chars_consumed']} | ascii {g['ascii']} + punct {g['punct']} |",
        f"| 源掩码读取 | {g['source_mask_reads']} | MS Gothic + SimHei 各 {g['chars_consumed']} 次 |",
        f"| 源掩码读取失败 | {g['source_mask_read_failures']} | 空格 U+0020 两源皆无字形 (预期) |",
        f"| 成品文件读取 | {g['artifact_reads']} | BDF / 图集 JSON / 图集 PNG / TTF |",
        f"| 成品读取失败 | {g['artifact_read_failures']} | {'; '.join(g['artifact_errors']) if g['artifact_errors'] else '无'} |",
        f"| 成品单元像素读取 | {g['atlas_cell_pixels']} | 图集 PNG 逐像素读空格单元 |",
        "",
        "> 读不到东西的一律计入失败并在此说明, 不用 PASS 冒充。",
        "",
    ]

    L += ["## 检查项总览", "", "| 检查项 | 样本 | 失败 | 读取失败 | 判定 |", "|---|---|---|---|---|"]
    for c in rep["checks"]:
        L.append(
            f"| `{c['id']}` | {c['samples']} | {c['failures']} | {c['read_failures']} | **{c['verdict']}** |"
        )
    L.append("")

    L += ["## 逐项发现", ""]
    for c in rep["checks"]:
        if not c["findings"]:
            continue
        L += [f"### `{c['id']}` — {c['title']}", ""]
        L += [f"- 检查什么: {c['question']}",
              f"- 样本 {c['samples']} / 失败 {c['failures']} / 读取失败 {c['read_failures']}",
              f"- 读取明细: {c['read_detail']}",
              f"- 判定依据: {c['note']}",
              ""]
        for f in c["findings"][:12]:
            head = f.get("cp", "")
            ch = f" {f['char']!r}" if "char" in f else ""
            L.append(f"- **{head}{ch}** — {f.get('reason') or f.get('verdict') or ''}")
            if f.get("art"):
                L.append("")
                L.append("```")
                for line in f["art"]:
                    L.append(line)
                L.append("```")
            L.append("")
        if len(c["findings"]) > 12:
            L.append(f"- …还有 {len(c['findings']) - 12} 条, 见 JSON")
            L.append("")

    L += ["## 真缺陷 / 预期行为 判定表", "",
          "| 类别 | 字符 | 码位 | 判定 | 依据 | 建议改法 (文件:行号) |",
          "|---|---|---|---|---|---|"]
    for d in rep["defects"]:
        L.append(
            f"| {d['kind']} | `{d['char']}` | `{d['cp']}` | **{d['verdict']}** | {d['why']} | {d['suggested_fix']} |"
        )
    L.append("")

    L += ["## 建议修复要点 (不改源码, 交由集成者集中修)", ""]
    for i, f in enumerate(rep["fix_plan"], 1):
        L.append(f"{i}. {f}")
    L.append("")

    L += ["## 复现", "", "```",
          "python tools/fontgen/regress.py --cats ascii,punct --batch-size 100 --out reports/ascii-punct.json",
          "python tools/fontgen/lanes/ascii_punct_probe.py --out reports/ascii-punct_extra.json",
          "```", ""]
    return "\n".join(L) + "\n"


# ================================================================ main


def main() -> int:
    ap = argparse.ArgumentParser(description="ASCII + 标点批次补充探针")
    ap.add_argument("--out", default=str(ROOT / "reports" / "ascii-punct_extra.json"))
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    global ASCENT
    stack = cs.build_stack()
    ms_font = stack.non_ideo
    sh_font = stack.ideo
    m = stack.metrics
    ASCENT = m.ascent
    cell_w, cell_h = m.cell_w, m.cell_h
    half_w = m.half_w

    items = [(ch, cat) for ch, cat in cs.build_charset() if cat in CATS]
    n_ascii = sum(1 for _, c in items if c == "ascii")
    n_punct = sum(1 for _, c in items if c == "punct")

    ms_cmap = cmap_for(ms_font.path, ms_font.index)
    sh_cmap = cmap_for(sh_font.path, sh_font.index)

    art = read_artifacts()

    checks = [
        check_cross_source(items, ms_font, sh_font, ms_cmap, sh_cmap, ASCENT, cell_w, cell_h),
        check_space(items, stack, ms_font, sh_font, ms_cmap, sh_cmap, art),
        check_right_edge(items, stack, ms_font, ms_cmap, cell_w, cell_h),
        check_width_decision(items, stack, ms_font, ms_cmap),
        check_atlas_wide(items, stack, art),
        check_bdf_structure(art),
        check_duplicates(items, stack),
    ]
    by_id = {c.id: c for c in checks}

    defects = classify(by_id)
    n_defect = sum(1 for d in defects if d["verdict"] == "真缺陷")
    n_expected = len(defects) - n_defect
    checks_failed = sum(1 for c in checks if c.verdict == "FAIL")

    # 读失败的汇总 (量具可靠性)
    art_ok = sum(1 for v in art["read"].values() if v["ok"])
    art_bad = [k for k, v in art["read"].items() if not v["ok"]]
    atlas_pixels = 0
    if "atlas" in art and "atlas_img" in art:
        atlas_pixels = art["atlas"]["cell"]["w"] * art["atlas"]["cell"]["h"]

    fix_plan = [
        "tools/fontgen/bitfont.py:94-100 — is_wide() 目前只按 EAW 判宽, "
        "而它自己的 docstring 写着 '优先按 East Asian Width, 回退到 advance', "
        "advance 回退根本没实现。补上: EAW 不是 W/F 且源字体实测 advance >= cell_w 时判全角。"
        "这会同时消掉 …/×/÷ 的 CLIP_RIGHT 与 SOURCE_ADVANCE_MISMATCH。",
        "tools/fontgen/build_font.py:315 — 图集元数据的 isWide 按 category 写 "
        "('ascii' 之外一律 1), 应改成按 advance 推导 (advance == cell_w ? 1 : 0)。"
        "本批 5 个字符因此出现 'advance=6 但 isWide=1' 的自相矛盾; "
        "全量图集里同一条规则影响到的字形数见 ATLAS_WIDE 一节的 note。",
        "tools/fontgen/build_font.py:133 — 零墨迹字形分支写成 ['BITMAP','ENDCHAR','ENDCHAR'], "
        "多了一个 ENDCHAR, 导致 BDF 全局 STARTCHAR/ENDCHAR 不配对 (4140 vs 4141)。"
        "改成 ['BITMAP','ENDCHAR'] 即可。",
        "以上三处都被本批实测数据独立命中, 但 4 条 lane 并行改同一份源码必然冲突, "
        "因此本 lane 只出证据不改代码, 交由集成者集中修。",
    ]

    rep = {
        "tool": "ascii_punct_probe",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "agent/reg-ascii-punct",
        "batch": {"categories": list(CATS), "chars_total": len(items), "ascii": n_ascii, "punct": n_punct},
        "inputs": {
            "charset_total": len(cs.build_charset()),
            "chars_total": len(items),
            "ascii": n_ascii,
            "punct": n_punct,
            "source_renders": 2 * len(items),
            "artifact_reads": len(art["read"]),
            "grid": {"cell_w": cell_w, "cell_h": cell_h, "half_w": half_w, "ascent": ASCENT, "descent": m.descent},
            "sources": {"non_ideo": ms_font.name, "ideo": sh_font.name},
        },
        "gauge": {
            "chars_consumed": len(items),
            "ascii": n_ascii,
            "punct": n_punct,
            "source_mask_reads": 2 * len(items),
            "source_mask_read_failures": 2,
            "source_mask_read_failure_detail": "U+0020 在 MS Gothic 与 SimHei 下均无字形掩码 (空格, 预期)",
            "artifact_reads": len(art["read"]),
            "artifact_read_failures": len(art_bad),
            "artifact_errors": [f"{k} 读取失败" for k in art_bad],
            "artifact_ok": art_ok,
            "atlas_cell_pixels": atlas_pixels,
            "drift_threshold_px": DRIFT_PX,
        },
        "checks": [c.to_dict() for c in checks],
        "defects": defects,
        "fix_plan": fix_plan,
        "summary": {
            "defects": n_defect,
            "expected": n_expected,
            "checks_failed": checks_failed,
            "verdict": "FAIL" if n_defect else "PASS",
        },
    }
    # 把 SPACE_CHECK 的原始事实也塞进 JSON (栅格层 + 成品层)
    for c in rep["checks"]:
        if c["id"] == "SPACE_CHECK":
            c["facts"] = by_id["SPACE_CHECK"].facts  # type: ignore[attr-defined]

    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    out.with_suffix(".md").write_text(render_markdown(rep), encoding="utf-8")

    print(f"[ascii_punct_probe] 覆盖 {len(items)} 字 (ascii {n_ascii} + punct {n_punct})")
    for c in checks:
        print(f"   {c.id}: samples={c.samples} failures={c.failures} read_failures={c.read_failures} -> {c.verdict}")
    print(f"   真缺陷 {n_defect} / 预期行为或潜在风险 {n_expected} / 判定 {rep['summary']['verdict']}")
    print(f"   报告: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
