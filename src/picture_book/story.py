"""加载、校验绘本数据：data/books/ 下每本一个 JSON，文件名即书目 id。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
BOOKS_DIR = DATA_DIR / "books"
ASSETS_DIR = PROJECT_ROOT / "assets" / "images"
CACHE_DIR = PROJECT_ROOT / "assets" / ".cache"
PLACEHOLDER_DIR = PROJECT_ROOT / "assets" / ".placeholders"
DIST_DIR = PROJECT_ROOT / "dist"

REQUIRED_FIELDS = {"no", "kind", "title", "image", "prompt"}
KNOWN_FIELDS = REQUIRED_FIELDS | {"text"}
VALID_KINDS = {"cover", "story", "back"}


@dataclass
class Page:
    no: int
    kind: str  # cover | story | back
    title: str
    image: str
    prompt: str
    text: str | None = None

    @property
    def is_story(self) -> bool:
        return self.kind == "story"


@dataclass
class Book:
    id: str  # 文件名去扩展名，如 cao-chuan-jie-jian
    title: str
    subtitle: str
    pages: list[Page]

    @property
    def story_pages(self) -> list[Page]:
        return [p for p in self.pages if p.is_story]


def _validate_page(raw: dict, index: int) -> Page:
    where = f"第 {index} 页"
    unknown = set(raw) - KNOWN_FIELDS
    if unknown:
        raise ValueError(f"{where} 含有未知字段: {sorted(unknown)}，允许的字段: {sorted(KNOWN_FIELDS)}")
    missing = REQUIRED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"{where} 缺少字段: {sorted(missing)}")
    if raw["kind"] not in VALID_KINDS:
        raise ValueError(f"{where} kind 必须是 {sorted(VALID_KINDS)} 之一，现在是 {raw['kind']!r}")
    if raw["kind"] == "story" and not (raw.get("text") or "").strip():
        raise ValueError(f"{where}（story 页）必须提供正文 text")
    return Page(**raw)


def _parse_book(book_id: str, data: dict, source: Path) -> Book:
    for key in ("title", "subtitle", "pages"):
        if key not in data:
            raise ValueError(f"{source} 缺少顶层字段 {key!r}")
    pages = [_validate_page(raw, i) for i, raw in enumerate(data["pages"], start=1)]
    nums = [p.no for p in pages]
    if not pages:
        raise ValueError(f"{source} 里没有任何页面")
    if len(set(nums)) != len(nums):
        raise ValueError(f"{source} 页码有重复: {sorted(nums)}")
    return Book(id=book_id, title=data["title"], subtitle=data["subtitle"], pages=pages)


def available_book_ids() -> list[str]:
    if not BOOKS_DIR.exists():
        return []
    return sorted(p.stem for p in BOOKS_DIR.glob("*.json"))


def load_book(book_id: str) -> Book:
    path = BOOKS_DIR / f"{book_id}.json"
    if not path.exists():
        ids = ", ".join(available_book_ids()) or "（无）"
        raise FileNotFoundError(f"找不到绘本 {book_id!r}（{path}）。现有书目: {ids}")
    return _parse_book(book_id, json.loads(path.read_text(encoding="utf-8")), path)


def load_books() -> list[Book]:
    ids = available_book_ids()
    if not ids:
        raise FileNotFoundError(f"{BOOKS_DIR} 下没有任何绘本 JSON。")
    return [load_book(i) for i in ids]


def find_image(page: Page) -> Path | None:
    """按页面对应的文件名找图，找不到再试同名其他扩展名。"""
    exact = ASSETS_DIR / page.image
    if exact.exists():
        return exact
    stem = Path(page.image).stem
    for ext in (".jpg", ".jpeg", ".webp"):
        candidate = ASSETS_DIR / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None
