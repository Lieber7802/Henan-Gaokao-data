from __future__ import annotations

import csv
import json
import re
from pathlib import Path

try:
    from .pilot_paths import REVIEW_DIR, TABLES_CSV_DIR, ensure_output_dirs
except ImportError:
    from pilot_paths import REVIEW_DIR, TABLES_CSV_DIR, ensure_output_dirs

CONTROL_LINES = {
    ("2024", "本科一批"): 511,
    ("2024", "本科二批"): 396,
    ("2024", "高职高专批"): 185,
    ("2023", "本科一批"): 514,
    ("2023", "本科二批"): 409,
    ("2023", "高职高专批"): 185,
}

COMMON_NUMERIC_CONFUSIONS = str.maketrans({
    "O": "0",
    "o": "0",
    "D": "0",
    "I": "1",
    "l": "1",
    "L": "1",
    "B": "8",
})

TABLE_BATCH = {
    "chapter2_batch1_application": "本科一批",
    "chapter2_batch2_application": "本科二批",
    "chapter2_vocational_application": "高职高专批",
}


def normalize_numeric_text(value: object) -> str:
    return str(value).strip().translate(COMMON_NUMERIC_CONFUSIONS)


def validate_score_row(row: dict[str, object]) -> dict[str, object]:
    issues = []
    year = normalize_numeric_text(row.get("year", ""))
    batch = str(row.get("batch", "")).strip()
    min_score = normalize_numeric_text(row.get("min_score", ""))
    score_diff = normalize_numeric_text(row.get("score_diff", ""))

    if year not in {"2023", "2024"}:
        issues.append("invalid_year")

    if not min_score.isdigit():
        issues.append("invalid_min_score")
    elif not 100 <= int(min_score) <= 750:
        issues.append("min_score_out_of_range")

    if not score_diff.lstrip("-").isdigit():
        issues.append("invalid_score_diff")

    control_line = CONTROL_LINES.get((year, batch))
    if control_line is None:
        issues.append("unknown_batch_control_line")
    elif min_score.isdigit() and score_diff.lstrip("-").isdigit():
        if int(min_score) - control_line != int(score_diff):
            issues.append("score_diff_mismatch")

    return {
        **row,
        "year": year,
        "min_score": min_score,
        "score_diff": score_diff,
        "review_status": "auto_pass" if not issues else "needs_review",
        "issues": ";".join(issues),
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def validate_tables() -> dict[str, object]:
    ensure_output_dirs()
    failures: list[dict[str, object]] = []
    summary: dict[str, dict[str, int]] = {}

    for table_type, batch in TABLE_BATCH.items():
        path = TABLES_CSV_DIR / f"{table_type}.csv"
        rows = _read_csv(path)
        summary[table_type] = {"rows_checked": 0, "auto_pass": 0, "needs_review": 0}
        for row in rows:
            parsed = json.loads(row.get("parsed_fields_json") or "{}")
            if not parsed:
                continue
            candidate = {
                "year": parsed.get("year", ""),
                "batch": batch,
                "min_score": parsed.get("min_score", ""),
                "score_diff": parsed.get("score_diff", ""),
            }
            result = validate_score_row(candidate)
            summary[table_type]["rows_checked"] += 1
            summary[table_type][result["review_status"]] += 1
            if result["review_status"] != "auto_pass":
                failures.append({
                    "source_page": row.get("source_page", ""),
                    "row_index_on_page": row.get("row_index_on_page", ""),
                    "table_type": table_type,
                    "field_name": "score_row",
                    "detected_value": row.get("text", ""),
                    "issues": result["issues"],
                    "crop_reference": row.get("source_image", ""),
                })

    failures_path = REVIEW_DIR / "field_failures.csv"
    if failures:
        _write_csv(failures_path, failures)
    else:
        _write_csv(failures_path, [{
            "source_page": "",
            "row_index_on_page": "",
            "table_type": "",
            "field_name": "",
            "detected_value": "",
            "issues": "",
            "crop_reference": "",
        }])

    summary_path = REVIEW_DIR / "numeric_validation_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"summary": summary, "failure_count": len(failures)}


def parse_application_line(text: str) -> dict[str, str]:
    year_match = re.search(r"(202[34])", text)
    if not year_match:
        return {}
    year = year_match.group(1)
    tail = normalize_numeric_text(text[year_match.end():])
    numbers = re.findall(r"-?\d+(?:\.\d+)?", tail)
    if len(numbers) < 8:
        return {"year": year}
    return {
        "year": year,
        "published_plan": numbers[0],
        "actual投档人数": numbers[1],
        "min_score": numbers[2],
        "chinese": numbers[3],
        "math": numbers[4],
        "foreign_listening": numbers[5],
        "score_diff": numbers[6],
        "rank": numbers[7],
    }


def main() -> None:
    result = validate_tables()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
