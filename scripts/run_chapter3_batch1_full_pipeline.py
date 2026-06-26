from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "ppstructure_full" / "chapter3_batch1"
REVIEW_DIR = OUTPUT_DIR / "review"
PREVIEW_DIR = OUTPUT_DIR / "preview"
DATA_JSON = REVIEW_DIR / "major_history_chapter3_batch1_data.json"
WORKBOOK_PATH = PREVIEW_DIR / "major_history_chapter3_batch1.xlsx"
STATUS_PATH = REVIEW_DIR / "pipeline_status.json"
PYTHON = Path(sys.executable)


def write_status(status: str, step: str, extra: dict | None = None) -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "step": step,
        "updated_at_epoch": time.time(),
        "output_dir": str(OUTPUT_DIR),
        "workbook_path": str(WORKBOOK_PATH),
    }
    if extra:
        payload.update(extra)
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_command(step: str, command: list[str]) -> None:
    write_status("running", step, {"command": command})
    result = subprocess.run(command, cwd=str(ROOT), check=False)
    if result.returncode == 0:
        return
    write_status("failed", step, {"returncode": result.returncode, "command": command})
    raise SystemExit(result.returncode)


def main() -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()
    write_status("running", "ppstructure_extract", {"started_at_epoch": started})

    run_command(
        "ppstructure_extract",
        [
            str(PYTHON),
            "scripts/run_ppstructure_pilot.py",
            "--page-from",
            "123",
            "--page-to",
            "456",
            "--section-id",
            "chapter3_batch1_major_admission",
            "--section-name-cn",
            "第三章本科一批分专业录取",
            "--table-family",
            "major_admission",
            "--expected-final-sheet",
            "06_本科一批分专业录取",
            "--output-dir",
            str(OUTPUT_DIR),
            "--model-profile",
            "cpu-medium",
            "--skip-existing-ok",
        ],
    )

    run_command(
        "build_wide_table_data",
        [
            str(PYTHON),
            "scripts/build_major_history_pilot_data.py",
            "--raw-dir",
            str(OUTPUT_DIR / "raw"),
            "--output-json",
            str(DATA_JSON),
            "--sections",
            "chapter3_batch1_major_admission",
        ],
    )

    run_command(
        "build_workbook",
        [
            str(PYTHON),
            "scripts/build_major_history_workbook.py",
            str(DATA_JSON),
            str(WORKBOOK_PATH),
        ],
    )

    write_status(
        "complete",
        "done",
        {
            "started_at_epoch": started,
            "elapsed_seconds": round(time.time() - started, 3),
            "data_json": str(DATA_JSON),
        },
    )
    print(WORKBOOK_PATH)


if __name__ == "__main__":
    main()
