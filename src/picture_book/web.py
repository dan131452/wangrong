"""生成单文件网页阅读器：dist/绘本阅读器.html。

双击即可打开（file:// 直读），无任何外部依赖：两本绘本的页面图以 base64 内嵌，
支持书目切换、按钮 / 键盘方向键 / 触屏滑动翻页。
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from .build import cover_crop
from .story import CACHE_DIR, Book

WEB_RATIO = 16 / 10
WEB_MAX_W = 1280

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>数字绘本 · 三国故事</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #2b2622; min-height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 14px; padding: 18px;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif; color: #4a3a2e;
  }
  #tabs { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
  .tab {
    padding: 7px 22px; border-radius: 999px; border: 1px solid #6a5a48;
    color: #d8cbb8; background: rgba(255,255,255,0.04); cursor: pointer;
    font-size: 15px; letter-spacing: 2px; user-select: none; transition: all .2s;
  }
  .tab.active { background: #fef8ec; color: #6b3f2a; border-color: #fef8ec; font-weight: bold; }
  #stage {
    position: relative; width: min(96vw, calc((100vh - 130px) * 1.6));
    aspect-ratio: 16 / 10; border-radius: 14px; overflow: hidden;
    box-shadow: 0 18px 50px rgba(0,0,0,0.55); background: #000;
  }
  #pageImg { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
  .frame { position: absolute; inset: 10px; border: 2.4px solid rgba(254,248,236,0.75);
           border-radius: 10px; pointer-events: none; }
  .frame2 { position: absolute; inset: 17px; border: 1px solid rgba(120,100,80,0.45);
            border-radius: 8px; pointer-events: none; }
  #band {
    position: absolute; left: 0; right: 0; bottom: 0; padding: 14px 20px 18px;
    background: rgba(254,248,236,0.95); text-align: center;
  }
  #band h1 { font-size: clamp(20px, 3.2vw, 34px); color: #6b3f2a; letter-spacing: 6px; }
  #band p  { font-size: clamp(11px, 1.4vw, 14px); color: #9a8f82; margin-top: 6px; letter-spacing: 2px; }
  #card {
    position: absolute; left: 3.2%; bottom: 5.5%; width: min(46%, 560px);
    background: rgba(254,248,236,0.95); border-radius: 14px; padding: 18px 22px 22px;
    box-shadow: 0 10px 26px rgba(0,0,0,0.35);
  }
  #card h2 { font-size: clamp(15px, 2vw, 20px); color: #6b3f2a; margin: 0 0 8px 16px; }
  #card .bar { position: absolute; left: 10px; top: 20px; width: 5px; height: 24px;
               background: #c77c3a; border-radius: 3px; }
  #card p { font-size: clamp(12px, 1.55vw, 16px); line-height: 1.75; color: #4a3a2e; }
  #pageNum { position: absolute; right: 14px; bottom: 8px; font-size: 12px; color: #9a8f82; }
  #centerCard {
    position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
    width: min(64%, 560px); background: #fef8ec; border-radius: 14px;
    padding: 26px 30px; text-align: left; box-shadow: 0 10px 26px rgba(0,0,0,0.35);
  }
  #centerCard h2 { color: #6b3f2a; font-size: clamp(16px, 2.2vw, 21px); margin-bottom: 6px 0 6px 16px; }
  #centerCard .bar { position: absolute; left: 12px; top: 28px; width: 5px; height: 24px;
                     background: #c77c3a; border-radius: 3px; }
  #centerCard .div { color: #c77c3a; font-size: 11px; margin: 4px 0 10px; }
  #centerCard p { font-size: clamp(13px, 1.7vw, 16px); line-height: 1.8; color: #4a3a2e; }
  #centerCard .fin { text-align: center; color: #9a8f82; font-size: 12px; margin-top: 14px;
                     letter-spacing: 3px; }
  .nav {
    position: absolute; top: 50%; transform: translateY(-50%); width: 46px; height: 46px;
    border-radius: 50%; border: none; background: rgba(254,248,236,0.85); color: #6b3f2a;
    font-size: 22px; cursor: pointer; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 14px rgba(0,0,0,0.35); transition: transform .15s;
  }
  .nav:hover { transform: translateY(-50%) scale(1.1); }
  #prev { left: 14px; } #next { right: 14px; }
  #counter { color: #b7a894; font-size: 14px; letter-spacing: 2px; user-select: none; }
  #hint { color: #7d6f5e; font-size: 12px; user-select: none; }
</style>
</head>
<body>
<div id="tabs"></div>
<div id="stage">
  <img id="pageImg" alt="">
  <div class="frame"></div><div class="frame2"></div>
  <div id="band" style="display:none"><h1></h1><p></p></div>
  <div id="card" style="display:none"><div class="bar"></div><h2></h2><p></p><span id="pageNum"></span></div>
  <div id="centerCard" style="display:none"><div class="bar"></div><h2></h2><div class="div">◆</div><p></p><div class="fin">—— ◆ 完 ◆ ——</div></div>
  <button class="nav" id="prev">‹</button>
  <button class="nav" id="next">›</button>
</div>
<div id="counter"></div>
<div id="hint">← → 方向键 / 点击图片左右两侧 / 手机滑动 均可翻页</div>
<script>
var BOOKS = $BOOKS_JSON;
var curBook = 0, curPage = 0;
var stage = document.getElementById('stage');
var img = document.getElementById('pageImg');
var band = document.getElementById('band');
var card = document.getElementById('card');
var centerCard = document.getElementById('centerCard');
var tabs = document.getElementById('tabs');

BOOKS.forEach(function (b, i) {
  var t = document.createElement('div');
  t.className = 'tab'; t.textContent = b.title;
  t.onclick = function () { curBook = i; curPage = 0; render(); };
  tabs.appendChild(t);
});

function render() {
  var b = BOOKS[curBook], p = b.pages[curPage];
  img.src = p.img;
  band.style.display = 'none'; card.style.display = 'none'; centerCard.style.display = 'none';
  if (p.kind === 'cover') {
    band.style.display = 'block';
    band.querySelector('h1').textContent = p.title;
    band.querySelector('p').textContent = b.subtitle;
  } else if (p.kind === 'back') {
    centerCard.style.display = 'block';
    centerCard.querySelector('h2').textContent = p.title;
    centerCard.querySelector('p').textContent = p.text;
  } else {
    card.style.display = 'block';
    card.querySelector('h2').textContent = p.title;
    card.querySelector('p').textContent = p.text;
    document.getElementById('pageNum').textContent = '· ' + p.no + ' ·';
  }
  document.getElementById('counter').textContent = (curPage + 1) + ' / ' + b.pages.length;
  Array.prototype.forEach.call(tabs.children, function (t, i) {
    t.className = (i === curBook) ? 'tab active' : 'tab';
  });
}

function go(d) {
  var n = BOOKS[curBook].pages.length;
  curPage = (curPage + d + n) % n;
  render();
}
document.getElementById('prev').onclick = function () { go(-1); };
document.getElementById('next').onclick = function () { go(1); };
document.addEventListener('keydown', function (e) {
  if (e.key === 'ArrowLeft') go(-1);
  if (e.key === 'ArrowRight') go(1);
});
stage.addEventListener('click', function (e) {
  if (e.target.className === 'nav') return;
  var x = e.clientX - stage.getBoundingClientRect().left;
  if (x < stage.offsetWidth * 0.35) go(-1);
  else if (x > stage.offsetWidth * 0.65) go(1);
});
var tx = null;
stage.addEventListener('touchstart', function (e) { tx = e.touches[0].clientX; });
stage.addEventListener('touchend', function (e) {
  if (tx === null) return;
  var dx = e.changedTouches[0].clientX - tx;
  if (Math.abs(dx) > 40) go(dx > 0 ? -1 : 1);
  tx = null;
});
render();
</script>
</body>
</html>
"""

# stage 点击会命中导航按钮的父级判断：nav 在 stage 内，click 冒泡到 stage；
# e.target.className === 'nav' 时跳过，按钮自身 onclick 已处理。


def _web_image(src: Path, cache_name: str) -> str:
    """裁成 16:10、压到 1280 宽，返回 data URI（JPEG）。"""
    from PIL import Image

    cropped = cover_crop(src, CACHE_DIR / cache_name, WEB_RATIO)
    img = Image.open(cropped)
    if img.width > WEB_MAX_W:
        img = img.resize((WEB_MAX_W, int(img.height * WEB_MAX_W / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def build_web(books: list[Book], images_by_book: dict[str, dict[int, Path]], out_path: Path) -> None:
    payload = []
    for book in books:
        images = images_by_book[book.id]
        pages = [
            {
                "no": p.no,
                "kind": p.kind,
                "title": p.title,
                "text": p.text or "",
                "img": _web_image(images[p.no], f"{book.id}-p{p.no:02d}-web.jpg"),
            }
            for p in book.pages
        ]
        payload.append({"id": book.id, "title": book.title, "subtitle": book.subtitle, "pages": pages})

    html = TEMPLATE.replace("$BOOKS_JSON", json.dumps(payload, ensure_ascii=False))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"WEB : {out_path}（{len(payload)} 本 / {sum(len(b['pages']) for b in payload)} 页 / {size_mb:.1f} MB）")
