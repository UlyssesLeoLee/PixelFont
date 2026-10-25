# 12. 字体授权与交付说明书

> 适用版本：v1.0.0（已发布）
> 适用字体：`PixelFont PC98 12`（单字重 Regular）
> 事实底稿日期：2026-10-24
> 相关文档：`docs/reference-fonts.md`（参考字体清单）、`docs/install.md`（面向普通用户的完整安装说明）、交付包内 `word-compat.md`（Word 兼容性）

---

## 结论先行

**授权分四档，互不影响、不可混谈。** ① 构建与校验代码走 **GNU AGPL-3.0**（`LICENSE`，覆盖 `tools/fontgen/`）；② 入库的生产源（Fusion Pixel Font 12px 简体裁剪版，`vendor/fusion-pixel-12px/`）走 **OFL-1.1**，且因 Fusion 是缝合字体，须随附**三份**许可（Ark Pixel OFL-1.1 / Cubic 11 OFL-1.1 / Galmuri LICENSE）；③ 本机系统字体 **SimHei**（汉字源）与 **MS Gothic**（拉丁/假名源）是**微软专有字体**，只在构建时从本机系统字体目录读取，**本仓库不分发它们**；④ 四套**参考字体**只做校验、不参与构建、不入库（`third_party/` 已在 `.gitignore`）。

**成品不能无条件自由分发。** 成品 TTF/BDF 的字形派生自 SimHei 与 MS Gothic 这两个专有字体，因此 `dist/` 被 `.gitignore` 排除——仓库发布的是**源码 + 可复现的构建**，而不是成品二进制。若将来要随包分发成品，**必须先解决 SimHei / MS Gothic 的再分发授权**；这是法律判断，不在技术范围内。

**用户要做什么（三步）。** ① 从 GitHub Release v1.0.0 下载 zip；② 完全退出所有 Word 窗口（含后台进程）后，把 `PixelFontPC98-12.ttf` **覆盖**安装到 `%LOCALAPPDATA%\Microsoft\Windows\Fonts\`；③ 重启 Word，在字体对话框的**中文字体**和**西文字体**两栏**都**选 `PixelFont PC98 12`，字号**只用 12 的整数倍**（9 / 18 / 27 / 36 pt）。

**安装失败的最常见根因是"装了却像没装"**：旧版 OS/2 元数据错误导致 Windows 根本不选中该字体，所以必须**覆盖同名文件**，而不是与旧版并存。

---

## 1. 范围与目的

### 1.1 目的

本文是 PixelFont 项目 12 份设计规格文档中的第 12 份，负责把三件事一次说清：

| 事项 | 本文回答的问题 |
|---|---|
| 授权 | 仓库里每一类文件各受什么许可证约束？哪些能分发，哪些不能？ |
| 交付 | 用户实际拿到手的是哪些文件？各自多大、指纹是什么？ |
| 使用 | 用户装完怎么用才算"装对了"？字号、Word 交互、硬边效果有哪些硬约束？ |

### 1.2 范围

- **在范围内**：`PixelFont PC98 12` v1.0.0 的许可证分层、交付物清单、安装与使用流程、验收判据、已知边界。
- **不在范围内**：成品二进制的再分发授权判定（法律问题）；多语言版 `PixelFont Multi 12`（计划中，尚未开工）；字形设计本身的美术决策。

### 1.3 读者

| 读者 | 关心什么 |
|---|---|
| 仓库维护者 | 哪些文件能进仓、哪些必须外置，验收时怎么查 |
| 终端用户 | 怎么装、怎么设字号、Word 里为什么选不中 |
| 合规审阅者 | 四档授权的义务与边界是否被正确表述 |

### 1.4 术语

- **OFL-1.1** = SIL Open Font License 1.1。
- **AGPL-3.0** = GNU Affero General Public License v3.0。
- **sha256** = 文件内容指纹，用于核对"我拿到的和我预期的是同一个文件"。
- **name ID 1 / 16** = OpenType `name` 表中的家族名 / 完整名（subfamily）。
- **achVendID** = OpenType `OS/2` 表中的 4 字节厂商标识。
- **dist/** = 构建产物目录，已被 `.gitignore` 排除。
- **vendor/** = 入库的生产源（参与构建）。
- **third_party/** = 参考字体目录，只校验、不参与构建，已被 `.gitignore` 排除。

---

## 2. 正文

### 2.1 授权分层

四档授权彼此独立：**代码的许可证不覆盖字体文件的许可证，参考字体的许可证也不因"被读过"而污染产物**。判定与义务如下表。

| 档位 | 对象（仓库内路径 / 来源） | 许可证 | 是否入库 | 是否参与构建 | 关键义务与边界 |
|---|---|---|---|---|---|
| **① 代码** | `tools/fontgen/` 下的构建与校验代码；仓库根 `LICENSE` | **GNU AGPL-3.0** | 是 | —（工具本身，不产出字形） | 分发修改版必须以 AGPL-3.0 提供对应源码；不得以闭源方式发布修改版 |
| **② 生产源（入库）** | Fusion Pixel Font 12px 简体裁剪版：`vendor/fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans-subset.ttf`（764,748 字节，sha256 `fc910f23ff8ee2df8f2fec6f91381a60df812e3a16ce177f48528f1db6551a37`） | **OFL-1.1**；因 Fusion 为缝合字体，`vendor/fusion-pixel-12px/LICENSES/` 下须随附**三份**许可：**Ark Pixel OFL-1.1** / **Cubic 11 OFL-1.1** / **Galmuri LICENSE** | 是 | 是 | ① 保留版权与许可声明；② 随附 OFL 全文；③ **不得单独售卖字体本身**；④ **不得使用保留字体名**（Reserved Font Name） |
| **③ 生产源（系统字体，不入库）** | **SimHei**（汉字源）+ **MS Gothic**（拉丁/假名源），来自本机系统字体目录 | **微软专有字体（proprietary）** | **否** | 是（仅构建时读取） | 本仓库**不分发**这两个字体；成品字形派生自它们 —— 详见 2.1.1 |
| **④ 参考字体（只校验）** | Ark Pixel 12px（OFL-1.1）/ Fusion Pixel 12px（OFL-1.1）/ Zpix v3.3.0（MIT）/ GNU Unifont 16.0.01（GPL-2.0+，含字体嵌入例外） | 各如左 | **否**（`third_party/` 在 `.gitignore`） | **否** | 来源、版本与 sha256 清单见仓库 `docs/reference-fonts.md`；抓取脚本 `tools/fontgen/fetch_ref_fonts.py`，`--verify` 只校验不重下 |

#### 2.1.1 关键法律边界（不得含糊）

成品 `PixelFontPC98-12.ttf` / `PixelFontPC98-12.bdf` 的字形**派生自 SimHei 与 MS Gothic**（微软专有字体）。由此产生两条硬约束：

1. **`dist/` 不入库。** `.gitignore` 排除 `dist/`，仓库发布的是**源码 + 可复现的构建流程**，而不是成品二进制。
2. **随包分发成品前必须先解决授权。** 若将来要把成品 TTF/BDF 随包分发，**必须先解决 SimHei / MS Gothic 的再分发授权**。这是**法律判断，不在技术范围内**——本项目不做、也不应被技术结论替代。

推论：当前 Release 的 zip 是"**源码 + 构建工具 + 许可文本**"的可分发形态，成品二进制的再分发属于**待决事项**（见第 5 节）。

### 2.2 交付物清单

#### 2.2.1 字体规格

| 项 | 值 | 来源 |
|---|---|---|
| 家族名（name ID 1 / 16） | `PixelFont PC98 12` | 成品 `name` 表 |
| PostScript 名 | `PixelFontPC98-12` | 成品 `name` 表 |
| achVendID | `PXLF` | 成品 `OS/2` 表 |
| 设计网格 | 12×13 像素，12px 等宽，PC-98 风格 | 设计规格 |
| 字重 | 单字重 Regular（**无** Bold / Italic / 可变字体轴） | 设计规格 |
| 覆盖码位 | **4,161** = ASCII 95 + 标点符号 56 + 假名 255 + 汉字 3,755 | 成品 cmap |
| 汉字来源 | GB2312 一级（区位 16–55 区）机械推导，得 3,755 字 | 构建流程 |
| OpenType 特性 | 仅 `gasp`（无 kerning、无连字、无其它特性） | 成品表 |

#### 2.2.2 文件清单（zip 内，9 项）

zip 内实际 **9 项**（2026-10-24 实测 `dist/PixelFontPC98-12-2026-10-24.zip` 的条目清单）：

| # | zip 内路径 | 字节 | sha256 | 用途 |
|---|---|---|---|---|
| 1 | `PixelFontPC98-12.ttf` | **973,712** | `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1` | 成品字体，Windows 安装用 |
| 2 | `PixelFontPC98-12.bdf` | 665,950 | 待验证（zip 内 `SHA256SUMS.txt` 未收录该文件） | 点阵源（BitFont 格式），可再加工 |
| 3 | `PixelFontPC98-12-atlas.png` | 141,857 | 待验证（同上） | 全字符集图集，肉眼核对字形 |
| 4 | `PixelFontPC98-12-specimen.png` | 2,977 | 待验证（同上） | 样张 |
| 5 | `安装与使用说明.md` | 6,434 | 待验证（同上） | 面向普通用户的安装说明；仓库 `docs/install.md` 为其展开版 |
| 6 | `word-compat.md` | 23,718 | 待验证（同上） | Word 兼容性技术附录 |
| 7 | `SHA256SUMS.txt` | 744 | — | 包内校验和清单 |
| 8 | `说明-各字号渲染对比.png` | 32,725 | `c3b117dcfe1ea20aebb8c2b3be709a2a604b62fd62f7c24458e3e91fa2b373bc` | 各字号渲染对比图 |
| 9 | `说明-轮廓合并前后对比.png` | 16,440 | `80cf703189e7a00cd73c472e4aa210b474ceec376e5e75dfffe28c9e04707a61` | 轮廓合并前后对比图 |

发布包 zip 本体：`dist/PixelFontPC98-12-2026-10-24.zip`，**533,116 字节**，sha256 `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8`。

#### 2.2.3 Release 附件

v1.0.0 为 GitHub Release（**正式版，非 draft**），共 **5 个附件**：

| 附件 | 字节 | sha256 | 说明 |
|---|---|---|---|
| `PixelFontPC98-12-2026-10-24.zip` | 533,116 | `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8` | 发布包本体，内含上表 9 项 |
| `PixelFontPC98-12.ttf` | 973,712 | `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1` | 单独提供成品字体 |
| `PixelFontPC98-12-sizescale.png` | 32,725 | `c3b117dcfe1ea20aebb8c2b3be709a2a604b62fd62f7c24458e3e91fa2b373bc` | 字号比例说明图；字节数与 zip 内 `说明-各字号渲染对比.png` 一致，是否为同一份待验证 |
| `PixelFontPC98-12-merge-before-after.png` | 16,440 | `80cf703189e7a00cd73c472e4aa210b474ceec376e5e75dfffe28c9e04707a61` | 轮廓合并前后对比图；字节数与 zip 内 `说明-轮廓合并前后对比.png` 一致，是否为同一份待验证 |
| `SHA256SUMS` | 待验证 | — | 校验和清单 |

### 2.3 安装与使用

#### 2.3.1 安装步骤

| 步 | 操作 | 验证点 / 注意事项 |
|---|---|---|
| 1 | 从 GitHub Release v1.0.0 下载发布包 zip | 用 sha256 `96EE924E…FDE8` 校验（见第 4 节命令） |
| 2 | 解压 zip，取出 `PixelFontPC98-12.ttf` | 校验 sha256 `3298AE4D…F69FB1`（64 位十六进制，注意长度） |
| 3 | **完全退出所有 Word 窗口**（含后台进程） | 未退出会导致后续覆盖失败或被占用锁住 |
| 4 | 把 ttf **覆盖**写入 `%LOCALAPPDATA%\Microsoft\Windows\Fonts\` | **必须覆盖同名文件**，不能并存（见 2.3.2） |
| 5 | **重启 Word** | Windows 缓存已加载的字体资源，覆盖后不重启不会生效 |
| 6 | Word 字体对话框：**中文字体**栏选 `PixelFont PC98 12` | 见 2.3.5 |
| 7 | Word 字体对话框：**西文字体**栏同样选 `PixelFont PC98 12` | 见 2.3.5 |
| 8 | 字号只用 **12 的整数倍** | 见 2.3.4 |
| 9 | 如需硬边效果：设置 → 个性化 → 字体 → 关闭"字体平滑" | 见 2.3.6 |

#### 2.3.2 为什么必须覆盖安装

旧版的 **OS/2 元数据错误**，Windows **根本不选中**它——这就是"装了却像没装"的根因。症状是：字体文件明明在字体目录里，Word 字体下拉框却搜不到、或能搜到但 Word 拒绝使用。

结论：**直接覆盖同名文件即可**，不需要先卸载、不需要清理注册表。

#### 2.3.3 三代指纹表（供用户核对装的是哪一版）

| 版本 | 大小 | sha256 | 状态 |
|---|---|---|---|
| 旧版（10-23） | 1,362,480 字节 | `FCC65BCBCD8A1A022007065E3444464916EDB537BB172B6F2ACDC9596DE3303B` | 元数据错误，Word 选不中 |
| 中间版（10-24 早） | 1,364,528 字节 | `269619D5EAA0B84BC478B550893C6F5CCAAB6B0709F86AB19433AD5A8A46B2D3` | 元数据已修，轮廓未合并 |
| **当前版（本包）** | **973,712 字节** | **`3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1`** | 元数据已修 + 轮廓已合并 |

判断口径：**大小 973,712 字节且 sha256 为 `3298AE4D…F69FB1`** = 装的是当前版。命中另外两组指纹即说明装的不是本包版本。

#### 2.3.4 字号约束（硬约束）

字号**必须取 12 的整数倍**：

| 场景 | 可用字号 | 对应像素 |
|---|---|---|
| 标准（100% 缩放） | 9 / 18 / 27 / 36 pt | 12 / 24 / 36 / 48 px |
| 150% 显示缩放 | 12 / 18 / 24 / 30 / 36 pt | — |

**不要用 10.5 pt**：10.5 pt 是 Word 的中文默认值，换算为 14px，**非整数倍**，像素会被拉成不等宽格子。

#### 2.3.5 Word 字体对话框有两栏

Word 的字体对话框分**中文字体**栏与**西文字体**栏（两栏各自独立决定用哪套字形）。

| 做法 | 结果 |
|---|---|
| **两栏都设为 `PixelFont PC98 12`** | ✅ 英文、数字与中文同源同网格，等宽对齐 |
| 只设中文字体栏 | ❌ 英文数字走另一栏字体，基线与宽度都对不齐 |
| 只设西文字体栏 | ❌ 中文走另一栏字体，效果同上 |

#### 2.3.6 硬边效果

| 手段 | 说明 |
|---|---|
| 设置 → 个性化 → 字体 → 关闭"字体平滑" | 系统级硬边开关 |
| 实测结论 | GDI 路径下**即使系统平滑开着，抗锯齿像素也是 0**；但 **Word 可能走 ClearType 等其它路径**，所以仍建议关闭 |

### 2.4 验收判据（概览）

完整的"用户如何确认装对了、授权没问题"见 **第 3 节**。此处仅列出两类判据的入口：

- **安装侧**：装入文件的 sha256 = `3298AE4D…F69FB1`；Word 两栏都能选中；字号为 12 的整数倍。
- **授权侧**：`dist/`、`third_party/`、专有字体均不在版本库中；Fusion 三份许可随附；成品未使用 OFL 保留字体名。

### 2.5 使用限制（如实列出）

| 编号 | 限制 | 实际影响 | 缓解方式 |
|---|---|---|---|
| L1 | 单字重 Regular，**无** Bold / Italic，**无可变字体轴** | Word 里没有粗体/斜体可用；无法做整档字重变化 | 用字号与颜色表达层级，不依赖字重 |
| L2 | **无 kerning、无连字、无 OpenType 特性**（仅 `gasp`） | 字距不可调，特定字母组合不会自动调整 | 接受默认等距网格 |
| L3 | 非整数倍字号会**笔画断裂**（18ppem 实测墨迹量**偏细 43%**） | 10.5 pt 等非整数倍下笔画断裂、视觉发虚 | 严格使用 12 的整数倍（2.3.4） |
| L4 | 本机已安装的仍是 **10-23 旧版**（`FCC65B…303B`），**尚未覆盖** | 本机此刻用不到当前版 | 是否由维护方代为覆盖安装**需用户确认**（涉及改主机状态） |
| L5 | 多语言版 `PixelFont Multi 12` **计划中、尚未开工**（31,392 码位） | 目前只有 PC-98 中文 + 拉丁/假名覆盖 | 本文件只描述已发布的 v1.0.0 |

---

## 3. 验收判据

### 3.1 安装验收（用户侧）

| 编号 | 检查项 | 方法 | 通过标准 |
|---|---|---|---|
| A1 | 文件确实被覆盖 | 对 `%LOCALAPPDATA%\Microsoft\Windows\Fonts\PixelFontPC98-12.ttf` 取 sha256 | = `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1` |
| A2 | 不是旧版 | 同上，比对大小 | 973,712 字节；**不是** 1,362,480 或 1,364,528 |
| A3 | Windows 选得中 | Word 字体下拉框搜索 | 能搜到 `PixelFont PC98 12` |
| A4 | 两栏都能选 | Word 字体对话框：中文栏 + 西文栏 | **两栏**都能选到并生效 |
| A5 | 字号合法 | 查看当前字号 | 属 9 / 18 / 27 / 36 pt（100%）或 12 / 18 / 24 / 30 / 36 pt（150%）；**不含 10.5 pt** |
| A6 | 硬边 | 设置 → 个性化 → 字体 → 关闭"字体平滑"，放大查看 | 无灰边、无抗锯齿 |
| A7 | 等宽对齐 | 在 Word 中输入 ASCII + 汉字混排 | 12px 等宽，列对齐不跳动 |
| A8 | 覆盖码位 | 抽查 ASCII、标点、假名、汉字 | 四类均在 4,161 码位内可用 |

### 3.2 授权合规验收（维护者侧）

| 编号 | 检查项 | 方法 | 通过标准 |
|---|---|---|---|
| B1 | 成品二进制不入库 | `git ls-files dist/` | 输出为空 |
| B2 | 专有字体不入库 | 在已跟踪文件中检索 SimHei / MS Gothic 字体文件 | 无命中 |
| B3 | 参考字体不入库 | `git ls-files third_party/` | 输出为空 |
| B4 | Fusion 三份许可随附 | 列出 `vendor/fusion-pixel-12px/LICENSES/` | 齐备：Ark Pixel OFL-1.1 / Cubic 11 OFL-1.1 / Galmuri LICENSE（三份） |
| B5 | Fusion 本体未被篡改 | 对 `vendor/fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans-subset.ttf` 取 sha256 | = `fc910f23ff8ee2df8f2fec6f91381a60df812e3a16ce177f48528f1db6551a37` |
| B6 | 未使用保留字体名 | 检查成品 `name` 表 | name ID 1/16 = `PixelFont PC98 12`，PostScript = `PixelFontPC98-12`，**不含** OFL 保留字体名 |
| B7 | 未单独售卖字体 | 分发形态检查 | 字体与源码、许可文本同包提供，未以"单独售卖字体文件"的形式分发 |
| B8 | 参考字体可校验 | `python tools/fontgen/fetch_ref_fonts.py --verify` | 全部一致（只校验、不重下） |
| B9 | 指纹可复现 | 按第 4 节命令重算 sha256 | 与 2.2.2 / 2.3.3 表中数值一致 |

---

## 4. 复现命令

以下命令用于核对"拿到的文件是不是预期的那个"。Windows 用 PowerShell 7，类 Unix 用 bash。

### 4.1 校验发布包 zip

```powershell
$ErrorActionPreference = 'Stop'
$zip = '.\PixelFontPC98-12-2026-10-24.zip'
Get-FileHash -Algorithm SHA256 -LiteralPath $zip
# 期望: 96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8
```

```bash
sha256sum ./PixelFontPC98-12-2026-10-24.zip
# 期望: 96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8
```

### 4.2 校验成品 TTF

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\PixelFontPC98-12.ttf'
# 期望: 3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1
```

```bash
sha256sum ./PixelFontPC98-12.ttf
# 期望: 3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1
```

### 4.3 列出 zip 内容并核对清单

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::OpenRead((Resolve-Path $zip)).Entries |
  Select-Object FullName, Length, CompressedLength
# 期望 9 项: ttf / bdf / atlas.png / specimen.png / 安装与使用说明.md / word-compat.md
#           / SHA256SUMS.txt / 说明-各字号渲染对比.png / 说明-轮廓合并前后对比.png
```

```bash
unzip -l ./PixelFontPC98-12-2026-10-24.zip
```

### 4.4 校验已安装到系统的字体（用户侧）

```powershell
$installed = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts\PixelFontPC98-12.ttf'
Get-Item -LiteralPath $installed | Select-Object Name, Length
Get-FileHash -Algorithm SHA256 -LiteralPath $installed
# 期望 Length = 973712, SHA256 = 3298AE4D...F69FB1
```

### 4.5 校验参考字体（只校验，不重下）

```powershell
# 待验证: 解释器名可能是 python3 或 python, 以本机为准
python tools/fontgen/fetch_ref_fonts.py --verify
```

```bash
# 待验证: 解释器名可能是 python3 或 python, 以本机为准
python3 tools/fontgen/fetch_ref_fonts.py --verify
```

参考字体的来源、版本与 sha256 清单另见仓库 `docs/reference-fonts.md`。

### 4.6 校验入库的生产源与许可随附

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'vendor\fusion-pixel-12px\fusion-pixel-12px-monospaced-zh_hans-subset.ttf'
# 期望: fc910f23ff8ee2df8f2fec6f91381a60df812e3a16ce177f48528f1db6551a37

Get-ChildItem 'vendor\fusion-pixel-12px\LICENSES\'
# 期望: 三份 —— Ark Pixel (OFL-1.1) / Cubic 11 (OFL-1.1) / Galmuri (LICENSE)
```

### 4.7 确认成品与参考字体均未入库

```powershell
git ls-files dist/          # 期望: 空
git ls-files third_party/   # 期望: 空
```

### 4.8 重建字体并验证可复现

```powershell
cd E:\PixelFont
python tools/fontgen/build_font.py     # 重建 TTF / BDF / 图集 / 样张
python tools/fontgen/verify_all.py      # 8 步全链路验收, 期望 8/8 PASS
```

重建后重新计算 `dist/PixelFontPC98-12.ttf` 的 sha256，应等于第 4.2 节的值 —— 一致即证明构建可复现。

```bash
cd /path/to/PixelFont
python3 tools/fontgen/build_font.py
python3 tools/fontgen/verify_all.py
```

---

## 5. 已知边界与待办

### 5.1 法律与授权边界

| 编号 | 事项 | 状态 | 归属 |
|---|---|---|---|
| K1 | 成品字形派生自 **SimHei / MS Gothic**（专有字体） | 已知边界，已在 2.1.1 写明 | 法律判断 |
| K2 | `dist/` 不入库，仓库只发"源码 + 可复现构建" | 已落地 | 技术 |
| K3 | 若要随包分发成品 TTF/BDF，须先解决 SimHei / MS Gothic 的再分发授权 | **待决**，不在技术范围 | 法律判断 |

### 5.2 事实底稿中的"待验证"项

以下数值本文**未编造**，统一标注为待验证，并附验证方法：

| 编号 | 待验证内容 | 验证方法 |
|---|---|---|
| V1 | zip 内 `PixelFontPC98-12.bdf`、`-atlas.png`、`-specimen.png`、`安装与使用说明.md`、`word-compat.md` 的 sha256 | 待在 zip 内 `SHA256SUMS.txt`（744 字节）中核对 |
| V2 | Release 附件 `SHA256SUMS` 的字节数与 sha256 | 待在 Release v1.0.0 下载该附件后核对 |
| V3 | 发布对应的 commit / tag 短 SHA | 待在 `git log` 中核对 |
| V4 | 参考字体各自的 sha256 | 待在仓库 `docs/reference-fonts.md` 核对（本文只列名称与许可证，不复制哈希） |
| V5 | Python 解释器名（`python` / `python3`） | 待在本机确认（本文命令以 `python` 为准） |

### 5.3 待办

| 编号 | 待办 | 说明 |
|---|---|---|
| T1 | 本机覆盖安装 | 本机当前仍是 10-23 旧版（`FCC65B…303B`），**尚未覆盖**；是否由维护方代为覆盖安装**需用户确认**（涉及改主机状态） |
| T2 | 成品再分发授权 | 见 K3，属法律判断，需要单独推进，不在本规格内 |
| T3 | 多语言版 | `PixelFont Multi 12`（31,392 码位）**计划中、尚未开工**；本文件只描述已发布的 v1.0.0 |
| T4 | 后续版本字号说明 | 若未来发布新版本，须同步更新 2.3.3 三代指纹表与 2.3.4 字号约束 |

---

*本文所有数值均来自 2026-10-24 已核实的事实底稿；未能核实的项一律标注「待验证」并附验证方法，不做推测性填写。*
