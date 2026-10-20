# 回归测试流程 (PixelFont)

本项目的回归测试不是"跑一次构建看有没有报错", 而是**分批抽样 + 四路交叉对比 + 异常检测**。
理由: 像素字体的失败模式大多是**静默**的 —— 一个字被裁掉半边、一个字宽标错、
一个字符块的 ENDCHAR 多写一个, 字体照样能被字体加载器打开, 只有逐像素对比才看得出来。

## 为什么"四路交叉对比"是必须的

同一个字形, 用四条**互相独立**的路径取出来, 必须得到同一张位图:

| 路径 | 来源 | 独立在哪 |
|---|---|---|
| R | 栅格化器现场渲染 (`bitfont.BitmapFont.glyph`) | 源头 |
| B | 从成品 BDF 重新解析 (`build_font.verify_bdf` 同款解析) | 写文件 + 读文件 |
| T | 从成品 TTF 轮廓反解像素 (`fontTools` 轮廓 -> 格) | 轮廓 + 整数缩放 |
| A | 从成品 PNG 图集 + 元数据解码 | 位图 + 元数据 |

只对比"成品 vs 源位图"是**自证**: 源位图错了, 成品跟着错, 校验照样通过。
R/B/T/A 互相对照, 任何一路写坏或读错都会暴露。

## 覆盖到的异常类型

| ID | 含义 |
|---|---|
| `CLIP_RIGHT` / `CLIP_BOTTOM` | 源字形超出分配到的 cell, 墨迹被裁 |
| `SOURCE_ADVANCE_MISMATCH` | 源字体实测 advance 与分配格宽不符 (裁剪的根因信号) |
| `EMPTY_INK` | 非空白字符没有墨迹 (缺字/豆腐块) |
| `MISMATCH_BDF` / `MISMATCH_TTF` / `MISMATCH_ATLAS` | 四路交叉对比不一致 |
| `ATLAS_WIDE_MISMATCH` | 图集 `isWide` 标记与实际 advance 不符 |
| `ADVANCE_MISMATCH` / `BBX_MISMATCH` / `TTF_LSB_MISMATCH` | 成品表结构与源数据不一致 |
| `BDF_STRUCTURE` | BDF 字符块结构损坏 (ENDCHAR 配对 / 行数 / 填充位) |
| `CMAP_MISSING` / `BDF_MISSING` / `ATLAS_MISSING` | 成品缺字 |
| `DENSITY_OUTLIER` | 单字墨量远离全字符集参考分布 (用 median+MAD, 不用 mean+std) |
| `BASELINE_DRIFT` | 整批墨迹垂直范围偏离参考中位 (系统性错位信号) |
| `DUPLICATE_BITMAP` | 不同码位共享同一位图 (**info 级**: 字体里合法) |

## 分批抽样

字符集按类别 (ascii / punct / kana / hanzi) 切开, 再按固定批量切批。
每批统计墨量中位、墨量最高、墨迹垂直范围、全角比例、空墨迹数, 与**全字符集参考分布**对比找离群批。
单个字符的问题会被批统计放大成"这一整批不对劲", 便于定位到路由/字号层面的系统性错误。

## 判定不许撒谎

- 没测到东西 (输入为空 / 构建失败) -> 判定 `NO_DATA` 或 `BUILD_FAILED`, **绝不用 PASS 冒充**
- 报告里同时给出"消费了多少输入"和"消费失败了多少" —— 只给结论的分不清"没东西"和"都没问题"
- 量具自检: `python tools/fontgen/regress.py --selftest` 会注入 6 类已知坏数据 + 16 条纯规则,
  断言每个检测器确实会响。**没跑过自检的回归结果不构成证据**。

## 用法

```powershell
# 单批次
python tools/fontgen/regress.py --cats ascii,punct --batch-size 100 --out reports/ascii-punct.json

# 汉字前半 / 后半
python tools/fontgen/regress.py --cats hanzi --slice 0:1900   --out reports/hanzi-a.json
python tools/fontgen/regress.py --cats hanzi --slice 1900:3755 --out reports/hanzi-b.json

# 全量
python tools/fontgen/regress.py --out reports/all.json

# 量具自检
python tools/fontgen/regress.py --selftest
```

每次运行会先真实执行一次 `build_font.py` (生产构建路径, 包含它自己的回读门禁),
再对产物做四路对比。`--skip-build` 可以复用现有 `dist/`, 迭代时更快。

输出成对: `<out>` (JSON, 机器读) + `<out>.md` (人读摘要)。两者是同一份数据的两种渲染。

## 并行 lane 约定

多 Agent 并行跑回归时, **每条 lane 独占自己的批次与文件路径**, 不要并行改同一份源码:

| lane | 批次 | 独占路径 |
|---|---|---|
| A | ascii + punct | `reports/ascii-punct*`, `tools/fontgen/lanes/ascii_punct_probe.py` |
| B | kana | `reports/kana*`, `tools/fontgen/lanes/kana_probe.py` |
| C | hanzi 前 1900 | `reports/hanzi-a*`, `tools/fontgen/lanes/hanzi_a_probe.py` |
| D | hanzi 后 1855 + 成品结构 | `reports/hanzi-b*`, `tools/fontgen/lanes/hanzi_b_probe.py` |

**共享源码 (`tools/fontgen/{bitfont,charset,build_font,coverage,regress}.py`) 只有集成者能改。**
lane 发现源码级缺陷时, 写证据 (文件:行号 + 最小复现 + ASCII art) 进报告, 由集成者集中修 ——
否则 4 条 lane 并行改同一份源码必然互相冲突。

lane 完成后: 各 lane 分支 rebase 到 `dev`, 再 merge 进 `dev`。
