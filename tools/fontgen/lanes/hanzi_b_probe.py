"""hanzi_b_probe —— 汉字后 1855 字的成品结构级校验探针 (lane: agent/reg-hanzi-b)。

与 tools/fontgen/regress.py 的分工 (两者互补, 不重复):

  regress.py      同一个字形的**四路交叉对比** (R 栅格化器 / B BDF / T TTF / A 图集),
                  回答"三份成品的内容是否都等于源位图", 再加批统计离群检测。
  本探针         成品文件的**结构级**校验, 回答"文件的骨架对不对":
                    A 图集网格对齐 (单元格原点 / 墨迹不渗邻格 / PNG 尺寸 vs 元数据)
                    B TTF 表结构 (.notdef 空心方框 / hhea vs OS/2 / gasp / maxp)
                    C BDF 头尾与字符块结构 (头字段 / ENDCHAR 配对 / BBX 高度 / 行位宽与填充位)
                    D 汉字之间位图唯一性 (批内同位图 = 路由/映射错误的强信号)

只读既有源码 (tools/fontgen/*.py 一律不改), 只写:
  reports/hanzi-b_extra.json
  reports/hanzi-b_extra.md

用法:
  python tools/fontgen/lanes/hanzi_b_probe.py
  python tools/fontgen/lanes/hanzi_b_probe.py --rebuild     # 先跑一次生产构建再校验
  python tools/fontgen/lanes/hanzi_b_probe.py --out reports/hanzi-b_extra.json

退出码: 0 = 无 error 级异常 / 1 = 有 error 级异常 / 2 = 没测到东西 (绝不拿 PASS 冒充)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
FONTGEN = HERE.parents[1]  # tools/fontgen
ROOT = HERE.parents[3]  # 仓库根
sys.path.insert(0, str(FONTGEN))

from PIL import Image  # noqa: E402

import build_font as bf  # noqa: E402
import charset as cs  # noqa: E402
import regress  # noqa: E402

ERROR = "error"
WARN = "warn"
INFO = "info"

# 探针自身的量具可靠度记录: 每个检查项一条
GAUGE: list[dict] = []


def gauge(check_id: str, title: str, samples: int, failures: int, read_errors: int, note: str) -> None:
    GAUGE.append(
        {
            "id": check_id,
            "title": title,
            "samples": samples,
            "failures": failures,
            "read_errors": read_errors,
            "note": note,
        }
    )


class Findings:
    """异常收集器 (带对象 / 码位 / 数值证据)。"""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(
        self,
        id: str,
        severity: str,
        detail: str,
        cp: int | None = None,
        char: str = "",
        evidence: dict | None = None,
        fix: str = "",
    ) -> None:
        d: dict = {"id": id, "severity": severity, "detail": detail}
        if cp is not None:
            d["cp"] = f"U+{cp:04X}"
            d["char"] = char
        if evidence:
            d["evidence"] = evidence
        if fix:
            d["suggested_fix"] = fix
        self.items.append(d)

    def count(self, sev: str) -> int:
        return sum(1 for i in self.items if i["severity"] == sev)


# ================================================================ 工具


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ascii_art(rows: list[list[int]], ink: str = "#", paper: str = ".") -> str:
    return "\n".join("".join(ink if v else paper for v in r) for r in rows)


def hex_to_bits(hexs: str, nbits: int) -> list[int]:
    val = int(hexs, 16) if hexs else 0
    return [(val >> (nbits - 1 - b)) & 1 for b in range(nbits)]


# ================================================================ A 图集


def check_atlas(png_path: Path, js_path: Path, stack, scope: list[tuple[str, str]]) -> dict:
    """A1 单元格原点 / A2 墨迹不渗邻格 / A3 PNG 尺寸 vs 元数据 / A4 墨色一致。"""
    f = Findings()
    meta = json.loads(js_path.read_text(encoding="utf-8"))
    img = Image.open(png_path).convert("RGBA")
    px = img.load()
    W, H = img.size

    cw = meta["cell"]["w"]
    ch = meta["cell"]["h"]
    columns = meta["columns"]
    rows = meta["rows"]
    entries = meta["glyphs"]

    m = stack.metrics
    ascent, descent = m.ascent, m.descent

    # ---- A3: PNG 实际尺寸 vs 元数据 columns/rows/size
    exp_w = columns * cw
    exp_h = rows * ch
    a3_fail = 0
    checks_a3 = [
        ("PNG 实际尺寸", [W, H], [meta["size"]["w"], meta["size"]["h"]]),
        ("元数据 size vs columns*cell", [meta["size"]["w"], meta["size"]["h"]], [exp_w, exp_h]),
        ("rows vs ceil(glyphCount/columns)", rows, math.ceil(len(entries) / columns)),
        ("glyphCount vs glyphs 数组长度", meta["glyphCount"], len(entries)),
        ("cell vs 栅格化器度量", [cw, ch], [m.cell_w, m.cell_h]),
        ("baseline vs 栅格化器 ascent", meta["baseline"], ascent),
        ("descent vs 栅格化器 descent", meta["descent"], descent),
    ]
    a3_detail = []
    for label, got, want in checks_a3:
        if got != want:
            a3_fail += 1
            a3_detail.append(f"{label}: 实际 {got} != 期望 {want}")
    if a3_fail:
        f.add(
            "ATLAS_SIZE_MISMATCH",
            ERROR,
            f"图集尺寸/元数据不自洽 ({a3_fail} 项)",
            evidence={"mismatches": a3_detail, "png_size": [W, H], "meta_size": [meta["size"]["w"], meta["size"]["h"]]},
        )
    gauge("A3", "图集 PNG 尺寸与元数据 columns/rows/size 一致", len(checks_a3), a3_fail, 0, "7 项标量比对 (PNG 实际尺寸 + 元数据自洽 + 与栅格化器度量)")

    # ---- A1: 单元格原点 == (列*12, 行*13)
    a1_fail = 0
    a1_examples = []
    for i, e in enumerate(entries):
        cp, gx, gy, adv, wide = e
        want_x = (i % columns) * cw
        want_y = (i // columns) * ch
        if (gx, gy) != (want_x, want_y):
            a1_fail += 1
            if len(a1_examples) < 10:
                a1_examples.append({"index": i, "cp": f"U+{cp:04X}", "meta_xy": [gx, gy], "expect_xy": [want_x, want_y]})
    if a1_fail:
        f.add(
            "ATLAS_ORIGIN_MISMATCH",
            ERROR,
            f"{a1_fail} 个字形的单元格原点与 (列*{cw}, 行*{ch}) 不符",
            evidence={"examples": a1_examples},
        )
    gauge("A1", "图集单元格原点 == (列*12, 行*13) 且与元数据一致", len(entries), a1_fail, 0, "遍历元数据 glyphs 全量 4140 条, 按数组下标反推列/行")

    # ---- A2: 墨迹不渗出自己那格 (结构层: 墨迹列 < advance) + 批内逐像素相等
    scope_cps = {ord(ch) for ch, _ in scope}
    a2_fail = 0
    a2_examples = []
    pixel_cmp = 0
    pixel_diff_total = 0
    ink_outside_advance = 0
    total_ink_png = 0
    for i, e in enumerate(entries):
        cp, gx, gy, adv, wide = e
        # 结构层: 本格内的墨迹列必须全部落在 [0, adv) —— 半角字形 (adv=6) 的
        # 右侧 6 列必须为空, 那 6 列若出现墨迹就是写图集时渗到了下一格的地盘。
        cols_with_ink = [x for x in range(cw) if any(px[gx + x, gy + y][3] > 0 for y in range(ch))]
        rows_with_ink = [y for y in range(ch) if any(px[gx + x, gy + y][3] > 0 for x in range(cw))]
        total_ink_png += sum(1 for y in range(ch) for x in range(cw) if px[gx + x, gy + y][3] > 0)
        if cols_with_ink and max(cols_with_ink) >= adv:
            ink_outside_advance += 1
            if len(a2_examples) < 10:
                a2_examples.append(
                    {
                        "cp": f"U+{cp:04X}",
                        "cell_xy": [gx, gy],
                        "advance": adv,
                        "ink_cols": cols_with_ink,
                        "detail": f"墨迹列 {min(cols_with_ink)}..{max(cols_with_ink)} 越出 advance={adv}",
                    }
                )
        if rows_with_ink and max(rows_with_ink) >= ch:
            a2_fail += 1
        # 像素层 (只对本 lane 的 1855 字做, 其余只做结构层): 与栅格化器逐像素比
        if cp in scope_cps:
            g = stack.glyph(chr(cp))
            gp = g.load()
            diff = 0
            for y in range(g.height):
                for x in range(g.width):
                    want = 1 if gp[x, y] > 0 else 0
                    got = 1 if px[gx + x, gy + y][3] > 0 else 0
                    if want != got:
                        diff += 1
            pixel_cmp += 1
            pixel_diff_total += diff
            if diff:
                a2_fail += 1
                if len(a2_examples) < 10:
                    a2_examples.append({"cp": f"U+{cp:04X}", "cell_xy": [gx, gy], "diff_px": diff})
    if ink_outside_advance:
        f.add(
            "ATLAS_INK_LEAK",
            ERROR,
            f"{ink_outside_advance} 个字形的墨迹越出自身 advance 宽度, 渗进了本格空白区",
            evidence={"examples": a2_examples, "ink_outside_advance": ink_outside_advance},
        )
    if pixel_diff_total:
        f.add(
            "ATLAS_PIXEL_MISMATCH",
            ERROR,
            f"批内 {pixel_cmp} 字与栅格化器共差 {pixel_diff_total} px",
            evidence={"examples": a2_examples, "diff_px_total": pixel_diff_total},
        )
    gauge(
        "A2",
        "图集墨迹不渗邻格 (结构: 墨迹列 < advance) + 批内逐像素相等",
        len(entries),
        a2_fail + ink_outside_advance,
        0,
        f"结构层消费 {len(entries)} 格; 像素层消费 {pixel_cmp} 字 (本 lane 批次), 共 {pixel_cmp * 13 * 12} 次像素比对",
    )

    # ---- A4: 墨迹像素 RGB 恒为白 (元数据声明 "白色 + alpha")
    a4_fail = 0
    non_white = 0
    for e in entries:
        cp, gx, gy, adv, wide = e
        for y in range(ch):
            for x in range(cw):
                r, g, b, a = px[gx + x, gy + y]
                if a > 0 and (r, g, b) != (255, 255, 255):
                    non_white += 1
    a4_fail = 1 if non_white else 0
    if a4_fail:
        f.add(
            "ATLAS_INK_COLOR",
            WARN,
            f"{non_white} 个墨迹像素不是纯白 RGB",
            evidence={"non_white_pixels": non_white},
        )
    gauge("A4", "图集墨迹像素 RGB 恒为 (255,255,255)", len(entries) * ch * cw, a4_fail, 0, "扫描全部 4140 格 × 156 px")

    return {
        "findings": f.items,
        "meta": {
            "columns": columns,
            "rows": rows,
            "cell": [cw, ch],
            "png_size": [W, H],
            "glyph_count": len(entries),
        },
        "gauge": GAUGE,
    }


# ================================================================ B TTF


def outline_contours(glyphset, name: str) -> list[list[tuple[float, float]]]:
    """取一个 glyph 的闭合轮廓点列。"""
    from fontTools.pens.recordingPen import DecomposingRecordingPen

    pen = DecomposingRecordingPen(glyphset[name])
    glyphset[name].draw(pen)
    contours: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for op, args in pen.value:
        if op == "moveTo":
            cur = [(args[0][0], args[0][1])]
        elif op == "lineTo":
            cur.append((args[0][0], args[0][1]))
        elif op == "closePath":
            if cur:
                contours.append(cur)
            cur = []
    if cur:
        contours.append(cur)
    return contours


def signed_area(c: list[tuple[float, float]]) -> float:
    s = 0.0
    for i in range(len(c)):
        x0, y0 = c[i]
        x1, y1 = c[(i + 1) % len(c)]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def rasterize_nonzero(
    contours: list[list[tuple[float, float]]], px: int, ascent: int, cell_w: int, cell_h: int
) -> list[list[int]]:
    """按 TrueType 的非零环绕规则做扫描线填充 (像素中心采样)。

    用途: 独立验证 .notdef 真的是"空心方框" —— 只看轮廓点数不够,
    绕向写反会让方框被填实, 只有真正按填充规则栅格化才看得出来。
    """
    out = [[0] * cell_w for _ in range(cell_h)]
    edges = []
    for c in contours:
        for i in range(len(c)):
            x0, y0 = c[i]
            x1, y1 = c[(i + 1) % len(c)]
            if y0 != y1:
                edges.append((x0, y0, x1, y1))
    for r in range(cell_h):
        yc = (ascent - r - 0.5) * px
        xs = []
        for (x0, y0, x1, y1) in edges:
            if (y0 <= yc < y1) or (y1 <= yc < y0):
                t = (yc - y0) / (y1 - y0)
                xs.append((x0 + t * (x1 - x0), 1 if y1 > y0 else -1))
        xs.sort()
        wind = 0
        for i in range(len(xs) - 1):
            wind += xs[i][1]
            if wind == 0:
                continue
            xa, xb = xs[i][0], xs[i + 1][0]
            for c in range(cell_w):
                cx = (c + 0.5) * px
                if xa <= cx < xb:
                    out[r][c] = 1
    return out


def check_ttf(ttf_path: Path, stack) -> dict:
    from fontTools.ttLib import TTFont

    f = Findings()
    tt = TTFont(str(ttf_path))
    m = stack.metrics
    ascent, descent = m.ascent, m.descent
    cell_w, cell_h = m.cell_w, m.cell_h
    px = tt["head"].unitsPerEm // cell_w

    # ---- B1: .notdef 必须是空心方框, 且尺寸 (0..em 宽) x (-descent..ascent)
    b1_fail = 0
    glyf = tt["glyf"]
    nd = glyf[".notdef"]
    nd_evidence = {
        "numberOfContours": nd.numberOfContours,
        "xMin": nd.xMin,
        "xMax": nd.xMax,
        "yMin": nd.yMin,
        "yMax": nd.yMax,
        "expect_xMin": 0,
        "expect_xMax": cell_w * px,
        "expect_yMin": -descent * px,
        "expect_yMax": ascent * px,
    }
    if nd.numberOfContours != 2:
        b1_fail += 1
        f.add(
            "TTF_NOTDEF_NOT_BOX",
            ERROR,
            f".notdef 轮廓数 {nd.numberOfContours} != 2 (空心方框应是外环+内环)",
            evidence=nd_evidence,
        )
    if (nd.xMin, nd.xMax) != (0, cell_w * px):
        b1_fail += 1
        f.add(
            "TTF_NOTDEF_SIZE",
            ERROR,
            f".notdef 横向范围 ({nd.xMin}..{nd.xMax}) != (0..{cell_w * px})",
            evidence=nd_evidence,
        )
    if (nd.yMin, nd.yMax) != (-descent * px, ascent * px):
        b1_fail += 1
        f.add(
            "TTF_NOTDEF_SIZE",
            ERROR,
            f".notdef 纵向范围 ({nd.yMin}..{nd.yMax}) != ({-descent * px}..{ascent * px})",
            evidence=nd_evidence,
        )
    # 绕向: 非零填充下, 内环必须与外环绕向相反才是空心
    glyphset = tt.getGlyphSet()
    contours = outline_contours(glyphset, ".notdef")
    areas = [round(signed_area(c), 3) for c in contours]
    nd_evidence["contour_signed_areas"] = areas
    if len(areas) == 2 and (areas[0] > 0) == (areas[1] > 0):
        b1_fail += 1
        f.add(
            "TTF_NOTDEF_NOT_BOX",
            ERROR,
            f".notdef 两环绕向相同 (面积 {areas}), 非零填充下会变成实心块",
            evidence=nd_evidence,
        )
    # 真正按填充规则栅格化, 验证是空心方框
    got = rasterize_nonzero(contours, px, ascent, cell_w, cell_h)
    # 期望: 外框 12x13 实心, 内部 (行 1..11, 列 1..10) 为洞
    expect = [[0] * cell_w for _ in range(cell_h)]
    for r in range(cell_h):
        for c in range(cell_w):
            in_hole = 1 <= r <= cell_h - 2 and 1 <= c <= cell_w - 2
            expect[r][c] = 0 if in_hole else 1
    nd_evidence["rasterized"] = ascii_art(got)
    nd_evidence["expected_hollow_box"] = ascii_art(expect)
    if got != expect:
        b1_fail += 1
        f.add(
            "TTF_NOTDEF_NOT_BOX",
            ERROR,
            ".notdef 按非零环绕规则栅格化后不是预期的空心方框",
            evidence=nd_evidence,
        )
    if got[cell_h // 2][cell_w // 2] != 0:
        b1_fail += 1
        f.add("TTF_NOTDEF_NOT_BOX", ERROR, ".notdef 中心像素被填实 (不是空心)", evidence=nd_evidence)
    gauge("B1", ".notdef 空心方框 (2 环 / 相反绕向 / 非零填充栅格化 / 尺寸)", 1, b1_fail, 0, "对 .notdef 做 6 项判定: 环数、x 范围、y 范围、绕向、栅格化比对、中心为空")

    # ---- B2: hhea 与 OS/2 的 ascent/descent 一致
    hhea = tt["hhea"]
    os2 = tt["OS/2"]
    a, d = ascent * px, descent * px
    b2_fail = 0
    b2_items = [
        ("hhea.ascent", hhea.ascent, a),
        ("OS/2.usWinAscent", os2.usWinAscent, a),
        ("OS/2.sTypoAscender", os2.sTypoAscender, a),
        ("-hhea.descent", -hhea.descent, d),
        ("OS/2.usWinDescent", os2.usWinDescent, d),
        ("-OS/2.sTypoDescender", -os2.sTypoDescender, d),
    ]
    b2_bad = [f"{k}: 实际 {g} != 期望 {w}" for k, g, w in b2_items if g != w]
    b2_fail = len(b2_bad)
    if b2_bad:
        f.add(
            "TTF_METRICS_MISMATCH",
            ERROR,
            f"hhea / OS/2 垂直度量不一致或与栅格化器不符 ({b2_fail} 项)",
            evidence={"mismatches": b2_bad, "table": {k: g for k, g, _ in b2_items}},
        )
    if hhea.ascent != os2.usWinAscent or -hhea.descent != os2.usWinDescent:
        b2_fail += 1
        f.add(
            "TTF_METRICS_MISMATCH",
            ERROR,
            "hhea 与 OS/2 的 usWinAscent/usWinDescent 不一致",
            evidence={
                "hhea": [hhea.ascent, hhea.descent],
                "os2": [os2.usWinAscent, os2.usWinDescent],
            },
        )
    gauge("B2", "hhea.ascent/descent 与 OS/2 usWinAscent/usWinDescent 一致", len(b2_items), b2_fail, 0, "6 项标量比对 (hhea 2 + usWin 2 + sTypo 2), 期望值 = ascent*64 / descent*64")

    # ---- B3: gasp 存在, 12ppem 的 range 必须是 0 (单色)
    b3_fail = 0
    b3_evidence = {"has_gasp": "gasp" in tt}
    if "gasp" not in tt:
        b3_fail += 1
        f.add(
            "TTF_NO_GASP",
            ERROR,
            "缺 gasp 表 —— 12px 处渲染器会开抗锯齿, 像素边缘变灰",
            evidence=b3_evidence,
            fix="build_font.py:267-273 已在写 gasp; 若成品里没有, 说明 fb.font['gasp'] = gasp 未落盘",
        )
    else:
        gasp = tt["gasp"]
        ranges = {int(k): int(v) for k, v in gasp.gaspRange.items()}
        b3_evidence["version"] = gasp.version
        b3_evidence["gaspRange"] = {str(k): v for k, v in ranges.items()}
        b3_evidence["gasp12_value"] = ranges.get(12)
        b3_evidence["meaning"] = "0 = 既不 GRIDFIT 也不 DOGRAY -> 12ppem 单色输出"
        if ranges.get(12) != 0:
            b3_fail += 1
            f.add(
                "TTF_GASP_NOT_MONO",
                ERROR,
                f"gasp 12ppem 的 range = {ranges.get(12)} != 0 (0 才是单色)",
                evidence=b3_evidence,
            )
    gauge("B3", "gasp 表存在且 12ppem 的 range == 0 (单色)", 1, b3_fail, 0, "查表存在性 + gaspRange[12] 标量比对")

    # ---- B4: maxp 的 maxPoints/maxContours 必须与实际 glyf 一致
    b4_fail = 0
    maxp = tt["maxp"]
    order = tt.getGlyphOrder()
    actual_points = 0
    actual_contours = 0
    max_point_glyph = ""
    max_contour_glyph = ""
    empty_glyphs = 0
    for name in order:
        cs_ = outline_contours(glyphset, name)
        npts = sum(len(c) for c in cs_)
        ncts = len(cs_)
        if ncts == 0:
            empty_glyphs += 1
        if npts > actual_points:
            actual_points = npts
            max_point_glyph = name
        if ncts > actual_contours:
            actual_contours = ncts
            max_contour_glyph = name
    b4_evidence = {
        "maxp_maxPoints": maxp.maxPoints,
        "actual_maxPoints": actual_points,
        "maxp_maxContours": maxp.maxContours,
        "actual_maxContours": actual_contours,
        "maxp_numGlyphs": maxp.numGlyphs,
        "glyph_order_len": len(order),
        "max_points_glyph": max_point_glyph,
        "max_contours_glyph": max_contour_glyph,
        "empty_glyphs": empty_glyphs,
    }
    if maxp.maxPoints != actual_points:
        b4_fail += 1
        f.add(
            "TTF_MAXP_POINTS_MISMATCH",
            ERROR,
            f"maxp.maxPoints = {maxp.maxPoints} != 实际最大轮廓点数 {actual_points} (字形 {max_point_glyph})",
            evidence=b4_evidence,
            fix="build_font.py:263 的 fb.font['maxp'].recalc(fb.font) 必须保留 (它按 glyf 重算)",
        )
    if maxp.maxContours != actual_contours:
        b4_fail += 1
        f.add(
            "TTF_MAXP_CONTOURS_MISMATCH",
            ERROR,
            f"maxp.maxContours = {maxp.maxContours} != 实际最大轮廓数 {actual_contours} (字形 {max_contour_glyph})",
            evidence=b4_evidence,
            fix="build_font.py:263",
        )
    if maxp.numGlyphs != len(order):
        b4_fail += 1
        f.add(
            "TTF_MAXP_NUMGLYPHS_MISMATCH",
            ERROR,
            f"maxp.numGlyphs = {maxp.numGlyphs} != 字形表长度 {len(order)}",
            evidence=b4_evidence,
        )
    gauge(
        "B4",
        "maxp.maxPoints/maxContours/numGlyphs 与实际 glyf 一致",
        len(order),
        b4_fail,
        0,
        f"逐个字形取轮廓点数/轮廓数 (共 {len(order)} 个字形, 含 .notdef), 与 maxp 三个字段比对",
    )

    return {"findings": f.items, "evidence": {"B1": nd_evidence, "B2": b2_items, "B4": b4_evidence}, "gauge": GAUGE}


# ================================================================ C BDF


def parse_bdf_strict(text: str) -> tuple[dict, list[dict], list[str]]:
    """独立于 regress.py 的严格 BDF 解析器 (只做结构, 不做像素还原)。

    刻意不复用 regress.decode_bdf: 两个独立解析器同时认可, 才说明文件结构没问题。
    """
    lines = text.splitlines()
    header: dict = {}
    blocks: list[dict] = []
    issues: list[str] = []
    n = len(lines)
    i = 0
    while i < n:
        ln = lines[i].strip()
        if ln.startswith("STARTCHAR"):
            break
        parts = ln.split(None, 1)
        if parts and parts[0] in (
            "FONTBOUNDINGBOX",
            "CHARS",
            "SIZE",
            "FONT_ASCENT",
            "FONT_DESCENT",
            "FONT",
        ):
            header[parts[0]] = parts[1] if len(parts) > 1 else ""
        i += 1
    while i < n:
        if not lines[i].strip().startswith("STARTCHAR"):
            i += 1
            continue
        b: dict = {"start_line": i + 1, "endchars": 0, "rows": [], "bitmap": False, "encoding": None, "bbx": None}
        i += 1
        while i < n and not lines[i].strip().startswith("STARTCHAR"):
            l2 = lines[i].strip()
            if l2.startswith("ENCODING "):
                try:
                    b["encoding"] = int(l2.split()[1])
                except ValueError:
                    issues.append(f"第 {i + 1} 行 ENCODING 非法: {l2!r}")
            elif l2.startswith("BBX "):
                try:
                    b["bbx"] = tuple(int(v) for v in l2.split()[1:5])
                except ValueError:
                    issues.append(f"第 {i + 1} 行 BBX 非法: {l2!r}")
            elif l2 == "BITMAP":
                b["bitmap"] = True
                h = b["bbx"][1] if b["bbx"] else 0
                i += 1
                for k in range(h):
                    if i + k >= n:
                        issues.append(f"第 {b['start_line']} 行字符块 BITMAP 行数不足 (声明 {h} 行)")
                        break
                    b["rows"].append(lines[i + k].strip())
                i += h
                continue
            elif l2 == "ENDCHAR":
                b["endchars"] += 1
            i += 1
        blocks.append(b)
    return header, blocks, issues


def row_padding_ok(w: int, hexs: str) -> tuple[bool, str]:
    """BDF 每行按字节对齐, 填充位必须为 0 (MSB 在前: 4px 宽的合法编码是 F0 不是 0F)。"""
    nbytes = (w + 7) // 8
    if len(hexs) != nbytes * 2:
        return False, f"行宽 {len(hexs)} != ceil({w}/8)*2 = {nbytes * 2}"
    if not hexs:
        return (nbytes == 0), "空行"
    try:
        val = int(hexs, 16)
    except ValueError:
        return False, f"非十六进制: {hexs!r}"
    used = w % 8
    if used == 0:
        return True, "整字节"
    mask = (1 << (8 - used)) - 1
    if val & mask:
        return False, f"填充位非 0: {hexs!r} (低 {8 - used} 位必须是 0, MSB 在前)"
    return True, "填充位为 0"


def check_bdf(
    bdf_path: Path,
    stack,
    items_all: list[tuple[str, str]],
    glyphs_all,
    run_fix_sim: bool = True,
) -> dict:
    f = Findings()
    text = bdf_path.read_text(encoding="utf-8")
    header, blocks, issues = parse_bdf_strict(text)
    m = stack.metrics
    ascent, descent = m.ascent, m.descent
    cell_w, cell_h = m.cell_w, m.cell_h

    # ---- C1: 头尾字段
    c1_fail = 0
    fbb = header.get("FONTBOUNDINGBOX", "").split()
    c1_items = [
        ("FONTBOUNDINGBOX", fbb, [str(cell_w), str(cell_h), "0", str(-descent)]),
        ("FONT_ASCENT", header.get("FONT_ASCENT", "").split(), [str(ascent)]),
        ("FONT_DESCENT", header.get("FONT_DESCENT", "").split(), [str(descent)]),
        ("CHARS", header.get("CHARS", "").split(), [str(len(items_all))]),
    ]
    c1_bad = []
    for label, got, want in c1_items:
        if [str(x) for x in got] != want:
            c1_fail += 1
            c1_bad.append(f"{label}: 实际 {got} != 期望 {want}")
    # CHARS 声明数 vs 实际字符块数
    actual_blocks = len(blocks)
    if actual_blocks != len(items_all):
        c1_fail += 1
        c1_bad.append(f"实际字符块数 {actual_blocks} != 字符集 {len(items_all)}")
    if issues:
        c1_fail += len(issues)
        c1_bad.extend(issues[:10])
    if c1_fail:
        f.add(
            "BDF_HEADER_MISMATCH",
            ERROR,
            f"BDF 头字段不自洽 ({c1_fail} 项)",
            evidence={"mismatches": c1_bad, "header": {k: v for k, v in header.items()}},
        )
    gauge(
        "C1",
        "BDF 头字段 (FONTBOUNDINGBOX / FONT_ASCENT / FONT_DESCENT / CHARS) 与实际字符数一致",
        len(c1_items) + 1,
        c1_fail,
        0,
        f"读 1 个头 + {actual_blocks} 个字符块; 期望值取自栅格化器度量 (ascent={ascent} descent={descent} cell={cell_w}x{cell_h})",
    )

    # ---- C2: 每块恰好一个 ENDCHAR / BBX 高度 == BITMAP 行数 / 行位宽与填充位
    c2_fail = 0
    endchar_bad = []
    bbx_h_bad = []
    row_w_bad = []
    pad_bad = []
    rows_checked = 0
    for b in blocks:
        cp = b["encoding"]
        if b["endchars"] != 1:
            c2_fail += 1
            endchar_bad.append({"cp": f"U+{cp:04X}", "endchar_count": b["endchars"], "line": b["start_line"]})
        if b["bbx"] is None:
            c2_fail += 1
            bbx_h_bad.append({"cp": f"U+{cp:04X}", "detail": "缺 BBX 行"})
            continue
        w, h, xoff, yoff = b["bbx"]
        if h != len(b["rows"]):
            c2_fail += 1
            bbx_h_bad.append({"cp": f"U+{cp:04X}", "bbx_h": h, "bitmap_rows": len(b["rows"])})
        for k, hexs in enumerate(b["rows"]):
            rows_checked += 1
            ok, why = row_padding_ok(w, hexs)
            if not ok:
                c2_fail += 1
                if "行宽" in why or "非十六进制" in why:
                    row_w_bad.append({"cp": f"U+{cp:04X}", "row": k, "hex": hexs, "why": why})
                else:
                    pad_bad.append({"cp": f"U+{cp:04X}", "row": k, "hex": hexs, "why": why})
    if endchar_bad:
        first = endchar_bad[0]
        f.add(
            "BDF_ENDCHAR_PAIRING",
            ERROR,
            f"{len(endchar_bad)} 个字符块的 ENDCHAR 数量不是 1 (首个: U+{first['cp'][2:]} 写了 {first['endchar_count']} 个 ENDCHAR)",
            cp=int(first["cp"][2:], 16),
            char=chr(int(first["cp"][2:], 16)),
            evidence={"examples": endchar_bad[:20], "total": len(endchar_bad)},
            fix="tools/fontgen/build_font.py:133 —— 零墨迹分支的 lines += [\"BITMAP\", \"ENDCHAR\", \"ENDCHAR\"] 少写一个 ENDCHAR",
        )
    if bbx_h_bad:
        f.add(
            "BDF_BBX_HEIGHT_MISMATCH",
            ERROR,
            f"{len(bbx_h_bad)} 个字符块的 BBX 高度 != BITMAP 行数",
            evidence={"examples": bbx_h_bad[:20], "total": len(bbx_h_bad)},
        )
    if row_w_bad:
        f.add(
            "BDF_ROW_WIDTH",
            ERROR,
            f"{len(row_w_bad)} 行十六进制长度 != ceil(w/8)*2",
            evidence={"examples": row_w_bad[:20], "total": len(row_w_bad)},
        )
    if pad_bad:
        f.add(
            "BDF_ROW_PADDING",
            ERROR,
            f"{len(pad_bad)} 行填充位非 0 (BDF 是 MSB 在前, 渲染器会把填充位当墨迹)",
            evidence={"examples": pad_bad[:20], "total": len(pad_bad)},
        )
    gauge(
        "C2",
        "BDF 每块恰好一个 ENDCHAR / BBX 高度 == BITMAP 行数 / 行位宽 == ceil(w/8)*2 / 填充位为 0",
        len(blocks),
        c2_fail,
        0,
        f"消费 {len(blocks)} 个字符块 + {rows_checked} 个 BITMAP 数据行 (每行 3 项判定: 长度/十六进制/填充位)",
    )

    # ---- C3: 零墨迹字形清单 + 哪些中了双 ENDCHAR
    zero_ink = []
    zero_bad = []
    for b in blocks:
        if b["bbx"] and b["bbx"][0] == 0:
            zero_ink.append(
                {
                    "cp": f"U+{b['encoding']:04X}",
                    "endchar_count": b["endchars"],
                    "bitmap_present": b["bitmap"],
                    "bitmap_rows": len(b["rows"]),
                    "line": b["start_line"],
                }
            )
            if b["endchars"] != 1:
                zero_bad.append(zero_ink[-1])
    if zero_bad:
        first = zero_bad[0]
        f.add(
            "BDF_ZERO_INK_DOUBLE_ENDCHAR",
            ERROR,
            f"{len(zero_bad)} 个零墨迹字形的字符块里写了多个 ENDCHAR "
            f"(U+{first['cp'][2:]} 写了 {first['endchar_count']} 个); "
            f"全字符集共 {len(zero_ink)} 个零墨迹字形, 中招的只有这 {len(zero_bad)} 个",
            cp=int(first["cp"][2:], 16),
            char=chr(int(first["cp"][2:], 16)),
            evidence={
                "zero_ink_glyphs": zero_ink,
                "broken": zero_bad,
                "root_cause": "tools/fontgen/build_font.py:133 —— 零墨迹分支写的是 ['BITMAP', 'ENDCHAR', 'ENDCHAR']",
            },
            fix=(
                "tools/fontgen/build_font.py:133 改为 lines += [\"BITMAP\", \"ENDCHAR\"] "
                "(保留 BITMAP 关键字: 去掉它会让 regress.decode_bdf 收不到该码位, 空格会被误报 BDF_MISSING)"
            ),
        )
    gauge(
        "C3",
        "零墨迹字形清单 + 逐块 ENDCHAR 计数",
        len(blocks),
        len(zero_bad),
        0,
        f"扫描全部 {len(blocks)} 个字符块的 BBX 宽; 命中 {len(zero_ink)} 个零墨迹字形",
    )

    # ---- C4: 修掉之后 BDF 是否仍被解析器接受 (在内存里改, 不动成品)
    if run_fix_sim:
        fix_sim = simulate_bdf_fix(text, blocks, glyphs_all, ascent, descent, cell_w, cell_h)
        if fix_sim.get("errors"):
            f.add(
                "BDF_FIX_REGRESSION",
                ERROR,
                "建议的修法 (删掉多余的 ENDCHAR) 之后, BDF 反而不能被解析",
                evidence=fix_sim,
            )
        gauge(
            "C4",
            "建议修法回灌: 修正后的 BDF 仍被解析器接受, 且像素不变",
            1,
            1 if fix_sim.get("errors") else 0,
            0,
            "在内存里删掉多余 ENDCHAR, 交给两个独立解析器 (本探针 + regress.decode_bdf) 与生产门禁 build_font.verify_bdf 复核",
        )
    else:
        fix_sim = {"skipped": True, "errors": [], "checked": []}

    return {
        "findings": f.items,
        "header": header,
        "blocks": len(blocks),
        "zero_ink": zero_ink,
        "fix_sim": fix_sim,
        "gauge": GAUGE,
    }


def simulate_bdf_fix(text: str, blocks: list[dict], glyphs_all, ascent, descent, cell_w, cell_h) -> dict:
    """模拟"删掉零墨迹字形多余的 ENDCHAR"这个修法, 复核 BDF 仍合法。"""
    out: dict = {"errors": [], "checked": []}
    # 构造修正后的文本: 对 ENDCHAR 计数 != 1 的块, 去掉多余的 ENDCHAR
    lines = text.splitlines()
    # 重新扫描, 定位每个块的多余 ENDCHAR 行号
    fixed = list(lines)
    i = 0
    removed = 0
    while i < len(fixed):
        if not fixed[i].strip().startswith("STARTCHAR"):
            i += 1
            continue
        start = i
        i += 1
        end_idx = None
        ends = []
        while i < len(fixed) and not fixed[i].strip().startswith("STARTCHAR"):
            if fixed[i].strip() == "ENDCHAR":
                ends.append(i)
            i += 1
        if len(ends) > 1:
            for extra in ends[1:]:
                del fixed[extra]
                removed += 1
            i = start
    out["endchar_removed"] = removed
    new_text = "\n".join(fixed) + "\n"

    # 反面对照: 另一种"看起来同样合理"的修法 —— 把零墨迹块的 BITMAP 段整段删掉。
    # 实测该修法会让 regress.decode_bdf 收不到这个码位 (它只在遇到 BITMAP 时登记字形),
    # 于是空格会被误报成 BDF_MISSING。留着 BITMAP 关键字才能既配平 ENDCHAR 又不丢码位。
    no_bitmap_lines: list[str] = []
    _nl = new_text.splitlines()
    j = 0
    while j < len(_nl):
        if _nl[j].strip() == "BITMAP" and j + 1 < len(_nl) and _nl[j + 1].strip() == "ENDCHAR":
            j += 1  # 跳过这一个 BITMAP 关键字 (BBX 0 0 0 0, 0 行数据)
            continue
        no_bitmap_lines.append(_nl[j])
        j += 1
    no_bitmap_text = "\n".join(no_bitmap_lines) + "\n"

    # 1) 本探针的严格解析器
    header2, blocks2, issues2 = parse_bdf_strict(new_text)
    if issues2:
        out["errors"].append({"parser": "hanzi_b_probe.parse_bdf_strict", "issues": issues2[:10]})
    bad_end = [b for b in blocks2 if b["endchars"] != 1]
    if bad_end:
        out["errors"].append({"parser": "hanzi_b_probe.parse_bdf_strict", "endchar_not_1": len(bad_end)})
    if len(blocks2) != len(blocks):
        out["errors"].append(
            {"parser": "hanzi_b_probe.parse_bdf_strict", "blocks": [len(blocks2), len(blocks)]}
        )
    out["checked"].append(
        {
            "parser": "hanzi_b_probe.parse_bdf_strict",
            "blocks": len(blocks2),
            "issues": len(issues2),
            "endchar_mismatch": len(bad_end),
            "ok": not issues2 and not bad_end,
        }
    )

    # 2) regress.py 的第二个独立解析器
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "fixed.bdf"
        p.write_text(new_text, encoding="utf-8")
        parsed, iss = regress.decode_bdf(p, ascent, cell_w, cell_h)
        out["checked"].append(
            {
                "parser": "regress.decode_bdf",
                "parsed_glyphs": len(parsed),
                "issues": len(iss),
                "ok": not iss,
            }
        )
        if iss:
            out["errors"].append({"parser": "regress.decode_bdf", "issues": iss[:10]})
        # 3) 生产门禁 build_font.verify_bdf (真实回读逐像素)
        try:
            bf.verify_bdf(glyphs_all, ascent, descent, p)
            out["checked"].append({"parser": "build_font.verify_bdf", "ok": True, "detail": "生产回读门禁通过"})
        except SystemExit as e:  # noqa: PERF203
            out["checked"].append({"parser": "build_font.verify_bdf", "ok": False, "detail": str(e)})
            out["errors"].append({"parser": "build_font.verify_bdf", "detail": str(e)})

        # 4) 反面对照: 删掉 BITMAP 段的另一种修法, 看 regress.decode_bdf 会不会丢码位
        p2 = Path(td) / "no_bitmap.bdf"
        p2.write_text(no_bitmap_text, encoding="utf-8")
        parsed2, iss2 = regress.decode_bdf(p2, ascent, cell_w, cell_h)
        zero_cp = 0x0020
        out["variant_no_bitmap"] = {
            "parsed_glyphs": len(parsed),
            "parsed_glyphs_after": len(parsed2),
            "space_found_after": zero_cp in parsed2,
            "note": "去掉 BITMAP 段 -> regress.decode_bdf 少收 1 个码位, 该码位会被误报 BDF_MISSING",
        }
    return out


# ================================================================ D 唯一性


def check_uniqueness(
    stack,
    scope: list[tuple[str, str]],
    all_items: list[tuple[str, str]],
    sig_override: dict[str, tuple] | None = None,
) -> dict:
    """D1 批内汉字之间位图唯一性; D2 跨类别同位图 (合法, 仅作对照)。"""
    f = Findings()

    def sig(ch: str) -> tuple:
        if sig_override and ch in sig_override:
            return sig_override[ch]
        g = stack.glyph(ch)
        px = g.load()
        return tuple(tuple(1 if px[x, y] > 0 else 0 for x in range(g.width)) for y in range(g.height))

    # D1: 本 lane 批内
    groups: dict[tuple, list[str]] = defaultdict(list)
    for ch, _ in scope:
        groups[sig(ch)].append(ch)
    dups = [(k, v) for k, v in groups.items() if len(v) > 1]
    dups.sort(key=lambda kv: kv[1][0])
    if dups:
        f.add(
            "HANZI_DUPLICATE_BITMAP",
            ERROR,
            f"批内 {len(dups)} 组汉字位图完全相同 (路由/映射错误的强信号)",
            evidence={
                "groups": [
                    {
                        "members": [{"char": c, "cp": f"U+{ord(c):04X}"} for c in mem],
                        "art": ascii_art([list(r) for r in k]),
                    }
                    for k, mem in dups[:10]
                ],
                "total_groups": len(dups),
            },
        )
    gauge(
        "D1",
        "批内汉字位图唯一性 (1855 字两两比对)",
        len(scope),
        len(dups),
        0,
        f"消费 {len(scope)} 个汉字的位图签名 (12x13 元组), 相同签名归组",
    )

    # D2: 全字符集跨类别同位图 (对照项: 合法, 不算缺陷)
    cat_of = {ch: cat for ch, cat in all_items}
    allgroups: dict[tuple, list[str]] = defaultdict(list)
    for ch, _ in all_items:
        allgroups[sig(ch)].append(ch)
    cross = []
    for k, mem in allgroups.items():
        cats = {cat_of.get(c, "?") for c in mem}
        if len(cats) > 1:
            cross.append(
                {
                    "members": [{"char": c, "cp": f"U+{ord(c):04X}", "cat": cat_of.get(c, "?")} for c in mem],
                    "art": ascii_art([list(r) for r in k]),
                }
            )
    # 汉字之间 (全 3755, 不限本批) 的同位图 —— 供集成者参考
    hanzi_all = [ch for ch, cat in all_items if cat == "hanzi"]
    hgroups: dict[tuple, list[str]] = defaultdict(list)
    for ch in hanzi_all:
        hgroups[sig(ch)].append(ch)
    hdups = [(k, v) for k, v in hgroups.items() if len(v) > 1]
    hdups.sort(key=lambda kv: kv[1][0])
    gauge(
        "D2",
        "对照项: 全字符集跨类别同位图 (合法) + 全 3755 汉字内部同位图",
        len(all_items),
        0,
        0,
        f"消费 {len(all_items)} 个全字符集位图签名; 跨类别同位图 {len(cross)} 组, 全汉字内部同位图 {len(hdups)} 组 (均不计入失败)",
    )

    return {
        "findings": f.items,
        "batch_dups": [
            {
                "members": [{"char": c, "cp": f"U+{ord(c):04X}"} for c in mem],
                "art": ascii_art([list(r) for r in k]),
            }
            for k, mem in dups
        ],
        "cross_category": cross[:10],
        "cross_category_total": len(cross),
        "hanzi_all_dups": [
            {
                "members": [{"char": c, "cp": f"U+{ord(c):04X}"} for c in mem],
                "art": ascii_art([list(r) for r in k]),
            }
            for k, mem in hdups
        ],
        "hanzi_all_dups_total": len(hdups),
        "gauge": GAUGE,
    }


# ================================================================ 量具自检


def _ids(findings: list[dict]) -> set[str]:
    return {x["id"] for x in findings}


def selftest(dist: Path, stack, scope, items_all, glyphs_all) -> list[dict]:
    """注入已知坏数据, 断言每个检测器确实会响。

    没有这一步, "全部 PASS" 只是"没报异常", 不能证明"查得动"。
    合成坏数据 = 已知答案, 可以断言; 每个用例都只改副本, 不动成品。
    """
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont

    ps = bf.PS_NAME
    results: list[dict] = []
    gauge_mark = len(GAUGE)

    def run(name: str, expected: str, mutate, checker) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for src in dist.iterdir():
                if src.is_file():
                    shutil.copy2(src, tmp / src.name)
            try:
                mutate(tmp)
            except Exception as e:  # noqa: BLE001
                results.append({"case": name, "expected": expected, "fired": [], "ok": False, "error": repr(e)})
                return
            try:
                fired = _ids(checker(tmp))
            except Exception as e:  # noqa: BLE001
                results.append({"case": name, "expected": expected, "fired": [], "ok": False, "error": repr(e)})
                return
            results.append(
                {
                    "case": name,
                    "expected": expected,
                    "fired": sorted(fired),
                    "ok": expected in fired,
                }
            )

    # ---- A1: 图集元数据把某个字形的 x 挪 1 像素
    def m_a1(tmp: Path) -> None:
        p = tmp / f"{ps}-atlas.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["glyphs"][100][1] += 1
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    run(
        "图集元数据 x 挪 1px -> ATLAS_ORIGIN_MISMATCH",
        "ATLAS_ORIGIN_MISMATCH",
        m_a1,
        lambda t: check_atlas(t / f"{ps}-atlas.png", t / f"{ps}-atlas.json", stack, scope)["findings"],
    )

    # ---- A2a: 半角字形格子的空白区被点上墨 (渗进本格空白, 逼近邻格)
    def m_a2_leak(tmp: Path) -> None:
        p = tmp / f"{ps}-atlas.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data = json.loads(p.read_text(encoding="utf-8"))
        victim = next(g for g in data["glyphs"] if g[3] == 6)
        png = tmp / f"{ps}-atlas.png"
        from PIL import Image as _I

        img = _I.open(png).convert("RGBA")
        px = img.load()
        px[victim[1] + 8, victim[2]] = (255, 255, 255, 255)  # advance=6, 第 8 列在本格空白区
        img.save(png)

    run(
        "半角格空白区点墨 -> ATLAS_INK_LEAK",
        "ATLAS_INK_LEAK",
        m_a2_leak,
        lambda t: check_atlas(t / f"{ps}-atlas.png", t / f"{ps}-atlas.json", stack, scope)["findings"],
    )

    # ---- A2b: 格子内部翻一个像素 -> ATLAS_PIXEL_MISMATCH
    def m_a2_px(tmp: Path) -> None:
        png = tmp / f"{ps}-atlas.png"
        from PIL import Image as _I

        img = _I.open(png).convert("RGBA")
        px = img.load()
        # 取本 lane 第一个汉字的格子, 找一个当前是空白的像素点上墨
        cp = ord(scope[0][0])
        js = json.loads((tmp / f"{ps}-atlas.json").read_text(encoding="utf-8"))
        entry = next(g for g in js["glyphs"] if g[0] == cp)
        for y in range(13):
            for x in range(12):
                if px[entry[1] + x, entry[2] + y][3] == 0:
                    px[entry[1] + x, entry[2] + y] = (255, 255, 255, 255)
                    img.save(png)
                    return
        raise AssertionError("找不到空白像素")

    run(
        "格子内翻 1 像素 -> ATLAS_PIXEL_MISMATCH",
        "ATLAS_PIXEL_MISMATCH",
        m_a2_px,
        lambda t: check_atlas(t / f"{ps}-atlas.png", t / f"{ps}-atlas.json", stack, scope)["findings"],
    )

    # ---- A4: 墨色不是纯白
    def m_a4(tmp: Path) -> None:
        png = tmp / f"{ps}-atlas.png"
        from PIL import Image as _I

        img = _I.open(png).convert("RGBA")
        px = img.load()
        js = json.loads((tmp / f"{ps}-atlas.json").read_text(encoding="utf-8"))
        e = js["glyphs"][0]
        px[e[1], e[2]] = (255, 0, 0, 255)
        img.save(png)

    run(
        "墨色改成红 -> ATLAS_INK_COLOR",
        "ATLAS_INK_COLOR",
        m_a4,
        lambda t: check_atlas(t / f"{ps}-atlas.png", t / f"{ps}-atlas.json", stack, scope)["findings"],
    )

    # ---- B1: .notdef 改成单环实心
    def m_b1(tmp: Path) -> None:
        p = tmp / f"{ps}.ttf"
        tt = TTFont(str(p))
        pen = TTGlyphPen(None)
        pen.moveTo((0, -128))
        pen.lineTo((768, -128))
        pen.lineTo((768, 704))
        pen.lineTo((0, 704))
        pen.closePath()
        tt["glyf"][".notdef"] = pen.glyph()
        tt.save(str(p))

    run(
        ".notdef 改成单环实心 -> TTF_NOTDEF_NOT_BOX",
        "TTF_NOTDEF_NOT_BOX",
        m_b1,
        lambda t: check_ttf(t / f"{ps}.ttf", stack)["findings"],
    )

    # ---- B2: hhea.ascent 改错
    def m_b2(tmp: Path) -> None:
        p = tmp / f"{ps}.ttf"
        tt = TTFont(str(p))
        tt["hhea"].ascent += 7
        tt.save(str(p))

    run(
        "hhea.ascent 改 7 -> TTF_METRICS_MISMATCH",
        "TTF_METRICS_MISMATCH",
        m_b2,
        lambda t: check_ttf(t / f"{ps}.ttf", stack)["findings"],
    )

    # ---- B3a: 删掉 gasp 表
    def m_b3a(tmp: Path) -> None:
        p = tmp / f"{ps}.ttf"
        tt = TTFont(str(p))
        if "gasp" in tt:
            del tt["gasp"]
        tt.save(str(p))

    run(
        "删掉 gasp 表 -> TTF_NO_GASP",
        "TTF_NO_GASP",
        m_b3a,
        lambda t: check_ttf(t / f"{ps}.ttf", stack)["findings"],
    )

    # ---- B3b: gasp 12ppem 改成 2 (开灰度)
    def m_b3b(tmp: Path) -> None:
        p = tmp / f"{ps}.ttf"
        tt = TTFont(str(p))
        tt["gasp"].gaspRange[12] = 2
        tt.save(str(p))

    run(
        "gasp 12ppem 改 2 -> TTF_GASP_NOT_MONO",
        "TTF_GASP_NOT_MONO",
        m_b3b,
        lambda t: check_ttf(t / f"{ps}.ttf", stack)["findings"],
    )

    # ---- B4: maxp.maxPoints 写错
    def m_b4(tmp: Path) -> None:
        p = tmp / f"{ps}.ttf"
        tt = TTFont(str(p))
        tt["maxp"].maxPoints = 9999
        tt.save(str(p))

    run(
        "maxp.maxPoints 改 9999 -> TTF_MAXP_POINTS_MISMATCH",
        "TTF_MAXP_POINTS_MISMATCH",
        m_b4,
        lambda t: check_ttf(t / f"{ps}.ttf", stack)["findings"],
    )

    # ---- C1: CHARS 写错
    def m_c1(tmp: Path) -> None:
        p = tmp / f"{ps}.bdf"
        txt = p.read_text(encoding="utf-8")
        txt = txt.replace("\nCHARS 4140\n", "\nCHARS 4139\n", 1)
        p.write_text(txt, encoding="utf-8")

    run(
        "BDF CHARS 写错 -> BDF_HEADER_MISMATCH",
        "BDF_HEADER_MISMATCH",
        m_c1,
        lambda t: check_bdf(t / f"{ps}.bdf", stack, items_all, glyphs_all, run_fix_sim=False)["findings"],
    )

    # ---- C2a: 塞一个多余的 ENDCHAR
    def m_c2a(tmp: Path) -> None:
        p = tmp / f"{ps}.bdf"
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines):
            if ln.strip() == "ENDCHAR":
                lines.insert(i, "ENDCHAR")
                break
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    run(
        "BDF 塞多余 ENDCHAR -> BDF_ENDCHAR_PAIRING",
        "BDF_ENDCHAR_PAIRING",
        m_c2a,
        lambda t: check_bdf(t / f"{ps}.bdf", stack, items_all, glyphs_all, run_fix_sim=False)["findings"],
    )

    # ---- C2b: 某行填充位写成 1 (只动低 4 位, 不碰像素位)
    def m_c2b(tmp: Path) -> None:
        p = tmp / f"{ps}.bdf"
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines):
            if ln.startswith("BBX 12 "):
                # 下一行是 BITMAP, 再下一行是第一个数据行 (12px 宽 -> 2 字节)
                row = lines[i + 2].strip()
                assert len(row) == 4, row
                val = int(row, 16) | 0x000F  # 低 4 位是填充位, 像素位在高位
                lines[i + 2] = f"{val:04X}"
                break
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    run(
        "BDF 行填充位置 1 -> BDF_ROW_PADDING",
        "BDF_ROW_PADDING",
        m_c2b,
        lambda t: check_bdf(t / f"{ps}.bdf", stack, items_all, glyphs_all, run_fix_sim=False)["findings"],
    )

    # ---- D1: 伪造两个不同汉字同位图
    def m_d1(stack2=stack, scope2=scope) -> list[dict]:
        a, b = scope2[0][0], scope2[1][0]
        ga = stack2.glyph(a)
        px = ga.load()
        sig = tuple(tuple(1 if px[x, y] > 0 else 0 for x in range(ga.width)) for y in range(ga.height))
        return check_uniqueness(stack2, scope2, items_all, sig_override={b: sig})["findings"]

    d1_fired = _ids(m_d1())
    results.append(
        {
            "case": "两个不同汉字同位图 -> HANZI_DUPLICATE_BITMAP",
            "expected": "HANZI_DUPLICATE_BITMAP",
            "fired": sorted(d1_fired),
            "ok": "HANZI_DUPLICATE_BITMAP" in d1_fired,
        }
    )

    del GAUGE[gauge_mark:]  # 自检的量具行不计入正式报告
    return results


# ================================================================ 报告


def render_markdown(rep: dict) -> str:
    s = rep["summary"]
    L = [
        f"# 成品结构级校验 (补充探针) — {rep['selection']['label']}",
        "",
        f"- 生成时间: {rep['generated_at']}",
        f"- 分支: `{rep['lane']}`",
        f"- 判定: **{s['verdict']}** (error {s['errors']} / warn {s['warnings']} / info {s['infos']})",
        f"- 覆盖: 本 lane {rep['inputs']['chars_in_scope']} 字 "
        f"(hanzi {rep['selection']['slice']}, 全字符集 {rep['inputs']['charset_total']} 字)",
        "",
        "本探针只查**成品文件的骨架**: 图集网格对齐 / TTF 表结构 / BDF 头尾与字符块结构 / 汉字位图唯一性。"
        "字形内容的一致性由共享工具 `tools/fontgen/regress.py` 负责 (见 reports/hanzi-b.md)。",
        "",
    ]
    if s["verdict"] == "NO_DATA":
        L.append("> **没有测到任何东西** —— 不构成任何结论。")
        L.append("")
        L.append(f"原因: {rep['inputs'].get('reason', '未说明')}")
        return "\n".join(L) + "\n"

    L.append("## 1. 量具可靠性 (消费了多少输入, 多少处读取失败)")
    L.append("")
    L.append("| 检查项 | 样本数 | 失败数 | 读取失败 | 判定 | 覆盖说明 |")
    L.append("|---|---|---|---|---|---|")
    for g in rep["gauge"]:
        L.append(
            f"| `{g['id']}` {g['title']} | {g['samples']} | {g['failures']} | {g['read_errors']} | "
            f"{'PASS' if g['failures'] == 0 else 'FAIL'} | {g['note']} |"
        )
    L.append("")
    L.append("> 说明: `bdflib` 与 X11 `bdftopcf` 在本机均未安装, 因此 \"标准解析器能否接受\" "
             "由**两个互相独立的解析器** (本探针的严格解析器 + regress.py 的 decode_bdf) "
             "加生产门禁 build_font.verify_bdf 三方共同判定。")
    L.append("")

    st = rep.get("gauge_selftest", {})
    L.append("### 量具自检 (注入已知坏数据, 断言检测器会响)")
    L.append("")
    if not st.get("ran"):
        L.append("本次跳过量具自检 (`--no-selftest`)。")
        L.append("")
    else:
        L.append(f"注入 {st['cases_total']} 个已知坏数据用例, {st['cases_ok']} 个检测器如期报警, "
                 f"{st['cases_failed']} 个失灵。")
        L.append("")
        L.append("| 注入的坏数据 | 期望报警 | 实际报警 | 结果 |")
        L.append("|---|---|---|---|")
        for c in st["cases"]:
            L.append(
                f"| {c['case'].split(' -> ')[0]} | `{c['expected']}` | "
                f"{', '.join('`' + x + '`' for x in c['fired']) or '(无)'} | "
                f"{'PASS' if c['ok'] else 'FAIL'} |"
            )
        L.append("")

    L.append("## 2. 异常清单")
    L.append("")
    if not rep["anomalies"]:
        L.append("无异常。")
        L.append("")
    else:
        L.append("| 异常 ID | 级别 | 对象 | 证据 | 建议改法 |")
        L.append("|---|---|---|---|---|")
        for a in rep["anomalies"]:
            obj = a.get("cp", "-")
            if a.get("char"):
                obj += " " + a["char"]
            ev = json.dumps(a.get("evidence", {}), ensure_ascii=False)
            if len(ev) > 220:
                ev = ev[:220] + "…"
            ev = ev.replace("|", "\\|").replace("\n", " ")
            fix = a.get("suggested_fix", "-").replace("|", "\\|")
            L.append(f"| `{a['id']}` | {a['severity']} | {obj} | {ev} | {fix} |")
        L.append("")
        for a in rep["anomalies"]:
            L.append(f"### {a['id']} — {a.get('cp', '')} {a.get('char', '')}")
            L.append("")
            L.append(f"- 说明: {a['detail']}")
            if a.get("suggested_fix"):
                L.append(f"- 建议改法: {a['suggested_fix']}")
            art = (a.get("evidence") or {}).get("art")
            if art:
                L.append("")
                L.append("```")
                L.append(art)
                L.append("```")
            L.append("")

    L.append("## 3. A 图集网格对齐")
    L.append("")
    am = rep["atlas"]
    L.append(f"- 元数据: columns={am['meta']['columns']}, rows={am['meta']['rows']}, cell={am['meta']['cell']}, "
             f"PNG 实际尺寸={am['meta']['png_size']}, 字形数={am['meta']['glyph_count']}")
    L.append(f"- A1 单元格原点: {rep['gauge_by_id']['A1']['failures']} 处不符 (遍历全部 {rep['gauge_by_id']['A1']['samples']} 条元数据)")
    L.append(f"- A2 墨迹不渗邻格: 结构层 {rep['gauge_by_id']['A2']['samples']} 格 + 像素层 {rep['inputs']['chars_in_scope']} 字, "
             f"{rep['gauge_by_id']['A2']['failures']} 处失败")
    L.append("")

    L.append("## 4. B TTF 结构")
    L.append("")
    b1 = rep["ttf"]["evidence"]["B1"]
    L.append(f"- .notdef: 轮廓数 {b1['numberOfContours']}, x {b1['xMin']}..{b1['xMax']} "
             f"(期望 {b1['expect_xMin']}..{b1['expect_xMax']}), y {b1['yMin']}..{b1['yMax']} "
             f"(期望 {b1['expect_yMin']}..{b1['expect_yMax']})")
    L.append(f"- 两环有向面积: {b1['contour_signed_areas']} (异号 = 非零填充下为空心)")
    L.append("")
    L.append("非零环绕规则栅格化结果 (本探针自算, 与期望空心方框逐像素比对):")
    L.append("")
    L.append("```")
    L.append(b1["rasterized"])
    L.append("```")
    L.append("")
    b4 = rep["ttf"]["evidence"]["B4"]
    L.append(f"- maxp: maxPoints {b4['maxp_maxPoints']} (实际 {b4['actual_maxPoints']}), "
             f"maxContours {b4['maxp_maxContours']} (实际 {b4['actual_maxContours']}), "
             f"numGlyphs {b4['maxp_numGlyphs']} (字形表 {b4['glyph_order_len']})")
    L.append("")

    L.append("## 5. C BDF 头尾与字符块结构")
    L.append("")
    bd = rep["bdf"]
    L.append(f"- 字符块数: {bd['blocks']}")
    L.append(f"- 零墨迹字形: {len(bd['zero_ink'])} 个")
    L.append("")
    if bd["zero_ink"]:
        L.append("| 码位 | ENDCHAR 数 | 有 BITMAP 段 | BITMAP 行数 | 起始行 |")
        L.append("|---|---|---|---|---|")
        for z in bd["zero_ink"]:
            L.append(
                f"| {z['cp']} | {z['endchar_count']} | {'是' if z['bitmap_present'] else '否'} | "
                f"{z['bitmap_rows']} | {z['line']} |"
            )
        L.append("")
    L.append("### 修法回灌 (删掉多余的 ENDCHAR) 复核")
    L.append("")
    L.append("| 解析器 | 结果 | 明细 |")
    L.append("|---|---|---|")
    for c in bd["fix_sim"]["checked"]:
        detail = ", ".join(f"{k}={v}" for k, v in c.items() if k not in ("parser", "ok"))
        L.append(f"| `{c['parser']}` | {'PASS' if c['ok'] else 'FAIL'} | {detail} |")
    L.append("")
    L.append(f"- 删除的多余 ENDCHAR 数: {bd['fix_sim']['endchar_removed']}")
    vnb = bd["fix_sim"].get("variant_no_bitmap")
    if vnb:
        L.append("")
        L.append(f"- 反面对照 (把零墨迹块的 BITMAP 段整段删掉): regress.decode_bdf 解析到 "
                 f"{vnb['parsed_glyphs_after']} 个码位 (保留 BITMAP 时是 {vnb['parsed_glyphs']} 个), "
                 f"U+0020 {'仍能' if vnb['space_found_after'] else '**收不到**'} —— "
                 "所以修法必须**保留 BITMAP 关键字**, 只删多余的 ENDCHAR。")
    L.append("")

    L.append("## 6. D 汉字位图唯一性")
    L.append("")
    u = rep["uniqueness"]
    L.append(f"- 本 lane 批内同位图组: {len(u['batch_dups'])}")
    L.append(f"- 全 3755 汉字内部同位图组: {u['hanzi_all_dups_total']} (含批外的字, 供集成者参考)")
    L.append(f"- 跨类别同位图组: {u['cross_category_total']} (合法, 两个源字体本来就画得一样, 不算缺陷)")
    L.append("")
    if u["batch_dups"]:
        for g in u["batch_dups"]:
            L.append("```")
            L.append(g["art"])
            L.append("```")
            L.append("  " + "  ".join(f"{m['char']} {m['cp']}" for m in g["members"]))
            L.append("")

    L.append("## 7. 假设与局限")
    L.append("")
    for a in rep["assumptions"]:
        L.append(f"- {a}")
    L.append("")
    return "\n".join(L) + "\n"


# ================================================================ main


def main() -> int:
    ap = argparse.ArgumentParser(description="hanzi_b 成品结构级校验探针")
    ap.add_argument("--dist", default=str(ROOT / "dist"), help="成品目录 (默认 dist/)")
    ap.add_argument("--out", default=str(ROOT / "reports" / "hanzi-b_extra.json"))
    ap.add_argument("--cats", default="hanzi")
    ap.add_argument("--slice", dest="slice_", default="1900:3755")
    ap.add_argument("--rebuild", action="store_true", help="先跑一次生产构建再校验")
    ap.add_argument("--no-selftest", action="store_true", help="跳过量具自检 (注入坏数据断言检测器会响)")
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    dist = Path(args.dist)

    ps_name = bf.PS_NAME
    bdf_path = dist / f"{ps_name}.bdf"
    ttf_path = dist / f"{ps_name}.ttf"
    png_path = dist / f"{ps_name}-atlas.png"
    js_path = dist / f"{ps_name}-atlas.json"

    missing = [p.name for p in (bdf_path, ttf_path, png_path, js_path) if not p.exists()]
    if missing and args.rebuild:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "fontgen" / "build_font.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
        )
        if proc.returncode != 0:
            print("构建失败, 不构成任何结论", file=sys.stderr)
            return 2
        missing = [p.name for p in (bdf_path, ttf_path, png_path, js_path) if not p.exists()]
    if missing:
        report = {
            "tool": "hanzi_b_probe",
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "lane": "agent/reg-hanzi-b",
            "selection": {"cats": args.cats.split(","), "slice": args.slice_, "label": "hanzi_b"},
            "inputs": {"charset_total": 0, "chars_in_scope": 0, "reason": f"成品缺失: {missing}"},
            "gauge": [],
            "anomalies": [],
            "summary": {"errors": 0, "warnings": 0, "infos": 0, "verdict": "NO_DATA"},
        }
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        out.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
        print(f"成品缺失 {missing} —— 没有测到东西, 退出码 2", file=sys.stderr)
        return 2

    # ---- 字符集与本 lane 范围
    items_all = cs.build_charset()
    stack = cs.build_stack()
    cats = [c.strip() for c in args.cats.split(",") if c.strip()]
    sel = [(ch, cat) for ch, cat in items_all if cat in cats]
    a, _, b = args.slice_.partition(":")
    s0 = int(a) if a else 0
    s1 = int(b) if b else len(sel)
    scope = sel[s0:s1]
    if not scope:
        print("选择为空 —— 没有测到东西", file=sys.stderr)
        return 2

    m = stack.metrics

    # ---- 各项检查
    atlas = check_atlas(png_path, js_path, stack, scope)
    ttf = check_ttf(ttf_path, stack)
    glyphs_all = bf.collect_glyphs(stack, items_all)
    bdf = check_bdf(bdf_path, stack, items_all, glyphs_all)
    uniq = check_uniqueness(stack, scope, items_all)

    # ---- 量具自检: 注入已知坏数据, 断言每个检测器会响 (否则"全部 PASS"只是"没报异常")
    st = []
    if not args.no_selftest:
        st = selftest(dist, stack, scope, items_all, glyphs_all)
        failed = [r for r in st if not r["ok"]]
        if failed:
            print(f"量具自检失败 {len(failed)}/{len(st)} 项: "
                  + "; ".join(f"{r['case']} (期望 {r['expected']}, 实到 {r['fired']})" for r in failed),
                  file=sys.stderr)

    anomalies: list[dict] = []
    anomalies += atlas["findings"]
    anomalies += ttf["findings"]
    anomalies += bdf["findings"]
    anomalies += uniq["findings"]

    errors = sum(1 for x in anomalies if x["severity"] == ERROR)
    warns = sum(1 for x in anomalies if x["severity"] == WARN)
    infos = sum(1 for x in anomalies if x["severity"] == INFO)
    verdict = "FAIL" if errors else "PASS"

    gauge_by_id = {g["id"]: g for g in GAUGE}
    artifacts = {}
    for label, p in (("bdf", bdf_path), ("ttf", ttf_path), ("atlas_png", png_path), ("atlas_json", js_path)):
        artifacts[label] = {
            "path": str(p.relative_to(ROOT)).replace("\\", "/"),
            "bytes": p.stat().st_size,
            "sha256": sha256_of(p),
        }

    report = {
        "tool": "hanzi_b_probe",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lane": "agent/reg-hanzi-b",
        "selection": {
            "cats": cats,
            "slice": args.slice_,
            "label": "hanzi_b",
            "scope_first_cp": f"U+{ord(scope[0][0]):04X}",
            "scope_last_cp": f"U+{ord(scope[-1][0]):04X}",
        },
        "inputs": {
            "charset_total": len(items_all),
            "hanzi_total": sum(1 for _, c in items_all if c == "hanzi"),
            "chars_in_scope": len(scope),
            "grid": {
                "cell_w": m.cell_w,
                "cell_h": m.cell_h,
                "half_w": m.half_w,
                "ascent": m.ascent,
                "descent": m.descent,
            },
            "artifacts": artifacts,
        },
        "gauge": GAUGE,
        "gauge_by_id": gauge_by_id,
        "gauge_selftest": {
            "ran": not args.no_selftest,
            "cases": st,
            "cases_total": len(st),
            "cases_ok": sum(1 for r in st if r["ok"]),
            "cases_failed": sum(1 for r in st if not r["ok"]),
        },
        "atlas": {"meta": atlas["meta"]},
        "ttf": {"evidence": ttf["evidence"]},
        "bdf": {
            "blocks": bdf["blocks"],
            "header": bdf["header"],
            "zero_ink": bdf["zero_ink"],
            "fix_sim": bdf["fix_sim"],
        },
        "uniqueness": {
            "batch_dups": uniq["batch_dups"],
            "cross_category": uniq["cross_category"],
            "cross_category_total": uniq["cross_category_total"],
            "hanzi_all_dups": uniq["hanzi_all_dups"],
            "hanzi_all_dups_total": uniq["hanzi_all_dups_total"],
        },
        "anomalies": anomalies,
        "assumptions": [
            "本探针不重建成品时, 校验对象是 dist/ 里已有的产物 —— 报告里记了每个产物的 sha256, "
            "结论只对那一份产物成立。",
            "结构级判定的参照系是栅格化器度量 (charset.build_stack): cell "
            f"{m.cell_w}x{m.cell_h}, 基线 {m.ascent}/{m.descent}; "
            "成品里的头字段若与之不符, 以栅格化器为准 (成品是派生物)。",
            "A 路墨迹比较以 alpha 通道为判据 (元数据声明 \"白色 + alpha\"), RGB 另作 A4 单列检查。",
            "环境内无第三方 BDF 解析器 (bdflib / X11 bdftopcf 均未安装), "
            "因此 C4 的\"修法回灌\"由本探针严格解析器 + regress.decode_bdf + 生产门禁 build_font.verify_bdf 三方判定。",
            "D 组位图唯一性只在汉字之间比对; 跨类别同位图 (如片假名「ニ」与汉字「二」) 按任务约定视为合法。",
        ],
        "summary": {
            "errors": errors,
            "warnings": warns,
            "infos": infos,
            "verdict": verdict,
        },
    }

    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")

    print(f"[hanzi_b_probe] 覆盖 {len(scope)} 字  error={errors} warn={warns} info={infos}  判定={verdict}")
    for g in GAUGE:
        print(f"   {g['id']}: 样本 {g['samples']} 失败 {g['failures']} 读取失败 {g['read_errors']}")
    if st:
        bad = [r for r in st if not r["ok"]]
        print(f"   量具自检: {len(st) - len(bad)}/{len(st)} 项如期报警"
              + (f" (失灵: {[r['case'] for r in bad]})" if bad else ""))
    for a in anomalies:
        print(f"   ! {a['id']} {a.get('cp','')} {a['detail'][:90]}")
    print(f"   报告: {out}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
