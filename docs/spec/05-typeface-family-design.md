# 05. 字体家族设计书

> PixelFont 规格文档集 · 第 5 份 · 主题：字体家族（Typeface Family）设计规范
> 事实基线：`E:\PixelFont` 仓库 `dev` 分支 HEAD `4300fc1`（`main` 为发布镜像，两者零分叉）

---

## 结论先行

**本家族当前只有一个字重：Regular。** 具体形态是——单字重（`usWeightClass=400`）、固定宽度等宽（`usWidthClass=5`，全角 advance 12 / 半角 advance 6）、正立无斜体、**没有任何可变字体轴**（字体内无 `fvar` / `gvar` / `avar` / `STAT` / `HVAR` / `VVAR`，唯一存在的 OpenType 表是 `gasp = {0xFFFF: 0}`）。这不是"做了一半"的家族，而是**在像素字体这一品类下主动收敛到单一点阵形态**的结果。

**结论一：Bold 不做。** 12×13 的设计网格里，笔画间隙最小只有 **1px**；任何加粗都要在两侧各扩 1px，必然把 1px 间隙填满，汉字会从"笔画"糊成"色块"。这与本项目已经确立的渲染结论是同一条底线——只有 **12 的整数倍字号**（12ppem = 9pt、24ppem = 18pt、36ppem = 27pt @96dpi）能逐格还原设计，非整数倍（如 18ppem = 1.5 倍）笔画断裂且**墨迹量偏细 43%**。在这样的像素契约上再叠一层"加粗"，等于主动破坏逐格还原性。

**结论二：字宽轴不做（`usWidthClass` 恒为 5）。** 像素字必须等宽，否则列宽、行高、图元对齐全部失控。`tools/fontgen/bitfont.py` 的 `stretch` 参数是**构建期**的"全角 cell 额外加宽量"，用于拉开字距的排版风格，**不是**可变轴，也不产生第二个家族。

**结论三：真斜体不做。** 点阵斜体需要斜切像素网格，必然破坏等宽 advance 与基线对齐；逐行错位的假斜体则破坏 12px 行网格。

**结论四：可变字体轴不做。** `gvar` 插值的中间实例天然产生非整数坐标，而本家族的坐标必须恒为 **64 单位（= UPM 768 / 12）** 的整数倍，否则逐格还原性失效。变体轴与像素整数网格在数学上互斥。

**结论五：多语言需求走"独立家族"，不走"加轴"。** `PixelFont Multi 12` 是**独立家族**（覆盖 31,392 码位），共享同一套度量与网格，但字形集合不同；中日共享的 2,078 个汉字里有 **434 个（20.9%）** 字形像素不同，策略是"中文形为主 + JIS 独有 2,297 字走 ja 源"。加轴解决不了字形集合问题，家族拆分才能。

**拟议路线**：本家族维持 **单字重 + 固定宽度 + 正立** 的形态并长期固化进 `OS/2` 门禁；若未来必须提供视觉强调，优先走"独立家族 + 独立文件"（`PixelFont PC98 12 Bold` / `PixelFontPC98-12-Bold.ttf`）而非在现有家族上加轴，且 Bold 家族必须**独立走一套字形网格设计**，不得在 Regular 轮廓上做程序化加粗。

---

## 1. 范围与目的

### 1.1 目的

本文件是 PixelFont 的**家族设计规范**，不是"已发布多字重家族的描述"。它规定：

1. 家族命名规则（name 表 / PostScript 名 / `achVendID`）与将来新增家族时的扩展方式；
2. 字重轴、字宽轴、斜体、可变字体轴这四条设计轴的**取值约定与实现方式**；
3. 族内成员如何组合、共享哪些度量、差异落在哪里；
4. 在像素字体品类下这四条轴各自的**技术代价**，以及本家族的取舍结论。

凡本家族尚未具备的能力，一律标注 **规划中 / 未实现**，不得写成已具备。

### 1.2 适用范围

| 项 | 范围 |
|---|---|
| 适用家族 | `PixelFont PC98 12`（已发布 v1.0.0）；`PixelFont Multi 12`（规划中 / 未开工） |
| 适用产物 | `dist/PixelFontPC98-12.ttf`（973,712 字节，sha256 `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1`） |
| 适用流水线 | `tools/fontgen/build_font.py`（构建 + `verify_ttf_metadata()` 不变量）、`tools/fontgen/verify_all.py`（8 步门禁）、`tools/fontgen/verify_gdi.py`（Windows 兼容） |
| 不适用 | 参考字体（Ark Pixel / Fusion Pixel / Zpix / GNU Unifont）本身的设计；`third_party/` 参考字体不进构建 |
| 不适用 | 字形来源与许可细则（见 `docs/reference-fonts.md` 与仓库 `LICENSE` = GNU AGPL-3.0 / `vendor/` Fusion = OFL-1.1） |

### 1.3 读者

| 读者 | 关注点 |
|---|---|
| 字体生成流水线维护者 | 家族名 / PostScript 名 / `OS/2` 字段的写入规则与门禁 |
| 打包与发布人员 | 家族成员清单、文件名规则、zip 内条目与 sha256 清单 |
| 下游使用者（终端 / 编辑器 / Word） | 字重、字宽、斜体是否可用，元数据是否被正确识别 |
| 未来维护者 | 本家族**为什么**只有单字重，避免"顺手补个 Bold"破坏像素契约 |

### 1.4 术语

| 术语 | 英文 / 字段名 | 本文含义 |
|---|---|---|
| 家族名 | family name（name ID 1 / ID 16） | `PixelFont PC98 12` |
| PostScript 名 | PostScript name（name ID 6） | `PixelFontPC98-12` |
| 字重 | weight（`OS/2.usWeightClass`） | 本家族仅 Regular = 400 |
| 字宽 | width（`OS/2.usWidthClass`） | 固定宽度 = 5 |
| 样式选择 | `OS/2.fsSelection` | 0x0040 = REGULAR |
| 安装权限 | `OS/2.fsType` | 0 = 可自由安装 |
| 厂商标识 | `OS/2.achVendID` | `PXLF` |
| 代码页范围 | `OS/2.ulCodePageRange1` | `(1<<0)\|(1<<17)\|(1<<18)` = 1252 + 932 + 936 |
| Unicode 区段 | `OS/2.ulUnicodeRange1`–`4` | 不手写，由 fontTools 按 cmap 实际覆盖重算 |
| 网格拟合 / 灰度抗锯齿 | `gasp` | `{0xFFFF: 0}`，禁 DOGRAY + GRIDFIT |
| 可变字体轴 | `fvar` / `gvar` / `avar` / `STAT` / `HVAR` / `VVAR` | 本家族**全部不存在** |
| 设计网格 | design grid | 12 × 13 像素（宽 × 高），12px 等宽，PC-98 风格 |
| 单位 | UPM / units per em | 768；1 像素 = 64 单位（768 / 12） |
| 基线 | baseline | ascent 11 / descent 2（基线在第 11 行下方，cell 第 12 行），cell 高 13 |
| advance | 字距 / 前进宽度 | 全角 12（768 单位）、半角 6（384 单位） |
| 规划中 / 未实现 | planned / not implemented | 本仓库当前**不具备**该能力，本文只给约定不给现状 |

---

## 2. 正文

### 2.1 家族定位与命名规范

| 项 | 当前值 | 规则 |
|---|---|---|
| 家族定位 | 12px 等宽点阵 CJK 正文/终端字体，PC-98 风格 | 规则：像素字体不做比例字距，全角 12 / 半角 6 恒定 |
| 家族名（name ID 1 / ID 16） | `PixelFont PC98 12` | 规则：发布后不再改动；ID 16 与 ID 1 同值（单字重家族） |
| 风格名（name ID 2 / ID 17） | `Regular` | 规则：单字重家族 ID 2 恒为 `Regular`；ID 17 实际字符串**待验证**（验证方法：fontTools `name.getDebugName(2)` / `getDebugName(17)`） |
| PostScript 名（name ID 6） | `PixelFontPC98-12` | 规则：`PixelFont` + `<Variety>`（去空格）+ `-` + `<Size>` |
| 命名模式 | `PixelFont <Variety> <Size>` | 规则：`<Variety>` ∈ {`PC98`, `Multi`}；`<Size>` = 像素格边长 `12` |
| 「12」的含义 | 全角 advance = 12 px（768 单位） | 规则：家族名只写宽度维度；cell 高 13 不进家族名。取名出处**待验证**（验证方法：查 `docs/` 与 README 中 `PC98` 命名说明） |
| `achVendID` | `PXLF` | 规则：4 字节全大写，仓库内唯一，不复用 |
| 风格后缀 | 当前**不适用**（无第二风格） | 规则（规划中）：若出 Bold/Italic，PostScript 名与文件名加 `-Bold` / `-Italic`，但走 OpenType 四段式，见 2.7 |
| 多语言版 | `PixelFont Multi 12` | 规则：**独立家族**，不改现有家族（形态决策已拍板）；共享度量与网格，字形集合不同 |
| 字体版本 | v1.0.0（已发布） | 规则：注解 tag 在 `main`，GitHub Release 正式版（`draft=false`），5 个附件 |

### 2.2 族内成员清单

| 成员 | 状态 | 覆盖 | 备注 |
|---|---|---|---|
| `PixelFontPC98-12.ttf` | **已发布 v1.0.0** | 4,161 码位 | ASCII 95 + 标点/符号 56 + 假名 255 + 汉字 3,755（GB2312 一级，机械推导） |
| ↳ 其中汉字来源 | 已发布 | 3,755 | GB2312 一级（区位 16–55 区，`0xB0A1`–`0xD7F9`）机械推导，非凭记忆列字表 |
| ↳ 源列表合计 | 已发布 | 4,164 → 去重 4,161 | 重复 3 字：`ヶ` U+30F6、`ー` U+30FC、`～` U+FF5E |
| ↳ 明确排除 | 已发布 | — | `charset.EXCLUDE`：`U+3097 ゗`、`U+3098 ゘`（非 JIS 字集，MS Gothic 无此字形） |
| ↳ 2026-10-24 补充 | 已发布 | +21 码位 | 弯引号、全角空格 U+3000、NBSP、`– • ‧`、`¥ ° ½`、`€ →`、`≠ ≤ ≥`、`［ ］ ｛ ｝` |
| `PixelFontPC98-12.bdf` | 已发布 | 4,161 | 665,950 字节 |
| `PixelFontPC98-12-atlas.png` / `-atlas.json` / `-specimen.png` / `-bdf.map` | 已发布 | — | 141,857 / 87,300 / 2,977 / 183,034 字节 |
| `PixelFontPC98-12-2026-10-24.zip` | 已发布 | zip 内 9 项 | 533,116 字节，sha256 `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8` |
| `PixelFont Multi 12`（独立家族） | **规划中 / 未开工** | 31,392 码位（方案 C） | 逐层账目 L0–L7 见 2.9；PostScript 名按命名模式推导为 `PixelFontMulti-12`（推导值，未实现） |
| `PixelFont PC98 12 Bold` | **规划中 / 未实现** | — | 需独立字形集，不得由 Regular 程序化加粗派生 |
| `PixelFont PC98 12 Italic` | **规划中 / 未实现（结论：倾向不做）** | — | 见 2.5 |
| `PixelFont PC98 12 Bold Italic` | **规划中 / 未实现** | — | 依赖 Bold 先行，结论同 2.3 + 2.5 |

### 2.3 字重轴设计

| 字重名 | `usWeightClass` | `fsSelection` 位 | 实现方式 | 状态 |
|---|---|---|---|---|
| Regular | **400** | **0x0040**（REGULAR，bit 6） | 唯一字重：源位图逐像素转轮廓（每像素一个矩形，竖向游程合并），12×13 网格 / UPM 768 | **已实现（v1.0.0）** |
| Bold | 拟议 700 | 拟议 0x0020（BOLD，bit 5） | 需为 4,161 个字形**另建**加粗位图集并独立走网格设计 | **规划中 / 未实现** |
| Italic | 拟议 400 | 拟议 0x0001（ITALIC，bit 0） | 见 2.5，结论倾向不做 | **规划中 / 未实现** |
| Bold Italic | 拟议 700 | 拟议 0x0021（BOLD \| ITALIC） | 依赖 Bold 与 Italic 两者先行 | **规划中 / 未实现** |
| Light / Black 等 | — | — | 不在规划内；像素字体不做连续字重梯度 | 不适用 |

**Bold 的技术难点（量化与机理）**

| 难点 | 机理 | 影响 | 状态 |
|---|---|---|---|
| 笔画间隙被吞 | 12×13 网格内相邻笔画之间的间隙最小仅 **1px**；加粗 1px 即填满该间隙 | 汉字由"笔画"变"色块"，笔画数不可辨 | 待验证（验证方法：见 2.3 量化口径） |
| 轮廓游程合并规则失效 | v1.0.0 起竖向相邻、x 范围相同的水平游程合并成一个矩形，轮廓数 107,209 → **73,933**（-31%）；TTF 1,364,528 → **973,712 字节**（-28.6%），整数倍精确性 12,483 / 12,483 | 加粗后合并结果与 Regular 不同，Bold 需重新设计合并结果 | 待验证 |
| 墨迹量失衡 | 12px 格内墨迹率随笔画膨胀上升 | 在 12ppem 下密集笔画区域可能糊成实心 | 待验证 |
| 体积翻倍 | 平均 **234.0 字节/字**（4,161 字 = 973,712 字节） | Bold 若同等复杂度约 1.95 MB（按同均值外推的**粗估**，非实测） | 待验证（验证方法：实际构建 Bold 后取真值） |
| 逐格还原契约 | 只有 12 的整数倍字号（12 / 24 / 36 ppem）能逐格还原设计；非整数倍笔画断裂且墨迹量偏细 **43%** | Bold 同样受此约束，加粗后容错更低 | 已确认（实测结论，见 `docs/word-compat.md` §7.6） |

> **量化口径（Bold 粘连的验证方法）**：用 `tools/fontgen/bitfont.py` 的 `ink_ratio()` / `count_runs()` / `count_holes()` 对"Regular 位图"与"Bold 位图"重算笔画连通数与孔洞数；粘连字数 = 笔画连通数下降的汉字数（> 0 即证伪"加粗可行"）。该实验当前**未执行**，结论标为待验证。

### 2.4 字宽轴设计

| 字宽名 | `usWidthClass` | 全角 advance | 半角 advance | 状态 |
|---|---|---|---|---|
| 固定宽度（等宽） | **5** | 12 px = 768 单位 | 6 px = 384 单位 | **已实现** |
| 半比例（SemiCondensed 等） | 拟议 3 | — | — | **规划中 / 未实现（结论：不做）** |
| 全比例（Proportional） | 拟议 3 / 4 | — | — | **规划中 / 未实现（结论：不做）** |

| 规则项 | 内容 |
|---|---|
| 固定宽度理由 | 像素字体必须等宽，否则网格对齐、终端列宽、图元定位全部失控；advance 全角 12 / 半角 6 是家族级不变量 |
| `stretch` 参数澄清 | `tools/fontgen/bitfont.py` 的 `stretch` 是**构建期**的"全角 cell 额外加宽量"，用途是拉开字距的排版风格；它是**排版风格调节**，**不是可变轴**，也不产生第二个家族：产物元数据仍是 `usWeightClass=400` / `usWidthClass=5` |
| 若将来做字宽轴的前提 | 半角 advance 必须仍是 384 单位的整数倍；否则等宽契约破裂（与 2.6 的整数网格约束同源） |
| 现状自检 | 全字符集 4,161 码位 advance 一致性由 `verify_all.py` 步骤 2 与 `verify_gdi.py` 逐格回归覆盖 |

### 2.5 斜体设计

| 方案 | 效果 | 代价 | 状态 |
|---|---|---|---|
| 轮廓斜切（oblique / skew） | 真正的斜体观感 | 对 4,161 个字形逐个重绘；斜切后坐标不再是 64 单位整数倍 → 逐格还原性失效；advance 与基线对齐同时被破坏 | **不采用** |
| 逐行错位假斜体（每行右移 1px） | 近似斜体 | 行间偏移破坏 12px 行网格；与基线（ascent 11 / descent 2）不齐 | **评估中 / 未实现** |
| 省略斜体，由宿主端合成（CSS `font-synthesis` / 编辑器 synthetic italic） | 使用者仍能得到斜体外观 | 合成斜体由渲染器在运行时偏移，偏移量与目标 ppem 不成比例，可能产生半像素，违背逐格还原契约 | 备选项（下游自行决定，家族不提供） |
| 复用源字体斜体样式（MS Gothic 等） | 复用现成斜体 | 源字体是否提供斜体样式**待验证**（验证方法：fontTools 读 `C:\Windows\Fonts\msgothic.ttc` 的 `OS/2.fsSelection`）；且 MS Gothic 为微软专有源，`dist/` 不入库 | 未评估 |

**结论**：像素字体不做真斜体。本家族不提供 Italic 家族成员，`fsSelection` 恒为 `0x0040`。

### 2.6 可变字体轴设计

| 轴 | 范围 | 默认值 | 技术前提 | 状态 |
|---|---|---|---|---|
| `wght`（字重） | 拟议 400–700 | 400 | 需 `fvar` + `gvar`；每个实例须落在 12×13 整数网格上；实例须落在整数倍字号下可逐格还原 | **规划中 / 未实现（结论：不做）** |
| `wdth`（字宽） | 拟议 1–3 | 1 | 需 `fvar` + `HVAR` / `VVAR` + 实例轮廓重排；advance 变化违反等宽契约 | **规划中 / 未实现（结论：不做）** |
| `slnt`（倾斜） | 拟议 0 至 -12 | 0 | 需 `gvar` 插值；插值产生非整数坐标，破坏网格 | **规划中 / 未实现（结论：不做）** |
| `opsz`（光学尺寸） | 拟议 12 | 12 | 需 `fvar` + `STAT`；对像素字体仅是渲染器提示，不改变字形 | **规划中 / 未实现（结论：不做）** |
| 现状 | **无任何轴** | — | 字体内**无** `fvar` / `gvar` / `avar` / `STAT` / `HVAR` / `VVAR`；唯一存在的 OpenType 表是 `gasp = {0xFFFF: 0}` | **已确认** |

**可变轴的技术难点**

| 难点 | 机理 | 后果 | 状态 |
|---|---|---|---|
| 整数网格约束 | 本家族所有轮廓坐标必须是 64 单位（UPM 768 / 12）的整数倍 | `gvar` 插值天然产出非整数坐标 → 12ppem 下笔画断裂 + 墨迹偏细 **43%**（已有实测） | 规划中 / 未实现 |
| 轮廓合并与游程 | 竖向游程合并把 107,209 个矩形压到 73,933 个 | 变体需在插值点重新做合并，合并规则在插值结果上不成立 | 规划中 / 未实现 |
| 等宽 advance 不变 | 全角 advance 恒 768 单位 | 半宽变体无法等宽，与 2.4 冲突 | 规划中 / 未实现 |
| 门禁与回归成本 | 现有 8 步门禁以 4,161 字固定集为准（43 批逐像素回归） | 变体需对每个实例重跑全量回归，成本按实例数倍增 | 规划中 / 未实现 |
| `usWeightClass` 与 `fvar` 一致性 | 可变家族要求 `fvar` 的 `wght` 实例范围包含 `usWeightClass` 取值 | 单字重家族无需维护该一致性 | 不适用（当前无 `fvar`） |

### 2.7 家族矩阵与命名实例

| 拟议组合 | 家族名 | 文件名 | 状态 |
|---|---|---|---|
| PC98 × Regular（现状） | `PixelFont PC98 12` | `PixelFontPC98-12.ttf` | **已发布 v1.0.0** |
| PC98 × Bold | `PixelFont PC98 12 Bold`（独立家族口径） | `PixelFontPC98-12-Bold.ttf` | 规划中 / 未实现 |
| PC98 × Italic | `PixelFont PC98 12 Italic` | `PixelFontPC98-12-Italic.ttf` | 规划中 / 未实现（结论：倾向不做） |
| PC98 × Bold Italic | `PixelFont PC98 12 Bold Italic` | `PixelFontPC98-12-BoldItalic.ttf` | 规划中 / 未实现 |
| Multi × Regular | `PixelFont Multi 12` | `PixelFontMulti-12.ttf` | 规划中 / 未开工 |
| Multi × Bold | `PixelFont Multi 12 Bold` | `PixelFontMulti-12-Bold.ttf` | 规划中 / 未开工 |

**命名规则（规划中风格后缀的写法）**

| 规则项 | 内容 |
|---|---|
| 四段式 name ID | 若出 Bold：ID 1 = `PixelFont PC98 12`（不带风格词）、ID 2 = `Bold`、ID 16 = `PixelFont PC98 12`、ID 17 = `Bold`；PostScript ID 6 = `PixelFontPC98-12-Bold` |
| 文件名 | 与 PostScript 名同形：`<PostScriptName>.ttf`，另出 `.bdf` / `-atlas.png` / `-atlas.json` / `-specimen.png` / `-bdf.map` |
| zip 名 | `<PostScriptName>-<YYYY-MM-DD>.zip`（现状：`PixelFontPC98-12-2026-10-24.zip`） |
| 禁止 | 同一家族内用文件名区分字重而元数据不区分（会导致 `fsSelection` 与实际字形不一致） |

### 2.8 元数据映射规范

| `OS/2` 字段 | 值 | 依据 |
|---|---|---|
| `usWeightClass` | **400** | 单字重 Regular 家族（无 `fvar`，无第二字重）。旧值缺失会导致宿主按默认 400 猜测，不可控 |
| `usWidthClass` | **5** | 固定宽度等宽；全角 advance 12 / 半角 advance 6 恒定 |
| `fsSelection` | **0x0040**（REGULAR） | commit `cef4a22` 修复项：旧值 `0x0000` 缺 REGULAR，Windows 可能不把它当正文常规字 |
| `fsType` | **0** | 可自由安装（安装型嵌入限制） |
| `achVendID` | **PXLF** | 仓库内唯一厂商标识，4 字节全大写 |
| `ulCodePageRange1` | **`(1<<0) \| (1<<17) \| (1<<18)`** = 1252 + 932 + 936 | commit `cef4a22` 修复项：覆盖 Latin-1 / Shift-JIS / GB2312 三套代码页；旧值 `0x00030000` 实为 bit16（874 泰语）+ bit17（932），既无 1252 也无 936 |
| `ulUnicodeRange1`–`4` | **不手写**，由 fontTools 按 cmap 实际覆盖重算 | 手写查表会再次出错（`cef4a22` 修复说明） |
| `ulCodePageRange2` | 不额外声明 | **待验证**（验证方法：fontTools 读 `OS/2.ulCodePageRange2`） |
| `version` | OS/2 表版本 | **待验证**（验证方法：fontTools 读 `OS/2.version`） |

| `name` 表字段 | 值 | 依据 |
|---|---|---|
| ID 1（家族名） | `PixelFont PC98 12` | 家族定位 |
| ID 2（风格名） | `Regular` | 单字重家族；实际字符串**待验证**（验证方法：`name.getDebugName(2)`） |
| ID 6（PostScript 名） | `PixelFontPC98-12` | 命名规则（2.1） |
| ID 16 / ID 17（排版家族/风格） | 与 ID 1 / ID 2 同值 | 单字重家族规范；ID 17 实际字符串**待验证** |
| ID 5（版本） | `Version 1.0.0` | v1.0.0 已发布；实际字符串**待验证**（验证方法：`name.getDebugName(5)`） |
| ID 3 / ID 4 / ID 13 / ID 14 | — | 唯一标识 / 全名 / 许可 / 许可 URL | 实际字符串**待验证**（验证方法：`name.getDebugName(n)`） |

| 非 `OS/2` 表 | 值 | 依据 |
|---|---|---|
| `gasp` | `{0xFFFF: 0}` | 像素字不该请求灰度抗锯齿（DOGRAY）或网格拟合（GRIDFIT）；`verify_ttf_metadata()` 硬拦 |
| `fvar` / `gvar` / `avar` / `STAT` / `HVAR` / `VVAR` | **不存在** | 无可变轴 |
| `kern` / `GSUB` / `GPOS` | **不存在** | 无 kerning、无连字、无 OpenType 特性 |
| `EBDT` / `EBLC` | 不由本项目生成 | GDI **会**采用 `EBDT`/`EBLC` 内嵌位图，但**只在请求字号与 strike 的 ppem 精确相等时**命中，**不会拿最近的 strike 缩放**（实测：Calibri 的 `A` 在 12/15/16/17/19ppem 命中对应 strike，14/18/20–24ppem 回落到 `glyf` 轮廓） |
| `head.unitsPerEm` | 768 | 1 像素 = 64 单位（768 / 12） |
| 门禁不变量 | 代码页位 / `fsSelection` / Unicode 区段位与 cmap 一致 / `gasp` 禁 DOGRAY\|GRIDFIT | `build_font.py::verify_ttf_metadata()` 四组硬拦 |

### 2.9 多语言家族与现有家族的关系

| 项 | `PixelFont PC98 12` | `PixelFont Multi 12` | 关系 |
|---|---|---|---|
| 形态 | **已发布 v1.0.0** | **规划中 / 未开工** | **独立家族**（形态决策已拍板：新增独立家族，现有家族不动） |
| 码位覆盖 | 4,161 | 31,392（方案 C = A + 全部 CJK） | 字形集合**不同** |
| 度量 | 12×13 网格 / UPM 768 / 1px = 64 单位 / ascent 11 descent 2 / 全角 12 半角 6 | 同左 | **共享度量与网格** |
| 字重 / 字宽 / 斜体 | 单字重 / 固定宽度 / 正立 | 同左（规划中同样单字重） | 一致，不引入新轴 |
| 命名 | `PixelFont PC98 12` / `PixelFontPC98-12` | `PixelFont Multi 12` / `PixelFontMulti-12`（推导值） | 同一命名模式 |
| 体积 | 973,712 字节 | 约 **7.0 MB**（按 234.0 字节/字同均值**粗估**，非实测） | — |

**逐层覆盖账目（`PixelFont Multi 12`，每层可加总复核）**

| 层 | 内容 | 增量 | 累计 |
|---|---|---|---|
| L0 | 当前家族 | 4,161 | 4,161 |
| L1 | +Latin Ext A/B（U+0100–U+024F ∩ Fusion latin） | 241 | 4,402 |
| L2 | +Greek（U+0370–U+03FF ∩ Fusion latin） | 99 | 4,501 |
| L3 | +Cyrillic（U+0400–U+04FF ∩ Fusion latin） | 151 | 4,652 |
| L4 | +Hangul syllables（U+AC00–U+D7AF ∩ Fusion ko） | 11,172 | 15,824 |
| L5 | +JIS X 0208 假名/符号/全角（Shift-JIS 首字节 0x81–0x87 / 0xE0–0xEF ∩ Fusion ja） | 1,695 | 17,519 |
| L6 | +JIS X 0208 汉字 4,375（Shift-JIS 首字节 0x88–0x9F ∩ Fusion ja） | 2,297 | 19,816 |
| L7 | +CJK 其余（U+4E00–U+9FFF ∩ Fusion ja） | 11,576 | **31,392** |

交叉核对：方案 A（L0–L6）= 19,816；CJK 整块 U+4E00–U+9FFF ∩ Fusion ja = 19,317；A ∪ CJK = 31,392 ✔。

**中日字形关系（机械推导 + 实测，非凭记忆）**

| 项 | 数量 | 说明 |
|---|---|---|
| GB2312 一级汉字 | 3,755 | 现有家族汉字集 |
| JIS X 0208 汉字（Shift-JIS 双字节判定） | 4,375 | — |
| 两者交集（中日共享） | **2,078** | Fusion ja / zh_hans 均 100% 覆盖，且两者在共享集上的码位集合完全相同 |
| JIS 独有 | 2,297 | 在 Fusion ja 源中 2,297 / 2,297 全部有墨迹（不缺字） |
| GB 独有 | 1,677 | — |
| 共享集内**像素完全相同** | **1,644 / 2,078**（79.1%） | 12×13 单色 cell 逐像素实测 |
| 共享集内**像素不同** | **434 / 2,078**（20.9%） | 中日字形分歧真实存在 |

- 差异最大的字（异或格数）：`肩` U+80A9 (78)、`扇` U+6247 (71)、`房` U+623F (69)、`雇` U+96C7 (69)、`遍` U+904D (59)、`扁` U+6241 (54)、`煽` U+717D (53)、`灰` U+7070 (44)、`曾` U+66FE (41)、`罪` U+7F6A (40)、`偏` U+504F (38)、`奠` U+5960 (38)、`判` U+5224 (37)、`歉` U+6B49 (35)、`遥` U+9065 (30)、`滞` U+6EDE (29)、`直` U+76F4 (28)、`氏` U+6C0F (26)、`才` U+624D (25)。
- 异或格数分布：1 格 102 字、2 格 94 字、3 格 40 字、4 格 42 字、5 格 27 字、6 格 18 字，≥7 格共 93 字，最大 78 格。
- **策略**：中文形为主（zh_hans 源）+ JIS 独有 2,297 字走 ja 源；GSUB `locl` 变体因架构改动过大**未选**。
- 覆盖缺口：方案 C 的 31,392 中有 **4 个码位不被任何 Fusion 变体覆盖**——`U+20AC €`、`U+2260 ≠`、`U+2264 ≤`、`U+2265 ≥`；这 4 个在当前家族里已有（走 MS Gothic / SimHei），多语言版需沿用同样的非第三源路径。
- 未覆盖语系（方案 B 未选）：Arabic / Hebrew / Devanagari / Thai —— 唯一可用源是 GNU Unifont 16（16×16 网格），塞不进 12px 格。

---

## 3. 验收判据

| 编号 | 家族规则 | 判据（可量化） | 验证方式 |
|---|---|---|---|
| A1 | 单字重 Regular | `OS/2.usWeightClass == 400` | fontTools 读 `dist/PixelFontPC98-12.ttf` |
| A2 | REGULAR 标志位 | `OS/2.fsSelection == 0x0040` | 同上；亦由 `verify_ttf_metadata()` 硬拦 |
| A3 | 无 Bold / Italic 家族成员 | `dist/` 下不存在 `*Bold*.ttf` / `*Italic*.ttf` | 目录列举 |
| A4 | 固定宽度 | `OS/2.usWidthClass == 5` | fontTools 读取 |
| A5 | 等宽 advance 不变 | 全角 advance == 768 单位；半角 advance == 384 单位 | fontTools 读 `hmtx`（全角样本 U+4E00，半角样本 `A`） |
| A6 | 整数网格 | `head.unitsPerEm == 768` 且 768 / 12 == 64；抽查轮廓坐标均为 64 的整数倍 | fontTools 读 `head` + 抽字形轮廓 |
| A7 | 基线 | ascent 11 / descent 2（cell 高 13） | 构建产物回读 + 字形基线位置抽查 |
| A8 | 无可变轴 | 表清单中**不含** `fvar` / `gvar` / `avar` / `STAT` / `HVAR` / `VVAR` | fontTools 列出 `f.keys()` |
| A9 | `gasp` 禁灰度 | `gasp == {0xFFFF: 0}`（禁 DOGRAY \| GRIDFIT） | fontTools 读 `gasp.gaspRange` |
| A10 | 无 OpenType 排版特性 | 不含 `kern` / `GSUB` / `GPOS` | fontTools 列出表名 |
| A11 | 家族身份 | name ID 1 / ID 16 == `PixelFont PC98 12`；ID 6 == `PixelFontPC98-12` | fontTools 读 `name` 表 |
| A12 | 厂商标识 | `OS/2.achVendID == "PXLF"` | fontTools 读取 |
| A13 | 可自由安装 | `OS/2.fsType == 0` | fontTools 读取 |
| A14 | 代码页覆盖 | `ulCodePageRange1 & ((1<<0)\|(1<<17)\|(1<<18)) == (1<<0)\|(1<<17)\|(1<<18)` | fontTools 读取；亦为门禁不变量 |
| A15 | Unicode 区段一致 | `ulUnicodeRange1`–`4` 与 cmap 实际覆盖一致 | `verify_ttf_metadata()` 不变量（第 3 组） |
| A16 | 逐格还原 | 12ppem 与 24ppem 下全字符集 **4,161 / 4,161** 逐格一致，抗锯齿像素 **0** | `python tools/fontgen/verify_gdi.py`；报告 `reports/gdi_compat.json` + `reports/gdi_raster_scan.tsv`（逐码位 4,162 行） |
| A17 | 全量门禁 | `verify_all.py` **8 / 8 PASS**；回归 0 error 0 warn | `python tools/fontgen/verify_all.py` |
| A18 | 产物一致性 | 独立读 `dist/` 与当前源逐字比对一致（门禁第 5 步） | `verify_all.py` 步骤 5 |
| A19 | 产物指纹 | `dist/PixelFontPC98-12.ttf` sha256 == `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1`；字节 == 973,712 | `Get-FileHash` / 文件长度 |
| A20 | 家族独立性（规划中） | 新增 `PixelFont Multi 12` 后，`PixelFont PC98 12` 的字节与 sha256 **不变** | 构建前后 sha256 对比 + `git diff` |
| A21 | 单字重策略不倒退 | 任何新增 `*Bold*` / `*Italic*` 文件必须走独立家族口径并同步更新本文 2.7 | 评审检查 |

---

## 4. 复现命令

以下命令在 `E:\PixelFont`（分支 `dev`，HEAD `4300fc1`）执行，均为只读或重建构建，不改动其它仓库。

```powershell
cd E:\PixelFont

# 1) 家族身份与 OS/2 关键字段
python -c "from fontTools.ttLib import TTFont; f=TTFont('dist/PixelFontPC98-12.ttf'); o=f['OS/2']; print('family :', f['name'].getDebugName(1)); print('psname :', f['name'].getDebugName(6)); print('weight :', o.usWeightClass); print('width  :', o.usWidthClass); print('fsel   :', hex(o.fsSelection)); print('fstype :', o.fsType); print('vendor :', o.achVendID)"
# 期望：family : PixelFont PC98 12
#       psname : PixelFontPC98-12
#       weight : 400
#       width  : 5
#       fsel   : 0x40
#       fstype : 0
#       vendor : PXLF

# 2) 确认无可变轴、无 kerning / GSUB / GPOS
python -c "from fontTools.ttLib import TTFont; f=TTFont('dist/PixelFontPC98-12.ttf'); print(sorted(t for t in f.keys() if t in ('fvar','gvar','avar','STAT','HVAR','VVAR','GSUB','GPOS','kern')))"
# 期望：[]

# 3) gasp：禁灰度抗锯齿与网格拟合
python -c "from fontTools.ttLib import TTFont; f=TTFont('dist/PixelFontPC98-12.ttf'); print(f['gasp'].gaspRange)"
# 期望：[(65535, 0)]

# 4) 网格与等宽 advance（1 像素 = 64 单位）
python -c "from fontTools.ttLib import TTFont; f=TTFont('dist/PixelFontPC98-12.ttf'); h=f['hmtx']; print('UPM', f['head'].unitsPerEm); print('half  A advance', h['A'][0]); print('full  U+4E00 advance', h['\u4e00'][0])"
# 期望：UPM 768
#       half  A advance 384
#       full  U+4E00 advance 768

# 5) 代码页覆盖位
python -c "from fontTools.ttLib import TTFont; f=TTFont('dist/PixelFontPC98-12.ttf'); v=f['OS/2'].ulCodePageRange1; print(hex(v), bool(v & (1<<0)), bool(v & (1<<17)), bool(v & (1<<18)))"
# 期望：0x60001 True True True   （bit0 = 1252 / bit17 = 932 / bit18 = 936）

# 6) 确认不存在 Bold / Italic 家族成员
Get-ChildItem dist -Filter '*Bold*'; Get-ChildItem dist -Filter '*Italic*'
# 期望：无输出（当前仅 Regular 单字重家族）

# 7) 产物指纹
Get-FileHash dist/PixelFontPC98-12.ttf -Algorithm SHA256
# 期望：3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1

# 8) 重建 + 8 步门禁
python tools/fontgen/build_font.py
python tools/fontgen/verify_all.py
# 期望：8/8 PASS；回归 0 error 0 warn；对抗审核三轮命中 60/139/19，待裁决 0，确认缺陷 0

# 9) Windows 兼容门禁（全字符集）
python tools/fontgen/verify_gdi.py
# 期望：12ppem 与 24ppem 下全字符集 4161/4161 逐格一致，抗锯齿像素 0

# 10) 生产源自检与参考字体校验（只校验不重下）
python tools/fontgen/vendor_fusion_pixel.py --check
python tools/fontgen/fetch_ref_fonts.py --verify
```

---

## 5. 已知边界与待办

| 编号 | 事项 | 状态 | 下一步 |
|---|---|---|---|
| B1 | 无 Bold（`usWeightClass` 恒 400） | 规划中 / 未实现，**结论：不做** | 若必须强调，走独立家族 + 独立字形设计，禁止程序化加粗 |
| B2 | 无 Italic / Oblique | 规划中 / 未实现，**结论：不做** | 依赖 2.5 逐行错位方案的评估结论，当前不排期 |
| B3 | 无可变字体轴（无 `fvar`/`gvar`） | 规划中 / 未实现，**结论：不做** | 若将来要 `wght`，先做"实例是否落在 12×13 整数网格"的可行性实验 |
| B4 | 固定宽度（`usWidthClass = 5`） | 已实现，长期固化 | 保持；`stretch` 只是排版风格参数，不是轴 |
| B5 | `PixelFont Multi 12` 尚未开工 | 规划中 / 未开工 | 按 2.9 逐层账目 L0–L7 推进，保持"独立家族"形态 |
| B6 | Multi 12 有 4 个码位无 Fusion 覆盖（`U+20AC` `U+2260` `U+2264` `U+2265`） | 已知 | 沿用 MS Gothic / SimHei 非第三源路径 |
| B7 | Multi 12 体积约 7.0 MB（234.0 字节/字粗估） | 待验证 | 实际构建后取真实字节数替换 |
| B8 | 本机安装的仍是 10-23 旧版（1,362,480 字节，sha256 `FCC65BCBCD8A1A022007065E3444464916EDB537BB172B6F2ACDC9596DE3303B`） | 已知 | 覆盖安装 v1.0.0 后重跑 Word 路径验证 |
| B9 | 参考字体（Ark Pixel / Fusion Pixel）的字重覆盖情况 | 待验证 | 验证方法：fontTools 读 `vendor/fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans-subset.ttf` 的 `OS/2.usWeightClass` |
| B10 | Bold 的粘连/墨迹影响未量化 | 待验证 | 验证方法：用 `bitfont.ink_ratio()` / `count_runs()` / `count_holes()` 对 Regular 与 Bold 位图重算连通笔画数与孔洞数 |
| B11 | 源字体（MS Gothic）是否提供斜体样式 | 待验证 | 验证方法：fontTools 读 `C:\Windows\Fonts\msgothic.ttc` 的 `OS/2.fsSelection` |
| B12 | `OS/2.version`、`ulCodePageRange2`、`name` ID 2/3/4/5/13/14/16/17 具体字符串 | 待验证 | 验证方法：fontTools 逐字段读取 `OS/2` 与 `name` 表 |
| B13 | 12px 层面只有 2 票参考（Ark / Zpix）；引入 Ark 作生产源后 Ark 票变自证，目视复核参考列已改为 Zpix + Unifont | 已知 | 维持参考列独立性 |
| B14 | 无 Arabic / Hebrew / Devanagari / Thai 的 12px 点阵源（仅 Unifont 16×16，塞不进 12px 格） | 已知边界 | 不在本家族覆盖范围 |
| B15 | 成品字形派生自 SimHei / MS Gothic（微软专有），`dist/` 不入库；仓库 `LICENSE` = GNU AGPL-3.0，`vendor/` Fusion = OFL-1.1（三份许可随附） | 已知 | 发布 zip 需携带许可说明（现有 zip 内 `安装与使用说明.md` 6,434 字节） |

---

*本文所有数值均来自统一事实底稿（仓库 `E:\PixelFont` @ `4300fc1`）；底稿未覆盖者一律标注「待验证」并附验证方法，未作任何推算性断言。*
