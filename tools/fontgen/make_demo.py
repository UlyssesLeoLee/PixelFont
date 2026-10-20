"""生成浏览器对照页 demo。

左边是**设计意图**（直接用图集位图画出来, 由 BDF/图集回读校验过）,
右边是**浏览器渲染的 TTF 文字**。两者并排, 肉眼就能看出渲染器有没有
在小字号下加粗/错位 —— 这比任何自说自话的校验都有说服力。

图集元数据直接内嵌成 JS 数组, 因为 file:// 下 fetch 本地 JSON 会被 CORS 拦掉。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from charset import build_charset, build_stack  # noqa: E402
from sheet import COPY_LINES  # noqa: E402

OUTDIR = Path(__file__).resolve().parents[2] / "dist"
PS = "PixelFontPC98-12"

TEST_LINES = [
    "中日語漢字画面攻撃",
    "あアカヲンソツ",
    "ABCDEFGHIJ 0123456789",
    *COPY_LINES,
]


def main() -> None:
    atlas_json = json.loads((OUTDIR / f"{PS}-atlas.json").read_text(encoding="utf-8"))
    lut = {m[0]: m for m in atlas_json["glyphs"]}
    cell_w, cell_h = atlas_json["cell"]["w"], atlas_json["cell"]["h"]

    js_lut = {chr(cp): [m[1], m[2], m[3]] for cp, m in lut.items() if cp <= 0xFFFF}
    text_lines = json.dumps(TEST_LINES, ensure_ascii=False)

    html = f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<title>{PS} — 渲染对照</title>
<style>
  @font-face {{
    font-family: "PixelFontPC98";
    src: url("./{PS}.ttf") format("truetype");
    font-display: block;
  }}
  html, body {{ margin:0; background:#0e1016; color:#f2ede3;
    font-family: "Microsoft YaHei", sans-serif; }}
  .wrap {{ padding: 28px 32px; }}
  h2 {{ font-size: 15px; color:#93a1b5; margin: 26px 0 8px; font-weight: 600;
        letter-spacing:.04em; }}
  .note {{ font-size: 12px; color:#6c7688; line-height:1.7; margin: 0 0 6px; }}
  canvas {{ display:block; image-rendering: pixelated; background:#1a1f2b;
            border:1px solid #2e3648; border-radius:3px; }}
  .tru {{ font-family: "PixelFontPC98"; -webkit-font-smoothing: none;
          font-smooth: never; text-rendering: geometricPrecision;
          font-kerning: none; white-space: pre; }}
  .s12 {{ font-size: 12px; }}
  .s24 {{ font-size: 24px; }}
  .s48 {{ font-size: 48px; }}
  .rows {{ display:grid; grid-template-columns: auto auto; gap:10px 26px;
          align-items:start; }}
</style>
<div class="wrap">
  <h2>1 · 设计意图（图集位图, 4× 最近邻放大）</h2>
  <p class="note">这一列直接从 {PS}-atlas.png 按元数据绘制, 与 BDF / TTF 字形数据同源,
     并已通过 4140 字形逐像素回读校验。它是"这本字体应该长什么样"的唯一权威答案。</p>
  <canvas id="truth"></canvas>

  <h2>2 · 浏览器渲染 TTF · 12px（实际使用尺寸）</h2>
  <p class="note">Chrome 会做字体平滑; 已用 -webkit-font-smoothing:none 关闭灰度抗锯齿。
     若这里与第 1 节一致, 说明 TTF 在浏览器里可正常使用。</p>
  <div class="tru s12" id="t12"></div>

  <h2>3 · 浏览器渲染 TTF · 48px（4× 放大, 便于逐像素核对）</h2>
  <div class="tru s48" id="t48"></div>

  <h2>4 · Chrome 在 12px 的真实栅格化结果（Skia 渲染后 6× 最近邻放大）</h2>
  <p class="note">这一栏不是 CSS 放大：先用 Chrome 把文字按 12px 真实栅格化成位图，
     再用 image-rendering:pixelated 放大 6 倍。所以看到的就是本字体在设计尺寸下
     逐像素的样子，可与第 1 节逐行对照。</p>
  <canvas id="raster12"></canvas>

  <h2>5 · 并排核对：12px 位图（atlas） vs 12px 浏览器栅格化</h2>
  <div class="rows">
    <div>
      <p class="note">atlas 位图（权威）</p>
      <canvas id="cmpA"></canvas>
    </div>
    <div>
      <p class="note">Chrome 12px 栅格化</p>
      <canvas id="cmpB"></canvas>
    </div>
  </div>
</div>
<script>
const CELL_W = {cell_w}, CELL_H = {cell_h};
const LUT = {json.dumps(js_lut, ensure_ascii=False)};
const LINES = {text_lines};
const atlas = new Image();
atlas.src = "./{PS}-atlas.png";

function drawAtlas(canvas, scale, text) {{
  // 先按"缩放后的单位"推进, 再一次性设画布尺寸 —— 反过来写会把所有字叠在一起
  const placed = [];
  let w = 0;
  for (const ch of text) {{
    const e = LUT[ch];
    if (!e) continue;
    placed.push([ch, e, w]);
    w += (e[2] + 1) * scale;
  }}
  canvas.width = w;
  canvas.height = CELL_H * scale;
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  for (const [ch, e, x] of placed) {{
    ctx.drawImage(atlas, e[0], e[1], CELL_W, CELL_H,
                  x, 0, CELL_W * scale, CELL_H * scale);
  }}
}}

function drawRaster12(canvas, scale, lines) {{
  // 关键: 先按 12px 真实渲染到中间画布, 再最近邻放大。
  // 直接用 CSS 放大文字会被 Chrome 重新矢量渲染, 看不到真实的小字号栅格化结果。
  const mid = document.createElement("canvas");
  const mctx = mid.getContext("2d");
  mctx.font = '12px "PixelFontPC98"';
  mctx.textBaseline = "alphabetic";
  let w = 0;
  const lines12 = [];
  for (const line of lines) {{
    const lw = Math.ceil(mctx.measureText(line).width);
    lines12.push([line, w]);
    w = Math.max(w, lw);
  }}
  const lh = CELL_H;
  mid.width = w + 2;
  mid.height = lh * lines12.length;
  mctx.font = '12px "PixelFontPC98"';
  mctx.fillStyle = "#fff";
  for (const [line, x] of lines12) {{
    mctx.fillText(line, 1, lh * (lines12.indexOf(lines12.find(l => l[0] === line)) + 1) - 2);
  }}
  canvas.width = mid.width * scale;
  canvas.height = mid.height * scale;
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(mid, 0, 0, canvas.width, canvas.height);
}}

function ready() {{
  drawAtlas(document.getElementById("truth"), 4, LINES[3] || LINES[0]);
  drawAtlas(document.getElementById("cmpA"), 6, LINES[0]);
  document.fonts.ready.then(() => {{
    drawRaster12(document.getElementById("raster12"), 6, [LINES[0]]);
    const src = document.getElementById("raster12");
    const dst = document.getElementById("cmpB");
    dst.width = src.width; dst.height = src.height;
    const c = dst.getContext("2d");
    c.imageSmoothingEnabled = false;
    c.drawImage(src, 0, 0);
  }});
}}
if (atlas.complete && atlas.naturalWidth) ready();
else atlas.onload = ready;
for (const id of ["t12", "t48"]) {{
  document.getElementById(id).textContent = LINES.join("\\n");
}}
</script>
</html>
"""
    path = OUTDIR / f"{PS}-demo.html"
    path.write_text(html, encoding="utf-8")
    print(path)
    print(f"  ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
