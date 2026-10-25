# 规格文档集 · 统一事实底稿 v2

> 本文件是 12 份规格文档**共用**的唯一事实底稿（v2，2026-10-24 核实）。
> 文档中出现的「底稿 §N」「事实底稿 §N」均指本文件的第 N 节。
> 本文件随仓库入库，**不含任何机器本地路径**，任何 clone 都能解析这些引用。

---

## 0. 仓库与流程

| 项 | 值 |
|---|---|
| 仓库 | `E:\PixelFont`（GitHub https://github.com/UlyssesLeoLee/PixelFont ，**PUBLIC**） |
| 分支 | `dev` = 集成分支；`main` = 发布镜像。两者**零分叉**，`--ff-only` 快进 |
| 当前 HEAD | `4300fc1` |
| 文档语言 | 中文正文，英文技术术语保留原名（hinting / UPM / gasp / cmap / kerning / GSUB / locl / em …） |
| 提交信息风格 | `docs(spec): <主题>` |
| 仓库政策 | `dist/` **不入库**；`vendor/` **入库**；`third_party/` **不入库** |

---

## 1. 家族与命名

| 项 | 值 |
|---|---|
| 家族名（name ID 1 / 16） | `PixelFont PC98 12` |
| PostScript 名 | `PixelFontPC98-12` |
| achVendID | `PXLF` |
| 多语言版（计划中） | **独立家族** `PixelFont Multi 12`，不改现有家族 |

---

## 2. 网格与度量

- 设计网格 **12 × 13 像素**（宽 × 高），12px 等宽，PC-98 风格。
- UPM = **768**，1 像素 = **64** 单位（768 / 12 = 64）。
- em 方框按**字宽 12** 取，**不是** cell 高 13。早先按 13 除会让 12ppem 下每像素落在 0.923 个设备像素上，整副字糊掉。
- 基线：**ascent 11 / descent 2**（基线在第 11 行下方，cell 第 12 行），cell 高 **13**。
- advance：半角 **6**，全角 **12**。
- 源码：`tools/fontgen/build_font.py`（`UPM` 常量、`px = UPM // cell_w`、`_emit_rect()`、`_merge_vertical_runs()`）、`tools/fontgen/bitfont.py`（`BitmapFont` 的 `cell_ascent` / `cell_descent`、`ScriptStack`、`count_holes()`、`count_runs()`、`ink_ratio()`、`to_ascii()`）。

---

## 3. 字符集（当前家族，4,161 码位）

| 类别 | 数量 | 来源 |
|---|---|---|
| ASCII | 95 | `U+0020`–`U+007E` |
| 标点/符号 | 56 | `charset.extras()` |
| 假名 | 255 | `charset.kana_chars()` |
| 汉字 | 3,755 | **GB2312 一级**（区位 16–55 区，`0xB0A1`–`0xD7F9`）**机械推导** |

- 源列表合计 **4,164**（`ascii_chars()` 95 + `extras()` 56 + `kana_chars()` **258** + `gb2312_level1()` 3,755），去重后 **4,161**。
- 重复的 3 个字符：`ヶ` U+30F6、`ー` U+30FC、`～` U+FF5E（假名表与符号表各出现一次）。
- 汉字集用**机械推导**，不是凭记忆列字表 —— 凭记忆列字表就是编造。
- 假名覆盖：平假名 `U+3041`–`U+309F`、片假名 `U+30A0`–`U+30FF`、半角片假名 `U+FF61`–`U+FF9F`，外加 `々 〆 〇 ヶ ー ～`。
- **明确排除**（`charset.EXCLUDE`）：`U+3097 ゗`、`U+3098 ゘` —— 古旧假名合字，非 JIS 字集，MS Gothic 无此字形。
- 2026-10-24 补入 21 个 Word 常用字符：弯引号 `“ ” ‘ ’`、全角空格 `U+3000`、NBSP `U+00A0`、`– • ‧`、`¥ ° ½`、`€ →`、`≠ ≤ ≥`、`［ ］ ｛ ｝`。
- 源码：`tools/fontgen/charset.py`（`gb2312_level1()` / `ascii_chars()` / `kana_chars()` / `extras()` / `EXCLUDE` / `SOURCE_OVERRIDES` / `build_charset()` / `load_ideo_route()` / `build_stack()` / `gate_ideo_route()` / `gate_full_coverage()`）。

---

## 4. 生产源（参与构建，裁剪后入库 `vendor/`）

| 源 | 路径 | 角色 |
|---|---|---|
| SimHei | `C:\Windows\Fonts\simhei.ttf` | 汉字源 |
| MS Gothic | `C:\Windows\Fonts\msgothic.ttc` | 拉丁 / 假名源 |
| Fusion Pixel 12px 简体（OFL-1.1） | `vendor/fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans-subset.ttf`（**764,748 字节**，sha256 `FC910F23FF8EE2DF8F2FEC6F91381A60DF812E3A16CE177F48528F1DB6551A37`） | 第三源 |

- `vendor/fusion-pixel-12px/LICENSES/` 下**三份**许可：`ark-pixel-OFL.txt` / `cubic-11-OFL.txt` / `galmuri-LICENSE.txt`。
- 源例外 `charset.SOURCE_OVERRIDES`：`U+005C` 反斜杠切到 fusion —— MS Gothic 按 **JIS 惯例**把 `U+005C` 画成 `¥`，导致它与 `U+00A5` 整格逐字节相同。
- `bitfont.ScriptStack` 的 `overrides` 参数是这类"源字体语系惯例"问题的**专用通道**；`ideo_route.json` 只管汉字（**3,010** 条路由记录）。
- 裁剪脚本 `tools/fontgen/vendor_fusion_pixel.py`（`--check` 只验证已入库裁剪版），做两项验证：裁剪前后逐像素一致 + 裁剪版 cmap == 原字体 cmap ∩ 本项目字符集。

---

## 5. 参考字体（只用于校验，不参与构建，不入库 `third_party/`）

| 字体 | 版式 | 许可证 | 角色 |
|---|---|---|---|
| Ark Pixel 12px | 12px 等宽 | OFL-1.1 | 12px 基准（与生产源同源，现只作交叉验证） |
| Fusion Pixel 12px（ja/ko/latin/zh_hans/zh_hant/zh_hk/zh_tw 七变体） | 12px 等宽 | OFL-1.1 | 第三源上游 / 交叉验证 |
| Zpix（最像素）v3.3.0 | 12px | MIT | **与生产源独立**的 12px 票 |
| GNU Unifont 16.0.01 | 16×16 | GPL-2.0+（含字体嵌入例外） | 非 CJK 谱系基准，16px 不参与 12px 笔画数比对 |

- 来源、版本、sha256 清单见 `docs/reference-fonts.md`；抓取脚本 `tools/fontgen/fetch_ref_fonts.py`（`--verify` 只校验不重下）。
- 12px 层面只有 **2 票**（Ark / Zpix），Unifont 因 16px 不参与笔画数比对；引入 Ark 作生产源后 Ark 票也变自证，目视复核的参考列已改为 **Zpix + Unifont**。

---

## 6. OS/2 与渲染元数据（2026-10-24 修复，commit `cef4a22`）

**这是"Word 里装了却用不上"的根因**：旧值 `ulCodePageRange1 = 0x00030000` 实际是 bit16（874 泰语）+ bit17（932），**既没有 1252 也没有 936**；`fsSelection` 为 0x0000 缺 REGULAR；手写 `ulUnicodeRange` 查表会再次出错。

| 字段 | 修复后的值 | 为什么 |
|---|---|---|
| `ulCodePageRange1` | `(1<<0) \| (1<<17) \| (1<<18)` = 1252 + 932 + 936 | 覆盖 Latin-1 / Shift-JIS / GB2312 三套代码页 |
| `fsSelection` | `0x0040`（REGULAR） | 缺 REGULAR 时 Windows 可能不把它当正文常规字 |
| `ulUnicodeRange1`–`4` | **不手写**，由 fontTools 按 cmap 实际覆盖重算 | 手写查表会再次出错 |
| `gasp` | `{0xFFFF: 0}` | 像素字不该请求灰度抗锯齿或网格拟合 |

四组不变量由 `build_font.py::verify_ttf_metadata()` 硬拦（代码页位 / fsSelection / Unicode 区段位与 cmap 一致 / gasp 禁 DOGRAY|GRIDFIT）。

---

## 7. 轮廓生成规则

- 每个像素 → 一个矩形轮廓（TrueType 坐标系，y 向上）。所有矩形同向绕向（non-zero 环绕规则填充）。
- **v1.0.0 起**：竖向相邻、x 范围相同的水平游程**合并成一个矩形**（像素并集不变）。
  - 效果：轮廓数 107,209 → **73,933**（-31%）；TTF 1,364,528 → **973,712 字节**（-28.6%）；整数倍精确性不变（**12,483 / 12,483**）。
  - 动机：非整数缩放下每个矩形**独立**吸附到输出网格，1.5px 的方块有的落进 1 格、有的整个落空 → 笔画断成虚线。
- 源码：`tools/fontgen/build_font.py::_merge_vertical_runs()` 与 `_emit_rect()`。

---

## 8. 关键渲染结论（已实测）

- **只有 12 的整数倍字号能逐格还原设计**：12ppem (=9pt)、24ppem (=18pt)、36ppem (=27pt) @96dpi。
- 非整数倍（如 18ppem = 1.5 倍）：笔画断裂 + 墨迹量偏细 **43%**。
- 栅格化走 **FreeType MONO 目标**（`FT_LOAD_TARGET_MONO`，等同 GDI 1-bit 文字），输出 0/255 单色 L 图。Pillow 默认灰度抗锯齿再二值化会得到"缩小的矢量字体"而不是点阵。
- **GDI**（Windows / Word 的渲染路径）：12ppem 与 24ppem 下**全字符集 4161/4161 逐格一致**，抗锯齿像素 **0**（本机字体平滑开启时也是 0）。
- **FreeType**（Pillow / Chrome / Linux）：12px 平均偏差 **19.00 px/字**（最坏 44），24px+ 偏差 0。
- GDI **会**采用 `EBDT`/`EBLC` 内嵌位图，但**只在请求字号与 strike 的 ppem 精确相等时**（实测：Calibri 的 `A` 在 12/15/16/17/19ppem 命中对应 strike，14/18/20–24ppem 回落到 `glyf` 轮廓），**不会拿最近的 strike 缩放**。
- 详见 `docs/word-compat.md`（§7.2 全字符集栅格化、§7.5 渲染器相关性、§7.6 只有 12 整数倍精确、§7.7 内嵌位图路线）。

---

## 9. 质量门禁（`tools/fontgen/verify_all.py`，8 步）

| 步 | 名称 | 判据 |
|---|---|---|
| 1 | 生产源自检 | Fusion 裁剪版与原字体逐像素一致 + cmap 覆盖相符 |
| 2 | 构建 | 缺字门禁 + 路由名单门禁 + BDF/图集/TTF 回读校验 + OS/2 元数据不变量 |
| 3 | 全量回归 | 4,161 字分 43 批，产物与源位图逐像素一致 |
| 4 | 字形硬检查 | 参考集 Zpix + Unifont（与生产源独立） |
| 5 | 产物与源同步 | 独立读 `dist/` 与当前源逐字比对（不靠构建脚本自证） |
| 6 | 路由名单自检 | 按名单自述的输入重新推导，与入库名单比对 |
| 7 | 对抗式审核 | 三轮独立攻击面（身份反查 / 部件级结构 / 链条），阈值按对照集标定 |
| 8 | Windows 兼容性 | GDI 字体选择 + 12/24ppem 全字符集栅格化逐像素一致 |

最近一次结果 **8/8 PASS**；回归 0 error 0 warn；硬检查命中 71（warn 69 / error 2，参考集分歧）；对抗审核三轮 60/139/19 命中，待裁决 0，已裁决非缺陷 169，确认缺陷 0。

---

## 10. 产物与复现命令

| 产物 | 字节 | sha256 |
|---|---|---|
| `dist/PixelFontPC98-12.ttf` | **973,712** | `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1` |
| `dist/PixelFontPC98-12.bdf` | 665,950 | — |
| `dist/PixelFontPC98-12-atlas.png` | 141,857 | — |
| `dist/PixelFontPC98-12-specimen.png` | 2,977 | — |
| `dist/PixelFontPC98-12-atlas.json` | 87,300 | — |
| `dist/PixelFontPC98-12.bdf.map` | 183,034 | — |
| `dist/PixelFontPC98-12-2026-10-24.zip` | **533,116** | `96EE924E853FCE5A29EDA0990ED4B68EFEF46B74F7782B764053CB2AD150FDE8` |

zip 内实际 **9 项**（实测条目清单）：

| zip 内路径 | 字节 | sha256 |
|---|---|---|
| `PixelFontPC98-12.ttf` | 973,712 | `3298AE4D9E28E7F3D5939E007DF43EA82B64860922AB246FC7A4B82414F69FB1` |
| `PixelFontPC98-12.bdf` | 665,950 | 待验证（zip 内 SHA256SUMS.txt 未收录） |
| `PixelFontPC98-12-atlas.png` | 141,857 | 待验证（同上） |
| `PixelFontPC98-12-specimen.png` | 2,977 | 待验证（同上） |
| `安装与使用说明.md` | 6,434 | 待验证（同上） |
| `word-compat.md` | 23,718 | 待验证（同上） |
| `SHA256SUMS.txt` | 744 | — |
| `说明-各字号渲染对比.png` | 32,725 | `c3b117dcfe1ea20aebb8c2b3be709a2a604b62fd62f7c24458e3e91fa2b373bc` |
| `说明-轮廓合并前后对比.png` | 16,440 | `80cf703189e7a00cd73c472e4aa210b474ceec376e5e75dfffe28c9e04707a61` |

```powershell
# 重建字体
cd E:\PixelFont; python tools/fontgen/build_font.py
# 全链路 8 步验收（约 6 分钟）
cd E:\PixelFont; python tools/fontgen/verify_all.py
# Windows 兼容门禁（全字符集，约 9 秒）
cd E:\PixelFont; python tools/fontgen/verify_gdi.py
# 抓参考字体 / 只校验
python tools/fontgen/fetch_ref_fonts.py
python tools/fontgen/fetch_ref_fonts.py --verify
# 裁剪生产源 / 只验证
python tools/fontgen/vendor_fusion_pixel.py
python tools/fontgen/vendor_fusion_pixel.py --check
```

- 报告：`reports/gdi_compat.json`（摘要 1.5KB）+ `reports/gdi_raster_scan.tsv`（逐码位 4,162 行）。

---

## 11. 版本与发布

- **v1.0.0 已发布**：注解 tag 在 `main`，GitHub Release 正式版（`draft=false`），**5 个附件**（zip / ttf / 2 张说明图 / SHA256SUMS）。
- **回下载校验已做**：资产从 GitHub 重新下载后逐字节一致，且下载回的 TTF 在 GDI 里正常被选中与渲染。
- 推送必须走 gh 凭据通道：
  `git -c credential.helper= -c "credential.https://github.com.helper=!gh auth git-credential" push origin dev`

---

## 12. 已知边界（写文档时必须如实写，不许夸大）

- **没有** Arabic / Hebrew / Devanagari / Thai 的 12px 点阵源 —— 只有 Unifont 16（16×16 网格），塞不进 12px 格。
- **单字重** Regular，无 Bold / Italic / 无可变字体轴。
- **无 kerning、无连字、无 OpenType 特性**（除 `gasp`）。
- 本机已安装的是**当前版**（973,712 字节，sha256 `3298AE4D…F69FB1`），与发布产物逐字节一致；四层复核（文件指纹 / 枚举 / 选择 / 全字符集渲染）全过，见 `tools/fontgen/verify_install.py`。
- 成品字形派生自 **SimHei / MS Gothic**（微软专有）→ `dist/` **不入库**；仓库 `LICENSE` = **GNU AGPL-3.0**（覆盖 `tools/fontgen/` 代码）；`vendor/` 的 Fusion = **OFL-1.1**（三份许可随附）。

---

## 13. 多语言版 `PixelFont Multi 12`（计划中，**尚未开工**）

**已拍板的三项方向决策**：① 范围 = 方案 C（A + 全部 CJK）= **31,392 码位**；② 形态 = **新增独立家族** `PixelFont Multi 12`，现有 `PixelFont PC98 12` 不动；③ 中日共享 2,078 汉字 = **中文形为主（zh_hans 源）** + JIS 独有 2,297 字走 **ja 源**（GSUB `locl` 变体因架构改动过大**未选**）。

### 13.1 逐层账目（每层都能加总复核）

| 层 | 内容 | 增量 | 累计 |
|---|---|---|---|
| L0 | 当前家族 | 4,161 | 4,161 |
| L1 | +Latin Ext A/B（U+0100–U+024F ∩ Fusion latin） | 241 | 4,402 |
| L2 | +Greek（U+0370–U+03FF ∩ Fusion latin） | 99 | 4,501 |
| L3 | +Cyrillic（U+0400–U+04FF ∩ Fusion latin） | 151 | 4,652 |
| L4 | +Hangul syllables（U+AC00–U+D7AF ∩ Fusion ko） | 11,172 | 15,824 |
| L5 | +JIS X 0208 **二级汉字**（首字节 0xE0–0xEF）+ 符号/假名（0x81–0x87）∩ Fusion ja | 1,695（汉字 1,689 / 符号 6） | 17,519 |
| L6 | +JIS X 0208 **一级**汉字 4,375（Shift-JIS 首字节 0x88–0x9F ∩ Fusion ja） | 2,297 | 19,816 |
| L7 | +CJK 其余（U+4E00–U+9FFF ∩ Fusion ja） | 11,576 | **31,392** |

交叉核对：方案 A（L0–L6）= **19,816**；CJK 整块 U+4E00–U+9FFF ∩ Fusion ja = **19,317**；A ∪ CJK = **31,392** ✔（与逐层累加一致）。

### 13.2 中日汉字重叠（机械推导，非凭记忆）

| 项 | 数量 |
|---|---|
| GB2312 一级汉字 | 3,755 |
| JIS X 0208 汉字（Shift-JIS 双字节判定） | 4,375 |
| **两者交集（中日共享）** | **2,078** |
| JIS 独有 | 2,297 |
| GB 独有 | 1,677 |

- Fusion ja / zh_hans **都 100% 覆盖**这 2,078 + 2,297 + 1,677（2078/2078、2297/2297、1677/1677），且 ja 与 zh 在共享集上的**码位集合完全相同**。
- JIS 独有 2,297 字在 Fusion ja 源中渲染 **2,297 / 2,297 全部有墨迹**（不缺字）。

### 13.3 中日字形差异（实测，逐像素，12×13 单色 cell）

在 2,078 个中日共享汉字上，Fusion ja 与 Fusion zh_hans：

| 判据 | 数量 |
|---|---|
| **像素完全相同** | **1,644 / 2,078**（79.1%） |
| **像素不同** | **434 / 2,078**（20.9%） |

差异最大的字（异或格数）：`肩` U+80A9 (78)、`扇` U+6247 (71)、`房` U+623F (69)、`雇` U+96C7 (69)、`遍` U+904D (59)、`扁` U+6241 (54)、`煽` U+717D (53)、`灰` U+7070 (44)、`曾` U+66FE (41)、`罪` U+7F6A (40)、`偏` U+504F (38)、`奠` U+5960 (38)、`判` U+5224 (37)、`歉` U+6B49 (35)、`遥` U+9065 (30)、`滞` U+6EDE (29)、**`直` U+76F4 (28)**（中日字形分歧的经典例）、`氏` U+6C0F (26)、`才` U+624D (25)。

异或格数分布：1 格 102 字、2 格 94 字、3 格 40 字、4 格 42 字、5 格 27 字、6 格 18 字，≥7 格共 93 字，最大 78 格。

> 结论：中日字形分歧**真实存在**（约 21% 的共享字不同）。这正是"中文形为主 + JIS 独有走 ja 源"策略的依据 —— 共享字默认取中文形，用户若需日式字形须另行提供变体机制（`locl` 未选）。

### 13.4 方案 C 覆盖缺口

Fusion 七个变体的 cmap 并集 = **37,415** 码位。方案 C 的 31,392 中有 **4 个码位不被任何 Fusion 变体覆盖**：`U+20AC €`、`U+2260 ≠`、`U+2264 ≤`、`U+2265 ≥` —— 这 4 个在当前家族里已有（走 MS Gothic / SimHei），多语言版需沿用同样的非第三源路径。

### 13.5 体积粗估

当前 4,161 字 = 973,712 字节 → 平均 **234.0 字节/字**。方案 C 31,392 字 → 约 **7.0 MB**（按同一均值粗估；实际会因 CJK 字形复杂度不同而偏离）。

### 13.6 方案 B（Unifont 16 语系）—— **未选**

Unifont 16 独有、方案 C 不含的部分：谚文字母 256、假名扩展 16、希伯来 112、阿拉伯 256、天城文 128、泰文 128，合计 **896**。这些是 16×16 网格，塞不进 12px 格，故方案 C **不覆盖** Hebrew / Arabic / Devanagari / Thai。

---

## 14. 文档写作硬要求

1. **结论先行**：开头就给结论，不要先铺背景。
2. **每个数字可追溯**：给出来源（仓库文件路径 / 命令 / commit / 报告文件）。
3. 核不实的写「待验证」并给出验证方法。**禁止编数字。**
4. **详尽版**：每份 4–8 页（约 200–450 行 Markdown），用**表格**承载规格（不是散文堆砌）。
5. **章节结构**（可按文档性质微调，但保留这五段）：
   - 结论先行
   - 1. 范围与目的
   - 2. 正文（表格化规格）
   - 3. 验收判据
   - 4. 复现命令
   - 5. 已知边界与待办
6. 只写你被分配的文件，**不要动其它车道或主仓的任何文件**。
