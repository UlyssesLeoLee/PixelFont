# PixelFont 字体度量设计书

> 文档编号：SPEC-06（12 份规格文档之第 6 份）
> 适用家族：`PixelFont PC98 12`（PostScript 名 `PixelFontPC98-12`，achVendID `PXLF`）
> 事实底稿版本：统一事实底稿 v2（2026-10-24 核实）
> 仓库：`E:\PixelFont`（GitHub https://github.com/UlyssesLeoLee/PixelFont ，PUBLIC）　基线 HEAD：`4300fc1`

---

## 结论先行

PixelFont 的度量只有一个核心决定：**把 em 方框按字宽 12 像素取，而不是按 cell 高 13 像素取**。由此推导出全部其余度量——`UPM = 768`、1 像素 = 64 单位、`hhea.ascent = 704`、`hhea.descent = -128`、`hhea.lineGap = 0`、OS/2 的 `sTypo*` 与 `usWin*` 双套同值、`sxHeight = 384`、`sCapHeight = 512`、半角 advance 384 / 全角 advance 768、行高 832 单位 = 13 像素。

这一选择是**可验证的、非直觉的、且一旦选错无法从渲染结果看出来**的：若按 cell 高 13 作除数，ppem = 12 时缩放比变成 12/13，每个像素落在 0.923 个设备像素上，整副字会糊掉——而字体仍然「能打开、能显示」，缺陷不会以任何报错形式暴露。因此本设计书把度量写成**带硬门禁的规格**：`tools/fontgen/build_font.py::verify_ttf_metadata()` 硬拦四组不变量，`tools/fontgen/verify_gdi.py` 在真实 GDI 渲染路径上验证 12ppem / 24ppem 全字符集 4161/4161 逐格一致、抗锯齿像素 0。

三条工程结论：

1. **度量必须一次定死并在多语言版复用**。计划中的 `PixelFont Multi 12`（31,392 码位）必须沿用同一套 UPM / 网格 / ascent / descent / lineGap / 半角 6 · 全角 12 等宽规则，否则 12×13 网格与等宽基线被破坏。
2. **只有 12 的整数倍字号能逐格还原设计**（12ppem = 9pt、24ppem = 18pt、36ppem = 27pt @96dpi）。非整数倍（如 18ppem = 1.5 倍）笔画断裂、墨迹量偏细 43%。这不是可以靠 `gasp` 修掉的问题，而是点阵字体在任意字号下精确还原的固有限制，必须在安装说明与验收判据中显式承认。
3. **lsb 不是装饰字段**。`lsb` 必须等于 `glyf.xMin`（墨迹左边缘），一律填 0 会让 `!` `'` `(` `)` `,` 这类不从 x=0 起笔的窄字形被渲染器整体左移 1–3 像素；汉字几乎占满宽度，所以在汉字上完全看不出来。

---

## 1. 范围与目的

### 1.1 目的

本文定义 PixelFont 像素字体的**度量层规格**：坐标体系与单位、垂直度量、基线与网格对齐、水平 advance、左侧边距、行距、`.notdef` 度量，以及这些度量在多语言版上的继承规则。

本文不描述字形轮廓的像素设计（那是字形集规格）、不描述 OpenType 特性路线、不描述渲染器兼容性的全部实测细节（见 `docs/word-compat.md`）。本文的职责是给出一条**可被脚本自动验证**的度量契约——所有条目都落到 `dist/PixelFontPC98-12.ttf` 的某个具体表项上，并且能通过 `ttx` 读回或 Python 一行脚本判定。

### 1.2 适用范围

| 对象 | 是否适用 | 说明 |
|---|---|---|
| `PixelFont PC98 12`（当前家族，4,161 码位） | 适用 | 本文的规范对象 |
| `PixelFont Multi 12`（计划中，31,392 码位） | 适用（继承约束） | 独立家族，但度量必须沿用，见 §2.8 |
| 其它家族 / 其它网格尺寸 | 不适用 | 本文所有数值与 12×13 网格绑定 |
| 非 12 整数倍的字号 | 不适用「逐格还原」判据 | 见 §2.3 与 §5 已知边界 |

范围边界：本文只覆盖 **outline（`glyf`）路线**。GDI 在请求字号与 `EBDT`/`EBLC` strike 的 ppem 精确相等时会采用内嵌位图，但本字体产物不带 `EBDT`/`EBLC`，实测 GDI 走的是 `glyf` 轮廓路径（详见 `docs/word-compat.md` §7.7）。

### 1.3 读者

| 读者 | 关注本文的哪部分 |
|---|---|
| 字体构建维护者 | §2.1–§2.7 的规格表、§3 验收判据、§4 复现命令 |
| 渲染兼容性排查者 | §2.3 字号映射、§2.9 陷阱表（尤其 T-09 / T-10）、§5 |
| `PixelFont Multi 12` 实施者 | §2.8 继承约束表、§3 中 M-10 / M-11 / M-19 |
| 文档与安装说明作者 | §2.3 字号表、§5 已知边界（B-05 / B-04） |

### 1.4 术语

| 术语 | 含义 | 本项目取值 |
|---|---|---|
| UPM | units per em，`head.unitsPerEm`，em 方框边长（字体单位） | 768 |
| px | 1 设计像素等于多少字体单位，`px = UPM // cell_w` | 64 |
| cell | 字形设计格：12 像素宽 × 13 像素高 | 12 × 13 |
| em 方框 | 排版意义上的正方形边长，按**字宽 12 像素**取 | 12 像素 = 768 单位 |
| ascent | 基线以上的设计行数 | 11 像素 = 704 单位 |
| descent | 基线以下的设计行数 | 2 像素 = 128 单位 |
| baseline | 字形基线，TrueType 坐标 y = 0 | y = 0 |
| advance | 字形前进宽度（`hmtx`） | 半角 384 / 全角 768 |
| lsb | 左边距（left side bearing），`hmtx` 第二项 | `= glyf.xMin × 64` |
| lineGap | 行间额外间距（`hhea` / `OS/2.sTypoLineGap`） | 0 |
| 行高 | 一行占的总高度 | `usWinAscent + usWinDescent` = 832 单位 = 13 像素 |
| ppem | 每 em 的设备像素数 | 12 / 24 / 36 为精确值 |
| ccppem / gasp | 灰度抗锯齿 / 网格拟合控制表 | `{0xFFFF: 0}` |

---

## 2. 正文

### 2.1 坐标体系与单位

| 项 | 值 | 说明 |
|---|---|---|
| 字体单位基准 | UPM = **768** | `tools/fontgen/build_font.py` 的 `UPM` 常量 |
| 1 像素 | **64** 单位 | `px = UPM // cell_w` = 768 // 12 = 64 |
| 整除约束 | `UPM % cell_w != 0` → 构建直接 `raise SystemExit` | 提示语：「UPM 无法被 em 宽整除, 像素会错位」 |
| 轮廓坐标方向 | TrueType，**y 向上** | 基线 y = 0，正值在基线上方 |
| 位图源坐标方向 | 像素位图，**y 向下** | 第一行在顶部 |
| 换算关系 | `y_font = (cell_ascent − row) × 64` | 11 行 ascent、2 行 descent，cell 共 13 行 |
| cell 高度 | 13 像素 = **832** 单位 | 11 + 2 = 13；**不是** em 高度 |
| em 高度 | 12 像素 = **768** 单位 | 按字宽取，正方形 |
| 轮廓生成 | 每像素一个矩形（`glyf`），竖向同 x 范围游程合并 | `_emit_rect()` / `_merge_vertical_runs()` |

**关键点：cell 高 13 ≠ em 高 12。** cell 的第 13 行位于基线以下（负 y），是合法轮廓位置。em 方框只覆盖基线以上 11 行 + 基线 1 行。第 13 行（descent 区）不占 em，但计入行高。

### 2.2 垂直度量

| 字段 | 值（单位） | 值（像素） | 来源 |
|---|---|---|---|
| `head.unitsPerEm` | 768 | 12 | `build_font.py` `UPM` 常量 |
| `hhea.ascent` | **704** | 11 | `setupHorizontalHeader(ascent=a, descent=-d, lineGap=0)`，`a = ascent * px = 11 * 64` |
| `hhea.descent` | **-128** | -2 | 同上，`-d = -2 * 64` |
| `hhea.lineGap` | **0** | 0 | 同上，固定 0 |
| `OS/2.sTypoAscender` | **704** | 11 | `setupOS2(sTypoAscender=a, ...)` |
| `OS/2.sTypoDescender` | **-128** | -2 | `setupOS2(sTypoDescender=-d, ...)` |
| `OS/2.sTypoLineGap` | **0** | 0 | `setupOS2(sTypoLineGap=0, ...)` |
| `OS/2.usWinAscent` | **704** | 11 | `setupOS2(usWinAscent=a, ...)` |
| `OS/2.usWinDescent` | **128** | 2 | `setupOS2(usWinDescent=d, ...)`，OS/2 取正值 |
| `OS/2.sxHeight` | **384** | 6 | `round(6 * px)` |
| `OS/2.sCapHeight` | **512** | 8 | `round(8 * px)` |
| `OS/2.usWeightClass` | 400 | — | 单字重 Regular |
| `OS/2.usWidthClass` | 5 | — | 固定宽度（等宽） |
| `OS/2.fsSelection` | 0x0040 | — | REGULAR；旧值 0x0000 缺 REGULAR，Windows 可能不当作正文常规字（commit `cef4a22` 修复） |
| `OS/2.fsType` | 0 | — | 可安装 / 可嵌入 |
| `OS/2.achVendID` | `PXLF` | — | 厂商标识 |
| `OS/2.ulCodePageRange1` | `(1<<0) \| (1<<17) \| (1<<18)` | — | 1252 + 932 + 936 三套代码页；旧值 0x00030000 实为 bit16(874)+bit17(932)，既无 1252 也无 936 |
| `OS/2.ulUnicodeRange1`–`4` | **不手写**，由 fontTools 按 cmap 实际覆盖重算 | — | 手写查表会再次出错（commit `cef4a22`） |
| `head.yMax` | 待验证 | 待验证 | 验证方法：`ttx -t head -o - dist/PixelFontPC98-12.ttf` 读回 |
| `head.yMin` | 待验证 | 待验证 | 同上 |
| `OS/2.version` / `head.fontRevision` 等其它版本字段 | 待验证 | — | 验证方法：同上 `ttx` 导出后逐字段读回 |

**硬门禁**：`build_font.py::verify_ttf_metadata()` 对四组不变量硬拦——代码页位、`fsSelection` 含 REGULAR、Unicode 区段位与 cmap 实际覆盖一致、`gasp` 不含 DOGRAY | GRIDFIT。

### 2.3 基线与网格对齐

| 项 | 值 | 说明 |
|---|---|---|
| 基线位置 | 第 **11** 行下方 | ascent = 11 行 |
| cell 第 12 行 | 基线下一行（descent 区） | 负 y 位置，合法 |
| cell 第 13 行 | 第二个 descent 行 | 负 y 位置，合法 |
| em 方框 | 12 像素（= 768 单位） | 按**字宽**取；**不是** cell 高 13 |
| 若误按 13 取 | 缩放比 12/13 = 0.923 | 每个像素落在 0.923 个设备像素上，整副字糊掉，且「字体能打开」时完全看不出来 |
| 基线在坐标中的位置 | y = 0 | TrueType 坐标 |
| 全角字面 | 约 12 像素宽（汉字几乎占满宽度） | 所以 lsb 错误在汉字上不易察觉 |

**字号映射（@96dpi，ppem = pt × 96/72 = pt × 4/3）**

| ppem | pt | 每字设备像素 | 状态 |
|---|---|---|---|
| 12 | 9 | 12 | 逐格还原（实测） |
| 24 | 18 | 24 | 逐格还原（实测） |
| 36 | 27 | 36 | 逐格还原（实测） |
| 18 | 13.5 | 18 | 非整数倍：笔画断裂 + 墨迹量偏细 **43%** |

只有 **12 的整数倍字号**能逐格还原设计。这是点阵字体的固有限制，不是可调参数。

### 2.4 水平度量与 advance

| 项 | 值 | 说明 |
|---|---|---|
| 半角 advance | **384** 单位 = 6 像素 | `setupHorizontalMetrics` 中 `advance * px`，`advance = 6` |
| 全角 advance | **768** 单位 = 12 像素 | `advance = 12` |
| 比例 | 半角 = 全角的一半（6 : 12） | 恰好 1:2，等宽基线成立 |
| `OS/2.usWidthClass` | 5 | 固定宽度，向渲染器声明等宽 |
| ASCII 强制半角 | `latin_force_half = True` | 保证等宽网格不被源字体的 Latin advance 破坏 |
| 全角/半角判定依据 | **源字体自己的实测 advance**：`round(self._font.getlength(ch)) > half_w` 即判全角 | EAW 只作拿不到实测 advance 时的兜底 |
| 等宽硬约束 | 全部字形 advance ∈ {384, 768} | 见 §3 判据 M-19 |

**为什么不能用 EAW 判全角/半角**：`…` `×` `÷` 的 East Asian Width 是 `'A'`（ambiguous），按非 CJK 惯例算半角；但 MS Gothic 里它们本来就是 12px 全角字形。按 EAW 判半角就会把 12px 字形塞进 6px 格，**右半边整列墨迹被切掉**。

### 2.5 左侧边距（lsb）规则

| 规则 | 后果 | 依据 |
|---|---|---|
| `lsb = (min(xs) if xs else 0) * px` | lsb 与墨迹左边缘一致 | `setupHorizontalMetrics` 逐字形计算 |
| lsb **必须等于** `glyf.xMin` | 渲染器按 lsb 放置墨迹，lsb ≠ xMin 即产生位移 | 轮廓 xMin 即墨迹左边缘 |
| lsb 一律填 0（**禁止**） | 不从 x=0 起笔的窄字形被整体左移 1–3 像素 | `!` `'` `(` `)` `,` 明显；汉字占满宽度所以看不出来 |
| 空轮廓字形 lsb = 0 | 无墨迹可对齐 | `min(xs)` 为空时取 0 |

### 2.6 行距与段距

| 项 | 值 | 说明 |
|---|---|---|
| `hhea.lineGap` | 0 | 行距全部由 ascent/descent 决定 |
| `OS/2.sTypoLineGap` | 0 | 同上 |
| 行高 | `usWinAscent + usWinDescent` = 704 + 128 = **832 单位 = 13 像素** | 12ppem 下 = 13 设备像素 |
| 行高 / em | 832 / 768 = 1.0833 | 行高约为 1.083 em |
| 两套度量是否一致 | **一致**（hhea.ascent = sTypoAscender = usWinAscent = 704；descent 绝对值均 128） | 两套都取 `ascent * px` / `descent * px` |
| Word vs GDI 行距分裂 | **不存在** | 渲染器在 `usWinAscent/usWinDescent` 大于 `sTypo*` 时会改用 win 度量算行高；本字体两套同值，故无分裂 |
| 段距（段前/段后） | 不由字体决定 | 由宿主（Word / 浏览器）的段落设置给出 |

### 2.7 `.notdef` 与缺字度量

| 项 | 值 | 说明 |
|---|---|---|
| `.notdef` advance | **768** 单位 = 12 像素 | `cell_w * px` |
| `.notdef` lsb | 0 | 空心方框从 x = 0 起画 |
| 空心方框上沿 | y = **+704**（基线上方 ascent 处） | 与真实字面上沿齐平 |
| 空心方框下沿 | y = **-128**（基线下方 descent 处） | 伸到基线以下 descent 区 |
| 禁止的画法 | 不从 y = 0 起画 | 否则缺字框比真实字面高一截，排版时明显错位 |
| 缺字时的实际字面高度 | 704 + 128 = 832 单位 = 13 像素 | 与全角真实字面同高 |

### 2.8 多语言版的度量兼容性

`PixelFont Multi 12` 是**独立家族**（底稿已拍板形态），现有 `PixelFont PC98 12` 不动。但度量是**共享契约**，必须沿用。

| 要求 | 依据 | 状态 |
|---|---|---|
| 沿用 UPM 768 / 1 像素 = 64 单位 / 12×13 网格 / ascent 11 / descent 2 / lineGap 0 | 同一套度量与网格（底稿 §13 形态决策） | 已拍板 |
| 沿用半角 advance 6 / 全角 advance 12 的等宽规则 | 若多语言版引入其它 advance，12×13 网格与等宽基线被破坏 | **必须沿用** |
| 沿用 lsb = `glyf.xMin × 64` 规则 | 与 §2.5 同源 | **必须沿用** |
| 沿用行距规则（832 单位 = 13 像素，两套度量同值） | 与 §2.6 同源 | **必须沿用** |
| 拉丁扩展 A/B 241 码位 → 半角 384 单位（6 像素） | L1 增量 241，等宽规则 | 必须沿用 |
| 希腊 99 码位 → 半角 384 单位（6 像素） | L2 增量 99 | 必须沿用 |
| 西里尔 151 码位 → 半角 384 单位（6 像素） | L3 增量 151 | 必须沿用 |
| 韩文音节 11,172 码位 → 半角 384 单位（6 像素） | L4 增量 11,172，等宽规则 | 必须沿用 |
| JIS X 0208 假名/符号/全角 1,695 + 汉字 2,297 → 全角 768 单位（12 像素） | L5 / L6 增量 | 必须沿用 |
| CJK 其余 11,576 码位 → 全角 768 单位（12 像素） | L7 增量 | 必须沿用 |
| 增量交叉核对 | 241 + 99 + 151 + 11,172 + 1,695 + 2,297 + 11,576 = 27,231；27,231 + 4,161 = **31,392** | 与逐层累加一致 ✔ |
| 方案 C 覆盖缺口 | `U+20AC €`、`U+2260 ≠`、`U+2264 ≤`、`U+2265 ≥` 不被任何 Fusion 变体覆盖，走 MS Gothic / SimHei 非第三源路径 | 多语言版需登记源例外 |
| 多语言版开工状态 | 尚未开工 | 见 §5 B-06 |

### 2.9 度量相关的已知陷阱

| 编号 | 陷阱 | 后果 | 规避 |
|---|---|---|---|
| T-01 | 按 cell 高 13 作 em 除数 | ppem=12 下缩放比 12/13，每像素落 0.923 个设备像素，整副字糊掉且不报错 | em 方框按**字宽 12** 取；`UPM = 768`；`px = UPM // cell_w = 64` |
| T-02 | `lsb` 一律填 0 | 不从 x=0 起笔的窄字形（`!` `'` `(` `)` `,`）被整体左移 1–3 像素；汉字上看不出来 | `lsb = min(xs) * px`，必须 == `glyf.xMin` |
| T-03 | 用 East Asian Width 判全角/半角 | `…` `×` `÷` 的 EAW 是 `'A'`(ambiguous)，按半角会把 12px 字形塞进 6px 格，右半列墨迹被切 | 以源字体实测 advance 判定（`round(getlength(ch)) > half_w`），EAW 仅兜底 |
| T-04 | `UPM % cell_w != 0` | 像素错位 | 构建时 `raise SystemExit`「UPM 无法被 em 宽整除, 像素会错位」 |
| T-05 | `hhea` 与 `OS/2` 两套垂直度量不一致 | Word 行距与 GDI 行距分裂 | 两套都取 `ascent * px` / `descent * px`，lineGap 均为 0 |
| T-06 | `usWinAscent/usWinDescent` 大于 `sTypo*` | 渲染器改用 win 度量算行高，行高被放大 | 本字体两套同值（704 / 128），不存在该分裂 |
| T-07 | `.notdef` 从 y=0 起画 | 缺字框比真实字面高一截，排版明显错位 | 上沿到 +704，下沿到 -128 |
| T-08 | 手写 `ulUnicodeRange` 查表 / 沿用旧 `ulCodePageRange1` | 「Word 里装了却用不上」；旧值 0x00030000 实为 bit16(874)+bit17(932)，既无 1252 也无 936 | `ulUnicodeRange1–4` 交 fontTools 按 cmap 重算；`ulCodePageRange1 = (1<<0)\|(1<<17)\|(1<<18)`；`fsSelection = 0x0040` |
| T-09 | 用 Pillow 默认灰度抗锯齿再二值化 | 得到「缩小的矢量字体」而不是点阵 | 栅格化走 FreeType MONO 目标 `FT_LOAD_TARGET_MONO`（等同 GDI 1-bit 文字），输出 0/255 单色 L 图 |
| T-10 | 以为 GDI 会拿最近的 strike 缩放 | GDI **只在**请求 ppem 与 strike 的 ppem 精确相等时命中 `EBDT`/`EBLC`，否则回落 `glyf`（实测 Calibri 的 `A` 在 12/15/16/17/19ppem 命中，14/18/20–24ppem 回落） | 只承诺 12 整数倍字号；不依赖 strike 缩放 |
| T-11 | 非 12 整数倍字号期待逐格一致 | 18ppem 下笔画断裂、墨迹量偏细 **43%** | 用 `gasp {0xFFFF: 0}` 禁灰度抗锯齿/网格拟合；字号承诺写入安装说明 |

---

## 3. 验收判据

| 编号 | 规则或要求 | 判据（可量化） | 验证方式 |
|---|---|---|---|
| M-01 | UPM 固定 | `head.unitsPerEm == 768` | `ttx -t head -o - dist/PixelFontPC98-12.ttf` |
| M-02 | 像素单位整除 | `px == UPM // cell_w == 64` 且 `UPM % cell_w == 0` | 读 `build_font.py` 的 `UPM` 常量 + 构建日志 |
| M-03 | 整除守卫生效 | 构造 `UPM % cell_w != 0` 时构建以 `SystemExit` 失败，消息含「UPM 无法被 em 宽整除」 | 改 `UPM` 试构建 → 期望非 0 退出码（改动仅在本地实验，不入库） |
| M-04 | `hhea.ascent` | `== 704`（= 11 像素） | `ttx -t hhea -o - dist/PixelFontPC98-12.ttf` |
| M-05 | `hhea.descent` | `== -128`（= -2 像素） | 同上 |
| M-06 | `hhea.lineGap` | `== 0` | 同上 |
| M-07 | `OS/2.sTypo*` | `sTypoAscender == 704`、`sTypoDescender == -128`、`sTypoLineGap == 0` | `ttx -t OS/2 -o - dist/PixelFontPC98-12.ttf` |
| M-08 | `OS/2.usWin*` | `usWinAscent == 704`、`usWinDescent == 128` | 同上 |
| M-09 | x-height / cap-height | `sxHeight == 384`（6 像素）、`sCapHeight == 512`（8 像素） | 同上 |
| M-10 | 宽度类 | `usWidthClass == 5` | 同上 |
| M-11 | 常规体标记 | `fsSelection == 0x0040`（REGULAR） | 同上 |
| M-12 | 推进宽度 | 全角字形 `hmtx` advance `== 768`；半角字形 `== 384` | 逐字形读 `f['hmtx']` |
| M-13 | 左侧边距 | 全部有轮廓字形满足 `hmtx.lsb == glyf.xMin * 64`，例外数 **0** | Python 遍历 `f.getGlyphOrder()` 比对 `f['glyf'][n].xMin` |
| M-14 | `.notdef` | advance `== 768`、lsb `== 0` | 同 M-12 / M-13 的遍历 |
| M-15 | 行高 | `usWinAscent + usWinDescent == 832`（= 13 像素）；`hhea.ascent == sTypoAscender == usWinAscent`（无分裂） | `ttx` 读回后做加法与相等判定 |
| M-16 | 等宽硬约束 | 全部字形 advance ∈ {384, 768}，例外数 **0** | Python 遍历 `f['hmtx']` |
| M-17 | 字符集规模 | 当前家族码位数 `== 4161` | `python tools/fontgen/verify_all.py` 第 3 步（4,161 字分 43 批） |
| M-18 | GDI 逐格一致 | 12ppem 与 24ppem 下 **4161/4161** 逐格一致，抗锯齿像素 **0** | `python tools/fontgen/verify_gdi.py`（约 9 秒） |
| M-19 | 负向字号判据 | 18ppem 下不承诺逐格一致；实测墨迹量偏细 **43%**、笔画断裂 | `docs/word-compat.md` §7.6 实测记录；负向判据不得被改写为「一致」 |
| M-20 | BDF 宽度声明 | 全角 `SWIDTH 1000 0` / `DWIDTH 12 0`；半角 `SWIDTH 500 0` / `DWIDTH 6 0` | 读 `dist/PixelFontPC98-12.bdf` 的 `SWIDTH` / `DWIDTH` 行 |
| M-21 | 元数据不变量 | `verify_ttf_metadata()` 四组不变量全过（代码页位 / fsSelection / Unicode 区段位与 cmap 一致 / gasp 禁 DOGRAY\|GRIDFIT） | `python tools/fontgen/verify_all.py` 第 2 步 |
| M-22 | 端到端门禁 | `verify_all.py` **8/8 PASS**，回归 0 error 0 warn | `python tools/fontgen/verify_all.py`（约 6 分钟） |

---

## 4. 复现命令

以下命令在 PowerShell 下执行，工作目录为 `E:\PixelFont`。注释行以 `#` 标注期望输出。

```powershell
# ---- 1. 重建字体（期望：构建成功，产物 dist/PixelFontPC98-12.ttf = 973,712 字节）----
cd E:\PixelFont; python tools/fontgen/build_font.py

# ---- 2. 全链路 8 步验收（期望：8/8 PASS；回归 0 error 0 warn）----
cd E:\PixelFont; python tools/fontgen/verify_all.py

# ---- 3. Windows 兼容性门禁（期望：12/24ppem 全字符集 4161/4161 逐格一致，抗锯齿像素 0；约 9 秒）----
cd E:\PixelFont; python tools/fontgen/verify_gdi.py
```

```powershell
# ---- 4. 直接读回垂直/水平度量（期望输出见下）----
python -c "from fontTools.ttLib import TTFont; f=TTFont(r'E:\PixelFont\dist\PixelFontPC98-12.ttf'); h=f['hhea']; o=f['OS/2']; print('hhea',h.ascent,h.descent,h.lineGap); print('typo',o.sTypoAscender,o.sTypoDescender,o.sTypoLineGap); print('win',o.usWinAscent,o.usWinDescent); print('x/cap',o.sxHeight,o.sCapHeight); print('widthclass',o.usWidthClass,'sel',hex(o.fsSelection)); print('upm',f['head'].unitsPerEm,'lineheight',o.usWinAscent+o.usWinDescent)"
# 期望输出：
# hhea 704 -128 0
# typo 704 -128 0
# win 704 128
# x/cap 384 512
# widthclass 5 sel 0x40
# upm 768 lineheight 832
```

```powershell
# ---- 5. 校验 lsb == glyf.xMin（期望输出：lsb!=xMin: 0）----
python -c "from fontTools.ttLib import TTFont; f=TTFont(r'E:\PixelFont\dist\PixelFontPC98-12.ttf'); g=f['glyf']; bad=[n for n in f.getGlyphOrder() if g[n].numberOfContours>0 and f['hmtx'][n][1]!=g[n].xMin*64]; print('lsb!=xMin:',len(bad))"

# ---- 6. 校验 advance 只取 {384, 768}（期望输出：bad advance: 0）----
python -c "from fontTools.ttLib import TTFont; f=TTFont(r'E:\PixelFont\dist\PixelFontPC98-12.ttf'); bad=[(n,a) for n,a in f['hmtx'].metrics.items() if a[0] not in (384,768)]; print('bad advance:',len(bad))"

# ---- 7. .notdef 度量（期望输出：notdef advance 768 lsb 0）----
python -c "from fontTools.ttLib import TTFont; f=TTFont(r'E:\PixelFont\dist\PixelFontPC98-12.ttf'); a,l=f['hmtx']['.notdef']; print('notdef advance',a,'lsb',l)"

# ---- 8. 字形总数（期望输出：一个整数；具体值待验证，验证方法即本命令）----
python -c "from fontTools.ttLib import TTFont; f=TTFont(r'E:\PixelFont\dist\PixelFontPC98-12.ttf'); print('glyphs',len(f.getGlyphOrder()))"
```

```powershell
# ---- 9. ttx 导出人工复核（期望：hhea.ascent=704 / descent=-128 / lineGap=0；OS/2 sTypo*=704/-128/0）----
cd E:\PixelFont; python -m fontTools.ttx -t hhea -t OS/2 -t head -o - dist/PixelFontPC98-12.ttf

# ---- 10. 产物字节与散列核对（期望：973712 字节，sha256 = 3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1）----
cd E:\PixelFont; (Get-Item dist\PixelFontPC98-12.ttf).Length; (Get-FileHash dist\PixelFontPC98-12.ttf -Algorithm SHA256).Hash

# ---- 11. BDF 宽度声明抽查（期望：全角 SWIDTH 1000 / DWIDTH 12；半角 SWIDTH 500 / DWIDTH 6）----
cd E:\PixelFont; Select-String -Path dist\PixelFontPC98-12.bdf -Pattern '^(SWIDTH|DWIDTH) ' | Select-Object -First 8
```

```bash
# ---- 12. 抓参考字体 / 只校验（期望：抓取成功；--verify 仅校验不重下）----
python tools/fontgen/fetch_ref_fonts.py
python tools/fontgen/fetch_ref_fonts.py --verify

# ---- 13. 裁剪生产源 / 只验证（期望：逐像素一致 + 裁剪版 cmap == 原字体 cmap ∩ 本项目字符集）----
python tools/fontgen/vendor_fusion_pixel.py
python tools/fontgen/vendor_fusion_pixel.py --check
```

> 依赖说明：第 4–9 条命令依赖 Python 环境下已安装 `fontTools`；其确切版本号**待验证**（验证方法：`python -c "import fontTools; print(fontTools.version)"`）。第 10 条为 PowerShell 专有写法。

---

## 5. 已知边界与待办

| 编号 | 事项 | 状态 | 下一步 |
|---|---|---|---|
| B-01 | **只有 12 的整数倍字号能逐格还原设计**（12ppem=9pt / 24ppem=18pt / 36ppem=27pt @96dpi）；非整数倍（如 18ppem）笔画断裂 + 墨迹量偏细 **43%** | 已知边界（`gasp {0xFFFF: 0}` 已禁灰度抗锯齿与网格拟合，但无法消除非整数倍误差） | 在安装说明与 `docs/word-compat.md` 显式列出推荐字号；不做「任意字号精确」的承诺 |
| B-02 | 单字重 Regular，**无 Bold / Italic / 可变字体轴** | 已知边界 | 如需粗体，走宿主合成或另找 12px 粗体点阵源；届时须重开一次垂直度量评审（合成粗体会改变 xMin → 影响 lsb 规则） |
| B-03 | **无 kerning、无连字、无 OpenType 特性**（除 `gasp`） | 已知边界 | 等宽场景下 kerning 收益有限，暂不排期；若 `PixelFont Multi 12` 重新评估 GSUB `locl`（中日字形分歧），须连带重审度量契约 |
| B-04 | 本机已安装的是 **10-23 旧版**（1,362,480 字节，sha256 `FCC65BCBCD8A1A022007065E3444464916EDB537BB172B6F2ACDC9596DE3303B`），**尚未覆盖** | 待办 | 安装 `dist/PixelFontPC98-12.ttf` 后重跑 `python tools/fontgen/verify_gdi.py`，确认本机也命中 4161/4161 |
| B-05 | `PixelFont Multi 12`（31,392 码位）**尚未开工** | 待办 | 开工时新增度量回归门禁：逐字比对 advance ∈ {384, 768}、lsb == xMin、行高 832 |
| B-06 | 方案 C 中 `U+20AC €`、`U+2260 ≠`、`U+2264 ≤`、`U+2265 ≥` **不被任何 Fusion 变体覆盖** | 待办 | 多语言版构建脚本需在 `charset.SOURCE_OVERRIDES` 显式登记这 4 个码位的非第三源路径（沿用当前家族走 MS Gothic / SimHei 的做法） |
| B-07 | 中日共享 2,078 汉字中 **434 字（20.9%）** 中日字形不同；GSUB `locl` 变体机制**未选**（架构改动过大） | 已拍板不选 | 共享字默认取中文形（zh_hans 源）；用户若需日式字形须另行提需求，届时重新评估 |
| B-08 | 无 Arabic / Hebrew / Devanagari / Thai 的 12px 点阵源；Unifont 16 为 16×16 网格，塞不进 12px 格 | 已知边界 | 方案 C **不覆盖**这四个语系（Unifont 16 独有部分合计 896 码位）；如需覆盖须另找 12px 点阵源 |
| B-09 | 多语言版体积粗估约 **7.0 MB**（按当前 234.0 字节/字 均值推算） | 待验证 | 实测构建后回填；实际会因 CJK 字形复杂度不同而偏离 |
| B-10 | TTF 总字形数 | 待验证 | 验证方法见 §4 第 8 条命令 |
| B-11 | `head.yMax` / `head.yMin` / `OS/2.version` 等未在底稿固化的表项 | 待验证 | 验证方法：`ttx -t head -t OS/2 -o - dist/PixelFontPC98-12.ttf` 读回 |
| B-12 | 12px 层面只有 **2 票**参考（Ark Pixel 12px / Zpix v3.3.0）；Unifont 16px 因网格不同不参与笔画数比对；Ark 已作生产源后其票自证 | 已知边界 | 目视复核参考列固定为 Zpix + Unifont；来源与 sha256 清单见 `docs/reference-fonts.md` |
| B-13 | 成品字形派生自 **SimHei / MS Gothic**（微软专有）→ `dist/` 不入库；仓库 `LICENSE` = GNU AGPL-3.0（覆盖 `tools/fontgen/`）；`vendor/` 的 Fusion Pixel = OFL-1.1（三份许可随附） | 已知政策 | 发布包内保留三份许可与安装说明；产物不随仓库分发 |
| B-14 | 本仓库同时存在 `dev`（集成）与 `main`（发布镜像）两条分支，零分叉、`--ff-only` 快进 | 已知流程 | 提交信息沿用 `docs(spec): <主题>` 风格；推送走 gh 凭据通道 |

---

### 附：本文事实来源索引

| 内容 | 来源 |
|---|---|
| UPM / px / 轮廓生成 | `tools/fontgen/build_font.py`（`UPM` 常量、`px = UPM // cell_w`、`_emit_rect()`、`_merge_vertical_runs()`） |
| cell ascent / descent / latin_force_half / 全角判定 | `tools/fontgen/bitfont.py`（`BitmapFont` 的 `cell_ascent` / `cell_descent`、`ScriptStack`） |
| 字符集规模与来源 | `tools/fontgen/charset.py`（`gb2312_level1()` / `ascii_chars()` / `kana_chars()` / `extras()` / `EXCLUDE` / `SOURCE_OVERRIDES` / `build_charset()`） |
| 元数据不变量门禁 | `tools/fontgen/build_font.py::verify_ttf_metadata()`（commit `cef4a22`，2026-10-24 修复） |
| 8 步质量门禁 | `tools/fontgen/verify_all.py` |
| GDI 全字符集栅格化 | `tools/fontgen/verify_gdi.py`；报告 `reports/gdi_compat.json` + `reports/gdi_raster_scan.tsv` |
| 渲染器相关性与字号实测 | `docs/word-compat.md`（§7.2 / §7.5 / §7.6 / §7.7） |
| 多语言版逐层账目与中日字形分歧 | 统一事实底稿 §13 |
| 参考字体版本与 sha256 | `docs/reference-fonts.md`；`tools/fontgen/fetch_ref_fonts.py` |
| 生产源裁剪验证 | `tools/fontgen/vendor_fusion_pixel.py`（`--check` 只校验） |
