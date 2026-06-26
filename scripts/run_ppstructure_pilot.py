from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from pathlib import Path
from typing import Any

os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

try:
    from .ocr_result_utils import result_to_dict, unwrap_result
    from .pilot_paths import RENDERED_DIR
    from .render_pilot_pages import render_page
except ImportError:
    from ocr_result_utils import result_to_dict, unwrap_result
    from pilot_paths import RENDERED_DIR
    from render_pilot_pages import render_page

from paddleocr import PPStructureV3

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "ppstructure_pilot_sections.json"
OUTPUT_DIR = ROOT / "output" / "ppstructure_pilot"
RAW_DIR = OUTPUT_DIR / "raw"
REVIEW_DIR = OUTPUT_DIR / "review"
TIMING_PATH = REVIEW_DIR / "ppstructure_timing.json"


def configure_output_dir(output_dir: Path) -> None:
    global OUTPUT_DIR, RAW_DIR, REVIEW_DIR, TIMING_PATH
    OUTPUT_DIR = output_dir
    RAW_DIR = OUTPUT_DIR / "raw"
    REVIEW_DIR = OUTPUT_DIR / "review"
    TIMING_PATH = REVIEW_DIR / "ppstructure_timing.json"


def load_config(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    return json.loads(config_path.read_text(encoding="utf-8"))


def iter_target_sections(config: dict[str, Any], only_sections: set[str] | None, only_pages: set[int] | None) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for section in config["sections"]:
        if only_sections and section["section_id"] not in only_sections:
            continue
        pages = [int(page) for page in section["pdf_pages"]]
        if only_pages:
            pages = [page for page in pages if page in only_pages]
        if not pages:
            continue
        copied = dict(section)
        copied["pdf_pages"] = pages
        sections.append(copied)
    return sections


def ensure_section_dirs(section_id: str) -> dict[str, Path]:
    dirs = {
        "json": RAW_DIR / section_id / "json",
        "markdown": RAW_DIR / section_id / "markdown",
        "html": RAW_DIR / section_id / "html",
        "xlsx": RAW_DIR / section_id / "xlsx",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def page_stem(page: int) -> str:
    return f"page_{page:03d}-{page:03d}"


def expected_image(page: int) -> Path:
    return RENDERED_DIR / f"{page_stem(page)}.png"


def ensure_image(page: int, force_render: bool = False) -> Path:
    image_path = expected_image(page)
    if image_path.exists() and not force_render:
        return image_path
    return render_page(page, force=force_render)


def create_pipeline(model_profile: str = "cpu-medium") -> PPStructureV3:
    kwargs: dict[str, Any] = {
        "use_table_recognition": True,
        "use_formula_recognition": False,
        "use_seal_recognition": False,
        "use_chart_recognition": False,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        "use_region_detection": False,
        "layout_detection_model_name": "PP-DocLayout_plus-L",
        "text_recognition_batch_size": 1,
        "textline_orientation_batch_size": 1,
        "device": "cpu",
        "enable_mkldnn": False,
    }
    if model_profile == "cpu-light":
        kwargs["layout_detection_model_name"] = "PP-DocLayout-S"
        kwargs.update(
            {
                "text_detection_model_name": "PP-OCRv6_tiny_det",
                "text_recognition_model_name": "PP-OCRv6_tiny_rec",
            }
        )
    elif model_profile == "cpu-medium":
        kwargs.update(
            {
                "text_detection_model_name": "PP-OCRv6_medium_det",
                "text_recognition_model_name": "PP-OCRv6_medium_rec",
            }
        )
    elif model_profile == "cpu-server":
        kwargs["layout_detection_model_name"] = "PP-DocLayout-S"
    else:
        raise ValueError(f"Unsupported model profile: {model_profile}")
    try:
        return PPStructureV3(**kwargs)
    except TypeError:
        kwargs.pop("enable_mkldnn", None)
        return PPStructureV3(**kwargs)


def normalize_predictions(predictions: Any) -> list[Any]:
    if predictions is None:
        return []
    if isinstance(predictions, list):
        return predictions
    if isinstance(predictions, tuple):
        return list(predictions)
    try:
        return list(predictions)
    except TypeError:
        return [predictions]


def table_count_from_result(data: dict[str, Any]) -> int:
    res = unwrap_result(data)
    table_res_list = res.get("table_res_list") or []
    if isinstance(table_res_list, list):
        return len(table_res_list)
    return 0


def table_text_from_result(data: dict[str, Any]) -> str:
    res = unwrap_result(data)
    chunks: list[str] = []
    for block in res.get("parsing_res_list") or []:
        if isinstance(block, dict) and block.get("block_content"):
            chunks.append(str(block["block_content"]))
    for table in res.get("table_res_list") or []:
        if not isinstance(table, dict):
            continue
        pred_html = table.get("pred_html")
        if pred_html:
            chunks.append(str(pred_html))
        table_ocr = table.get("table_ocr_pred") or {}
        if isinstance(table_ocr, dict):
            chunks.extend(str(text) for text in table_ocr.get("rec_texts") or [])
    overall_ocr = res.get("overall_ocr_res") or {}
    if isinstance(overall_ocr, dict):
        chunks.extend(str(text) for text in overall_ocr.get("rec_texts") or [])
    return "\n".join(chunks)


def save_result_variants(result: Any, section_dirs: dict[str, Path]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    save_calls = {
        "json": "save_to_json",
        "markdown": "save_to_markdown",
        "html": "save_to_html",
        "xlsx": "save_to_xlsx",
    }
    for name, method_name in save_calls.items():
        method = getattr(result, method_name, None)
        if not callable(method):
            statuses[name] = "method_missing"
            continue
        try:
            method(str(section_dirs[name]))
            statuses[name] = "ok"
        except Exception as exc:  # noqa: BLE001 - save failures are review evidence.
            statuses[name] = f"error: {type(exc).__name__}: {exc}"
    return statuses


def output_files_for_page(section_dirs: dict[str, Path], stem: str, suffix: str) -> list[Path]:
    key = "markdown" if suffix == ".md" else suffix.lstrip(".")
    return sorted(section_dirs[key].glob(f"{stem}*{suffix}"))


def load_existing_timing(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or TIMING_PATH
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_timing(rows: list[dict[str, Any]], path: Path | None = None) -> None:
    path = path or TIMING_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def run_page(
    pipeline: PPStructureV3,
    section: dict[str, Any],
    page: int,
    force_render: bool = False,
    model_profile: str = "cpu-medium",
) -> dict[str, Any]:
    section_id = section["section_id"]
    section_dirs = ensure_section_dirs(section_id)
    image_path = ensure_image(page, force_render=force_render)
    started = time.perf_counter()
    row: dict[str, Any] = {
        "section_id": section_id,
        "section_name_cn": section["section_name_cn"],
        "table_family": section["table_family"],
        "expected_final_sheet": section["expected_final_sheet"],
        "pdf_page": page,
        "image_path": str(image_path),
        "model_profile": model_profile,
        "status": "started",
    }
    try:
        predictions = normalize_predictions(pipeline.predict(str(image_path)))
        table_count = 0
        has_table_res_list = False
        combined_text_parts: list[str] = []
        save_statuses: list[dict[str, str]] = []
        for result in predictions:
            data = result_to_dict(result)
            res = unwrap_result(data)
            if isinstance(res.get("table_res_list"), list):
                has_table_res_list = True
            table_count += table_count_from_result(data)
            combined_text_parts.append(table_text_from_result(data))
            save_statuses.append(save_result_variants(result, section_dirs))

        stem = page_stem(page)
        row.update(
            {
                "status": "ok",
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "prediction_count": len(predictions),
                "table_count": table_count,
                "has_table_res_list": has_table_res_list,
                "has_json": bool(output_files_for_page(section_dirs, stem, ".json")),
                "has_markdown": bool(output_files_for_page(section_dirs, stem, ".md")),
                "has_html": bool(output_files_for_page(section_dirs, stem, ".html")),
                "has_xlsx": bool(output_files_for_page(section_dirs, stem, ".xlsx")),
                "save_statuses": save_statuses,
                "contains_shoudu_tiyu": "首都体育学院" in "\n".join(combined_text_parts),
                "contains_tianjin_tiyu": "天津体育学院" in "\n".join(combined_text_parts),
                "contains_beijing_tiyu": "北京体育大学" in "\n".join(combined_text_parts),
            }
        )
    except Exception as exc:  # noqa: BLE001 - failures are written to the decision report.
        row.update(
            {
                "status": "error",
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(limit=8),
            }
        )
    return row


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a PP-StructureV3 section-level pilot.")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--sections", nargs="*", help="Optional section_id filter.")
    parser.add_argument("--pages", nargs="*", type=int, help="Optional PDF page filter.")
    parser.add_argument("--page-from", type=int, help="Inclusive PDF page start for a one-section run.")
    parser.add_argument("--page-to", type=int, help="Inclusive PDF page end for a one-section run.")
    parser.add_argument("--section-id", default="chapter3_batch1_major_admission")
    parser.add_argument("--section-name-cn", default="第三章本科一批分专业录取")
    parser.add_argument("--table-family", default="major_admission")
    parser.add_argument("--expected-final-sheet", default="06_本科一批分专业录取")
    parser.add_argument("--model-profile", choices=["cpu-medium", "cpu-light", "cpu-server"], default="cpu-medium")
    parser.add_argument("--force-render", action="store_true")
    parser.add_argument("--skip-existing-ok", action="store_true", help="Skip pages already recorded as ok in timing JSON.")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    configure_output_dir(args.output_dir.resolve())
    if args.page_from is not None or args.page_to is not None:
        if args.page_from is None or args.page_to is None:
            raise SystemExit("--page-from and --page-to must be provided together.")
        if args.page_from > args.page_to:
            raise SystemExit("--page-from must be <= --page-to.")
        pages = list(range(args.page_from, args.page_to + 1))
        if args.pages:
            selected = set(args.pages)
            pages = [page for page in pages if page in selected]
        sections = [
            {
                "section_id": args.section_id,
                "section_name_cn": args.section_name_cn,
                "table_family": args.table_family,
                "expected_final_sheet": args.expected_final_sheet,
                "pdf_pages": pages,
            }
        ]
    else:
        config = load_config(args.config)
        sections = iter_target_sections(config, set(args.sections or []) or None, set(args.pages or []) or None)
    if not sections:
        raise SystemExit("No target sections/pages selected.")

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    existing_rows = load_existing_timing()
    existing_ok = {
        (row.get("section_id"), int(row.get("pdf_page", -1)))
        for row in existing_rows
        if row.get("status") == "ok"
    }
    rows = list(existing_rows)
    pipeline = create_pipeline(args.model_profile)

    for section in sections:
        ensure_section_dirs(section["section_id"])
        for page in section["pdf_pages"]:
            key = (section["section_id"], int(page))
            if args.skip_existing_ok and key in existing_ok:
                print(f"skip existing ok: {section['section_id']} page {page}", flush=True)
                continue
            print(f"PP-StructureV3 predict: {section['section_id']} page {page}", flush=True)
            row = run_page(
                pipeline,
                section,
                int(page),
                force_render=args.force_render,
                model_profile=args.model_profile,
            )
            rows = [
                existing
                for existing in rows
                if not (existing.get("section_id") == section["section_id"] and int(existing.get("pdf_page", -1)) == int(page))
            ]
            rows.append(row)
            rows.sort(key=lambda item: (str(item.get("section_id", "")), int(item.get("pdf_page", 0))))
            write_timing(rows)
            if row.get("status") == "error":
                print(f"ERROR page {page}: {row.get('error')}", flush=True)
            else:
                print(
                    "ok page {page}: tables={tables}, xlsx={xlsx}, html={html}, seconds={seconds}".format(
                        page=page,
                        tables=row.get("table_count"),
                        xlsx=row.get("has_xlsx"),
                        html=row.get("has_html"),
                        seconds=row.get("elapsed_seconds"),
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
