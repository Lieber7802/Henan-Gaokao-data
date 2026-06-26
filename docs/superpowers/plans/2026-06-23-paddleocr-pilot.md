# PaddleOCR Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate whether PaddleOCR can reliably extract the tables from `D:\gaokao_data\2025年理科录取统计.pdf` before running the full 912-page conversion.

**Architecture:** Treat the PDF as an image source and ignore the existing OCR text layer. Render a representative page set to images, run PaddleOCR locally on CPU, combine OCR output with table-line/page-layout rules, then produce sample CSV/XLSX outputs and a QA report that quantifies structure errors, OCR errors, numeric validation failures, and expected full-run cost.

**Tech Stack:** Windows 11 PowerShell, isolated Python virtual environment, PaddlePaddle CPU, PaddleOCR, Poppler `pdftoppm`, Pillow, pandas, openpyxl, pytest.

---

## Current Findings

- Source PDF: `D:\gaokao_data\2025年理科录取统计.pdf`
- Pages: 912
- PDF creation device: RICOH MP C6503
- Main content: scanned image pages with an unreliable OCR text layer
- Local hardware: Intel i7-10700, 8 cores / 16 threads, about 32GB RAM
- GPU status: no NVIDIA CUDA runtime detected; pilot should assume CPU inference
- Existing safe ASCII hardlink: `D:\gaokao_data\tmp_input_2025_science_stats.pdf`

## Pilot Decision Gates

Move to full extraction only if the pilot meets these thresholds:

- Rendering succeeds for every selected pilot page.
- PaddleOCR installation and model download are reproducible in an isolated environment.
- OCR can process at least 20 representative pages without crashes or memory exhaustion.
- Table boundary detection succeeds on at least 95% of pilot table pages.
- Numeric fields have at least 98% auto-validation pass rate after correction rules.
- Remaining failures can be isolated into a review CSV with page number, row number, field name, detected value, and crop reference.
- Estimated full-run time is acceptable, or the pipeline supports resumable batch processing.

## Pilot Page Set

Use these physical PDF page numbers, not printed page numbers:

- Chapter 1, simple tables / score bands: `5, 6, 10, 18`
- Chapter 2, application statistics, undergraduate first batch: `20, 21, 22, 43`
- Chapter 2, application statistics, undergraduate second batch: `44, 45`
- Chapter 2, application statistics, higher vocational batch: `82, 83, 122`
- Chapter 3, admission statistics, undergraduate first batch by major: `123, 124, 125, 456`
- Chapter 3, admission statistics, undergraduate second batch by major: `457, 458, 869`
- Chapter 3, admission statistics, higher vocational batch: `870, 871, 912`

Total: 23 pages.

## Target Output Shape

Create pilot outputs under `D:\gaokao_data\output\pilot\`:

- `rendered_pages\`: rendered PNG files for the pilot pages
- `ocr_raw\`: raw PaddleOCR JSON output per page
- `tables_csv\`: normalized CSV extracts by table type
- `tables_xlsx\paddleocr_pilot_extract.xlsx`: workbook with one sheet per table type
- `review\field_failures.csv`: fields requiring human review
- `review\qa_report.md`: pilot result summary

Expected workbook sheets:

- `chapter1_score_lines`
- `chapter1_score_bands`
- `chapter2_batch1_application`
- `chapter2_batch2_application`
- `chapter2_vocational_application`
- `chapter3_batch1_major_admission`
- `chapter3_batch2_major_admission`
- `chapter3_vocational_admission`

Every extracted row must include:

- `source_pdf`
- `source_page`
- `printed_page`
- `chapter`
- `section`
- `table_type`
- `row_index_on_page`
- `review_status`

## File Structure

- Create: `D:\gaokao_data\requirements\paddleocr-pilot.txt`
  - Pins only pilot dependencies.
- Create: `D:\gaokao_data\configs\pilot_pages.json`
  - Stores the representative page set and table-type labels.
- Create: `D:\gaokao_data\scripts\pilot_paths.py`
  - Centralizes input/output paths and Poppler binary paths.
- Create: `D:\gaokao_data\scripts\render_pilot_pages.py`
  - Renders pilot PDF pages to PNG.
- Create: `D:\gaokao_data\scripts\paddleocr_smoke.py`
  - Confirms PaddleOCR can run on one known sample image.
- Create: `D:\gaokao_data\scripts\table_line_probe.py`
  - Detects table line candidates from rendered images.
- Create: `D:\gaokao_data\scripts\pilot_extract.py`
  - Runs OCR and writes raw/normalized pilot outputs.
- Create: `D:\gaokao_data\scripts\validate_pilot.py`
  - Applies numeric and structural checks.
- Create: `D:\gaokao_data\tests\test_pilot_config.py`
  - Verifies pilot page mapping and required schema fields.
- Create: `D:\gaokao_data\tests\test_validation_rules.py`
  - Verifies numeric correction and validation rules.

## Task 1: Create Isolated Pilot Environment

**Files:**
- Create: `D:\gaokao_data\requirements\paddleocr-pilot.txt`

- [ ] **Step 1: Create dependency file**

Add:

```text
paddleocr>=3.5.0,<4.0.0
pillow>=10.0.0
pandas>=2.0.0
openpyxl>=3.1.0
pytest>=8.0.0
numpy>=1.26.0
```

- [ ] **Step 2: Create virtual environment**

Run:

```powershell
C:\Users\libermanli\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m venv D:\gaokao_data\.venv-paddleocr
```

Expected: `D:\gaokao_data\.venv-paddleocr\Scripts\python.exe` exists.

- [ ] **Step 3: Install dependencies**

Run:

```powershell
D:\gaokao_data\.venv-paddleocr\Scripts\python.exe -m pip install --upgrade pip
D:\gaokao_data\.venv-paddleocr\Scripts\python.exe -m pip install paddlepaddle==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
D:\gaokao_data\.venv-paddleocr\Scripts\python.exe -m pip install -r D:\gaokao_data\requirements\paddleocr-pilot.txt
```

Expected: installation completes without modifying the bundled Codex Python runtime.

- [ ] **Step 4: Verify imports**

Run:

```powershell
$script = @'
import importlib.metadata
import paddle
import pandas
import PIL
print("paddle", paddle.__version__)
print("paddleocr", importlib.metadata.version("paddleocr"))
'@
$script | D:\gaokao_data\.venv-paddleocr\Scripts\python.exe -
```

Expected: versions print successfully.

## Task 2: Define Pilot Page Configuration

**Files:**
- Create: `D:\gaokao_data\configs\pilot_pages.json`
- Create: `D:\gaokao_data\tests\test_pilot_config.py`

- [ ] **Step 1: Write failing config test**

Create `D:\gaokao_data\tests\test_pilot_config.py`:

```python
import json
from pathlib import Path


def test_pilot_config_has_23_pages():
    config = json.loads(Path("configs/pilot_pages.json").read_text(encoding="utf-8"))
    pages = [item["pdf_page"] for item in config["pages"]]
    assert len(pages) == 23
    assert len(set(pages)) == 23
    assert pages == sorted(pages)


def test_every_page_has_required_labels():
    config = json.loads(Path("configs/pilot_pages.json").read_text(encoding="utf-8"))
    required = {"pdf_page", "chapter", "section", "table_type"}
    for item in config["pages"]:
        assert required <= set(item)
        assert 1 <= item["pdf_page"] <= 912
        assert item["chapter"] in {"chapter1", "chapter2", "chapter3"}
```

- [ ] **Step 2: Run test and confirm it fails**

Run:

```powershell
D:\gaokao_data\.venv-paddleocr\Scripts\python.exe -m pytest D:\gaokao_data\tests\test_pilot_config.py -v
```

Expected: fails because `configs/pilot_pages.json` does not exist yet.

- [ ] **Step 3: Create pilot page config**

Create `D:\gaokao_data\configs\pilot_pages.json`:

```json
{
  "source_pdf": "D:\\gaokao_data\\tmp_input_2025_science_stats.pdf",
  "pages": [
    {"pdf_page": 5, "chapter": "chapter1", "section": "score_lines", "table_type": "chapter1_score_lines"},
    {"pdf_page": 6, "chapter": "chapter1", "section": "score_bands", "table_type": "chapter1_score_bands"},
    {"pdf_page": 10, "chapter": "chapter1", "section": "score_bands", "table_type": "chapter1_score_bands"},
    {"pdf_page": 18, "chapter": "chapter1", "section": "score_bands", "table_type": "chapter1_score_bands"},
    {"pdf_page": 20, "chapter": "chapter2", "section": "batch1_application", "table_type": "chapter2_batch1_application"},
    {"pdf_page": 21, "chapter": "chapter2", "section": "batch1_application", "table_type": "chapter2_batch1_application"},
    {"pdf_page": 22, "chapter": "chapter2", "section": "batch1_application", "table_type": "chapter2_batch1_application"},
    {"pdf_page": 43, "chapter": "chapter2", "section": "batch1_application", "table_type": "chapter2_batch1_application"},
    {"pdf_page": 44, "chapter": "chapter2", "section": "batch2_application", "table_type": "chapter2_batch2_application"},
    {"pdf_page": 45, "chapter": "chapter2", "section": "batch2_application", "table_type": "chapter2_batch2_application"},
    {"pdf_page": 82, "chapter": "chapter2", "section": "vocational_application", "table_type": "chapter2_vocational_application"},
    {"pdf_page": 83, "chapter": "chapter2", "section": "vocational_application", "table_type": "chapter2_vocational_application"},
    {"pdf_page": 122, "chapter": "chapter2", "section": "vocational_application", "table_type": "chapter2_vocational_application"},
    {"pdf_page": 123, "chapter": "chapter3", "section": "batch1_major_admission", "table_type": "chapter3_batch1_major_admission"},
    {"pdf_page": 124, "chapter": "chapter3", "section": "batch1_major_admission", "table_type": "chapter3_batch1_major_admission"},
    {"pdf_page": 125, "chapter": "chapter3", "section": "batch1_major_admission", "table_type": "chapter3_batch1_major_admission"},
    {"pdf_page": 456, "chapter": "chapter3", "section": "batch1_major_admission", "table_type": "chapter3_batch1_major_admission"},
    {"pdf_page": 457, "chapter": "chapter3", "section": "batch2_major_admission", "table_type": "chapter3_batch2_major_admission"},
    {"pdf_page": 458, "chapter": "chapter3", "section": "batch2_major_admission", "table_type": "chapter3_batch2_major_admission"},
    {"pdf_page": 869, "chapter": "chapter3", "section": "batch2_major_admission", "table_type": "chapter3_batch2_major_admission"},
    {"pdf_page": 870, "chapter": "chapter3", "section": "vocational_admission", "table_type": "chapter3_vocational_admission"},
    {"pdf_page": 871, "chapter": "chapter3", "section": "vocational_admission", "table_type": "chapter3_vocational_admission"},
    {"pdf_page": 912, "chapter": "chapter3", "section": "vocational_admission", "table_type": "chapter3_vocational_admission"}
  ]
}
```

- [ ] **Step 4: Run config test**

Run:

```powershell
D:\gaokao_data\.venv-paddleocr\Scripts\python.exe -m pytest D:\gaokao_data\tests\test_pilot_config.py -v
```

Expected: 2 tests pass.

## Task 3: Render Pilot Pages

**Files:**
- Create: `D:\gaokao_data\scripts\pilot_paths.py`
- Create: `D:\gaokao_data\scripts\render_pilot_pages.py`

- [ ] **Step 1: Create shared paths module**

Create `D:\gaokao_data\scripts\pilot_paths.py`:

```python
from pathlib import Path

ROOT = Path(r"D:\gaokao_data")
SOURCE_PDF = ROOT / "tmp_input_2025_science_stats.pdf"
CONFIG_PATH = ROOT / "configs" / "pilot_pages.json"
OUTPUT_DIR = ROOT / "output" / "pilot"
RENDERED_DIR = OUTPUT_DIR / "rendered_pages"
OCR_RAW_DIR = OUTPUT_DIR / "ocr_raw"
TABLES_CSV_DIR = OUTPUT_DIR / "tables_csv"
TABLES_XLSX_DIR = OUTPUT_DIR / "tables_xlsx"
REVIEW_DIR = OUTPUT_DIR / "review"
PDFTOPPM_EXE = Path(
    r"C:\Users\libermanli\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)


def ensure_output_dirs() -> None:
    for path in [RENDERED_DIR, OCR_RAW_DIR, TABLES_CSV_DIR, TABLES_XLSX_DIR, REVIEW_DIR]:
        path.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: Create render script**

Create `D:\gaokao_data\scripts\render_pilot_pages.py`:

```python
import json
import subprocess

from pilot_paths import CONFIG_PATH, PDFTOPPM_EXE, RENDERED_DIR, SOURCE_PDF, ensure_output_dirs


def load_pages() -> list[int]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return [item["pdf_page"] for item in config["pages"]]


def render_page(page: int, dpi: int = 300) -> None:
    output_prefix = RENDERED_DIR / f"page_{page:03d}"
    cmd = [
        str(PDFTOPPM_EXE),
        "-f",
        str(page),
        "-l",
        str(page),
        "-r",
        str(dpi),
        "-png",
        str(SOURCE_PDF),
        str(output_prefix),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    ensure_output_dirs()
    for page in load_pages():
        render_page(page)
        print(f"rendered page {page}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run rendering**

Run:

```powershell
D:\gaokao_data\.venv-paddleocr\Scripts\python.exe D:\gaokao_data\scripts\render_pilot_pages.py
```

Expected: 23 PNG files appear under `D:\gaokao_data\output\pilot\rendered_pages`.

- [ ] **Step 4: Inspect sample file sizes**

Run:

```powershell
Get-ChildItem D:\gaokao_data\output\pilot\rendered_pages\*.png | Select-Object Name,Length | Sort-Object Name
```

Expected: 23 non-empty PNG files, each usually larger than 100KB.

## Task 4: PaddleOCR Smoke Test

**Files:**
- Create: `D:\gaokao_data\scripts\paddleocr_smoke.py`

- [ ] **Step 1: Create smoke test script**

Create `D:\gaokao_data\scripts\paddleocr_smoke.py`:

```python
import json
from pathlib import Path

from paddleocr import PaddleOCR

from pilot_paths import OCR_RAW_DIR, RENDERED_DIR, ensure_output_dirs


def main() -> None:
    ensure_output_dirs()
    image_path = sorted(RENDERED_DIR.glob("page_044-*.png"))[0]
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    result = ocr.predict(str(image_path))
    output_dir = OCR_RAW_DIR / "smoke_page_044"
    output_dir.mkdir(parents=True, exist_ok=True)
    for res in result:
        res.save_to_json(save_path=str(output_dir))
    print(f"image={image_path}")
    print(f"result_pages={len(result)}")
    print(f"output_dir={output_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run smoke test**

Run:

```powershell
D:\gaokao_data\.venv-paddleocr\Scripts\python.exe D:\gaokao_data\scripts\paddleocr_smoke.py
```

Expected: PaddleOCR downloads models if needed, prints a positive result count, and writes JSON under `D:\gaokao_data\output\pilot\ocr_raw\smoke_page_044`.

- [ ] **Step 3: Record elapsed time**

Run:

```powershell
Measure-Command { D:\gaokao_data\.venv-paddleocr\Scripts\python.exe D:\gaokao_data\scripts\paddleocr_smoke.py }
```

Expected: second run is faster than first run because models are cached.

## Task 5: Probe Table Lines Before Full OCR

**Files:**
- Create: `D:\gaokao_data\scripts\table_line_probe.py`

- [ ] **Step 1: Create table-line probe**

Create `D:\gaokao_data\scripts\table_line_probe.py`:

```python
import csv
from pathlib import Path

import numpy as np
from PIL import Image

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
    return {
        "image": path.name,
        "width": width,
        "height": height,
        "table_y0": y0,
        "table_y1": y1,
        "horizontal_line_count": len(horizontal),
        "vertical_line_count": len(thin_vertical),
        "vertical_centers": " ".join(str(cluster[2]) for cluster in thin_vertical),
    }


def main() -> None:
    ensure_output_dirs()
    rows = [analyze_image(path) for path in sorted(RENDERED_DIR.glob("*.png"))]
    output_path = REVIEW_DIR / "table_line_probe.csv"
    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(output_path)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run table-line probe**

Run:

```powershell
D:\gaokao_data\.venv-paddleocr\Scripts\python.exe D:\gaokao_data\scripts\table_line_probe.py
```

Expected: `D:\gaokao_data\output\pilot\review\table_line_probe.csv` exists.

- [ ] **Step 3: Review probe result**

Run:

```powershell
Import-Csv D:\gaokao_data\output\pilot\review\table_line_probe.csv | Format-Table image,horizontal_line_count,vertical_line_count -AutoSize
```

Expected: regular table pages show many horizontal lines and enough vertical line candidates; pages with low counts are flagged for custom handling.

## Task 6: Run Raw OCR On All Pilot Pages

**Files:**
- Create: `D:\gaokao_data\scripts\pilot_extract.py`

- [ ] **Step 1: Create raw OCR batch script**

Create `D:\gaokao_data\scripts\pilot_extract.py`:

```python
import json
import time

from paddleocr import PaddleOCR

from pilot_paths import OCR_RAW_DIR, RENDERED_DIR, ensure_output_dirs


def main() -> None:
    ensure_output_dirs()
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    timing_rows = []
    for image_path in sorted(RENDERED_DIR.glob("*.png")):
        started = time.time()
        result = ocr.predict(str(image_path))
        elapsed = round(time.time() - started, 3)
        output_dir = OCR_RAW_DIR / image_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)
        for res in result:
            res.save_to_json(save_path=str(output_dir))
        timing_rows.append({"image": image_path.name, "elapsed_seconds": elapsed, "result_pages": len(result)})
        print(f"{image_path.name}: {len(result)} result page(s), {elapsed}s")

    timing_path = OCR_RAW_DIR / "timing.json"
    timing_path.write_text(json.dumps(timing_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(timing_path)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run raw OCR batch**

Run:

```powershell
D:\gaokao_data\.venv-paddleocr\Scripts\python.exe D:\gaokao_data\scripts\pilot_extract.py
```

Expected: one JSON directory per rendered page plus `timing.json`.

- [ ] **Step 3: Estimate full-run cost**

Run:

```powershell
$script = @'
import json
from pathlib import Path
rows = json.loads(Path(r"D:\gaokao_data\output\pilot\ocr_raw\timing.json").read_text(encoding="utf-8"))
avg = sum(r["elapsed_seconds"] for r in rows) / len(rows)
print("pilot_pages", len(rows))
print("avg_seconds_per_page", round(avg, 2))
print("estimated_full_hours_for_912_pages", round(avg * 912 / 3600, 2))
'@
$script | D:\gaokao_data\.venv-paddleocr\Scripts\python.exe -
```

Expected: prints a realistic CPU runtime estimate.

## Task 7: Add Validation Rules

**Files:**
- Create: `D:\gaokao_data\tests\test_validation_rules.py`
- Create: `D:\gaokao_data\scripts\validate_pilot.py`

- [ ] **Step 1: Write validation tests**

Create `D:\gaokao_data\tests\test_validation_rules.py`:

```python
from scripts.validate_pilot import normalize_numeric_text, validate_score_row


def test_normalize_numeric_text_fixes_common_ocr_confusions():
    assert normalize_numeric_text("1O3") == "103"
    assert normalize_numeric_text("5B7") == "587"
    assert normalize_numeric_text("l25") == "125"
    assert normalize_numeric_text("4D0") == "400"


def test_validate_score_row_accepts_consistent_application_row():
    row = {
        "year": "2024",
        "batch": "本科二批",
        "min_score": "503",
        "score_diff": "107",
    }
    result = validate_score_row(row)
    assert result["review_status"] == "auto_pass"


def test_validate_score_row_flags_wrong_diff():
    row = {
        "year": "2024",
        "batch": "本科二批",
        "min_score": "503",
        "score_diff": "999",
    }
    result = validate_score_row(row)
    assert result["review_status"] == "needs_review"
    assert "score_diff_mismatch" in result["issues"]
```

- [ ] **Step 2: Create validation module**

Create `D:\gaokao_data\scripts\validate_pilot.py`:

```python
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


def main() -> None:
    print("validation module ready")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run validation tests**

Run:

```powershell
Set-Location D:\gaokao_data
D:\gaokao_data\.venv-paddleocr\Scripts\python.exe -m pytest D:\gaokao_data\tests\test_validation_rules.py -v
```

Expected: 3 tests pass.

## Task 8: Produce Pilot QA Report

**Files:**
- Create: `D:\gaokao_data\output\pilot\review\qa_report.md`

- [ ] **Step 1: Gather metrics**

Run:

```powershell
Get-ChildItem D:\gaokao_data\output\pilot\rendered_pages\*.png | Measure-Object
Get-ChildItem D:\gaokao_data\output\pilot\ocr_raw\*.json | Measure-Object
Import-Csv D:\gaokao_data\output\pilot\review\table_line_probe.csv | Format-Table image,horizontal_line_count,vertical_line_count -AutoSize
```

Expected: rendered page count, OCR JSON count, and table-line summary are visible.

- [ ] **Step 2: Write QA report**

Create `D:\gaokao_data\output\pilot\review\qa_report.md` with these sections:

```markdown
# PaddleOCR Pilot QA Report

## Summary

- Source PDF:
- Pilot page count:
- PaddleOCR version:
- PaddlePaddle version:
- CPU/GPU mode:
- Average seconds per page:
- Estimated full-run hours:

## Table Structure Findings

| Page | Table Type | Boundary Detection | Notes |
|---:|---|---|---|

## OCR Findings

| Page | Table Type | Good Fields | Problem Fields | Notes |
|---:|---|---:|---:|---|

## Numeric Validation Findings

| Table Type | Rows Checked | Auto Pass | Needs Review | Pass Rate |
|---|---:|---:|---:|---:|

## Full Extraction Recommendation

- Recommendation:
- Required rule changes before full run:
- Expected manual review burden:
- Estimated runtime:
```

- [ ] **Step 3: Decide next phase**

Use the decision gates in this plan:

- If the pilot passes, proceed to full extractor design.
- If table-line detection fails mainly on Chapter 3 major tables, add custom line recovery and stateful row parsing before full run.
- If OCR quality fails mainly on numeric fields, switch to cell-level OCR with stronger numeric correction.
- If CPU runtime is too high, split extraction into resumable overnight batches.

## Implementation Notes

- Do not depend on the PDF's existing OCR text layer for final data.
- Keep `tmp_input_2025_science_stats.pdf` as the ASCII input path to avoid Windows encoding issues.
- Keep every intermediate artifact page-addressable, so review can jump from CSV row to source page.
- Do not delete original PDF or previous temporary sample images.
- Prefer resumable scripts: if an output JSON already exists and `--force` is not provided, skip that page.
- Use UTF-8 with BOM (`utf-8-sig`) for CSV files that will be opened in Excel on Windows.

## Self-Review

- Spec coverage: The plan tests local PaddleOCR suitability, machine pressure, sample-page extraction, table-line detection, validation, and a go/no-go report.
- Placeholder scan: No task depends on an undefined output; each file and command has a concrete path.
- Type consistency: Page config keys are `pdf_page`, `chapter`, `section`, and `table_type`; these names are reused consistently.
