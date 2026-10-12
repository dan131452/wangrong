"""系统中文字体探测：reportlab（PDF）与 Pillow（占位图）共用一份候选清单。"""

from __future__ import annotations

from pathlib import Path

_FONT_FILES: dict[str, list[str]] = {
    "regular": [
        r"C:\Windows\Fonts\msyh.ttc",   # 微软雅黑
        r"C:\Windows\Fonts\simhei.ttf",  # 黑体
        r"C:\Windows\Fonts\simsun.ttc",  # 宋体
    ],
    "bold": [
        r"C:\Windows\Fonts\msyhbd.ttc",  # 微软雅黑 Bold
        r"C:\Windows\Fonts\simhei.ttf",  # 黑体当作粗体兜底
    ],
}


def first_existing(kind: str = "regular") -> Path | None:
    """返回候选清单里第一个存在的字体文件，全都没有则返回 None。"""
    for path in _FONT_FILES.get(kind, _FONT_FILES["regular"]):
        p = Path(path)
        if p.exists():
            return p
    return None


def pil_font(size: int, kind: str = "regular"):
    """给 Pillow 用的字体对象；系统字体全缺时退回内置位图字体。"""
    from PIL import ImageFont

    path = first_existing(kind)
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()
