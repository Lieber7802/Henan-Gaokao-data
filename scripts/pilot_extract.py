from __future__ import annotations

import csv
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from paddleocr import PaddleOCR

try:
    from .ocr_result_utils import extract_ocr_lines, find_json_files, load_saved_result
    from .pilot_paths import (
        CONFIG_PATH,
        OCR_RAW_DIR,
        RENDERED_DIR,
        SOURCE_PDF,
        TABLES_CSV_DIR,
        TABLES_XLSX_DIR,
        ensure_output_dirs,
    )
    from .validate_pilot import TABLE_BATCH, parse_application_line, validate_score_row, validate_tables
except ImportError:
    from ocr_result_utils import extract_ocr_lines, find_json_files, load_saved_result
    from pilot_paths import (
        CONFIG_PATH,
        OCR_RAW_DIR,
        RENDERED_DIR,
        SOURCE_PDF,
        TABLES_CSV_DIR,
        TABLES_XLSX_DIR,
        ensure_output_dirs,
    )
    from validate_pilot import TABLE_BATCH, parse_application_line, validate_score_row, validate_tables

REQUIRED_ROW_FIELDS = [
    "source_pdf",
    "source_page",
    "printed_page",
    "chapter",
    "section",
    "table_type",
    "row_index_on_page",
    "review_status",
]


def load_config() -> list[dict[str, Any]]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return config["pages"]


def image_for_page(page: int) -> Path:
    matches = sorted(RENDERED_DIR.glob(f"page_{page:03d}-*.png"))
    if not matches:
        raise FileNotFoundError(f"Rendered image missing for PDF page {page}")
    return matches[0]


def run_ocr_for_page(ocr: PaddleOCR, image_path: Path, force: bool = False) -> tuple[Path, float, int]:
    output_dir = OCR_RAW_DIR / image_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = find_json_files(output_dir)
    if existing and not force:
        return output_dir, 0.0, len(existing)

    for path in existing:
        path.unlink()

    started = time.time()
    result = ocr.predict(str(image_path))
    elapsed = round(time.time() - started, 3)
    for res in result:
        res.save_to_json(save_path=str(output_dir))
    return output_dir, elapsed, len(result)


def printed_page_for_pdf_page(pdf_page: int) -> str:
    if pdf_page >= 5:
        return str(pdf_page - 4)
    return ""


def review_status_for_line(table_type: str, parsed: dict[str, str], confidence: object) -> str:
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        conf = 0.0
    if conf and conf < 0.85:
        return "needs_review"

    if table_type in TABLE_BATCH and parsed.get("year") and parsed.get("min_score") and parsed.get("score_diff"):
        result = validate_score_row({
            "year": parsed["year"],
            "batch": TABLE_BATCH[table_type],
            "min_score": parsed["min_score"],
            "score_diff": parsed["score_diff"],
        })
        return result["review_status"]

    if table_type in TABLE_BATCH and re.search(r"202[34]", json.dumps(parsed, ensure_ascii=False)):
        return "needs_review"

    return "auto_pass"


def normalize_page_lines(meta: dict[str, Any], output_dir: Path, image_path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for json_path in find_json_files(output_dir):
        data = load_saved_result(json_path)
        for line in extract_ocr_lines(data):
            text = line["text"]
            parsed = parse_application_line(text) if meta["table_type"] in TABLE_BATCH else {}
            rows.append({
                "source_pdf": str(SOURCE_PDF),
                "source_page": meta["pdf_page"],
                "printed_page": printed_page_for_pdf_page(meta["pdf_page"]),
                "chapter": meta["chapter"],
                "section": meta["section"],
                "table_type": meta["table_type"],
                "row_index_on_page": len(rows) + 1,
                "review_status": review_status_for_line(meta["table_type"], parsed, line.get("confidence")),
                "ocr_index": line["ocr_index"],
                "text": text,
                "confidence": line["confidence"],
                "bbox_json": line["bbox_json"],
                "poly_json": line["poly_json"],
                "parsed_fields_json": json.dumps(parsed, ensure_ascii=False),
                "source_image": str(image_path),
                "source_ocr_json": str(json_path),
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        rows = [{field: "" for field in REQUIRED_ROW_FIELDS}]
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(rows_by_table: dict[str, list[dict[str, object]]]) -> None:
    TABLES_CSV_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_XLSX_DIR.mkdir(parents=True, exist_ok=True)

    workbook_path = TABLES_XLSX_DIR / "paddleocr_pilot_extract.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        for table_type in sorted(rows_by_table):
            rows = rows_by_table[table_type]
            csv_path = TABLES_CSV_DIR / f"{table_type}.csv"
            write_csv(csv_path, rows)
            df = pd.DataFrame(rows)
            if df.empty:
                df = pd.DataFrame([{field: "" for field in REQUIRED_ROW_FIELDS}])
            df.to_excel(writer, sheet_name=table_type[:31], index=False)
    print(workbook_path)


def main() -> None:
    ensure_output_dirs()
    pages = load_config()
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_detection_model_name=os.environ.get("PILOT_TEXT_DETECTION_MODEL_NAME", "PP-OCRv6_tiny_det"),
        text_recognition_model_name=os.environ.get("PILOT_TEXT_RECOGNITION_MODEL_NAME", "PP-OCRv6_tiny_rec"),
    )

    timing_rows = []
    rows_by_table: dict[str, list[dict[str, object]]] = defaultdict(list)
    for meta in pages:
        image_path = image_for_page(meta["pdf_page"])
        output_dir, elapsed, result_pages = run_ocr_for_page(ocr, image_path)
        normalized_rows = normalize_page_lines(meta, output_dir, image_path)
        rows_by_table[meta["table_type"]].extend(normalized_rows)
        timing_rows.append({
            "image": image_path.name,
            "pdf_page": meta["pdf_page"],
            "table_type": meta["table_type"],
            "text_detection_model": os.environ.get("PILOT_TEXT_DETECTION_MODEL_NAME", "PP-OCRv6_tiny_det"),
            "text_recognition_model": os.environ.get("PILOT_TEXT_RECOGNITION_MODEL_NAME", "PP-OCRv6_tiny_rec"),
            "elapsed_seconds": elapsed,
            "result_pages": result_pages,
            "normalized_rows": len(normalized_rows),
            "used_cached_ocr": elapsed == 0.0,
        })
        print(f"{image_path.name}: {len(normalized_rows)} OCR lines, {elapsed}s")

    timing_path = OCR_RAW_DIR / "timing.json"
    timing_path.write_text(json.dumps(timing_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    write_outputs(rows_by_table)
    validate_tables()
    print(timing_path)


if __name__ == "__main__":
    main()
