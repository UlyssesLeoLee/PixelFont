"""「简日全量」门禁的**自测** —— 证明这两道门禁真能抓到错。

背景: 用户 2026-10-25 指令「确保日语字和中文简体都是全量」。这条要求如果只
写成一句文档里的断言, 它就只是一句文档; 写进门禁才可执行, 而**门禁也要被测**
—— 一个从不知道自己被测的门禁, 等于没有门禁。

这里对四道新门禁做故障注入:

  · 字符集门禁 6 —— 简体中文全量 (GB2312 6,763)
  · 字符集门禁 7 —— 日文全量 (JIS X 0208 6,355 汉字 + 200 符号/假名)
  · 推导门禁 11 —— zlabs_cn 只承接 Fusion 两源都不覆盖的码位 (向后兼容不变式)
  · 推导门禁 12 —— 每个全量码位都有路由

用法:
    python tools/fontgen/verify_coverage_gates.py

全部用例通过 = 退出码 0。

**故障注入打在哪儿** (这个选择本身是门禁设计的一部分):

  · 门禁 6 / 7 注入在「口径」上 —— 把 GB2312 / JIS X 0208 的判定集合**扩大一个
    字符集里本来就没有的码位**, 模拟「标准要求的字我们没有」。这样字符集本身
    不变, 门禁 1..5 照样过, 门禁 6/7 才真的被走到 —— 否则门禁 1 (总量) 会先炸,
    门禁 6/7 就永远测不到。
  · 另有一例注入在**源字体**上 (「某个源少了一个字」) 并同步把预期总量改成
    自洽的值 —— 这是最真实的故障形态: 所有计数门禁都绿, 只有「全量」门禁
    能抓到标准未被满足。
  · 门禁 11 / 12 注入在「路由表」上 —— 改路由表的副本, 不动磁盘上的快照。

同样地, 「门禁崩了」和「门禁报出了问题」是两回事, 前者是 bug。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "fontgen"))

import charset_multi12 as m12  # noqa: E402
import derive_route_multi12 as dr  # noqa: E402
import route_multi12 as rm  # noqa: E402


def _charset_cps() -> set[int]:
    return {ord(c) for c, _ in m12.build_charset_multi12()}


def _absent_cjk() -> int:
    """找一个**不在**当前字符集里的 CJK 码位 (用来模拟「标准多要求一个字」)。"""
    cps = _charset_cps()
    for cp in range(0x4E00, 0xA000):
        if cp not in cps:
            return cp
    raise SystemExit("用例前提不成立: 字符集已覆盖整个 CJK 块")


def _run_charset_gate() -> str:
    """跑字符集层的全量门禁, 返回错误文本 (空 = 通过)。"""
    try:
        m12.gate_multi12()
        return ""
    except SystemExit as e:
        return str(e)
    except Exception as e:  # noqa: BLE001 —— 这里就是要把它抓出来当 bug 报
        return f"__CRASH__ 门禁抛了未预期的异常: {type(e).__name__}: {e}"


def _run_charset_gate_with_patches(patch: dict) -> str:
    """临时替换模块级函数/常量, 跑完整的 `gate_multi12()`。

    用完必须还原 —— 这个脚本是进程内改模块状态, 泄漏出去会污染别的用例。
    """
    saved = {k: getattr(m12, k) for k in patch}
    try:
        for k, v in patch.items():
            setattr(m12, k, v)
        return _run_charset_gate()
    finally:
        for k, v in saved.items():
            setattr(m12, k, v)


CASES: list[tuple[str, str, callable]] = []


def case(label: str, expect: str):
    def deco(fn):
        CASES.append((label, expect, fn))
        return fn
    return deco


# --------------------------------------------------------------------------
# 门禁 6: 简体中文全量
# --------------------------------------------------------------------------


@case("GB2312 口径多要求一个字 (字符集里本来就没有的那个)", "简体中文不全量")
def _c_gb():
    victim = _absent_cjk()
    # 先抓住原函数 —— 补丁里再调 `m12.gb2312_hanzi()` 会调到自己, 直接递归爆栈
    real = m12.gb2312_hanzi
    return _run_charset_gate_with_patches(
        {"gb2312_hanzi": lambda: set(real()) | {victim}}
    )


@case("某个源少了一个 GB2312 汉字, 且预期总量被改成自洽值 (计数门禁全绿, 只有全量门禁能抓到)",
      "简体中文不全量")
def _c_gb_source_lost():
    ja_cps = m12.cjk_source_cmaps()["fusion_ja"]
    gb = m12.gb2312_hanzi()
    # 挑一个**只有 ZLabs 提供**的 GB2312 汉字 —— Fusion 不覆盖, 去掉它只能靠 zlabs
    victim = min(gb - ja_cps)
    real_cmap = m12._cmap

    def patched_cmap(p):
        return set(real_cmap(p)) - {victim}

    saved = {k: getattr(m12, k) for k in ("_cmap", "TARGET_TOTAL", "TARGET_A")}
    try:
        m12._cmap = patched_cmap
        # 把预期总量改成「少一个字之后」的自洽值 ——
        # 于是门禁 1 (总量) / 门禁 2 (方案 A 交叉) / 门禁 3 (A∪CJK 交叉) 全绿,
        # 只有门禁 6 能抓到「标准没被满足」。这正是这道门禁存在的意义。
        rows = m12.ledger()
        m12.TARGET_TOTAL = rows[-1][2]
        m12.TARGET_A = rows[-2][2]
        try:
            m12.gate_multi12()
        except SystemExit as e:
            return str(e)
        except Exception as e:  # noqa: BLE001
            return f"__CRASH__ 门禁抛了未预期的异常: {type(e).__name__}: {e}"
    finally:
        for k, v in saved.items():
            setattr(m12, k, v)
    return ""


# --------------------------------------------------------------------------
# 门禁 7: 日文全量
# --------------------------------------------------------------------------


@case("JIS X 0208 汉字口径多要求一个字", "日文不全量")
def _c_jis():
    victim = _absent_cjk()
    real = m12.jis_x0208_all
    return _run_charset_gate_with_patches(
        {"jis_x0208_all": lambda: set(real()) | {victim}}
    )


@case("JIS X 0208 符号/假名口径多要求一个字", "日文不全量")
def _c_kana():
    victim = _absent_cjk()
    real = m12.jis_x0208_kana_punct
    return _run_charset_gate_with_patches(
        {"jis_x0208_kana_punct": lambda: set(real()) | {victim}}
    )


# --------------------------------------------------------------------------
# 门禁 11 / 12: 路由表
# --------------------------------------------------------------------------


@case("把一个 Fusion 能提供的汉字改路由到 zlabs_cn", "抢了 Fusion 能提供的")
def _c_zlabs_steal():
    route = dict(rm.build_route())
    victim = next(cp for cp, s in route.items()
                  if s == "fusion_ja" and cp > 0x4E00)
    route[victim] = "zlabs_cn"
    return "\n".join(dr.gate_zlabs_only_holes(route))


@case("把一个 GB2312 汉字从路由表里删掉", "没有路由")
def _c_missing_route():
    route = dict(rm.build_route())
    gb = m12.gb2312_hanzi()
    victim = min(gb & set(route))
    del route[victim]
    return "\n".join(dr.gate_full_coverage(route))


@case("把一个 JIS 汉字从路由表里删掉", "没有路由")
def _c_missing_jis_route():
    route = dict(rm.build_route())
    jis = m12.jis_x0208_all()
    victim = min(jis & set(route))
    del route[victim]
    return "\n".join(dr.gate_full_coverage(route))


def main() -> int:
    print("=" * 74)
    print("「简日全量」门禁 —— 故障注入自测")
    print("=" * 74)
    print()

    # 先确认未注入时全过 —— 否则「注入后报错」可能只是因为它本来就坏
    base = _run_charset_gate()
    if base:
        print("[FAIL] 未注入任何故障时字符集门禁就没过 —— 门禁本身有问题:")
        print(base)
        return 1
    print("[OK  ] 未注入故障时, 字符集门禁通过")

    route = rm.build_route()
    p11 = dr.gate_zlabs_only_holes(route)
    p12 = dr.gate_full_coverage(route)
    if p11 or p12:
        print("[FAIL] 未注入故障时推导门禁就没过 —— 门禁本身有问题:")
        print("\n".join(p11 + p12))
        return 1
    print("[OK  ] 未注入故障时, 推导门禁 11/12 通过")
    print()

    bad = 0
    for label, expect, fn in CASES:
        err = fn()
        if not err:
            print(f"[FAIL] {label}")
            print("       门禁**没有报错** —— 它抓不到这类损坏, 等于没门禁")
            bad += 1
        elif "__CRASH__" in err:
            print(f"[FAIL] {label}")
            print("       门禁**崩了**, 而不是报出问题:")
            print("       " + err.replace("__CRASH__ ", ""))
            bad += 1
        elif expect not in err:
            print(f"[FAIL] {label}")
            print(f"       报错了, 但不是预期的 {expect!r}:")
            for ln in err.splitlines()[:6]:
                print("       " + ln)
            bad += 1
        else:
            print(f"[OK  ] {label}")
            for ln in err.splitlines()[:4]:
                print("       " + ln)

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
