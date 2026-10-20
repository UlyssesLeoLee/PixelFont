"""语种覆盖体检 —— 中日英三语字体的第一性问题: 缺字。

我先前渲染「开始游戏」时最后一个字变成豆腐块, 说明 MS Gothic 只有 JIS 汉字、没有简体。
像素字体格子极少, 缺字无法像矢量字体那样回退, 所以源字体的覆盖范围必须在设计阶段就查清。

方法: 用 FreeType 的 cmap 直接查, 而不是靠"渲染出来像不像豆腐块"猜。
"""

from __future__ import annotations

from functools import lru_cache

from fontTools.ttLib import TTFont, TTCollection  # type: ignore

PROBES = {
    "简体中文": "开始游戏金币买卖国语学习时间电脑游戏开始新世界攻击画面选择确认退出设置声音效果继续暂停战斗等级经验装备武器技能职业任务剧情结局动画帧率延迟服务器客户端数据库网络连接成功失败错误警告提示",
    "日本語": "日本語あいうえおかきくけこサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン.game start ゲームデータプレイヤー",
    "ASCII": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_=+[]{};:,.<>/?",
}

FONTS = {
    "MS Gothic": (r"C:\Windows\Fonts\msgothic.ttc", 0),
    "MS Mincho": (r"C:\Windows\Fonts\msmincho.ttc", 0),
    "SimSun (新宋体)": (r"C:\Windows\Fonts\simsun.ttc", 0),
    "SimHei (黑体)": (r"C:\Windows\Fonts\simhei.ttf", None),
    "Microsoft YaHei": (r"C:\Windows\Fonts\msyh.ttc", 0),
    "Meiryo": (r"C:\Windows\Fonts\meiryo.ttc", 0),
    "BIZ UDMincho": (r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc", 0),
    "Yu Gothic": (r"C:\Windows\Fonts\YuGothM.ttc", 0),
}


@lru_cache(maxsize=32)
def cmap_for(path: str, index: int = 0) -> frozenset[int]:
    """带缓存的 cmap 查询 —— 缺字门禁会对每个候选逐字符调用它。"""
    if path.lower().endswith(".ttc"):
        font = TTCollection(path).fonts[index or 0]
    else:
        font = TTFont(path, fontNumber=index or 0)
    cps: set[int] = set()
    for table in font["cmap"].tables:
        cps.update(table.cmap.keys())
    return frozenset(cps)


def cmap_set(path: str, index: int | None) -> set[int]:
    return set(cmap_for(path, index or 0))


def main() -> None:
    probes = {k: v for k, v in PROBES.items()}
    print(f"{'font':<20}" + "".join(f"{k:<12}" for k in probes))
    for name, (path, idx) in FONTS.items():
        try:
            cps = cmap_set(path, idx)
        except Exception as e:  # noqa: BLE001
            print(f"{name:<20} ERROR {e}")
            continue
        row = f"{name:<20}"
        for _, text in probes.items():
            missing = [c for c in text if ord(c) not in cps]
            pct = 100.0 * (len(text) - len(missing)) / len(text)
            row += f"{pct:5.1f}% ({len(missing):>2})  "
        print(row)


if __name__ == "__main__":
    main()
