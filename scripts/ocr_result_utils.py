from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def result_to_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    json_attr = getattr(result, "json", None)
    if isinstance(json_attr, dict):
        return json_attr
    if callable(json_attr):
        value = json_attr()
        if isinstance(value, dict):
            return value
    if hasattr(result, "__dict__"):
        return dict(result.__dict__)
    return {"raw_repr": repr(result)}


def find_json_files(output_dir: Path) -> list[Path]:
    return sorted(path for path in output_dir.glob("*.json") if path.name != "timing.json")


def load_saved_result(json_path: Path) -> dict[str, Any]:
    return json.loads(json_path.read_text(encoding="utf-8"))


def unwrap_result(data: dict[str, Any]) -> dict[str, Any]:
    if "res" in data and isinstance(data["res"], dict):
        return data["res"]
    return data


def extract_ocr_lines(data: dict[str, Any]) -> list[dict[str, Any]]:
    res = unwrap_result(data)
    texts = res.get("rec_texts") or []
    scores = res.get("rec_scores") or []
    boxes = res.get("rec_boxes") or res.get("dt_boxes") or []
    polys = res.get("rec_polys") or res.get("dt_polys") or []

    rows: list[dict[str, Any]] = []
    for idx, text in enumerate(texts):
        score = scores[idx] if idx < len(scores) else ""
        box = boxes[idx] if idx < len(boxes) else ""
        poly = polys[idx] if idx < len(polys) else ""
        rows.append({
            "ocr_index": idx,
            "text": str(text),
            "confidence": float(score) if isinstance(score, (float, int)) else score,
            "bbox_json": json.dumps(box, ensure_ascii=False),
            "poly_json": json.dumps(poly, ensure_ascii=False),
        })
    return rows
