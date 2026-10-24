"""回归测试 —— 分批抽样 + 四路交叉对比 + 异常检测。

为什么要另写一个 harness, 而不是只跑 build_font.py:
build_font 里的 verify_* 只保证"成品 == 源位图", 那是同一条流水线里的**自证** ——
源位图本身错了, 成品会跟着错, 回读校验照样通过。真正的回归测试必须引入流水线
之外的事实来对照:

    · 源字体的真实墨迹范围 (掩码实际有多宽, 会被 cell 裁掉多少)
    · 源字体的真实 advance (这个字符在源字体里到底占半角还是全角)
    · 字体文件格式的结构约定 (BDF 的 ENDCHAR 配对 / TTF 的 lsb / cmap 完整性)
    · 批与批之间的统计一致性 (某一整批突然变密 / 变稀 / 基线漂移)

四路交叉对比 —— 同一个字形, 四条互相独立的路径必须给出同一张位图:
    R = 栅格化器现场渲染 (rasterizer)
    B = 从 BDF 成品解码回来
    T = 从 TTF 成品轮廓反解回来
    A = 从 PNG 图集 + 元数据解码回来
任何一路不一致, 说明成品写坏了、或者读回逻辑本身理解错了。

分批抽样 —— 字符集按类别切开后按固定批量切批, 每批统计墨量/基线/宽度分布,
再拿每批跟全字符集参考分布对比, 找出离群批。单个字符的问题会被批统计放大
成"这一批整体不对劲", 便于定位到路由/字号层面的系统性错误。

用法:
    python tools/fontgen/regress.py --cats ascii,punct --out reports/ascii_punct.json
    python tools/fontgen/regress.py --cats hanzi --slice 0:1900 --out reports/hz_a.json
    python tools/fontgen/regress.py --selftest          # 量具自检: 注入坏数据, 断言检测器会响

输出:
    <out>            JSON 全量结果 (机器读)
    <out>.md         人读摘要 (同一份数据的另一种渲染, 不是另一次计算)

退出码:
    0 = 无 error 级异常
    1 = 有 error 级异常
    2 = 没测到东西 (输入为空 / 构建失败) —— 绝不用 PASS 冒充
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image  # noqa: E402

import build_font as bf  # noqa: E402
import charset as cs  # noqa: E402
from bitfont import ScriptStack  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PS_NAME = bf.PS_NAME
# 空白字符: 本来就没有墨迹, **不能**按"缺字/豆腐块"判。
# U+0020 空格 / U+3000 全角空格 / U+00A0 不换行空格 / U+0009 制表符。
# 用转义写 —— 这些字符在源码里是看不见的, 写成字面量等于埋雷 (见 charset.extras 的同一条纪律)。
WHITESPACE = {"\u0020", "\u3000", "\u00a0", "\t"}

# 严重级别
ERROR = "error"
WARN = "warn"
INFO = "info"


# ================================================================ 异常记录


@dataclass
class Anomaly:
    id: str
    severity: str
    detail: str
    cp: int | None = None
    char: str = ""
    category: str = ""
    batch: int = -1
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "severity": self.severity,
            "detail": self.detail,
        }
        if self.cp is not None:
            d["cp"] = f"U+{self.cp:04X}"
            d["char"] = self.char
            d["category"] = self.category
        if self.batch >= 0:
            d["batch"] = self.batch
        if self.evidence:
            d["evidence"] = self.evidence
        return d


class AnomalyBag:
    def __init__(self) -> None:
        self.items: list[Anomaly] = []

    def add(self, a: Anomaly) -> None:
        self.items.append(a)

    def count(self, severity: str) -> int:
        return sum(1 for a in self.items if a.severity == severity)

    def ids(self) -> set[str]:
        return {a.id for a in self.items}


# ================================================================ 纯规则
#
# 检测规则单独抽成纯函数 (输入 -> 是否异常), 这样量具自检可以喂合成数据,
# 证明"检测器确实会响", 而不是拿真实数据碰运气。


def rule_clip(ink_w: int, dx: int, ink_h: int, dy: int, cell_w: int, cell_h: int) -> list[str]:
    """源字体墨迹超出分配到的 cell -> 会被裁掉。

    这是"宽度判定错"的直接症状: 字符拿到了半角格 (6px), 但源字体里它是
    12px 的全角字形, 右半边整整 6 列墨迹被切掉。
    """
    out = []
    if ink_w and dx + ink_w > cell_w:
        out.append("CLIP_RIGHT")
    if ink_h and dy + ink_h > cell_h:
        out.append("CLIP_BOTTOM")
    return out


def rule_advance(src_advance: int, cell_w: int) -> str | None:
    """源字体实测 advance 与分配到的 cell 宽度不一致。

    这是 CLIP 的**根因信号**: 源字体说它要 12px, 我们却只给了 6px 格。
    """
    if src_advance and abs(src_advance - cell_w) > 0:
        return "SOURCE_ADVANCE_MISMATCH"
    return None


def rule_empty_ink(ink: int, ch: str) -> bool:
    """没有墨迹, 且不是空白字符 -> 缺字/豆腐块。"""
    return ink == 0 and ch not in WHITESPACE


def rule_atlas_wide(advance: int, wide_flag: int, cell_w: int, half_w: int) -> bool:
    """图集的 isWide 标记必须跟实际 advance 一致。

    按"分类"写标记是错的: 半角片假名 (ｦ ｧ ...) 和半角标点 (｡ ｢ ...) 的
    advance 是 6, 但只要分类不是 ascii 就会被标成全角, 引擎按全角推进就会错位。
    """
    expect = 1 if advance == cell_w else 0
    return int(wide_flag) != expect


def rule_lsb(lsb: int, ink_xmin: int, px: int) -> bool:
    """hmtx 的 lsb 必须等于墨迹左边缘。

    lsb 一律填 0 会让墨迹不从 x=0 开始的窄字形 (! ' ( ) , 等) 被整体左移。
    """
    return lsb != ink_xmin * px


def rule_bdf_rows(bbx_h: int, bitmap_rows: int) -> bool:
    """BBX 声明的高度必须与 BITMAP 实际行数一致。"""
    return bbx_h != bitmap_rows


def rule_bdf_padding(w: int, hexs: str) -> bool:
    """BDF 每行按字节对齐, 填充位必须是 0 (否则渲染器会把填充位当成墨迹)。"""
    nbytes = (w + 7) // 8
    if not hexs:
        return nbytes != 0
    if len(hexs) != nbytes * 2:
        return True
    val = int(hexs, 16)
    used = w % 8
    if used == 0:
        return False
    pad_mask = (1 << (8 - used)) - 1
    return bool(val & pad_mask)


def rule_density(d: float, median: float, mad: float, sigma: float) -> bool:
    """墨量离群 (相对全字符集参考分布)。

    用 median + MAD 而不是 mean + std: 离群点本身会把 std 拉大, 导致
    真正的离群点反而测不出来 (掩耳盗铃)。MAD 对离群点不敏感。
    """
    if mad > 0:
        return abs(d - median) / (1.4826 * mad) > 6.0
    if sigma > 0:
        return abs(d - median) / sigma > 6.0
    return False


# ================================================================ 产物读取


@dataclass
class Artifacts:
    d: Path

    @property
    def bdf(self) -> Path:
        return self.d / f"{PS_NAME}.bdf"

    @property
    def ttf(self) -> Path:
        return self.d / f"{PS_NAME}.ttf"

    @property
    def atlas_png(self) -> Path:
        return self.d / f"{PS_NAME}-atlas.png"

    @property
    def atlas_json(self) -> Path:
        return self.d / f"{PS_NAME}-atlas.json"

    def missing(self) -> list[str]:
        out = []
        for label, p in (
            ("bdf", self.bdf),
            ("ttf", self.ttf),
            ("atlas.png", self.atlas_png),
            ("atlas.json", self.atlas_json),
        ):
            if not p.exists():
                out.append(label)
        return out


def decode_bdf(path: Path, ascent: int, cell_w: int, cell_h: int) -> tuple[dict, list[str]]:
    """严格解析 BDF。

    返回 ({cp: (w, h, xoff, rows)}, 结构问题列表)。
    刻意严格: ENDCHAR 配对、BBX 高度 vs BITMAP 行数、每行位宽、填充位。
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    parsed: dict[int, tuple[int, int, int, list[list[int]]]] = {}
    issues: list[str] = []
    i = 0
    cur: int | None = None
    start_count = 0
    end_count = 0
    while i < len(lines):
        ln = lines[i].strip()
        if ln.startswith("STARTCHAR"):
            start_count += 1
        elif ln == "ENDCHAR":
            end_count += 1
        elif ln.startswith("ENCODING "):
            cur = int(ln.split()[1])
        elif ln == "BITMAP" and cur is not None:
            w, h, xoff, yoff = (int(v) for v in lines[i - 1].split()[1:5])
            nbytes = (w + 7) // 8
            rows = [[0] * cell_w for _ in range(cell_h)]
            bitmap_rows = 0
            for k in range(h):
                if i + 1 + k >= len(lines):
                    issues.append(f"U+{cur:04X} BITMAP 行数不足 (声明 {h} 行)")
                    break
                hexs = lines[i + 1 + k].strip()
                bitmap_rows += 1
                if rule_bdf_padding(w, hexs):
                    issues.append(f"U+{cur:04X} 第 {k} 行位宽/填充位异常: {hexs!r}")
                val = int(hexs, 16) if hexs else 0
                bits = [(val >> (nbytes * 8 - 1 - b)) & 1 for b in range(nbytes * 8)]
                for b in range(w):
                    if bits[b]:
                        yy = ascent + yoff + k
                        if 0 <= yy < cell_h and xoff + b < cell_w:
                            rows[yy][xoff + b] = 1
            if rule_bdf_rows(h, bitmap_rows):
                issues.append(f"U+{cur:04X} BBX 高度 {h} != BITMAP 行数 {bitmap_rows}")
            parsed[cur] = (w, h, xoff, rows)
            i += h
        i += 1
    if start_count != end_count:
        issues.append(
            f"STARTCHAR {start_count} 个但 ENDCHAR {end_count} 个 —— 字符块结构不配对"
        )
    return parsed, issues


def decode_ttf(path: Path, ascent: int, cell_w: int, cell_h: int, cps: list[int]) -> dict:
    """从 TTF 轮廓反解像素位图, 并取出 cmap / hmtx。"""
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.ttLib import TTFont

    tt = TTFont(str(path))
    upm = tt["head"].unitsPerEm
    if upm % cell_w:
        raise SystemExit(f"TTF upm={upm} 与 em 宽 {cell_w} 不整除")
    px = upm // cell_w
    glyphset = tt.getGlyphSet()
    cmap = tt.getBestCmap()
    hmtx = tt["hmtx"]
    out: dict[int, dict] = {}
    for cp in cps:
        name = cmap.get(cp)
        if name is None:
            out[cp] = {"rows": None, "lsb": None, "advance": None, "name": None}
            continue
        pen = DecomposingRecordingPen(glyphset[name])
        glyphset[name].draw(pen)
        cell = [[0] * cell_w for _ in range(cell_h)]
        cur: list[tuple[float, float]] = []
        for op, args in pen.value:
            if op == "moveTo":
                cur = [args[0]]
            elif op == "lineTo":
                cur.append(args[0])
            elif op == "closePath":
                if len(cur) == 4:
                    xs = [p[0] for p in cur]
                    ys = [p[1] for p in cur]
                    cx0, cx1 = int(min(xs) // px), int(max(xs) // px)
                    r0, r1 = ascent - int(max(ys) // px), ascent - int(min(ys) // px)
                    for r in range(r0, r1):
                        for c in range(cx0, cx1):
                            if 0 <= r < cell_h and 0 <= c < cell_w:
                                cell[r][c] = 1
                cur = []
        out[cp] = {
            "rows": cell,
            # hmtx.metrics[name] = (advance, lsb) —— 顺序别搞反
            "lsb": hmtx.metrics[name][1] if name in hmtx.metrics else None,
            "advance": hmtx.metrics[name][0] if name in hmtx.metrics else None,
            "name": name,
        }
    return out


def decode_atlas(png: Path, js: Path) -> tuple[dict, dict]:
    """从图集 PNG + 元数据解码。返回 ({cp: rows}, 元数据)。"""
    img = Image.open(png).convert("RGBA")
    px = img.load()
    data = json.loads(js.read_text(encoding="utf-8"))
    cw, ch = data["cell"]["w"], data["cell"]["h"]
    out: dict[int, list[list[int]]] = {}
    for cp, gx, gy, adv, wide in data["glyphs"]:
        rows = [
            [1 if px[gx + x, gy + y][3] > 0 else 0 for x in range(cw)] for y in range(ch)
        ]
        out[cp] = rows
    return out, data


# ================================================================ 主检查


def collect_reference(items: list[tuple[str, str]], stack: ScriptStack) -> dict:
    """全字符集参考分布 (只用栅格化器, 快且不依赖成品)。"""
    dens: list[float] = []
    tops: list[int] = []
    bots: list[int] = []
    by_cat: dict[str, list[float]] = defaultdict(list)
    for ch, cat in items:
        g = stack.glyph(ch)
        p = g.load()
        on = sum(1 for y in range(g.height) for x in range(g.width) if p[x, y] > 0)
        dens.append(on / max(1, g.width * g.height))
        by_cat[cat].append(on / max(1, g.width * g.height))
        ys = [y for y in range(g.height) for x in range(g.width) if p[x, y] > 0]
        if ys:
            tops.append(min(ys))
            bots.append(max(ys))
    dens.sort()
    n = len(dens)

    def pct(p: float) -> float:
        if not dens:
            return 0.0
        return dens[min(n - 1, max(0, int(round(p * (n - 1)))))]

    med = pct(0.5)
    mad = sorted(abs(d - med) for d in dens)[n // 2] if dens else 0.0
    sigma = (sum((d - med) ** 2 for d in dens) / n) ** 0.5 if dens else 0.0
    return {
        "density_median": med,
        "density_mad": mad,
        "density_sigma": sigma,
        "density_p95": pct(0.95),
        "density_max": dens[-1] if dens else 0.0,
        "ink_top_median": sorted(tops)[len(tops) // 2] if tops else 0,
        "ink_bottom_median": sorted(bots)[len(bots) // 2] if bots else 0,
        "cat_density_median": {k: sorted(v)[len(v) // 2] for k, v in by_cat.items()},
        "chars": n,
    }


def run_checks(
    art: Artifacts,
    stack: ScriptStack,
    items: list[tuple[str, str]],
    selected: list[tuple[str, str]],
    batches: list[list[tuple[str, str]]],
    ref: dict,
) -> tuple[AnomalyBag, dict]:
    """对选定字符做四路交叉对比 + 异常检测。"""
    bag = AnomalyBag()
    m = stack.metrics
    ascent, descent = m.ascent, m.descent
    cell_w, cell_h = m.cell_w, m.cell_h
    half_w = m.half_w

    missing = art.missing()
    if missing:
        bag.add(
            Anomaly(
                "ARTIFACT_MISSING",
                ERROR,
                f"成品缺失: {', '.join(missing)}",
            )
        )
        return bag, {}

    sel_cps = [ord(ch) for ch, _ in selected]
    # 字符 -> 批号: 预建索引, 否则逐字扫批号是 O(n^2)
    batch_of: dict[str, int] = {}
    for bi, b in enumerate(batches):
        for ch, _ in b:
            batch_of.setdefault(ch, bi)
    bdf_rows, bdf_issues = decode_bdf(art.bdf, ascent, cell_w, cell_h)
    for issue in bdf_issues[:20]:
        bag.add(Anomaly("BDF_STRUCTURE", ERROR, issue))
    ttf = decode_ttf(art.ttf, ascent, cell_w, cell_h, sel_cps)
    atlas_rows, atlas_meta = decode_atlas(art.atlas_png, art.atlas_json)
    atlas_entries = {m_[0]: m_ for m_ in atlas_meta["glyphs"]}

    # ---- 逐字符四路对比
    dup_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for idx, (ch, cat) in enumerate(selected):
        cp = ord(ch)
        batch_no = batch_of.get(ch, -1)
        g = stack.glyph(ch)
        gp = g.load()
        R = [[1 if gp[x, y] > 0 else 0 for x in range(g.width)] for y in range(g.height)]
        rw, rh = g.width, g.height
        ink = sum(sum(r) for r in R)

        if rule_empty_ink(ink, ch):
            bag.add(
                Anomaly(
                    "EMPTY_INK",
                    ERROR,
                    f"{ch!r} 没有任何墨迹 (缺字/豆腐块)",
                    cp=cp,
                    char=ch,
                    category=cat,
                    batch=batch_no,
                )
            )

        # 源字体墨迹/advance 对照 (宽度判定错的话, 这里会响)
        src = stack._pick(ch)
        try:
            mask, (dx, dy) = src._render_mask(ch)
        except Exception:  # noqa: BLE001
            mask, (dx, dy) = None, (0, 0)
        if mask is not None:
            for rid in rule_clip(mask.width, dx, mask.height, dy, rw, cell_h):
                bag.add(
                    Anomaly(
                        rid,
                        ERROR,
                        f"{ch!r} 源字形 {mask.width}x{mask.height} 起点({dx},{dy}) "
                        f"超出 {rw}x{cell_h} 的格 —— 右侧/底部墨迹被裁掉",
                        cp=cp,
                        char=ch,
                        category=cat,
                        batch=batch_no,
                        evidence={"mask": [mask.width, mask.height], "offset": [dx, dy], "cell": [rw, cell_h]},
                    )
                )
        try:
            src_adv = round(src._font.getlength(ch))
        except Exception:  # noqa: BLE001
            src_adv = 0
        if rule_advance(src_adv, rw):
            bag.add(
                Anomaly(
                    "SOURCE_ADVANCE_MISMATCH",
                    WARN,
                    f"{ch!r} 源字体实测 advance={src_adv}, 但分配到的格宽={rw} "
                    f"(EAW={unicodedata.east_asian_width(ch)})",
                    cp=cp,
                    char=ch,
                    category=cat,
                    batch=batch_no,
                    evidence={"src_advance": src_adv, "cell": rw, "eaw": unicodedata.east_asian_width(ch)},
                )
            )

        # B 路
        if cp not in bdf_rows:
            bag.add(
                Anomaly("BDF_MISSING", ERROR, f"{ch!r} 不在 BDF 中", cp=cp, char=ch, category=cat, batch=batch_no)
            )
        else:
            bw, bh, bxoff, B = bdf_rows[cp]
            diff = sum(
                1 for y in range(rh) for x in range(rw) if B[y][x] != R[y][x]
            )
            if diff:
                bag.add(
                    Anomaly(
                        "MISMATCH_BDF",
                        ERROR,
                        f"{ch!r} 栅格化器与 BDF 成品差 {diff} px",
                        cp=cp, char=ch, category=cat, batch=batch_no,
                        evidence={"diff_px": diff},
                    )
                )
            # BDF 的 BBX 记的是**墨迹包围盒**, 不是字格 —— 拿格宽去比会全量误报。
            # 正确对照: 墨迹 x 跨度/行跨度/左上角偏移 三者都要对上。
            xs = [x for y in range(rh) for x in range(rw) if R[y][x]]
            ys = [y for y in range(rh) for x in range(rw) if R[y][x]]
            if xs and ys:
                exp_w = max(xs) - min(xs) + 1
                exp_h = max(ys) - min(ys) + 1
                exp_xoff = min(xs)
                exp_yoff = min(ys) - ascent
                if (bw, bh, bxoff) != (exp_w, exp_h, exp_xoff):
                    bag.add(
                        Anomaly(
                            "BBX_MISMATCH",
                            ERROR,
                            f"{ch!r} BDF BBX=({bw},{bh},{bxoff}) != 墨迹包围盒"
                            f"({exp_w},{exp_h},{exp_xoff})",
                            cp=cp, char=ch, category=cat, batch=batch_no,
                            evidence={"bdf": [bw, bh, bxoff], "expected": [exp_w, exp_h, exp_xoff]},
                        )
                    )

        # T 路
        tinfo = ttf.get(cp)
        if tinfo is None or tinfo["rows"] is None:
            bag.add(
                Anomaly("CMAP_MISSING", ERROR, f"{ch!r} 不在 TTF cmap 中", cp=cp, char=ch, category=cat, batch=batch_no)
            )
        else:
            T = tinfo["rows"]
            diff = sum(1 for y in range(rh) for x in range(rw) if T[y][x] != R[y][x])
            if diff:
                bag.add(
                    Anomaly(
                        "MISMATCH_TTF",
                        ERROR,
                        f"{ch!r} 栅格化器与 TTF 轮廓反解差 {diff} px",
                        cp=cp, char=ch, category=cat, batch=batch_no,
                        evidence={"diff_px": diff},
                    )
                )
            xs = [x for y in range(rh) for x in range(rw) if R[y][x]]
            ink_xmin = min(xs) if xs else 0
            px_unit = 768 // cell_w
            if tinfo["lsb"] is not None and rule_lsb(tinfo["lsb"], ink_xmin, px_unit):
                bag.add(
                    Anomaly(
                        "TTF_LSB_MISMATCH",
                        ERROR,
                        f"{ch!r} hmtx lsb={tinfo['lsb']} != 墨迹左边缘 {ink_xmin * px_unit}",
                        cp=cp, char=ch, category=cat, batch=batch_no,
                        evidence={"lsb": tinfo["lsb"], "expected": ink_xmin * px_unit},
                    )
                )
            if tinfo["advance"] is not None and tinfo["advance"] != rw * px_unit:
                bag.add(
                    Anomaly(
                        "ADVANCE_MISMATCH",
                        ERROR,
                        f"{ch!r} TTF advance={tinfo['advance']} != 期望 {rw * px_unit}",
                        cp=cp, char=ch, category=cat, batch=batch_no,
                    )
                )

        # A 路
        if cp not in atlas_rows:
            bag.add(
                Anomaly("ATLAS_MISSING", ERROR, f"{ch!r} 不在图集元数据中", cp=cp, char=ch, category=cat, batch=batch_no)
            )
        else:
            A = atlas_rows[cp]
            diff = sum(1 for y in range(rh) for x in range(rw) if A[y][x] != R[y][x])
            if diff:
                bag.add(
                    Anomaly(
                        "MISMATCH_ATLAS",
                        ERROR,
                        f"{ch!r} 栅格化器与图集成品差 {diff} px",
                        cp=cp, char=ch, category=cat, batch=batch_no,
                        evidence={"diff_px": diff},
                    )
                )
            entry = atlas_entries.get(cp)
            if entry:
                _, _, _, adv, wide = entry
                if adv != rw:
                    bag.add(
                        Anomaly(
                            "ADVANCE_MISMATCH",
                            ERROR,
                            f"{ch!r} 图集 advance={adv} != 栅格化器 {rw}",
                            cp=cp, char=ch, category=cat, batch=batch_no,
                        )
                    )
                if rule_atlas_wide(adv, wide, cell_w, half_w):
                    bag.add(
                        Anomaly(
                            "ATLAS_WIDE_MISMATCH",
                            ERROR,
                            f"{ch!r} 图集 isWide={wide} 但 advance={adv} (全角={cell_w}/半角={half_w})",
                            cp=cp, char=ch, category=cat, batch=batch_no,
                            evidence={"advance": adv, "isWide": wide},
                        )
                    )

        dup_map[hashlib.sha1(bytes(g.tobytes())).hexdigest()].append((ch, cat))

    # ---- 重复位图 (信息级: 不同码位共享同一位图在字体里是合法的)
    for h, members in dup_map.items():
        if len(members) > 1:
            bag.add(
                Anomaly(
                    "DUPLICATE_BITMAP",
                    INFO,
                    "位图完全相同的字符: " + ", ".join(f"{c!r}(U+{ord(c):04X},{k})" for c, k in members),
                    evidence={"sha1": h[:12], "members": [f"U+{ord(c):04X}" for c, _ in members]},
                )
            )

    # ---- 批统计 + 与参考分布对比
    batch_stats = []
    for bi, batch in enumerate(batches):
        dens: list[float] = []
        tops: list[int] = []
        bots: list[int] = []
        empties = 0
        wide = 0
        for ch, cat in batch:
            g = stack.glyph(ch)
            p = g.load()
            on = sum(1 for y in range(g.height) for x in range(g.width) if p[x, y] > 0)
            dens.append(on / max(1, g.width * g.height))
            if on == 0 and ch not in WHITESPACE:
                empties += 1
            ys = [y for y in range(g.height) for x in range(g.width) if p[x, y] > 0]
            if ys:
                tops.append(min(ys))
                bots.append(max(ys))
            if g.width == cell_w:
                wide += 1
        if not dens:
            continue
        dens.sort()
        bmed = dens[len(dens) // 2]
        bmad = sorted(abs(d - bmed) for d in dens)[len(dens) // 2]
        btop = sorted(tops)[len(tops) // 2] if tops else 0
        bbot = sorted(bots)[len(bots) // 2] if bots else 0
        wide_ratio = wide / len(dens)
        stat = {
            "batch": bi,
            "chars": len(dens),
            "density_median": round(bmed, 4),
            "density_max": round(dens[-1], 4),
            "ink_top_median": btop,
            "ink_bottom_median": bbot,
            "wide_ratio": round(wide_ratio, 4),
            "empty_ink": empties,
        }
        batch_stats.append(stat)

        # 批内墨量离群
        for ch, cat in batch:
            g = stack.glyph(ch)
            p = g.load()
            on = sum(1 for y in range(g.height) for x in range(g.width) if p[x, y] > 0)
            d = on / max(1, g.width * g.height)
            if rule_density(d, ref["density_median"], ref["density_mad"], ref["density_sigma"]):
                bag.add(
                    Anomaly(
                        "DENSITY_OUTLIER",
                        WARN,
                        f"{ch!r} 墨量 {d:.0%} 远离参考中位 {ref['density_median']:.0%}",
                        cp=ord(ch), char=ch, category=cat, batch=bi,
                        evidence={"density": round(d, 4)},
                    )
                )

        # 基线漂移
        if abs(btop - ref["ink_top_median"]) >= 3 or abs(bbot - ref["ink_bottom_median"]) >= 3:
            bag.add(
                Anomaly(
                    "BASELINE_DRIFT",
                    WARN,
                    f"第 {bi} 批墨迹垂直范围 top={btop}/bottom={bbot}, "
                    f"参考中位 {ref['ink_top_median']}/{ref['ink_bottom_median']}",
                    batch=bi,
                    evidence=stat,
                )
            )

    return bag, {"batch_stats": batch_stats}


# ================================================================ 构建


def run_build(root: Path) -> tuple[int, str]:
    """跑生产构建脚本, 拿真实退出码和输出。

    刻意用子进程而不是 import 复用: 回归测试要验的是**生产命令本身**
    (包括它自己的 verify_* 门禁), 不是另写一遍等价逻辑。
    """
    cmd = [sys.executable, str(root / "tools" / "fontgen" / "build_font.py")]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(root)
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or ""))


# ================================================================ 量具自检


def selftest(root: Path) -> int:
    """注入已知坏数据, 断言检测器确实会响。

    量具自己必须被验过: "没报异常"只有在这台量具确实能发现问题的前提下
    才有意义。合成坏数据 = 已知答案, 可以断言。
    """
    print("== 量具自检 (注入已知坏数据, 断言检测器会响) ==")
    failures: list[str] = []

    # 纯规则级
    checks: list[tuple[str, bool, str]] = []
    checks.append(("CLIP_RIGHT 规则", "CLIP_RIGHT" in rule_clip(12, 0, 13, 0, 6, 13), "12px 墨迹进 6px 格"))
    checks.append(("CLIP_RIGHT 无裁剪", "CLIP_RIGHT" not in rule_clip(6, 0, 13, 0, 6, 13), "6px 墨迹进 6px 格"))
    checks.append(("CLIP_BOTTOM 规则", "CLIP_BOTTOM" in rule_clip(6, 0, 14, 0, 6, 13), "14px 高墨迹进 13 行格"))
    checks.append(("CLIP_BOTTOM 规则(刚好装下)", "CLIP_BOTTOM" not in rule_clip(6, 0, 13, 0, 6, 13), "13px 高墨迹进 13 行格"))
    checks.append(("advance 规则", rule_advance(12, 6) == "SOURCE_ADVANCE_MISMATCH", "源 12px / 格 6px"))
    checks.append(("advance 规则(一致)", rule_advance(12, 12) is None, "源 12px / 格 12px"))
    checks.append(("空墨迹规则", rule_empty_ink(0, "A"), "非空白无墨迹"))
    checks.append(("空墨迹规则(空格)", not rule_empty_ink(0, " "), "空格无墨迹不算异常"))
    checks.append(("isWide 规则", rule_atlas_wide(6, 1, 12, 6), "advance=6 却标全角"))
    checks.append(("isWide 规则(一致)", not rule_atlas_wide(12, 1, 12, 6), "advance=12 标全角"))
    checks.append(("lsb 规则", rule_lsb(0, 3, 64), "lsb=0 但墨迹从 x=3 开始"))
    checks.append(("lsb 规则(一致)", not rule_lsb(192, 3, 64), "lsb=3*64"))
    checks.append(("BDF 行数规则", rule_bdf_rows(13, 12), "BBX 13 行 / BITMAP 12 行"))
    checks.append(("BDF 填充位规则", rule_bdf_padding(4, "FF"), "4px 用 1 字节, 填充位非 0"))
    checks.append(("BDF 填充位规则(合法)", not rule_bdf_padding(8, "FF"), "8px 整字节"))
    checks.append(("BDF 填充位规则(合法 4px)", not rule_bdf_padding(4, "F0"), "4px: MSB 在前, 高 4 位是像素"))
    checks.append(("BDF 填充位规则(非法 4px)", rule_bdf_padding(4, "0F"), "4px: 低 4 位是填充位, 必须为 0"))

    for label, ok, why in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}  ({why})")
        if not ok:
            failures.append(label)

    # 产物级: 复制一份 dist, 逐个破坏, 断言对应检测器报出来
    dist = root / "dist"
    if not dist.exists():
        print("  [SKIP] 产物级自检: dist/ 不存在 (先跑一次构建)")
    else:
        import shutil
        import tempfile

        items = cs.build_charset()
        stack = cs.build_stack()
        sel = items[:24]
        ref = collect_reference(items, stack)
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "dist"
            shutil.copytree(dist, tmp)
            art = Artifacts(tmp)

            def sel_check(art2: Artifacts) -> AnomalyBag:
                bag2, _ = run_checks(art2, stack, items, sel, [sel], ref)
                return bag2

            # 1) 图集 PNG 翻一个像素 -> MISMATCH_ATLAS
            #    注入点必须落在**被测字符**上, 否则检测器压根不会去看那个格子。
            shutil.rmtree(tmp)
            shutil.copytree(dist, tmp)
            img = Image.open(art.atlas_png).convert("RGBA")
            px = img.load()
            data = json.loads(art.atlas_json.read_text(encoding="utf-8"))
            sel_cps = {ord(ch) for ch, _ in sel}
            victim = next(m for m in data["glyphs"] if m[0] in sel_cps)
            cp0, gx, gy, _, _ = victim
            old = px[gx, gy]
            px[gx, gy] = (255, 255, 255, 255) if old[3] == 0 else (0, 0, 0, 0)
            img.save(art.atlas_png)
            landed = Image.open(art.atlas_png).convert("RGBA").getpixel((gx, gy)) != old
            bag2 = sel_check(art)
            ok = landed and "MISMATCH_ATLAS" in bag2.ids()
            print(f"  [{'PASS' if ok else 'FAIL'}] 图集翻像素 -> MISMATCH_ATLAS")
            if not ok:
                failures.append("图集翻像素")

            # 2) 图集 isWide 标错 -> ATLAS_WIDE_MISMATCH
            #    注意: 这一条曾经是假阳性 —— 旧产物里所有 advance=6 的字符本来就被
            #    错标成全角, 于是"标错"是空操作, 检测器报的却是**早已存在**的错。
            #    现在产物本身是对的, 注入才真正制造出新的不一致。
            shutil.rmtree(tmp)
            shutil.copytree(dist, tmp)
            data = json.loads(art.atlas_json.read_text(encoding="utf-8"))
            victim = next((m for m in data["glyphs"] if m[3] == 6 and m[0] in sel_cps), None)
            if victim:
                victim[4] = 1
            art.atlas_json.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            landed = bool(
                victim
                and next(
                    (m[4] for m in json.loads(art.atlas_json.read_text(encoding="utf-8"))["glyphs"] if m[0] == victim[0]),
                    None,
                )
                == 1
            )
            bag2 = sel_check(art)
            ok = landed and "ATLAS_WIDE_MISMATCH" in bag2.ids()
            print(f"  [{'PASS' if ok else 'FAIL'}] 图集 isWide 标错 -> ATLAS_WIDE_MISMATCH")
            if not ok:
                failures.append("图集 isWide 标错")

            # 3) BDF 改一个十六进制位 -> MISMATCH_BDF
            #    必须原地翻位: 换整行会改掉行宽, 那测到的是结构规则而不是像素对比。
            shutil.rmtree(tmp)
            shutil.copytree(dist, tmp)
            lines = art.bdf.read_text(encoding="utf-8").splitlines()
            hit = False
            for i, ln in enumerate(lines):
                if ln.strip() != "BITMAP":
                    continue
                row = lines[i + 1].strip()
                if len(row) < 2 or not all(c in "0123456789ABCDEF" for c in row):
                    continue
                lines[i + 1] = ("0" if row[0] != "0" else "F") + row[1:]
                hit = True
                break
            art.bdf.write_text("\n".join(lines) + "\n", encoding="utf-8")
            bag2 = sel_check(art) if hit else AnomalyBag()
            ok = hit and "MISMATCH_BDF" in bag2.ids()
            print(f"  [{'PASS' if ok else 'FAIL'}] BDF 改位 -> MISMATCH_BDF")
            if not ok:
                failures.append("BDF 改位")

            # 4) BDF 多塞一个 ENDCHAR -> BDF_STRUCTURE
            shutil.rmtree(tmp)
            shutil.copytree(dist, tmp)
            lines = art.bdf.read_text(encoding="utf-8").splitlines()
            for i, ln in enumerate(lines):
                if ln.strip() == "ENDCHAR":
                    lines.insert(i, "ENDCHAR")
                    break
            art.bdf.write_text("\n".join(lines) + "\n", encoding="utf-8")
            bag2 = sel_check(art)
            ok = "BDF_STRUCTURE" in bag2.ids()
            print(f"  [{'PASS' if ok else 'FAIL'}] BDF 多 ENDCHAR -> BDF_STRUCTURE")
            if not ok:
                failures.append("BDF 多 ENDCHAR")

            # 5) TTF 删一个 cmap 条目 -> CMAP_MISSING
            shutil.rmtree(tmp)
            shutil.copytree(dist, tmp)
            from fontTools.ttLib import TTFont

            tt = TTFont(str(art.ttf))
            victim = sel[0][0]
            for t in tt["cmap"].tables:
                t.cmap.pop(ord(victim), None)
            tt.save(str(art.ttf))
            landed = ord(victim) not in TTFont(str(art.ttf)).getBestCmap()
            bag2 = sel_check(art)
            ok = landed and "CMAP_MISSING" in bag2.ids()
            print(f"  [{'PASS' if ok else 'FAIL'}] TTF 删 cmap -> CMAP_MISSING")
            if not ok:
                failures.append("TTF 删 cmap")

            # 6) TTF 改 lsb -> TTF_LSB_MISMATCH
            #    目标字符必须挑 lsb **非 0** 的: lsb 本来就是 0 的字符 (" 之类),
            #    把它设成 0 等于没改 —— 注入不落地, 用例就成了空转的假阳性。
            #    这一条曾经真的假阳性过: 早期版本 hmtx 的 (advance, lsb) 取反了,
            #    检测器拿 advance 去比 lsb, 报的是"每个字符都错", 正好把空操作盖住了。
            shutil.rmtree(tmp)
            shutil.copytree(dist, tmp)
            tt = TTFont(str(art.ttf))
            hm = tt["hmtx"]
            ttcmap = tt.getBestCmap()
            target = None
            for ch, _ in sel:
                nm = ttcmap.get(ord(ch))
                if nm and hm.metrics.get(nm, (0, 0))[1] != 0:
                    target = (ch, nm)
                    break
            if target:
                ch, name = target
                orig_lsb = hm.metrics[name][1]
                hm.metrics[name] = (hm.metrics[name][0], 0)
            tt.save(str(art.ttf))
            # 注入必须真的落进文件 —— 否则这个用例什么都没测
            landed = False
            if target:
                ch, name = target
                tt_chk = TTFont(str(art.ttf))
                new_lsb = tt_chk["hmtx"].metrics.get(tt_chk.getBestCmap().get(ord(ch)), (0, 0))[1]
                landed = new_lsb == 0 and orig_lsb != 0
            bag2 = sel_check(art)
            ok = landed and "TTF_LSB_MISMATCH" in bag2.ids()
            print(f"  [{'PASS' if ok else 'FAIL'}] TTF 改 lsb -> TTF_LSB_MISMATCH")
            if not ok:
                failures.append("TTF 改 lsb")

    print()
    if failures:
        print(f"量具自检失败 {len(failures)} 项: {failures}")
        return 1
    print("量具自检全部通过 —— 检测器确实能发现注入的问题。")
    return 0


# ================================================================ 报告


def render_markdown(report: dict) -> str:
    s = report["summary"]
    L = [
        f"# 回归测试报告 — {report['selection']['label']}",
        "",
        f"- 生成时间: {report['generated_at']}",
        f"- 判定: **{s['verdict']}** (error {s['errors']} / warn {s['warnings']} / info {s['infos']})",
        f"- 覆盖: {report['inputs']['chars_checked']} 字 / {report['inputs']['batches']} 批 "
        f"(字符集 {report['inputs']['chars_selected']} 字选自全集 {report['inputs']['charset_total']} 字)",
        "",
    ]
    if s["verdict"] == "NO_DATA":
        L.append("> **没有测到任何东西** —— 这个结果不构成任何结论。")
        L.append("")
        L.append(f"原因: {report['inputs'].get('reason', '未说明')}")
        return "\n".join(L) + "\n"

    by_id: dict[str, list[dict]] = defaultdict(list)
    for a in report["anomalies"]:
        by_id[a["id"]].append(a)
    if not by_id:
        L.append("## 无异常")
        return "\n".join(L) + "\n"

    L.append("## 异常汇总")
    L.append("")
    L.append("| 异常 ID | 级别 | 次数 | 说明 |")
    L.append("|---|---|---|---|")
    desc = {
        "CLIP_RIGHT": "源字形宽度超出 cell, 墨迹被裁",
        "CLIP_BOTTOM": "源字形高度超出 cell, 墨迹被裁",
        "SOURCE_ADVANCE_MISMATCH": "源字体实测 advance 与分配格宽不符",
        "EMPTY_INK": "非空白字符没有墨迹",
        "MISMATCH_BDF": "栅格化器与 BDF 成品不一致",
        "MISMATCH_TTF": "栅格化器与 TTF 成品不一致",
        "MISMATCH_ATLAS": "栅格化器与图集成品不一致",
        "ATLAS_WIDE_MISMATCH": "图集 isWide 标记与 advance 不符",
        "ADVANCE_MISMATCH": "advance 各路不一致",
        "WIDTH_MISMATCH": "字形宽度各路不一致",
        "TTF_LSB_MISMATCH": "hmtx lsb 与墨迹左边缘不符",
        "BDF_STRUCTURE": "BDF 结构损坏",
        "CMAP_MISSING": "TTF cmap 缺字",
        "BDF_MISSING": "BDF 缺字",
        "ATLAS_MISSING": "图集缺字",
        "ARTIFACT_MISSING": "成品文件缺失",
        "DENSITY_OUTLIER": "墨量离群",
        "BASELINE_DRIFT": "批基线漂移",
        "DUPLICATE_BITMAP": "位图重复 (信息)",
    }
    def sev_key(aid: str) -> tuple:
        return (0 if by_id[aid][0]["severity"] == ERROR else 1, aid)

    for aid in sorted(by_id, key=sev_key):
        items = by_id[aid]
        sev = items[0]["severity"]
        L.append(f"| `{aid}` | {sev} | {len(items)} | {desc.get(aid, '')} |")
    L.append("")

    for aid in sorted(by_id, key=sev_key):
        items = by_id[aid]
        L.append(f"## {aid} ({len(items)})")
        L.append("")
        for a in items[:40]:
            where = ""
            if a.get("cp"):
                where = f"`{a['cp']}` {a.get('char', '')!r} ({a.get('category', '')})"
                if a.get("batch", -1) >= 0:
                    where += f" · 批 {a['batch']}"
            L.append(f"- {where} — {a['detail']}")
        if len(items) > 40:
            L.append(f"- …还有 {len(items) - 40} 条, 见 JSON")
        L.append("")

    bs = report.get("batch_stats", [])
    if bs:
        L.append("## 批统计")
        L.append("")
        L.append("| 批 | 字数 | 墨量中位 | 墨量最高 | 墨迹top | 墨迹bottom | 全角比 | 空墨迹 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for b in bs:
            L.append(
                f"| {b['batch']} | {b['chars']} | {b['density_median']:.0%} | {b['density_max']:.0%} | "
                f"{b['ink_top_median']} | {b['ink_bottom_median']} | {b['wide_ratio']:.0%} | {b['empty_ink']} |"
            )
        L.append("")
    return "\n".join(L) + "\n"


# ================================================================ main


def main() -> int:
    ap = argparse.ArgumentParser(description="PixelFont 回归测试 (分批抽样 + 四路交叉对比)")
    ap.add_argument("--cats", default="", help="要测的类别, 逗号分隔: ascii,punct,kana,hanzi (默认全部)")
    ap.add_argument("--slice", dest="slice_", default="", help="对选出的字符再切一段, 形如 0:1900")
    ap.add_argument("--batch-size", type=int, default=100, help="每批字数")
    ap.add_argument("--out", default="", help="JSON 报告输出路径")
    ap.add_argument("--label", default="", help="报告标签 (默认按选择自动生成)")
    ap.add_argument("--skip-build", action="store_true", help="不重新构建, 直接用现有 dist/")
    ap.add_argument("--selftest", action="store_true", help="只跑量具自检")
    args = ap.parse_args()

    if args.selftest:
        return selftest(ROOT)

    out = Path(args.out) if args.out else None
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)

    items = cs.build_charset()
    stack = cs.build_stack()

    # ---- 选择字符
    cats = [c.strip() for c in args.cats.split(",") if c.strip()]
    if cats:
        sel = [(ch, cat) for ch, cat in items if cat in cats]
    else:
        sel = list(items)
    total_selected = len(sel)
    if args.slice_:
        a, _, b = args.slice_.partition(":")
        s0 = int(a) if a else 0
        s1 = int(b) if b else len(sel)
        sel = sel[s0:s1]
    if not sel:
        print("选择为空 —— 没有任何字符可测, 退出 (绝不用 PASS 冒充)", file=sys.stderr)
        return 2

    # ---- 构建
    build_rc = 0
    build_log = ""
    if not args.skip_build:
        build_rc, build_log = run_build(ROOT)
        print(build_log.strip())
        if build_rc != 0:
            report = {
                "tool": "regress",
                "version": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "selection": {"cats": cats or ["<all>"], "slice": args.slice_, "label": args.label or "build-failed"},
                "inputs": {
                    "charset_total": len(items),
                    "chars_selected": total_selected,
                    "chars_checked": 0,
                    "batches": 0,
                    "reason": f"构建失败 (退出码 {build_rc})",
                },
                "anomalies": [
                    {
                        "id": "BUILD_FAILED",
                        "severity": ERROR,
                        "detail": f"build_font.py 退出码 {build_rc}",
                        "evidence": {"log_tail": build_log[-2000:]},
                    }
                ],
                "batch_stats": [],
                "summary": {"errors": 1, "warnings": 0, "infos": 0, "verdict": "BUILD_FAILED"},
            }
            if out:
                out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                out.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
            print("构建失败 —— 结果不构成任何结论", file=sys.stderr)
            return 2

    # ---- 分批
    bs = max(1, args.batch_size)
    batches = [sel[i : i + bs] for i in range(0, len(sel), bs)]

    # ---- 参考分布 (全字符集)
    ref = collect_reference(items, stack)

    # ---- 检查
    art = Artifacts(ROOT / "dist")
    bag, extra = run_checks(art, stack, items, sel, batches, ref)

    errors = bag.count(ERROR)
    warns = bag.count(WARN)
    infos = bag.count(INFO)
    checked = len(sel)
    # 关键: 没测到东西就不给结论。summary 必须同时说明"消费了多少输入"。
    verdict = "FAIL" if errors else "PASS"
    if checked == 0 or not batches:
        verdict = "NO_DATA"

    label = args.label or (f"{'+'.join(cats) or 'all'}{'_' + args.slice_.replace(':', '-') if args.slice_ else ''}")
    report = {
        "tool": "regress",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection": {
            "cats": cats or ["<all>"],
            "slice": args.slice_,
            "batch_size": bs,
            "label": label,
        },
        "inputs": {
            "charset_total": len(items),
            "chars_selected": total_selected,
            "chars_checked": checked,
            "batches": len(batches),
            "artifacts": {
                "bdf": art.bdf.stat().st_size if art.bdf.exists() else 0,
                "ttf": art.ttf.stat().st_size if art.ttf.exists() else 0,
                "atlas_png": art.atlas_png.stat().st_size if art.atlas_png.exists() else 0,
                "atlas_json": art.atlas_json.stat().st_size if art.atlas_json.exists() else 0,
            },
            "build_exit_code": build_rc,
        },
        "reference": ref,
        "anomalies": [a.to_dict() for a in bag.items],
        "batch_stats": extra.get("batch_stats", []),
        "summary": {
            "errors": errors,
            "warnings": warns,
            "infos": infos,
            "verdict": verdict,
        },
    }

    if out:
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        out.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")

    print()
    print(
        f"[{label}] 覆盖 {checked} 字 / {len(batches)} 批  "
        f"error={errors} warn={warns} info={infos}  判定={verdict}"
    )
    by_id = Counter(a["id"] for a in report["anomalies"])
    for aid, n in by_id.most_common():
        print(f"   {aid}: {n}")
    if out:
        print(f"   报告: {out}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
