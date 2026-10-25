"""已安装字体的复核工具。

安装完成的判据不是「文件拷过去了」, 而是**系统会话里用的就是这一份**。
本脚本从四个层面取证, 全部针对**系统里装的那份**, 不做私有注册
(私有注册只证明文件本身, 不证明安装):

  1. 文件层: 注册表登记的用户字体路径 / 大小 / sha256
  2. 枚举层: GDI 能不能枚举到 "PixelFont PC98 12" (ANSI 与 GB2312)
  3. 选择层: 按名字请求时 GDI 选中的族名 —— 这正是「Word 里选不中」那个问题
  4. 渲染层: 全字符集 4,161 字, 12ppem 与 24ppem 下与设计位图逐格比对

已知边界 (不要当没看见):
  `GetFontData` 的**读取**在本机被系统拒绝 (size 查询可用, 读取一律 GDI_ERROR;
  Arial 等系统字体同样如此), 所以「会话内字体缓存里的字节」无法直接取证。
  本工具用「文件指纹 + 枚举 + 选择 + 全字符集渲染」四层间接证明;
  若需要字节级证据, 需注销重登后重跑。

用法:
    python tools/fontgen/verify_install.py
退出码 0 = 四层全过; 1 = 有不一致
"""
from __future__ import annotations

import ctypes
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import verify_gdi as vg  # noqa: E402
from verify_products import read_bdf  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FONT_NAME = vg.FONT_NAME
REG_VALUE = "PixelFont PC98 12 (TrueType)"
REG_PATH = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"


def release_artifact() -> tuple[Path, bytes]:
    ttf = REPO / "dist" / "PixelFontPC98-12.ttf"
    if not ttf.exists():
        raise SystemExit(f"[FATAL] 缺少发布产物 {ttf}, 先跑构建")
    return ttf, ttf.read_bytes()


def installed_path() -> Path | None:
    """注册表登记的用户字体文件路径 (HKCU = 按用户安装, 不需要管理员)。"""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as k:
            val, _ = winreg.QueryValueEx(k, REG_VALUE)
    except OSError:
        return None
    return Path(val)


def main() -> int:
    ttf, art = release_artifact()
    exp_sha = hashlib.sha256(art).hexdigest().upper()
    print("=" * 72)
    print(f"{FONT_NAME} —— 已安装字体复核 (针对系统安装的那份, 不做私有注册)")
    print("=" * 72)
    print(f"期望 (发布产物 {ttf.name}): {len(art)} 字节 / {exp_sha}")

    bad = 0

    # ---------- 1. 文件层 ----------
    print("\n== 1. 文件层 (注册表登记的路径 + 指纹) ==")
    p = installed_path()
    if p is None:
        print("  [FAIL] 注册表 HKCU\\...\\Fonts 里没有登记该字体")
        return 1
    print(f"  注册表路径: {p}")
    if not p.exists():
        print("  [FAIL] 注册表指向的文件不存在")
        return 1
    data = p.read_bytes()
    got_sha = hashlib.sha256(data).hexdigest().upper()
    print(f"  实测: {len(data)} 字节 / {got_sha}")
    if got_sha != exp_sha:
        print("  [FAIL] 与发布产物不一致 —— 需要覆盖安装")
        bad += 1
    else:
        print("  [OK  ] 与发布产物逐字节一致")

    vg._bind()
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    # ---------- 2. 枚举层 ----------
    print("\n== 2. 枚举层 (EnumFontFamiliesEx) ==")
    for cs, label in vg.MUST_SELECT.items():
        hit, cnt = vg.enum_has(gdi32, user32, cs)
        print(f"  [{'OK  ' if hit else 'FAIL'}] {label:<20} 枚举 {cnt} 族, 含本族={hit}")
        if not hit:
            bad += 1

    # ---------- 3. 选择层 ----------
    print("\n== 3. 选择层 (按名字请求, GDI 实际选中的族)")
    for cs, label in vg.MUST_SELECT.items():
        face = vg.pick(gdi32, user32, cs)
        ok = face == FONT_NAME
        print(f"  [{'OK  ' if ok else 'FAIL'}] {label:<20} 选中={face!r}")
        if not ok:
            bad += 1
    for cs, label in vg.MUST_NOT_SELECT.items():
        face = vg.pick(gdi32, user32, cs)
        ok = face != FONT_NAME
        print(f"  [{'OK  ' if ok else 'FAIL'}] {label:<20} 选中={face!r} "
              f"(该语系不在字符集内, 选不中才对)")
        if not ok:
            bad += 1

    # ---------- 4. 渲染层 ----------
    print("\n== 4. 渲染层 (全字符集 vs 设计位图, 12ppem + 24ppem) ==")
    bdf = read_bdf(vg.BDF)
    cv = vg.GdiCanvas(gdi32, user32)
    n12_box = n12_shape = n24_box = n24_shape = 0
    aa_total = 0
    scanned = 0
    fails: list[str] = []
    try:
        for cp in sorted(bdf):
            w, h, bmp = bdf[cp]
            want = vg.design_cells(bmp)
            ch = chr(cp)
            mono12, _ = cv.render(ch, 12, 3)     # NONANTIALIASED
            _, aa = cv.render(ch, 12, 0)         # DEFAULT (抗锯齿只作报告)
            mono24, _ = cv.render(ch, 24, 3)
            aa_total += aa
            scanned += 1

            box_ok = vg.box_of(want) == vg.box_of(mono12)
            shape_ok = vg.normalize(want) == vg.normalize(mono12)
            exp24 = vg.scale_cells(want, 2)
            box24_ok = vg.box_of(exp24) == vg.box_of(mono24)
            shape24_ok = vg.normalize(exp24) == vg.normalize(mono24)

            n12_box += box_ok
            n12_shape += shape_ok
            n24_box += box24_ok
            n24_shape += shape24_ok
            if not (box_ok and shape_ok and box24_ok and shape24_ok):
                fails.append(f"U+{cp:04X} {ch!r}")
    finally:
        cv.close()

    print(f"  扫描 {scanned} 个码位")
    print(f"  12ppem 墨迹外框一致      : {n12_box} / {scanned}")
    print(f"  12ppem 墨迹集合逐格一致  : {n12_shape} / {scanned}")
    print(f"  24ppem 墨迹外框一致      : {n24_box} / {scanned}")
    print(f"  24ppem 墨迹集合逐格一致  : {n24_shape} / {scanned}")
    print(f"  DEFAULT 质量下抗锯齿像素 : {aa_total}")
    if fails:
        print(f"  [FAIL] {len(fails)} 个码位不一致: {', '.join(fails[:10])}"
              + (" ..." if len(fails) > 10 else ""))
        bad += len(fails)
    else:
        print("  [OK  ] 全字符集逐格一致")

    print()
    print("=" * 72)
    print(f"复核结论: {'全部通过' if bad == 0 else f'{bad} 项不一致'}")
    print("=" * 72)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
