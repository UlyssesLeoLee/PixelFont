# 三轮对抗式字形审核

- 生成时间: 2026-10-24T11:41:01.639663+00:00
- 覆盖: **4140** 个码位 (有墨字形 4139 个)
- 参考集: zpix, unifont-16
- 裁决: 待裁决 **0** / 已裁决非缺陷 **160** / 确认缺陷 **0** / 干净 **3979**

## 三轮的分工 (为什么换攻击面, 而不是同一把尺子量三遍)

| 轮 | 攻击面 | 量具 | 攻击的是谁 |
|---|---|---|---|
| 1 | 身份反查 | 多腔镜像 / 像素级反向近邻 / 拓扑签名 / 我方近重复 | 「身份错误 0 例」 |
| 2 | 部件级结构 | 腔面积集合 / 部件格归属 / 桥接间隙 | 「结构劣化已修完」 |
| 3 | 链条 | 源字体重渲 / 产物独立读 / 结论对撞 | 「我方这一列 = 字体的字形」 |

## 第 1 轮 —— 身份反查

> 上一轮结论: 身份错误 0 例 (4140/4140 目视)。本轮从**四个方向**反查换字。

| 判据 | 命中 |
|---|---|
| `COUNTER_GAINED` | 28 |
| `REVERSE_NN` | 8 |
| `OWN_EXACT_DUP` | 7 |
| `OWN_NEAR_DUP` | 5 |
| `REF_AMBIGUITY_DIVERGENCE` | 2 |

阈值标定 (取自对照集的经验分布, 不拍脑袋):

- `COUNTER_GAINED`: 我方多腔数 (按类别标定): 阈值 3.000 (对照集中位 0.000, 样本 3967) | 分类别: ascii:1.1, hanzi:3.0, kana:0.5
- `REVERSE_NN`: 反向近邻领先量: 阈值 72.100 px (对照集中位 7.000 px, 样本 3956)

## 第 2 轮 —— 部件级结构攻击

> 上一轮结论: 结构劣化已修完 (确认劣化 0)。本轮放弃全字腔数, 改在部件尺度上找。

| 判据 | 命中 |
|---|---|
| `BRIDGED_GAP` | 39 |
| `HOLE_DEFICIT` | 31 |
| `MAX_CAVITY_GAP` | 30 |
| `CAVITY_AREA_L1` | 30 |
| `COMPONENT_DEFICIT` | 7 |

阈值标定 (取自对照集的经验分布, 不拍脑袋):

- `HOLE_DEFICIT`: 腔数缺口: 阈值 3.000 (对照集中位 0.000, 样本 3956) | 分类别: ascii:0.0, hanzi:3.0, kana:0.0
- `CAVITY_AREA_L1`: 腔面积 L1: 阈值 21.450 (对照集中位 2.000, 样本 3956) | 分类别: ascii:8.2, hanzi:22.0, kana:0.0
- `MAX_CAVITY_GAP`: 最大腔面积差: 阈值 12.000 (对照集中位 0.000, 样本 3956) | 分类别: ascii:6.1, hanzi:12.0, kana:0.0
- `BRIDGED_GAP`: 桥接处数: 阈值 3.000 (对照集中位 0.000, 样本 3956) | 分类别: ascii:1.0, hanzi:3.0, kana:1.0
- `COMPONENT_DEFICIT`: 单部件腔数缺口: 阈值 1.000 (对照集中位 0.000, 样本 2689) | 分类别: ascii:1.0, hanzi:1.0, kana:0.0

## 第 3 轮 —— 链条攻击

> 前两轮都默认「我方这一列 = 字体的字形」。本轮证伪这个前提本身。

| 判据 | 命中 |
|---|---|
| `UNSURE_CONFIRMED` | 18 |
| `REGRESS_DEGRADED` | 1 |

## 量具自检

- 两份实现 (洪水填充 / 并查集) 在我方 4139 个字形上: 不一致 **0**
- 在参考 81137 个字形上: 不一致 **0**
- 阳性对照 (注入: 填掉最大的腔): 200/200 被检出
- 阴性对照 (自己对自己比): 误报 0

## 结论回灌: 目视已裁决的字 (不再算新发现)

共 140 个: U+002E . (punct_homoglyph); U+0030 0 (reference_ambiguity); U+0036 6 (punct_homoglyph); U+0038 8 (punct_homoglyph); U+0040 @ (looser_than_ref); U+004F O (reference_ambiguity); U+005F _ (punct_homoglyph); U+0060 ` (punct_homoglyph); U+00B7 · (punct_homoglyph); U+3094 ゔ (looser_than_ref); U+3095 ゕ (looser_than_ref); U+309F ゟ (looser_than_ref); U+30FB ・ (punct_homoglyph); U+4E92 互 (style_density); U+4FCA 俊 (style_density); U+4FEF 俯 (style_density); U+5192 冒 (style_density); U+5195 冕 (style_density); U+51F0 凰 (style_density); U+51F3 凳 (style_density); U+52AB 劫 (style_density); U+52C9 勉 (style_density); U+533F 匿 (style_density); U+53E3 口 (style_density); U+53EC 召 (style_density); U+5409 吉 (style_density); U+5446 呆 (style_density); U+5496 咖 (style_density); U+56DB 四 (style_density); U+56E4 囤 (style_density); U+56ED 园 (style_density); U+56FE 图 (style_density); U+5703 圃 (style_density); U+5723 圣 (style_density); U+58A9 墩 (looser_than_ref); U+591A 多 (style_density); U+5993 妓 (style_density); U+5AE9 嫩 (looser_than_ref); U+5B9D 宝 (style_density); U+5C4E 屎 (style_density)

## 机械印证: 历史结论在本轮仍然成立

共 32 条: U+3099 换字修复成立 (第一轮不再命中); U+53E0 劣化修复成立 (第二轮不再命中); U+554A 劣化修复成立 (第二轮不再命中); U+55D3 劣化修复成立 (第二轮不再命中); U+560E 劣化修复成立 (第二轮不再命中); U+56B7 劣化修复成立 (第二轮不再命中); U+5BA3 劣化修复成立 (第二轮不再命中); U+60E7 劣化修复成立 (第二轮不再命中); U+613F 劣化修复成立 (第二轮不再命中); U+61C8 劣化修复成立 (第二轮不再命中); U+63D6 劣化修复成立 (第二轮不再命中); U+64AC 劣化修复成立 (第二轮不再命中); U+690D 劣化修复成立 (第二轮不再命中); U+6A47 劣化修复成立 (第二轮不再命中); U+6BD7 劣化修复成立 (第二轮不再命中); U+6E23 劣化修复成立 (第二轮不再命中); U+718F 劣化修复成立 (第二轮不再命中); U+76F2 劣化修复成立 (第二轮不再命中); U+7701 劣化修复成立 (第二轮不再命中); U+770B 劣化修复成立 (第二轮不再命中); U+77A9 劣化修复成立 (第二轮不再命中); U+80B2 劣化修复成立 (第二轮不再命中); U+8205 劣化修复成立 (第二轮不再命中); U+852B 劣化修复成立 (第二轮不再命中); U+85C9 劣化修复成立 (第二轮不再命中); U+86E4 劣化修复成立 (第二轮不再命中); U+86F0 劣化修复成立 (第二轮不再命中); U+8845 劣化修复成立 (第二轮不再命中); U+8A8A 劣化修复成立 (第二轮不再命中); U+9171 劣化修复成立 (第二轮不再命中); U+9547 劣化修复成立 (第二轮不再命中); U+9CD6 劣化修复成立 (第二轮不再命中)

