from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from .pilot_paths import RENDERED_DIR, REVIEW_DIR, ensure_output_dirs
except ImportError:
    from pilot_paths import RENDERED_DIR, REVIEW_DIR, ensure_output_dirs


def clusters(indices: np.ndarray, gap: int = 4) -> list[tuple[int, int, int, int]]:
    if len(indices) == 0:
        return []
    output = []
    start = prev = int(indices[0])
    for value in indices[1:]:
        value = int(value)
        if value - prev <= gap:
            prev = value
        else:
            output.append((start, prev, (start + prev) // 2, prev - start + 1))
            start = prev = value
    output.append((start, prev, (start + prev) // 2, prev - start + 1))
    return output


def analyze_image(path: Path) -> dict[str, object]:
    image = Image.open(path).convert("L")
    arr = np.array(image)
    dark = arr < 120
    height, width = dark.shape

    row_counts = dark.sum(axis=1)
    horizontal = clusters(np.where(row_counts > width * 0.25)[0])
    candidate_ys = [cluster[2] for cluster in horizontal if cluster[2] > height * 0.12]
    y0 = min(candidate_ys) if candidate_ys else 0
    y1 = max(candidate_ys) if candidate_ys else height - 1

    roi = dark[y0 : y1 + 1, :]
    col_counts = roi.sum(axis=0)
    vertical = clusters(np.where(col_counts > roi.shape[0] * 0.10)[0])
    thin_vertical = [cluster for cluster in vertical if cluster[3] <= 12]

    boundary_ok = len(horizontal) >= 5 and len(thin_vertical) >= 4
    return {
        "image": path.name,
        "width": width,
        "height": height,
        "table_y0": y0,
        "table_y1": y1,
        "horizontal_line_count": len(horizontal),
        "vertical_line_count": len(thin_vertical),
        "boundary_status": "ok" if boundary_ok else "needs_review",
        "vertical_centers": " ".join(str(cluster[2]) for cluster in thin_vertical),
    }


def main() -> None:
    ensure_output_dirs()
    images = sorted(RENDERED_DIR.glob("*.png"))
    if not images:
        raise FileNotFoundError("Render pilot pages before running table line probe.")

    rows = [analyze_image(path) for path in images]
    output_path = REVIEW_DIR / "table_line_probe.csv"
    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(output_path)


if __name__ == "__main__":
    main()
