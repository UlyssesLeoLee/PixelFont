# 假名 (kana) 批次补充探针报告

- 生成时间: 2026-10-20T23:37:16.062204+00:00
- 判定: **FAIL** (error 2 / warn 0 / info 1)
- 覆盖: 假名 255 字 (平假名 93 / 片假名 96 / 半角片假名 63 / 其他 3), 字符集共 4140 字
- 消费输入: 汉字 3755 字 (仅用于碰撞比对), 成品 BDF/TTF/图集 各读 1 份

## 检查项汇总

| 检查 ID | 样本数 | 失败数 | 读取失败 | 状态 | 说明 |
|---|---|---|---|---|---|
| `HALFWIDTH_GRID_FIT` | 63 | 0 | 0 | PASS | 半角片假名 6px 格对齐 / 墨迹裁剪 |
| `MARK_INK` | 11 | 0 | 0 | PASS | 浊点/手浊点/迭代记号墨量与位置 |
| `HIRA_KATA_PAIR` | 88 | 0 | 0 | PASS | 平↔片一一对应墨量比值 / 同源 |
| `ADVANCE_EAW` | 255 | 0 | 0 | PASS | advance 与 East Asian Width 一致 |
| `FULLWIDTH_OVERFLOW` | 192 | 0 | 0 | PASS | 全角假名 12px 格越界 / 裁剪 |
| `ATLAS_WIDE_FLAG` | 255 | 63 | 0 | FAIL | 图集 isWide 标记 vs 实际 advance |
| `BDF_STRUCTURE` | 4140 | 1 | 0 | FAIL | BDF 字符块结构配对 |
| `SOURCE_FIDELITY` | 255 | 0 | 0 | PASS | 假名位图 == non_ideo 源 且 != ideo 源 |
| `KANA_HANZI_COLLISION` | 957525 | 0 | 0 | PASS | 假名 vs 汉字位图逐位相同碰撞 |
| `SOURCE_ROUTING` | 255 | 0 | 0 | PASS | 假名码位路由到 non_ideo 源 |
| `ARTIFACT_COVERAGE` | 255 | 0 | 0 | PASS | 假名在 BDF / TTF cmap / 图集中的覆盖 |

- 合计: 样本 963294 项, 失败 64 项, 读取失败 0 处

## 发现

### `ATLAS_WIDE_MISMATCH` — 真缺陷 (error)

**图集 isWide 标记与 advance 不符: 63 个假名**

63 个假名的图集 isWide=1 但 advance=6 (半角). 其中 advance=6 的半角假名 63 个, 全部落在 U+FF61-FF9F 连续区间。

| 字符 | 码位 | 备注 |
|---|---|---|
| ｡ | `U+FF61` | advance=6, isWide=1 |
| ｢ | `U+FF62` | advance=6, isWide=1 |
| ｣ | `U+FF63` | advance=6, isWide=1 |
| ､ | `U+FF64` | advance=6, isWide=1 |
| ･ | `U+FF65` | advance=6, isWide=1 |
| ｦ | `U+FF66` | advance=6, isWide=1 |
| ｧ | `U+FF67` | advance=6, isWide=1 |
| ｨ | `U+FF68` | advance=6, isWide=1 |
| ｩ | `U+FF69` | advance=6, isWide=1 |
| ｪ | `U+FF6A` | advance=6, isWide=1 |
| ｫ | `U+FF6B` | advance=6, isWide=1 |
| ｬ | `U+FF6C` | advance=6, isWide=1 |
| ｭ | `U+FF6D` | advance=6, isWide=1 |
| ｮ | `U+FF6E` | advance=6, isWide=1 |
| ｯ | `U+FF6F` | advance=6, isWide=1 |
| ｰ | `U+FF70` | advance=6, isWide=1 |
| ｱ | `U+FF71` | advance=6, isWide=1 |
| ｲ | `U+FF72` | advance=6, isWide=1 |
| ｳ | `U+FF73` | advance=6, isWide=1 |
| ｴ | `U+FF74` | advance=6, isWide=1 |
| ｵ | `U+FF75` | advance=6, isWide=1 |
| ｶ | `U+FF76` | advance=6, isWide=1 |
| ｷ | `U+FF77` | advance=6, isWide=1 |
| ｸ | `U+FF78` | advance=6, isWide=1 |
| ｹ | `U+FF79` | advance=6, isWide=1 |
| ｺ | `U+FF7A` | advance=6, isWide=1 |
| ｻ | `U+FF7B` | advance=6, isWide=1 |
| ｼ | `U+FF7C` | advance=6, isWide=1 |
| ｽ | `U+FF7D` | advance=6, isWide=1 |
| ｾ | `U+FF7E` | advance=6, isWide=1 |
| ｿ | `U+FF7F` | advance=6, isWide=1 |
| ﾀ | `U+FF80` | advance=6, isWide=1 |
| ﾁ | `U+FF81` | advance=6, isWide=1 |
| ﾂ | `U+FF82` | advance=6, isWide=1 |
| ﾃ | `U+FF83` | advance=6, isWide=1 |
| ﾄ | `U+FF84` | advance=6, isWide=1 |
| ﾅ | `U+FF85` | advance=6, isWide=1 |
| ﾆ | `U+FF86` | advance=6, isWide=1 |
| ﾇ | `U+FF87` | advance=6, isWide=1 |
| ﾈ | `U+FF88` | advance=6, isWide=1 |
| ﾉ | `U+FF89` | advance=6, isWide=1 |
| ﾊ | `U+FF8A` | advance=6, isWide=1 |
| ﾋ | `U+FF8B` | advance=6, isWide=1 |
| ﾌ | `U+FF8C` | advance=6, isWide=1 |
| ﾍ | `U+FF8D` | advance=6, isWide=1 |
| ﾎ | `U+FF8E` | advance=6, isWide=1 |
| ﾏ | `U+FF8F` | advance=6, isWide=1 |
| ﾐ | `U+FF90` | advance=6, isWide=1 |
| ﾑ | `U+FF91` | advance=6, isWide=1 |
| ﾒ | `U+FF92` | advance=6, isWide=1 |
| ﾓ | `U+FF93` | advance=6, isWide=1 |
| ﾔ | `U+FF94` | advance=6, isWide=1 |
| ﾕ | `U+FF95` | advance=6, isWide=1 |
| ﾖ | `U+FF96` | advance=6, isWide=1 |
| ﾗ | `U+FF97` | advance=6, isWide=1 |
| ﾘ | `U+FF98` | advance=6, isWide=1 |
| ﾙ | `U+FF99` | advance=6, isWide=1 |
| ﾚ | `U+FF9A` | advance=6, isWide=1 |
| ﾛ | `U+FF9B` | advance=6, isWide=1 |
| ﾜ | `U+FF9C` | advance=6, isWide=1 |
| ﾝ | `U+FF9D` | advance=6, isWide=1 |
| ﾞ | `U+FF9E` | advance=6, isWide=1 |
| ﾟ | `U+FF9F` | advance=6, isWide=1 |

**建议改法**: build_font.py:315 `meta.append([ord(g.ch), cx, cy, g.advance, 0 if g.category == "ascii" else 1])` —— isWide 按“字符分类”写死, 应改为按实际 advance 推导: `1 if g.advance == cell_w else 0`。

### `BDF_STRUCTURE` — 真缺陷 (error)

**BDF 字符块不配对: STARTCHAR 4140 个, ENDCHAR 4141 个 (多 1 个)**

多余的 ENDCHAR 来自零宽字形的分支: 该分支写出了两个 ENDCHAR。受影响的码位: ['U+0020'] (全字符集里唯一没有墨迹的字符)。

| 字符 | 码位 | 备注 |
|---|---|---|
|   | `U+0020` |  |

**建议改法**: build_font.py:133 `lines += ["BITMAP", "ENDCHAR", "ENDCHAR"]` → 改为 `lines += ["BITMAP", "ENDCHAR"]` (零宽字形只需一个 ENDCHAR)。

### `KANA_HANZI_BITMAP_COLLISION` — 预期行为 (info)

**假名 'ニ' (U+30CB) 与汉字 '二' (U+4E8C) 位图逐位相同 —— 属设计使然**

Unicode 名称: 假名 = KATAKANA LETTER NI; 汉字 = CJK UNIFIED IDEOGRAPH-4E8C。片假名 ニ (KATAKANA LETTER NI) 的字形就是汉字 二 的草书形, 两者同形是字形设计本身, 不是路由串源。已用独立渲染器 (GDI+/DirectWrite, 完全不经 FreeType) 复核: U+30CB 与 U+4E8C 在该渲染器下同样是两根横杠。另: 假名侧路由到 non_ideo 源 (MS Gothic/Regular), 汉字侧路由到 ideo 源 (SimHei/Regular); 两者恰好 12px MONO 栅格化到同一张位图。已用 SOURCE_FIDELITY 客观量具排除串源: 该假名的位图与 non_ideo 源逐位一致、与 ideo 源不一致。

| 字符 | 码位 | 备注 |
|---|---|---|
| ニ | `U+30CB` |  |
| 二 | `U+4E8C` |  |

```text
............
............
............
..########..
............
............
............
............
............
............
.##########.
............
............
```

```text
............
............
............
..########..
............
............
............
............
............
............
.##########.
............
............
```

- TTC 交叉验证: 3 个字体渲染: MS Gothic: ink=18 bbox=[10, 8] 墨迹2段; MS UI Gothic: ink=14 bbox=[8, 9] 墨迹2段; MS PGothic: ink=18 bbox=[10, 8] 墨迹2段 (三者像素略有差异, 形状同为 2 段独立横画)
- 同形字符对照 `U+4E8C`: ink=20, bbox=[11, 8] (注: 与该假名字形同形的汉字 (片假名由汉字草书演变而来, 同形是设计本身))

```text
MS Gothic 12px:
............
............
............
..########..
............
............
............
............
............
............
.##########.
............
............
U+4E8C:
............
............
............
.#########..
............
............
............
............
............
............
###########.
............
............
```

**建议改法**: 无需修改 —— 这是片假名/汉字同形的固有事实, 属预期行为。

## 预期行为 (已验证非缺陷)

以下记号墨量低是**组合/间隔记号本来就小**, 不是丢了字形 —— 墨迹非 0、位置正确 (组合记号在右上象限), 已逐个验证:

| 字符 | 码位 | EAW | advance | 墨迹 px | 墨量 | 墨迹包围盒 | 判定 |
|---|---|---|---|---|---|---|---|
| ゙ | `U+3099` | W | 12 | 4 | 2.56% | 3x3 | 预期行为 |
| ゚ | `U+309A` | W | 12 | 6 | 3.85% | 2x3 | 预期行为 |
| ゛ | `U+309B` | W | 12 | 4 | 2.56% | 4x3 | 预期行为 |
| ゜ | `U+309C` | W | 12 | 4 | 2.56% | 3x3 | 预期行为 |
| ・ | `U+30FB` | W | 12 | 4 | 2.56% | 2x2 | 预期行为 |
| ー | `U+30FC` | W | 12 | 9 | 5.77% | 9x2 | 预期行为 |
| ゝ | `U+309D` | W | 12 | 7 | 4.49% | 4x5 | 预期行为 |
| ゞ | `U+309E` | W | 12 | 11 | 7.05% | 6x7 | 预期行为 |
| ゟ | `U+309F` | W | 12 | 25 | 16.03% | 7x9 | 预期行为 |
| ﾞ | `U+FF9E` | H | 6 | 4 | 5.13% | 3x4 | 预期行为 |
| ﾟ | `U+FF9F` | H | 6 | 6 | 7.69% | 3x4 | 预期行为 |

平↔片墨量比值的极值对 (全部未越界, 已逐对看过 ASCII art, 差异来自平假名/片假名本身笔画数不同, 如 の 是单笔回环而 ノ 是两撇):

| 平假名 | 片假名 | 平墨量 | 片墨量 | 比值 |
|---|---|---|---|---|
| の `U+306E` | ノ `U+30CE` | 19.9% | 6.4% | 0.323 |
| は `U+306F` | ハ `U+30CF` | 23.1% | 10.3% | 0.444 |
| め `U+3081` | メ `U+30E1` | 23.7% | 10.9% | 0.460 |
| う `U+3046` | ウ `U+30A6` | 12.2% | 16.7% | 1.368 |
| ぐ `U+3050` | グ `U+30B0` | 9.6% | 16.7% | 1.733 |
| く `U+304F` | ク `U+30AF` | 7.0% | 13.5% | 1.909 |

剔除的 +0x60 配对 (Unicode 语义上不对应):

- `U+3097` ↔ `U+30F7` — 不在 kana 字符集内 (charset.py EXCLUDE)
- `U+3098` ↔ `U+30F8` — 不在 kana 字符集内 (charset.py EXCLUDE)
- `U+3099` ↔ `U+30F9` — +0x60 两侧不是对应字符: COMBINING KATAKANA-HIRAGANA VOICED SOUND MARK ↔ KATAKANA LETTER VE
- `U+309A` ↔ `U+30FA` — +0x60 两侧不是对应字符: COMBINING KATAKANA-HIRAGANA SEMI-VOICED SOUND MARK ↔ KATAKANA LETTER VO
- `U+309B` ↔ `U+30FB` — +0x60 两侧不是对应字符: KATAKANA-HIRAGANA VOICED SOUND MARK ↔ KATAKANA MIDDLE DOT
- `U+309C` ↔ `U+30FC` — +0x60 两侧不是对应字符: KATAKANA-HIRAGANA SEMI-VOICED SOUND MARK ↔ KATAKANA-HIRAGANA PROLONGED SOUND MARK
- `U+309F` ↔ `U+30FF` — +0x60 两侧不是对应字符: HIRAGANA DIGRAPH YORI ↔ KATAKANA DIGRAPH KOTO

## 量具可靠性

- 输入消费: 字符集 4140 字全量建栈; 假名 255 字逐字栅格化 (复用同一 BitmapFont 缓存); 汉字 3755 字仅用于位图碰撞比对。
- 成品读取: BDF 读取成功: PixelFontPC98-12.bdf (658776 bytes); 图集 JSON 读取成功: PixelFontPC98-12-atlas.json (4140 个字形元数据); TTF cmap 读取成功: 4140 个码位
- 读取失败合计: 0 处 (读取失败 = 成品/字形取不到, 已单独计数, 不计入 PASS)。
- 所有失败项都带 ASCII art 或数值证据, 见 findings[].evidence 与 JSON 的 checks[].rows。

## 阈值及其经验依据

- **MARK_MAX_BBOX** = `6x6 px` — 同一字体 (MS Gothic 12px) 内合法的间隔形浊点 U+309B / U+309C 实测墨迹包围盒 均为 4x3 px (ink 4 px), 半角浊点 U+FF9E / U+FF9F 为 3x4 px。取 6x6 作为宽松上界, 覆盖全部 11 个实测合法记号的包围盒 (最大 4x5)。
- **PAIR_INK_RATIO** = `[0.25, 4.0]` — 平↔片 88 对合法配对 (Unicode 名称归一后一致的才算对应) 的实测比值区间为 0.323 (U+306E の/ノ) .. 1.909 (U+304F く/ク)。该界是宽松护栏, 用于捕捉「整对路由到错误源」这种量级错误, 本批次实测 0 越界。
- **INK_LOST_TOLERANCE** = `0 px` — 粘贴后格内墨迹数必须与源字形墨迹数完全相等; 少 1 px 即为裁掉。

