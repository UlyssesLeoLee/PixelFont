# 参考字体清单（字形身份校验用）与生产源清单

本项目的字形校验需要**独立来源**的开源免费像素字体当基准。

**两类字体的处理不一样, 别混**:

| 类别 | 是什么 | 入库? | 为什么 |
|---|---|---|---|
| **参考字体** | 只用于**校验**, 不参与构建 | **不入库** (`third_party/` 在 `.gitignore` 里) | 只提交来源/版本/许可证/sha256 清单, 保证任何人能取到同一份字节 |
| **生产源** | **参与构建**, 字形真的进到成品里 | **入库** (`vendor/`) | 不入库就等于"构建依赖某台机器上恰好下载过某个字体", 换台机器构建不出同一个结果 |

复现方式：

```bash
python tools/fontgen/fetch_ref_fonts.py            # 下载参考字体到 third_party/ref_fonts/
python tools/fontgen/fetch_ref_fonts.py --verify   # 只校验本地已有文件的 sha256
python tools/fontgen/vendor_fusion_pixel.py           # 裁剪并验证生产源 Ark Pixel
python tools/fontgen/vendor_fusion_pixel.py --check   # 只验证已入库的裁剪版
```

## 为什么是这五套

判据是**设计谱系互相独立**——只有独立来源画出来的字，才能当"这个字本来就该长这样"的基准。
如果拿同一套点阵的衍生字体互相比对，就成了自己证明自己。

| 字体 | 版式 | 谱系 | 许可证 | 在校验里的角色 |
|---|---|---|---|---|
| Ark Pixel | 12px 等宽 | 日系点阵，笔画方正规整，作者自绘 | OFL-1.1 | 主力 12px 基准；**同时是生产源**（见下） |
| Fusion Pixel | 12px 等宽 | **缝合字体**：把 Ark / Cubic11 / Galmuri 等多套点阵缝进同一套字重体系 | OFL-1.1 | 交叉验证 Ark 的结论；**Multi 12 的主力生产源** |
| **ZLabs Pixel** | 12px 等宽 | 国产点阵，作者自绘，**简体覆盖最全** | OFL-1.1（保留字体名「Z工坊/ZLabs」） | **Multi 12 的简体补源**（见下）；12px 层面与 Ark / Fusion 正交的第三票 |
| Zpix（最像素） | 12px | 国产点阵，笔画带手绘味，作者自绘 | **非 MIT**（商用付费，且禁止修改/拆分/再分发，见下文更正） | 与日系谱系正交的第三票；**引入 Ark 作生产源后, 它成了唯一独立的 12px 票** |
| GNU Unifont | 16×16 | 学术项目，**八字节点阵**直写渲染，与 CJK 点阵毫无血缘 | GPL-2.0+ （含字体嵌入例外） | 非 CJK 谱系基准；因是 16px，不参与 12px 的笔画数比对 |

### 实测更正: Fusion 的简体版与 Ark 结构完全相同

早先这份清单说"Fusion 与 Ark 高度一致, 仍算一票"。**实测下来这句话是错的**：

```
ark-pixel-zh_hans vs fusion-pixel-zh_hans
  共有 3605 字   结构距离均值 0.00   中位 0.0   |差|>=12 的占比 0.0%
```

**3605 个汉字的结构签名（字腔数 / 竖笔分段 / 横笔分段）逐个完全相同。**
Fusion Pixel 的简体版（zh_hans）就是 Ark Pixel 的简体版 —— 它缝进去的
Cubic 11 / Galmuri 落在日文与韩文变体上，简体变体没用到。

后果很直接：**Fusion 对简体字不提供任何独立票**。
早先"独立票数 = 3 票（Ark / Zpix / Unifont）"的说法，
准确表述是 **12px 层面只有 2 票（Ark / Zpix），Unifont 因 16px 不参与笔画数比对**。

更要紧的是：**引入 Ark Pixel 作生产源之后，Ark 票也变成自证的**——
拿生产源自己当基准，比对就变成了自己和自己比。
所以目视复核的参考列已改为 **Zpix + Unifont**（都独立于生产源），
详见 [`glyph-review-protocol.md`](glyph-review-protocol.md) 第 4 节。

### 选它们时踩过的坑

- **Cubic 11 不可得**：4 个候选 URL 全部 404（项目已改用 Fusion 缝合它）。
  所以"日系日系"之外的独立票只有 Zpix 与 Unifont，样本量受限，结论按"≥2/3 票"才采信。
- **必须用原生 ppem 渲染**：像素字体的轮廓是按自己的网格设计的，在别的字号下栅格化会重排笔画，
  那时的形状已经不是它"本来该有的样子"。因此 Ark/Fusion/Zpix 一律 12px、Unifont 一律 16px。
- **参考字体自身缺字**：Ark 缺 150 个（GB2312 后半的简体字），Zpix 缺 12 个
  （U+3094-3096 / 3099 / 309A / 309F / 30A0 / 30F7-30FF 等假名）。
  覆盖缺口是**参考字体的属性，不是本项目的缺陷**，报告中单列，不参与判定。
- **缺字时 FreeType 会画 `.notdef`**（一个空心豆腐框，自带 1 个"字腔"）。
  判断"某个源行不行"必须先查 cmap，不能靠渲染结果猜 ——
  这个坑真踩过：推导出的名单里一度混进 39 个 MS Gothic 根本没有的码位。


## 版本与校验和

全部 sha256 实测值（`fetch_ref_fonts.py --verify` 会逐个核对）：

### Ark Pixel Font 12px — v2026.10.16

- 来源：<https://github.com/TakWolf/ark-pixel-font>（release `2026.10.16`）
- 归档 URL：`https://github.com/TakWolf/ark-pixel-font/releases/download/2026.10.16/ark-pixel-font-12px-monospaced-ttf-v2026.10.16.zip`
- 归档 sha256：`ae1512de69702ebfd3def3de65b73037f112431452766dc4fc8fbc404838554d`
- 使用文件：`ark-pixel-12px-monospaced-zh_hans.ttf`
  sha256 `56e82b4fa83e9e7bc586da288a7eb0481f8bc1f1fa8ecc6ad952781c8c0e366a`
- 许可证：SIL Open Font License 1.1
- 落地路径：`third_party/ref_fonts/ark-pixel-12px/ark-pixel-12px-monospaced-zh_hans.ttf`

### Fusion Pixel Font 12px — v2026.10.16

- 来源：<https://github.com/TakWolf/fusion-pixel-font>（release `2026.10.16`）
- 归档 URL：`https://github.com/TakWolf/fusion-pixel-font/releases/download/2026.10.16/fusion-pixel-font-12px-monospaced-ttf-v2026.10.16.zip`
- 归档 sha256：`c4c9e466042d76f4b37c78232b6ecd4e1f25be3a27cd0f3aacdfaf7de5bd515b`
- 使用文件：`fusion-pixel-12px-monospaced-zh_hans.ttf`
  sha256 `4ae459a3bdff66bcf430f1b1cd4641a0b4433732a70c57d6a975ab058b0a88e7`
- 许可证：SIL Open Font License 1.1
- 落地路径：`third_party/ref_fonts/fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans.ttf`

### Zpix（最像素）— v3.3.0

- 来源：<https://github.com/SolidZORO/zpix-pixel-font>（release `v3.3.0`）
- 下载 URL：`https://github.com/SolidZORO/zpix-pixel-font/releases/download/v3.3.0/zpix.ttf`
- sha256：`a67917d94bb597acbdf3bfe1cf97047cc3e1cdd3839d21da188e35cc0737e828`
- 许可证：**不是 MIT** —— 见下面的更正
- 落地路径：`third_party/ref_fonts/zpix.bin`

#### 更正：Zpix 的许可不是 MIT，且**禁止修改/拆分/再分发**

本文早先写的是「许可证：MIT」，那是**错的**。2026-10-24 核验上游后更正：

| 证据 | 结果 |
|---|---|
| 仓库根目录的 `LICENSE` 文件 | **不存在**（`v3.3.0` 与 `main` 都没有） |
| GitHub license API（`/repos/SolidZORO/zpix-pixel-font/license`） | **404** —— GitHub 识别不到任何许可 |
| `package.json` 的 `license` 字段 | **没有这个字段** |
| 上游 README「授权与价格」 | 商用单产品 **USD $1000 / ￥7000**；教育与个人用途免费 |
| 上游 README「版权声明」 | 明确写着 **禁止对本字体进行修改、反编译、转换、拆分**（所有授权版本均不允许） |

后果有两条，都影响本仓库：

1. **Zpix 只能当校验用的参考字体，不能当生产源。**
   裁剪成子集入库正是「修改 + 再分发」，直接违反其条款。
   Multi 12 需要它覆盖的 4 个码位（`€` `≠` `≤` `≥`）因此改用**本仓库原创手绘**。
2. **不可随本仓库分发。** 它留在 `third_party/`（不入库）只用于比对，
   任何打包分发都不能带上它。

> 教训：许可证字段要**以上游原文为准**，不能凭印象填。
> 「看起来像开源字体」不等于「可以随便改、随便发」。

### ZLabs Pixel 12px — Build_20260519

- 来源：<https://github.com/Astro-2539/ZLabs-Pixel-12px>（release `Build_20260519`）
- 下载 URL：`https://github.com/Astro-2539/ZLabs-Pixel-12px/releases/download/Build_20260519/ZLabsPixel_12px_M_CN.ttf`
- sha256：`c4bf6069b8e5e31dc42c81f310afbc322c2cbc843ceba6c871358f9f1aaae033`（3 350 152 字节）
- 许可证：SIL Open Font License 1.1，`Copyright (c) 2023-2025, Astro_2539`，
  **保留字体名 "Z工坊/ZLabs"**
  （许可文件 sha256 `1b4d4877cb561c1800e3a2eacdbcd024760d20971656cec042d434ae9ee33c1d`）
- 落地路径：`third_party/ref_fonts/zlabs-pixel-12px/ZLabsPixel_12px_M_CN.ttf`
- 抓取：`python tools/fontgen/fetch_ref_fonts.py`（按 sha256 校验）

**为什么需要它（2026-10-25 实测）**：Fusion Pixel 与 Ark Pixel 的**七个变体全部**
缺少 **128 个 GB2312 二级汉字**（生僻字，如 `劐 唣 垡 墚 墼 娈 媵 嫠 嬷 尜 峁 嵴`）。
实测覆盖对照：

| 源 | GB2312 汉字覆盖 |
|---|---|
| Fusion Pixel 12px（七个变体） | 6,635 / 6,763（98.11%） |
| Ark Pixel 12px（七个变体） | 6,635 / 6,763（98.11%） |
| **ZLabs Pixel 12px CN** | **6,763 / 6,763（100%）** |

也就是说，**12px 开源点阵里只有 ZLabs 覆盖 GB2312 全部汉字**。
GNU Unifont 也能覆盖全部，但它是 16×16 网格，降到 12×13 需要重采样，
生僻字的笔画会因降采样失真 —— 质量不可控，所以不选。

**网格同构（实测）**：ZLabs CN 与 Fusion ja 的自然度量完全一致 ——
`ascent=10 / descent=2`、CJK advance 12px、拉丁 advance 6px、upm 1200；
墨迹都落在第 0..11 行。可以直接拼进同一个家族而不错基线。

> **保留字体名**：ZLabs 的 OFL-1.1 带保留字体名「Z工坊/ZLabs」。
> OFL-1.1 §3 要求派生作品**不得使用**保留字体名 ——
> 本家族叫 `PixelFont Multi 12` / `PixelFontMulti-12`，与它无关，**未使用**任何保留字体名。
> 发布包的 `OFL.txt` 里显式写明了这一点。

### GNU Unifont — 16.0.01

- 来源：<https://unifoundry.com/unifont/>
- 下载 URL：`https://unifoundry.com/pub/unifont/unifont-16.0.01/font-builds/unifont-16.0.01.otf`
- sha256：`ea39a0e614e7486490239c5759e1a0cd86fd49e335c4b08d2fd13e313147f022`
- 许可证：GPL-2.0+，**含字体嵌入例外**（因此可随软件分发）
- 落地路径：`third_party/ref_fonts/unifont-16.bin`

## 生产源（参与构建，入库）

### Fusion Pixel Font 12px 简体 — v2026.10.16（裁剪版，**生产源**）

- 上游来源 / 版本 / 归档 sha256：见上面「Fusion Pixel Font 12px — v2026.10.16」一节
- 入库文件：`vendor/fusion-pixel-12px/fusion-pixel-12px-monospaced-zh_hans-subset.ttf`
- 大小：764 748 字节（未裁剪的原始文件 7 135 828 字节）
- sha256：`fc910f23ff8ee2df8f2fec6f91381a60df812e3a16ce177f48528f1db6551a37`
- 许可证：`vendor/fusion-pixel-12px/LICENSES/` 下三份
  （Ark Pixel OFL / Cubic 11 OFL / Galmuri LICENSE）—— Fusion 是缝合字体，三份都要随附
- 裁剪脚本：`tools/fontgen/vendor_fusion_pixel.py`

**为什么生产源用 Fusion 而不是 Ark**：实测 Fusion 的简体版与 Ark 的**结构**完全相同
（3605 个共有汉字逐个一致），但**覆盖**多 12054 个码位。对我们 4161 个码位：
Ark 覆盖 3990（缺 150），**Fusion 覆盖 4157 / 4161**（缺的 4 个是 € ≠ ≤ ≥，
它们走 MS Gothic / SimHei，不走第三个源）；而共有部分
**3989/3989 位图逐字节相同** —— 换源对已有字**零画风变化**，
却让原先没得选的 150 个字有了真正的点阵字形。

`--check` 做两项验证，缺一不可：

1. 裁剪前后**逐像素一致**（实测 4157 个字形，0 处不一致）；
2. 裁剪版的 cmap == 原字体 cmap ∩ 本项目字符集（少一个就是裁剪把字弄丢了，
   多一个就是裁剪没生效）。

> 踩过的坑：`fontTools.subset --unicodes` 收的是**十六进制码位**，
> 写成 `U+4E01` 会被静默忽略一部分 —— 那 150 个码位随后退化成 `.notdef`，
> 而 `.notdef` 是空心豆腐框、自带 1 个"字腔"，会让"这个源能画"变成假阳性。

**为什么必须入库**：Ark/Fusion 作为**生产源**，它的原生点阵直接进到成品里。
不入库就等于构建依赖"这台机器上恰好下载过它"，换台机器构建不出同一个结果。
（参考字体则相反 —— 它们不参与构建，所以只记清单。）

### Multi 12 的生产源（`vendor/multi12/`）

`PixelFont Multi 12` 的生产源是 **5 个裁剪版 + 1 个手绘数据文件**，全部 OFL-1.1：

| 入库文件 | 负责范围 | 字节 | sha256 |
|---|---|---|---|
| `fusion-pixel-12px-monospaced-ja-subset.ttf` | 日文形汉字 / 假名 / CJK 标点 / 全角（17,544 码位） | 3,648,456 | `3eac69c9c43c1a4822c09b85bf9e1ac83099fe1da157cadbf9ad6adda2f7b152` |
| `fusion-pixel-12px-monospaced-ko-subset.ttf` | 谚文音节（11,172 码位） | 1,699,732 | `fdb0c7df9acee449c59f6614051589d770cb96596d3ece0facf6fcea190e03ac` |
| `fusion-pixel-12px-monospaced-zh_hans-subset.ttf` | 中日共享的 2,078 汉字（中文形） | 386,868 | `67d36dce34b9d9b2e5ba12dfec3f8613bb61e6a5e1e7216d3364c7ae68558680` |
| `fusion-pixel-12px-monospaced-latin-subset.ttf` | Latin / Greek / Cyrillic / 西文标点（594 码位） | 53,420 | `e475a74809b25d9c8ad322e4281ca04e342fbe5642c4ee4799105fa678cfad73` |
| `ZLabsPixel_12px_M_CN-subset.ttf` | **简体补源**：Fusion 两源都不覆盖的 361 个汉字 | 93,128 | `1daf313ed9b2aa0697de3f3828d2c01f585e6972c0e515f15a16fa0ce10da679` |
| `handdrawn-glyphs.txt` | `€` `≠` `≤` `≥` 4 个原创手绘字形 | 1,443 | `745dc5dd0b9b7b2f2b5e8af4829ca7d9b8ee88c68d3f2fb0c6181843bc0a4cc1` |

许可随附在 `vendor/multi12/LICENSES/`：
`fusion-pixel-OFL.txt`（TakWolf）/ `ark-pixel-OFL.txt` / `cubic-11-OFL.txt` /
`galmuri-LICENSE.txt`（以上三份是 Fusion 缝进去的上游）/ `zlabs-pixel-OFL.txt`（Astro_2539）；
手绘字形的许可在 `vendor/multi12/OFL.txt`。

裁剪脚本：`tools/fontgen/vendor_multi12_sources.py`（两层验证：
逐像素一致 + cmap 覆盖相符；连续两次裁剪**逐字节可复现**）。

## 发布

| 项 | 状态 | 理由 |
|---|---|---|
| `main` | 与 `dev` **同步**（都指向同一提交） | 仓库默认分支原本只有 `LICENSE` 一个文件（初始提交），32 个提交的工作全在 `dev` 上 —— 谁 clone 仓库都看不到项目本身。`main` 与 `dev` 零分叉，`--ff-only` 快进即可，无合并提交。`main` 上**没有 CI 流水线**（无 `.github/` 目录），快进不会触发任何自动发布。 |
| `dist/` 成品 | **不入库**（`.gitignore`） | 成品里嵌着 **SimHei 与 MS Gothic 的位图** —— 两者都是微软的**专有**字体。把含它们派生位图的 TTF/BDF 放进公开仓库等于再分发专有字体的衍生作品，这是许可证问题，不该由我替你决定。仓库发布的是**源码 + 可复现的构建**；构建时从本机系统字体目录读 SimHei/MS Gothic，从 `vendor/` 读 Fusion Pixel（OFL，随附许可证）。 |
| `vendor/` 的 Fusion Pixel | **入库** | 它是**生产源**，参与构建。不入库就等于构建依赖"这台机器上恰好下载过它"，换台机器构建不出同一个结果。OFL-1.1 + Cubic 11 OFL + Galmuri LICENSE 三份随附。 |
| `third_party/` 的参考字体 | **不入库** | 只用于**校验**，不参与构建，所以只记来源/版本/许可证/sha256（见本文档上半部分）。 |

> 如果将来要把成品（`dist/`）随包分发，需要先解决 SimHei / MS Gothic 的再分发授权，
> 那是一个法律判断，不在技术范围内。

## 许可证义务

| 字体 | 是否随本仓库分发 | 义务 |
|---|---|---|
| Fusion Pixel（**生产源**，`vendor/`） | **是** | OFL-1.1：保留版权与许可证声明，随附 OFL 全文（已放在 `vendor/fusion-pixel-12px/OFL.txt`），不得单独售卖字体本身，不得用保留字体名 |
| Fusion Pixel 原始包 | 否 | 若将来打包分发，需保留 OFL 声明 |
| **Multi 12 手绘 4 字形**（`vendor/multi12/`，**生产源**） | **是** | OFL-1.1：本仓库原创，按标准几何形制手绘，版权与 OFL 全文见 `vendor/multi12/OFL.txt` |
| **ZLabs Pixel 12px CN**（`vendor/multi12/`，**生产源**） | **是** | OFL-1.1：版权与保留字体名见 `vendor/multi12/LICENSES/zlabs-pixel-OFL.txt`；**不得使用保留字体名「Z工坊/ZLabs」**（本家族未使用）；不得单独售卖字体本身 |
| Zpix | **否，且不得修改/拆分/再分发** | 商用需付费；上游明确禁止修改与再分发，**不能**当生产源、不能随包分发 |
| GNU Unifont | 否 | GPL-2.0+ 字体嵌入例外；按例外条款随附声明即可 |

**另需注意**：本项目另两个源（SimHei、MS Gothic）是**系统字体**，属各自权利人的专有资产，
本仓库不分发它们，只在构建时从本机系统字体目录读取。
`PixelFont PC98 12` 的成品字形派生自它们，因此 `dist/` 不入库；
`PixelFont Multi 12` 的生产源全部是宽松许可，成品**可以**入库存放。

## 相关文档

- 校验方法与结论：[`glyph-identity-verification.md`](glyph-identity-verification.md)
- 目视复核协议：[`glyph-review-protocol.md`](glyph-review-protocol.md)
- 回归测试方法：[`regression.md`](regression.md)
