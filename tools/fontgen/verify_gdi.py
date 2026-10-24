"""Windows GDI 层面的兼容性门禁 —— "这个字体在 Word 里到底能不能用"。

为什么字形全对还不够:
    实测过一份轮廓逐像素正确的 TTF, 因为 OS/2 的代码页位写错, 在 GDI 的
    ANSI charset 请求下被替换成 Arial、在 GB2312 请求下被替换成宋体。
    字是对的, 字体却用不上 —— 而且这种故障在"打开字体看轮廓"的检查里完全看不出来。

所以这里直接**问操作系统**: 把成品 TTF 注册进 GDI, 用 Word 会用的方式去选它、
用它去渲染, 然后拿结果跟设计位图比对。

三组检查:
    1. 选择检查 (硬门禁): 各 charset 请求下 GDI 是否选中本字体。
       覆盖到的 charset 必须选中; 没覆盖的 (韩文/繁体) 必须**不**选中 ——
       选中反而是虚报。
    2. 枚举检查 (硬门禁): EnumFontFamiliesEx 在 ANSI/GB2312 下能否枚举到本族。
    3. 栅格化检查 (条件门禁): 用 GDI 把字画到 24bpp DIB, 跟设计位图逐像素比。
       用 NONANTIALIASED_QUALITY 强制单色渲染, 这样量的是**字体文件本身**的
       像素化行为, 与系统"字体平滑"开关无关 —— 后者是用户的选择, 不是文件的属性。

非 Windows 平台直接跳过 (退出码 0), 免得跨平台流水线红。

用法:
    python tools/fontgen/verify_gdi.py
    python tools/fontgen/verify_gdi.py --json reports/gdi_compat.json
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))

TTF = ROOT / "dist" / "PixelFontPC98-12.ttf"
BDF = ROOT / "dist" / "PixelFontPC98-12.bdf"
FONT_NAME = "PixelFont PC98 12"
FR_PRIVATE = 0x10

# lfCharSet 取值 (wingdi.h)
CS_DEFAULT = 1
CS_ANSI = 0
CS_SYMBOL = 2
CS_SHIFTJIS = 128
CS_HANGEUL = 129
CS_GB2312 = 134
CS_BIG5 = 136

# 字体覆盖到的代码页 -> 必须能选中的 charset
MUST_SELECT = {
    CS_ANSI: "ANSI (西文)",
    CS_DEFAULT: "DEFAULT",
    CS_GB2312: "GB2312 (简体中文)",
    CS_SHIFTJIS: "SHIFTJIS (日文)",
}
# 字体没覆盖的代码页 -> 必须**选不中**, 选中说明 OS/2 在虚报
MUST_NOT_SELECT = {
    CS_HANGEUL: "HANGEUL (韩文)",
    CS_BIG5: "BIG5 (繁体中文)",
}

# 用来做栅格化比对的样字: 全角汉字 + 半角拉丁 + 全角标点 + 假名
SAMPLES = ["中", "国", "A", "g", "，", "あ"]


class LOGFONTW(ctypes.Structure):
    _fields_ = [
        ("lfHeight", ctypes.c_long),
        ("lfWidth", ctypes.c_long),
        ("lfEscapement", ctypes.c_long),
        ("lfOrientation", ctypes.c_long),
        ("lfWeight", ctypes.c_long),
        ("lfItalic", ctypes.c_byte),
        ("lfUnderline", ctypes.c_byte),
        ("lfStrikeOut", ctypes.c_byte),
        ("lfCharSet", ctypes.c_byte),
        ("lfOutPrecision", ctypes.c_byte),
        ("lfClipPrecision", ctypes.c_byte),
        ("lfQuality", ctypes.c_byte),
        ("lfPitchAndFamily", ctypes.c_byte),
        ("lfFaceName", ctypes.c_wchar * 32),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", ctypes.c_ubyte),
        ("rgbGreen", ctypes.c_ubyte),
        ("rgbRed", ctypes.c_ubyte),
        ("rgbReserved", ctypes.c_ubyte),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 3)]


ENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_int,
    ctypes.POINTER(LOGFONTW),
    ctypes.POINTER(LOGFONTW),
    ctypes.c_ulong,
    wintypes.LPARAM,
)


def _bind() -> None:
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    gdi32.AddFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
    gdi32.AddFontResourceExW.restype = ctypes.c_int
    gdi32.RemoveFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
    gdi32.CreateFontIndirectW.argtypes = [ctypes.POINTER(LOGFONTW)]
    gdi32.CreateFontIndirectW.restype = wintypes.HGDIOBJ
    gdi32.GetTextFaceW.argtypes = [wintypes.HDC, ctypes.c_int, wintypes.LPWSTR, ctypes.c_int]
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(BITMAPINFO),
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.TextOutW.argtypes = [
        wintypes.HDC,
        ctypes.c_int,
        wintypes.LPCWSTR,
        ctypes.c_int,
    ]
    gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
    gdi32.EnumFontFamiliesExW.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(LOGFONTW),
        ENUMPROC,
        wintypes.LPARAM,
        wintypes.DWORD,
    ]
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]


def pick(gdi32, user32, charset: int, height: int = -12, quality: int = 0) -> str | None:
    """按某个 charset 请求字体, 返回 GDI 实际选中的族名。"""
    lf = LOGFONTW()
    lf.lfHeight = height
    lf.lfCharSet = charset
    lf.lfQuality = quality
    lf.lfFaceName = FONT_NAME
    hf = gdi32.CreateFontIndirectW(ctypes.byref(lf))
    if not hf:
        return None
    hdc = user32.GetDC(None)
    old = gdi32.SelectObject(hdc, hf)
    buf = ctypes.create_unicode_buffer(64)
    gdi32.GetTextFaceW(hdc, 64, buf, 64)
    face = buf.value
    gdi32.SelectObject(hdc, old)
    user32.ReleaseDC(None, hdc)
    gdi32.DeleteObject(hf)
    return face


def enum_has(gdi32, user32, charset: int) -> tuple[bool, int]:
    found = {"hit": False, "n": 0}

    def cb(lf, _nt, _ft, _l):
        found["n"] += 1
        if lf and lf.contents.lfFaceName == FONT_NAME:
            found["hit"] = True
            return 0
        return 1

    lf = LOGFONTW()
    lf.lfCharSet = charset
    lf.lfFaceName = FONT_NAME
    hdc = user32.GetDC(None)
    gdi32.EnumFontFamiliesExW(hdc, ctypes.byref(lf), ENUMPROC(cb), 0, 0)
    user32.ReleaseDC(None, hdc)
    return found["hit"], found["n"]


def render_mono(gdi32, user32, ch: str, ppem: int, quality: int) -> tuple[list[list[int]], int]:
    """把一个字画进 24bpp DIB, 返回 (墨迹掩码, 灰阶像素数)。

    灰阶像素数 > 0 说明渲染器做了抗锯齿 —— 像素字一旦出现灰阶就是"糊了"。
    """
    W, H = 64, 48
    hdc_screen = user32.GetDC(None)
    hdc = gdi32.CreateCompatibleDC(hdc_screen)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = W
    bmi.bmiHeader.biHeight = -H  # 负数 = 自上而下
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 24
    bmi.bmiHeader.biCompression = 0  # BI_RGB
    bits = ctypes.c_void_p()
    dib = gdi32.CreateDIBSection(hdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    if not dib:
        gdi32.DeleteDC(hdc)
        user32.ReleaseDC(None, hdc_screen)
        raise SystemExit("CreateDIBSection 失败")
    old_bmp = gdi32.SelectObject(hdc, dib)
    ctypes.memset(bits, 0xFF, W * H * 3)  # 白底
    gdi32.SetBkMode(hdc, 1)  # TRANSPARENT
    gdi32.SetTextColor(hdc, 0x000000)  # 黑字

    lf = LOGFONTW()
    lf.lfHeight = -ppem
    lf.lfCharSet = CS_ANSI
    lf.lfQuality = quality
    lf.lfFaceName = FONT_NAME
    hf = gdi32.CreateFontIndirectW(ctypes.byref(lf))
    old_font = gdi32.SelectObject(hdc, hf)
    gdi32.TextOutW(hdc, 0, 0, ch, 1)

    raw = ctypes.string_at(bits, W * H * 3)
    rows = []
    gray = 0
    for y in range(H):
        row = []
        base = y * W * 3
        for x in range(W):
            o = base + x * 3
            b, g, r = raw[o], raw[o + 1], raw[o + 2]
            row.append(1 if (b | g | r) < 128 else 0)
            # 抗锯齿像素 = 既不是纯黑也不是纯白。
            # 注意: ClearType 是**彩色**边 (R≠G≠B), 只查"灰阶"会漏掉它, 所以判据
            # 用"是否纯黑/纯白"而不是"三通道是否相等"。
            if (b, g, r) != (0, 0, 0) and (b, g, r) != (255, 255, 255):
                gray += 1
        rows.append(row)

    gdi32.SelectObject(hdc, old_font)
    gdi32.SelectObject(hdc, old_bmp)
    gdi32.DeleteObject(hf)
    gdi32.DeleteObject(dib)
    gdi32.DeleteDC(hdc)
    user32.ReleaseDC(None, hdc_screen)
    return rows, gray


def ink_cells(mask: list[list[int]]) -> set[tuple[int, int]]:
    return {
        (y, x)
        for y, row in enumerate(mask)
        for x, v in enumerate(row)
        if v
    }


def design_cells(rows: list[list[int]]) -> set[tuple[int, int]]:
    """BDF 里的位图是**墨迹外框** (BBX), 逐行 0/1。"""
    return {(y, x) for y, row in enumerate(rows) for x, v in enumerate(row) if v}


def normalize(cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
    """按墨迹框左上角归一化 —— 只比形状, 不比画布上的绝对位置。"""
    if not cells:
        return set()
    min_y = min(y for y, _ in cells)
    min_x = min(x for _, x in cells)
    return {(y - min_y, x - min_x) for y, x in cells}


def scale_cells(cells: set[tuple[int, int]], k: int) -> set[tuple[int, int]]:
    """整数倍放大 = 每个像素变成 k×k 的实心块 (不是坐标乘 k —— 那样会漏掉实心块本身)。"""
    return {
        (y * k + dy, x * k + dx)
        for y, x in cells
        for dy in range(k)
        for dx in range(k)
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Windows GDI 兼容性门禁")
    ap.add_argument("--json", default=str(ROOT / "reports" / "gdi_compat.json"))
    args = ap.parse_args()

    if sys.platform != "win32":
        print("非 Windows 平台, 跳过 GDI 兼容性检查")
        return 0
    if not TTF.exists():
        raise SystemExit(f"找不到成品字体: {TTF}")

    _bind()
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    from verify_products import read_bdf

    bdf = read_bdf(BDF)

    print("== 注册字体 ==")
    n = gdi32.AddFontResourceExW(str(TTF), FR_PRIVATE, None)
    print(f"  AddFontResourceExW -> {n}")
    if n == 0:
        raise SystemExit("GDI 拒绝注册该字体")

    result: dict[str, object] = {"ttf": str(TTF), "family": FONT_NAME}
    failures: list[str] = []

    # ---- 1. 选择检查 ----
    print("\n== 1. 各 charset 下的字体选择 ==")
    sel = {}
    for cs, label in MUST_SELECT.items():
        face = pick(gdi32, user32, cs)
        ok = face == FONT_NAME
        sel[cs] = {"label": label, "picked": face, "ok": ok}
        print(f"  [{'OK ' if ok else 'FAIL'}] lfCharSet={cs:<4} {label:<20} 选中={face!r}")
        if not ok:
            failures.append(f"charset {label} 选中了 {face!r} 而不是本字体")
    for cs, label in MUST_NOT_SELECT.items():
        face = pick(gdi32, user32, cs)
        ok = face != FONT_NAME
        sel[cs] = {"label": label, "picked": face, "ok": ok, "expect": "不选中"}
        print(
            f"  [{'OK ' if ok else 'FAIL'}] lfCharSet={cs:<4} {label:<20} 选中={face!r} "
            f"(字体不含该语系字形, 选不中才对)"
        )
        if not ok:
            failures.append(f"charset {label} 选中了本字体, 但字体没有该语系字形 (虚报)")
    result["selection"] = sel

    # ---- 2. 枚举检查 ----
    print("\n== 2. EnumFontFamiliesEx 枚举 ==")
    en = {}
    for cs, label in MUST_SELECT.items():
        hit, cnt = enum_has(gdi32, user32, cs)
        en[cs] = {"label": label, "hit": hit, "families": cnt}
        print(f"  [{'OK ' if hit else 'FAIL'}] lfCharSet={cs:<4} {label:<20} 枚举 {cnt} 族, 含本族={hit}")
        if not hit:
            failures.append(f"charset {label} 的字体枚举里没有本族")
    result["enumeration"] = en

    # ---- 3. 栅格化检查 ----
    print("\n== 3. GDI 栅格化 vs 设计位图 ==")
    ras = []
    for ch in SAMPLES:
        cp = ord(ch)
        if cp not in bdf:
            print(f"  跳过 {ch!r} (BDF 里没有)")
            continue
        w, h, bmp = bdf[cp]
        want = design_cells(bmp)
        for ppem in (12, 24):
            for quality, qname in ((3, "NONANTIALIASED"), (0, "DEFAULT")):
                mask, gray = render_mono(gdi32, user32, ch, ppem, quality)
                got = ink_cells(mask)
                # 形状比: 归一化后逐格比对 (2 倍字号 = 每个像素变成 2x2 实心块)
                exp = want if ppem == 12 else scale_cells(want, ppem // 12)
                exp_norm = normalize(exp)
                got_norm = normalize(got)
                same = exp_norm == got_norm
                exp_box = (
                    max(y for y, _ in exp) - min(y for y, _ in exp) + 1,
                    max(x for _, x in exp) - min(x for _, x in exp) + 1,
                )
                got_box = (
                    (max(y for y, _ in got) - min(y for y, _ in got) + 1)
                    if got
                    else 0,
                    (max(x for _, x in got) - min(x for _, x in got) + 1) if got else 0,
                )
                entry = {
                    "char": ch,
                    "cp": f"U+{cp:04X}",
                    "ppem": ppem,
                    "quality": qname,
                    "shape_match": same,
                    "gray_pixels": gray,
                    "expected_ink_box": list(exp_box),
                    "got_ink_box": list(got_box),
                    "expected_ink_cells": len(exp),
                    "got_ink_cells": len(got),
                }
                ras.append(entry)
                flag = "OK " if same else "DIFF"
                print(
                    f"  [{flag}] {ch!r} U+{cp:04X} {ppem}ppem {qname:<15} "
                    f"墨迹 {len(got)}/{len(exp)} 格, 墨迹框 {got_box} vs 设计 {exp_box}, 灰阶 {gray}px"
                )
    result["raster"] = ras

    # 12ppem + NONANTIALIASED 是"字体文件本身的像素化行为", 与系统平滑开关无关 -> 硬门禁
    hard = [e for e in ras if e["ppem"] == 12 and e["quality"] == "NONANTIALIASED"]
    hard_bad = [e for e in hard if not e["shape_match"]]
    if hard_bad:
        failures.append(
            "12ppem 单色渲染与设计位图不一致: "
            + ", ".join(f"{e['char']}({e['got_ink_cells']}/{e['expected_ink_cells']})" for e in hard_bad)
        )
    result["hard_gate_failures"] = failures

    gdi32.RemoveFontResourceExW(str(TTF), FR_PRIVATE, None)

    print()
    if failures:
        print("GDI 兼容性检查失败:")
        for f in failures:
            print(f"  - {f}")
    else:
        print("GDI 兼容性检查: 通过 (各 charset 均能选中本字体, 12ppem 单色渲染与设计位图一致)")

    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({**result, "verdict": "PASS" if not failures else "FAIL"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"报告: {out}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
