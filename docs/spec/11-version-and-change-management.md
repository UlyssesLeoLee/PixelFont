# PixelFont 版本与变更管理书

> 文档编号：11 / 12（规格文档集）  
> 适用仓库：`E:\PixelFont`（https://github.com/UlyssesLeoLee/PixelFont ，PUBLIC）  
> 基线 commit：`4300fc1`（`dev` 与 `main` 当前共同指向的 HEAD）  
> 撰写日期：2026-10-24  
> 状态：**规格草稿**（§2.1 / §2.2 中标注「拟议」的条目尚未在仓库中生效）

---

## 结论先行

PixelFont 当前处于 **v1.0.0 已发布**状态，发布链已闭环：注解 tag `v1.0.0` → 正式版 GitHub Release（`draft=false`，5 个附件）→ 资产回下载逐字节一致 → 回下载的 TTF 在 GDI 中被正常选中并渲染。本书的作用不是记录已经发生的事，而是把**下一次发布**将要依赖的判定口径先写死。

四个需要下判断的结论：

1. **版本号规则用「像素级」判定，不用「功能级」判定。** 本书的兼容性与版本段规则全部锚定一个可机器测量的不变量：**在 12 / 24 ppem 下逐格栅格化出的 12×13 单色位图集合是否改变**。该口径已有现成基础设施（`tools/fontgen/verify_gdi.py` → `reports/gdi_raster_scan.tsv`），不需要新增概念就能判定。
2. **度量 / 基线 / advance / 家族身份变更 = major；字形集合或单字形外观变更 = minor；两者都不变 = patch。** 按此口径回看，`8ae04fc`（轮廓合并，TTF 1,364,528 → 973,712 字节、轮廓 107,209 → 73,933）属于 **patch** ——它改的是轮廓细分，不是字形外观；`729403c`（字符集 4,140 → 4,161）属于 **minor**。
3. **字形修改记录目前没有台账。** 相关裁决结果散落在 `tools/fontgen/adversarial_review.py` 与 `reports/` 下，无法机器化回答「某码位何时、为何、由哪个 commit 改成现在这样」。这是本书 §5 的首要待办，不是已完成项。
4. **发布历史已固化进仓库** —— `CHANGELOG.md` 已补（commit `d1aa64c`），格式为 Keep a Changelog 1.1.0 + SemVer 2.0.0，两个家族的版本序列分列。它与 GitHub Release notes、git 历史三者并存、互为印证。

另：`PixelFont Multi 12`（多语言版）为**独立家族**，不继承本家族码位与外观，使用自己的版本序列与命名标识（§2.2）。命名标识已由构建验证落地（见 §2.2 与 `docs/multi12.md`）。

---

## 1. 范围与目的

### 1.1 目的

| 项 | 内容 |
|---|---|
| 目标 | 定义 PixelFont 的版本号规则、家族与版本的对应关系、兼容性判定口径、字形修改记录规范、分支与集成政策、提交信息规范、发布流程与门禁、发布历史与产物识别方式 |
| 要解决的问题 | ① 下一次发布时「该发 1.0.1 还是 1.1.0」没有可判定依据；② 字形改动缺少可追溯台账；③ 发布正确性目前依赖人工流程记忆；④ 产物版本识别靠文件名而非指纹 |
| 不解决的问题 | 字体设计本身（网格、码位取舍、字形美学）；多语言版的具体字形与源选择（见 `13. 多语言版规格`）；CI / 自动化发布的落地（§5 列为待办） |
| 判定基准 | 「12 / 24 ppem 下逐格栅格化位图集合是否改变」，其余判定一律从该基准派生 |

### 1.2 适用范围

| 适用 | 不适用 |
|---|---|
| 家族 `PixelFont PC98 12`（name ID 1/16），当前版本 v1.0.0 | 家族 `PixelFont Multi 12`（尚未开工，本书仅给出版本序列的**拟议**规则） |
| 仓库 `E:\PixelFont` 的 `dev` / `main` 两分支协作 | 其它仓库 / 其它字体项目 |
| TTF / BDF / 图集 / specimen / zip 等 `dist/` 产物的发布 | `dist/` 产物内部的排版设计 |
| 已发布的 v1.0.0 与其之前的三代产物 | 未来版本的实际内容（本书只定义规则，不预言版本内容） |

### 1.3 读者

| 读者 | 需要的章节 |
|---|---|
| 维护者 / 发布人 | §2.5 分支与集成政策、§2.6 提交信息规范、§2.7 发布流程与门禁、§4 复现命令 |
| 兼容性评估方（下游集成者） | §2.3 兼容性判定、§2.9 产物版本识别、§3 验收判据 |
| 字形审查方 | §2.4 字形修改记录规范、§2.9 产物版本识别 |
| 决策者 | §结论先行、§5 已知边界与待办 |

### 1.4 术语

| 术语 | 定义（本文口径） |
|---|---|
| 家族（family） | 由 `name` 表 name ID 1（家族名）与 name ID 16（排版家族名）标识的一组字形。当前家族名 `PixelFont PC98 12`，PostScript 名 `PixelFontPC98-12`，achVendID `PXLF` |
| UPM | 每 em 的单位数，当前 **768**；1 像素 = **64** 单位（768 / 12） |
| em 方框 | 按**字宽 12** 取（不是 cell 高 13）。按 13 除会让 12ppem 下每像素落在 0.923 个设备像素上，整副字糊掉 |
| advance | 字形前进宽度。半角 **6**，全角 **12** |
| 基线 | ascent **11** / descent **2**，基线在第 11 行下方（cell 第 12 行），cell 高 **13** |
| 12 整数倍字号 | 12 / 24 / 36 ppem（@96dpi 即 9pt / 18pt / 27pt）。只有这些字号能逐格还原设计网格 |
| 字形外观（本文判定用） | 在 12ppem 或 24ppem 下渲染出的 12×13 单色位图 |
| 字形指纹 | 字形外观的机器可比对摘要（§2.4 定义） |
| 零分叉 | `dev` 与 `main` 互相没有对方没有的提交：`git rev-list main..dev` 与 `git rev-list dev..main` 均为空 |
| `--ff-only` | 只允许快进合并，禁止产生合并提交 |
| 注解 tag | 带说明文字的 Git tag（`git tag -a`），本项目发布统一使用 |
| `draft=false` | GitHub Release 处于正式发布状态（不是草稿） |
| dist / vendor / third_party | 仓库内容政策的三类路径，见 §2.10 |

---

## 2. 正文

### 2.1 版本号规则（拟议，v1.0.0 之后适用）

版本号形如 `MAJOR.MINOR.PATCH`，三段的判定基准统一为「**12 / 24 ppem 下逐格栅格化位图集合**」与「**度量**」两项。

| 版本段 | 规则 | 触发条件 | 示例（回看已发布历史） |
|---|---|---|---|
| MAJOR | 度量或身份变更 | UPM / ascent / descent / cell 高 / advance 任一变化；`name` 表 name ID 1、16 变化；PostScript 名变化；移除任一码位 | 尚未发生（v1.0.0 为首个发布版本） |
| MAJOR | 结构性重绘 | 12 或 24 ppem 下**至少一个**码位的位图与上一发布版本不同，且改动面覆盖 ≥ 100 个码位（成片重绘） | 尚未发生 |
| MINOR | 字形集合变化 | 新增码位（无论数量）；或单字形外观修正（位图改变但度量与 advance 不变） | `729403c`：字符集 4,140 → **4,161**（补入 21 个 Word 常用字符：`“ ” ‘ ’`、`U+3000`、`U+00A0`、`– • ‧`、`¥ ° ½`、`€ →`、`≠ ≤ ≥`、`［ ］ ｛ ｝`） |
| MINOR | 单字形外观修正 | 同一码位在 12 / 24 ppem 下位图改变，度量不变 | 随 MINOR 版本发布 |
| PATCH | 仅修 bug，字形外观不变 | 位图集合不变且度量不变；TTF 字节数、轮廓数、`OS/2` 字段等可以变 | `8ae04fc`：合并竖向相邻等宽游程，轮廓 107,209 → **73,933**、TTF 1,364,528 → **973,712** 字节，整数倍精确性 **12,483 / 12,483** 未破；`cef4a22`：修 `OS/2` 元数据三处错误 |
| PATCH | 构建与元数据修复 | 不改任何码位外观；只修 `OS/2`、命名、元数据或构建脚本行为 | `cef4a22`（`ulCodePageRange1` / `fsSelection` / 手写 `ulUnicodeRange`），此即「Word 里装了却用不上」的根因修复 |

补充规则：

| 项 | 规则 |
|---|---|
| 首个版本 | v1.0.0 是首个公开发布版本，此前不存在公开版本号；上表三段规则自 v1.0.0 起适用 |
| 预发布标识（拟议） | `-alpha.N` / `-rc.N` 后缀；**尚未使用过**，仅登记规则，不作为既有事实 |
| 产物日期段 | 发布产物名带发布日：`PixelFontPC98-12-2026-10-24.zip`；日期段随**发布**变化，不随每次构建变化 |
| 版本与 commit | 每个发布版本必须能追溯到一个 commit；v1.0.0 对应 `4300fc1` |
| 判定证据 | 段位判定必须由 §3 的判据实测得出，不能凭「感觉改动大」 |

### 2.2 家族与版本的对应

| 家族 | name ID 1 / 16 | PostScript 名 | achVendID | 当前版本 | 版本序列规则 |
|---|---|---|---|---|---|
| `PixelFont PC98 12` | `PixelFont PC98 12` | `PixelFontPC98-12` | `PXLF` | **v1.0.0**（已发布，2026-10-24） | 自 v1.0.0 起按 §2.1 三段规则递增；单序列，无并行版本线 |
| `PixelFont Multi 12` | `PixelFont Multi 12` | `PixelFontMulti-12`（**已构建验证**，2026-10-25） | `PXLF`（**已验证**，沿用项目 vendor ID） | **v1.1.0**（独立序列） | **独立版本序列**，自 v1.0.0 起编号，与 `PixelFont PC98 12` 互不递增、互不覆盖 |

**多家族并存时的 tag 命名**（2026-10-25 补）：

两个家族的版本序列各自从 `v1.0.0` 起步，但**同一个 git 仓库里 tag 名字是全局唯一的** ——
两个家族都用 `v1.0.0` 会撞车。因此规定：

| 家族 | tag 形式 | 例 |
|---|---|---|
| `PixelFont PC98 12` | `v<版本>`（**已发布，不可改**） | `v1.0.0` |
| `PixelFont Multi 12` | `<家族短名>-v<版本>` | `multi12-v1.0.0`、`multi12-v1.0.1`、`multi12-v1.1.0` |

`multi12` 短名取自 PostScript 名 `PixelFontMulti-12` 的小写化短形式。
先发布的家族保留无前缀形式（历史既成），后发布的家族必须带前缀。

多语言版的相关既有事实（用于说明为何必须独立成家族）：
| 项 | 值 | 来源 |
|---|---|---|
| 形态决策 | 新增独立家族，现有 `PixelFont PC98 12` 不动 | 底稿 §13 拍板决策 ② |
| 范围决策 | 方案 C（A + 全部 CJK）= **31,753 码位**（原决策 31,392，2026-10-25 扩到 31,753） | 底稿 §13 逐层账目 + `multi12-v1.1.0` 变更记录（19,816 + 11,937 = 31,753） |
| 中日共享汉字 | **2,078**；共享字默认取**中文形（zh_hans 源）**，JIS 独有 **2,297** 走 ja 源 | 底稿 §13.2 |
| 中日字形分歧 | 共享字中 **434 / 2,078（20.9%）** 像素不同 | 底稿 §13.3 实测 |
| 变体机制 | GSUB `locl` **未选**（架构改动过大） | 底稿 §13 拍板决策 ③ |

> **产物名必须带家族名**（已落地）：发布包名形如 `PixelFontMulti-12-<发布日>.zip`；
> **同一发布日在同一家族上发布多次时改用 `PixelFontMulti-12-<版本>.zip`**
> —— v1.0.0 与 v1.0.1 就撞在同一天，日期式命名会让两个 Release 出现
> **同名但内容不同**的附件。`multi12-v1.1.0` 起用的是后者
> （`PixelFontMulti-12-v1.1.0.zip`）。打包脚本 `tools/fontgen/package_multi12.py`。

### 2.3 兼容性判定

兼容性口径：下游是否已经在用这个字体排版内容、且内容的外观/布局不能被改变。

| 变更类型 | 兼容性 | 判定依据 | 处置 |
|---|---|---|---|
| 新增码位 | **向后兼容** | 已有码位位图不变，advance 不变 | MINOR；发布说明列出新增码位清单 |
| 单字形外观修正 | **视觉不兼容**（内容不变） | 该码位在 12 / 24 ppem 下位图改变 | MINOR；发布说明**逐字列出**码位与原因 |
| UPM / ascent / descent / cell 高变更 | **破坏性** | 行高与基线改变 → 换行与基线对齐全变 | MAJOR；必须给迁移说明 |
| advance 变更 | **破坏性** | 行宽改变 → 换行位置改变 | MAJOR |
| 家族名 / name ID 1、16 变更 | **破坏性** | 字体身份变更 → 已有引用 `PixelFontPC98-12` 的配置失配 | MAJOR |
| PostScript 名变更 | **破坏性** | 同上（PostScript 名被大量工具用作标识） | MAJOR |
| `name` 表其它字段变更（版权、许可、描述） | 向后兼容 | 不参与选择与排版 | PATCH；发布说明记录 |
| `OS/2` `fsSelection` 变更 | **可能破坏字体选择** | 缺 REGULAR（0x0040）时 Windows 可能不把它当正文常规字 | 按 PATCH 发布，但必须过 §3 判据 09（Windows 选择 + 全字符集栅格化） |
| `OS/2` `ulCodePageRange*` 变更 | **可能破坏字体选择** | 代码页位决定字体的语言归属 | 同上 |
| `OS/2` `ulUnicodeRange*` 变更 | 向后兼容 | 由 fontTools 按 cmap 实际覆盖重算，与 cmap 一致即可 | PATCH；**不手写查表**（手写查表会再次出错） |
| `gasp` 变更 | 视觉相关 | 影响是否请求灰度抗锯齿 / 网格拟合 | 若改变 12 整数倍下像素 → MINOR；否则 PATCH |
| 移除码位 | **破坏性** | 已有文本掉字 | MAJOR |
| 轮廓细分策略变更（不改位图） | 向后兼容（整数倍字号下） | 位图集合不变，仅轮廓数/文件大小变化 | PATCH（如 `8ae04fc`） |

对照表：当前 v1.0.0 的 `OS/2` 取值（commit `cef4a22` 修复后）

| 字段 | 值 | 为什么 |
|---|---|---|
| `ulCodePageRange1` | `(1<<0) \| (1<<17) \| (1<<18)` = 1252 + 932 + 936 | 覆盖 Latin-1 / Shift-JIS / GB2312 三套代码页 |
| `fsSelection` | `0x0040`（REGULAR） | 缺 REGULAR 时 Windows 可能不把它当正文常规字 |
| `ulUnicodeRange1`–`4` | **不手写**，由 fontTools 按 cmap 实际覆盖重算 | 手写查表会再次出错 |
| `gasp` | `{0xFFFF: 0}` | 像素字不该请求灰度抗锯齿或网格拟合 |

> 历史教训（旧值 `ulCodePageRange1 = 0x00030000` 实际是 bit16 泰语 + bit17，既没有 1252 也没有 936；`fsSelection` 为 0x0000）就是「元数据错误 → 装了却用不上」的直接成因，因此 `OS/2` 字段变更必须走 §3 判据 09。

### 2.4 字形修改记录规范

单条记录描述「一个码位的字形在某个时间点发生了什么变化、为什么、谁批准的」。字段定义如下（**拟议格式**，尚无台账文件承载，见本节末）：

| 字段 | 含义 | 必填 | 取值 / 格式 |
|---|---|---|---|
| 记录 ID | 记录唯一标识 | 是 | `GLY-<U+XXXX>-<YYYYMMDD>` 形式 |
| 日期 | 变更发生日 | 是 | `YYYY-MM-DD` |
| 码位 | 被修改的码位 | 是 | `U+XXXX` |
| 旧字形指纹 | 修改前的字形外观摘要 | 是 | §2.4.1 定义 |
| 新字形指纹 | 修改后的字形外观摘要 | 是 | §2.4.1 定义 |
| 异或格数 | 新旧位图逐格异或的格子数 | 是 | 整数；0 表示无变化；口径已在多语言版中日字形差异实测中使用（最大 78 格，例：`肩` U+80A9 = 78、`扇` U+6247 = 71） |
| 修改原因 | 为什么改 | 是 | 自由文本；应指明是「源字体惯例修正」「字形错误修正」「新增覆盖」哪一类 |
| 影响面 | 是否影响 advance / 度量 / advance 宽度 | 是 | 枚举：`字形外观` / `advance` / `度量` / `无` |
| 审核状态 | 该修改是否已裁决 | 是 | 沿用既有对抗审核口径：`待裁决` / `已裁决非缺陷` / `确认缺陷` |
| 关联 commit | 产生该修改的提交 | 是 | 短 hash + 提交信息前缀（见 §2.6） |
| 关联源与许可 | 该码位当前字形来自哪个源 | 是 | `SimHei` / `MS Gothic` / `Fusion Pixel 12px`（三者许可状态见 §5） |

#### 2.4.1 字形指纹定义（拟议）

| 项 | 定义 |
|---|---|
| 摘要内容 | 12×13 单色位图，按行打包（12 bit / 行，共 13 行） |
| 摘要算法 | `sha256`（**拟议**，尚未在仓库中实现） |
| 可比对性 | 与 `reports/gdi_raster_scan.tsv`（逐码位 4,162 行）中的逐码位栅格结果口径一致，可直接互相印证 |
| 兜底口径 | 无法取得指纹时，用「异或格数 + 12 / 24 ppem 逐格一致」两项断言 |

#### 2.4.2 当前记录落点（现状）

| 项 | 现状 |
|---|---|
| 现有落点 | `tools/fontgen/adversarial_review.py` 的裁决结果 + `reports/` 目录（`gdi_compat.json` 摘要 1.5KB、`gdi_raster_scan.tsv` 逐码位 4,162 行） |
| 对抗审核当前计数 | 三轮独立攻击面命中 60 / 139 / 19，待裁决 **0**，已裁决非缺陷 **169**，确认缺陷 **0** |
| 缺口 | **尚未有独立的字形修改台账文件** —— 无法机器化回答「某码位何时、为何、由哪个 commit 改成现在这样」 |
| 处置 | 列为 §5 待办；本文只定字段规范，不假装台账已存在 |

### 2.5 分支与集成政策

| 分支 | 用途 | 与主干的同步方式 | 硬约束 |
|---|---|---|---|
| `dev` | **集成分支**。全部 32 个提交的工作都在 `dev` 上 | 是 `main` 的唯一上游；`main` 由 `dev` 快进而来 | 推送必须走 gh 凭据通道，否则 Windows credential manager 会拦；提交信息前缀见 §2.6 |
| `main` | **发布镜像**。只接受 `dev` 的快进 | `git push origin dev:main`（配 `--ff-only` 语义，即目标必须可快进） | `main` 与 `dev` **零分叉**；`main` 上**没有 CI 流水线**（仓库无 `.github/` 目录），快进不会触发任何自动发布 —— 发布必须人工按 §2.7 执行 |

| 事实 | 说明 |
|---|---|
| 仓库最初只有 `LICENSE` 一个文件（初始提交） | 32 个提交的工作全在 `dev` 上 → 谁 clone 仓库都看不到项目本身，所以 `main` 与 `dev` 必须同步 |
| 零分叉的检验 | `git rev-list main..dev` 与 `git rev-list dev..main` 均为空 |
| 快进的检验 | `git merge-base --is-ancestor main dev` 返回 0 |
| 发布镜像的额外含义 | `main` 上的 tag 即发布版本；`v1.0.0` 注解 tag 指向 `main` 的 `4300fc1` |

### 2.6 提交信息规范

| 前缀 | 用途 | 示例 |
|---|---|---|
| `docs(spec):` | 规格 / 设计文档变更 | `docs(spec): 补充版本与变更管理书` |
| `feat(font):` | 字体生成逻辑或字形集合变更 | `feat(font): v1.0.0 -- 首个实测可在 Word 中使用的版本`（`v1.0.0` tag 说明原文） |
| `feat(verify):` | 门禁 / 校验能力扩充 | `feat(verify): GDI 门禁扩到全字符集逐格验证` |
| `fix(font):` | 字体生成或元数据缺陷修复 | `fix(font): 修 OS/2 元数据三处错误`（`cef4a22`） |
| `docs:` | 非规格类文档变更 | `docs: 用 10-24 远端 clone 复跑结果刷新可复现性表`（`4300fc1`） |
| `chore:` | 构建脚本 / 杂项维护 | `chore: 更新 vendor 裁剪脚本` |

| 约束 | 内容 |
|---|---|
| 正文语言 | **中文** |
| 格式 | `<前缀>: <主题>`，主题一行说清改了什么 |
| 关联 | 影响字形的提交必须在正文中指出受影响的码位或范围，以便回填 §2.4 台账 |

### 2.7 发布流程与门禁

| 阶段 | 动作 | 判据 | 失败处置 |
|---|---|---|---|
| 1 准备 | 确认 `dev` 与 `main` 零分叉；确认工作区干净 | `git rev-list main..dev` 与 `git rev-list dev..main` 均为空 | 先同步分支，不进入构建 |
| 2 构建 | `python tools/fontgen/build_font.py` | 构建成功，无缺字门禁 / 路由名单门禁失败 | 修生成源后重跑，不得跳过门禁 |
| 3 验收 | `python tools/fontgen/verify_all.py`（8 步，约 6 分钟） | **8/8 PASS**；回归 0 error 0 warn；硬检查命中 71（warn 69 / error 2，参考集分歧）；对抗审核三轮 60 / 139 / 19，待裁决 0，确认缺陷 0 | 任一步失败即中止发布，修复后从阶段 2 重跑全链 |
| 4 Windows 兼容门禁 | `python tools/fontgen/verify_gdi.py`（全字符集，约 9 秒） | 12ppem 与 24ppem 各 **4,161 / 4,161** 逐格一致；抗锯齿像素 **0** | 同上 |
| 5 产物指纹 | 计算 `dist/` 产物 sha256 | TTF = `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1`；zip = `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8` | 与预期不符 → 查构建是否含未提交改动，禁止发布 |
| 6 打包 | 产出 `PixelFontPC98-12-<发布日>.zip`；**同一发布日在同一家族上发布多次时改用 `<家族>-<版本>.zip`** | zip 内实际 **9 项**：`PixelFontPC98-12.ttf` / `.bdf` / `-atlas.png` / `-specimen.png` / `安装与使用说明.md` / `word-compat.md` / `SHA256SUMS.txt` / `说明-各字号渲染对比.png` / `说明-轮廓合并前后对比.png` | 条目数或内容不符 → 重打包 |
| 7 发布前自检 | 逐字节核对 zip 与 `dist/` 内对应文件 | 完全一致 | 重打包 |
| 8 **回下载校验** | 从 GitHub 重新下载已上传资产，逐字节比对 | 与上传件**逐字节一致**（v1.0.0 已做过：一致） | 不一致 → 撤回 Release 重传 |
| 9 **实际渲染抽检** | 用回下载回来的 TTF 在 GDI 中选中并渲染 | 正常被选中、正常渲染（v1.0.0 已做过：通过） | 不通过 → 撤回 Release |
| 10 打 tag | `git tag -a <version> -m "<说明>"` 打在 `main` 上 | 注解 tag 指向 `main` 的发布 commit | 指向错误 → 删 tag 重打 |
| 11 建 Release | `gh release create`，`draft=false` | 附件 **5 个**：zip / ttf / `PixelFontPC98-12-sizescale.png` / `PixelFontPC98-12-merge-before-after.png` / `SHA256SUMS`。（**`PixelFont Multi 12` 是 6 个** —— 多了 `OFL.txt`：OFL-1.1 要求随包附许可证全文，是必须项） | 附件缺失 → 补传后重做阶段 8、9 |
| 12 推分支 | 按 §4 凭据通道推 `dev`，再推 `dev:main` | 推送成功且远端 `main` == 远端 `dev` | 重推 |

> 阶段 8、9 的定位：**不信任上传结果或任务状态这类间接信号，一律以回下载后的实际字节与实际渲染为准**。v1.0.0 走完这两步（逐字节一致 + GDI 渲染通过）。

### 2.8 发布历史

| 版本 | 日期 | 变更摘要 | 产物指纹（TTF） | tag |
|---|---|---|---|---|
| 旧版（10-23） | 2026-10-23 | 元数据错误（`ulCodePageRange1` = 0x00030000 无 1252/936；`fsSelection` = 0x0000 缺 REGULAR），Word 选不中 | 1,362,480 字节 / `FCC65BCBCD8A1A022007065E3444464916EDB537BB172B6F2ACDC9596DE3303B` | 无（未发布） |
| 中间版（10-24 早） | 2026-10-24 | 元数据已修（`cef4a22`），轮廓未合并 | 1,364,528 字节 / `269619D5EAA0B84BC478B550893C6F5CCAAB6B0709F86AB19433AD5A8A46B2D3` | 无（未发布） |
| **v1.0.0** | **2026-10-24** | ① `OS/2` 元数据三处修复（`cef4a22`）；② 字符集 4,140 → **4,161**，补 21 个 Word 常用字符，新增 `charset.SOURCE_OVERRIDES` 与 `bitfont.ScriptStack` 的 `overrides` 通道，修 `U+005C` 被 MS Gothic 按 JIS 惯例画成 `¥` 的缺陷（`729403c`）；③ GDI 门禁从 6 样字扩到全字符集逐格验证，新增 `docs/install.md`（`c403eea`）；④ 合并竖向相邻等宽游程，轮廓 107,209 → **73,933**、TTF 1,364,528 → **973,712** 字节，整数倍精确性 **12,483 / 12,483** 未破（`8ae04fc`）；⑤ 刷新可复现性表（`4300fc1`） | **973,712 字节** / `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1` | **注解 tag `v1.0.0`** → `main` 的 `4300fc1`，说明「feat(font): v1.0.0 -- 首个实测可在 Word 中使用的版本」 |
| **multi12-v1.0.0** | **2026-10-24** | **`PixelFont Multi 12` 家族的首个版本** —— 独立序列，与上表互不递增。字符集 **31,392** 码位（汉字 19,317 / 谚文 11,172 / 拉丁系 593 / 假名全角标点 305 / 其它 5），生产源全部 OFL-1.1（Fusion Pixel 12px + 4 个原创手绘），成品可自由分发、可商用（`ec064e4`、`b6350ef`）；`OS/2` 声明 bit19 韩文代码页，否则 GDI 在 `lfCharSet=HANGEUL` 下根本不会考虑本字体（`b6350ef`）；PostScript 名定为 `PixelFontMulti-12`，与 `PixelFontPC98-12` 同一套风格（`8c19d9d`） | **7,736,520 字节** / `D28E0FB5134415319A9A42F19A706463C9FDDC8A992F76729BAB7F9FF5131913` | **注解 tag `multi12-v1.0.0`** → `main` 的 `a3509b3` |
| **multi12-v1.0.1** | **2026-10-25** | **PATCH** —— 字体产物与 v1.0.0 **逐字节相同**（重建后 6 个产物 sha256 全部 IDENTICAL），改的是**验证门禁**：① 快照自洽门禁的「层必须互斥」是永不触发的死门禁（`layer` 是 `{码位: 层名}` 字典，一个码位只可能有一个层名）；② 门禁记下「未登记的源」后没中止，下一步崩成 `KeyError` 盖住报错；③ 错误报告 `problems[:20]` 全局截断，把「缺少这些层」这类根因挤掉；④ 层名与标签只存在于快照里，没有外部基准。配套新增 `tools/fontgen/verify_snapshot_gate.py`（8 种故障注入全抓到，并区分「报错」与「崩了」）—— 该自测当场抓出了 ② 与 ③ | **7,736,520 字节**（同 v1.0.0） / `D28E0FB5134415319A9A42F19A706463C9FDDC8A992F76729BAB7F9FF5131913` | **注解 tag `multi12-v1.0.1`** → `main` 的 `0b9c686` |
| **multi12-v1.1.0** | **2026-10-25** | **MINOR** —— 字符集 **31,392 → 31,753**（新增 361 个码位），**已发布码位的位图一个都没变**（纯新增）。① 引入 **ZLabs Pixel 12px CN**（OFL-1.1）作简体补源：实测 Fusion 与 Ark 的**七个变体全都缺 128 个 GB2312 二级汉字**，只有 ZLabs 覆盖 GB2312 全部 6,763 个；② 把「日语字和中文简体都是全量」写成**硬门禁**（字符集门禁 6/7，口径由 `gb2312` / `shift_jis` 编码器机械判定），并新增 `tools/fontgen/verify_coverage_gates.py` 对 4 道新门禁做故障注入（7/7 抓到）；③ 新增推导门禁 11「zlabs_cn 只承接 Fusion 两源都不覆盖的码位」，从**规则结构**上保证已发布码位路由不变；④ 修「裁剪不是逐字节可复现」（差异只在 head 表 `modified` 一个字段）；⑤ 修 `vendor_multi12_sources.py --check` 文档与实现矛盾（它需要 third_party，干净克隆上会抛错）；⑥ 打包流程入库为 `tools/fontgen/package_multi12.py`（**可复现**，此前是临时脚本）；⑦ 发布包 `OFL.txt` 改为列出**全部**三个上游的版权声明与保留字体名（此前漏了 Fusion 的）；⑧ 发布包名改用版本号（`PixelFontMulti-12-v1.1.0.zip`），避免同日重名 | **7,853,876 字节** / `B844D8C1F92114ACFCB2745DCFF6C1C13711BB6853B372D6BAB6B8137BF87C15` | **注解 tag `multi12-v1.1.0`** → `main` 的 `334740c` |

`PixelFont Multi 12` 的发布事实（独立于上表的 PC98 12 行）：

| 发布事实 | 值 |
|---|---|
| Release 状态 | 正式版（`draft=false`） |
| 最新 Release | `multi12-v1.1.0` → <https://github.com/UlyssesLeoLee/PixelFont/releases/tag/multi12-v1.1.0>（标记为 Latest） |
| 上一版 | `multi12-v1.0.1` → <https://github.com/UlyssesLeoLee/PixelFont/releases/tag/multi12-v1.0.1> |
| 附件数 | **6**（三版都是） |
| zip 附件 | v1.1.0：`PixelFontMulti-12-v1.1.0.zip`，2,681,102 字节 / `68FC526C9566AEE4B3C76EECCEC9A5ECCDD15495EE1337CBEB5A46E2FDB44C7AC`；v1.0.1：`PixelFontMulti-12-2026-10-25.zip`，2,626,345 字节 / `729C3D457C3AB331B50BC330EE129DD592E82B98BD9360D73D711C8A1C0EFB78`；v1.0.0：`PixelFontMulti-12-2026-10-24.zip`，2,626,345 字节 / `6EAB85EAECB1DEE433DC7F40E43F554AB9023D81475D96C554AE9FF903012FD9`（**包内 7 项**：TTF / BDF / 图集 / 样张 / 安装说明 / OFL 全文 / 校验和。v1.0.0 与 v1.0.1 的 zip sha256 不同，**仅因为包内条目时间戳跟着发布日走**；字体产物字节完全相同。v1.1.0 起打包由 `tools/fontgen/package_multi12.py` 生成，**条目时间戳固定** —— 同样的输入产出同样的字节） |
| ttf 附件 | v1.1.0：`PixelFontMulti-12.ttf`，7,853,876 字节 / `B844D8C1F92114ACFCB2745DCFF6C1C13711BB6853B372D6BAB6B8137BF87C15`；v1.0.0 / v1.0.1：7,736,520 字节 / `D28E0FB5134415319A9A42F19A706463C9FDDC8A992F76729BAB7F9FF5131913`（两版相同） |
| 图集 / 样张附件 | v1.1.0：`PixelFontMulti-12-atlas.png` 780,395 字节 / `6012EDAB6E61BD11EF680B40B69E51FAA07B8A57D01B609AB053AB681EA1A9BC`；v1.0.0 / v1.0.1：764,187 字节 / `6DF3BFCE5E24CA135D94F7D12BA836F352908C2DF4627752C8D43021C1EE63CA`。样张三版相同：3,174 字节 / `C9D93FF4E4EFEAE4C0C61BB5E96342584AC77D8E0475755566A1BF0B75931A25` |
| 许可附件 | v1.1.0：`OFL.txt` 5,360 字节 / `18B74DA7A733340EAD037E30EAA63FF5C4CB58E02ADD5DF77A5B2F1D79E98E87`（**列出全部三个上游的版权声明与保留字体名**）；v1.0.0 / v1.0.1：4,518 字节 / `983AF89B36518A85EE5205B6CAD1DE232DBC2852B536C50FF2956BF74DB3B5A4`（OFL-1.1 要求随包附全文，**必须项**；此前**漏了 Fusion 的版权声明** —— v1.1.0 修掉） |
| 回下载校验 | 6 个资产重新下载后**逐字节一致**；下载回的 TTF 在 GDI 中被正常选中，全字符集 **31,753** 码位 × (12 ppem + 24 ppem) 与设计位图**逐格一致**，抗锯齿像素 **0**（`python tools/fontgen/verify_gdi_multi12.py --ttf <回下载路径> --bdf <回下载 zip 内路径>`）；另与 `multi12-v1.0.1` 的 TTF 逐字形比对，**31,392 个已发布码位的位图全一致** |

`PixelFont PC98 12` 的发布事实：

| 发布事实 | 值 |
|---|---|
| Release 状态 | 正式版（`draft=false`） |
| 附件数 | **5** |
| zip 附件 | `PixelFontPC98-12-2026-10-24.zip`，533,116 字节 / `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8` |
| ttf 附件 | `PixelFontPC98-12.ttf`，973,712 字节 / `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1` |
| 说明图附件 | `PixelFontPC98-12-sizescale.png` 32,725 字节 / `c3b117dcfe1ea20aebb8c2b3be709a2a604b62fd62f7c24458e3e91fa2b373bc`；`PixelFontPC98-12-merge-before-after.png` 16,440 字节 / `80cf703189e7a00cd73c472e4aa210b474ceec376e5e75dfffe28c9e04707a61` |
| 回下载校验 | 资产重新下载后**逐字节一致**，且下载回的 TTF 在 GDI 里正常被选中与渲染 |
| 历史完整性 | `main` 与 `dev` 零分叉；`CHANGELOG.md` 已入仓（commit `d1aa64c`），发布历史由它 + Release notes + git 历史三者共同维系 |

### 2.9 产物版本识别

用户手里的 TTF 属于哪一代 —— 不看文件名，看字节数与 sha256。

| 版本 | TTF 字节 | sha256 | 状态 | 识别口径 |
|---|---|---|---|---|
| 旧版（10-23） | 1,362,480 | `FCC65BCBCD8A1A022007065E3444464916EDB537BB172B6F2ACDC9596DE3303B` | 元数据错误，Word 选不中 | 字节数落在 1,362,480 ± 0 即可初判，再以 sha256 确认 |
| 中间版（10-24 早） | 1,364,528 | `269619D5EAA0B84BC478B550893C6F5CCAAB6B0709F86AB19433AD5A8A46B2D3` | 元数据已修，轮廓未合并 | 同上 |
| **当前版（v1.0.0）** | **973,712** | **`3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1`** | 元数据已修 + 轮廓已合并 | 字节数 < 1,000,000 即可初判为当前代 |

| 识别口径 | 说明 |
|---|---|
| 一级：字节数 | 三代字节数两两不同（1,362,480 / 1,364,528 / 973,712），无需哈希即可区分 |
| 二级：sha256 | 精确确认，用于回下载校验与发布核对 |
| 三级：行为特征 | 旧版在 Word 字体列表中选不中；中间版在非整数倍字号下笔画断裂；当前版两者都正常 |
| 本机现状 | 本机已安装的是 **10-23 旧版**（1,362,480 字节），**尚未覆盖** —— 拿本机字体验证新版时必须先确认装的是 v1.0.0 |

### 2.10 仓库内容政策

| 路径 | 是否入库 | 理由 |
|---|---|---|
| `dist/` | **不入库** | 成品字形派生自 **SimHei / MS Gothic**（微软专有），分发权受限，不进公开仓库。**注意**：`PixelFont Multi 12` 的生产源全部是宽松许可（Fusion Pixel OFL-1.1 + 本仓库原创手绘 OFL-1.1），**不受这条限制** —— 它可自由分发、可商用；但为保持「产物不入库、走 Release」这一条政策不变，本项目对**两个家族一视同仁**，`dist/` 仍不入库 |
| `vendor/` | **入库** | 生产源参与构建（Fusion Pixel 12px 的四个变体 + ZLabs Pixel 12px CN 简体补源 + 本仓库原创手绘，均 OFL-1.1）：不入库则换台机器构建不出同一结果。裁剪后入库：`vendor/multi12/`（5 个裁剪版 + `handdrawn-glyphs.txt` + `OFL.txt` + `LICENSES/` 下 5 份许可）。**裁剪必须逐字节可复现** —— 2026-10-25 修掉了「重新裁剪产出字节不同的文件」（差异只在 head 表 `modified`） |
| `third_party/` | **不入库** | 参考字体只用于校验（Ark Pixel 12px、Zpix v3.3.0、GNU Unifont 16.0.01 等），只记来源 / 版本 / 许可证 / sha256 清单（`docs/reference-fonts.md`），由 `tools/fontgen/fetch_ref_fonts.py` 按需抓取、`--verify` 只校验不重下 |
| `tools/fontgen/` | **入库** | 构建与门禁代码，仓库 `LICENSE` = **GNU AGPL-3.0** 覆盖此目录 |
| 报告 `reports/` | 入库 | 门禁证据（`gdi_compat.json` 摘要 1.5KB、`gdi_raster_scan.tsv` 逐码位 4,162 行） |

---

## 3. 验收判据

| 编号 | 规则或要求 | 判据（可量化） | 验证方式 |
|---|---|---|---|
| V-01 | `dev` 与 `main` 零分叉 | `git rev-list main..dev` 与 `git rev-list dev..main` 输出行数均为 **0** | §4 命令块 A1 |
| V-02 | `main` 可被 `dev` 快进 | `git merge-base --is-ancestor main dev` 退出码 **0** | §4 命令块 A2 |
| V-03 | 发布镜像无自动副作用 | 仓库存在 `.github/` 目录 = **否** | §4 命令块 A3 |
| V-04 | 提交信息前缀合规 | 最近 **20** 条提交全部匹配 `^(docs(spec)\|feat(font)\|feat(verify)\|fix(font)\|docs\|chore): ` | §4 命令块 A4 |
| V-05 | 产物指纹与已发布版一致 | `dist/PixelFontPC98-12.ttf` 字节 = **973,712**，sha256 = `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1` | §4 命令块 B1 |
| V-06 | 质量门禁全通过 | `verify_all.py` **8/8 PASS**；回归 **0 error / 0 warn** | §4 命令块 B2 |
| V-07 | 字形硬检查结果已知 | 命中 **71**（warn 69 / error 2，参考集分歧） | §4 命令块 B2 输出 |
| V-08 | 对抗审核已清账 | 三轮命中 60 / 139 / 19；待裁决 **0**；已裁决非缺陷 169；确认缺陷 **0** | §4 命令块 B2 输出 |
| V-09 | Windows 字体选择与栅格化 | GDI 字体选择成功；12ppem 与 24ppem 各 **4,161 / 4,161** 逐格一致；抗锯齿像素 **0** | §4 命令块 B3 + `reports/gdi_compat.json` |
| V-10 | 度量不变量未被改动 | UPM = **768**；ascent **11** / descent **2**；cell 高 **13**；半角 advance **6** / 全角 **12**；1 像素 = **64** 单位 | `tools/fontgen/build_font.py` 的 `UPM` 常量 + `tools/fontgen/bitfont.py` 的 `cell_ascent` / `cell_descent` |
| V-11 | `OS/2` 不变量 | `ulCodePageRange1` 含 bit0/17/18（1252+932+936）；`fsSelection` = **0x0040**；`ulUnicodeRange1–4` 与 cmap 实际覆盖一致；`gasp` 不含 DOGRAY/GRIDFIT | `build_font.py::verify_ttf_metadata()` 硬拦 + §4 命令块 B1 回读 |
| V-12 | 包内容完整 | zip 内实际 **9 项**（清单见 §2.7 阶段 6）；Release 附件 **5 个** | §4 命令块 C1 / C2 |
| V-13 | 回下载逐字节一致 | 回下载资产的 sha256 与发布时一致（v1.0.0：TTF 与 zip 均一致） | §4 命令块 C3 |
| V-14 | 回下载产物可渲染 | 回下载 TTF 在 GDI 中被正常选中并渲染 | §4 命令块 B3（指向回下载目录） |
| V-15 | tag 指向发布镜像 | `v1.0.0` 为**注解 tag**，指向 `main` 的 `4300fc1` | §4 命令块 C4 |
| V-16 | 仓库内容政策 | `dist/` 与 `third_party/` 在 `git ls-files` 中**无条目**；`vendor/` 中存在上述 4 个已知路径 | §4 命令块 A5 |
| V-17 | 生产源自检 | Fusion 裁剪版与原字体逐像素一致，且裁剪版 cmap == 原字体 cmap ∩ 本项目字符集 | `python tools/fontgen/vendor_fusion_pixel.py --check` |
| V-18 | 参考字体清单完整 | 参考字体来源 / 版本 / sha256 与 `docs/reference-fonts.md` 相符 | `python tools/fontgen/fetch_ref_fonts.py --verify` |

---

## 4. 复现命令

以下命令在 `E:\PixelFont`（PowerShell 7）执行。

### A. 分支与仓库状态

```powershell
# A1 零分叉检查：两行输出都应为 0
git -C E:\PixelFont rev-list --count main..dev
git -C E:\PixelFont rev-list --count dev..main

# A2 快进检查：无输出且退出码为 0 表示 main 是 dev 的祖先
git -C E:\PixelFont merge-base --is-ancestor main dev
$LASTEXITCODE   # 期望 0

# A3 发布镜像上无 CI（仓库无 .github/ 目录）
Test-Path E:\PixelFont\.github   # 期望 False

# A4 提交信息前缀合规（期望最近 20 条全部命中）
git -C E:\PixelFont log --oneline -n 20
git -C E:\PixelFont log -n 20 --pretty=%s |
  Select-String -NotMatch '^(docs\(spec\)|feat\(font\)|feat\(verify\)|fix\(font\)|docs|chore): '

# A5 仓库内容政策（dist/ 与 third_party/ 期望无输出；vendor/ 期望列出已知 4 个路径）
git -C E:\PixelFont ls-files dist third_party
git -C E:\PixelFont ls-files vendor
```

### B. 构建与验收

```powershell
# B0 重建字体
Set-Location E:\PixelFont
python tools/fontgen/build_font.py

# B1 产物指纹（期望 973,712 字节 / 3298AE4D...F69FB1）
Get-Item dist\PixelFontPC98-12.ttf | Select-Object Length
Get-FileHash -Algorithm SHA256 dist\PixelFontPC98-12.ttf

# B2 全链路 8 步验收（约 6 分钟）
# 期望：8/8 PASS；回归 0 error 0 warn；硬检查命中 71（warn 69 / error 2）；
#       对抗审核三轮 60/139/19，待裁决 0，已裁决非缺陷 169，确认缺陷 0
python tools/fontgen/verify_all.py

# B3 Windows 兼容门禁（全字符集，约 9 秒）
# 期望：12ppem 与 24ppem 各 4161/4161 逐格一致，抗锯齿像素 0
python tools/fontgen/verify_gdi.py
Get-Content reports\gdi_compat.json
(Get-Content reports\gdi_raster_scan.tsv).Count   # 期望 4162 行
```

### C. 发布物与回下载校验

```powershell
# C1 包内容（期望 9 项）
Expand-Archive -Path dist\PixelFontPC98-12-2026-10-24.zip -DestinationPath .\_pkg -Force
(Get-ChildItem .\_pkg -Recurse -File).Count   # 期望 9

# C2 Release 资产（期望 draft=false、5 个附件）
gh release view v1.0.0 --repo UlyssesLeoLee/PixelFont

# C3 回下载 + 逐字节比对
# 期望：TTF 3298AE4D...F69FB1、zip 96EE924E...50FDE8（与 §2.8 一致）
gh release download v1.0.0 --repo UlyssesLeoLee/PixelFont -D .\_dl --clobber
Get-FileHash -Algorithm SHA256 .\_dl\PixelFontPC98-12.ttf
Get-FileHash -Algorithm SHA256 .\_dl\PixelFontPC98-12-2026-10-24.zip

# C4 tag 指向检查（期望指向 main 的 4300fc1）
git -C E:\PixelFont ls-remote --tags origin
```

### D. 推送（必须走 gh 凭据通道）

```powershell
# 否则会被 Windows credential manager 拦
git -C E:\PixelFont -c credential.helper= -c "credential.https://github.com.helper=!gh auth git-credential" push origin dev
git -C E:\PixelFont -c credential.helper= -c "credential.https://github.com.helper=!gh auth git-credential" push origin dev:main
```

### E. 源与参考字体校验

```powershell
# 生产源自检（裁剪版与原字体逐像素一致 + cmap 覆盖相符）
python tools/fontgen/vendor_fusion_pixel.py --check

# 参考字体清单校验（只校验不重下）
python tools/fontgen/fetch_ref_fonts.py --verify
```

---

## 5. 已知边界与待办

| 编号 | 事项 | 状态 | 下一步 |
|---|---|---|---|
| B-01 | 仓库**没有 `CHANGELOG.md`**，发布历史只靠 GitHub Release notes + git 历史维系 | **已落地**（commit `d1aa64c`） | `CHANGELOG.md` 已补：Keep a Changelog 1.1.0 + SemVer 2.0.0，两个家族的版本序列分列（「何时算一次发布」按 §2.7 阶段 10 的 tag 判定） |
| B-02 | **没有独立的字形修改台账文件** —— 字形改动记录散落在 `adversarial_review.py` 裁决结果与 `reports/` 下 | 待办 | 按 §2.4 字段规范建台账；先落 2.4.1 的指纹定义（12×13 位图打包 + sha256），再回填 v1.0.0 涉及的码位（`U+005C` 及 21 个新增字符） |
| B-03 | 多语言版 `PixelFont Multi 12` 的版本标识与命名规则 | **已落地**（2026-10-25） | PostScript 名 `PixelFontMulti-12`、vendor ID `PXLF` 均经构建与 GDI 门禁验证；版本走**独立序列**自 v1.0.0 起。构建期曾误用 `PixelFontMulti12`（无连字符），已按 §2.2 与同项目 `PixelFontPC98-12` 的风格改回 |
| B-04 | 单字重 **Regular**，无 Bold / Italic，无可变字体轴 | 已知边界 | 若未来加字重，须按 §2.1 判 MAJOR（度量与 advance 影响排版） |
| B-05 | 无 kerning、无连字、无 OpenType 特性（除 `gasp`） | 已知边界 | 多语言版已因「架构改动过大」放弃 GSUB `locl`；如需变体机制须另立专项 |
| B-06 | **只有 12 的整数倍字号能逐格还原设计**（12 / 24 / 36 ppem = 9 / 18 / 27 pt @96dpi）；非整数倍（如 18ppem = 1.5 倍）笔画断裂 + 墨迹量偏细 **43%** | 已知边界（已实测） | 在安装说明与发布说明中持续标注；`8ae04fc` 的游程合并已把断裂面从 107,209 轮廓降到 73,933，但非整数倍仍不精确 |
| B-07 | 本机已安装的是 **10-23 旧版**（1,362,480 字节，sha256 `FCC65BCC…3303B`），**尚未覆盖** | 待办 | 验证新版前先覆盖安装；否则「Word 里用不上」可能是旧版残留而非新缺陷 |
| B-08 | `dist/` 不入库 → 仓库内没有产物历史 | 已知边界 | 版本识别只能靠 §2.9 的字节数 / sha256；台账（见 B-02）落地后可作为补充索引 |
| B-09 | 无 CI 流水线（仓库无 `.github/` 目录），发布全靠人工按 §2.7 执行 | 已知边界 | 若要自动化，需先解决 `dist/` 不入库与「发布前人工抽检」两步的机器化 |
| B-10 | **没有** Arabic / Hebrew / Devanagari / Thai 的 12px 点阵源（只有 Unifont 16 的 16×16 网格，塞不进 12px 格） | 已知边界 | 这四条语系不在任何当前版本的覆盖范围内 |
| B-11 | 许可边界：成品字形派生自 **SimHei / MS Gothic**（微软专有）→ `dist/` 不入库；仓库 `LICENSE` = **GNU AGPL-3.0**（覆盖 `tools/fontgen/` 代码）；`vendor/` 的 Fusion Pixel = **OFL-1.1**（三份许可随附） | 已知边界 | 任何新增分发渠道前先复核许可边界。**注意**：`PixelFont Multi 12` 的生产源全部宽松许可（Fusion Pixel OFL-1.1 + ZLabs Pixel OFL-1.1 + 本仓库手绘 OFL-1.1），**不受微软专有的限制** —— 但 `dist/` 仍按统一政策不入库，成品走 Release |
| B-14 | `Multi 12` 的 `PostScript 名` / `achVendID` / 产物命名 | **已解决**（2026-10-25） | `PixelFontMulti-12` / `PixelFontMulti` / `PXLF` 均已由 fontTools 回读校验；见 §2.2 |
| B-15 | **规格书 05–12 与事实底稿仍写着「多语言版尚未开工」** | 已知边界（**先于** `multi12-v1.0.0` 存在） | 那几份设计书是**基线冻结**文档（写明「事实截止 2026-10-24，基线 commit `4300fc1`」），其「尚未开工」是写作当时的状态。多语言版的**现行**数据以 `docs/multi12.md` + `CHANGELOG.md` + 本文 §2.2 / §2.8 为准；彻底改写那几份设计书属独立的文档债 |
| B-12 | zip 内 5 个条目（`.bdf` / `-atlas.png` / `-specimen.png` / `安装与使用说明.md` / `word-compat.md`）的 sha256 **未收录**于 zip 内 `SHA256SUMS.txt` | 待验证 + 待补 | 验证方法：`Expand-Archive` 后逐个 `Get-FileHash` 并与 `SHA256SUMS.txt` 对照；建议把 9 项全部纳入 `SHA256SUMS.txt` 后重新打包 |
| B-13 | 参考字体在上游可获取性未做持续校验 | 已知边界 | `fetch_ref_fonts.py --verify` 仅在本地有缓存时有效；上游变动需重抓后复核 sha256 清单 |
| B-14 | `Multi 12` 的 `PostScript 名` / `achVendID` / 产物命名 | 待验证 | 家族尚未构建，命名未经 fontTools 校验；开工后以实际构建产物回填 §2.2 |

---

### 附：本文数字的来源索引

| 来源 | 本文引用的内容 |
|---|---|
| `tools/fontgen/build_font.py` | `UPM` = 768、像素 = 64 单位、`_emit_rect()`、`_merge_vertical_runs()`、`verify_ttf_metadata()` |
| `tools/fontgen/bitfont.py` | `cell_ascent` / `cell_descent`、`ScriptStack`（含 `overrides` 通道）、`count_holes()` / `count_runs()` / `ink_ratio()` |
| `tools/fontgen/charset.py` | `ascii_chars()` / `extras()` / `kana_chars()` / `gb2312_level1()` / `EXCLUDE` / `SOURCE_OVERRIDES` / `build_charset()` |
| `tools/fontgen/verify_all.py` | 8 步门禁定义与最近一次结果（8/8 PASS 等计数） |
| `tools/fontgen/verify_gdi.py` | 全字符集 GDI 栅格化判定（4161/4161、抗锯齿 0） |
| `tools/fontgen/vendor_fusion_pixel.py` | Fusion 裁剪版双项验证（逐像素一致 + cmap 覆盖相符） |
| `tools/fontgen/fetch_ref_fonts.py` | 参考字体抓取与 `--verify` |
| `tools/fontgen/adversarial_review.py` | 对抗审核三轮裁决计数与状态取值 |
| `reports/gdi_compat.json` / `reports/gdi_raster_scan.tsv` | GDI 门禁报告（摘要 1.5KB / 逐码位 4,162 行） |
| `docs/word-compat.md` | 全字符集栅格化、渲染器相关性、12 整数倍精确性、内嵌位图路线 |
| `docs/reference-fonts.md` | 参考字体来源 / 版本 / sha256 清单 |
| commit `cef4a22` / `729403c` / `c403eea` / `8ae04fc` / `4300fc1` | §2.1 示例、§2.8 发布历史、§2.6 提交信息前缀实例 |
| GitHub Release `v1.0.0` | 5 个附件、zip 9 项、回下载校验结论 |
