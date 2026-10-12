"""本地 AIGC 绘本生成器：uv run picture-book serve [--port 8765] [--demo]。

浏览器打开后：选择故事 -> 点击「生成绘本」-> 逐页观察生成进度 -> 阅读成品。
--demo 演示模式：不调用真实 API，用占位图模拟逐页生成（课堂演示/离线可用）。
真实模式调用 .env 配置的生图 API，已存在的页面自动跳过。
仅用标准库，无新增依赖。
"""

from __future__ import annotations

import json
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import gen
from .build import cover_crop
from .story import CACHE_DIR, load_book, load_books

APP_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>三国演义 · AIGC 绘本生成器</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  /* 宣纸底：米色为基，叠一层细颗粒纤维纹理 */
  body { min-height:100vh; color:#2f2a24;
    font-family:"Songti SC","STSong","KaiTi","楷体","SimSun","宋体",serif;
    background-color:#e7dcc4;
    background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='p'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='160' height='160' filter='url(%23p)' opacity='0.16'/></svg>"); }
  #app { max-width:1180px; margin:0 auto; padding:28px 20px 60px; }
  /* ---------- 首页 ---------- */
  .hero { text-align:center; padding:34px 0 26px; }
  .hero .seal { display:inline-block; background:#9e2b25; color:#f6f0e2; font-size:13px;
    letter-spacing:6px; padding:5px 16px 5px 22px; border-radius:2px;
    box-shadow:inset 0 0 0 1px rgba(246,240,226,.5); }
  .hero h1 { color:#2f2a24; font-size:clamp(26px,4vw,40px); font-weight:normal;
    letter-spacing:10px; margin:16px 0 8px; }
  .hero h1::after { content:''; display:block; width:210px; margin:16px auto 0;
    border-top:1px solid #b9a887; border-bottom:1px solid #b9a887; height:3px; }
  .hero p { color:#7a6f5c; font-size:14px; letter-spacing:2px; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:22px; margin-top:26px; }
  .bcard { position:relative; border-radius:2px; overflow:hidden; cursor:pointer;
    border:1px solid #b9a887; transition:border-color .18s; min-height:210px; }
  .bcard img { width:100%; height:100%; object-fit:cover; position:absolute; inset:0;
    filter:sepia(.24) brightness(.84) contrast(.96); transition:filter .18s; }
  .bcard .meta { position:absolute; inset:0; padding:20px; display:flex; flex-direction:column;
    justify-content:flex-end;
    background:linear-gradient(transparent 34%,rgba(31,28,24,.52) 58%,rgba(31,28,24,.94)); }
  .bcard h3 { color:#f6f0e2; font-size:22px; font-weight:normal; letter-spacing:5px; }
  .bcard .sub { color:#cdbfa6; font-size:12px; margin:6px 0 10px; letter-spacing:1px; }
  .bcard .desc { color:#e8ddc8; font-size:13px; line-height:1.7; display:-webkit-box;
    -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
  .bcard .pages { position:absolute; top:14px; right:14px; background:rgba(31,28,24,.72);
    color:#e8ddc8; font-size:12px; padding:3px 10px; border-radius:2px; }
  .bcard.sel { border-color:#9e2b25; outline:1px solid #9e2b25; outline-offset:3px; }
  .bcard.sel img { filter:sepia(.08) brightness(1); }
  .bcard.sel .tick { position:absolute; top:12px; left:12px; width:26px; height:26px; border-radius:2px;
    background:#9e2b25; color:#f6f0e2; font-size:16px; display:flex; align-items:center; justify-content:center; }
  .actions { text-align:center; margin-top:34px; }
  .btn { border:none; cursor:pointer; border-radius:2px; font-family:inherit; transition:all .18s; }
  .btn-main { background:#9e2b25; color:#f6f0e2; font-size:18px; letter-spacing:6px;
    padding:15px 58px; box-shadow:inset 0 0 0 1px rgba(246,240,226,.45); }
  .btn-main:not(:disabled):hover { background:#8a231e; }
  .btn-main:disabled { opacity:.3; cursor:not-allowed; }
  .btn-ghost { background:transparent; color:#6f6555; border:1px solid #b9a887; font-size:14px;
    letter-spacing:2px; padding:10px 26px; margin:0 6px; }
  .btn-ghost:hover { color:#9e2b25; border-color:#9e2b25; }
  .hint { text-align:center; color:#8b7f6a; font-size:12px; margin-top:14px; letter-spacing:1px; }
  .demo-tag { display:inline-block; margin-left:8px; background:#b8963f; color:#3a2f18;
    font-size:11px; padding:2px 10px; border-radius:2px; letter-spacing:2px; vertical-align:middle; }
  /* ---------- 生成视图 ---------- */
  #viewGen .top { display:flex; align-items:center; gap:16px; margin:10px 0 20px; }
  #viewGen h2 { color:#2f2a24; font-size:20px; font-weight:normal; letter-spacing:4px; }
  .bar { flex:1; height:8px; background:#d6c9ad; border:1px solid #b9a887; border-radius:0; overflow:hidden; }
  .bar i { display:block; height:100%; width:0; background:#9e2b25; transition:width .4s; }
  .pct { color:#9e2b25; font-size:14px; min-width:64px; text-align:right; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(132px,1fr)); gap:14px; }
  .cell { position:relative; border-radius:2px; overflow:hidden; aspect-ratio:16/11;
    background:#d6c9ad; border:1px solid #b9a887; }
  .cell img { width:100%; height:100%; object-fit:cover; opacity:.3; transition:opacity .4s;
    filter:sepia(.3) contrast(.94); }
  .cell.done img { opacity:1; filter:sepia(.06) contrast(1); }
  .cell .no { position:absolute; top:6px; left:8px; color:#f6f0e2; font-size:11px;
    text-shadow:0 1px 3px rgba(0,0,0,.85); }
  .cell .st { position:absolute; right:6px; top:5px; font-size:13px; }
  .cell.done { border-color:#6f7d55; }
  .cell.generating { border-color:#b8963f; }
  .cell.failed { border-color:#9e2b25; }
  .cell.failed img { opacity:.22; }
  .spin { width:15px; height:15px; border:2px solid #b8963f; border-top-color:transparent;
    border-radius:50%; animation:r 0.8s linear infinite; display:inline-block; }
  @keyframes r { to { transform:rotate(360deg); } }
  .cell .cap { position:absolute; bottom:0; left:0; right:0; padding:4px 8px; font-size:11px;
    color:#e8ddc8; background:linear-gradient(transparent,rgba(31,28,24,.88));
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  #genActions { text-align:center; margin-top:28px; }
  #log { color:#7a6f5c; font-size:12px; text-align:center; margin-top:16px; min-height:18px; }
  /* ---------- 阅读视图 ---------- */
  #viewRead { max-width:1280px; margin:0 auto; }
  .rhead { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }
  .rhead h2 { color:#2f2a24; font-size:18px; font-weight:normal; letter-spacing:4px; }
  .spread { display:flex; border-radius:2px; overflow:hidden; border:1px solid #b9a887;
    box-shadow:0 6px 22px rgba(60,48,30,.22); min-height:min(66vh,560px); }
  .imgSide { flex:1.55; position:relative; background:#1f1c18; }
  .imgSide img { width:100%; height:100%; object-fit:cover; display:block; }
  .imgSide .frame { position:absolute; inset:10px; border:1px solid rgba(246,240,226,.62);
    border-radius:0; pointer-events:none; }
  .nav { position:absolute; top:50%; transform:translateY(-50%); width:42px; height:42px; border:none;
    border-radius:2px; background:rgba(246,240,226,.88); color:#2f2a24; font-size:20px; cursor:pointer; }
  .nav:hover { background:#f6f0e2; color:#9e2b25; }
  #rPrev { left:12px; } #rNext { right:12px; }
  /* 书页：浅米色纸面，左侧一道朱砂竖线 */
  .panel { flex:1; background:#f2ead6; padding:34px 32px 24px; display:flex; flex-direction:column;
    position:relative; border-left:1px solid #cdbfa6; }
  .panel .bar-deco { position:absolute; left:18px; top:40px; width:4px; height:30px;
    background:#9e2b25; border-radius:0; }
  .panel h3 { color:#5a3a24; font-size:clamp(19px,2.2vw,24px); font-weight:normal;
    margin:0 0 4px 20px; letter-spacing:3px; }
  .panel .chap { color:#8b7f6a; font-size:12px; letter-spacing:3px; margin:0 0 14px 20px; }
  .panel .body { flex:1; overflow-y:auto; color:#3a332a; font-size:clamp(14px,1.6vw,17px);
    line-height:2.1; padding-right:6px; }
  .panel .fin { text-align:center; color:#8b7f6a; font-size:12px; letter-spacing:4px; margin:14px 0 4px; }
  .panel .div { color:#9e2b25; font-size:11px; margin:2px 0 10px 20px; }
  .rfoot { display:flex; justify-content:space-between; align-items:center; margin-top:14px; }
  .rcount { color:#7a6f5c; font-size:14px; letter-spacing:3px; }
  .coverPanel { justify-content:center; }
  .coverPanel .bigtitle { color:#5a3a24; font-size:clamp(30px,4vw,44px); letter-spacing:12px;
    margin:10px 0 12px 20px; font-weight:normal; }
  @media (max-width:860px) {
    .spread { flex-direction:column; }
    .imgSide { min-height:300px; }
    .panel { padding:22px 20px; }
  }
  .hidden { display:none !important; }
</style>
</head>
<body>
<div id="app">

  <div id="viewHome">
    <div class="hero">
      <span class="seal">AIGC</span><span class="demo-tag hidden" id="demoTag">演示模式</span>
      <h1>三国演义 · 绘本生成器</h1>
      <p>选择一个故事，点击生成，看 AI 把它变成一本数字绘本</p>
    </div>
    <div class="cards" id="cards"></div>
    <div class="actions">
      <button class="btn btn-main" id="goGen" disabled>✦ 生 成 绘 本</button>
    </div>
    <div class="hint">生成调用本地服务与生图 API · 已有插画的页面会自动跳过 · 生成完可直接阅读</div>
  </div>

  <div id="viewGen" class="hidden">
    <div class="top">
      <h2 id="genTitle"></h2>
      <div class="bar"><i id="barFill"></i></div>
      <span class="pct" id="pct">0%</span>
    </div>
    <div class="grid" id="grid"></div>
    <div id="log"></div>
    <div id="genActions" class="hidden">
      <button class="btn btn-main" id="goRead">开 始 阅 读</button>
      <button class="btn btn-ghost" id="retryFailed">重试失败页</button>
      <button class="btn btn-ghost" id="backHome1">返回选择</button>
    </div>
  </div>

  <div id="viewRead" class="hidden">
    <div class="rhead">
      <h2 id="rTitle"></h2>
      <button class="btn btn-ghost" id="backHome2">← 返回生成器</button>
    </div>
    <div class="spread">
      <div class="imgSide">
        <img id="rImg" alt="">
        <div class="frame"></div>
        <button class="nav" id="rPrev">‹</button>
        <button class="nav" id="rNext">›</button>
      </div>
      <div class="panel" id="rPanel"></div>
    </div>
    <div class="rfoot">
      <span class="rcount" id="rCount"></span>
      <span class="rcount">← → 翻页</span>
    </div>
  </div>

</div>
<script>
var BOOKS = [], selBook = null, curPage = 0, pollTimer = null, jobBook = null;

function $(id) { return document.getElementById(id); }
function show(view) {
  ['viewHome','viewGen','viewRead'].forEach(function (v) { $(v).classList.add('hidden'); });
  $(view).classList.remove('hidden');
}

/* ---------- 首页 ---------- */
function loadBooks() {
  fetch('/api/books').then(function (r) { return r.json(); }).then(function (bs) {
    BOOKS = bs;
    var wrap = $('cards');
    wrap.innerHTML = '';
    bs.forEach(function (b) {
      var c = document.createElement('div');
      c.className = 'bcard';
      c.innerHTML = '<img src="/api/page/' + b.id + '/1.jpg">' +
        '<span class="pages">' + b.pages.length + ' 页</span><span class="tick hidden">✓</span>' +
        '<div class="meta"><h3>' + b.title + '</h3><div class="sub">' + b.subtitle + '</div>' +
        '<div class="desc">' + (b.pages[1] ? b.pages[1].text : '') + '</div></div>';
      c.onclick = function () {
        selBook = b.id;
        Array.prototype.forEach.call(wrap.children, function (x) {
          x.classList.remove('sel'); x.querySelector('.tick').classList.add('hidden');
        });
        c.classList.add('sel'); c.querySelector('.tick').classList.remove('hidden');
        $('goGen').disabled = false;
      };
      wrap.appendChild(c);
    });
    if (bs.length && bs[0].demo) { $('demoTag').classList.remove('hidden'); }
  });
}

/* ---------- 生成 ---------- */
function startGen() {
  fetch('/api/generate', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ book: selBook }) })
    .then(function (r) { return r.json(); })
    .then(function (res) {
      if (res.error) { alert(res.error); return; }
      jobBook = selBook;
      var b = bookById(jobBook);
      $('genTitle').textContent = '《' + b.title + '》· 生成中';
      $('genActions').classList.add('hidden');
      var g = $('grid'); g.innerHTML = '';
      b.pages.forEach(function (p) {
        var d = document.createElement('div');
        d.className = 'cell'; d.id = 'cell' + p.no;
        d.innerHTML = '<img src="/api/page/' + b.id + '/' + p.no + '.jpg">' +
          '<span class="no">P' + p.no + '</span><span class="st"></span>' +
          '<div class="cap">' + p.title + '</div>';
        g.appendChild(d);
      });
      show('viewGen');
      poll();
    });
}
function poll() {
  clearInterval(pollTimer);
  pollTimer = setInterval(function () {
    fetch('/api/job').then(function (r) { return r.json(); }).then(function (j) {
      var total = j.pages.length, done = 0, failed = 0;
      j.pages.forEach(function (p) {
        var cell = $('cell' + p.no);
        if (!cell) return;
        cell.className = 'cell ' + (p.status === 'done' ? 'done' :
          p.status === 'generating' ? 'generating' : p.status === 'failed' ? 'failed' : '');
        var st = cell.querySelector('.st');
        st.innerHTML = p.status === 'done' ? '<span style="color:#6f7d55">✓</span>' :
          p.status === 'generating' ? '<span class="spin"></span>' :
          p.status === 'failed' ? '<span style="color:#c0533f">✗</span>' : '';
        if (p.status === 'done') done++;
        if (p.status === 'failed') failed++;
      });
      var pct = total ? Math.round(done / total * 100) : 0;
      $('barFill').style.width = pct + '%';
      $('pct').textContent = pct + '%';
      $('log').textContent = j.running ? '正在生成第 ' + (done + (failed ? 0 : 0) + 1 > total ? total : done + 1) + ' 页 …' :
        failed ? '完成：' + done + ' 页成功，' + failed + ' 页失败' : '全部生成完成！';
      if (!j.running) {
        clearInterval(pollTimer);
        $('genTitle').textContent = '《' + bookById(j.book).title + '》· ' + (failed ? '部分完成' : '生成完成');
        $('goRead').disabled = false;
        $('retryFailed').style.display = failed ? '' : 'none';
        $('genActions').classList.remove('hidden');
      }
    });
  }, 600);
}
function retryFailedPages() {
  fetch('/api/retry', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ book: jobBook }) })
    .then(function () { $('genActions').classList.add('hidden'); poll(); });
}

/* ---------- 阅读 ---------- */
function bookById(id) {
  for (var i = 0; i < BOOKS.length; i++) if (BOOKS[i].id === id) return BOOKS[i];
  return BOOKS[0];
}
function openReader(bookId) {
  var b = bookById(bookId);
  $('rTitle').textContent = '《' + b.title + '》';
  curPage = 0;
  show('viewRead');
  renderPage();
}
function renderPage() {
  var b = bookById(jobBook || selBook), p = b.pages[curPage];
  $('rImg').src = '/api/page/' + b.id + '/' + p.no + '.jpg?v=' + Date.now();
  var panel = $('rPanel');
  if (p.kind === 'cover') {
    panel.className = 'panel coverPanel';
    panel.innerHTML = '<div class="bar-deco"></div><div class="chap">AIGC 数字绘本</div>' +
      '<div class="bigtitle">' + p.title + '</div><div class="chap" style="margin-left:20px">' + b.subtitle + '</div>';
  } else if (p.kind === 'back') {
    panel.className = 'panel';
    panel.innerHTML = '<div class="bar-deco"></div><h3>' + p.title + '</h3><div class="div">◆</div>' +
      '<div class="body">' + p.text + '</div><div class="fin">—— ◆ 完 ◆ ——</div>';
  } else {
    panel.className = 'panel';
    panel.innerHTML = '<div class="bar-deco"></div><h3>' + p.title + '</h3>' +
      '<div class="chap">第 ' + p.no + ' 页 · ' + b.title + '</div>' +
      '<div class="body">' + p.text + '</div>';
  }
  $('rCount').textContent = (curPage + 1) + ' / ' + b.pages.length;
}
function rGo(d) {
  var b = bookById(jobBook || selBook), n = b.pages.length;
  curPage = (curPage + d + n) % n;
  renderPage();
}

$('goGen').onclick = startGen;
$('goRead').onclick = function () { openReader(jobBook); };
$('retryFailed').onclick = retryFailedPages;
$('backHome1').onclick = function () { clearInterval(pollTimer); show('viewHome'); };
$('backHome2').onclick = function () { show('viewHome'); };
$('rPrev').onclick = function () { rGo(-1); };
$('rNext').onclick = function () { rGo(1); };
document.addEventListener('keydown', function (e) {
  if ($('viewRead').classList.contains('hidden')) return;
  if (e.key === 'ArrowLeft') rGo(-1);
  if (e.key === 'ArrowRight') rGo(1);
});
loadBooks();
</script>
</body>
</html>
"""


class Job:
    """一次生成任务的状态（线程安全由 LOCK 保证）。"""

    def __init__(self) -> None:
        self.running = False
        self.book: str | None = None
        self.demo = False
        self.pages: list[dict] = []

    def snapshot(self) -> dict:
        done = sum(1 for p in self.pages if p["status"] == "done")
        failed = sum(1 for p in self.pages if p["status"] == "failed")
        return {
            "running": self.running,
            "book": self.book,
            "demo": self.demo,
            "total": len(self.pages),
            "done": done,
            "failed": failed,
            "pages": list(self.pages),
        }


JOB = Job()
LOCK = threading.Lock()


def _run_job(book_id: str, demo: bool, only: list[int] | None = None) -> None:
    book = load_book(book_id)
    with LOCK:
        JOB.book = book_id
        JOB.demo = demo
        JOB.pages = [
            {"no": p.no, "title": p.title, "status": "pending", "error": ""}
            for p in book.pages
            if only is None or p.no in only
        ]
        JOB.running = True
    try:
        cfg = None if demo else gen.build_config()
    except RuntimeError as exc:
        for entry in JOB.pages:
            entry["status"], entry["error"] = "failed", str(exc)
        JOB.running = False
        return

    from .story import ASSETS_DIR

    for entry in JOB.pages:
        page = next(p for p in book.pages if p.no == entry["no"])
        entry["status"] = "generating"
        try:
            if demo:
                time.sleep(random.uniform(0.4, 1.0))  # 模拟生成耗时
                entry["status"] = "done"
                continue
            out_path = ASSETS_DIR / page.image
            if out_path.exists():
                entry["status"] = "done"  # 已有图片，跳过
                continue
            gen._generate_one(page.prompt, out_path, cfg)
            entry["status"] = "done"
        except Exception as exc:  # noqa: BLE001 - 单页失败不中断整本
            entry["status"] = "failed"
            entry["error"] = str(exc)[:200]
        time.sleep(0.1)

    with LOCK:
        JOB.running = False


def _page_image_bytes(book_id: str, no: int) -> bytes:
    from .build import resolve_image

    book = load_book(book_id)
    page = next(p for p in book.pages if p.no == no)
    src, _ = resolve_image(page, book.id)
    cache_name = f"srv-{book_id}-{no:02d}.jpg"
    cropped = cover_crop(src, CACHE_DIR / cache_name, 16 / 10)
    return cropped.read_bytes()


def make_handler(demo: bool):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args) -> None:  # 安静模式
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self._send(200, APP_HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/books":
                books = [
                    {
                        "id": b.id,
                        "title": b.title,
                        "subtitle": b.subtitle,
                        "demo": demo,
                        "pages": [
                            {"no": p.no, "kind": p.kind, "title": p.title, "text": p.text or ""}
                            for p in b.pages
                        ],
                    }
                    for b in load_books()
                ]
                self._json(books)
            elif path == "/api/job":
                with LOCK:
                    self._json(JOB.snapshot())
            elif path.startswith("/api/page/") and path.endswith(".jpg"):
                parts = path.split("/")
                try:
                    body = _page_image_bytes(parts[3], int(parts[4].removesuffix(".jpg")))
                    self._send(200, body, "image/jpeg")
                except (StopIteration, ValueError, OSError, FileNotFoundError):
                    self._send(404, b"not found", "text/plain")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/generate":
                book_id = payload.get("book", "")
                try:
                    load_book(book_id)
                except FileNotFoundError as exc:
                    self._json({"error": str(exc)}, 404)
                    return
                with LOCK:
                    if JOB.running:
                        self._json({"error": "已有生成任务进行中，请稍候"}, 409)
                        return
                threading.Thread(target=_run_job, args=(book_id, demo), daemon=True).start()
                self._json({"ok": True})
            elif path == "/api/retry":
                book_id = payload.get("book", "")
                with LOCK:
                    if JOB.running:
                        self._json({"error": "已有生成任务进行中"}, 409)
                        return
                    only = [p["no"] for p in JOB.pages if p["status"] == "failed"]
                if not only:
                    self._json({"error": "没有失败页"}, 400)
                    return
                threading.Thread(target=_run_job, args=(book_id, demo, only), daemon=True).start()
                self._json({"ok": True})
            else:
                self._send(404, b"not found", "text/plain")

    return Handler


def cmd_serve(port: int = 8765, demo: bool = False) -> int:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(demo))
    mode = "演示模式（占位图模拟生成）" if demo else "真实模式（调用 .env 配置的生图 API）"
    print(f"AIGC 绘本生成器已启动：http://127.0.0.1:{port}  （{mode}，Ctrl+C 退出）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0
