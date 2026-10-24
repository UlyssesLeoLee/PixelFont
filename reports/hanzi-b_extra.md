# 成品结构级校验 (补充探针) — hanzi_b

> **快照说明**：本报告是 **4140 字符集那一版**（2026-10-20 那一轮）的记录，
> 文中出现的「全集 4140 字」指**当时**的字符集，不是当前值。
> 2026-10-24 补入 21 个 Word 常用符号后字符集为 **4161**
> （新增字形逐个 12px 点阵目视 + 自动化 8 步流水线覆盖，见
> `docs/glyph-identity-verification.md` §5.3）。

- 生成时间: 2026-10-20T23:22:51.430993+00:00
- 分支: `agent/reg-hanzi-b`
- 判定: **FAIL** (error 2 / warn 0 / info 0)
- 覆盖: 本 lane 1855 字 (hanzi 1900:3755, 全字符集 4140 字)

本探针只查**成品文件的骨架**: 图集网格对齐 / TTF 表结构 / BDF 头尾与字符块结构 / 汉字位图唯一性。字形内容的一致性由共享工具 `tools/fontgen/regress.py` 负责 (见 reports/hanzi-b.md)。

## 1. 量具可靠性 (消费了多少输入, 多少处读取失败)

| 检查项 | 样本数 | 失败数 | 读取失败 | 判定 | 覆盖说明 |
|---|---|---|---|---|---|
| `A3` 图集 PNG 尺寸与元数据 columns/rows/size 一致 | 7 | 0 | 0 | PASS | 7 项标量比对 (PNG 实际尺寸 + 元数据自洽 + 与栅格化器度量) |
| `A1` 图集单元格原点 == (列*12, 行*13) 且与元数据一致 | 4140 | 0 | 0 | PASS | 遍历元数据 glyphs 全量 4140 条, 按数组下标反推列/行 |
| `A2` 图集墨迹不渗邻格 (结构: 墨迹列 < advance) + 批内逐像素相等 | 4140 | 0 | 0 | PASS | 结构层消费 4140 格; 像素层消费 1855 字 (本 lane 批次), 共 289380 次像素比对 |
| `A4` 图集墨迹像素 RGB 恒为 (255,255,255) | 645840 | 0 | 0 | PASS | 扫描全部 4140 格 × 156 px |
| `B1` .notdef 空心方框 (2 环 / 相反绕向 / 非零填充栅格化 / 尺寸) | 1 | 0 | 0 | PASS | 对 .notdef 做 6 项判定: 环数、x 范围、y 范围、绕向、栅格化比对、中心为空 |
| `B2` hhea.ascent/descent 与 OS/2 usWinAscent/usWinDescent 一致 | 6 | 0 | 0 | PASS | 6 项标量比对 (hhea 2 + usWin 2 + sTypo 2), 期望值 = ascent*64 / descent*64 |
| `B3` gasp 表存在且 12ppem 的 range == 0 (单色) | 1 | 0 | 0 | PASS | 查表存在性 + gaspRange[12] 标量比对 |
| `B4` maxp.maxPoints/maxContours/numGlyphs 与实际 glyf 一致 | 4141 | 0 | 0 | PASS | 逐个字形取轮廓点数/轮廓数 (共 4141 个字形, 含 .notdef), 与 maxp 三个字段比对 |
| `C1` BDF 头字段 (FONTBOUNDINGBOX / FONT_ASCENT / FONT_DESCENT / CHARS) 与实际字符数一致 | 5 | 0 | 0 | PASS | 读 1 个头 + 4140 个字符块; 期望值取自栅格化器度量 (ascent=11 descent=2 cell=12x13) |
| `C2` BDF 每块恰好一个 ENDCHAR / BBX 高度 == BITMAP 行数 / 行位宽 == ceil(w/8)*2 / 填充位为 0 | 4140 | 1 | 0 | FAIL | 消费 4140 个字符块 + 43805 个 BITMAP 数据行 (每行 3 项判定: 长度/十六进制/填充位) |
| `C3` 零墨迹字形清单 + 逐块 ENDCHAR 计数 | 4140 | 1 | 0 | FAIL | 扫描全部 4140 个字符块的 BBX 宽; 命中 1 个零墨迹字形 |
| `C4` 建议修法回灌: 修正后的 BDF 仍被解析器接受, 且像素不变 | 1 | 0 | 0 | PASS | 在内存里删掉多余 ENDCHAR, 交给两个独立解析器 (本探针 + regress.decode_bdf) 与生产门禁 build_font.verify_bdf 复核 |
| `D1` 批内汉字位图唯一性 (1855 字两两比对) | 1855 | 0 | 0 | PASS | 消费 1855 个汉字的位图签名 (12x13 元组), 相同签名归组 |
| `D2` 对照项: 全字符集跨类别同位图 (合法) + 全 3755 汉字内部同位图 | 4140 | 0 | 0 | PASS | 消费 4140 个全字符集位图签名; 跨类别同位图 1 组, 全汉字内部同位图 0 组 (均不计入失败) |

> 说明: `bdflib` 与 X11 `bdftopcf` 在本机均未安装, 因此 "标准解析器能否接受" 由**两个互相独立的解析器** (本探针的严格解析器 + regress.py 的 decode_bdf) 加生产门禁 build_font.verify_bdf 三方共同判定。

### 量具自检 (注入已知坏数据, 断言检测器会响)

注入 13 个已知坏数据用例, 13 个检测器如期报警, 0 个失灵。

| 注入的坏数据 | 期望报警 | 实际报警 | 结果 |
|---|---|---|---|
| 图集元数据 x 挪 1px | `ATLAS_ORIGIN_MISMATCH` | `ATLAS_ORIGIN_MISMATCH` | PASS |
| 半角格空白区点墨 | `ATLAS_INK_LEAK` | `ATLAS_INK_LEAK` | PASS |
| 格子内翻 1 像素 | `ATLAS_PIXEL_MISMATCH` | `ATLAS_PIXEL_MISMATCH` | PASS |
| 墨色改成红 | `ATLAS_INK_COLOR` | `ATLAS_INK_COLOR` | PASS |
| .notdef 改成单环实心 | `TTF_NOTDEF_NOT_BOX` | `TTF_NOTDEF_NOT_BOX` | PASS |
| hhea.ascent 改 7 | `TTF_METRICS_MISMATCH` | `TTF_METRICS_MISMATCH` | PASS |
| 删掉 gasp 表 | `TTF_NO_GASP` | `TTF_NO_GASP` | PASS |
| gasp 12ppem 改 2 | `TTF_GASP_NOT_MONO` | `TTF_GASP_NOT_MONO` | PASS |
| maxp.maxPoints 改 9999 | `TTF_MAXP_POINTS_MISMATCH` | `TTF_MAXP_POINTS_MISMATCH` | PASS |
| BDF CHARS 写错 | `BDF_HEADER_MISMATCH` | `BDF_ENDCHAR_PAIRING`, `BDF_HEADER_MISMATCH`, `BDF_ZERO_INK_DOUBLE_ENDCHAR` | PASS |
| BDF 塞多余 ENDCHAR | `BDF_ENDCHAR_PAIRING` | `BDF_ENDCHAR_PAIRING`, `BDF_ZERO_INK_DOUBLE_ENDCHAR` | PASS |
| BDF 行填充位置 1 | `BDF_ROW_PADDING` | `BDF_ENDCHAR_PAIRING`, `BDF_ROW_PADDING`, `BDF_ZERO_INK_DOUBLE_ENDCHAR` | PASS |
| 两个不同汉字同位图 | `HANZI_DUPLICATE_BITMAP` | `HANZI_DUPLICATE_BITMAP` | PASS |

## 2. 异常清单

| 异常 ID | 级别 | 对象 | 证据 | 建议改法 |
|---|---|---|---|---|
| `BDF_ENDCHAR_PAIRING` | error | U+0020   | {"examples": [{"cp": "U+0020", "endchar_count": 2, "line": 12}], "total": 1} | tools/fontgen/build_font.py:133 —— 零墨迹分支的 lines += ["BITMAP", "ENDCHAR", "ENDCHAR"] 少写一个 ENDCHAR |
| `BDF_ZERO_INK_DOUBLE_ENDCHAR` | error | U+0020   | {"zero_ink_glyphs": [{"cp": "U+0020", "endchar_count": 2, "bitmap_present": true, "bitmap_rows": 0, "line": 12}], "broken": [{"cp": "U+0020", "endchar_count": 2, "bitmap_present": true, "bitmap_rows": 0, "line": 12}], "r… | tools/fontgen/build_font.py:133 改为 lines += ["BITMAP", "ENDCHAR"] (保留 BITMAP 关键字: 去掉它会让 regress.decode_bdf 收不到该码位, 空格会被误报 BDF_MISSING) |

### BDF_ENDCHAR_PAIRING — U+0020  

- 说明: 1 个字符块的 ENDCHAR 数量不是 1 (首个: U+0020 写了 2 个 ENDCHAR)
- 建议改法: tools/fontgen/build_font.py:133 —— 零墨迹分支的 lines += ["BITMAP", "ENDCHAR", "ENDCHAR"] 少写一个 ENDCHAR

### BDF_ZERO_INK_DOUBLE_ENDCHAR — U+0020  

- 说明: 1 个零墨迹字形的字符块里写了多个 ENDCHAR (U+0020 写了 2 个); 全字符集共 1 个零墨迹字形, 中招的只有这 1 个
- 建议改法: tools/fontgen/build_font.py:133 改为 lines += ["BITMAP", "ENDCHAR"] (保留 BITMAP 关键字: 去掉它会让 regress.decode_bdf 收不到该码位, 空格会被误报 BDF_MISSING)

## 3. A 图集网格对齐

- 元数据: columns=32, rows=130, cell=[12, 13], PNG 实际尺寸=[384, 1690], 字形数=4140
- A1 单元格原点: 0 处不符 (遍历全部 4140 条元数据)
- A2 墨迹不渗邻格: 结构层 4140 格 + 像素层 1855 字, 0 处失败

## 4. B TTF 结构

- .notdef: 轮廓数 2, x 0..768 (期望 0..768), y -128..704 (期望 -128..704)
- 两环有向面积: [638976.0, -450560.0] (异号 = 非零填充下为空心)

非零环绕规则栅格化结果 (本探针自算, 与期望空心方框逐像素比对):

```
############
#..........#
#..........#
#..........#
#..........#
#..........#
#..........#
#..........#
#..........#
#..........#
#..........#
#..........#
############
```

- maxp: maxPoints 176 (实际 176), maxContours 44 (实际 44), numGlyphs 4141 (字形表 4141)

## 5. C BDF 头尾与字符块结构

- 字符块数: 4140
- 零墨迹字形: 1 个

| 码位 | ENDCHAR 数 | 有 BITMAP 段 | BITMAP 行数 | 起始行 |
|---|---|---|---|---|
| U+0020 | 2 | 是 | 0 | 12 |

### 修法回灌 (删掉多余的 ENDCHAR) 复核

| 解析器 | 结果 | 明细 |
|---|---|---|
| `hanzi_b_probe.parse_bdf_strict` | PASS | blocks=4140, issues=0, endchar_mismatch=0 |
| `regress.decode_bdf` | PASS | parsed_glyphs=4140, issues=0 |
| `build_font.verify_bdf` | PASS | detail=生产回读门禁通过 |

- 删除的多余 ENDCHAR 数: 1

- 反面对照 (把零墨迹块的 BITMAP 段整段删掉): regress.decode_bdf 解析到 4139 个码位 (保留 BITMAP 时是 4140 个), U+0020 **收不到** —— 所以修法必须**保留 BITMAP 关键字**, 只删多余的 ENDCHAR。

## 6. D 汉字位图唯一性

- 本 lane 批内同位图组: 0
- 全 3755 汉字内部同位图组: 0 (含批外的字, 供集成者参考)
- 跨类别同位图组: 1 (合法, 两个源字体本来就画得一样, 不算缺陷)

## 7. 假设与局限

- 本探针不重建成品时, 校验对象是 dist/ 里已有的产物 —— 报告里记了每个产物的 sha256, 结论只对那一份产物成立。
- 结构级判定的参照系是栅格化器度量 (charset.build_stack): cell 12x13, 基线 11/2; 成品里的头字段若与之不符, 以栅格化器为准 (成品是派生物)。
- A 路墨迹比较以 alpha 通道为判据 (元数据声明 "白色 + alpha"), RGB 另作 A4 单列检查。
- 环境内无第三方 BDF 解析器 (bdflib / X11 bdftopcf 均未安装), 因此 C4 的"修法回灌"由本探针严格解析器 + regress.decode_bdf + 生产门禁 build_font.verify_bdf 三方判定。
- D 组位图唯一性只在汉字之间比对; 跨类别同位图 (如片假名「ニ」与汉字「二」) 按任务约定视为合法。

