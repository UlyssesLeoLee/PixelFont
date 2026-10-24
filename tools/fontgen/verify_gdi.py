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

# 栅格化比对**不做抽样**: 全字符集逐字扫。抽 6 个字样只能证明那 6 个字没问题,
# 而"这个字在 Word 里画对了吗"本来就是逐字的问题。


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


class GdiCanvas:
    """一块可复用的 24bpp DIB 画布 —— 全字符集扫描要画几千次, 每次重建 DC 太慢。

    为什么用 24bpp 而不是 1bpp: 1bpp 的调色板极性(index 0/1 谁是黑)有歧义,
    读回会全 0; 24bpp 没有这个问题, 而且能直接判"这个像素既不是纯黑也不是纯白"
    (抗锯齿留下的中间色, 含 ClearType 的彩色边)。
    """

    W, H = 64, 48

    def __init__(self, gdi32, user32):
        import numpy as np

        self.np = np
        self.gdi32 = gdi32
        self.user32 = user32
        self.hdc_screen = user32.GetDC(None)
        self.hdc = gdi32.CreateCompatibleDC(self.hdc_screen)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.W
        bmi.bmiHeader.biHeight = -self.H  # 负数 = 自上而下
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 24
        bmi.bmiHeader.biCompression = 0  # BI_RGB
        self.bits = ctypes.c_void_p()
        dib = gdi32.CreateDIBSection(
            self.hdc, ctypes.byref(bmi), 0, ctypes.byref(self.bits), None, 0
        )
        if not dib:
            raise SystemExit("CreateDIBSection 失败")
        self.dib = dib
        self.old_bmp = gdi32.SelectObject(self.hdc, dib)
        gdi32.SetBkMode(self.hdc, 1)  # TRANSPARENT
        gdi32.SetTextColor(self.hdc, 0x000000)  # 黑字
        self._fonts: dict[tuple[int, int], object] = {}

    def _font(self, ppem: int, quality: int):
        key = (ppem, quality)
        f = self._fonts.get(key)
        if f is None:
            lf = LOGFONTW()
            lf.lfHeight = -ppem
            lf.lfCharSet = CS_ANSI
            lf.lfQuality = quality
            lf.lfFaceName = FONT_NAME
            f = self.gdi32.CreateFontIndirectW(ctypes.byref(lf))
            self._fonts[key] = f
        return f

    def render(self, ch: str, ppem: int, quality: int) -> tuple[set[tuple[int, int]], int]:
        """画一个字, 返回 (墨迹格集合, 抗锯齿像素数)。"""
        np = self.np
        ctypes.memset(self.bits, 0xFF, self.W * self.H * 3)  # 白底
        hf = self._font(ppem, quality)
        old_font = self.gdi32.SelectObject(self.hdc, hf)
        self.gdi32.TextOutW(self.hdc, 0, 0, ch, 1)
        self.gdi32.SelectObject(self.hdc, old_font)
        raw = ctypes.string_at(self.bits, self.W * self.H * 3)
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(self.H, self.W, 3)
        non_white = (arr != 255).any(axis=2)
        # 抗锯齿像素 = 既不是纯黑也不是纯白 (ClearType 是彩色边, 不能只查灰阶)
        mixed = non_white & ~((arr == 0).all(axis=2))
        ys, xs = np.nonzero(non_white)
        cells = {(int(y), int(x)) for y, x in zip(ys, xs)}
        return cells, int(mixed.sum())

    def close(self) -> None:
        for f in self._fonts.values():
            self.gdi32.DeleteObject(f)
        self.gdi32.SelectObject(self.hdc, self.old_bmp)
        self.gdi32.DeleteObject(self.dib)
        self.gdi32.DeleteDC(self.hdc)
        self.user32.ReleaseDC(None, self.hdc_screen)


def render_mono(gdi32, user32, ch: str, ppem: int, quality: int) -> tuple[list[list[int]], int]:
    """单字渲染的兼容入口 (保留给按需调用的脚本)。"""
    cv = GdiCanvas(gdi32, user32)
    try:
        cells, gray = cv.render(ch, ppem, quality)
    finally:
        cv.close()
    w, h = GdiCanvas.W, GdiCanvas.H
    return [[1 if (y, x) in cells else 0 for x in range(w)] for y in range(h)], gray


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


def box_of(cells: set[tuple[int, int]]) -> tuple[int, int]:
    """墨迹外框尺寸 (高, 宽); 空字形算 0×0。"""
    if not cells:
        return (0, 0)
    return (
        max(y for y, _ in cells) - min(y for y, _ in cells) + 1,
        max(x for _, x in cells) - min(x for _, x in cells) + 1,
    )


def _esc(ch: str) -> str:
    """把字符转成可安全放进 TSV 的形式 (转义制表/换行/控制符)。"""
    return ch.encode("unicode_escape").decode("ascii")


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

    # ---- 3. 栅格化检查: **全字符集**, 不抽样 ----
    #
    # 为什么必须全量: "这个字在 Word 里画对了吗" 是**逐字**的问题, 抽 6 个字样
    # 只能证明那 6 个字没问题。4161 个字全扫一遍, 才是"确保能用"。
    #
    # 三条判据 (分层, 因为它们对系统设置的敏感度不同):
    #   a) 墨迹外框尺寸一致 —— 与抗锯齿无关, 任何系统上都必须成立 (硬门禁)
    #   b) 墨迹集合逐格一致 —— 强制单色渲染 (NONANTIALIASED) 时必须成立 (硬门禁);
    #      这条量的是**字体文件本身**的像素化行为, 与系统字体平滑开关无关
    #   c) DEFAULT 质量下的抗锯齿像素数 —— 只是报告, 不是判据 (系统设置的事)
    #
    # 报告分两份, 避免主报告被 4161 条记录撑成 1.4 MB:
    #   reports/gdi_compat.json      —— 结论 (计数 + 失败明细)
    #   reports/gdi_raster_scan.tsv  —— 逐码位明细 (可 grep 任意一个码位)
    print("\n== 3. GDI 栅格化 vs 设计位图 (全字符集, 不抽样) ==")
    cv = GdiCanvas(gdi32, user32)
    ras_fail: list[dict] = []
    scan_rows: list[str] = [
        "cp\tchar\tink_cells\tbox12\tshape12\tbox24\tshape24\taa_default"
    ]
    n12_box = n12_shape = n24_box = n24_shape = 0
    aa_total = 0
    scanned = 0
    try:
        for cp in sorted(bdf):
            w, h, bmp = bdf[cp]
            want = design_cells(bmp)
            ch = chr(cp)

            # 12ppem = 设计尺寸 (1:1)。强制单色量形状, DEFAULT 质量量抗锯齿。
            mono12, _ = cv.render(ch, 12, 3)
            _, aa = cv.render(ch, 12, 0)
            # 24ppem (=18pt): 精确 2 倍整数缩放
            mono24, _ = cv.render(ch, 24, 3)

            aa_total += aa
            scanned += 1

            exp_box, got_box = box_of(want), box_of(mono12)
            box_ok = exp_box == got_box
            shape_ok = normalize(want) == normalize(mono12)

            exp24 = scale_cells(want, 2)
            exp24_box, got24_box = box_of(exp24), box_of(mono24)
            box24_ok = exp24_box == got24_box
            shape24_ok = normalize(exp24) == normalize(mono24)

            n12_box += box_ok
            n12_shape += shape_ok
            n24_box += box24_ok
            n24_shape += shape24_ok

            scan_rows.append(
                f"U+{cp:04X}\t{_esc(ch)}\t{len(want)}\t{int(box_ok)}\t"
                f"{int(shape_ok)}\t{int(box24_ok)}\t{int(shape24_ok)}\t{aa}"
            )

            if not (box_ok and shape_ok and box24_ok and shape24_ok):
                ras_fail.append(
                    {
                        "cp": f"U+{cp:04X}",
                        "char": ch,
                        "expected_ink_box_12": list(exp_box),
                        "got_ink_box_12": list(got_box),
                        "expected_ink_box_24": list(exp24_box),
                        "got_ink_box_24": list(got24_box),
                        "expected_ink_cells": len(want),
                        "got_ink_cells_12": len(mono12),
                        "got_ink_cells_24": len(mono24),
                        "box_match_12": box_ok,
                        "shape_match_12": shape_ok,
                        "box_match_24": box24_ok,
                        "shape_match_24": shape24_ok,
                    }
                )
    finally:
        cv.close()

    scan_path = ROOT / "reports" / "gdi_raster_scan.tsv"
    scan_path.write_text("\n".join(scan_rows) + "\n", encoding="utf-8")

    print(f"  扫描 {scanned} 个码位 x (12ppem + 24ppem), 两种渲染路径")
    print(f"  12ppem 墨迹外框一致      : {n12_box} / {scanned}")
    print(f"  12ppem 墨迹集合逐格一致  : {n12_shape} / {scanned}")
    print(f"  24ppem 墨迹外框一致      : {n24_box} / {scanned}")
    print(f"  24ppem 墨迹集合逐格一致  : {n24_shape} / {scanned}")
    print(f"  DEFAULT 质量下抗锯齿像素合计: {aa_total}")
    print(f"  逐码位明细: {scan_path}")
    if ras_fail:
        print(f"  不一致 {len(ras_fail)} 例, 例: {ras_fail[:3]}")

    result["raster_summary"] = {
        "scanned": scanned,
        "box_match_12": n12_box,
        "shape_match_12": n12_shape,
        "box_match_24": n24_box,
        "shape_match_24": n24_shape,
        "aa_pixels_default_total": aa_total,
        "detail_file": str(scan_path.relative_to(ROOT)).replace("\\", "/"),
    }
    result["raster_failures"] = ras_fail

    if ras_fail:
        failures.append(
            f"GDI 12/24ppem 栅格化与设计位图不一致 {len(ras_fail)} 例: "
            + "; ".join(f"{r['cp']} {r['char']!r}" for r in ras_fail[:5])
        )
    result["hard_gate_failures"] = failures

    gdi32.RemoveFontResourceExW(str(TTF), FR_PRIVATE, None)

    print()
    if failures:
        print("GDI 兼容性检查失败:")
        for f in failures:
            print(f"  - {f}")
    else:
        print(
            "GDI 兼容性检查: 通过 "
            f"(各 charset 均能选中本字体; {scanned} 个码位在 12ppem/24ppem 下"
            "单色渲染与设计位图逐格一致)"
        )

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
