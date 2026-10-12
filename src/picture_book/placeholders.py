"""为缺失的插画生成美观的占位图：渐变天空 + 云朵 + 飞鸟 + 层叠远山 + 太阳 + 江浪。"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from .fonts import pil_font
from .story import PLACEHOLDER_DIR

W, H = 1600, 1200
TOP = (255, 244, 222)      # 奶油色天空
BOTTOM = (206, 228, 216)   # 浅青绿地平线
INK = (107, 63, 42)        # 暖棕文字
SUB = (150, 110, 84)       # 次级暖棕

# 三层远山：(颜色, 基准线 y, 振幅, 频率, 相位)
MOUNTAINS = [
    ((214, 232, 220), int(H * 0.50), 70, 2.1, 0.0),
    ((192, 218, 202), int(H * 0.58), 85, 1.6, 1.3),
    ((172, 208, 190), int(H * 0.66), 95, 1.2, 2.6),
]

# 三层江浪：(颜色, 基准线 y, 相位)
WAVES = [
    ((164, 202, 192), H - 200, 0.0),
    ((138, 186, 176), H - 140, 1.8),
    ((106, 166, 156), H - 80, 3.6),
]

CLOUDS = [
    (260, 170, 150),
    (640, 110, 120),
    (1020, 200, 170),
    (1310, 130, 110),
]

BIRDS = [
    (470, 320, 26),
    (545, 285, 22),
    (600, 330, 18),
]


def _draw_gradient(draw: ImageDraw.ImageDraw) -> None:
    for y in range(H):
        t = y / (H - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))
        draw.line([(0, y), (W, y)], fill=color)


def _draw_sun(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse([W - 400, 70, W - 170, 300], fill=(255, 214, 153))
    draw.ellipse([W - 360, 110, W - 210, 260], fill=(255, 231, 186))


def _draw_cloud(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    color = (255, 252, 244)
    draw.ellipse([cx - size, cy - size * 0.38, cx + size, cy + size * 0.38], fill=color)
    draw.ellipse([cx - size * 0.55, cy - size * 0.75, cx + size * 0.35, cy - size * 0.05], fill=color)
    draw.ellipse([cx - size * 0.15, cy - size * 0.62, cx + size * 0.75, cy + size * 0.02], fill=color)


def _draw_bird(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int) -> None:
    color = (124, 124, 112)
    width = max(3, size // 7)
    draw.arc([cx - size, cy - size, cx, cy], 200, 330, fill=color, width=width)
    draw.arc([cx, cy - size, cx + size, cy], 210, 340, fill=color, width=width)


def _draw_mountains(draw: ImageDraw.ImageDraw) -> None:
    for color, y0, amp, freq, phase in MOUNTAINS:
        points = [
            (x, y0 - amp * (0.5 + 0.5 * math.sin(x / W * math.pi * freq + phase)))
            for x in range(0, W + 1, 8)
        ]
        draw.polygon(points + [(W, H), (0, H)], fill=color)


def _draw_waves(draw: ImageDraw.ImageDraw) -> None:
    for color, y0, phase in WAVES:
        points = [(x, y0 + math.sin(x / 90 + phase) * 14) for x in range(0, W + 1, 8)]
        draw.polygon(points + [(W, H), (0, H)], fill=color)


def make_placeholder(book_id: str, no: int, title: str, out_path: Path) -> Path:
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_gradient(draw)
    _draw_sun(draw)
    for cx, cy, size in CLOUDS:
        _draw_cloud(draw, cx, cy, size)
    for cx, cy, size in BIRDS:
        _draw_bird(draw, cx, cy, size)
    _draw_mountains(draw)
    _draw_waves(draw)

    f_big = pil_font(88)
    f_small = pil_font(44)
    line1 = f"第 {no} 页 · 插画占位"
    line2 = f"《{title}》待替换"
    draw.text(((W - draw.textlength(line1, font=f_big)) / 2, H / 2 - 90), line1, font=f_big, fill=INK)
    draw.text(((W - draw.textlength(line2, font=f_small)) / 2, H / 2 + 30), line2, font=f_small, fill=SUB)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def placeholder_for(book_id: str, no: int, title: str) -> Path:
    """占位图文件名带书目 id，避免多本书互相覆盖。"""
    return make_placeholder(book_id, no, title, PLACEHOLDER_DIR / f"ph-{book_id}-{no:02d}.png")
