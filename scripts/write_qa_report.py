from __future__ import annotations

import csv
import importlib.metadata
import json
from pathlib import Path

import paddle

try:
    from .pilot_paths import OCR_RAW_DIR, RENDERED_DIR, REVIEW_DIR, SOURCE_PDF, TABLES_CSV_DIR, TABLES_XLSX_DIR, ensure_output_dirs
except ImportError:
    from pilot_paths import OCR_RAW_DIR, RENDERED_DIR, REVIEW_DIR, SOURCE_PDF, TABLES_CSV_DIR, TABLES_XLSX_DIR, ensure_output_dirs


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.0%"
    return f"{numerator / denominator * 100:.1f}%"


def main() -> None:
    ensure_output_dirs()
    timing_path = OCR_RAW_DIR / "timing.json"
    timing_rows = json.loads(timing_path.read_text(encoding="utf-8")) if timing_path.exists() else []
    non_cached = [row for row in timing_rows if not row.get("used_cached_ocr")]
    timing_base = non_cached or timing_rows
    avg_seconds = sum(float(row.get("elapsed_seconds", 0)) for row in timing_base) / len(timing_base) if timing_base else 0
    estimated_hours = avg_seconds * 912 / 3600

    probe_rows = read_csv(REVIEW_DIR / "table_line_probe.csv")
    validation_summary_path = REVIEW_DIR / "numeric_validation_summary.json"
    validation_summary = (
        json.loads(validation_summary_path.read_text(encoding="utf-8"))
        if validation_summary_path.exists()
        else {}
    )

    table_lines = []
    for row in probe_rows:
        page = row["image"].split("-")[0].replace("page_", "")
        status = row.get("boundary_status", "")
        notes = f"h={row.get('horizontal_line_count', '')}, v={row.get('vertical_line_count', '')}"
        table_lines.append(f"| {int(page)} | inferred from config | {status} | {notes} |")

    ocr_lines = []
    for csv_path in sorted(TABLES_CSV_DIR.glob("*.csv")):
        rows = read_csv(csv_path)
        good = sum(1 for row in rows if row.get("review_status") == "auto_pass")
        bad = sum(1 for row in rows if row.get("review_status") == "needs_review")
        ocr_lines.append(f"| - | {csv_path.stem} | {good} | {bad} | {len(rows)} OCR rows |")

    numeric_lines = []
    for table_type, stats in validation_summary.items():
        rows_checked = int(stats.get("rows_checked", 0))
        auto_pass = int(stats.get("auto_pass", 0))
        needs_review = int(stats.get("needs_review", 0))
        numeric_lines.append(
            f"| {table_type} | {rows_checked} | {auto_pass} | {needs_review} | {pct(auto_pass, rows_checked)} |"
        )

    rendered_count = len(list(RENDERED_DIR.glob("*.png")))
    raw_json_count = len([path for path in OCR_RAW_DIR.glob("page_*/*.json") if path.name != "timing.json"])
    needs_custom_line_rules = any(row.get("boundary_status") != "ok" for row in probe_rows)
    needs_numeric_work = any(int(stats.get("needs_review", 0)) > 0 for stats in validation_summary.values())
    det_model = timing_rows[0].get("text_detection_model", "") if timing_rows else ""
    rec_model = timing_rows[0].get("text_recognition_model", "") if timing_rows else ""

    if needs_custom_line_rules or needs_numeric_work:
        recommendation = "Continue with a second pilot focused on cell-level OCR and stateful row parsing before full extraction."
    else:
        recommendation = "Proceed to full extractor design with resumable batches."

    report = "\n".join([
        "# PaddleOCR Pilot QA Report",
        "",
        "## Summary",
        "",
        f"- Source PDF: `{SOURCE_PDF}`",
        f"- Pilot page count: {rendered_count}",
        f"- Raw OCR JSON files: {raw_json_count}",
        f"- PaddleOCR version: {importlib.metadata.version('paddleocr')}",
        f"- PaddlePaddle version: {paddle.__version__}",
        "- CPU/GPU mode: CPU",
        f"- Text detection model: {det_model}",
        f"- Text recognition model: {rec_model}",
        f"- Average seconds per page: {avg_seconds:.2f}",
        f"- Estimated full-run hours: {estimated_hours:.2f}",
        f"- Workbook: `{TABLES_XLSX_DIR / 'paddleocr_pilot_extract.xlsx'}`",
        "",
        "## Table Structure Findings",
        "",
        "| Page | Table Type | Boundary Detection | Notes |",
        "|---:|---|---|---|",
        *(table_lines or ["| - | - | missing | table_line_probe.csv was not generated |"]),
        "",
        "## OCR Findings",
        "",
        "| Page | Table Type | Good Fields | Problem Fields | Notes |",
        "|---:|---|---:|---:|---|",
        *(ocr_lines or ["| - | - | 0 | 0 | no CSV outputs found |"]),
        "",
        "## Numeric Validation Findings",
        "",
        "| Table Type | Rows Checked | Auto Pass | Needs Review | Pass Rate |",
        "|---|---:|---:|---:|---:|",
        *(numeric_lines or ["| - | 0 | 0 | 0 | 0.0% |"]),
        "",
        "## Full Extraction Recommendation",
        "",
        f"- Recommendation: {recommendation}",
        "- Required rule changes before full run: add table-type-specific row grouping and cell-level numeric OCR for review-heavy pages.",
        "- Expected manual review burden: use `review/field_failures.csv` as the review queue.",
        f"- Estimated runtime: {estimated_hours:.2f} hours for 912 pages at the observed pilot speed.",
        "",
    ])

    output_path = REVIEW_DIR / "qa_report.md"
    output_path.write_text(report, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
