# 参考字体清单（字形身份校验用）

本项目的字形校验需要**独立来源**的开源免费像素字体当基准。二进制**不入库**
（`third_party/` 在 `.gitignore` 里），仓库只提交这份清单，保证任何人能取到**同一份字节**。

复现方式：

```bash
python tools/fontgen/fetch_ref_fonts.py            # 下载到 third_party/ref_fonts/
python tools/fontgen/fetch_ref_fonts.py --verify   # 只校验本地已有文件的 sha256
```

## 为什么是这四套

判据是**设计谱系互相独立**——只有独立来源画出来的字，才能当"这个字本来就该长这样"的基准。
如果拿同一套点阵的衍生字体互相比对，就成了自己证明自己。

| 字体 | 版式 | 谱系 | 许可证 | 在校验里的角色 |
|---|---|---|---|---|
| Ark Pixel | 12px 等宽 | 日系点阵，笔画方正规整，作者自绘 | OFL-1.1 | 主力 12px 基准 |
| Fusion Pixel | 12px 等宽 | **缝合字体**：把 Ark / Cubic11 / Galmuri 等多套点阵缝进同一套字重体系 | OFL-1.1 | 交叉验证 Ark 的结论 |
| Zpix（最像素） | 12px | 国产点阵，笔画带手绘味，作者自绘 | MIT | 与日系谱系正交的第三票 |
| GNU Unifont | 16×16 | 学术项目，**八字节点阵**直写渲染，与 CJK 点阵毫无血缘 | GPL-2.0+ （含字体嵌入例外） | 非 CJK 谱系基准；因是 16px，不参与 12px 的笔画数比对 |

### 关于 Fusion Pixel 的独立性

Fusion 是缝合产物，严格说不算完全独立。但两点让它仍然可用：

1. 它缝进去的底料（Cubic 11、Galmuri 等）**不在这份清单里**，也不在它自己的主要来源位上；
2. 实测它与 Ark 在所有判定上**高度一致**（覆盖缺口、字腔判定、离群字集合均相同或成对出现）。

真正的独立票数因此是 **Ark + Zpix + Unifont = 3 票**，下文所有"≥2/3 套参考一致"的判定
都只用这三套里的 12px 字体（Ark / Zpix）或全部三套（Unifont 另算）。

### 选它们时踩过的坑

- **Cubic 11 不可得**：4 个候选 URL 全部 404（项目已改用 Fusion 缝合它）。
  所以"日系日系"之外的独立票只有 Zpix 与 Unifont，样本量受限，结论按"≥2/3 票"才采信。
- **必须用原生 ppem 渲染**：像素字体的轮廓是按自己的网格设计的，在别的字号下栅格化会重排笔画，
  那时的形状已经不是它"本来该有的样子"。因此 Ark/Fusion/Zpix 一律 12px、Unifont 一律 16px。
- **参考字体自身缺字**：Ark 缺 150 个（GB2312 后半的简体字），Zpix 缺 12 个
  （U+3094-3096 / 3099 / 309A / 309F / 30A0 / 30F7-30FF 等假名）。
  覆盖缺口是**参考字体的属性，不是本项目的缺陷**，报告中单列，不参与判定。

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

## 许可证义务

本仓库**不**分发这些字体二进制（不在版本控制里），只记录来源与校验和。
若将来把任一字体打进成品/分发包，需要同时满足：

- OFL-1.1（Ark / Fusion）：保留版权与许可证声明，随附 OFL 全文，不得单独售卖字体本身；
- MIT（Zpix）：保留版权与许可声明；
- GPL-2.0+ 字体嵌入例外（Unifont）：按例外条款随附声明即可。

## 相关文档

- 校验方法与结论：[`glyph-identity-verification.md`](glyph-identity-verification.md)
- 回归测试方法：[`regression.md`](regression.md)
