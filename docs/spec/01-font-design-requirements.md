# 01. 字体设计需求规格书

> PixelFont 12 份设计规格文档中的第 1 份。
> 事实底稿：`C:\Users\leo19\AppData\Local\Temp\pf_facts_v2.md`（2026-10-24 核实版）。
> 仓库：`E:\PixelFont`（GitHub https://github.com/UlyssesLeoLee/PixelFont ，**PUBLIC**），当前 HEAD `4300fc1`。
> 本文中每个数值均给出可追溯来源（仓库文件路径 / 命令 / commit / 报告文件）；底稿未覆盖的数字标「待验证」并给出验证方法，不做推断性补写。

---

## 结论先行

**PixelFont PC98 12 是一个 12 × 13 像素设计网格的 PC-98 / 98 时代等宽点阵字体，定位是「Windows + Word 上的中日文正文排版字体」，当前已完成 v1.0.0 正式发布**（注解 tag 在 `main`，GitHub Release `draft=false`，5 个附件，回下载已逐字节校验）。它最可靠的部分是 **GDI 渲染路径**：12ppem（9pt）与 24ppem（18pt）下**全字符集 4161 / 4161 逐格一致、抗锯齿像素 0**（`tools/fontgen/verify_gdi.py`，报告 `reports/gdi_compat.json` + `reports/gdi_raster_scan.tsv` 4,162 行）。它最不可靠的部分也是渲染：**只有 12 的整数倍字号（12 / 24 / 36 ppem @96dpi）能逐格还原设计**，非整数倍（如 18ppem = 1.5×）笔画断裂、墨迹量偏细 43%。

因此本字体的适用边界必须写清楚三条判断：

1. **在 Windows / Word 上可用**，这是它的主场；**在 FreeType 小字号下有已知偏差** —— Pillow / Chrome / Linux 路径 12px 平均偏差 **19.00 px/字**（最坏 44），24px 及以上偏差 0，故它不是「Linux 12px 通用点阵方案」的候选。
2. **字符集是窄的**：当前家族仅 **4,161 码位**（ASCII 95 + 标点符号 56 + 假名 255 + GB2312 一级汉字 3,755，去重后）。**Hebrew / Arabic / Devanagari / Thai 明确不覆盖** —— 这些只有 GNU Unifont 16.0.01 的 16×16 点阵源，塞不进 12px 格（12px 层面唯一可用的方案 C 只覆盖 Latin / Greek / Cyrillic / Hangul / Kana / CJK）。
3. **形态是单一的**：仅 **Regular** 单一字重，无 Bold / Italic / 可变轴，无 kerning、无连字，除 `gasp` 外无 OpenType 特性；且成品字形派生自 **SimHei / MS Gothic（微软专有）**，故 `dist/` **不入库**，仓库 `LICENSE` 为 **GNU AGPL-3.0**（覆盖 `tools/fontgen/` 代码）。

多语言版 **`PixelFont Multi 12`（31,392 码位）尚未开工**，形态为**新增独立家族**，不动现有 `PixelFont PC98 12`。本文所有「需求」条目均按 **已满足 / 部分满足 / 未满足** 三态标注，不留模糊表述。

---

## 1. 范围与目的

### 1.1 目的

| 项 | 内容 |
|---|---|
| 文档目的 | 定义 PixelFont 的**需求侧**规格：字体用途、目标用户、支持语言、风格、字重、使用场景，以及支撑这些需求的技术约束、兼容性与非功能要求 |
| 文档性质 | 需求规格说明书（Requirements Specification），不是实现说明，也不是测试报告 |
| 需求来源 | 统一事实底稿 v2（2026-10-24 核实），对应仓库 `E:\PixelFont` HEAD `4300fc1` |
| 需求基线 | `PixelFont PC98 12` v1.0.0（已发布）；多语言版 `PixelFont Multi 12` 处于**已拍板方向、未开工**状态 |
| 判定口径 | 「已满足」= 当前产物实测通过；「部分满足」= 主路径通过但存在已知限制或未覆盖子集；「未满足」= 能力不存在或未实现 |
| 编号约定 | 需求条目在第 3 章以 `AC-xx` 给出可量化判据，并回指本文的章节与底稿来源 |

### 1.2 适用范围

**范围内**

- 家族 `PixelFont PC98 12`（name ID 1 / 16），PostScript 名 `PixelFontPC98-12`，achVendID `PXLF`。
- 字符集：4,161 码位（ASCII + 标点/符号 + 假名 + GB2312 一级汉字）。
- 度量与网格：12 × 13 设计网格、UPM 768、1 像素 = 64 单位、ascent 11 / descent 2、advance 半角 6 / 全角 12。
- 轮廓生成规则：每像素一矩形、non-zero 环绕规则、竖向游程合并（v1.0.0 起）。
- 渲染行为：FreeType MONO 目标栅格化；GDI 12 / 24ppem 全字符集逐格一致。
- 平台与许可要求、Windows / Word 兼容要求、体积 / 可复现性 / 仓库政策等非功能要求。

**范围外（明确不在本文覆盖范围）**

| 排除项 | 理由 / 归属 |
|---|---|
| `PixelFont Multi 12` 的实现细节（31,392 码位逐层账目、中日字形差异等） | 属于多语言版独立规格文档；本文仅在 2.3 引用其覆盖口径 |
| Hebrew / Arabic / Devanagari / Thai 的字形设计 | **不做** —— 无 12px 点阵源，12px 格塞不进 Unifont 16 的 16×16 网格 |
| Bold / Italic / 可变字体轴的字形设计与制作 | **不做**（当前为单字重路线） |
| kerning、连字、GSUB / GPOS 特性设计（`locl` 变体机制等） | **不做**（除 `gasp` 外无 OpenType 特性；`locl` 方案在多语言版决策中**未选**） |
| 字体打包分发授权（成品再分发） | 成品派生自专有字体，**不可再分发**；本文只规定仓库政策 |
| 源字体的许可谈判与合规审查 | 属法律事务，不在本文范围 |
| 变量字体的 WWS / 字体打包格式 | 不做 |

### 1.3 读者

| 读者 | 读本文的目的 |
|---|---|
| 字体设计 / 实现者 | 明确网格、度量、字符集边界与轮廓生成规则，避免实现漂移 |
| 工具链维护者 | 明确 `tools/fontgen/` 下各脚本的职责与门禁判据 |
| QA / 验收者 | 以第 3 章 `AC-xx` 与第 4 章命令作为验收清单 |
| 项目负责人 / 排版决策者 | 依据「已满足 / 部分满足 / 未满足」判断能力边界与下一步取舍 |
| 文档维护者 | 确认所有数值均可追溯至底稿来源 |

### 1.4 术语

| 术语 | 含义 |
|---|---|
| UPM | Units Per Em，字体设计单位。本字体 **768** |
| 像素 / px | 设计网格像素，12 × 13 网格 |
| 码位 / codepoint | Unicode 码位，本字体以码位计规模（4,161） |
| ppem | pixels per em，请求渲染的每 em 像素数 |
| advance | 字形前进宽度，本字体半角 **6** / 全角 **12** |
| em 方框 | 字体的 em 参照方框；本字体**按字宽 12 取**，而非 cell 高 13 |
| ascent / descent | 基线上 / 下方距离，本字体 **11 / 2**，cell 高 **13** |
| cmap | 字符到字形的映射表 |
| OS/2 | OpenType 字体元数据表（本字体含 `ulCodePageRange1`、`fsSelection`、`ulUnicodeRange1`–`4`、`gasp` 等） |
| code page | 代码页；本字体 `ulCodePageRange1` = 1252 + 932 + 936 |
| GDI | Windows 传统图形设备接口，Windows / Word 的文字渲染路径，1-bit 输出 |
| FreeType | 跨平台字体栅格化库，Pillow / Chrome / Linux 常用 |
| MONO | 单色栅格化目标（`FT_LOAD_TARGET_MONO`），等同 GDI 1-bit 文字 |
| 抗锯齿 / AA | 灰度平滑边缘像素；本字体在 GDI 路径下实测为 **0** |
| hinting | 网格拟合提示信息；本字体以 12 整数倍字号精确还原，不依赖 hinting |
| gasp | OS/2 内的字形抗锯齿/网格拟合策略表；本字体为 `{0xFFFF: 0}`，即禁 DOGRAY / GRIDFIT |
| non-zero 环绕规则 | 轮廓填充规则；本字体所有矩形同向绕向，靠 non-zero 填充得到像素并集 |
| 竖向游程合并 | 把竖向相邻、x 范围相同的水平游程合并为单个矩形；v1.0.0 起启用 |
| strike | EBDT / EBLC 中的内嵌位图尺寸档位 |
| EBDT / EBLC | 内嵌位图（EBDT）与位图位置表（EBLC） |
| kerning | 字距调整；本字体**无** |
| locl / GSUB / GPOS | OpenType 特性；本字体除 `gasp` 外**均无**，`locl` 变体方案在多语言版决策中**未选** |
| `dist/` / `vendor/` / `third_party/` | 仓库目录政策：产物 / 入库生产源 / 参考字体（不入库） |

---

## 2. 正文

### 2.1 字体用途与定位

| 维度 | 规格 | 来源 |
|---|---|---|
| 字体类别 | 像素点阵（bitmap）**等宽**字体，PC-98 / 98 时代点阵美学 | 底稿 §2、§13 |
| 家族名 | `PixelFont PC98 12`（name ID 1 / 16） | 底稿 §1 |
| PostScript 名 | `PixelFontPC98-12` | 底稿 §1 |
| achVendID | `PXLF` | 底稿 §1 |
| 设计网格 | 12 × 13 像素（宽 × 高），12px 等宽 | `tools/fontgen/build_font.py` |
| 基线 | ascent 11 / descent 2，基线在第 11 行下方（cell 第 12 行），cell 高 13 | `tools/fontgen/bitfont.py`（`cell_ascent` / `cell_descent`） |
| advance | 半角 **6** / 全角 **12**（= 12px 宽的一半与整宽） | 底稿 §2 |
| UPM | **768**；1 像素 = **64** 单位（768 / 12 = 64） | `build_font.py`（`UPM` 常量、`px = UPM // cell_w`） |
| em 方框 | **按字宽 12 取，不是 cell 高 13** | 底稿 §2（按 13 除会让 12ppem 下每像素落在 0.923 个设备像素上，整副字糊掉） |
| 轮廓模型 | 每个像素 → 一个矩形轮廓；所有矩形同向绕向，non-zero 环绕规则填充 | `build_font.py::_emit_rect()` |
| 竖向游程合并 | v1.0.0 起合并：轮廓数 107,209 → **73,933**（-31%）；TTF 1,364,528 → **973,712 字节**（-28.6%）；整数倍精确性不变（**12,483 / 12,483**） | `build_font.py::_merge_vertical_runs()` |
| 字符集规模 | **4,161 码位** | `tools/fontgen/charset.py::build_charset()` |
| 主要目标平台 | **Windows / Word**（GDI 路径）优先；FreeType 路径次之 | 底稿 §8 |
| 精确显示字号 | 12 的整数倍：12ppem (9pt)、24ppem (18pt)、36ppem (27pt) @96dpi | `docs/word-compat.md` §7.6 |
| 版本状态 | **v1.0.0 已发布**（tag 在 `main`，Release `draft=false`，5 个附件） | 底稿 §11 |
| 关联家族 | `PixelFont Multi 12`（**独立家族**，计划中尚未开工，31,392 码位） | 底稿 §13 |
| 命名与提交规范 | 文档中文正文 + 英文技术术语保留原名；提交信息 `docs(spec): <主题>`；`dev` 为集成分支、`main` 为发布镜像，二者零分叉、`--ff-only` 快进 | 底稿 §0 |

### 2.2 目标用户与典型使用场景

| 用户类型 | 场景 | 核心诉求 | 现状满足度 |
|---|---|---|---|
| Windows + Word 中文长文编辑者 | 正文以 9pt / 18pt 显示的文档 | 点阵不糊、逐格还原、与设计稿一致 | **已满足** —— GDI 12ppem / 24ppem 全字符集 **4161 / 4161 逐格一致**，抗锯齿像素 **0** |
| Word 字体对话框使用者 | 在字体列表中检索并选用本字体 | 字体能被 Word 识别并选用 | **已满足**（曾有「装了却用不上」的根因：旧 `ulCodePageRange1 = 0x00030000` 实为 bit16(874) + bit17(932)，既无 1252 也无 936；`fsSelection` 为 0x0000 缺 REGULAR）—— 已由 commit `cef4a22` 修复，见 2.7 |
| 中文简报 / 文档排版者 | GB2312 一级字常用范围 | 常用汉字不缺字 | **已满足** —— GB2312 一级 **3,755** 字机械推导覆盖（区位 16–55 区，`0xB0A1`–`0xD7F9`） |
| 日文 PC-98 风格排版爱好者 | 假名 + 汉字混排 | 假名齐全、全角等宽对齐 | **部分满足** —— 假名覆盖平假名 `U+3041`–`U+309F`、片假名 `U+30A0`–`U+30FF`、半角片假名 `U+FF61`–`U+FF9F` 及 `々 〆 〇 ヶ ー ～`（去重后 **255** 码位）；但**日式汉字变体不覆盖**（见 2.3） |
| 终端 / 代码阅读者 | 12px 等宽 Latin 文本 | 固定 advance、网格对齐、不抖动 | **部分满足** —— advance 半角 6 / 全角 12 固定；但仅 12 整数倍字号精确（FreeType 12px 平均偏差 **19.00 px/字**） |
| Linux / Chrome / Pillow 图形渲染者 | 把文本渲染成点阵图像或网页文字 | 与设计稿逐格一致 | **未满足（12px 场景）** —— FreeType 12px 平均偏差 **19.00 px/字**（最坏 44），24px 及以上偏差 **0** |
| 非 CJK 语系用户（阿拉伯 / 希伯来 / 天城文 / 泰文） | 多语种正文 | 覆盖本族文字 | **未满足** —— 无 12px 点阵源；仅 Unifont 16（16×16 网格），塞不进 12px 格 |
| 需要 Bold / Italic 的排版者 | 强调、标题、注释等 | 多字重与斜体 | **未满足** —— 单字重 Regular，无 Bold / Italic / 可变轴 |
| 二次分发者（在自己的产品中嵌入字体） | 随产品分发给终端用户 | 可再分发的许可 | **未满足** —— 成品字形派生自 SimHei / MS Gothic（微软专有），`dist/` 不入库 |
| 字体设计 / 工具链维护者 | 改字表、加字重、调网格 | 单一事实来源、可复现构建 | **已满足** —— `tools/fontgen/` 8 步门禁 `verify_all.py` 最近一次 **8/8 PASS** |

### 2.3 支持语言与字符集需求

**当前家族（4,161 码位）构成**：ASCII 95（`U+0020`–`U+007E`）+ 标点/符号 56（`charset.extras()`）+ 假名 255（`charset.kana_chars()`）+ 汉字 3,755（GB2312 一级，机械推导）。源列表合计 **4,164**（95 + 56 + **258** + 3,755），去重后 **4,161**；重复的 3 个字符为 `ヶ` U+30F6、`ー` U+30FC、`～` U+FF5E（假名表与符号表各出现一次）。2026-10-24 另补入 **21 个** Word 常用字符：弯引号 `“ ” ‘ ’`、全角空格 `U+3000`、NBSP `U+00A0`、`– • ‧`、`¥ ° ½`、`€ →`、`≠ ≤ ≥`、`［ ］ ｛ ｝`。

| 语系 / 区块 | 当前 `PixelFont PC98 12`（4,161 码位）覆盖情况 | `PixelFont Multi 12`（31,392 码位，方案 C）覆盖情况 | 状态 |
|---|---|---|---|
| 拉丁 ASCII（`U+0020`–`U+007E`） | **95 码位全覆盖** | 95（含于 L0） | **已满足** |
| 拉丁补充符号（`extras()`） | **56 码位**（含 `U+00A0`、`U+00A5`、`U+20AC`、`U+2260`、`U+2264`、`U+2265` 等）；该表以 `charset.extras()` 明列为准，**未声明整段 Latin-1 覆盖** | 随 L0 保留 | **部分满足**（边界由 `charset.extras()` 界定） |
| 拉丁扩展 A/B（`U+0100`–`U+024F`） | **未覆盖** | L1 **+241**（∩ Fusion latin），累计 4,402 | **未满足**（当前）／**已满足**（多语言版） |
| 希腊文（`U+0370`–`U+03FF`） | **未覆盖** | L2 **+99**，累计 4,501 | **未满足**／**已满足** |
| 西里尔文（`U+0400`–`U+04FF`） | **未覆盖** | L3 **+151**，累计 4,652 | **未满足**／**已满足** |
| 谚文音节（`U+AC00`–`U+D7AF`） | **未覆盖** | L4 **+11,172**（∩ Fusion ko），累计 15,824 | **未满足**／**已满足** |
| 假名（平 `U+3041`–`U+309F` / 片 `U+30A0`–`U+30FF` / 半角片 `U+FF61`–`U+FF9F` + `々 〆 〇 ヶ ー ～`） | **255 码位**；**明确排除** `U+3097 ゗`、`U+3098 ゘`（古旧假名合字，非 JIS 字集，MS Gothic 无此字形） | L0 保留 + L5 **+1,695**（JIS X 0208 假名/符号/全角，∩ Fusion ja），累计 17,519 | **已满足**（当前）／**已满足**（多语言版，含 JIS 扩展） |
| 汉字（GB2312 一级） | **3,755 码位全覆盖**（机械推导，非凭记忆列表） | L0 保留；与 JIS 共享 **2,078** 字按**中文形为主**（zh_hans 源） | **已满足** |
| 汉字（JIS X 0208 独有） | **未覆盖** | L6 **+2,297**（走 ja 源），累计 19,816 | **未满足**／**已满足** |
| 汉字（U+4E00–`U+9FFF` 其余） | **未覆盖** | L7 **+11,576**，累计 **31,392** | **未满足**／**已满足** |
| **Hebrew（希伯来文）** | **不覆盖** | **不覆盖** | **未满足（明确不做）** —— 12px 层面唯一来源 Unifont 16 是 16×16 网格，塞不进 12px 格 |
| **Arabic（阿拉伯文）** | **不覆盖** | **不覆盖** | **未满足（明确不做）** —— 同上 |
| **Devanagari（天城文）** | **不覆盖** | **不覆盖** | **未满足（明确不做）** —— 同上 |
| **Thai（泰文）** | **不覆盖** | **不覆盖** | **未满足（明确不做）** —— 同上 |
| 谚文字母 / 假名扩展（Unifont 16 独有） | **未覆盖** | **不覆盖**（属方案 B，**未选**） | **未满足（明确不做）** |
| Unifont 16 独有总计 | — | 方案 B 未选部分合计 **896**（谚文字母 256 + 假名扩展 16 + 希伯来 112 + 阿拉伯 256 + 天城文 128 + 泰文 128） | **未满足（明确不做）** |
| 多语言版覆盖缺口（已拍板路径） | — | Fusion 七变体 cmap 并集 **37,415**；方案 C 的 31,392 中 **4 个码位**不被任何 Fusion 变体覆盖：`U+20AC €`、`U+2260 ≠`、`U+2264 ≤`、`U+2265 ≥`（这 4 个在当前家族已有，走 MS Gothic / SimHei 非第三源路径） | **已满足**（路径已确定） |

> 补充事实：GB2312 一级 3,755 与 JIS X 0208 汉字 4,375 的**交集为 2,078**（中日共享），JIS 独有 2,297、GB 独有 1,677；Fusion ja / zh_hans 对 2,078 / 2,297 / 1,677 三组均 **100% 覆盖**，JIS 独有 2,297 字在 Fusion ja 源中 **2,297 / 2,297 全部有墨迹**。中日字形分歧真实存在：在 2,078 个共享汉字上，Fusion ja 与 zh_hans **像素完全相同 1,644 / 2,078（79.1%）**、**像素不同 434 / 2,078（20.9%）**，最大异或格数 78（`肩` U+80A9）。这正是「中文形为主 + JIS 独有走 ja 源」策略的依据。

### 2.4 风格与气质需求

| 需求项 | 规格 | 满足度 | 来源 / 判据 |
|---|---|---|---|
| 时代风格锚点 | **PC-98 / 98 时代等宽点阵**：严格 12px 等宽、硬边、无灰度过渡 | **已满足** | 底稿 §2；GDI 12ppem / 24ppem 抗锯齿像素 **0** |
| 像素风（硬边单色） | 轮廓为纯矩形并集，栅格化走 **MONO** 目标，输出 0/255 单色 L 图 | **已满足** | `FT_LOAD_TARGET_MONO`；`gasp = {0xFFFF: 0}`（禁 DOGRAY / GRIDFIT） |
| 等宽度量 | 半角 **6**、全角 **12**，全角恰为半角两倍 | **已满足** | 底稿 §2 |
| 网格对齐 | 12 × 13 设计网格，ascent 11 / descent 2，基线在第 11 行下方 | **已满足** | `bitfont.py`（`cell_ascent` / `cell_descent`） |
| 笔画完整性 | 竖向游程合并，保证非整数倍缩放时笔画不裂成虚线 | **已满足** | 轮廓数 107,209 → **73,933**（-31%），TTF **973,712 字节**（-28.6%），整数倍精确性 **12,483 / 12,483** 不变 |
| 笔画像素比 / 孔洞数 | 作为字形质量监控量（`ink_ratio()` / `count_holes()` / `count_runs()`） | **已满足**（监控用） | `tools/fontgen/bitfont.py` |
| 参考一致性的独立票 | 12px 层面只有 **2 票**（Ark / Zpix）；引入 Ark 作生产源后 Ark 票变自证，目视复核参考列已改为 **Zpix + Unifont** | **部分满足**（独立票数量有限） | 底稿 §5；Unifont 因 16px **不参与 12px 笔画数比对** |
| 气质一致性判据 | 参考集（Zpix + Unifont）与生产源独立比对 | **部分满足** —— 硬检查命中 71（warn 69 / error 2，参考集分歧），对抗式审核三轮 60 / 139 / 19 命中，待裁决 0，已裁决非缺陷 169，**确认缺陷 0** | `tools/fontgen/verify_all.py` 步骤 4 / 7 |

### 2.5 字重与样式需求

| 需求项 | 现状 | 缺口 | 拟议方案 |
|---|---|---|---|
| 常规体（Regular） | **已满足** —— 唯一字重 Regular；OS/2 `fsSelection = 0x0040`（REGULAR），commit `cef4a22` 修复（此前为 0x0000 缺 REGULAR，Windows 可能不把它当正文常规字）。规格记作 Regular 400，`OS/2.usWeightClass` 字段实测值**待验证** —— 验证方法：用 fontTools 读取 `dist/PixelFontPC98-12.ttf` 的 `OS/2` 表并打印 `usWeightClass` | 无（唯一既有字重） | 保持现状；`usWeightClass` 补一次实测并回写本文 |
| 粗体（Bold） | **未满足** —— 无 | 无 Bold 字重 | **未决**。12px 网格下加粗策略（外描边 / 人工加粗字表）需单独立项；GDI 合成加粗会破坏点阵，不作为方案 |
| 斜体（Italic） | **未满足** —— 无 | 无斜体字形 | **未决**。12 × 13 网格无斜体空间，人工倾斜会破坏网格对齐 |
| 可变字体轴（如 `wght`） | **未满足** —— 无 variable font 轴 | 无轴 | **未决**。12px 点阵的可变轴收益有限，优先级最低 |
| 合成粗体 / 合成斜体 | **未满足** —— 不提供 | 依赖渲染器合成 | 不支持；须在安装说明中显式声明，避免用户误用后出现笔画糊化 |
| 小型大写（small caps）/ 分数等 OpenType 特性 | **未满足** —— 除 `gasp` 外无 GSUB / GPOS | 无特性表 | **未决**；与多语言版「`locl` 未选」的决策取向一致（先不引入 OpenType 特性层） |
| kerning / 连字 | **未满足** —— 无 | 无字距调整 | **未决**；等宽点阵字体中 kerning 会破坏列对齐，默认不做 |

### 2.6 技术约束需求

| 约束 | 数值 | 依据 |
|---|---|---|
| 设计网格 | **12 × 13 像素**（宽 × 高），12px 等宽，PC-98 风格 | 底稿 §2；`build_font.py` |
| UPM | **768** | 底稿 §2；`build_font.py`（`UPM` 常量） |
| 像素 → 单位换算 | **1 像素 = 64 单位**（768 / 12 = 64） | `build_font.py`（`px = UPM // cell_w`） |
| em 方框基准 | **按字宽 12 取，不是 cell 高 13** | 底稿 §2：按 13 除会让 12ppem 下每像素落在 0.923 个设备像素上，整副字糊掉 |
| 基线与 cell 高 | ascent **11** / descent **2**，基线在第 11 行下方（cell 第 12 行），cell 高 **13** | `bitfont.py`（`cell_ascent` / `cell_descent`） |
| advance | 半角 **6** / 全角 **12** | 底稿 §2 |
| 栅格化目标 | **FreeType MONO**（`FT_LOAD_TARGET_MONO`），输出 0 / 255 单色 L 图 | 底稿 §8：Pillow 默认灰度抗锯齿再二值化会得到「缩小的矢量字体」而不是点阵 |
| 精确显示条件 | **只有 12 的整数倍字号精确**：12ppem (9pt)、24ppem (18pt)、36ppem (27pt) @96dpi | `docs/word-compat.md` §7.6 |
| 非整数倍行为（已知代价） | 18ppem（1.5×）下笔画断裂 + 墨迹量偏细 **43%** | `docs/word-compat.md` §7.6 |
| 轮廓生成 | 每像素 → 1 个矩形；所有矩形同向绕向；non-zero 环绕规则填充 | `build_font.py::_emit_rect()` |
| 竖向游程合并 | v1.0.0 起合并竖向相邻、x 范围相同的水平游程：轮廓数 **107,209 → 73,933**；TTF **1,364,528 → 973,712 字节**；整数倍精确性 **12,483 / 12,483** 不变 | `build_font.py::_merge_vertical_runs()` |
| 源例外通道 | `charset.SOURCE_OVERRIDES` 用于「源字体语系惯例」问题（`U+005C` 反斜杠切到 fusion，因 MS Gothic 按 JIS 惯例把 `U+005C` 画成 `¥`，与其 `U+00A5` 整格逐字节相同）；`ideo_route.json` 只管汉字（**3,010** 条路由记录） | `charset.py`、`bitfont.py::ScriptStack` |
| 字符集去重 | 源列表 4,164 → 去重 **4,161**；重复 3 个：`ヶ` U+30F6、`ー` U+30FC、`～` U+FF5E | `charset.py::build_charset()` |
| 汉字来源纪律 | GB2312 一级（区位 16–55 区，`0xB0A1`–`0xD7F9`）**机械推导**，禁止凭记忆列字表 | `charset.py::gb2312_level1()` |
| 排除清单 | `charset.EXCLUDE` = `U+3097 ゗`、`U+3098 ゘`（古旧假名合字，非 JIS 字集，MS Gothic 无此字形） | `charset.py::EXCLUDE` |
| 代码页覆盖 | `ulCodePageRange1 = (1<<0) \| (1<<17) \| (1<<18)` = **1252 + 932 + 936**（Latin-1 / Shift-JIS / GB2312） | commit `cef4a22`；`build_font.py::verify_ttf_metadata()` |
| fsSelection | `0x0040`（REGULAR） | commit `cef4a22` |
| Unicode 区段位 | `ulUnicodeRange1`–`4` **不手写**，由 fontTools 按 cmap 实际覆盖重算 | commit `cef4a22`（手写查表会再次出错） |
| gasp | `{0xFFFF: 0}`，禁 DOGRAY / GRIDFIT | commit `cef4a22` |
| 元数据硬门禁 | `verify_ttf_metadata()` 硬拦四组不变量：代码页位 / fsSelection / Unicode 区段位与 cmap 一致 / gasp 禁 DOGRAY\|GRIDFIT | `build_font.py::verify_ttf_metadata()` |

### 2.7 兼容性与平台需求

| 平台 / 环境 | 渲染路径 | 需求 | 现状 | 满足度 |
|---|---|---|---|---|
| Windows（原生应用） | **GDI**（1-bit 文字） | 12ppem / 24ppem 下全字符集逐格还原，且**无抗锯齿** | **4161 / 4161 逐格一致**，抗锯齿像素 **0**（本机字体平滑开启时也是 0） | **已满足** |
| Microsoft Word | **GDI** | 字体在字体对话框**中英文两栏**都能正常列出并选用 | 旧 `ulCodePageRange1 = 0x00030000` 实为 bit16(874) + bit17(932)，**既无 1252 也无 936**；`fsSelection` 0x0000 缺 REGULAR → 「装了却用不上」根因。已由 commit `cef4a22` 修复为 1252 + 932 + 936 与 `0x0040` | **已满足**（修复后） |
| FreeType（Pillow / Chrome / Linux） | `FT_LOAD_TARGET_MONO` | 12px 下与设计稿逐格一致 | 12px 平均偏差 **19.00 px/字**（最坏 **44**）；24px 及以上偏差 **0** | **部分满足**（12px 未达标，24px+ 达标） |
| 非整数倍字号（任意平台） | 任意 | 笔画不裂、墨迹不偏细 | 18ppem（1.5×）笔画断裂 + 墨迹量偏细 **43%** | **未满足（已知代价，已文档化）** |
| GDI 内嵌位图路线 | EBDT / EBLC | — | GDI **会**采用内嵌位图，但**只在请求字号与 strike 的 ppem 精确相等时**命中（实测 Calibri 的 `A` 在 12 / 15 / 16 / 17 / 19ppem 命中对应 strike，14 / 18 / 20–24ppem 回落到 `glyf` 轮廓），**不会拿最近的 strike 缩放** | 已文档化（`docs/word-compat.md` §7.7） |
| 跨平台字体标识 | name / OS/2 表 | 家族名 `PixelFont PC98 12`、PostScript `PixelFontPC98-12`、achVendID `PXLF` 三者一致可辨 | 与底稿 §1 一致 | **已满足** |
| 字符集来源纪律 | cmap | 汉字集须为 GB2312 一级**机械推导**结果；缺字门禁与路由名单门禁必须在构建期拦截 | `charset.py` 提供 `gate_ideo_route()` / `gate_full_coverage()`，构建期硬拦 | **已满足** |
| 生产源自检 | 第三方源 | Fusion 裁剪版须与原字体**逐像素一致**，且裁剪版 cmap == 原字体 cmap ∩ 本项目字符集 | `tools/fontgen/vendor_fusion_pixel.py --check` 验证 | **已满足** |

> 详细渲染行为证据见 `docs/word-compat.md`（§7.2 全字符集栅格化、§7.5 渲染器相关性、§7.6 只有 12 整数倍精确、§7.7 内嵌位图路线）；逐码位扫描数据见 `reports/gdi_raster_scan.tsv`（4,162 行）与摘要 `reports/gdi_compat.json`（1.5KB）。

### 2.8 非功能需求

| 需求项 | 规格 / 现状 | 来源 |
|---|---|---|
| 成品体积（TTF） | **973,712 字节**（4,161 字，平均 **234.0 字节/字**） | `dist/PixelFontPC98-12.ttf`，sha256 `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1` |
| 其它产物体积 | BDF **665,950** 字节；atlas.png **141,857** 字节；specimen.png **2,977** 字节；atlas.json **87,300** 字节；bdf.map **183,034** 字节；发布 zip **533,116** 字节（sha256 `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8`，内含 **9 项**） | `dist/` |
| 体积演进要求 | 竖向游程合并使 TTF 从 1,364,528 → 973,712 字节（**-28.6%**），整数倍精确性不变 | `build_font.py::_merge_vertical_runs()` |
| 构建可复现性 | `tools/fontgen/verify_all.py` 8 步门禁，最近一次 **8/8 PASS**；全量回归 4,161 字分 **43 批**，0 error 0 warn；产物与源同步检查**独立读 `dist/`** 比对，不靠构建脚本自证 | `tools/fontgen/verify_all.py` |
| 质量审核强度 | 对抗式审核三轮（身份反查 / 部件级结构 / 链条）命中 **60 / 139 / 19**，待裁决 **0**，已裁决非缺陷 **169**，确认缺陷 **0** | `verify_all.py` 步骤 7 |
| 门禁耗时 | 全链路 8 步约 **6 分钟**；Windows 兼容门禁约 **9 秒** | 底稿 §10 |
| 参考源可校验 | `tools/fontgen/fetch_ref_fonts.py`（`--verify` 只校验不重下）；来源、版本、sha256 清单见 `docs/reference-fonts.md` | `docs/reference-fonts.md` |
| 许可证（代码） | 仓库 `LICENSE` = **GNU AGPL-3.0**，覆盖 `tools/fontgen/` | 底稿 §12 |
| 许可证（入库生产源） | `vendor/` 的 Fusion Pixel = **OFL-1.1**，`vendor/fusion-pixel-12px/LICENSES/` 下**三份**许可（`ark-pixel-OFL.txt` / `cubic-11-OFL.txt` / `galmuri-LICENSE.txt`）随附 | 底稿 §4、§12 |
| 许可证（成品） | 成品字形派生自 **SimHei / MS Gothic（微软专有）** → **不可再分发** | 底稿 §12 |
| 仓库政策 | `dist/` **不入库**；`vendor/` **入库**；`third_party/` **不入库**（参考字体不入库，仅用于校验） | 底稿 §0、§5、§12 |
| 入库生产源完整性 | `vendor/fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans-subset.ttf` = **764,748 字节**，sha256 `FC910F23FF8EE2DF8F2FEC6F91381A60DF812E3A16CE177F48528F1DB6551A37` | 底稿 §4 |
| 发布可追溯 | v1.0.0 注解 tag 在 `main`，GitHub Release 正式版（`draft=false`），**5 个附件**（zip / ttf / 2 张说明图 / SHA256SUMS）；资产回下载后**逐字节一致**，且下载回的 TTF 在 GDI 中正常被选中与渲染 | 底稿 §11 |
| 报告留存 | `reports/gdi_compat.json`（摘要 1.5KB）+ `reports/gdi_raster_scan.tsv`（逐码位 4,162 行） | 底稿 §10 |
| 协作与分支规范 | `dev` 集成分支 / `main` 发布镜像，两者零分叉，`--ff-only` 快进；提交信息 `docs(spec): <主题>`；推送走 gh 凭据通道 | 底稿 §0、§11 |
| 多语言版体积预估 | 4,161 字 → 973,712 字节（234.0 字节/字）；方案 C 31,392 字 → 约 **7.0 MB**（按同一均值粗估，实际会因 CJK 字形复杂度不同而偏离） | 底稿 §13.5（**粗估，非实测**） |
| 文档语言规范 | 中文正文，英文技术术语保留原名（hinting / UPM / gasp / cmap / kerning / GSUB / locl / em …） | 底稿 §0、§14 |

---

## 3. 验收判据

| 编号 | 需求条目 | 判据（可量化） | 验证方式（命令或文件路径） |
|---|---|---|---|
| AC-01 | 家族标识唯一且一致 | name ID 1 / 16 = `PixelFont PC98 12`；PostScript = `PixelFontPC98-12`；achVendID = `PXLF` | `python tools/fontgen/build_font.py`；用 fontTools 读取 `dist/PixelFontPC98-12.ttf` 的 `name` 表 |
| AC-02 | 度量与网格 | 设计网格 12 × 13；UPM = 768；1 像素 = 64 单位；ascent 11 / descent 2；advance 半角 6 / 全角 12；em 方框按 **12** 取（非 13） | `tools/fontgen/build_font.py`（`UPM`、`px = UPM // cell_w`）、`tools/fontgen/bitfont.py`（`cell_ascent` / `cell_descent`） |
| AC-03 | 字符集规模与构成 | 去重后 **4,161** 码位 = ASCII 95 + extras 56 + 假名 255 + 汉字 3,755；源列表 4,164；重复仅 `ヶ` U+30F6、`ー` U+30FC、`～` U+FF5E | `tools/fontgen/charset.py::build_charset()`；`verify_all.py` 步骤 2 缺字门禁 |
| AC-04 | 汉字集机械推导 | 汉字集等于 GB2312 一级（区位 16–55 区，`0xB0A1`–`0xD7F9`）的机械推导结果，字数 **3,755** | `charset.py::gb2312_level1()`；`verify_all.py` 步骤 6 路由名单自检 |
| AC-05 | 排除清单 | `U+3097 ゗`、`U+3098 ゘` **不出现**在 cmap 中 | `charset.py::EXCLUDE`；用 fontTools 打印 cmap 键集 |
| AC-06 | GDI 全字符集逐格一致 | 12ppem 与 24ppem 下 **4161 / 4161** 逐格一致 | `python tools/fontgen/verify_gdi.py`（约 9 秒）；`reports/gdi_compat.json`、`reports/gdi_raster_scan.tsv`（4,162 行） |
| AC-07 | GDI 抗锯齿为 0 | 12ppem / 24ppem 抗锯齿像素计数 = **0**（本机字体平滑开启时同样为 0） | `python tools/fontgen/verify_gdi.py`；`reports/gdi_compat.json` |
| AC-08 | OS/2 元数据不变量 | `ulCodePageRange1` = `(1<<0)\|(1<<17)\|(1<<18)`（1252 + 932 + 936）；`fsSelection` = `0x0040`；`ulUnicodeRange1`–`4` 与 cmap 实际覆盖一致；`gasp` = `{0xFFFF: 0}` 且不含 DOGRAY / GRIDFIT | `build_font.py::verify_ttf_metadata()`（硬拦）；commit `cef4a22` |
| AC-09 | 12 整数倍字号精确 | 12ppem(9pt)、24ppem(18pt)、36ppem(27pt) @96dpi 下逐格还原；整数倍精确性计数 **12,483 / 12,483** | `tools/fontgen/verify_all.py` 步骤 2；`docs/word-compat.md` §7.6 |
| AC-10 | 非整数倍偏差已知 | 18ppem（1.5×）下笔画断裂 + 墨迹量偏细 **43%**（已知限制，须文档化） | `docs/word-compat.md` §7.6 |
| AC-11 | FreeType MONO 栅格化 | 输出为 0 / 255 单色 L 图（非灰度抗锯齿后二值化） | `verify_all.py` 栅格化实现；`build_font.py` 栅格路径 |
| AC-12 | FreeType 尺寸行为 | 12px 平均偏差 **19.00 px/字**（最坏 44）；24px 及以上偏差 **0** | `verify_all.py` 步骤 4 字形硬检查 + FreeType 扫描；`docs/word-compat.md` §7.5 |
| AC-13 | 竖向游程合并生效 | 轮廓数 **73,933**（合并前 107,209）；TTF **973,712 字节**（合并前 1,364,528）；整数倍精确性不变 | `build_font.py::_merge_vertical_runs()`；构建日志与产物字节数 |
| AC-14 | 字体选择路径可用 | Word 字体对话框**中英文两栏**均可列出并选用本字体 | `python tools/fontgen/verify_gdi.py`（Windows 兼容性门禁，步骤 8） |
| AC-15 | 入库生产源完整性 | `vendor/fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans-subset.ttf` = **764,748 字节**，sha256 `FC910F23FF8EE2DF8F2FEC6F91381A60DF812E3A16CE177F48528F1DB6551A37`；三份许可文件随附 | `python tools/fontgen/vendor_fusion_pixel.py --check`；`vendor/fusion-pixel-12px/LICENSES/` |
| AC-16 | 生产源裁剪一致性 | 裁剪前后**逐像素一致**，且裁剪版 cmap == 原字体 cmap ∩ 本项目字符集 | `python tools/fontgen/vendor_fusion_pixel.py --check`（`verify_all.py` 步骤 1） |
| AC-17 | 反斜杠源例外 | `U+005C` 走 fusion 源，渲染为反斜杠而**不是** `¥`；与 `U+00A5` 不整格相同 | `charset.py::SOURCE_OVERRIDES`；`bitfont.py::ScriptStack` 的 `overrides` 通道 |
| AC-18 | 汉字路由规模 | `ideo_route.json` 路由记录 **3,010** 条，且名单自检按名单自述输入重新推导后一致 | `charset.py::gate_ideo_route()` / `gate_full_coverage()`；`verify_all.py` 步骤 6 |
| AC-19 | 全链路门禁 | `verify_all.py` 最近一次 **8/8 PASS**；回归 0 error 0 warn（4,161 字分 43 批）；硬检查命中 71（warn 69 / error 2）；对抗审核三轮 60 / 139 / 19，待裁决 0，确认缺陷 0 | `python tools/fontgen/verify_all.py`（约 6 分钟） |
| AC-20 | 产物与源同步 | 独立读 `dist/` 与当前源逐字比对一致（不依赖构建脚本自证） | `verify_all.py` 步骤 5 |
| AC-21 | 参考字体可校验 | 参考字体 sha256 与清单一致；`--verify` 只校验不重下；参考列 = **Zpix + Unifont**（Ark 因成为生产源而转自证） | `python tools/fontgen/fetch_ref_fonts.py --verify`；`docs/reference-fonts.md` |
| AC-22 | 产物体积与哈希 | `dist/PixelFontPC98-12.ttf` = **973,712 字节**，sha256 `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1`；zip = **533,116 字节**，sha256 `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8`，内含 **9 项** | `Get-FileHash` / `sha256sum`；`unzip -l`（见第 4 章） |
| AC-23 | 仓库政策 | `dist/` **不入库**；`vendor/` **入库**；`third_party/` **不入库** | `git ls-files` 检查三个目录；仓库 `LICENSE` = GNU AGPL-3.0（覆盖 `tools/fontgen/`） |
| AC-24 | 发布可追溯 | v1.0.0 tag 在 `main`；GitHub Release `draft=false`；**5 个附件**；资产回下载后逐字节一致，且下载回的 TTF 在 GDI 中可被选中与渲染 | `gh release view`；底稿 §11 回下载校验记录 |
| AC-25 | 多语言版范围边界 | 方案 C = **31,392 码位**，以**新增独立家族** `PixelFont Multi 12` 实现，不改动现有家族；Hebrew / Arabic / Devanagari / Thai **不覆盖** | 底稿 §13；逐层账目 L0–L7 与交叉核对（A = 19,816；CJK 整块 19,317；并集 31,392） |
| AC-26 | 单字重边界 | 仅 Regular 一个字重；无 Bold / Italic / 可变轴；无 kerning / 连字；除 `gasp` 外无 OpenType 特性 | `tools/fontgen/build_font.py` 产物表检查（`OS/2` / `GSUB` / `GPOS`） |
| AC-27 | 字重字段实测 | `OS/2.usWeightClass` 实测值**待验证** —— 验证方法：用 fontTools 读取 `dist/PixelFontPC98-12.ttf` 的 `OS/2` 表并打印 `usWeightClass`；结果回写本文 2.5 | 待验证（本文 2.5 已标注） |

---

## 4. 复现命令

以下命令均在 `E:\PixelFont`（HEAD `4300fc1`）下执行。注释中给出**期望输出**。

### 4.1 PowerShell

```powershell
# 1) 重建字体 —— 期望：生成 dist/PixelFontPC98-12.ttf 等产物，缺字门禁 / 路由名单门禁 / 元数据不变量全部通过
cd E:\PixelFont; python tools/fontgen/build_font.py

# 2) 全链路 8 步验收（约 6 分钟）
#    期望：8/8 PASS；回归 0 error 0 warn（4,161 字分 43 批）；
#          硬检查命中 71（warn 69 / error 2）；对抗审核三轮 60/139/19，待裁决 0，已裁决非缺陷 169，确认缺陷 0
cd E:\PixelFont; python tools/fontgen/verify_all.py

# 3) Windows 兼容门禁（全字符集，约 9 秒）
#    期望：12ppem / 24ppem 全字符集 4161/4161 逐格一致，抗锯齿像素 0
#    产物：reports/gdi_compat.json（摘要 1.5KB）+ reports/gdi_raster_scan.tsv（逐码位 4,162 行）
cd E:\PixelFont; python tools/fontgen/verify_gdi.py

# 4) 参考字体：抓取 / 只校验
#    期望：sha256 与 docs/reference-fonts.md 清单一致（--verify 不重下）
cd E:\PixelFont; python tools/fontgen/fetch_ref_fonts.py
cd E:\PixelFont; python tools/fontgen/fetch_ref_fonts.py --verify

# 5) 生产源裁剪：重裁 / 只校验
#    期望：裁剪前后逐像素一致 + 裁剪版 cmap == 原字体 cmap ∩ 本项目字符集
cd E:\PixelFont; python tools/fontgen/vendor_fusion_pixel.py
cd E:\PixelFont; python tools/fontgen/vendor_fusion_pixel.py --check

# 6) 产物哈希核对
#    期望：
#      dist/PixelFontPC98-12.ttf            3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1
#      dist/PixelFontPC98-12-2026-10-24.zip 96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8
#      vendor/fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans-subset.ttf
#                                            FC910F23FF8EE2DF8F2FEC6F91381A60DF812E3A16CE177F48528F1DB6551A37
cd E:\PixelFont
Get-FileHash -Algorithm SHA256 dist\PixelFontPC98-12.ttf
Get-FileHash -Algorithm SHA256 dist\PixelFontPC98-12-2026-10-24.zip
Get-FileHash -Algorithm SHA256 vendor\fusion-pixel-12px\fusion-pixel-12px-monospaced-zh_hans-subset.ttf

# 7) 仓库政策自检 —— 期望：dist/ 与 third_party/ 无跟踪文件，vendor/ 有跟踪文件
cd E:\PixelFont
git ls-files dist third_party vendor
```

### 4.2 bash

```bash
# 1) 产物与生产源哈希 —— 期望值见上（PowerShell 6 节），实际输出应逐字符相同
cd /e/PixelFont
sha256sum dist/PixelFontPC98-12.ttf \
          dist/PixelFontPC98-12-2026-10-24.zip \
          vendor/fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans-subset.ttf

# 2) 发布包条目 —— 期望：9 项
#    PixelFontPC98-12.ttf / .bdf / -atlas.png / -specimen.png
#    安装与使用说明.md / word-compat.md / SHA256SUMS.txt
#    说明-各字号渲染对比.png / 说明-轮廓合并前后对比.png
unzip -l dist/PixelFontPC98-12-2026-10-24.zip

# 3) 构建 + 全链路验收
cd /e/PixelFont
python tools/fontgen/build_font.py
python tools/fontgen/verify_all.py
python tools/fontgen/verify_gdi.py
```

### 4.3 发布同步（仅在需要推送 `dev` 时）

```powershell
# 期望：推送成功，且 dev 与 main 保持零分叉（--ff-only 可快进）
cd E:\PixelFont
git -c credential.helper= -c "credential.https://github.com.helper=!gh auth git-credential" push origin dev
```

---

## 5. 已知边界与待办

| 编号 | 事项 | 状态 | 下一步 |
|---|---|---|---|
| B-01 | **Hebrew / Arabic / Devanagari / Thai 不覆盖** | 已定性为**明确不做** | 12px 层面无点阵源（仅 Unifont 16 的 16×16 网格，塞不进 12px 格）。若未来要覆盖，须另立 12px 点阵设计项目，不在 `PixelFont Multi 12`（方案 C）范围内 |
| B-02 | 谚文字母与假名扩展（Unifont 16 独有共 **896** 码位） | 属**方案 B，未选** | 维持不覆盖；如后续重启方案 B，须与方案 C 分支独立立项 |
| B-03 | 单字重：仅 Regular，无 Bold / Italic / 可变轴 | **未满足** | 加粗/斜体在 12 × 13 网格下的可行策略未决；不依赖渲染器合成（GDI 合成会破坏点阵） |
| B-04 | 无 kerning、无连字、无 OpenType 特性（除 `gasp`） | **未满足** | 默认不做；与多语言版「`locl` 未选」的取向一致 |
| B-05 | 非整数倍字号（12ppem 整数倍之外）笔画断裂、墨迹偏细 **43%** | **已知限制** | 已在 `docs/word-compat.md` §7.6 文档化；不做技术修补（会牺牲整数倍精确性），改为在安装说明中提示用户使用 9pt / 18pt / 27pt |
| B-06 | FreeType 12px 平均偏差 **19.00 px/字**（最坏 44）；24px+ 偏差 0 | **已知限制** | 不承诺 FreeType 小字号逐格还原；GDI 路径已达标，定位为 Windows / Word 优先 |
| B-07 | 日文汉字变体（共享 2,078 字中 **434 / 2,078 = 20.9%** 与中文形不同） | **已知限制** | 共享字默认取中文形（zh_hans 源）；用户若需日式字形，`locl` 变体机制**未选**，须另行提供变体机制（多语言版范围内） |
| B-08 | 本机已安装的是 10-23 旧版（**1,362,480 字节**，sha256 `FCC65BCBCD8A1A022007065E3444464916EDB537BB172B6F2ACDC9596DE3303B`），**尚未覆盖** | **未完成** | 用 v1.0.0 产物覆盖安装后复跑 `verify_gdi.py`，确认本机呈现逐格一致 |
| B-09 | 成品不可再分发（字形派生自 SimHei / MS Gothic 专有字体） | **已知限制** | `dist/` 不入库；对外分发走 GitHub Release 附件并附说明 |
| B-10 | 参考票数量有限：12px 层面仅 2 票（Ark / Zpix），Ark 已转自证 | **部分满足** | 目视复核参考列保持 **Zpix + Unifont**；Unifont 因 16px 不参与 12px 笔画数比对 |
| B-11 | 硬检查命中 **71**（warn 69 / error 2，参考集分歧） | **已裁决非缺陷 169 / 确认缺陷 0**，命中本身保留 | 维持参考集口径；新增参考票时重跑 `verify_all.py` 步骤 4 |
| B-12 | `PixelFont Multi 12`（31,392 码位）**尚未开工** | **已拍板方向、未开工** | 按方案 C（L0–L7）推进独立家族；沿用「4 个码位 `U+20AC / U+2260 / U+2264 / U+2265` 不被任何 Fusion 变体覆盖」的 MS Gothic / SimHei 非第三源路径 |
| B-13 | 多语言版体积 **约 7.0 MB**（31,392 字 × 234.0 字节/字均值粗估） | **粗估，非实测** | 开工后以实际构建产物字节数替换 |
| B-14 | `OS/2.usWeightClass` 实测值未在底稿中给出 | **待验证** | 用 fontTools 读 `dist/PixelFontPC98-12.ttf` 的 `OS/2` 表打印该字段，结果回写本文 2.5 与 AC-27 |
| B-15 | zip 内 5 个条目（BDF / atlas.png / specimen.png / 安装与使用说明.md / word-compat.md）的 SHA256 **未被 `SHA256SUMS.txt` 收录** | **待验证 / 待补** | 补录 zip 内全部条目的 sha256 到 `SHA256SUMS.txt`，与 zip 内已有 3 个条目口径一致 |
| B-16 | Release 附件 **5 个**（zip / ttf / 2 张说明图 / SHA256SUMS） | **已满足** | 保持现状；新增附件时同步更新本文 2.8 与 AC-24 |

---

*本文所有数值来源：统一事实底稿 v2（2026-10-24 核实，HEAD `4300fc1`）。底稿未覆盖处均标注「待验证」并给出验证方法，无推断性补写。*
