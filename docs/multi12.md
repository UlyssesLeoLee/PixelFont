# PixelFont Multi 12 —— 多语系 12px 家族

> 面向：想在简体中文 / 日文 / 韩文正文里用点阵字的人。
> 口径：本文的每个数字都标了出处命令，命令可复跑；核不实的写「待验证」并给验证方法。

## 结论

`PixelFont Multi 12` 是一个 **12px 等宽点阵字体家族**，覆盖 **31,753 个码位**，
把简体中文 / 日文 / 韩文 / 拉丁 / 希腊 / 西里尔装进**同一个字体文件**。

三件对使用者最要紧的事：

1. **覆盖**：31,753 码位，其中汉字 19,678 个、谚文音节 11,172 个、拉丁 / 希腊 / 西里尔 593 个。
   其中**简体中文 GB2312 全部 6,763 个汉字**与**日文 JIS X 0208 全部 6,355 个汉字
   \+ 200 个符号假名**都是 **100%**（这两条是**构建门禁**，每次构建都核对，
   见 §7 的门禁 6/7）。
2. **许可**：全部生产源是 **SIL OFL 1.1**（Fusion Pixel 12px + ZLabs Pixel 12px
   \+ 4 个本仓库原创手绘字形），
   **成品可自由分发、可商用**。这与现有的 `PixelFont PC98 12` 不同 ——
   后者有 3,053/4,161 码位派生自 SimHei / MS Gothic（微软专有），所以成品不能入库。
3. **可复现**：只 clone 本仓库、不下载任何参考字体，也能构建出**逐字节相同**的产物
   （已实测，见 §6）。
4. **已发布**：`multi12-v1.1.0` ——
   <https://github.com/UlyssesLeoLee/PixelFont/releases/tag/multi12-v1.1.0>
   （6 个资产，含 OFL 全文；回下载后逐字节一致，且回下载的 TTF 在 GDI 中
   被正常选中、全字符集逐格一致）。上一版 `multi12-v1.0.1`。

---

## 1. 家族标识与度量

| 项目 | 值 | 出处 |
|---|---|---|
| 家族名 | `PixelFont Multi 12` | TTF `name` ID 1 |
| PostScript 名 | `PixelFontMulti-12` | TTF `name` ID 6 |
| 全名 | `PixelFont Multi 12` | TTF `name` ID 4 |
| Vendor ID | `PXLF` | TTF `OS/2` `achVendID` |
| XLFD | `-PF-PixelFontMulti-Medium-R-Normal--12-1200-72-72-c-1000-ISO10646-1` | BDF 头 |
| UPM | 768 | TTF `head` |
| Ascender / Descender / LineGap | 704 / −128 / 0 | TTF `hhea` |
| 字形数 | 31,754（31,753 码位 + `.notdef`） | TTF `maxp` |
| OS/2 版本 | 3 | TTF `OS/2` |
| `usWeightClass` | 400 | TTF `OS/2` |
| `fsType` | 0（可安装、可嵌入） | TTF `OS/2` |
| `ulCodePageRange1` | `0x000E0001`（bit 0 / 17 / 18 / 19） | TTF `OS/2` |
| `ulCodePageRange2` | `0x00000000` | TTF `OS/2` |
| 网格 | 12 × 13 px（基线在第 11 行） | 构建输出 |
| 拉丁 / 希腊 / 西里尔 advance | 6 px | §3 |
| CJK / 谚文 advance | 12 px | §3 |

> **bit19 为什么必须开**：Multi 12 有 11,172 个谚文音节，对应代码页 **949（韩文）**。
> 不在 `ulCodePageRange1` 里声明 bit19 的话，GDI 在 `lfCharSet=HANGEUL` 下
> **根本不会考虑本字体** —— 实测枚举到 0 族、选不中，韩文正文会静默回退到系统字体。
> 这条是硬门禁，`verify_ttf(need_cp=...)` 会直接失败。
>
> **bit20（950 繁体）不开**：字符集里没有 zh_hant 码位。

**命名沿用同项目惯例**：PostScript 名 `PixelFontMulti-12` = 家族名 + 连字符 + 字号，
与 `PixelFontPC98-12` 同一套风格；XLFD 的**家族名段**不含连字符
（`-PF-PixelFontMulti-...`），也与 `-PF-PixelFontPC98-...` 一致 ——
XLFD 用 `-` 分隔字段，家族名段里带连字符会与字段分隔符混淆。
`docs/spec/11-version-and-change-management.md` §2.2 定的就是这个名（原先标注「拟议」，
现已构建验证）。

取数命令：

```powershell
python -c "from fontTools.ttLib import TTFont; f=TTFont(r'E:\PixelFont\dist\PixelFontMulti-12.ttf'); print(f['OS/2'].ulCodePageRange1, f['maxp'].numGlyphs, f['head'].unitsPerEm)"
```

---

## 2. 字符集账目

字符集是**逐层累加**的：每层只引入相对前面各层的增量，所以「增量之和 = 总量」。

| 层 | 增量 | 累计 | 判据 |
|---|---|---|---|
| L0 当前家族 | 4,161 | 4,161 | `PixelFont PC98 12` 已有的 4,161 码位 |
| L1 Latin Ext A/B | 241 | 4,402 | U+0100–U+024F ∩ Fusion latin 覆盖 |
| L2 Greek | 99 | 4,501 | U+0370–U+03FF ∩ Fusion latin 覆盖 |
| L3 Cyrillic | 151 | 4,652 | U+0400–U+04FF ∩ Fusion latin 覆盖 |
| L4 Hangul syllables | 11,172 | 15,824 | U+AC00–U+D7AF ∩ Fusion ko 覆盖 |
| L5 JIS X 0208 二级汉字 + 符号/假名 | 1,695 | 17,519 | Shift-JIS 首字节 0xE0–0xEF / 0x81–0x87 ∩ CJK 层可用源覆盖 |
| L6 JIS X 0208 一级汉字 | 2,297 | 19,816 | Shift-JIS 首字节 0x88–0x9F ∩ CJK 层可用源覆盖 |
| L7 CJK 其余 | 11,937 | 31,753 | U+4E00–U+9FFF ∩ CJK 层可用源覆盖（扣掉 L5/L6） |
| **合计** | **31,753** | | |

分类构成：`cjk-ext` 11,937 / `hangul` 11,172 / `current` 4,161 / `jis-kanji` 2,297 /
`jis-l2` 1,695 / `latin-ext` 241 / `cyrillic` 151 / `greek` 99。

> **「CJK 层可用源」是并集，不是某一个源**（2026-10-25 接入 ZLabs 后改）：
> `fusion_ja` ∪ `zlabs_cn`。以前只看 `fusion_ja`，于是 GB2312 二级汉字缺 128 个 ——
> Fusion 与 Ark 的**七个变体全都缺**这 128 个生僻字（`劐 唣 垡 墚 墼 娈 媵 嫠 嬷 尜 峁 嵴 …`），
> 而 ZLabs Pixel 12px CN 覆盖 GB2312 **全部 6,763 个**。用**并集**而不是
> 「特判那 128 个」，层定义里就不会出现一个只为修一个数字而存在的特例。
>
> **L7 的增量为什么从 11,576 变成 11,937**：多出的 361 个 = GB2312 二级汉字 **128**
> \+ GB2312/JIS 之外的简体生僻字 **233**。两者都来自 ZLabs CN。
> **已发布的 31,392 个码位路由一个都没变**（§7 门禁 11 盯着这条不变式）——
> 新增的码位才落到 ZLabs。

> **L5 的层名为什么是「二级汉字 + 符号/假名」**：JIS X 0208 的 Shift-JIS 首字节
> `0xE0–0xEF` 是**二级汉字行**（第 48–84 区），落在 U+4E00–U+9FFF 里。
> 早先把它当成「假名/符号/全角」，于是 L5 名义上写的是「假名/符号/全角」，
> 实际内容却有 **1,689 个汉字**。总量照样是 31,753，前三道门禁照样全绿，
> 但**层名是错的**。所以门禁必须盯构成，不能只盯总量 ——
> 现在门禁 5 硬断言「L5 = 1,689 汉字 + 6 符号（〃 〒 〓 〔 〕 〜）」。
>
> 7 道字符集门禁（总量 / 方案 A 交叉 / A∪CJK 交叉 / 手绘码位与排除项 / L5 构成 /
> **简体中文全量** / **日文全量**）全部在 `tools/fontgen/charset_multi12.py` 的
> `gate_multi12()`。其中后两道把「日语字和中文简体都是全量」钉成硬门禁 ——
> 口径由 `gb2312` / `shift_jis` 编解码器**机械判定**，不凭记忆列字表。

取数命令：

```powershell
python tools/fontgen/charset_multi12.py
```

---

## 3. 字形来源与路由规则

路由规则在 `tools/fontgen/route_multi12.py`（**规则本身才是产物**），
推导结果是可 diff 的快照 `tools/fontgen/route_multi12.json`（1,947,009 字节）。

**判据顺序即优先级**（`build_route()` 的 if 链）：

1. 4 个缺口码位（U+20AC / U+2260 / U+2264 / U+2265）→ `handdrawn`
2. U+AC00–U+D7AF → `fusion_ko`
3. U+4E00–U+9FFF → 中日共享的 2,078 个取 `fusion_zh_hans`；
   Fusion ja 覆盖的取 `fusion_ja`；**两个汉字源都不覆盖的取 `zlabs_cn`**
4. U+3000–U+30FF、U+FF00–U+FFEF → `fusion_ja`
5. U+2000–U+206F → `fusion_ja`
6. 其余 → `fusion_latin`

第 3 条里的次序保证了「**已有码位的路由一个都不变**」——
v1.0.0 / v1.0.1 已发布的 31,392 个码位仍走原来的源，新增的 361 个才落到 ZLabs。
§7 的门禁 11 专门盯这条不变式。

| 源 | 码位数 | 许可 | 负责范围 |
|---|---|---|---|
| `fusion_ja` | 17,544 | OFL-1.1 | 日文形汉字（JIS 独有 + 二级）/ 假名 / CJK 标点 / 全角 |
| `fusion_ko` | 11,172 | OFL-1.1 | 谚文音节（Hangul syllables） |
| `fusion_zh_hans` | 2,078 | OFL-1.1 | 中日共享的 2,078 汉字（中文形） |
| `fusion_latin` | 594 | OFL-1.1 | Latin / Latin Ext / Greek / Cyrillic / 通用西文标点 |
| `zlabs_cn` | 361 | OFL-1.1 | Fusion 两个汉字源都不覆盖的简体汉字（GB2312 二级罕用字 128 + 其它简体生僻字 233） |
| `handdrawn` | 4 | OFL-1.1 | 4 个缺口码位 —— 本仓库原创手绘 |
| **合计** | **31,753** | | |

**advance 由源字体的实际字形宽度决定**，不是本项目强行规定的：

| 宽度 | 码位数 | 来源 |
|---|---|---|
| 6 px | 663 | `fusion_latin` 592 + `fusion_ja` 68 + `handdrawn` 3 |
| 12 px | 31,090 | 其余全部（v1.0.1 的 30,729 + 新增 361，全部为全角） |

`fusion_ja` 的 68 个半角是日文排版惯例里的半角字符：U+2013 `–`、U+2018/2019 `‘ ’`、
U+201C/201D `“ ”`，以及 U+FF61–U+FF9F 的半角片假名（`｡ ｢｣､･ ｦ…ﾝ ﾞﾟ`）。
`fusion_latin` 里唯二 12 px 宽的是 U+00BD `½` 与 U+2192 `→`。

> **通用标点为什么走 `fusion_ja`**：U+2000–U+206F 里的 `‘ ’ “ ” …`
> 在 latin 变体里排成半角 6 px，在 ja 变体里排成全角 12 px（**字形同、宽度不同**）。
> 选 ja 是因为 CJK 正文里这些标点按全角排更符合惯例，也和当前家族一致。

---

## 4. 缺口码位：4 个原创手绘字形

`€` `≠` `≤` `≥` 四个码位，**Fusion 的七个变体都不覆盖**（门禁 14 每次重推都复核这一点）。

早先的方案是拿 [Zpix](https://github.com/SolidZORO/zpix-pixel-font) 补 ——
**核实后发现 Zpix 不是 MIT**：仓库无 `LICENSE` 文件、GitHub license API 返回 404、
`package.json` 无 `license` 字段，而上游 README 写明商用 USD $1000 / ￥7000，
且**明文禁止修改、反编译、转换、拆分**。裁剪成子集入库正是「修改 + 再分发」，
直接违反其条款。详见 `docs/reference-fonts.md` 的更正节。

所以这 4 个字形改为**本仓库原创手绘**：

| 码位 | 字面 | 宽度 | 依据 |
|---|---|---|---|
| U+20AC | `€` | 6 px | MS Gothic 惯例 |
| U+2260 | `≠` | 12 px | 全角运算符惯例 |
| U+2264 | `≤` | 6 px | MS Gothic 惯例 |
| U+2265 | `≥` | 6 px | MS Gothic 惯例 |

> 宽度**按当前家族实测值**取，不按 Fusion 的先例 ——
> Fusion 的 `≦ ≧ ≡` 其实是 `.notdef` 豆腐框，不能当先例。
> 绘制遵循 Unicode 标准几何形制。

> **2026-10-25 补充**：ZLabs Pixel 12px CN **也**覆盖这 4 个码位。
> 我们**仍然保留手绘字形** —— v1.0.0 / v1.0.1 已经发布过这 4 个字形的位图，
> 换字形等于对已发布码位做视觉不兼容的改动（版本规则见 `docs/spec/11` §2.10）。
> 所以「非第三源」这个说法已经不成立了（ZLabs 是第三方源），
> 现在门禁查的是「**Fusion 不覆盖它们**」，而门禁 3 查「这 4 个码位必须走 handdrawn」。

字形数据在 `vendor/multi12/handdrawn-glyphs.txt`（1,443 字节），
许可在 `vendor/multi12/OFL.txt`（标准 OFL-1.1 模板，`Copyright (c) 2026 UlyssesLeoLee`）。
构建代码在 `tools/fontgen/handdrawn.py`（与仓库既有「字体数据 / 工具代码」分界一致）。

---

## 5. 许可与分发义务

| 事项 | 结论 |
|---|---|
| 生产源许可 | 全部 **SIL OFL 1.1**（Fusion Pixel 12px + ZLabs Pixel 12px + 本仓库手绘 4 字形） |
| 成品可否分发 | **可以**（含商用） |
| 成品可否入库存放 | **可以** —— 这一点与 `PixelFont PC98 12` 不同 |
| 随包必须附 | OFL 全文 + **全部**版权声明；保留字体名 `PixelFont Multi 12` 不改名 |
| 不可 | 单独售卖字体本身；用保留字体名发布改名字体 |

> **v1.1.0 修掉的一个合规缺口**：v1.0.0 / v1.0.1 的发布包 `OFL.txt` 里只有
> **手绘字形**的版权声明，漏了 Fusion Pixel 12px 的 ——
> 而成品 TTF 的字形大量派生自 Fusion。接入 ZLabs 之后上游变成三个，
> 这个缺口更明显。v1.1.0 起 `OFL.txt` 列出**全部**版权声明与保留字体名
> （含 ZLabs 的「Z工坊/ZLabs」），再附一份 OFL-1.1 全文 ——
> 三个上游是同一个许可版本，全文只需一份。
> 本字体**不使用**任何保留字体名（OFL-1.1 §3）。

入库的生产源与许可：

| 文件 | 字节 | sha256 |
|---|---|---|
| `vendor/multi12/fusion-pixel-12px-monospaced-ja-subset.ttf` | 3,648,456 | `3eac69c9c43c1a4822c09b85bf9e1ac83099fe1da157cadbf9ad6adda2f7b152` |
| `vendor/multi12/fusion-pixel-12px-monospaced-ko-subset.ttf` | 1,699,732 | `fdb0c7df9acee449c59f6614051589d770cb96596d3ece0facf6fcea190e03ac` |
| `vendor/multi12/fusion-pixel-12px-monospaced-zh_hans-subset.ttf` | 386,868 | `67d36dce34b9d9b2e5ba12dfec3f8613bb61e6a5e1e7216d3364c7ae68558680` |
| `vendor/multi12/fusion-pixel-12px-monospaced-latin-subset.ttf` | 53,420 | `e475a74809b25d9c8ad322e4281ca04e342fbe5642c4ee4799105fa678cfad73` |
| `vendor/multi12/ZLabsPixel_12px_M_CN-subset.ttf` | 93,128 | `1daf313ed9b2aa0697de3f3828d2c01f585e6972c0e515f15a16fa0ce10da679` |
| `vendor/multi12/handdrawn-glyphs.txt` | 1,443 | `745dc5dd0b9b7b2f2b5e8af4829ca7d9b8ee88c68d3f2fb0c6181843bc0a4cc1` |
| `vendor/multi12/OFL.txt` | 4,518 | `983af89b36518a85ee5205b6cad1de232dbc2852b536c50ff2956bf74db3b5a4` |
| `vendor/multi12/LICENSES/fusion-pixel-OFL.txt` | 4,418 | `bc518cf64b8032c07690f33cc270c35c179255a6ac8efa7c165ebae7e8f76a63` |
| `vendor/multi12/LICENSES/ark-pixel-OFL.txt` | 4,412 | `3ab41567e68e3988ba1ef16dd2644eca95ca5648ea12e7d46e6287fc0bbe5aee` |
| `vendor/multi12/LICENSES/cubic-11-OFL.txt` | 5,364 | `2b6e5938e5cffa0b9e183bd05f8c363e174e7ebed1a0556e2855fd1707fa2188` |
| `vendor/multi12/LICENSES/galmuri-LICENSE.txt` | 4,360 | `86a3ee9495f942f0243f18c103da9faca27adb88142613edb8bb852e56c892c1` |
| `vendor/multi12/LICENSES/zlabs-pixel-OFL.txt` | 4,508 | `1b4d4877cb561c1800e3a2eacdbcd024760d20971656cec042d434ae9ee33c1d` |

> Fusion Pixel 是**缝合字体**（把 Ark Pixel / Cubic 11 / Galmuri 缝进同一套字重体系），
> 所以三份上游许可都随附在 `vendor/multi12/LICENSES/`。

> **裁剪版现在逐字节可复现**（2026-10-25 修复）：此前重新裁剪同一份源会产出
> **字节不同**的文件 —— 差异只在 head 表的 `modified` 一个字段
> （实测两次裁剪相差 14,974 秒 = 两次裁剪的间隔）。
> 现在裁剪器关掉时间戳重算，裁剪版**继承源字体自己的** `modified`，
> 于是「重新裁剪」不再产生内容没变却哈希不同的假 diff。

---

## 6. 构建与可复现性

### 6.1 分工

```
推导  derive_route_multi12.py   需要 third_party 原始下载 → 产出路由快照 (入库)
                                  ↓
构建  build_font_multi12.py      只读入库的快照 + 入库的裁剪版 → 产出 dist/
```

**关键设计**：字符集定义是「编码块 ∩ CJK 层**可用源的并集**」的 cmap，
那个 cmap 只存在于 `third_party/` 的原始下载里（入库的裁剪版只含路由分配给它的码位，
拿它反推字符集会形成循环定义）。所以：

- **推导**需要 `third_party/`（一次性，可复现 —— `fetch_ref_fonts.py` 按校验和下载）；
- **构建**只读**入库的**东西，干净克隆即可复现。

### 6.2 命令

```powershell
# 构建（只依赖入库文件）
python tools/fontgen/build_font_multi12.py

# 重新推导路由快照（需要 third_party 原始下载）
python tools/fontgen/fetch_ref_fonts.py
python tools/fontgen/derive_route_multi12.py --write

# 重新裁剪生产源（需要 third_party 原始下载）
python tools/fontgen/vendor_multi12_sources.py
python tools/fontgen/vendor_multi12_sources.py --check

# 门禁自测
python tools/fontgen/verify_snapshot_gate.py      # 快照自洽门禁的故障注入
python tools/fontgen/verify_coverage_gates.py     # 「简日全量」门禁的故障注入

# 打包（可复现）
python tools/fontgen/package_multi12.py --version v1.1.0 --date 2026-10-25
```

> `vendor_multi12_sources.py --check` **不需要** `third_party/` ——
> 它按**入库快照**核对裁剪版的 cmap。此前它走「临场重算规则」，
> 而那需要参考字体，于是在干净克隆上会直接抛「缺少参考字体」——
> 与它自己文档里写的「只验证已入库的裁剪版」矛盾。2026-10-25 修掉。

### 6.3 干净克隆可复现性（已实测）

把仓库里**已入库的文件**（排除 `third_party/`、`dist/`、`reports/`、`.git/`）
复制到一个空目录后构建，与主仓库产物**逐字节一致**：

| 产物 | 干净克隆 vs 主仓库 |
|---|---|
| `PixelFontMulti-12.ttf` | MATCH |
| `PixelFontMulti-12.bdf` | MATCH |
| `PixelFontMulti-12.bdf.map` | MATCH |
| `PixelFontMulti-12-atlas.png` | MATCH |
| `PixelFontMulti-12-atlas.json` | MATCH |
| `PixelFontMulti-12-specimen.png` | MATCH |

> 这条不是「推理」，是实跑出来的：**134 个入库文件、12,852,292 字节**、
> 逐文件 sha256 比对 0 不一致，然后在空目录里跑 `build_font_multi12.py`，
> 六个产物 sha256 全部 MATCH。

---

## 7. 验证门禁

| # | 门禁 | 工具 | 结果 |
|---|---|---|---|
| 1 | 逐层累加 = 31,753 | `charset_multi12.gate_multi12()` | PASS |
| 2 | 方案 A 交叉核对 = 19,816 | 同上 | PASS |
| 3 | 方案 A ∪ CJK 整块 = 31,753 | 同上 | PASS |
| 4 | 4 个手绘码位在集合内，且 **Fusion** 未覆盖它们 | 同上 | PASS |
| 5 | 排除项未被收进来 | 同上 | PASS |
| 6 | **L5 构成 = 1,689 汉字 + 6 符号** | 同上 | PASS |
| 7 | 路由覆盖 = 字符集（31,753 = 31,753） | `derive_route_multi12.py` | PASS |
| 8 | 源集合无未登记键 | 同上 | PASS |
| 9 | handdrawn 恰好 4 个 + 字形自检（画布/宽度/墨迹） | 同上 | PASS |
| 10 | fusion_ko = 11,172 | 同上 | PASS |
| 11 | fusion_zh_hans = 中日共享 2,078 | 同上 | PASS |
| 12 | 逐条渲染 31,753 个码位：无空字形、尺寸全合网格 | 同上 | PASS |
| 13 | U+005C ≠ U+00A5（反斜杠没被画成 ¥） | 同上 | PASS |
| 14 | 4 个缺口仍不被任何 Fusion 变体覆盖 | 同上 | PASS |
| 15 | 全部源均为 OFL-1.1 | 同上 | PASS |
| 16 | 裁剪前后**逐像素一致** 31,749 个字形（5 个源） | `vendor_multi12_sources.py` | 0 不一致 |
| 17 | 裁剪版 cmap == 路由分配给该源的码位 | 同上 | PASS |
| 18 | BDF 回读 31,753 字形逐像素一致 | `build_font_multi12.py` | PASS |
| 19 | PNG 图集回读 31,753 字形一致 | 同上 | PASS |
| 20 | TTF 轮廓全落像素网格且与源位图一致 | 同上 | PASS |
| 21 | TTF 元数据：代码页 1252/932/936/949 齐备 | 同上 | PASS |
| 22 | 路由快照自洽（总量/源/层归属/源覆盖/层集合） | `route_multi12.verify_snapshot()` | PASS |
| 23 | GDI 选择：ANSI/DEFAULT/GB2312/SHIFTJIS/HANGEUL 选中本族 | `verify_gdi_multi12.py` | 5/5 |
| 24 | GDI 枚举：同上 5 个 charset 均含本族 | 同上 | 5/5 |
| 25 | GDI 栅格化 vs 设计位图：31,753 码位 × (12ppem + 24ppem) | 同上 | 4 × 31,753 全一致 |
| 26 | DEFAULT 质量下抗锯齿像素 | 同上 | 0 |
| 27 | **回下载逐字节一致**（6 个资产） | 发布流程阶段 8 | 一致 |
| 28 | **回下载产物可渲染** | `verify_gdi_multi12.py --ttf <回下载路径> --bdf <回下载 zip 内路径>` | 5 个 charset + 4 × 31,753 逐格一致 |
| 29 | **快照门禁的故障注入自测** | `verify_snapshot_gate.py` | 8/8 种损坏全部被抓到 |
| 30 | **全量门禁的故障注入自测** | `verify_coverage_gates.py` | 7/7 种损坏全部被抓到 |
| 31 | **与 v1.0.1 的逐字形比对**：31,392 个已发布码位的位图逐格相同 | 发布流程阶段 8 | 全一致 |

> **门禁 30 为什么必须有**：「日语字和中文简体都是全量」如果只写进文档，
> 它就只是一句文档；写进门禁才可执行；而**门禁也要被测** ——
> `verify_coverage_gates.py` 对 4 道新门禁做故障注入，7/7 全抓到。
> 注入点打在「口径」与「路由表」上，**不动磁盘上的快照**。
>
> **门禁 31 为什么必须有**：本次是 MINOR 发布（新增码位），
> 按 `docs/spec/11` §2.10，已发布码位的位图必须**一个都不变**。
> 门禁 14（推导层第 11 条）从规则结构上保证这一点，门禁 31 从**实际产物**上再验一遍。

GDI 门禁的额外一条：繁体（`lfCharSet=BIG5`）**必须选不中**本字体 ——
字符集里没有 zh_hant 码位，选中了反而是 bug。实测选中的是系统字体 `Ebrima`，符合预期。

---

## 8. 产物清单与校验和

| 产物 | 字节 | sha256 |
|---|---|---|
| `dist/PixelFontMulti-12.ttf` | 7,853,876 | `b844d8c1f92114acfcb2745dcff6c1c13711bb6853b372d6bab6b8137bf87c15` |
| `dist/PixelFontMulti-12.bdf` | 5,147,221 | `64b6f8518eeddc1af50e1364e3389fd8d07f059156d46253fb3f0f6c68dddb76` |
| `dist/PixelFontMulti-12.bdf.map` | 1,396,265 | `6ab373e4bf976f0bcd8c2cdd5f73be6010371f3aba200a6f7f443d629d0f7b31` |
| `dist/PixelFontMulti-12-atlas.png` | 780,395 | `6012edab6e61bd11ef680b40b69e51faa07b8a57d01b609ab053ab681ea1a9bc` |
| `dist/PixelFontMulti-12-atlas.json` | 686,595 | `37bec853390fa093e92173ee1dd1a1a175c91f346aacfae56ae937bcd3b8cb08` |
| `dist/PixelFontMulti-12-specimen.png` | 3,174 | `c9d93ff4e4efeae4c0c61bb5e96342584ac77d8e0475755566a1bf0b75931a25` |

图集尺寸 768 × 6,461 px（64 列 × 12×13 单元）。

> `dist/` 按仓库政策不入库（见 `.gitignore`）。本家族与 `PixelFont PC98 12` 的
> 区别是**生产源全为宽松许可**，所以成品**可以**入库存放 ——
> 是否入库是发布策略选择，不是许可问题。

### 8.1 发布

- 最新 Release：`multi12-v1.1.0` → `main` 的 `（见 §8.2）`
  —— <https://github.com/UlyssesLeoLee/PixelFont/releases/tag/multi12-v1.1.0>
- 上一版：`multi12-v1.0.1` → `main` 的 `0b9c686`
  —— <https://github.com/UlyssesLeoLee/PixelFont/releases/tag/multi12-v1.0.1>

### 8.2 发布件清单（v1.1.0）

发布包由 `tools/fontgen/package_multi12.py` 生成（**可复现** ——
同样的输入产出同样的字节，条目时间戳固定为发布日正午）。

zip 内 7 项：TTF / BDF / 图集 / 样张 / `安装与使用说明.md` / `OFL.txt` / `SHA256SUMS.txt`。

> **打包流程为什么要入库**：v1.0.0 / v1.0.1 的打包是临时脚本做的，没入库 ——
> 意味着「发布包长什么样」这件事**无法复现**，也没法在干净克隆上核对。
> 发布流程的每一步都该是可重跑的。
>
> **zip 名字带版本号**：v1.0.0 与 v1.0.1 同一天发布过一次，日期式命名
> （`…-2026-10-25.zip`）会让两个 Release 出现**同名但内容不同**的附件。
> 从 v1.1.0 起改为 `<家族>-<版本>.zip`。
>
> **`OFL.txt` 是必须项** —— OFL-1.1 要求随字体分发附上许可证全文与版权声明。
> 它既在 zip 里，也作为独立附件发布。v1.1.0 起它列出**全部**三个上游的版权声明
> 与保留字体名（见 §5）。

---

## 9. 已知边界

### 9.1 12 px 下的渲染器网格拟合

构建自带的抽样（611 字）给出：

- **24 px 及以上**：平均偏差 **0.00 px/字**（最坏 0）—— 精确。
- **12 px**：平均偏差 **21.63 px/字**（最坏 45）—— 渲染器会做抗锯齿与网格拟合。

这不是字体缺陷，而是「点阵字体 + 缩放渲染」的固有行为。
**需要像素级精确时用 BDF 或 PNG 图集**，不要指望 TTF 在 12 ppem 下逐格对齐。
GDI 门禁在 `DEFAULT` 质量（关抗锯齿）下实测抗锯齿像素为 0。

### 9.2 待验证项

| 事项 | 状态 | 验证方法 |
|---|---|---|
| 在**真实韩文 Windows** 上系统级安装后，重启仍可选中 | **待验证** | 本机只做了 `AddFontResourceExW` 临时注册 + GDI 选择/枚举；系统级安装需另机复测 |
| 在 macOS / Linux（fontconfig）上的渲染 | **待验证** | 本仓门禁只覆盖 Windows GDI；跨平台需另测 |
| 12 px 下的 FreeType / CoreText 逐格一致性 | **待验证** | 上面 9.1 的 21.63 px 平均偏差就是这类渲染器的表现 |
| **ZLabs 字形与 Fusion 字形混排的观感一致性** | **待验证** | 361 个简体汉字用 ZLabs 字形，其邻字用 Fusion 字形；两者网格同构（实测 ascent/descent/advance 一致），但**笔画风格**由不同设计师决定。本机只验了「基线不错、逐格一致」，**没有**做主观观感评价 |

### 9.3 设计取舍

- **融合 5 个上游源成一个家族**，意味着汉字写法在不同源之间可能有细微差别
  （JIS 一级/二级、中日共享的 2,078 个汉字取中文形、Fusion 覆盖不到的 361 个简体字取 ZLabs）。
  这是「一个字体覆盖多语系」的固有代价。
- **advance 不统一**：663 个码位是 6 px 宽。这是源字体的既有宽度，
  强行拉成 12 px 会破坏西文排版；强行压成 6 px 会破坏 CJK 排版。
- **字符集边界**：CJK 扩展 A（U+3400–U+4DBF）与 CJK 兼容表意文字（U+F900–U+FAFF）
  **不在**本字体内 —— 它们不属于 GB2312 / JIS X 0208 的范围，在「全量」口径之外。
  简体常用字与日文常用字已 100% 覆盖。

---

## 相关文档

- `docs/spec/02-character-set.md` —— 字符集定义书
- `docs/spec/08-font-build.md` —— 字体制作详细设计书
- `docs/reference-fonts.md` —— 参考字体来源、许可与校验和（含 Zpix 许可更正）
- `docs/install.md` —— 安装与复核方法
- `docs/word-compat.md` —— Word 兼容性与已知问题
