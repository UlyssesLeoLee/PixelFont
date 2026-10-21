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
python tools/fontgen/vendor_ark_pixel.py           # 裁剪并验证生产源 Ark Pixel
python tools/fontgen/vendor_ark_pixel.py --check   # 只验证已入库的裁剪版
```

## 为什么是这四套

判据是**设计谱系互相独立**——只有独立来源画出来的字，才能当"这个字本来就该长这样"的基准。
如果拿同一套点阵的衍生字体互相比对，就成了自己证明自己。

| 字体 | 版式 | 谱系 | 许可证 | 在校验里的角色 |
|---|---|---|---|---|
| Ark Pixel | 12px 等宽 | 日系点阵，笔画方正规整，作者自绘 | OFL-1.1 | 主力 12px 基准；**同时是生产源**（见下） |
| Fusion Pixel | 12px 等宽 | **缝合字体**：把 Ark / Cubic11 / Galmuri 等多套点阵缝进同一套字重体系 | OFL-1.1 | 交叉验证 Ark 的结论 |
| Zpix（最像素） | 12px | 国产点阵，笔画带手绘味，作者自绘 | MIT | 与日系谱系正交的第三票；**引入 Ark 作生产源后, 它成了唯一独立的 12px 票** |
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
- 许可证：MIT
- 落地路径：`third_party/ref_fonts/zpix.bin`

### GNU Unifont — 16.0.01

- 来源：<https://unifoundry.com/unifont/>
- 下载 URL：`https://unifoundry.com/pub/unifont/unifont-16.0.01/font-builds/unifont-16.0.01.otf`
- sha256：`ea39a0e614e7486490239c5759e1a0cd86fd49e335c4b08d2fd13e313147f022`
- 许可证：GPL-2.0+，**含字体嵌入例外**（因此可随软件分发）
- 落地路径：`third_party/ref_fonts/unifont-16.bin`

## 生产源（参与构建，入库）

### Ark Pixel Font 12px 简体 — v2026.10.16（裁剪版）

- 上游来源 / 版本 / 许可证 / sha256：见上面「Ark Pixel Font 12px — v2026.10.16」一节
- 入库文件：`vendor/ark-pixel-12px/ark-pixel-12px-monospaced-zh_hans-subset.ttf`
- 大小：730 512 字节（未裁剪的原始文件 5 132 788 字节）
- sha256：`220c656957a2ce00bd00a4abc0e78086f0c479d6da547b5722a03ce3ae0d988b`
- 许可证：`vendor/ark-pixel-12px/OFL.txt`（SIL Open Font License 1.1 全文，随附）
- 裁剪脚本：`tools/fontgen/vendor_ark_pixel.py`

**裁剪做了什么**：只保留本项目 4140 个码位的字形，不动轮廓、不动 hinting。
`--check` 会做两项验证，缺一不可：

1. 裁剪前后的渲染**逐像素一致**（实测 3990 个字形，0 处不一致）；
2. 裁剪版的 cmap == 原字体 cmap ∩ 本项目字符集（少一个就是裁剪把字弄丢了，
   多一个就是裁剪没生效）。

> 踩过的坑：`fontTools.subset --unicodes` 收的是**十六进制码位**，
> 写成 `U+4E01` 会被静默忽略一部分 —— 那 150 个码位随后退化成 `.notdef`，
> 而 `.notdef` 是空心豆腐框、自带 1 个"字腔"，会让"这个源能画"变成假阳性。

**为什么必须入库**：Ark Pixel 现在是**生产源**，它的原生点阵直接进到成品里。
不入库就等于构建依赖"这台机器上恰好下载过 Ark Pixel"，换台机器构建不出同一个结果。
（参考字体则相反 —— 它们不参与构建，所以只记清单。）

## 许可证义务

| 字体 | 是否随本仓库分发 | 义务 |
|---|---|---|
| Ark Pixel（**生产源**，`vendor/`） | **是** | OFL-1.1：保留版权与许可证声明，随附 OFL 全文（已放在 `vendor/ark-pixel-12px/OFL.txt`），不得单独售卖字体本身，不得用保留字体名 |
| Fusion Pixel | 否 | 若将来打包分发，需保留 OFL 声明 |
| Zpix | 否 | 若将来打包分发，需保留 MIT 许可声明 |
| GNU Unifont | 否 | GPL-2.0+ 字体嵌入例外；按例外条款随附声明即可 |

**另需注意**：本项目另两个源（SimHei、MS Gothic）是**系统字体**，属各自权利人的专有资产，
本仓库不分发它们，只在构建时从本机系统字体目录读取。

## 相关文档

- 校验方法与结论：[`glyph-identity-verification.md`](glyph-identity-verification.md)
- 目视复核协议：[`glyph-review-protocol.md`](glyph-review-protocol.md)
- 回归测试方法：[`regression.md`](regression.md)
