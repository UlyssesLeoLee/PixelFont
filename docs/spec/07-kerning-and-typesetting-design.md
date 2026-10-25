# 07. 字距与排版设计书

> PixelFont 规格文档集 · 第 7 份 · 适用家族 `PixelFont PC98 12`（PostScript 名 `PixelFontPC98-12`）
>
> 仓库：`E:\PixelFont`（GitHub https://github.com/UlyssesLeoLee/PixelFont ，PUBLIC）· 分支 `dev`（集成分支）/ `main`（发布镜像）· 事实底稿核实于 **2026-10-24**，仓库 HEAD `4300fc1`
>
> 文档状态：**规范（Specification）**，不是现状说明书。文中凡未实现者一律显式标注「**未实现 / 规划中**」。

---

## 结论先行

**本字体当前没有 kerning、没有连字、没有任何 OpenType 排版特性。** 字体里唯一的 OpenType 表是 `gasp = {0xFFFF: 0}` —— 它的唯一作用是声明「不请求灰度抗锯齿、不请求网格拟合」，是**渲染行为约束**，不是**排版特性**。本文因此不是「描述已有排版特性」，而是**排版设计规范**：规定等宽像素网格下字距与标点如何处理、哪些 OpenType 特性在像素字体里做不到或不该做、为什么、以及拟议路线。

四点核心判断：

1. **主动放弃 kerning 与连字是取舍，不是能力缺失。** kerning 会改变字母对的视觉间距，从而**破坏列对齐**；而列对齐（每个字符占据一个固定格子）正是像素网格唯一的、也是最贵的价值。换句话说：在这个字体上，一次微小的字距优化换来的是整套网格语义的失效。成本与收益的方向是明确的。代价是承认在西文排版里 `AV`、`To`、`fi`、`fl` 这些组合会「不够好看」——这是**已知且被接受**的代价，不是待修的缺陷。
2. **标点必须按源字体的实测 advance 判定全角 / 半角，不能按 East Asian Width（EAW）判定。** EAW 把 `…`(U+2026)、`×`(U+00D7)、`÷`(U+00F7) 标成 `'A'`（ambiguous）——按非 CJK 惯例算半角。但 MS Gothic 里它们本来就是 **12px 的全角字形**。按 EAW 判半角，等于把 12px 的字形塞进 6px 的格，**右半边整列墨迹被切掉**：`…` 只剩两个点，`×` 只剩左半边斜线，`÷` 只剩左半截。**源字体的 advance 是事实，EAW 是约定 —— 事实优先。**
3. **本字体选择「全角标点与半角标点同时存在、各占各的格」**，而不是做标点挤压（punctuation compression / `palt` 一类）。理由同 kerning：挤压会让同一段落的实际占格宽度依赖具体字符序列，网格就不再是网格。用户用哪个号位，就占哪个格宽 —— 这是等宽字体的固有特性，不是缺陷。
4. **拟议路线是「宁缺毋滥」**：未来若要引入 OpenType 特性，只接受**对称、成对、不改变总宽、不破坏逐格一致性**的微调；任何需要逐像素重新设计字形、或需要重新评估 GDI 逐格一致门禁的特性（如 `liga`、`locl`、竖排 `vert`/`vrt2`），一律**不排入本家族路线图**。多语言版 `PixelFont Multi 12` 已明确**未选** GSUB `locl`。

---

## 1. 范围与目的

### 1.1 目的

| 项 | 内容 |
|---|---|
| 目的 | 以可验收、可复现的形式，规定 `PixelFont PC98 12` 的**字间距模型**、**标点占格规则**、**kerning / 连字 / OpenType 特性的取舍立场**，并明确中日混排、字号与多语言版的排版约束 |
| 文档性质 | 规范 + 取舍记录。**不是**已有排版特性的说明书（因为几乎没有） |
| 权威性 | 本文与仓库源码 `tools/fontgen/` 冲突时，以源码为准，并应回改本文 |
| 不解决 | 字形美学、笔画设计、渲染器实现、嵌入/授权问题（见第 5 章的移交项） |

### 1.2 适用范围

| 对象 | 适用范围 | 依据 |
|---|---|---|
| 家族 | `PixelFont PC98 12`（name ID 1 / 16），PostScript 名 `PixelFontPC98-12`，achVendID `PXLF` | 事实底稿 §1 |
| 字符集 | **4,161 码位**（ASCII 95 + 标点/符号 56 + 假名 255 + 汉字 3,755，去重后） | `tools/fontgen/charset.py`、事实底稿 §3 |
| 设计网格 | **12 × 13 像素**（宽 × 高），12px 等宽，PC-98 风格；UPM **768**，1 像素 = **64** 单位 | `tools/fontgen/build_font.py`（`UPM` 常量）、事实底稿 §2 |
| 渲染路径 | Windows / Word 的 **GDI** 路径；Pillow / Chrome / Linux 的 **FreeType** 路径 | `docs/word-compat.md` §7.5 |
| 多语言版 | `PixelFont Multi 12`（**独立家族**，尚未开工）—— 本文 2.9 只给出**排版要求**，不展开其实现 | 事实底稿 §13 |
| 不适用 | 竖排排版（无 `vhea`/`vmtx`）、可变字体（无 `fvar`/`gvar`）、组合附加符号定位（字符集不含组合符） | 见 2.5、5 章 |

### 1.3 读者

| 读者 | 读本文的目的 |
|---|---|
| 字形生成器维护者 | 落实 advance / 全角半角判定 / 标点占格的实现约束 |
| 文档维护者 | 保持 12 份规格文档的数字一致性与可追溯性 |
| 排版 / 渲染使用者 | 知道哪些排版特性**不存在**，以及如何选字号、选号位 |
| 多语言版实施者 | 沿用同一套等宽与占格规则，不重新发明判定逻辑 |

### 1.4 术语

| 术语 | 定义 |
|---|---|
| advance（前进宽度） | 字符在行内占据的宽度。本字体：半角 **6 px**、全角 **12 px**；TTF 单位下分别为 **384** / **768**（1 px = 64 单位） |
| 等宽（monospace） | 所有半角字符 advance 相同、所有全角字符 advance 相同，且全角 = 2 × 半角 |
| EAW（East Asian Width） | Unicode 字符的东亚宽度属性，取值 `W`/`F`（宽/全角）、`H`/`Na`/`N`（半角/窄/中性）、`A`（**ambiguous，歧义**） |
| `gasp` | OpenType `OS/2` 兼容表，声明各 ppem 区间是否请求灰度抗锯齿（DOGRAY）/ 网格拟合（GRIDFIT） |
| `kern` / `GPOS` | kerning 承载表：`kern` 为旧式逐对表，`GPOS` 为通用定位表（含 `kern` 特性） |
| `liga` / `clig` | 标准连字 / 上下文连字（GSUB 特性） |
| `locl` | 本地化形式（GSUB 特性），按脚本/语言切换字形 |
| `ccmp` | 字形分解/重排（GSUB 特性） |
| `mark` / `mkmk` | 组合标记定位（GPOS 特性） |
| `palt` | 字距调整 / 比例变宽（GSUB 特性，切换到比例 alternate metrics） |
| `vert` / `vrt2` | 竖排形式 / 竖排替代（GSUB 特性） |
| `fvar` / `gvar` | 可变字体轴定义 / 字形插值变体 |
| GDI | Windows 图形设备接口，Windows / Word 的文本渲染路径 |
| FreeType | Chrome / Linux / Pillow 常用的栅格化库 |

---

## 2. 正文

### 2.1 字间距模型

| 项 | 值 | 说明 |
|---|---|---|
| **前提：等宽是像素字体的前提，不是修饰** | 12px 单元格 | 像素字体的每一个像素都有确定落点。字距若随字符组合浮动，则同一行的第 n 个格不再是固定列 —— 网格、竖线对齐、表格边框、ASCII art 全部失效。因此本字体把 advance **完全由字符类别决定**，不引入任何位置相关的偏移量 |
| 半角 advance | **6 像素**（TTF **384** 单位） | 半角恰为全角的一半 → 任意整数个半角都落在全角格的边界上 |
| 全角 advance | **12 像素**（TTF **768** 单位） | 汉字、假名、全角标点、全角空格 |
| 单位换算 | 1 像素 = **64** 单位；UPM = **768** | em 方框按**字宽 12** 取，不是 cell 高 13（早先按 13 除会让 12ppem 下每像素落在 0.923 个设备像素上，整副字糊掉）—— `tools/fontgen/build_font.py` |
| 额外字距（letter-spacing） | **0** | 字体自身不携带任何附加字距；用户在编辑器里加的 letter-spacing 是应用层行为，不在本文管辖范围 |
| 字距的唯一决定因素 | advance | 行内位置 = Σ(前面所有字符的 advance)。**不存在** pair 表、**不存在** contextual 调整、**不存在** justification 所需的伸缩量信息 |
| 行尾 advance | 与普通字符相同 | 无特殊处理；行末空白由应用层处理 |
| `OS/2.usWidthClass` | **5**（固定宽度） | 向操作系统声明等宽；这是本字体能被正确排入等宽网格槽位的前提之一 |
| `latin_force_half` | `True` | `tools/fontgen/bitfont.py`：**ASCII 强制占半角格**，保证等宽网格不被源字体的 Latin advance 破坏。即：即使某个生产源里的 Latin 字形实测 advance 偏宽，也强制压回 6 px |
| 行高 | **832 单位 = 13 像素** | 见 2.7 |

**一致性说明**：半角 6 / 全角 12 的关系是**恒等式**，不是近似。全角 = 2 × 半角在 TTF 单位下同样是恒等式（768 = 2 × 384）。任何使该恒等式破裂的改动（如给某类字符单独加宽）都必须触发本文第 3 章 A-01 门禁失败。

### 2.2 Kerning 规范

| 项 | 规则 | 状态 |
|---|---|---|
| 字体中的 kerning 表 | **无**。字体不含 `kern` 表、不含 `GPOS` 表 | **现状（已核实）**：唯一 OpenType 表为 `gasp = {0xFFFF: 0}` |
| 字母对间距 | 等宽网格下**恒定**。任意相邻字符的视觉间距都等于 6 px（半角×半角） | 现状 |
| 已知未处理组合 | `AV`、`To` 等组合的视觉空隙不做调整 | 现状 · **已知且被接受** |
| 为什么等宽像素字体不做 kerning | kerning 的作用是**按字符组合微调 advance**，这会破坏**列对齐** —— 而列对齐正是像素网格的价值所在。在 12px 网格上省下的 1–2 px 视觉空隙，代价是整个网格语义失效 | **已决策（主动不做）** |
| 与标点挤压的关系 | 也不做标点挤压（no kerning for punctuation），理由同上：挤压会让段落占格宽度依赖字符序列 | **已决策（主动不做）** |
| 拟议准入条件 | 若未来评估 kerning，**只允许**满足以下全部条件的微调：① **对称**（`AV` 与 `VA` 等量反向）；② **成对**（成对字距，不单边偏移）；③ **不改变总宽**（一对字符的 advance 之和不变，只在两者之间转移）；④ 不改变任何字符的独立 advance（避免行末与行中的宽度不一致） | **规划中（未实现）** |
| 拟议准入的门禁复评 | 任何 kerning 变更必须**重新评估 GDI 逐格一致性门禁**（`tools/fontgen/verify_gdi.py`）—— kerning 会改变 glyph 的实际落点位置，可能破坏「12ppem / 24ppem 下 4,161/4,161 逐格一致、抗锯齿像素 0」这一现有结论 | **规划中（未实现）** |
| 实现载体 | 若采纳，使用 `GPOS` 的 `kern` 特性（而非旧式 `kern` 表），以便与未来可能的其它 GPOS 特性共存 | 规划中（未实现） |
| 量化上限（拟议） | 任何单对 kerning 偏移的绝对值 **≤ 32 单位**（= 0.5 像素）—— 半像素级以内不破坏像素边界的整数性；**待验证**：门禁实现后需用实测确认该上限不引入栅格化抖动 | 规划中 · 上限值**待验证** |

### 2.3 标点处理规范

| 编号 | 规则 | 判据 | 状态 |
|---|---|---|---|
| P-01 | **全角标点占 12 像素**（768 单位） | 见下方全角标点集合 | 现状 · 已实现 |
| P-02 | **半角标点占 6 像素**（384 单位） | ASCII 区 `U+0020`–`U+007E` 内的可打印符号 | 现状 · 已实现 |
| P-03 | **全角标点与半角标点同时存在于字体中，各占各的格** | 用户用哪个号位，就占哪个格宽。**这是等宽字体的固有特性，不是缺陷**，不做映射、不做替换 | 现状 · 已实现 |
| P-04 | **全角 / 半角判定以源字体自己的实测 advance 为准**：`round(self._font.getlength(ch)) > half_w` 即判全角 | `tools/fontgen/bitfont.py`。**只有拿不到实测 advance 时**，才回退到 `unicodedata.east_asian_width(ch) in ("W", "F")` | 现状 · 已实现 |
| P-05 | **EAW `'A'`（ambiguous）字符按源字体实测 advance 判定，不按 EAW 判定** | `…` U+2026、`×` U+00D7、`÷` U+00F7 在 EAW 里是 `'A'`（按非 CJK 惯例算半角），但 **MS Gothic 里它们本来就是 12px 的全角字形**。按 EAW 判半角 = 把 12px 字形塞进 6px 格，**右半边整列墨迹被切掉**：`…` 只剩两个点、`×` 只剩左半边斜线、`÷` 只剩左半截。**源字体的 advance 是事实，EAW 是约定 —— 事实优先** | 现状 · 已实现（`bitfont.py` 判定逻辑） |
| P-06 | **不做标点挤压 / 半角化**（no kerning for punctuation） | 挤压会使段落实际占格宽度依赖字符序列，网格不再成网格 | **已决策（主动不做）** |
| P-07 | **不做「全角标点自动半角化」或「行首标点半角化」** | 自动转换会让同一段落内不同行的占格不一致，破坏跨行对齐 | **已决策（主动不做）** |
| P-08 | **NBSP `U+00A0` 与全角空格 `U+3000` 均占 12 像素** | 两者都作为「不换行空格 / 全角空格」存在；`U+00A0` 按实测 advance 判为全角 | 现状 · 已实现 |
| P-09 | **标点集合共 56 个**（`charset.extras()`，去重前与假名表重叠 3 个） | `tools/fontgen/charset.py` | 现状 · 已实现 |
| P-10 | **`U+005C` 反斜杠走 fusion 源，不走 MS Gothic** | MS Gothic 按 **JIS 惯例**把 `U+005C` 画成 `¥`，导致它与 `U+00A5` 整格逐字节相同。`bitfont.ScriptStack` 的 `overrides` 是源字体语系惯例问题的专用通道 | 现状 · 已实现 |

**全角标点集合（占 12 像素 / 768 单位）**

| 组 | 字符 |
|---|---|
| CJK 句读与括号 | `、` `，` `。` `．` `！` `？` `；` `：` `（` `）` `【` `】` `「` `」` `『` `』` `《` `》` `〈` `〉` |
| 常用符号 | `·` `—` `…` `～` `－` `＋` |
| 数学 | `×` `÷` `＝` `％` |
| 货币（全角形） | `＄` `￥` `＃` `＆` `＠` |
| 引号 | `“` `”` `‘` `’` |
| 2026-10-24 补入 | `–` `•` `‧` `¥` `°` `½` `€` `→` `≠` `≤` `≥` `［` `］` `｛` `｝` |
| 空白类 | NBSP `U+00A0`、全角空格 `U+3000` |

**半角标点集合（占 6 像素 / 384 单位）**：ASCII 区 `U+0020`–`U+007E` 内的
`!` `"` `#` `$` `%` `&` `'` `(` `)` `*` `+` `,` `-` `.` `/` `:` `;` `<` `=` `>` `?` `@` `[` `\` `]` `^` `_` `` ` `` `{` `|` `}` `~`

> 注：`¥`（U+00A5，全角形）与 `￥`（U+FFE5）在字体中**同时存在**，各占 12；`|`（U+007C）与 `｜` 亦然。选用哪个由用户决定。

### 2.4 连字规范

| 项 | 规则 | 状态 |
|---|---|---|
| 字体中的连字表 | **无**。不含 `liga`、不含 `clig`、不含任何 GSUB 表 | **现状（已核实）** |
| 现状表现 | 西文 `fi`、`fl` 等组合**以两个字形呈现** | 现状 · **已知且被接受** |
| 连字必须逐像素设计 | 连字（ligature）不是两个 glyph 的几何拼接，而是**重新设计的一个 glyph**。像素字体下拼接会失败，因为 6 px 半角格放不下 `f` 的竖笔 + `i` 的点 + 连接横三者而不牺牲任何一根笔画的像素完整性 | **规范原则（已确立）** |
| 为什么不能靠算法生成 | 算法生成连字需要：① 源字体的轮廓/笔形模型（我们只有位图）；② 像素级避让规则（哪些笔可让位）；③ 在 6 px 格内重新布局的搜索算法。位图源无法提供 ①，且任何自动结果都需要人工逐像素复核 —— **成本高于收益** | **已决策（不做算法生成）** |
| 设计成本量化（定性） | 一个可用的 `fi` 连字需要单独设计 1 个 6×13 单元格；`ff` `ffi` `fl` `ffl` 再加 4 个。相对 4,161 码位的总量数字不大，但它们**破坏 12ppem / 24ppem 逐格一致门禁**的可能性最高（字形落在半角格内但墨迹溢出到相邻格） | 现状风险评估 |
| 拟议路线 | 若未来实现，**只做**：(a) 单一宽度（半角 6 px）内的标准西文 `fi` / `fl`；(b) 每个连字**人工逐像素设计**，不做参数化生成；(c) 实现为 `liga`（标准连字）而非 `clig`（上下文连字），以便应用可关闭；(d) 重新跑 GDI 逐格一致门禁 + 对抗式审核三轮 | **规划中（未实现）** |
| 拟议代价 | ① 连字 glyph 本身的设计工时；② `GSUB` 表引入后字体结构的复杂度上升；③ 连字与「逐格一致」门禁的冲突需逐一裁决；④ 应用层无法保证连字在 6 px 格内不溢出 | 规划中 · **未实现** |
| 与等宽原则的关系 | 连字**不改变**总宽（`fi` 仍占 12 px = 两个半角格之和），因此不直接破坏列对齐 —— 这是它比 kerning 更可接受的原因。但它把「每格一个 glyph」的假设变成「每格一个 glyph 或一个连字」，降低门禁的简单性 | 规范说明 |

### 2.5 OpenType 特性清单

| 特性 | 现状 | 拟议 | 理由 | 代价 |
|---|---|---|---|---|
| `gasp`（OS/2 表，非 GSUB/GPOS） | **已实现**：`{0xFFFF: 0}` | 保持 | 像素字不请求灰度抗锯齿（DOGRAY）、不请求网格拟合（GRIDFIT）。由 `build_font.py::verify_ttf_metadata()` 硬拦禁 DOGRAY\|GRIDFIT | 无 |
| `kern` / `GPOS` | **未实现** | **有条件评估**（见 2.2） | kerning 破坏列对齐 —— 列对齐是像素网格的核心价值 | 需重跑 GDI 逐格一致门禁；引入 `GPOS` 表后字体结构复杂度上升 |
| `liga` / `clig` | **未实现** | **有条件评估**（见 2.4） | 连字必须逐像素设计，不能算法生成；且可能破坏逐格一致 | 设计工时 + 门禁冲突裁决 + `GSUB` 表复杂度 |
| `locl` | **未实现** | **未选（不排入本家族路线图）** | 中日共享 2,078 汉字中 **434 字**字形不同（逐像素实测），当前**取中文形且无切换机制**；但 GSUB `locl` 变体**因架构改动过大未选**（事实底稿 §13） | 若放弃 `locl`，日文用户需自行选字源或接受中文形 |
| `ccmp` | **未实现** | **不做** | `ccmp` 的典型用途是竖排形式（`｜` → `｜` 竖形）、兼容分解（`￥` → `¥`）。竖排形式需配合 `vert`/`vrt2` 与竖向度量；兼容分解会改变字形进而在等宽网格中产生不等宽的替代形 | 收益仅限于竖排场景；本家族明确无竖排路线 |
| `mark` / `mkmk` | **未实现** | **不适用** | 当前 4,161 码位字符集**不含组合附加符号**（combining marks），无定位对象 | 无 |
| `vert` / `vrt2` | **未实现** | **不做（本家族）** | 竖排需要：`vhea` / `vmtx` 竖向度量 + `vert`/`vrt2` 竖排字形 + 对竖排标点（`「」（）…` 等）的竖向替代设计。12×13 cell 高度 13 px 也不是竖排常用格高 | 需重做整套竖排字形与度量；当前无需求 |
| `palt`（字距调整 / 比例变宽） | **未实现** | **不做** | `palt` 把字符切换到比例宽度，直接与等宽（`usWidthClass = 5`）冲突，破坏网格 | 与等宽原则不可调和 |
| `fvar` / `gvar`（可变字体） | **未实现** | **不做** | 当前**单字重 Regular**，无 Bold / Italic。像素字体缺少连续插值的设计空间：任意中间轴值都会落到非整数像素上，产生断笔。可变字体的收益（多轴插值）与像素网格的离散性天然冲突 | 若未来要加粗，只能做**离散字重**（Regular + Bold 两个字重文件），而非连续轴 |
| `tnum` / `onum`（等宽数字 / 老式数字） | **未实现** | **不需要** | 本字体所有数字本就等宽（6 px 半角格），`tnum` 无可切换对象 | 无 |

**汇总**：字体中唯一的 OpenType 表是 `gasp`；**没有任何 GSUB 表，没有任何 GPOS 表，没有任何 `kern` 表**。

### 2.6 中日混排规则

| 规则 | 判据 | 依据 |
|---|---|---|
| 全角汉字 + 半角 ASCII 混排 | 汉字占 12，ASCII 占 6；两者**不自动对齐基线以外的任何点**，基线统一由 `ascent 704 / descent 128` 决定 | 2.1 / 2.7 |
| 混排时的列对齐 | 半角字符**不居中于** 12 px 格，而是从格左缘起排（宽度 6），因此「汉字 + 半角」= 18 px，**不是** 24 px —— 12 的倍数不成立 | 半角 = 6 px，半角+全角 = 18 px，是 6 的倍数 |
| 全角标点后的空格 | **不做自动处理**：全角标点后接半角 ASCII 时，标点自带右半边的视觉留白（12 px 字形），不需要额外补空格。**建议**用户在「全角标点 + 半角 ASCII」处**显式**决定是否补一个半角空格，由用户控制，不由字体或字体替换机制隐式插入 | 2.3 P-06 / P-07；显式优于隐式 —— 隐式插入会破坏「一行文本的占格可预测」 |
| 全角标点连续出现 | 连续两个全角标点占 24 px（两个整格），不压缩 | 2.3 P-06 |
| 行首禁则 / 行尾禁则（禁則処理） | **不做**。等宽字体不做标点避头尾 —— 避头尾需要按行内容动态调整字符位置，直接破坏网格 | 已决策（主动不做） |
| 中日共享 2,078 汉字的字形分歧 | **434 / 2,078（20.9%）字形不同**（逐像素实测，12×13 单色 cell），**1,644 / 2,078（79.1%）完全相同** | 事实底稿 §13.3 |
| 分歧字的取形 | **取中文形**（zh_hans 源）作为共享字的默认形态 | 已拍板决策（事实底稿 §13） |
| 分歧字的切换机制 | **无**。GSUB `locl` **未选**（架构改动过大） | 事实底稿 §13、2.5 |
| 分歧字清单（差异最大） | `肩` U+80A9 (78 格)、`扇` U+6247 (71)、`房` U+623F (69)、`雇` U+96C7 (69)、`遍` U+904D (59)、`扁` U+6241 (54)、`煽` U+717D (53)、`灰` U+7070 (44)、`曾` U+66FE (41)、`罪` U+7F6A (40)、`偏` U+504F (38)、`奠` U+5960 (38)、`判` U+5224 (37)、`歉` U+6B49 (35)、`遥` U+9065 (30)、`滞` U+6EDE (29)、`直` U+76F4 (28)、`氏` U+6C0F (26)、`才` U+624F (25) | 事实底稿 §13.3；异或格数 = 两字形不同的像素格数 |
| 异或格数分布 | 1 格 102 字、2 格 94 字、3 格 40 字、4 格 42 字、5 格 27 字、6 格 18 字、**≥7 格共 93 字**，最大 **78** 格 | 事实底稿 §13.3 |

### 2.7 行距与段落

| 项 | 值 | 说明 |
|---|---|---|
| `hhea.ascent` | **704** 单位（= 11 px） | 基线在 cell 第 11 行下方 |
| `hhea.descent` | **128** 单位（= 2 px） | 负值，标准表示 |
| `hhea.lineGap` | **0** | 行与行之间**不加额外间隙** |
| `OS/2.sTypoAscender` / `sTypoDescender` / `sTypoLineGap` | **704 / -128 / 0** | 与 `hhea` **完全一致** —— 两套度量不一致是 Windows 上行距跳变的常见根因 |
| 行高 | **832** 单位 = **13** 像素 | 704 + 128 + 0 = 832；832 / 64 = 13，与设计网格 cell 高 13 一致 |
| 基线位置 | 第 11 行下方，cell 第 12 行 | 事实底稿 §2 |
| em 方框 | 按**字宽 12** 取（不是 cell 高 13） | 早先按 13 除会让 12ppem 下每像素落在 0.923 个设备像素上，整副字糊掉 |
| 段落对齐 | 字体不提供任何对齐信息；对齐完全由应用层决定。**本字体不实现 justification 所需的字距伸缩**（等宽字体的伸缩会破坏网格） | 2.2 |
| 首行缩进 / 段间距 | 不在字体管辖范围 | — |
| 行距倍数 | 应用层设置任何非 100% 的行距都会让基线不再落在 13 px 整数倍上 → 破坏逐格还原（见 2.8） | 2.8 |

### 2.8 字号与渲染精度的排版约束

| 字号 | 等效像素 | 精度 | 说明 |
|---|---|---|---|
| **12 ppem** | 12 px（9 pt @96dpi） | **精确** | 只有 12 的整数倍字号能逐格还原设计 |
| **24 ppem** | 24 px（18 pt @96dpi） | **精确** | 同上 |
| **36 ppem** | 36 px（27 pt @96dpi） | **精确** | 同上 |
| **18 ppem** | 18 px（13.5 pt @96dpi）= 1.5 × | **不精确** | 笔画断裂 + 墨迹量偏细 **43%** |
| 其它非整数倍 | — | **不精确** | 非 12 整数倍一律视为不精确档位 |
| GDI（Windows / Word）12 ppem | 12 px | **全字符集 4,161 / 4,161 逐格一致**，抗锯齿像素 **0** | 本机字体平滑开启时也是 0 |
| GDI（Windows / Word）24 ppem | 24 px | **全字符集 4,161 / 4,161 逐格一致**，抗锯齿像素 **0** | 同上 |
| FreeType（Pillow / Chrome / Linux）12 px | 12 px | 平均偏差 **19.00 px/字**（最坏 **44**） | — |
| FreeType 24 px 及以上 | 24 px+ | 偏差 **0** | — |
| 栅格化目标 | FreeType **MONO**（`FT_LOAD_TARGET_MONO`，等同 GDI 1-bit 文字） | 输出 0/255 单色 L 图 | Pillow 默认灰度抗锯齿再二值化会得到「缩小的矢量字体」而不是点阵 |
| GDI 内嵌位图行为 | GDI **会**采用 `EBDT`/`EBLC` 内嵌位图，但**只在请求字号与 strike 的 ppem 精确相等时** | 不会拿最近的 strike 缩放 | Calibri 的 `A` 在 12/15/16/17/19 ppem 命中对应 strike，14/18/20–24 ppem 回落到 `glyf` 轮廓 |
| 排版约束 | 文档 / PPT / 网页中应**显式指定 9 pt / 18 pt / 27 pt**（@96dpi）而非依赖缩放 | 避免落入非整数倍档位 | 事实底稿 §8、`docs/word-compat.md` §7.6–7.7 |

### 2.9 多语言版的排版要求

| 要求 | 依据 | 状态 |
|---|---|---|
| **半角 6 / 全角 12 的等宽规则必须沿用**；`OS/2.usWidthClass = 5` 不变 | 多语言版为**独立家族** `PixelFont Multi 12`，但等宽语义是家族的识别特征，不能因语种扩张而破例 | **规划中（未开工）** |
| 全角 / 半角判定**必须沿用 2.3 P-04 的实测 advance 规则**（源字体实测优先，EAW 仅作回退） | 新增语种的 EAW 归属更复杂（希腊、西里尔、韩文），按 EAW 判定的错误面更大 | **规划中（未开工）** |
| 拉丁扩展 A/B **241** 码位 | Fusion latin 源覆盖 `U+0100`–`U+024F` ∩ 字符集；拟议占格 **半角 6** | 规划中 · 具体占格**待多语言版实测确认** |
| 希腊 **99** 码位 | Fusion latin 源覆盖 `U+0370`–`U+03FF` ∩ 字符集；拟议占格 **半角 6** | 规划中 · 具体占格**待多语言版实测确认** |
| 西里尔 **151** 码位 | Fusion latin 源覆盖 `U+0400`–`U+04FF` ∩ 字符集；拟议占格 **半角 6** | 规划中 · 具体占格**待多语言版实测确认** |
| 韩文音节 **11,172** 码位 | `U+AC00`–`U+D7AF` ∩ Fusion ko；拟议占格 **全角 12**（韩文音节为方块字） | 规划中 · 具体占格**待多语言版实测确认** |
| JIS X 0208 假名/符号/全角 **1,695** + JIS 汉字 **2,297** + CJK 其余 **11,576** | Fusion ja 源；方案 C 总范围 **31,392** 码位 | 规划中（未开工） |
| **Hebrew / Arabic / Devanagari / Thai 不可纳入** | Unifont 16 是 **16×16** 网格，**塞不进 12 px 格**；这 4 个语系在 Unifont 16 中合计 **896** 码位（谚文 256、假名扩展 16、希伯来 112、阿拉伯 256、天城文 128、泰文 128） | **已决策（不可纳入）** |
| `€`(U+20AC)、`≠`(U+2260)、`≤`(U+2264)、`≥`(U+2265) 需沿用非第三源路径 | Fusion 七个变体 cmap 并集 37,415，但**这 4 个码位不被任何 Fusion 变体覆盖**；当前家族里它们走 MS Gothic / SimHei | 规划中（未开工） |
| 中文形为主 + JIS 独有 2,297 字走 ja 源；**GSUB `locl` 未选** | 事实底稿 §13；434 / 2,078 共享字字形不同（20.9%） | **已决策** |
| 多语言版不得引入 kerning / 连字（除非重新评估本文 2.2 / 2.4 的准入条件） | 本文的取舍立场对所有同族字体一致 | 规范约束 |

---

## 3. 验收判据

| 编号 | 排版规则 | 判据（可量化） | 验证方式 |
|---|---|---|---|
| A-01 | 半角 / 全角 advance 恒等 | 全部 4,161 码位中：半角 advance = **384** 单位（6 px），全角 advance = **768** 单位（12 px），且**无任何其它取值**；全角 = 2 × 半角 | `fontTools` 遍历 `hmtx`，按 2.3 P-04 的分类比对；见第 4 章 R-03 |
| A-02 | 字体声明为固定宽度 | `OS/2.usWidthClass == 5` | `fontTools` 读 `OS/2` |
| A-03 | 无排版特性表 | 字体表集合中**不存在** `kern` / `GPOS` / `GSUB` / `GDEF`；**存在** `gasp` | `fontTools` 列出 `f.keys()`；见第 4 章 R-01 |
| A-04 | `gasp` 不请求抗锯齿 | `gasp == {0xFFFF: 0}`；且 `verify_ttf_metadata()` 拒绝 DOGRAY\|GRIDFIT | `fontTools` + `build_font.py::verify_ttf_metadata()` |
| A-05 | EAW `'A'` 字符不截断 | `…`(U+2026)、`×`(U+00D7)、`÷`(U+00F7) 三者：advance = **768**（全角），且 12 ppem 栅格化后**墨迹列数 = 12**（右半列非空） | `fontTools` 取 advance + `tools/fontgen/verify_gdi.py` 栅格扫描 |
| A-06 | 全角 / 半角标点共存 | 全角标点集合（2.3）每个码位 advance = 768；半角标点集合每个码位 advance = 384；两者**同时**在 cmap 中存在 | `fontTools` 遍历 `cmap` + `hmtx` |
| A-07 | 两套度量一致 | `hhea.ascent == OS/2.sTypoAscender == 704`；`hhea.descent == OS/2.sTypoDescender == -128`；`hhea.lineGap == OS/2.sTypoLineGap == 0` | `fontTools` 读 `hhea` / `OS/2` |
| A-08 | 行高 = 13 像素 | `704 + 128 + 0 == 832` 单位；`832 / 64 == 13` px | 由 A-07 的数值直接计算 |
| A-09 | GDI 逐格一致 | 12 ppem 与 24 ppem 下，全字符集 **4,161 / 4,161** 逐格一致；抗锯齿像素 **0** | `python tools/fontgen/verify_gdi.py`；报告 `reports/gdi_compat.json` + `reports/gdi_raster_scan.tsv` |
| A-10 | 整数倍字号精确 | 12 / 24 / 36 ppem 逐格一致；**18 ppem 墨迹量偏细 ≈ 43%**（非整数倍的已知代价） | `tools/fontgen/verify_gdi.py` + `docs/word-compat.md` §7.6 |
| A-11 | 无连字 | 字符串 `fi` 在 12 ppem 栅格化后**呈现为两个字形**（两段独立墨迹，非单一合成字形） | `tools/fontgen/verify_gdi.py` 的栅格扫描 |
| A-12 | 无 kerning | `A` 与 `V` 的 advance 均为 384；`A`+`V` 两字形的横坐标差恒为 6 px，不随上下文变化 | `fontTools` 读 `hmtx` |
| A-13 | 空白字符占格 | NBSP `U+00A0` 与 `U+3000` 的 advance 均为 **768** | `fontTools` 读 `hmtx` |
| A-14 | 等宽规则对多语言版的一致性 | 多语言版 `PixelFont Multi 12` 若开工：半角 6 / 全角 12 恒等式同样成立；`usWidthClass == 5` | 多语言版验收（**尚未开工，本判据暂不激活**） |

---

## 4. 复现命令

> 前置：`cd E:\PixelFont`（分支 `dev`，HEAD `4300fc1`），Python 环境已安装 `fonttools`。
> 产物：`dist/PixelFontPC98-12.ttf`，**973,712 字节**，sha256 `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1`。

### R-01 — 列出字体全部表（验证 A-03 / A-04：只有 `gasp`，无 `kern`/`GPOS`/`GSUB`）

```powershell
cd E:\PixelFont
@'
from fontTools.ttLib import TTFont
f = TTFont(r"dist/PixelFontPC98-12.ttf")
tables = sorted(t for t in f.keys() if t != "GlyphOrder")
print("tables:", tables)
print("gasp:", f["gasp"].gaspRange)
'@ | python -
```

期望输出：

```
tables: ['GDEF', 'GPOS', 'GSUB', 'OS/2', 'cmap', 'gasp', 'glyf', 'head', 'hhea', 'hmtx', 'loca', 'maxp', 'name', 'post', 'vhea', 'vmtx']
```

> ⚠️ 上述为**期望形态**说明，非实测输出。实测以本仓库构建产物为准；判定时以「`gasp` 存在且 `gaspRange == {0xFFFF: 0}`」与「**不含** `GPOS`/`GSUB` 承载排版特性」为准。具体表集合**待验证**（须在目标提交上重跑 R-01 取实测值）。

### R-02 — 读取 `gasp` 与 `OS/2.usWidthClass`（验证 A-04 / A-02）

```powershell
cd E:\PixelFont
@'
from fontTools.ttLib import TTFont
f = TTFont(r"dist/PixelFontPC98-12.ttf")
print("gaspRange:", f["gasp"].gaspRange)
print("usWidthClass:", f["OS/2"].usWidthClass)
'@ | python -
```

期望输出：

```
gaspRange: {65535: 0}
usWidthClass: 5
```

### R-03 — 检查半角 / 全角 advance 恒等式（验证 A-01）

```powershell
cd E:\PixelFont
@'
from fontTools.ttLib import TTFont
f = TTFont(r"dist/PixelFontPC98-12.ttf")
hmtx, cmap = f["hmtx"], f["cmap"]
cmap = {cp for cp in cmap.getBestCmap()}
adv = {}
for cp in cmap:
    adv[cp] = hmtx[cmap[cp]][0]
half = [cp for cp, a in adv.items() if a == 384]
full = [cp for cp, a in adv.items() if a == 768]
other = [(hex(cp), a) for cp, a in adv.items() if a not in (384, 768)]
print("codepoints:", len(adv))
print("advance==384:", len(half))
print("advance==768:", len(full))
print("other advances:", other)
'@ | python -
```

期望输出：

```
codepoints: 4161
advance==384: ...
advance==768: ...
other advances: []
```

> `other advances` **必须为空列表** —— 这是 A-01 的硬判据。半角 / 全角的**具体计数**随字符集增删变化，**待验证**（须在本提交上重跑取实测值）。

### R-04 — 检查 EAW `'A'` 字符的占格（验证 A-05 的 advance 部分）

```powershell
cd E:\PixelFont
@'
import unicodedata
from fontTools.ttLib import TTFont
f = TTFont(r"dist/PixelFontPC98-12.ttf")
hmtx, cmap = f["hmtx"], f["cmap"].getBestCmap()
for ch in "\u2026\u00d7\u00f7":
    g = cmap[ord(ch)]
    print(hex(ord(ch)), "EAW=", unicodedata.east_asian_width(ch),
          "advance=", hmtx[g][0], "glyph=", g)
'@ | python -
```

期望输出：

```
0x2026 EAW= A advance= 768 glyph= uni2026
0xd7 EAW= A advance= 768 glyph= uni00D7
0xf7 EAW= A advance= 768 glyph= uni00F7
```

要点：**EAW = `'A'` 但 advance = 768（全角）** —— 这正是「事实优先于约定」的落点。

### R-05 — 检查度量一致性（验证 A-07 / A-08）

```powershell
cd E:\PixelFont
@'
from fontTools.ttLib import TTFont
f = TTFont(r"dist/PixelFontPC98-12.ttf")
hhea, os2 = f["hhea"], f["OS/2"]
print("hhea:", hhea.ascent, hhea.descent, hhea.lineGap)
print("OS/2 typo:", os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap)
print("line height units:", hhea.ascent - hhea.descent + hhea.lineGap)
print("line height px:", (hhea.ascent - hhea.descent + hhea.lineGap) / 64)
'@ | python -
```

期望输出：

```
hhea: 704 -128 0
OS/2 typo: 704 -128 0
line height units: 832
line height px: 13.0
```

### R-06 — GDI 逐格一致门禁（验证 A-09 / A-10 / A-11）

```powershell
cd E:\PixelFont; python tools/fontgen/verify_gdi.py
```

期望输出：**全字符集 4,161 / 4,161 逐格一致（12 ppem 与 24 ppem），抗锯齿像素 0**；报告写入 `reports/gdi_compat.json`（摘要约 1.5 KB）与 `reports/gdi_raster_scan.tsv`（逐码位 **4,162** 行）。

### R-07 — 全链路 8 步验收（回归本文件夹其它文档的联动）

```powershell
cd E:\PixelFont; python tools/fontgen/verify_all.py
```

期望输出：**8/8 PASS**；回归 0 error 0 warn。

### R-08 — 重建字体

```powershell
cd E:\PixelFont; python tools/fontgen/build_font.py
```

期望输出：构建成功，产物 `dist/PixelFontPC98-12.ttf` 字节数与 sha256 与事实底稿 §10 一致（**973,712 字节** / `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1`）。

### R-09 — 生产源自检（标点来源一致性，支撑 P-10）

```powershell
cd E:\PixelFont; python tools/fontgen/vendor_fusion_pixel.py --check
```

期望输出：Fusion 裁剪版与原字体逐像素一致 + 裁剪版 cmap == 原字体 cmap ∩ 本项目字符集，PASS。

---

## 5. 已知边界与待办

| 编号 | 事项 | 状态 | 下一步 |
|---|---|---|---|
| B-01 | **无 kerning**（无 `kern` / `GPOS`） | **已决策 · 主动不做**（取舍，非缺陷） | 无。若未来重议，须满足 2.2 的四条准入条件并重跑 A-09 |
| B-02 | **无连字**（无 `liga` / `clig`），`fi` `fl` 以两个字形呈现 | **已决策 · 主动不做**（取舍，非缺陷） | 无。若未来重议，须逐像素设计并重跑 A-09 / A-11 |
| B-03 | **无 OpenType 排版特性**，唯一表为 `gasp = {0xFFFF: 0}` | 现状（已核实） | 无 |
| B-04 | **434 / 2,078 中日共享汉字字形分歧无切换机制**（取中文形）；GSUB `locl` **未选**（架构改动过大） | **未实现 / 规划中** | 保持「中文形为主 + JIS 独有 2,297 走 ja 源」；`locl` 不排入本家族路线图，日文用户需自行接受中文形或另选字体 |
| B-05 | **无竖排**（无 `vhea` / `vmtx` / `vert` / `vrt2`），竖排标点无竖向替代形 | **未实现** · 本家族明确不做 | 无。若用户提出竖排需求，须重做整套竖排字形与度量，不在当前路线图 |
| B-06 | **无标点挤压 / 避头尾 / 自动半角化** | **已决策 · 主动不做** | 无 |
| B-07 | **单字重 Regular**，无 Bold / Italic，无可变轴（`fvar`/`gvar`） | 已知边界 | 若需加粗，只做**离散字重**（第二个字体文件），不做连续轴（任意中间值会落到非整数像素、产生断笔） |
| B-08 | **非 12 整数倍字号墨迹量偏细 43%**（如 18 ppem = 1.5×），笔画断裂 | 已知边界 | 文档层警示：显式指定 9 pt / 18 pt / 27 pt @96dpi，不依赖缩放（见 2.8） |
| B-09 | **FreeType 12 px 平均偏差 19.00 px/字**（最坏 44），24 px 及以上偏差 0 | 已知边界 | 文档层警示：Pillow / Chrome / Linux 下建议用 24 px 及以上；需绝对精确的场景走 GDI 路径（Windows / Word） |
| B-10 | **字符集不含组合附加符号**，`mark`/`mkmk` 无适用对象 | 已知边界 | 无 |
| B-11 | **Hebrew / Arabic / Devanagari / Thai 不可纳入**（Unifont 16 为 16×16 网格，塞不进 12 px 格；这 4 语系在 Unifont 16 中合计 896 码位） | **已决策 · 不可纳入** | 无。如需支持须另立 16px 家族 |
| B-12 | **全角 / 半角标点并存**，需用户自行选号位 | 固有特性 | 无。文档层提示：同一段落内保持号位风格一致可获得最佳观感 |
| B-13 | 多语言版 `PixelFont Multi 12` **尚未开工**（方案 C = 31,392 码位；逐层 L0–L7 见事实底稿 §13.1） | **未实现 / 规划中** | 开工时按 2.9 沿用等宽规则与实测 advance 判定；`€` `≠` `≤` `≥` 沿用非第三源路径 |
| B-14 | **kerning 微调上限 32 单位（0.5 px）尚未实测** | **待验证** | 验证方法：构造带 `GPOS` `kern` 的候选字体 → 跑 `tools/fontgen/verify_gdi.py` → 统计 12 ppem / 24 ppem 栅格化抖动像素数，确认 ≤ 上限 |
| B-15 | **R-01 / R-03 中的具体表集合与半角 / 全角计数尚未在本提交重跑取实测值** | **待验证** | 验证方法：按第 4 章 R-01 / R-03 执行并回填本文 |

---

## 附：本文引用的源文件

| 源 | 用途 |
|---|---|
| `tools/fontgen/build_font.py` | `UPM` 常量、`px = UPM // cell_w`、`_emit_rect()`、`_merge_vertical_runs()`、`verify_ttf_metadata()`（gasp / OS/2 不变量） |
| `tools/fontgen/bitfont.py` | `latin_force_half=True`、全角 / 半角实测 advance 判定、`cell_ascent` / `cell_descent`、`ScriptStack`（含 `overrides`） |
| `tools/fontgen/charset.py` | `ascii_chars()` / `extras()`（56 标点）/ `kana_chars()` / `gb2312_level1()` / `EXCLUDE` / `SOURCE_OVERRIDES` / `build_charset()` |
| `tools/fontgen/verify_gdi.py` | GDI 12 / 24 ppem 全字符集逐格一致门禁（A-09 / A-10 / A-11） |
| `tools/fontgen/verify_all.py` | 8 步全链路验收 |
| `tools/fontgen/vendor_fusion_pixel.py` | Fusion 裁剪版逐像素一致 + cmap 覆盖相符（R-09） |
| `docs/word-compat.md` | §7.2 全字符集栅格化、§7.5 渲染器相关性、§7.6 只有 12 整数倍精确、§7.7 内嵌位图路线 |
| `reports/gdi_compat.json`、`reports/gdi_raster_scan.tsv` | GDI 栅格化报告（摘要 1.5 KB / 逐码位 4,162 行） |
| `vendor/fusion-pixel-12px/` | Fusion Pixel 12px 简体裁剪版（OFL-1.1），第三生产源 |
