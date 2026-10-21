"""字形身份校验 —— 用独立来源的开源像素字体做基准, 确认每个码位画的确实是这个字。

为什么现有回归不够:
    1. build_font 的 verify_* 是**自证**: 成品 == 源位图。源位图错了, 成品跟着错,
       校验照样通过。
    2. lane C 的"源形保真"检查是**同源**的: 拿 SimHei 的灰度渲染当基准, 而 SimHei
       正是本字体栅格化的输入 —— 它给什么形状, 我们就画什么形状。
    两者的共同前提都是"SimHei / MS Gothic 画出来的就是对的字"。
    一旦源字体某个码位本身画错、或两个码位画成了同一个字, 上面两套检查永远发现不了。

所以这里引入**独立第三方**画的开源像素字体当基准:
    · 参考字体的字形是别人独立画的, 不经过 SimHei 这条链路
    · 硬证据: 我们的字形若与参考字体的**另一个**码位字形**逐像素完全相同**,
      说明我们画的是那个字 (不受画风差异影响)
    · 软证据(置换检验): 对每个码位, 在参考字体的同类别码位里找最像的那个 ——
      它应该是自己。若最像的却是别的码位, 且分差远超"随机两个字碰巧相似"的水平,
      就高度可疑

三类检查:
    A. COVERAGE      参考字体有的码位我们没有 / 反之 (不是错字, 是覆盖差异)
    B. EXACT_COLLIDE 我们的字形 == 参考字体另一个码位的字形 (逐像素) —— 硬信号
    C. IDENTITY      置换检验: 最佳匹配指向别的码位且分差超随机基线 —— 软信号

相似度用两个量, 互补:
    · 密度余弦 (3x3 + 5x5 网格的墨量分布 + 尺寸/墨量比) —— 对分辨率与画风差异鲁棒
    · 包围盒归一化后的 IoU —— 精确形状, 只对候选集算 (全量太慢)

判定不许撒谎:
    阈值来自**随机错配对**的经验分布 (chance baseline), 不拍脑袋。
    参考字体缺字 / 读取失败 都会被计数并写进报告 —— 没测到就说没测到。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageFont

sys.path.insert(0, str(Path(__file__).parent))

import charset as cs  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REFDIR = ROOT / "third_party" / "ref_fonts"

# 参考字体登记表: 名字 -> (相对路径, 原生 ppem, 许可证, 来源)
# 全部是开源免费字体, 二进制不入库 (third_party/ 在 .gitignore 里),
# 来源/版本/校验和见 docs/reference-fonts.md
#
# 选四套的理由 —— 设计谱系互相独立, 才叫"独立基准":
#   · Ark Pixel  : 日系点阵, 12px, 笔画方正规整 (OFL-1.1)
#   · Fusion Pixel: 缝合字体, 把 Ark/Cubic11/Galmuri 等多套点阵缝在一起, 12px (OFL-1.1)
#   · Zpix 最像素 : 国产点阵, 12px, 笔画带手绘味 (MIT)
#   · GNU Unifont : 16x16, 学术项目, BMP 全覆盖, 与 CJK 点阵毫无血缘 (GPL-2.0+ 字体例外)
REFS: dict[str, dict] = {
    "ark-pixel-zh_hans": {
        "path": "ark-pixel-12px/ark-pixel-12px-monospaced-zh_hans.ttf",
        "ppem": 12,
        "license": "OFL-1.1",
        "source": "https://github.com/TakWolf/ark-pixel-font (2026.10.16)",
    },
    "ark-pixel-ja": {
        "path": "ark-pixel-12px/ark-pixel-12px-monospaced-ja.ttf",
        "ppem": 12,
        "license": "OFL-1.1",
        "source": "https://github.com/TakWolf/ark-pixel-font (2026.10.16)",
    },
    "fusion-pixel-zh_hans": {
        "path": "fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans.ttf",
        "ppem": 12,
        "license": "OFL-1.1",
        "source": "https://github.com/TakWolf/fusion-pixel-font (2026.10.16)",
    },
    "fusion-pixel-ja": {
        "path": "fusion-pixel-12px/fusion-pixel-12px-monospaced-ja.ttf",
        "ppem": 12,
        "license": "OFL-1.1",
        "source": "https://github.com/TakWolf/fusion-pixel-font (2026.10.16)",
    },
    "zpix": {
        "path": "zpix.bin",
        "ppem": 12,
        "license": "MIT",
        "source": "https://github.com/SolidZORO/zpix-pixel-font (v3.3.0)",
    },
    "unifont-16": {
        "path": "unifont-16.bin",
        "ppem": 16,
        "license": "GPL-2.0+ (含字体嵌入例外)",
        "source": "https://unifoundry.com/unifont/ (16.0.01)",
    },
}

# 类别 -> 参考字体里参与比对的类别 (同类别比, 避免跨类别乱指)
SAME_CAT = {
    "ascii": {"ascii"},
    "punct": {"punct", "ascii"},
    "kana": {"kana"},
    "hanzi": {"hanzi"},
}


# ================================================================ 提取


def ref_glyphs(path: Path, ppem: int, cps: list[int]) -> tuple[dict[int, np.ndarray], int]:
    """把参考字体在**原生 ppem** 下渲染成 1-bit 位图 (墨迹外接矩形)。

    必须用原生 ppem: 像素字体的轮廓是按自己的网格设计的, 在别的字号下
    栅格化会重排笔画, 那时的形状已经不是它"本来该有的样子"了。
    """
    f = ImageFont.truetype(str(path), ppem, layout_engine=ImageFont.Layout.BASIC)
    out: dict[int, np.ndarray] = {}
    fails = 0
    for cp in cps:
        try:
            core, _off = f.getmask2(chr(cp), mode="1")
        except Exception:  # noqa: BLE001
            fails += 1
            continue
        w, h = core.size
        if w == 0 or h == 0:
            continue
        data = bytes(core)
        if len(data) < w * h:
            fails += 1
            continue
        img = Image.frombuffer("L", (w, h), data[: w * h])
        arr = (np.array(img, dtype=np.uint8) > 0).astype(np.float32)
        out[cp] = arr
    return out, fails


def our_glyphs(stack, items: list[tuple[str, str]]) -> dict[int, np.ndarray]:
    """本字体的字形 (栅格化器输出, 12x13 格 -> 墨迹外接矩形)。

    用栅格化器而不是从 TTF 反解: TTF 在 12px 会被渲染器抗锯齿/网格拟合,
    那是渲染器行为, 不是字形内容。栅格化器输出才是设计真相。
    """
    out: dict[int, np.ndarray] = {}
    for ch, _cat in items:
        g = stack.glyph(ch)
        a = (np.array(g, dtype=np.uint8) > 0).astype(np.float32)
        ys, xs = np.nonzero(a)
        if len(xs) == 0:
            # 空格这类**本来就没有墨迹**的字符不在这里 (返回 None = "没有字形"),
            # 由出图工具单独补一个空格子 —— 否则对照图上会把空格显示成红色的"缺",
            # 复核者会以为字体少了这个码位。
            # (硬检查的覆盖率统计也依赖这个语义: 空格子不能算"参考缺字"。)
            continue
        out[ord(ch)] = a[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    return out


# ================================================================ 特征与相似度


def density_features(a: np.ndarray) -> np.ndarray:
    """密度分布特征: 3x3 + 5x5 网格墨量占比 + 墨量比/宽高比。

    为什么要网格密度而不是直接比像素: 不同像素字体的笔画粗细与结构风格不同
    (黑体 vs 点阵宋体), 逐像素 IoU 会被风格差异压得很低, 而"字错了"
    (密度分布整个换掉) 在这个特征上依然显著。
    """
    h, w = a.shape
    feats: list[float] = []
    for gy, gx in ((3, 3), (5, 5)):
        ys = np.linspace(0, h, gy + 1).astype(int)
        xs = np.linspace(0, w, gx + 1).astype(int)
        for i in range(gy):
            for j in range(gx):
                y0, y1 = ys[i], max(ys[i] + 1, ys[i + 1])
                x0, x1 = xs[j], max(xs[j] + 1, xs[j + 1])
                cell = a[y0:y1, x0:x1]
                feats.append(float(cell.mean()) if cell.size else 0.0)
    feats.append(float(a.mean()))
    feats.append(w / 24.0)
    feats.append(h / 24.0)
    feats.append(w / max(1, h))
    return np.array(feats, dtype=np.float32)


def iou_scaled(a: np.ndarray, b: np.ndarray, n: int = 16) -> float:
    """包围盒归一化到 n x n 后的 IoU (最近邻缩放)。

    只用于候选集精排 —— 全量算太慢。
    """
    def rs(x: np.ndarray) -> np.ndarray:
        im = Image.fromarray((x * 255).astype(np.uint8), mode="L")
        return (np.array(im.resize((n, n), Image.NEAREST), dtype=np.float32) > 127).astype(np.float32)

    ra, rb = rs(a), rs(b)
    inter = float((ra * rb).sum())
    union = float(((ra + rb) > 0).sum())
    return inter / union if union else 0.0


def build_matrix(ours: dict[int, np.ndarray], refs: dict[int, np.ndarray]) -> tuple[np.ndarray, np.ndarray, list[int]]:
    o_cps = list(ours)
    r_cps = list(refs)
    if not o_cps or not r_cps:
        return np.zeros((len(o_cps), len(r_cps)), dtype=np.float32), np.zeros((len(o_cps), len(r_cps)), dtype=np.float32), r_cps
    A = np.stack([density_features(ours[c]) for c in o_cps])
    B = np.stack([density_features(refs[c]) for c in r_cps])
    A = A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-9)
    B = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-9)
    return A @ B.T, A, r_cps


def sim_block(
    ours: dict[int, np.ndarray],
    refs: dict[int, np.ndarray],
    o_list: list[int],
    r_list: list[int],
) -> np.ndarray:
    """只算 (o_list x r_list) 的相似度矩阵。

    分块是必须的: 汉字类别的参考候选池能有两万多个码位, 全量矩阵
    3755x21000 float32 就是 300MB 上下, 没必要一次吃掉。
    """
    if not o_list or not r_list:
        return np.zeros((len(o_list), len(r_list)), dtype=np.float32)
    A = np.stack([density_features(ours[c]) for c in o_list])
    B = np.stack([density_features(refs[c]) for c in r_list])
    A = A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-9)
    B = B / (np.linalg.norm(B, axis=1, keepdims=True) + 1e-9)
    return A @ B.T


# ================================================================ 校验


def category_of(cp: int) -> str:
    ch = chr(cp)
    if cp < 0x80:
        return "ascii"
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return "hanzi" if cp >= 0x2E80 and not _is_kana(cp) else "kana"
    return "punct"


def _is_kana(cp: int) -> bool:
    return (0x3000 <= cp <= 0x30FF) or (0x31F0 <= cp <= 0x31FF) or (0xFF61 <= cp <= 0xFF9F)


def ascii_art(a: np.ndarray, ink: str = "#", paper: str = ".") -> str:
    return "\n".join("".join(ink if v else paper for v in row) for row in a)


def side_by_side(a: np.ndarray, b: np.ndarray, gap: int = 3) -> str:
    ha, hb = a.shape[0], b.shape[0]
    h = max(ha, hb)
    wa, wb = a.shape[1], b.shape[1]
    canvas = np.zeros((h, wa + gap + wb), dtype=np.float32)
    canvas[:ha, :wa] = a
    canvas[:hb, wa + gap :] = b
    return ascii_art(canvas)


def run(args) -> int:
    out_path = Path(args.out) if args.out else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)

    items = cs.build_charset()
    stack = cs.build_stack()

    cats = [c.strip() for c in args.cats.split(",") if c.strip()]
    sel = [(ch, cat) for ch, cat in items if (not cats or cat in cats)]
    if args.slice_:
        a, _, b = args.slice_.partition(":")
        sel = sel[int(a) if a else 0 : int(b) if b else len(sel)]
    if not sel:
        print("选择为空 —— 没有可测字符, 退出 (绝不用 PASS 冒充)", file=sys.stderr)
        return 2

    ref_name = args.ref
    if ref_name not in REFS:
        print(f"未知参考字体 {ref_name}; 可选: {', '.join(REFS)}", file=sys.stderr)
        return 2
    meta = REFS[ref_name]
    ref_path = REFDIR / meta["path"]
    if not ref_path.exists():
        print(
            f"参考字体缺失: {ref_path}\n"
            f"请先下载 (见 docs/reference-fonts.md) —— 没测到东西就不能给判定",
            file=sys.stderr,
        )
        return 2

    sel_cps = [ord(ch) for ch, _ in sel]
    ours = our_glyphs(stack, sel)

    # 参考字体的候选池 = 它覆盖的全部码位 (错配候选必须来自整个同类集合,
    # 否则"最像的另一个字"会被候选池缩小, 置换检验就失去意义了)
    all_ref_cps: list[int] = []
    try:
        from fontTools.ttLib import TTCollection, TTFont

        if ref_path.suffix.lower() == ".ttc":
            tt = TTCollection(str(ref_path)).fonts[0]
        else:
            tt = TTFont(str(ref_path), fontNumber=0)
        all_ref_cps = sorted(tt.getBestCmap().keys())
    except Exception as e:  # noqa: BLE001
        print(f"参考字体 cmap 读取失败 ({e}); 退回只比选中码位 —— 置换检验会因此变弱", file=sys.stderr)
        all_ref_cps = list(sel_cps)

    refs, read_fail = ref_glyphs(ref_path, meta["ppem"], all_ref_cps)

    cat_of_ours = {cp: category_of(cp) for cp in ours}
    cat_of_ref = {cp: category_of(cp) for cp in refs}

    print(f"参考字体: {ref_name}  ({meta['license']}, ppem={meta['ppem']})")
    print(f"我方字形 {len(ours)} 个, 参考候选池 {len(refs)} 个, 读取失败 {read_fail} 处")

    anomalies: list[dict] = []
    coverage_missing_ref: list[int] = []
    r_index = {cp: i for i, cp in enumerate(refs)}
    r_cps = list(refs)

    # ---------- A. 覆盖差异 ----------
    for cp in sel_cps:
        if cp not in refs:
            coverage_missing_ref.append(cp)

    # ---------- B. 逐像素完全相同 (硬信号) ----------
    exact: dict[tuple[int, int, str], list[int]] = defaultdict(list)
    for cp, arr in refs.items():
        h, w = arr.shape
        exact[(h, w, arr.tobytes())].append(cp)
    for cp, arr in ours.items():
        h, w = arr.shape
        same = exact.get((h, w, arr.tobytes()), [])
        others = [c for c in same if c != cp]
        if others:
            anomalies.append(
                {
                    "id": "EXACT_COLLIDE",
                    "severity": "error",
                    "cp": f"U+{cp:04X}",
                    "char": chr(cp),
                    "category": cat_of_ours[cp],
                    "detail": f"我方字形与参考字体的 {', '.join(f'U+{c:04X} {chr(c)!r}' for c in others[:4])} 逐像素完全相同",
                    "ref_cps": [f"U+{c:04X}" for c in others],
                    "art": side_by_side(arr, refs[others[0]]),
                }
            )

    # ---------- C. 置换检验 ----------
    # 分类别分块: 汉字的参考候选池有两万多个码位, 一次性算 3755x21000 的矩阵
    # 内存吃不住, 也没必要 —— 类别内检索本来就不该跨类别。
    top1_hit = 0
    ranks: list[int] = []
    scores_self: list[float] = []
    scores_best_wrong: list[float] = []
    chance_samples: list[float] = []
    suspects: list[tuple[float, int, int, float, float]] = []

    ours_by_cat: dict[str, list[int]] = defaultdict(list)
    for cp, cat in cat_of_ours.items():
        ours_by_cat[cat].append(cp)
    refs_by_cat: dict[str, list[int]] = defaultdict(list)
    for cp, cat in cat_of_ref.items():
        refs_by_cat[cat].append(cp)

    for cat, o_list in ours_by_cat.items():
        allowed_cats = SAME_CAT.get(cat, {cat})
        # 注意推导式里的循环变量: 写成 [cp for c, k in ...] 会拿到**外层**残留的 cp,
        # 整池变成同一个值重复 N 次 —— 不报错, 只是结果全错。
        r_list = [c for c, k in cat_of_ref.items() if k in allowed_cats]
        if not r_list:
            continue
        pos = {cp: j for j, cp in enumerate(r_list)}
        # 自检: 池子必须真的含有被测对象, 否则后面全是空转
        in_pool = sum(1 for cp in o_list if cp in pos)
        if in_pool < 0.5 * len(o_list):
            print(
                f"参考候选池不含我方字符 (类别 {cat}: 池 {len(r_list)} / 我方 {len(o_list)} / "
                f"命中 {in_pool}) —— 换一个参考字体或调整类别划分, 否则判定无意义",
                file=sys.stderr,
            )
            return 2
        for i0 in range(0, len(o_list), 400):
            chunk = o_list[i0 : i0 + 400]
            S = sim_block(ours, refs, chunk, r_list)
            for k, cp in enumerate(chunk):
                row = S[k]
                order = np.argsort(-row)
                j_self = pos.get(cp)
                s_self = float(row[j_self]) if j_self is not None else 0.0
                j_wrong = -1
                for j in order:
                    if r_list[j] != cp:
                        j_wrong = int(j)
                        break
                if j_wrong < 0:
                    continue
                s_wrong = float(row[j_wrong])
                scores_self.append(s_self)
                scores_best_wrong.append(s_wrong)
                if j_self is not None:
                    ranks.append(int(np.where(order == j_self)[0][0]) + 1)
                    if order[0] == j_self:
                        top1_hit += 1
                # 随机错配基线: 从同类别池里随机取几个不相干的码位
                for _ in range(3):
                    pick = int(np.random.randint(0, len(r_list)))
                    if pick != j_self:
                        chance_samples.append(float(row[pick]))
                if j_wrong != j_self and s_wrong - s_self > 0:
                    suspects.append((s_wrong - s_self, cp, r_list[j_wrong], s_self, s_wrong))

    n_cmp = max(1, len(scores_self))
    chance = np.array(chance_samples) if chance_samples else np.zeros(1)
    chance_p99 = float(np.percentile(chance, 99)) if chance.size else 0.0
    chance_max = float(chance.max()) if chance.size else 0.0
    self_med = float(np.median(scores_self)) if scores_self else 0.0
    wrong_med = float(np.median(scores_best_wrong)) if scores_best_wrong else 0.0
    margin = self_med - wrong_med

    # 可疑判定: 最佳错配分差超过随机基线 p99 之上, 才算"这个码位画的不是它自己"
    flag_margin = max(0.02, chance_p99 - self_med + 0.02)
    suspects.sort(key=lambda t: -t[0])
    for diff, cp, best_cp, s_self, s_best in suspects:
        if diff <= flag_margin:
            break
        cat = cat_of_ours[cp]
        anomalies.append(
            {
                "id": "IDENTITY_SUSPECT",
                "severity": "warn",
                "cp": f"U+{cp:04X}",
                "char": chr(cp),
                "category": cat,
                "detail": (
                    f"最佳匹配是 U+{best_cp:04X} {chr(best_cp)!r} (相似度 {s_best:.3f}), "
                    f"与自己的相似度只有 {s_self:.3f} (分差 {diff:.3f}); "
                    f"随机错配基线 p99={chance_p99:.3f}, 门槛={flag_margin:.3f}"
                ),
                "best_match": f"U+{best_cp:04X}",
                "self_score": round(s_self, 4),
                "best_score": round(s_best, 4),
                "margin": round(diff, 4),
                "art": side_by_side(ours[cp], refs[best_cp]),
            }
        )

    # ---------- 汇总 ----------
    errors = sum(1 for a in anomalies if a["severity"] == "error")
    warns = sum(1 for a in anomalies if a["severity"] == "warn")
    if not ours or not refs:
        verdict = "NO_DATA"
    else:
        verdict = "FAIL" if errors else ("REVIEW" if warns else "PASS")

    report = {
        "tool": "verify_identity",
        "reference": {
            "name": ref_name,
            "license": meta["license"],
            "source": meta["source"],
            "ppem": meta["ppem"],
            "path": str(ref_path.relative_to(ROOT)) if ref_path.is_relative_to(ROOT) else str(ref_path),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection": {
            "cats": cats or ["<all>"],
            "slice": args.slice_,
            "label": args.label or ref_name,
        },
        "inputs": {
            "chars_selected": len(sel),
            "ours_glyphs": len(ours),
            "ref_glyphs_pool": len(refs),
            "read_failures": read_fail,
            "coverage_missing_in_ref": [f"U+{c:04X}" for c in coverage_missing_ref[:200]],
            "coverage_missing_count": len(coverage_missing_ref),
        },
        "calibration": {
            "chance_p99": round(chance_p99, 4),
            "chance_max": round(chance_max, 4),
            "self_score_median": round(self_med, 4),
            "best_wrong_score_median": round(wrong_med, 4),
            "margin": round(margin, 4),
            "flag_margin": round(flag_margin, 4),
        },
        "metrics": {
            "top1_hit_rate": round(top1_hit / n_cmp, 4),
            "median_rank_of_correct": int(np.median(ranks)) if ranks else -1,
            "compared": len(scores_self),
        },
        "anomalies": anomalies,
        "summary": {"errors": errors, "warnings": warns, "verdict": verdict},
    }

    if out_path:
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        out_path.with_suffix(".md").write_text(render_md(report), encoding="utf-8")

    print()
    print(
        f"[{ref_name}] 覆盖 {len(ours)} 字 | 置换命中率 {report['metrics']['top1_hit_rate']:.1%} | "
        f"自身相似度中位 {self_med:.3f} vs 最佳错配中位 {wrong_med:.3f} | 随机基线 p99 {chance_p99:.3f}"
    )
    print(f"  判定={verdict}  error={errors} warn={warns}  参考覆盖缺口={len(coverage_missing_ref)}")
    for aid, n in Counter(a["id"] for a in anomalies).most_common():
        print(f"   {aid}: {n}")
    if out_path:
        print(f"   报告: {out_path}")
    return 1 if errors else 0


def render_md(report: dict) -> str:
    r = report["reference"]
    m = report["metrics"]
    c = report["calibration"]
    i = report["inputs"]
    s = report["summary"]
    L = [
        f"# 字形身份校验 — {r['name']}",
        "",
        f"- 参考字体: `{r['name']}` ({r['license']}, 原生 {r['ppem']}px) — {r['source']}",
        f"- 生成时间: {report['generated_at']}",
        f"- 判定: **{s['verdict']}** (error {s['errors']} / warn {s['warnings']})",
        f"- 覆盖: 我方 {i['ours_glyphs']} 字 / 参考池 {i['ref_glyphs_pool']} 字, 读取失败 {i['read_failures']} 处",
        f"- 置换检验: 命中率 {m['top1_hit_rate']:.1%} (比对 {m['compared']} 对), 自身相似度中位 {c['self_score_median']:.3f}",
        f"- 随机错配基线: p99 {c['chance_p99']:.3f} / max {c['chance_max']:.3f} → 告警门槛 {c['flag_margin']:.3f}",
        "",
    ]
    if i["coverage_missing_count"]:
        L.append(f"> 参考字体缺少我方 {i['coverage_missing_count']} 个码位 (不算错字, 已排除出比对)")
        L.append("")
    by_id: dict[str, list[dict]] = defaultdict(list)
    for a in report["anomalies"]:
        by_id[a["id"]].append(a)
    if not by_id:
        L.append("## 无异常")
        return "\n".join(L) + "\n"
    for aid in sorted(by_id):
        items = by_id[aid]
        L.append(f"## {aid} ({len(items)})")
        L.append("")
        for a in items[:30]:
            L.append(f"### {a['cp']} {a.get('char', '')!r} ({a.get('category', '')})")
            L.append("")
            L.append(f"{a['detail']}")
            L.append("")
            if a.get("art"):
                L.append("```")
                L.append(a["art"])
                L.append("```")
                L.append("")
        if len(items) > 30:
            L.append(f"…还有 {len(items) - 30} 条, 见 JSON")
            L.append("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="用开源像素字体做字形身份基准校验")
    ap.add_argument("--ref", required=True, help=f"参考字体: {', '.join(REFS)}")
    ap.add_argument("--cats", default="", help="类别过滤: ascii,punct,kana,hanzi")
    ap.add_argument("--slice", dest="slice_", default="", help="切片 如 0:1900")
    ap.add_argument("--out", default="", help="JSON 报告路径")
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    sys.exit(run(args))
