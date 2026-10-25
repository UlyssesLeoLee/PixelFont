"""快照自洽门禁的**自测** —— 证明这道门禁真能抓到错。

一个从不知道自己被测的门禁, 等于没有门禁。这里对快照做**故障注入**:
每次故意破坏一个地方, 门禁必须把问题报出来。跑法:

    python tools/fontgen/verify_snapshot_gate.py

全部用例通过 = 退出码 0。用例本身不依赖 `third_party/`, 只用入库的快照
与入库的生产源裁剪版。

用完的临时快照会删掉 —— 但只删**本脚本自己建的**那些, 不碰仓库里的。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "fontgen"))

import route_multi12 as rm  # noqa: E402

ORIG_SNAPSHOT = rm.SNAPSHOT


def _load() -> dict:
    return json.loads(ORIG_SNAPSHOT.read_text(encoding="utf-8"))


def _save(d: dict, path: Path) -> None:
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def _run_gate(snapshot: Path) -> str:
    """在临时快照上跑门禁, 返回错误文本 (空 = 通过)。

    门禁**崩了**和门禁**报出了问题**是两回事 —— 前者是 bug, 后面才是
    门禁在干活。所以崩溃单独打标记, 由调用方判 FAIL。
    """
    rm.SNAPSHOT = snapshot
    try:
        rm.verify_snapshot()
        return ""
    except SystemExit as e:
        return str(e)
    except Exception as e:  # noqa: BLE001 —— 这里就是要把它抓出来当 bug 报
        return f"__CRASH__ 门禁抛了未预期的异常: {type(e).__name__}: {e}"
    finally:
        rm.SNAPSHOT = ORIG_SNAPSHOT


# --------------------------------------------------------------------------
# 故障注入用例
# --------------------------------------------------------------------------


def case_layer_gap(d: dict) -> tuple[str, str]:
    """删掉几个码位的 layer 条目 -> 应报「layer 没覆盖 route」。"""
    keys = sorted(d["layer"])[:3]
    for k in keys:
        del d["layer"][k]
    return (f"删掉 {len(keys)} 个码位的 layer 条目",
            "layer 里没有")


def case_phantom_layer(d: dict) -> tuple[str, str]:
    """凭空加一层 -> 应报「未登记的层」。"""
    first = sorted(d["layer"])[0]
    d["layer"][first] = "L8 凭空的一层"
    return (f"给 {first} 安上未登记的层名", "未登记")


def case_wrong_block(d: dict) -> tuple[str, str]:
    """把 CJK 码位挪到 L6 (只收 JIS 一级汉字) -> 应报「不在该层的编码块内」。"""
    moved = None
    for cp, lname in sorted(d["layer"].items()):
        if lname == "L7 CJK 其余":
            d["layer"][cp] = "L6 JIS X 0208 一级汉字"
            moved = cp
            break
    if moved is None:
        raise SystemExit("用例前提不成立: 快照里没有 L7 的码位")
    return (f"把 {moved} 从 L7 挪到 L6 (它不是 JIS 一级汉字)", "编码块")


def case_unknown_source(d: dict) -> tuple[str, str]:
    """把路由指向未登记的源 -> 应报「路由指向未登记的源」。"""
    first = sorted(d["route"])[0]
    d["route"][first] = "no_such_source"
    return (f"把 {first} 路由到未登记的源", "未登记的源")


def case_wrong_source(d: dict) -> tuple[str, str]:
    """把路由指向一个没有该字形的源 -> 应报「该源没有这个字形」。"""
    hit = None
    for cp, key in sorted(d["route"].items()):
        if key == "fusion_ja" and int(cp[2:], 16) > 0x4E00:
            # 找一个 fusion_ko 没有的汉字码位
            hit = cp
            break
    if hit is None:
        raise SystemExit("用例前提不成立: 快照里没有可用的 CJK 码位")
    d["route"][hit] = "fusion_ko"
    return (f"把 {hit} (汉字) 路由到 fusion_ko (它没有这个字形)", "没有这个字形")


def case_empty_layer(d: dict) -> tuple[str, str]:
    """把某层整体搬空 -> 应报「空层」或「缺少这些层」。"""
    target = None
    for cp, lname in sorted(d["layer"].items()):
        if lname == "L2 Greek":
            target = lname
            break
    if target is None:
        raise SystemExit("用例前提不成立: 快照里没有 L2")
    for cp, lname in list(d["layer"].items()):
        if lname == target:
            d["layer"][cp] = "L1 Latin Ext A/B"
    return (f"把整层 {target} 搬空", "L2 Greek")


def case_total(d: dict) -> tuple[str, str]:
    """把 stats.total 改错 -> 应报「stats.total 与路由表条数不符」。"""
    d["stats"]["total"] = 12345
    return ("把 stats.total 改成 12,345", "stats.total")


def case_missing_tag(d: dict) -> tuple[str, str]:
    """删掉一个层的分类标签 -> 应报「layer_tags 缺项」。"""
    d["layer_tags"].pop("L4 Hangul syllables", None)
    return ("删掉 L4 的分类标签", "layer_tags")


CASES = [
    case_layer_gap,
    case_phantom_layer,
    case_wrong_block,
    case_unknown_source,
    case_wrong_source,
    case_empty_layer,
    case_total,
    case_missing_tag,
]


def main() -> int:
    print("=" * 74)
    print("快照自洽门禁 —— 故障注入自测")
    print("=" * 74)
    print(f"快照: {ORIG_SNAPSHOT.relative_to(ROOT)}\n")

    # 先确认未篡改的快照能过
    err = _run_gate(ORIG_SNAPSHOT)
    if err:
        print("[FAIL] 未篡改的快照就没过门禁 —— 门禁本身有问题:")
        print(err)
        return 1
    print("[OK  ] 未篡改的快照通过门禁\n")

    tmpdir = Path(tempfile.mkdtemp(prefix="pf_snapgate_"))
    bad = 0
    try:
        for fn in CASES:
            d = _load()
            desc, expect = fn(d)
            p = tmpdir / "route_multi12.json"
            _save(d, p)
            err = _run_gate(p)
            if not err:
                print(f"[FAIL] {desc}")
                print(f"       门禁**没有报错** —— 它抓不到这类损坏, 等于没门禁")
                bad += 1
            elif "__CRASH__" in err:
                print(f"[FAIL] {desc}")
                print(f"       门禁**崩了**, 而不是报出问题:")
                print("       " + err.replace("__CRASH__ ", ""))
                bad += 1
            elif expect not in err:
                print(f"[FAIL] {desc}")
                print(f"       报错了, 但不是预期的 {expect!r}:")
                print("       " + err.splitlines()[1] if len(err.splitlines()) > 1 else err)
                bad += 1
            else:
                detail = "\n".join("       " + ln for ln in err.splitlines()[1:7])
                print(f"[OK  ] {desc}")
                print(f"       抓到了:\n{detail}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print()
    print("=" * 74)
    if bad:
        print(f"[FAIL] {bad}/{len(CASES)} 个用例未过 —— 门禁不可信")
        print("=" * 74)
        return 1
    print(f"[OK  ] {len(CASES)}/{len(CASES)} 个故障注入用例全部被抓到")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
