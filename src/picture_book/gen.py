"""调用生图 API 批量生成插画（key 与平台配置在项目根目录 .env）。

.env 配置项：
    IMAGE_API_KEY   生图 API key（必填）
    IMAGE_API_BASE  API 根地址，默认 https://api.ipc.wiki/v1（OpenAI 兼容中转）
    IMAGE_MODEL     模型名，默认 gpt-image-2.5
    IMAGE_SIZE      出图尺寸，默认 1536x1024（gpt-image 系列横版；管道会自动居中裁剪）

用法：
    uv run picture-book gen                    # 生成所有绘本缺失的插画
    uv run picture-book gen --book san-gu-mao-lu   # 只生成《三顾茅庐》
    uv run picture-book gen --book cao-chuan-jie-jian --page 3   # 只生成某一本的第 3 页
    uv run picture-book gen --force            # 已有图片也重新生成
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from .story import ASSETS_DIR, PROJECT_ROOT, load_book, load_books

DEFAULT_BASE = "https://api.ipc.wiki/v1"
DEFAULT_MODEL = "gpt-image-2.5"
DEFAULT_SIZE = "1536x1024"
REQUEST_TIMEOUT = 300  # gpt-image 单张生成常超 2 分钟，中转排队更久


def _load_dotenv() -> None:
    """把 .env 的 KEY=VALUE 读进环境变量（已存在的环境变量优先）。"""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def build_config() -> dict[str, str]:
    """读 .env / 环境变量，返回生图配置；缺 key 时抛 RuntimeError。"""
    _load_dotenv()
    key = os.environ.get("IMAGE_API_KEY", "")
    if not key:
        raise RuntimeError(".env 里没有 IMAGE_API_KEY")
    return {
        "key": key,
        "base": os.environ.get("IMAGE_API_BASE", DEFAULT_BASE).rstrip("/"),
        "model": os.environ.get("IMAGE_MODEL", DEFAULT_MODEL),
        "size": os.environ.get("IMAGE_SIZE", DEFAULT_SIZE),
    }


def _generate_one(prompt: str, out_path: Path, cfg: dict[str, str]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)  # 新克隆的仓库里 assets/images 可能不存在
    body = json.dumps({"model": cfg["model"], "prompt": prompt, "size": cfg["size"]}).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg['base']}/images/generations",
        data=body,
        headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"},
        method="POST",
    )
    last_error = ""
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            item = payload["data"][0]
            if item.get("b64_json"):
                out_path.write_bytes(base64.b64decode(item["b64_json"]))
            elif item.get("url"):
                with urllib.request.urlopen(item["url"], timeout=120) as img:
                    out_path.write_bytes(img.read())
            else:
                raise KeyError("返回里既没有 b64_json 也没有 url")
            return
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            print(f"    第 {attempt} 次尝试失败：{last_error}", file=sys.stderr)
            time.sleep(3 * attempt)
    raise RuntimeError(f"生成失败：{last_error}")


def cmd_gen(book_id: str | None = None, page: int | None = None, force: bool = False) -> int:
    try:
        cfg = build_config()
    except RuntimeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    books = [load_book(book_id)] if book_id else load_books()
    targets = [(book, p) for book in books for p in book.pages if page is None or p.no == page]
    if page is not None and not targets:
        print(f"错误：没有第 {page} 页。", file=sys.stderr)
        return 1

    ok = skipped = failed = 0
    for book, p in targets:
        out_path = ASSETS_DIR / p.image
        if out_path.exists() and not force:
            skipped += 1
            print(f"[跳过] {book.title} P{p.no:02d} 已存在 {p.image}")
            continue
        print(f"[生成] {book.title} P{p.no:02d} {p.title} ...")
        try:
            _generate_one(p.prompt, out_path, cfg)
            ok += 1
            print(f"        -> {out_path}")
        except (RuntimeError, OSError) as exc:
            failed += 1
            print(f"        失败：{exc}", file=sys.stderr)
        time.sleep(2)

    print(f"\n完成：成功 {ok}，跳过 {skipped}，失败 {failed}。")
    if failed:
        print("可单独重试：uv run picture-book gen --book 书目id --page 页码")
        return 1
    print("全部就绪后运行：uv run picture-book build")
    return 0
