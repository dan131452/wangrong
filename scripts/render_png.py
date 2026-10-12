"""把成品 PDF 渲染成 PNG 预览图（用于快速检查版式）。

用法：uv run --group preview python scripts/render_png.py
输出：dist/preview/page-NN.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

DIST = Path(__file__).resolve().parents[1] / "dist"


def main() -> int:
    pdfs = sorted(DIST.glob("*.pdf"))
    if not pdfs:
        print("dist/ 下没有找到 PDF，请先 build。")
        return 1
    out_dir = DIST / "preview"
    out_dir.mkdir(exist_ok=True)
    for pdf in pdfs:
        doc = pymupdf.open(pdf)
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=120)
            pix.save(out_dir / f"page-{i:02d}.png")
        print(f"{pdf.name}: {len(doc)} 页 -> {out_dir}")
        doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
