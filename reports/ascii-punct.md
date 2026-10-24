# 回归测试报告 — ascii+punct

> **快照说明**：本报告是 **4140 字符集那一版**（2026-10-20 那一轮）的记录，
> 文中出现的「全集 4140 字」指**当时**的字符集，不是当前值。
> 2026-10-24 补入 21 个 Word 常用符号后字符集为 **4161**
> （新增字形逐个 12px 点阵目视 + 自动化 8 步流水线覆盖，见
> `docs/glyph-identity-verification.md` §5.3）。

- 生成时间: 2026-10-20T23:21:46.421658+00:00
- 判定: **FAIL** (error 9 / warn 3 / info 0)
- 覆盖: 130 字 / 2 批 (字符集 130 字选自全集 4140 字)

## 异常汇总

| 异常 ID | 级别 | 次数 | 说明 |
|---|---|---|---|
| `ATLAS_WIDE_MISMATCH` | error | 5 | 图集 isWide 标记与 advance 不符 |
| `BDF_STRUCTURE` | error | 1 | BDF 结构损坏 |
| `CLIP_RIGHT` | error | 3 | 源字形宽度超出 cell, 墨迹被裁 |
| `SOURCE_ADVANCE_MISMATCH` | warn | 3 | 源字体实测 advance 与分配格宽不符 |

## ATLAS_WIDE_MISMATCH (5)

- `U+00B7` '·' (punct) · 批 0 — '·' 图集 isWide=1 但 advance=6 (全角=12/半角=6)
- `U+2014` '—' (punct) · 批 0 — '—' 图集 isWide=1 但 advance=6 (全角=12/半角=6)
- `U+2026` '…' (punct) · 批 0 — '…' 图集 isWide=1 但 advance=6 (全角=12/半角=6)
- `U+00D7` '×' (punct) · 批 1 — '×' 图集 isWide=1 但 advance=6 (全角=12/半角=6)
- `U+00F7` '÷' (punct) · 批 1 — '÷' 图集 isWide=1 但 advance=6 (全角=12/半角=6)

## BDF_STRUCTURE (1)

-  — STARTCHAR 4140 个但 ENDCHAR 4141 个 —— 字符块结构不配对

## CLIP_RIGHT (3)

- `U+2026` '…' (punct) · 批 0 — '…' 源字形 12x12 起点(0,1) 超出 6x13 的格 —— 右侧/底部墨迹被裁掉
- `U+00D7` '×' (punct) · 批 1 — '×' 源字形 12x12 起点(0,1) 超出 6x13 的格 —— 右侧/底部墨迹被裁掉
- `U+00F7` '÷' (punct) · 批 1 — '÷' 源字形 12x12 起点(0,1) 超出 6x13 的格 —— 右侧/底部墨迹被裁掉

## SOURCE_ADVANCE_MISMATCH (3)

- `U+2026` '…' (punct) · 批 0 — '…' 源字体实测 advance=12, 但分配到的格宽=6 (EAW=A)
- `U+00D7` '×' (punct) · 批 1 — '×' 源字体实测 advance=12, 但分配到的格宽=6 (EAW=A)
- `U+00F7` '÷' (punct) · 批 1 — '÷' 源字体实测 advance=12, 但分配到的格宽=6 (EAW=A)

## 批统计

| 批 | 字数 | 墨量中位 | 墨量最高 | 墨迹top | 墨迹bottom | 全角比 | 空墨迹 |
|---|---|---|---|---|---|---|---|
| 0 | 100 | 18% | 36% | 2 | 10 | 2% | 0 |
| 1 | 30 | 10% | 26% | 2 | 10 | 93% | 0 |

