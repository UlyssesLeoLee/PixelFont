# 变更日志

本文件记录 PixelFont 的发布历史。格式参考 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。

- 仓库：<https://github.com/UlyssesLeoLee/PixelFont>
- 发布页：<https://github.com/UlyssesLeoLee/PixelFont/releases>

> **本仓库有两个字体家族，版本序列各自独立**（见
> [`docs/spec/11-version-and-change-management.md`](docs/spec/11-version-and-change-management.md) §2.2）：
>
> | 家族 | 版本序列 | tag 形式 |
> |---|---|---|
> | `PixelFont PC98 12` | `[1.0.0]` | `v1.0.0` |
> | `PixelFont Multi 12` | `[multi12-v1.0.0]` | `multi12-v1.0.0` |
>
> 两个家族都可以同时安装、同时使用，字体名与文件名不冲突。

> **本文件的每个数字都能追溯**：要么指向 commit，要么指向仓库路径，
> 要么指向一条可重跑的命令。核不实的写「待验证」并附验证方法 —— **禁止编数字**。

---

## [未发布]

### 新增

- **设计规格文档集（12 份）** —— `docs/spec/`，编号 `01` ~ `12`，加一份索引 `README.md`
  与一份统一事实底稿 `_facts-baseline.md`（共约 4,700 行）。
  覆盖需求 / 字符集 / 视觉 / 字形结构 / 家族 / 度量 / 字距排版 / 制作 / 质量 / 测试 /
  版本变更 / 授权交付。每份统一六段结构：结论先行 → 范围与目的 → 正文 → 验收判据 →
  复现命令 → 已知边界与待办。commit `7fab2c7` ~ `44f04fc`，索引 `e2c9a13`。
- **Multi 12 字符集定义模块** —— `tools/fontgen/charset_multi12.py`，
  把文档 02 的逐层账目落成可执行代码，**31,392** 码位（方案 C）五道硬门禁全过：
  逐层累加 = 31,392 / 方案 A 交叉 = 19,816 / A∪CJK 整块交叉 = 31,392 /
  非第三源与排除项不变 / L5 构成 = 1,689 汉字 + 6 符号。commit `7dabdae`。
  **已随 `multi12-v1.0.0` 发布，见下节。**
- **规格文档集审核工具** —— `tools/specreview/`，五个脚本让审核可复现而不是一次性结论：
  `audit_identity.py`（R1 身份反查）/ `audit_structure.py`（R2 部件级结构）/
  `audit_chain.py`（R3 链条复跑）/ `verify_facts.py`（事实核验 + 跨文档一致性）/
  `sync_index.py`（索引同步）。commit `8be0cc6`。
- **已安装字体复核工具** —— `tools/fontgen/verify_install.py`，
  针对**系统里装的那份**（不做私有注册）做四层取证：
  文件指纹 / GDI 枚举 / 按名字请求时 GDI 选中的族名 / 全字符集 4,161 字在 12ppem 与
  24ppem 下与设计位图逐格比对。commit `c1e9092`。
- **`docs/install.md` 补 3.5 节** —— 一条命令复核安装结果。

### 修复

- **规格文档集对抗式审核的 23 条缺陷** —— 详见
  [`docs/spec/_adversarial-review.md`](docs/spec/_adversarial-review.md) 的缺陷台账。
  最要紧的几条：
  - doc 06 的 lsb 判据多乘了一次 64（照抄会得到 821 个假失败）；
  - doc 04 的窄字形判据 `lsb < 1` 恒不触发（1 像素 = 64 单位，等于假通过）；
  - doc 08 声称 TTF 字形名为 `uXXXX`，实测 `post` 表 3.0 **不落盘字形名**；
  - doc 07 的期望字形名写成 `uni2026`，实测是 `ellipsis`（有 AGL 名就用 AGL 名）；
  - doc 02 的复现命令是 `python -c "..."` 占位符，不是可执行命令。
  commit `23c82d4`。
- **索引不再钉死会变的值** —— `docs/spec/README.md` 的「篇幅」列 / 底稿日期改由
  `sync_index.py` 从实际文件同步；仓库 HEAD 改为用 `git log -1 --format=%h` 查询的表述。
  commit `e4cdbcc`。
- **事实底稿的一处数字错误** —— vendor 生产源实际 **764,748** 字节
  （sha256 `FC910F23FF8EE2DF8F2FEC6F91381A60DF812E3A16CE177F48528F1DB6551A37`），
  旧底稿写的 746,800 是错的。随底稿入仓一并修正（commit `23c82d4`）。

### 文档

- **统一事实底稿入仓** —— `docs/spec/_facts-baseline.md`。
  12 份文档共用的唯一数字来源；文档里写的「底稿 §N」必须能在仓库内解析到。
- **审核报告** —— `docs/spec/_adversarial-review.md`，
  含 23 条缺陷台账与**审核工具自己翻了 10 次车**的记录（T1–T10）。

### 计划中（尚未实现，不构成任何发布内容）

- `PixelFont Multi 12` 的**跨平台渲染验证**（macOS / Linux fontconfig、CoreText）
  —— 见 [`docs/multi12.md`](docs/multi12.md) §9.2 的待验证表。
- `PixelFont Multi 12` 的**字形修改记录台账** —— 规格 §2.4 要求能机器化回答
  「某码位何时、为何、由哪个 commit 改成现在这样」，目前只有 git 历史。

---

## [multi12-v1.0.0] - 2026-10-25

**`PixelFont Multi 12` 家族的首个版本** —— 12px 等宽点阵，**31,392** 码位，
一个文件覆盖简体中文 / 日文 / 韩文 / 拉丁 / 希腊 / 西里尔。

- tag `multi12-v1.0.0` 指向 commit `a3509b3`（2026-10-24）；
  GitHub Release：<https://github.com/UlyssesLeoLee/PixelFont/releases/tag/multi12-v1.0.0>
- 资产 6 个：`PixelFontMulti-12-2026-10-24.zip`、`PixelFontMulti-12.ttf`、
  `PixelFontMulti-12-atlas.png`、`PixelFontMulti-12-specimen.png`、
  `PixelFontMulti-12-SHA256SUMS.txt`、`OFL.txt`
- **许可：全部 SIL OFL 1.1 —— 成品可自由分发、可商用**（这与 `PixelFont PC98 12`
  的 AGPL-3.0 + 微软专有字形派生不同，后者成品不入库）
- 回下载校验：6 个资产重新下载后与发布件**逐字节一致**；
  回下载的 TTF 在 GDI 中被正常选中，全字符集 31,392 码位 ×
  (12 ppem + 24 ppem) 与设计位图**逐格一致**，抗锯齿像素 **0**

### 新增

- **Multi 12 字形路由名单** —— `tools/fontgen/route_multi12.py`（规则）+ `derive_route_multi12.py`
  （推导与 10 道门禁）+ `route_multi12.json`（可 diff 的展开，1,926,812 字节）。
  源分布：`fusion_ja` 17,544 / `fusion_ko` 11,172 / `fusion_zh_hans` 2,078 /
  `fusion_latin` 594 / `handdrawn` 4 = **31,392**。commit `ec064e4`。
- **生产源裁剪并入库** —— `vendor/multi12/`，4 个 Fusion 裁剪版（合计 5.79 MB）
  + 4 个原创手绘字形 + OFL 全文与 3 份上游许可。逐像素对照 31,388 个字形，
  **不一致 0 个**。裁剪口径是「只留路由分配给该源的码位」。
  工具 `tools/fontgen/vendor_multi12_sources.py`。commit `b6350ef`。
- **4 个缺口码位改原创手绘** —— `€` `≠` `≤` `≥` 任何 12px 开源字体都不覆盖。
  原计划用 Zpix 补，核实后发现 **Zpix 不是 MIT**（无 `LICENSE` 文件、license API 404、
  商用付费 USD $1000 / ￥7000，且**明文禁止修改/拆分/再分发**），
  故改为本仓库原创手绘，许可 OFL-1.1（`vendor/multi12/OFL.txt`）。
  数据 `vendor/multi12/handdrawn-glyphs.txt`，代码 `tools/fontgen/handdrawn.py`。
  commit `b6350ef`。
- **`PixelFont Multi 12` 家族构建** —— `tools/fontgen/build_font_multi12.py`。
  31,392 字形，UPM 768 / Ascender 704 / Descender −128，
  BDF / PNG 图集 / TTF **三重回读全过**。
  产物 sha256 见 [`docs/multi12.md`](docs/multi12.md) §8。commit `b6350ef`。
- **Multi 12 专篇文档** —— [`docs/multi12.md`](docs/multi12.md)：
  字符集账目、路由规则、许可义务、构建与可复现性、26 道验证门禁、已知边界。
- **Multi 12 安装与使用说明** —— [`docs/install-multi12.md`](docs/install-multi12.md)，
  随发布包以 `安装与使用说明.md` 交付。commit `564109a`。

### 修复

- **OS/2 `ulCodePageRange1` 漏掉 bit19（代码页 949 韩文）** —— Multi 12 覆盖 11,172 个
  谚文音节，不声明 bit19 的话 GDI 在 `lfCharSet=HANGEUL` 下**根本不会考虑本字体**
  （实测枚举到 0 族、选不中），韩文正文会静默回退到系统字体。
  现在是 bit0 / 17 / 18 / 19（`0x000E0001`），并加 `need_cp` 硬门禁。
  繁体 950 不开 —— 字符集里没有 zh_hant。commit `b6350ef`。
- **PostScript 名改回 `PixelFontMulti-12`** —— 规格 §2.2 定的是「家族名 + 连字符 + 字号」，
  与同项目的 `PixelFontPC98-12` 同一套风格；实现曾误用无连字符的 `PixelFontMulti12`。
  XLFD 的家族名段也改成不含连字符（`-PF-PixelFontMulti-...`），
  与 PC98 12 家族的 `-PF-PixelFontPC98-...` 一致 —— XLFD 用 `-` 分隔字段，
  家族名段里带连字符会与字段分隔符混淆。commit `8c19d9d`。
- **`verify_gdi.pick()` 里族名写死** —— 只改了 `enum_has` 那处，`pick()` 仍在请求
  `FONT_NAME`（PC98 12），导致选择检查一直测的是另一个字体，门禁等于没测。
  已加 `name` 参数并修正，`verify_gdi_multi12.py` 据此新增。commit `ba6fd92`。
- **JIS X 0208 二级汉字被误判成「假名/符号/全角」** —— Shift-JIS 首字节 `0xE0–0xEF`
  实际是**二级汉字行**（1,980 个码位全是汉字），L5 那一层名义上写「假名/符号/全角」，
  实际内容却有 1,689 个汉字。已拆成 `jis_x0208_level2_kanji()` /
  `jis_x0208_kana_punct()`，L5 改名并加**盯构成**的第 5 道门禁。总量 31,392 不变。
  commit `ec064e4`。
- **构建不该依赖不入库的 `third_party/`** —— 原先 `require_sources()` 查的是
  `third_party/ref_fonts/` 的原始下载，而构建实际读的是入库的裁剪版，
  导致**干净克隆上直接退出**。现在分工明确：推导需要 `third_party`，
  **构建只读入库的路由快照 + 入库的裁剪版**。
  实测：93 个入库文件复制到空目录后构建，六个产物 sha256 与主仓库**逐字节一致**。
  commit `b6350ef`。
- **`route_multi12.json` 的 `sources[*].path` 语义含混** —— 原先只写 third_party 路径，
  容易被误读为构建输入。现在分列 `build_path` / `origin_path`。
- **`derive_route_multi12.py` 门禁 9 会静默失效** —— 查「Fusion 不覆盖 4 个缺口」
  必须在缺原始下载时**显式标未复核**，不能变成一个看起来在通过的假门禁。

---

## [1.0.0] - 2026-10-25

**首个实测可在 Microsoft Word 中正常使用的版本。**

- tag `v1.0.0` 指向 commit `4300fc1`（2026-10-24）；
  GitHub Release 发布于 2026-10-25T00:41:10Z。
- 发布页：<https://github.com/UlyssesLeoLee/PixelFont/releases/tag/v1.0.0>
- 资产：`PixelFontPC98-12-2026-10-24.zip`、`PixelFontPC98-12.ttf`、
  `PixelFontPC98-12-sizescale.png`、`PixelFontPC98-12-merge-before-after.png`、
  `SHA256SUMS.txt`。

### 修复（本版的核心）

- **OS/2 元数据错误 —— 「Word 里装了却用不上」的根因**（commit `cef4a22`）。
  旧值 `ulCodePageRange1 = 0x00030000` 实际是 874+932，既没有 1252 也没有 936；
  `fsSelection` 缺 `REGULAR`；`ulUnicodeRange` 是手写的。修完之后 Word 才会在中文正文里
  选中它。**从旧版升级必须覆盖安装** —— 家族名与旧版完全相同，不覆盖系统仍命中旧的那份。
- **补齐 21 个 Word 常用字符**，字符集 4,140 → **4,161**；顺带修掉
  `U+005C` 被画成 `¥` 的真缺陷（MS Gothic 按 JIS 惯例把反斜杠画成 Yen 符号，
  导致它与 `U+00A5` 整格逐字节相同）。commit `729403c`。
- **合并竖向相邻游程为单个矩形轮廓** —— 修非整数倍字号的笔画断裂（commit `8ae04fc`）。
  原因：字形是矢量 TTF，「每像素一个独立矩形」在栅格化时各自独立吸附到像素网格，
  缩放倍数不是整数时笔画会断成虚线。合并后轮廓数 −31%、体积 −28.6%，
  笔画断裂显著缓解（畸变本身无法消除）。

### 新增

- **GDI 门禁从 6 个样字扩到全字符集逐格验证** —— 4,161 字 × 12ppem/24ppem，
  墨迹外框与墨迹集合逐格比对，抗锯齿像素 **0**。commit `c403eea`。
- **三轮对抗式字形审核** —— 每个码位过三轮互相独立的攻击面
  （身份反查 / 部件级结构 / 链条），机器筛出 169 例高危，人工逐格裁决后
  **0 例确认缺陷**；链条级核验 4,158/4,158 逐字节一致。commit `19e915c`。
  方法论见 [`docs/adversarial-review.md`](docs/adversarial-review.md)。

### 验证结论

| 项 | 结果 |
|---|---|
| 字符集 | **4,161** 码位（ASCII 95 + 标点 56 + 假名 255 + 汉字 3,755，汉字为 GB2312 一级机械推导） |
| GDI 逐格一致 | 12ppem 与 24ppem 下 **4,161 / 4,161**，抗锯齿 **0** |
| 质量门禁 | `python tools/fontgen/verify_all.py` **8 步全 PASS** |
| 构建可复现 | 钉死字体头时间戳后，连续两次构建产物逐字节一致 |
| 回归 | 4,161 字分 43 批，**0 error 0 warn** |

### 产物

| 文件 | 大小 | sha256 |
|---|---|---|
| `PixelFontPC98-12.ttf` | 973,712 字节 | `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1` |
| `PixelFontPC98-12-2026-10-24.zip` | 533,116 字节 | `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8` |
| `PixelFontPC98-12-sizescale.png` | 32,725 字节 | `C3B117DCFE1EA20AEBB8C2B3BE709A2A604B62FD62F7C24458E3E91FA2B373BC` |
| `PixelFontPC98-12-merge-before-after.png` | 16,440 字节 | `80CF703189E7A00CD73C472E4AA210B474CEEC376E5E75DFFFE28C9E04707A61` |

> `dist/` **不入库**（见 `.gitignore`）。校验和清单见 `dist/SHA256SUMS.txt`。

### 许可

| 对象 | 许可 |
|---|---|
| 仓库代码 | **AGPL-3.0**（`LICENSE`） |
| 入库生产源 `vendor/fusion-pixel-12px/` | **OFL-1.1**（含 `ark-pixel-OFL.txt` / `cubic-11-OFL.txt` / `galmuri-LICENSE.txt` 三份） |
| 成品字形派生源 | SimHei / MS Gothic（微软专有）—— 这是 `dist/` 不入库的原因 |

---

## 构建版本对照（仅本机安装过，**未**作为发布版发布）

| 版本 | 大小 | sha256 | 状态 |
|---|---|---|---|
| 10-23 初版 | 1,362,480 字节 | `FCC65BCBCD8A1A022007065E3444464916EDB537BB172B6F2ACDC9596DE3303B` | OS/2 元数据错误，Word 选不中 |
| 10-24 早版 | 1,364,528 字节 | `269619D5EAA0B84BC478B550893C6F5CCAAB6B0709F86AB19433AD5A8A46B2D3` | 元数据已修，轮廓未合并 |
| 10-24 当前版 | 973,712 字节 | `3298AE4D…14F69FB1` | **即 v1.0.0** |

---

## 里程碑

| 日期 | 里程碑 | 代表 commit |
|---|---|---|
| 2026-10-08 | 仓库建立 | `0c7f5b5` |
| 2026-10-21 | 像素字体生成管线基线（BDF / TTF / 图集 + 回读校验） | `4decdb0` |
| 2026-10-21 | 用独立开源像素字体逐字校验字形身份，修掉 56 个渲染成白块的汉字 | `37db72e` |
| 2026-10-21 | 引入第三个像素源 Ark Pixel，整字白块从 119 降到 20 | `2ece730` |
| 2026-10-21 | 字符身份规则 —— 我方把某码位画成另一个码位时自动换源 | `27064af` |
| 2026-10-21 | 全部 4,140 字目视复核完成 | `eb901fe` |
| 2026-10-21 | 一条命令复核全部结论（`verify_all.py`） | `132e831` |
| 2026-10-22 | 终检：全新 clone 独立构建 | `d73a07a` |
| 2026-10-23 | 三轮对抗式字形审核 | `19e915c` |
| 2026-10-24 | 修 OS/2 元数据 —— Word 兼容性的根因 | `cef4a22` |
| 2026-10-24 | 字符集 4,140 → 4,161 | `729403c` |
| 2026-10-24 | GDI 门禁扩到全字符集 | `c403eea` |
| 2026-10-24 | 合并竖向相邻游程，修非整数倍字号断裂 | `8ae04fc` |
| 2026-10-24 | 设计规格文档集 12 份 | `7fab2c7` ~ `44f04fc` |
| 2026-10-24 | Multi 12 字符集模块（31,392 码位） | `7dabdae` |
| 2026-10-24 | 规格文档集对抗式审核，23 条缺陷修复 + 审核工具入仓 | `23c82d4`、`8be0cc6` |
| 2026-10-25 | **v1.0.0 发布** | `4300fc1` |

---

## 复现

```bash
# 全链路 8 步验收
python tools/fontgen/verify_all.py

# Windows 兼容门禁 (全字符集, 约 9 秒)
python tools/fontgen/verify_gdi.py

# 已安装字体复核 (四层取证)
python tools/fontgen/verify_install.py

# 规格文档集审核 (四件套)
python tools/specreview/audit_identity.py
python tools/specreview/audit_structure.py
python tools/specreview/audit_chain.py
python tools/specreview/verify_facts.py
```

参考字体需要先抓取（只用于校验，不参与构建，不入库 `third_party/`）：

```bash
python tools/fontgen/fetch_ref_fonts.py
```
