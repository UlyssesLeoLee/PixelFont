# 08. 字体制作详细设计书

> PixelFont 规格文档集 · 第 8 份 · 仓库 `E:\PixelFont`（GitHub https://github.com/UlyssesLeoLee/PixelFont ，PUBLIC）· 分支 `dev`（集成分支）/ `main`（发布镜像，两者零分叉，`--ff-only` 快进）· 核实基准 HEAD `4300fc1`
>
> 事实来源：`tools/fontgen/` 源码（2026-10-24 从源码核实）、`docs/word-compat.md`、`docs/reference-fonts.md`、统一事实底稿 v2。

---

## 结论先行

这套构建管线是一台**单进程、纯脚本、无外部设计工具**的点阵字体编译器：它把 `tools/fontgen/` 里 30 余个 Python 模块串成一条从「码位集合」到「可安装 TTF」的确定性流水线，中间的每一层产物（点阵 → BDF → 图集 → TTF）都被回读校验，**没有任何一步依赖「人眼看着差不多」**。

从字符集到 TTF 共 8 段：`charset.build_charset()`（4,164 条源列表去重为 **4,161** 码位）→ `charset.load_ideo_route()`（汉字路由名单 `ideo_route.json`，**3,010** 条记录）→ `bitfont.ScriptStack`（按 SimHei / MS Gothic / vendor Fusion Pixel 三源逐码位栅格化出 12×13 点阵）→ `build_font.collect_glyphs()`（收集为 `list[GlyphData]`）→ `write_bdf()` / `write_atlas()` / `write_specimen()` / `write_ttf()`（并行产出 4 类产物）→ `verify_bdf()` / `verify_atlas()` / `verify_ttf()` / `verify_ttf_metadata()` 回读校验 → `regress.py` 全量回归（4,161 字分 **43** 批逐像素比对）→ `verify_gdi.py` Windows GDI 兼容性门禁。产出物 `dist/PixelFontPC98-12.ttf` 为 **973,712** 字节，sha256 `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1`。

真正决定成败的**不是**码位数量，而是三个数学硬约束，它们全部踩过坑、且坑的共同特征是「字体照样能打开、照样能显示」：

1. **em 方框按字宽 12 取，不是 cell 高 13。** UPM = **768**、1 像素 = **64** 单位（768 / 12 = 64）。若按 13 除，12ppem 下缩放比变成 12/13，每像素落在 **0.923** 个设备像素上，整副字糊掉——而这种糊在「字体能装上、能预览」时完全看不出来。
2. **hmtx 的 lsb 必须等于 glyf 的 xMin（墨迹左边缘）。** `lsb = (min(xs) if xs else 0) * px`。一律填 0 会让墨迹不从 x=0 开始的窄字形（`!` `'` `(` `)` `,`）被渲染器整体左移 1–3 像素；汉字几乎占满宽度，这个问题在汉字上看不出来。
3. **UPM 必须被 cell 宽整除。** `cell_w = max(g.width for g in glyphs)`，`if UPM % cell_w: raise SystemExit(...)`。否则像素整体错位。

第四条是元数据层的硬约束（2026-10-24 修复，commit `cef4a22`）：`ulCodePageRange1 = (1<<0)|(1<<17)|(1<<18)`（1252 + 932 + 936）、`fsSelection = 0x0040`（REGULAR）、`gasp = {0xFFFF: 0}`，`ulUnicodeRange1–4` **不手写**、交由 fontTools 按 cmap 重算——这是「Word 里装了却用不上」的根因修复。

轮廓规则本身只有一条主线：**每个像素 → 一个矩形轮廓**（TrueType 坐标系 y 向上，所有矩形同向绕向，靠 non-zero 环绕规则填充），**竖向相邻、x 范围相同的水平游程合并为一个矩形**（v1.0.0 起）。合并后轮廓数 **107,209 → 73,933**（-31%），TTF **1,364,528 → 973,712 字节**（-28.6%），整数倍精确性不变（**12,483 / 12,483**）。动机是：非整数缩放下每个矩形**独立**吸附到输出网格，1.5px 的方块有的落进 1 格、有的整个落空，笔画断成虚线。

**一句话结论**：本管线的正确性来自「机械推导 + 逐像素回读 + 三重硬约束」，而不是来自人工调字；任何人改动 `build_font.py` 的度量或轮廓逻辑后，必须重跑 `verify_all.py` 的 8 步门禁才能声称有效。

---

## 1. 范围与目的

### 1.1 目的

| 项 | 说明 |
|---|---|
| 文档目的 | 规定 PixelFont 家族（当前 `PixelFont PC98 12`）**从码位集合到可安装 TTF** 的完整制作规格：Glyph 命名、轮廓生成规则、构建流程、字体格式（TrueType 表级）、工具链与陷阱 |
| 回答的问题 | ① 一个像素格如何变成一个轮廓矩形？② 命名规则在 TTF / BDF / `.bdf.map` 三处如何保持一致？③ 构建链路有哪些阶段、每阶段门禁是什么？④ 最终 TTF 里有哪些表、各表写什么值？⑤ 哪些实现细节是「错了也看不出来」的雷区？ |
| 规格地位 | 本文档是**实现规格**（what/how），不是需求规格（why）；字符集范围与质量门禁策略分别见 03 / 09 文档 |
| 版本基线 | v1.0.0 已发布（注解 tag 在 `main`，GitHub Release 正式版 `draft=false`，5 个附件）；本规格描述的代码状态对应 HEAD `4300fc1` |

### 1.2 适用范围

| 适用 | 不适用 |
|---|---|
| `tools/fontgen/` 全链路（构建 + 回读 + 回归 + 对抗审核 + GDI 门禁） | 多语言家族 `PixelFont Multi 12`（**尚未开工**，已拍板方向见 §5） |
| 单字重 Regular、等宽 12px、PC-98 风格网格（12×13） | Bold / Italic / 可变字体轴（**不存在**） |
| 当前家族 4,161 码位（ASCII 95 + 符号 56 + 假名 255 + 汉字 3,755） | kerning、连字、GSUB / GPOS / locl 等 OpenType 特性（除 `gasp` 外**无**） |
| Windows GDI（Word 渲染路径）与 FreeType（Pillow / Chrome / Linux）两条栅格化路径 | Arabic / Hebrew / Devanagari / Thai 的 12px 点阵（**无 12px 源**） |

### 1.3 读者

| 角色 | 关心什么 |
|---|---|
| 字体/图形工程师 | §2.2 命名、§2.3 轮廓规则、§2.4 度量、§2.6 表清单 |
| 构建管线维护者 | §2.1 模块职责、§2.5 构建流程、§2.8 陷阱、§2.9 可复现性 |
| QA / 验收人 | §3 验收判据、§4 复现命令 |
| 文档与发布负责人 | §5 已知边界与待办、`dist/` 不入库的授权影响 |

### 1.4 术语

| 术语 | 定义（本项目取值） |
|---|---|
| UPM | unitsPerEm，**768**；1 像素 = **64** 单位 |
| cell | 设计网格 **12 × 13** 像素（宽 × 高），12px 等宽 |
| px | `px = UPM // cell_w` = **64**（单位/像素） |
| ascent / descent | **11 / 2**；基线在第 11 行下方，cell 第 12 行 |
| advance | 半角 **6**，全角 **12**（像素） |
| lsb | left side bearing，= glyf 的 xMin（墨迹左边缘）× px |
| xMin | glyf 中所有轮廓点的最小 x（字形单位） |
| ideo route | 汉字路由名单，记录每个汉字从哪个源字体取形；`ideo_route.json` 共 **3,010** 条 |
| ScriptStack | `bitfont.ScriptStack`，按优先级尝试多个源字体取形的栈，支持 `overrides` 通道 |
| FT_LOAD_TARGET_MONO | FreeType 单色（1-bit）栅格化目标，等同 GDI 1-bit 文字 |
| EBDT / EBLC | 内嵌位图表与位图位置表；GDI **会**采用，但只在请求字号 ppem 与 strike 精确相等时 |
| BDF | Adobe Bitmap Distribution Format，本项目的中间产物与可交付格式 |

---

## 2. 正文

### 2.1 目录结构与模块职责

**主链路模块**（`tools/fontgen/`，字节 / 行数为 2026-10-24 源码实测）：

| 文件 | 字节 | 行数 | 职责 |
|---|---|---|---|
| `build_font.py` | 32,823 | 670 | 构建主程序：字符集 → 字形采集 → BDF / 图集 / 样张 / TTF 产出 → 回读校验 |
| `charset.py` | 21,558 | 398 | 字符集定义与门禁（`build_charset()` / `gate_full_coverage()` / `gate_ideo_route()` / `load_ideo_route()`） |
| `bitfont.py` | 16,367 | 349 | 点阵栅格化核心（`BitmapFont` / `ScriptStack` / `count_holes()` / `count_runs()` / `ink_ratio()`） |
| `verify_gdi.py` | 19,945 | 454 | Windows GDI 兼容性门禁（全字符集逐格栅格化比对） |
| `verify_all.py` | 8,142 | 196 | 8 步全链路验收 |
| `adversarial_review.py` | 73,086 | 1,586 | 三轮对抗式审核（身份反查 / 部件级结构 / 链条） |
| `regress.py` | 46,882 | 1,034 | 全量回归：产物与源位图逐像素比对 |
| `derive_ideo_route.py` | 26,587 | 562 | 推导汉字路由名单 |
| `compare_refs.py` | 26,248 | 539 | 与独立参考集（Zpix / Unifont）比对字形身份 |
| `route_rule.py` | 8,525 | 149 | 路由规则判定（`sig_of()` 签名） |
| `vendor_fusion_pixel.py` | 6,452 | 143 | 裁剪并验证生产源 Fusion Pixel |
| `ideo_route.json` | 1,450,372 | — | 入库的汉字路由名单（**3,010** 条路由记录） |

**辅助脚本**（同目录）：

| 脚本 | 职责 |
|---|---|
| `coverage.py` | `cmap_for` 覆盖率计算 |
| `fetch_ref_fonts.py` | 抓取 / 校验参考字体（`--verify` 只校验不重下） |
| `verify_identity.py` | 字形身份校验 |
| `verify_products.py` | 产物校验 |
| `verify_bitmap.py` | 位图校验 |
| `regress_all.py` | 全量回归入口 |
| `sheet.py` / `gen_sheets.py` / `gen_glyphcmp_sheets.py` | 样张与字形对比图生成 |
| `make_demo.py` | 演示用产物生成 |
| `explain_route.py` | 路由名单可读化输出 |
| `calibrate_detector.py` | 检测阈值按对照集标定 |
| `aggregate_glyphcmp_review.py` / `apply_review_fixes.py` / `account_fixes.py` | 对比结果汇总、复核修正落地与记账 |

### 2.2 字形命名规范

| 产物 | 命名格式 | 示例 | 说明 |
|---|---|---|---|
| TTF 字形名 | **构建期内存键名** `u{cp:04X}`（四位十六进制大写）；**文件里不落盘** | 构建期 `中` = `u4E2D`；重新打开后显示为 `uni4E2D` | `fb.setupPost(keepGlyphNames=False)` → `post` 表 **format 3.0**，**不保存字形名**。fontTools 重新打开时按 cmap 反推：有 AGL 名的用 AGL 名（`ellipsis` / `multiply` / `divide`），其余用 `uniXXXX`（实测 4,047 个）。**别拿 `ttx` 里看到的名字去核对 `uXXXX` 规则** —— 文件里根本没有那个名字 |
| TTF `.notdef` | `.notdef` | — | **独立于命名序列**，位于 glyph order **首位**；不占用 `uXXXX` 命名空间 |
| BDF 字形块 | `STARTCHAR uni{cp:04X}` + `ENCODING {cp}` | `STARTCHAR uni4E2D` / `ENCODING 20013` | `ENCODING` 写**十进制**码位 |
| `.bdf.map` 条目 | `STARTCHAR uni{cp:04X}` + `ENCODING {cp}` + `ENDCHAR` | `STARTCHAR uni4E2D` / `ENCODING 20013` / `ENDCHAR` | 与 BDF 块保持同一命名，便于机器双向索引 |
| BDF 宽度行 | `SWIDTH {round(1000 * advance / 12)} 0` / `DWIDTH {advance} 0` | `SWIDTH 500 0` / `DWIDTH 6 0`（半角） | SWIDTH 为 1000 单位制缩放值，DWIDTH 为像素 advance |

`.notdef` 的**画法**是硬规定：必须画成**空心方框**（双层矩形环），上沿到基线上方 `ascent` 处、下沿伸到基线下方 `descent` 处 —— **不从 y=0 起画**，否则缺字框比真实字面高一截，排版时明显错位。

### 2.3 轮廓生成规则

| 规则 | 取值 | 依据 | 后果 |
|---|---|---|---|
| 像素 → 矩形 | 每个**实心像素**生成 1 个矩形轮廓 | `build_font.py::_emit_rect()`；TrueType 坐标系 y 向上 | 轮廓数与像素数同阶，初始 107,209 |
| 矩形坐标换算 | `x0/x1/y0/y1` 均为像素边界，乘以 `px` = **64** 换成字形单位 | `px = UPM // cell_w` | 像素边界对齐，不产生半像素 |
| 竖向游程合并 | 竖向相邻、x 范围**相同**的水平游程**合并成一个矩形**（像素并集不变） | v1.0.0 起，`_merge_vertical_runs()` | 轮廓 107,209 → **73,933**（-31%）；TTF 1,364,528 → **973,712** 字节（-28.6%）；整数倍精确性不变（**12,483 / 12,483**） |
| 合并的动机 | 非整数缩放下每个矩形**独立**吸附到输出网格，1.5px 的方块有的落进 1 格、有的整个落空 | 合并前后对比图 `说明-轮廓合并前后对比.png`（16,440 字节） | 不合并则笔画断成虚线 |
| 绕向规则 | 所有矩形**同向绕向**，靠 TrueType **non-zero 环绕规则**填充 | `_emit_rect()` 统一输出顺序 | 相邻/重叠矩形不会互相挖洞，填充结果 = 像素并集 |
| 水平游程统计 | 逐行扫描 `g.rows` 求水平游程 `runs` | `build_font.collect_glyphs()` / `bitfont.count_runs()` | 合并前的切分依据 |
| 绘制顺序 | 水平游程 → `_merge_vertical_runs(runs)` → `_emit_rect(...)` → `TTGlyphPen(None)` | `write_ttf()` | 保证同一输入逐次生成同一份二进制 |
| 栅格化目标 | **FreeType MONO**（`FT_LOAD_TARGET_MONO`），输出 0/255 单色 L 图 | Pillow 默认灰度抗锯齿再二值化会得到「缩小的矢量字体」而不是点阵 | 必须显式指定 MONO，否则点阵退化为矢量观感 |
| 精确还原字号 | **12 的整数倍字号**才能逐格还原设计：12ppem(=9pt)、24ppem(=18pt)、36ppem(=27pt) @96dpi | `docs/word-compat.md` §7.6 | 非整数倍（如 18ppem = 1.5 倍）笔画断裂 + 墨迹量偏细 **43%** |
| 缺口形状 | `.notdef` = 空心方框（双层矩形环），上沿到 ascent、下沿到 descent | §2.2 | 从 y=0 起画会让缺字框比真实字面高一截 |

### 2.4 度量与 hmtx 规则

| 字段 / 规则 | 值 | 理由 |
|---|---|---|
| `cell_w` | `cell_w = max(g.width for g in glyphs)` | 取实际最大字宽作为 em 除数基准 |
| UPM 整除校验 | `if UPM % cell_w: raise SystemExit(...)` | UPM = **768** 必须被 cell 宽整除，否则像素整体错位；**硬失败**而非警告 |
| 像素单位 | `px = UPM // cell_w` = **64** | 768 / 12 = 64 |
| em 除数 | **12（字宽）**，不是 13（cell 高） | 按 13 除会让 12ppem 下缩放比变成 12/13，每像素落在 **0.923** 个设备像素上，整副字糊掉；这种糊在「字体能打开」时完全看不出来 |
| `hhea` / `OS/2` 垂直度量 | `setupHorizontalHeader(ascent=a, descent=-d, lineGap=0)`，`a = ascent * px` = **704**，`d = descent * px` = **128** | ascent 11 / descent 2 |
| `hmtx` lsb | **lsb 必须等于 glyf 的 xMin**：`lsb = (min(xs) if xs else 0) * px` | 一律填 0 会让墨迹不从 x=0 开始的窄字形（`!` `'` `(` `)` `,`）被渲染器整体左移 1–3 像素；汉字几乎占满宽度，这个问题在汉字上看不出来 |
| `hmtx` advance | 半角 **6**、全角 **12**（像素） | 与字符集分类对应 |
| `sTypoAscender` / `sTypoDescender` / `sTypoLineGap` | `a` / `-d` / `0` | 与 hhea 一致 |
| `usWinAscent` / `usWinDescent` | `a` / `d` | Windows 行高裁剪 |
| `sxHeight` / `sCapHeight` | `6*px` = **384** / `8*px` = **512** | 小写 x 高 / 大写首字母高 |
| `usWeightClass` / `usWidthClass` | **400** / **5**（固定宽度） | 单字重 Regular、等宽 |
| `fsType` | **0**（可自由安装） | 成品需被普通用户安装 |
| `fsSelection` | **0x0040**（REGULAR） | 缺 REGULAR 时 Windows 可能不把它当正文常规字（`cef4a22` 修复项） |
| `achVendID` | **`PXLF`** | 厂商标识 |
| `ulCodePageRange1` | `(1<<0) \| (1<<17) \| (1<<18)` = 1252 + 932 + 936 | 覆盖 Latin-1 / Shift-JIS / GB2312 三套代码页；旧值 `0x00030000` 实为 bit16(874 泰语)+bit17(932)，**既无 1252 也无 936** |
| `gasp` | `{0xFFFF: 0}` | 像素字不该请求灰度抗锯齿或网格拟合 |
| `ulUnicodeRange1–4` | **不手写**，由 fontTools 按 cmap 实际覆盖重算 | 手写查表会再次出错（`cef4a22`） |

### 2.5 构建流程

| 阶段 | 输入 | 处理 | 输出 | 门禁 |
|---|---|---|---|---|
| 1 字符集构建 | `ascii_chars()` 95 + `extras()` 56 + `kana_chars()` **258** + `gb2312_level1()` 3,755（源列表合计 **4,164**） | `charset.build_charset()` 去重（重复 3 个：`ヶ` U+30F6、`ー` U+30FC、`～` U+FF5E） | **4,161** 码位集合 | `gate_full_coverage()`：缺字门禁 |
| 2 路由名单 | `ideo_route.json`（**3,010** 条记录） | `charset.load_ideo_route()` 载入；`derive_ideo_route.py` / `route_rule.py::sig_of()` 推导 | 汉字→源字体映射 | `gate_ideo_route()`：路由名单门禁；名单自检（按名单自述输入重新推导并比对） |
| 3 字形采集 | SimHei（汉字）/ MS Gothic（拉丁·假名）/ vendor Fusion Pixel 12px（第三源） | `bitfont.ScriptStack` 按优先级取形，`overrides` 通道处理源字体语系惯例（如 `U+005C` 在 MS Gothic 按 JIS 惯例画成 `¥`）；栅格化为 12×13 `BitmapFont` | `BitmapFont` 集合 | 源自检：Fusion 裁剪版与原字体逐像素一致 + cmap 覆盖相符（`vendor_fusion_pixel.py --check`） |
| 4 BDF 写出 | `BitmapFont` 集合 | `write_bdf()`：写 `STARTCHAR` / `ENCODING` / `SWIDTH` / `DWIDTH` / `BBX` / `BITON` | `dist/PixelFontPC98-12.bdf`（**665,950** 字节）、`dist/PixelFontPC98-12.bdf.map`（**183,034** 字节） | `verify_bdf()` 回读校验 |
| 5 图集 / 样张 | `BitmapFont` 集合 | `write_atlas()` / `write_specimen()` | `dist/PixelFontPC98-12-atlas.png`（**141,857**）、`-specimen.png`（**2,977**）、`-atlas.json`（**87,300**） | `verify_atlas()` 回读校验 |
| 6 TTF 写出 | `BitmapFont` 集合 | `write_ttf()`：水平游程 → `_merge_vertical_runs()` → `_emit_rect()` → `TTGlyphPen(None)` → `FontBuilder` 装配 | `dist/PixelFontPC98-12.ttf`（**973,712** 字节，sha256 `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1`） | `verify_ttf()` 回读校验 + `verify_ttf_metadata()` 四组不变量（代码页位 / fsSelection / Unicode 区段位与 cmap 一致 / gasp 禁 DOGRAY\|GRIDFIT） |
| 7 全量回归 | 产物 vs 源位图 | `regress.py` / `regress_all.py`：**4,161** 字分 **43** 批逐像素比对 | 回归报告 | 0 error 0 warn |
| 8 Windows 兼容性 | TTF + 系统 GDI | `verify_gdi.py`：24bpp DIB 画布，12/24ppem 全字符集栅格化逐像素一致 | `reports/gdi_compat.json`（摘要 1.5KB）+ `reports/gdi_raster_scan.tsv`（逐码位 **4,162** 行） | GDI 字体选择 + 全字符集逐格一致，抗锯齿像素 **0** |

**fontTools 装配顺序**（`write_ttf()`）：`FontBuilder(UPM, isTTF=True)` → `setupGlyphOrder` → `setupCharacterMap` → `setupGlyf` → `setupHorizontalMetrics` → `setupHorizontalHeader` → `setupOS2` → `setupName` 等。`setupCharacterMap` 依赖 cmap 覆盖，故 `ulUnicodeRange` 交由 fontTools 重算而非手写。

### 2.6 输出字体格式与表清单

| 表 | 内容 | 备注 |
|---|---|---|
| `glyf` | 每个字形的轮廓矩形集合（TrueType 坐标系 y 向上，同向绕向） | 合并竖向游程后的结果；整体 **73,933** 个轮廓 |
| `loca` | 字形偏移表 | 由 fontTools 依据 `glyf` 自动生成 |
| `cmap` | 码位 → 字形映射，覆盖 **4,161** 码位 | `coverage.py::cmap_for` 负责覆盖统计 |
| `head` | `unitsPerEm = 768`、`indexToLocFormat`、字体创建/修改时间 | `UPM` 必须被 cell 宽整除 |
| `hhea` | `ascent = 704`、`descent = -128`、`lineGap = 0`、advanceWidthMax | `setupHorizontalHeader(ascent=a, descent=-d, lineGap=0)` |
| `hmtx` | 每字形的 advance + **lsb = xMin × px** | lsb 错值 → 窄字形整体左移 1–3 像素 |
| `maxp` | 字形数、轮廓数、最大点数等 | fontTools 自动计算 |
| `name` | 家族名 `PixelFont PC98 12`（name ID 1 / 16）、PostScript 名 `PixelFontPC98-12` | 多语言版为**独立家族** `PixelFont Multi 12`，不改现有家族 |
| `OS/2` | 见 §2.4 全部字段 | `cef4a22` 修复后为「Word 里用得上」的取值 |
| `post` | 格式版本等 | 无 kerning 数据 |
| `gasp` | `{0xFFFF: 0}` | 禁 DOGRAY / GRIDFIT |

**非 TTF 产物**：BDF（`STARTCHAR`/`ENCODING`/`SWIDTH`/`DWIDTH`/`BBX`/`BITON`）+ `.bdf.map`（同名条目 + `ENDCHAR`）、PNG 图集与样张、PNG 样张对应的 `atlas.json`、以及打包 zip `dist/PixelFontPC98-12-2026-10-24.zip`（**533,116** 字节，sha256 `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8`，内含 **9** 项）。

### 2.7 工具链与依赖

| 组件 | 版本 | 用途 |
|---|---|---|
| Python | 3 | 全部构建与门禁脚本 |
| fontTools | **4.62.1** | `fontTools.fontBuilder.FontBuilder`、`fontTools.pens.ttGlyphPen.TTGlyphPen`、`fontTools.ttLib.tables._g_a_s_p` |
| Pillow | 仓库环境版本（**待验证**，验证方法：`python -c "import PIL; print(PIL.__version__)"`） | FreeType 绑定，栅格化走 `FT_LOAD_TARGET_MONO`，输出 0/255 单色 L 图 |
| numpy | 仓库环境版本（**待验证**，验证方法：`python -c "import numpy; print(numpy.__version__)"`） | 位图布尔化与统计 |
| Windows GDI32 | 随系统 | `verify_gdi.py` 的 24bpp DIB 画布；仅 Windows 可跑 |

### 2.8 已知实现陷阱

| 编号 | 陷阱 | 后果 | 规避手段 |
|---|---|---|---|
| T-01 | **em 除数取 12（字宽）而非 13（cell 高）** | 12ppem 下缩放比变成 12/13，每像素落在 0.923 个设备像素上，整副字糊掉；**字体能打开、格式合法**，只有逐像素比对才暴露 | `px = UPM // cell_w` 且 `cell_w` 取字宽；回归与 GDI 门禁逐像素比对 |
| T-02 | **hmtx 的 lsb 必须等于 glyf 的 xMin** | 一律填 0 → 墨迹不从 x=0 开始的窄字形（`!` `'` `(` `)` `,`）被渲染器整体左移 1–3 像素；汉字几乎占满宽度故在汉字上看不出来 | `lsb = (min(xs) if xs else 0) * px`，与 `glyf` 同步计算 |
| T-03 | **UPM 必须被 cell 宽整除** | 像素整体错位，且错位量随字号放大 | `if UPM % cell_w: raise SystemExit(...)` 硬失败，不允许降级为警告 |
| T-04 | **`fontTools.subset --unicodes` 收十六进制码位** | 写成 `U+4E01` 会被**静默忽略一部分**（子集缺字，无报错） | 传 `4E01` 形式；子集结果必须与 cmap 覆盖数逐项核对 |
| T-05 | **`eblc.strikes` 是 list 不是 dict** | 按 dict 访问即抛异常或误判 strike 命中 | 用列表下标遍历；GDI 内嵌位图命中判断必须比较**请求 ppem == strike ppem** 精确相等 |
| T-06 | **`table_E_B_D_T_` 不是 dict** | 访问内嵌位图表内容时按 dict 处理会失败 | 走 fontTools 的 `EBDT` 表接口逐表读取 |
| T-07 | **哈希比对必须统一小写** | sha256 十六进制大小写不一致导致「同一产物」被判为不同 | 比对前统一 `.lower()`；清单 `SHA256SUMS.txt` 与实测值同格式 |
| T-08 | `ulCodePageRange1` 手写查表出错（历史值 `0x00030000` = 874 + 932） | 缺 1252 / 936 → Word 装了却用不上 | 固定写 `(1<<0)\|(1<<17)\|(1<<18)`，并由 `verify_ttf_metadata()` 硬拦 |
| T-09 | `fsSelection` 缺 REGULAR（历史值 `0x0000`） | Windows 可能不把它当正文常规字 | 固定 `0x0040`，`verify_ttf_metadata()` 硬拦 |
| T-10 | 手写 `ulUnicodeRange1–4` | 与 cmap 实际覆盖不一致 | 不手写，交给 fontTools 按 cmap 重算 |
| T-11 | `gasp` 请求灰度抗锯齿 / 网格拟合 | 点阵字被当矢量处理，出现抗锯齿边缘 | `gasp = {0xFFFF: 0}`，门禁禁 DOGRAY\|GRIDFIT |
| T-12 | Pillow 默认灰度抗锯齿再二值化 | 得到「缩小的矢量字体」而非点阵 | 显式 `FT_LOAD_TARGET_MONO` |
| T-13 | `.notdef` 从 y=0 起画 | 缺字框比真实字面高一截，排版明显错位 | 空心方框上沿到 ascent、下沿到 descent |
| T-14 | MS Gothic 按 JIS 惯例把 `U+005C` 画成 `¥` | `U+005C` 与 `U+00A5` 整格逐字节相同 | `charset.SOURCE_OVERRIDES` 把 `U+005C` 切到 Fusion Pixel |
| T-15 | 以 Ark Pixel 作为「独立票」 | Ark 引入生产源后其票变为自证 | 目视复核参考列改为 **Zpix + Unifont**（Unifont 16px 不参与笔画数比对） |

### 2.9 可复现性要求

| 要求 | 依据 |
|---|---|
| `dist/` **不入库** | 仓库政策；成品字形派生自 SimHei / MS Gothic（微软专有） |
| `vendor/` **入库** | Fusion Pixel 12px 简体裁剪版（**764,748** 字节，sha256 `FC910F23FF8EE2DF8F2FEC6F91381A60DF812E3A16CE177F48528F1DB6551A37`）参与构建，必须随仓可取；`vendor/fusion-pixel-12px/LICENSES/` 下三份许可（ark-pixel-OFL / cubic-11-OFL / galmuri-LICENSE）随附 |
| `third_party/` **不入库** | 参考字体只用于校验，不参与构建 |
| 参考字体只记来源与 sha256 | 来源、版本、sha256 清单见 `docs/reference-fonts.md`；抓取脚本 `tools/fontgen/fetch_ref_fonts.py`（`--verify` 只校验不重下） |
| `tools/fontgen/` 代码许可 | 仓库 `LICENSE` = **GNU AGPL-3.0**（覆盖 `tools/fontgen/` 代码） |
| 构建确定性 | 同一输入逐次生成同一份二进制：游程切分 → 合并 → `_emit_rect()` → `TTGlyphPen` 顺序固定，无时间戳依赖写入轮廓；`head` 的时间戳不影响 `glyf` 内容 |
| 发布包完整性 | 发布 zip 内含 `SHA256SUMS.txt`（**744** 字节），9 项附件逐一登记 |
| 分支策略 | `dev` = 集成分支，`main` = 发布镜像；两者**零分叉**，`--ff-only` 快进 |

---

## 3. 验收判据

| 编号 | 构建规则 | 判据（可量化） | 验证方式 |
|---|---|---|---|
| AC-01 | 字符集机械推导 | 源列表合计 **4,164** → 去重 **4,161** 码位；重复仅 3 个（`ヶ` `ー` `～`）；汉字 **3,755** 来自 GB2312 一级（`0xB0A1`–`0xD7F9`） | `python tools/fontgen/verify_all.py`（步 2 缺字门禁） |
| AC-02 | 显式排除古旧假名合字 | `U+3097` `U+3098` 不在字符集内 | `charset.EXCLUDE` 断言 |
| AC-03 | UPM 整除 | `768 % cell_w == 0`，否则构建 **SystemExit** 非零退出 | `python tools/fontgen/build_font.py`（应成功退出 0） |
| AC-04 | 像素单位换算 | `px == 64`（= 768 / 12） | 构建日志 / `build_font.py` 常量核对 |
| AC-05 | 竖向游程合并 | 轮廓数 **73,933**；TTF **973,712** 字节；整数倍精确性 **12,483 / 12,483** | `python tools/fontgen/verify_all.py`（步 3 全量回归） |
| AC-06 | hmtx lsb = xMin | 每个字形 `hmtx.lsb == glyf.xMin`（含 `!` `'` `(` `)` `,` 等窄字形） | `verify_ttf()` 回读 + 逐像素回归无左移 |
| AC-07 | OS/2 不变量 | `ulCodePageRange1 == (1<<0)\|(1<<17)\|(1<<18)`；`fsSelection == 0x0040`；`ulUnicodeRange1–4` 与 cmap 覆盖一致；`gasp` 禁 DOGRAY\|GRIDFIT | `verify_ttf_metadata()`（4 组全过） |
| AC-08 | 全量回归一致 | **4,161** 字分 **43** 批，产物与源位图逐像素一致，**0 error 0 warn** | `python tools/fontgen/regress.py` / `verify_all.py` 步 3 |
| AC-09 | Windows GDI 兼容 | 12ppem 与 24ppem 下 **4161/4161** 逐格一致，抗锯齿像素 **0** | `python tools/fontgen/verify_gdi.py`（约 9 秒） |
| AC-10 | 全链路 8 步 | **8/8 PASS** | `python tools/fontgen/verify_all.py`（约 6 分钟） |
| AC-11 | 字形硬检查 | 参考集 Zpix + Unifont 命中 **71**（warn **69** / error **2**，均为参考集分歧） | `verify_all.py` 步 4 |
| AC-12 | 对抗式审核 | 三轮命中 **60 / 139 / 19**，待裁决 **0**，已裁决非缺陷 **169**，确认缺陷 **0** | `python tools/fontgen/adversarial_review.py`（`verify_all.py` 步 7） |
| AC-13 | 产物与源同步 | 独立读 `dist/` 与当前源逐字比对一致（**不靠构建脚本自证**） | `verify_all.py` 步 5 |
| AC-14 | 路由名单自检 | 按名单自述输入重新推导的结果与入库 `ideo_route.json`（**3,010** 条）一致 | `verify_all.py` 步 6 |
| AC-15 | 生产源自检 | Fusion 裁剪版与原字体逐像素一致，且裁剪版 cmap == 原字体 cmap ∩ 本项目字符集 | `python tools/fontgen/vendor_fusion_pixel.py --check` |
| AC-16 | 参考字体可复现 | `fetch_ref_fonts.py --verify` 通过；来源/版本/sha256 与 `docs/reference-fonts.md` 一致 | `python tools/fontgen/fetch_ref_fonts.py --verify` |
| AC-17 | 发布包一致性 | zip **533,116** 字节，sha256 `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8`，内含 **9** 项 | `Get-FileHash dist/PixelFontPC98-12-2026-10-24.zip -Algorithm SHA256` |
| AC-18 | 渲染路径一致性 | FreeType 24px+ 偏差 **0**；12px 平均偏差 **19.00 px/字**（最坏 44）—— **已知偏差，非门禁项**，用于解释非整数倍字号的还原差异 | `docs/word-compat.md` §7.2 / §7.5 记录 |

---

## 4. 复现命令

```powershell
# ---- 重建字体（约 1 分钟级）----
cd E:\PixelFont; python tools/fontgen/build_font.py
# 期望：构建成功退出码 0；产出 dist/PixelFontPC98-12.ttf 等 5 类产物
# 期望：dist/PixelFontPC98-12.ttf = 973,712 字节
# 期望：sha256 = 3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1

# ---- 全链路 8 步验收（约 6 分钟）----
cd E:\PixelFont; python tools/fontgen/verify_all.py
# 期望：8/8 PASS；回归 0 error 0 warn；硬检查命中 71（warn 69 / error 2）
# 期望：对抗审核三轮 60/139/19，待裁决 0，已裁决非缺陷 169，确认缺陷 0

# ---- Windows 兼容门禁（全字符集，约 9 秒）----
cd E:\PixelFont; python tools/fontgen/verify_gdi.py
# 期望：12ppem 与 24ppem 下 4161/4161 逐格一致，抗锯齿像素 0
# 产出：reports/gdi_compat.json（1.5KB）、reports/gdi_raster_scan.tsv（4,162 行）

# ---- 抓参考字体 / 只校验 ----
python tools/fontgen/fetch_ref_fonts.py
python tools/fontgen/fetch_ref_fonts.py --verify
# 期望：--verify 全部通过，sha256 与 docs/reference-fonts.md 一致

# ---- 裁剪生产源 / 只验证 ----
python tools/fontgen/vendor_fusion_pixel.py
python tools/fontgen/vendor_fusion_pixel.py --check
# 期望：裁剪前后逐像素一致；裁剪版 cmap == 原字体 cmap ∩ 本项目字符集
```

```bash
# bash / Linux 等价形式（注意：GDI 门禁仅 Windows 可跑）
cd /e/PixelFont && python tools/fontgen/build_font.py
cd /e/PixelFont && python tools/fontgen/verify_all.py
cd /e/PixelFont && python tools/fontgen/verify_gdi.py   # 仅 Windows
```

```powershell
# ---- 产物哈希核对 ----
Get-FileHash E:\PixelFont\dist\PixelFontPC98-12.ttf -Algorithm SHA256
# 期望：3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1

Get-FileHash E:\PixelFont\dist\PixelFontPC98-12-2026-10-24.zip -Algorithm SHA256
# 期望：96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8
```

---

## 5. 已知边界与待办

| 编号 | 事项 | 状态 | 下一步 |
|---|---|---|---|
| B-01 | Arabic / Hebrew / Devanagari / Thai 无 12px 点阵源 | 已知边界（不可解） | 仅 Unifont 16（16×16 网格）可用，塞不进 12px 格；本家族不覆盖 |
| B-02 | 单字重 Regular | 已知边界 | 无 Bold / Italic / 可变字体轴 |
| B-03 | 无 kerning / 连字 / OpenType 特性（除 `gasp`） | 已知边界 | 等宽 12px 场景下优先级低 |
| B-04 | 非 12 整数倍字号不精确 | 已知边界 | 18ppem 笔画断裂 + 墨迹量偏细 **43%**；文档化引导用户用 12/24/36ppem |
| B-05 | FreeType 12px 与设计稿有偏差 | 已知边界 | 平均 **19.00 px/字**（最坏 44），24px+ 偏差 0；GDI 路径逐格一致 |
| B-06 | 本机已安装 10-23 旧版（1,362,480 字节，sha256 `FCC65BCBCD8A1A022007065E3444464916EDB537BB172B6F2ACDC9596DE3303B`） | **未覆盖** | 需在 Windows 上覆盖安装 v1.0.0 并复跑 `verify_gdi.py` |
| B-07 | zip 内 `SHA256SUMS.txt` 未收录 bdf / atlas / specimen / 说明文 / word-compat 的 sha256 | **待补** | 验证方法：解压后逐文件 `Get-FileHash` 与 `SHA256SUMS.txt` 比对，补齐缺失条目 |
| B-08 | 12px 层面独立参考票只有 2 张 | 已知边界 | Ark 引入生产源后变自证；Unifont 为 16px 不参与笔画数比对 |
| B-09 | 多语言家族 `PixelFont Multi 12` | **尚未开工** | 已拍板：范围 = 方案 C（A + 全部 CJK）= **31,392** 码位；形态 = 新增独立家族；中日共享 2,078 汉字走中文形 + JIS 独有 2,297 走 ja 源；`locl` 未选。体积粗估约 **7.0 MB** |
| B-10 | 多语言版覆盖缺口 4 码位 | 待处理 | `U+20AC €`、`U+2260 ≠`、`U+2264 ≤`、`U+2265 ≥` 不被任何 Fusion 变体覆盖，需沿用非第三源路径 |
| B-11 | `dist/` 不入库 → 成品不可由仓库直接分发 | 已知边界（授权原因） | 字形派生自 SimHei / MS Gothic（微软专有）；仅 GitHub Release 5 个附件对外 |
| B-12 | Pillow / numpy 具体版本 | **待验证** | `python -c "import PIL, numpy; print(PIL.__version__, numpy.__version__)"` |
