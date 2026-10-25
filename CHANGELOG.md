# 变更日志

本文件记录 PixelFont 的发布历史。格式参考 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。

- 仓库：<https://github.com/UlyssesLeoLee/PixelFont>
- 发布页：<https://github.com/UlyssesLeoLee/PixelFont/releases>

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
  把文档 02 的逐层账目落成可执行代码，**31,392** 码位（方案 C）四道硬门禁全过：
  逐层累加 = 31,392 / 方案 A 交叉 = 19,816 / A∪CJK 整块交叉 = 31,392 /
  非第三源与排除项不变。commit `7dabdae`。
  **注意：只出了字符集模块，Multi 12 字体本身尚未构建。**
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

- `PixelFont Multi 12` —— 独立家族，**31,392** 码位。
  已完成字符集定义模块，**尚未**推导字形路由名单、**尚未**构建字体。

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
