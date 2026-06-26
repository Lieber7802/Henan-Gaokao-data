from pathlib import Path

ROOT = Path(r"D:\gaokao_data")
SOURCE_PDF = ROOT / "tmp_input_2025_science_stats.pdf"
ORIGINAL_PDF = ROOT / "2025年理科录取统计.pdf"
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
