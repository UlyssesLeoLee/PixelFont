# PixelFont 设计规格文档集（12 份）

> 本目录是 PixelFont 项目的完整设计规格文档集，共 12 份。
> 事实底稿日期：**2026-10-24**；对应仓库 HEAD 随提交推进变化，以 `git log -1 --format=%h` 为准（v1.0.0 已发布）。
> 全部数值均可追溯到仓库文件路径 / 命令 / commit / 报告文件；核不实的项一律标「待验证」并附验证方法 —— **禁止编数字**。

## 文档索引

| # | 文件 | 内容 | 篇幅 |
|---|---|---|---|
| 01 | [`01-font-design-requirements.md`](01-font-design-requirements.md) | 字体设计需求规格书：用途、目标用户、支持语言、风格、字重、使用场景 | 389 行 |
| 02 | [`02-charset-definition.md`](02-charset-definition.md) | 字符集定义书：收录范围、规则、优先级、缺字策略 | 537 行 |
| 03 | [`03-visual-design-spec.md`](03-visual-design-spec.md) | 字体视觉设计规范：气质、笔画风格、粗细、曲线、重心、设计原则 | 306 行 |
| 04 | [`04-glyph-structure-design.md`](04-glyph-structure-design.md) | 字形结构设计书：字形比例、部件复用、字面框、笔画交接、构造规则 | 375 行 |
| 05 | [`05-typeface-family-design.md`](05-typeface-family-design.md) | 字体家族设计书：命名规范、字重 / 字宽 / 斜体 / 可变字体轴 | 390 行 |
| 06 | [`06-font-metrics-design.md`](06-font-metrics-design.md) | 字体度量设计书：UPM、Ascender、Descender、Baseline、行距 | 356 行 |
| 07 | [`07-kerning-and-typesetting-design.md`](07-kerning-and-typesetting-design.md) | 字距与排版设计书：字间距、Kerning、标点处理、连字、OpenType 特性 | 454 行 |
| 08 | [`08-font-production-design.md`](08-font-production-design.md) | 字体制作详细设计书：Glyph 命名、轮廓规则、构建流程、字体格式、工具链 | 329 行 |
| 09 | [`09-glyph-quality-check-spec.md`](09-glyph-quality-check-spec.md) | 字形质量检查规范：轮廓完整性、曲线质量、结构一致性、视觉平衡 | 297 行 |
| 10 | [`10-font-test-spec.md`](10-font-test-spec.md) | 字体测试规格书：字符覆盖、渲染兼容性、多平台、多字号、排版测试 | 344 行 |
| 11 | [`11-version-and-change-management.md`](11-version-and-change-management.md) | 版本与变更管理书：版本规则、字形修改记录、兼容性、发布历史 | 464 行 |
| 12 | [`12-license-and-delivery-manual.md`](12-license-and-delivery-manual.md) | 字体授权与交付说明书：许可证、版权、安装方法、格式、使用限制 | 382 行 |
| — | [`_facts-baseline.md`](_facts-baseline.md) | **统一事实底稿 v2**（2026-10-24 核实）：12 份文档共用的唯一数字来源，文档中「底稿 §N」即指本文件 | 284 行 |

## 每份文档的结构约定

每份文档都保留以下六段，章节标题一致，便于横向对照：

1. **结论先行** —— 开头直接下判断，不是目录式罗列
2. **1. 范围与目的** —— 目的 / 适用范围 / 读者 / 术语
3. **2. 正文** —— 用表格承载规格
4. **3. 验收判据** —— 可量化判据 + 验证方式
5. **4. 复现命令** —— 可复制的命令块
6. **5. 已知边界与待办**

## 贯穿全套文档的核心事实

| 项 | 值 |
|---|---|
| 家族名（name ID 1 / 16） | `PixelFont PC98 12`（PostScript `PixelFontPC98-12`，achVendID `PXLF`） |
| 设计网格 | 12 × 13 像素，12px 等宽，PC-98 风格 |
| UPM | 768（1 像素 = 64 单位；em 方框按**字宽 12** 取，不是 cell 高 13） |
| 基线 | ascent 11 / descent 2；advance 半角 6 / 全角 12；行高 832 单位 = 13 像素 |
| 当前字符集 | **4,161** 码位（ASCII 95 + 标点符号 56 + 假名 255 + 汉字 3,755） |
| 汉字来源 | GB2312 一级（区位 16–55 区）**机械推导**，非凭记忆列表 |
| 渲染 | FreeType MONO 目标；**只有 12 的整数倍字号**逐格还原（12 / 24 / 36 ppem @96dpi） |
| GDI 实测 | 12ppem 与 24ppem 下全字符集 **4,161 / 4,161 逐格一致**，抗锯齿 **0** |
| FreeType 实测 | 12px 平均偏差 **19.00 px/字**（最坏 44），24px+ 偏差 0 |
| 质量门禁 | `tools/fontgen/verify_all.py` 8 步全 PASS；回归 4,161 字分 43 批，0 error 0 warn |
| 成品 | `dist/PixelFontPC98-12.ttf` 973,712 字节 / sha256 `3298AE4D…F69FB1` |
| 多语言版 | `PixelFont Multi 12`，**31,392** 码位（方案 C），**独立家族**，计划中未开工 |

## 已知的硬边界（写清楚，不夸大）

- **不覆盖** 阿拉伯 / 希伯来 / 天城文 / 泰文 —— 只有 Unifont 16 的 16×16 点阵，塞不进 12px 格。
- **单字重** Regular，无 Bold / Italic / 可变字体轴；无 kerning、无连字，唯一的 OpenType 表是 `gasp`。
- 中日共享 2,078 汉字中 **434 字**在日文源与中文源之间字形不同，当前固定取中文形，**没有切换机制**（GSUB `locl` 未选）。
- 成品字形派生自 **SimHei / MS Gothic**（微软专有），故 `dist/` **不入库**；仓库代码为 **AGPL-3.0**，入库生产源 Fusion Pixel 为 **OFL-1.1**。

## 相关文档（仓库内）

- [`docs/word-compat.md`](../word-compat.md) —— Word 兼容性的根因、验证过程与全部实测数字
- [`docs/install.md`](../install.md) —— 面向普通用户的安装与使用说明
- [`docs/reference-fonts.md`](../reference-fonts.md) —— 参考字体与生产源清单（含来源 / 版本 / sha256 / 许可证）
- [`docs/glyph-identity-verification.md`](../glyph-identity-verification.md) —— 字形身份校验与可复现性
- [`docs/adversarial-review.md`](../adversarial-review.md) —— 三轮对抗式审核方法与结论
- [`_adversarial-review.md`](_adversarial-review.md) —— **本规格文档集**的对抗式审核报告（21 条缺陷与修复台账）
- [`tools/specreview/`](../../tools/specreview/) —— 审核工具（`audit_identity` / `audit_structure` / `audit_chain` / `verify_facts` / `sync_index`）
