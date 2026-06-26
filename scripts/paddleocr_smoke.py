from __future__ import annotations

import os

os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from paddleocr import PaddleOCR

try:
    from .ocr_result_utils import extract_ocr_lines, find_json_files, load_saved_result
    from .pilot_paths import OCR_RAW_DIR, RENDERED_DIR, ensure_output_dirs
except ImportError:
    from ocr_result_utils import extract_ocr_lines, find_json_files, load_saved_result
    from pilot_paths import OCR_RAW_DIR, RENDERED_DIR, ensure_output_dirs


def main() -> None:
    ensure_output_dirs()
    matches = sorted(RENDERED_DIR.glob("page_044-*.png"))
    if not matches:
        raise FileNotFoundError("Render page 44 before running the PaddleOCR smoke test.")

    image_path = matches[0]
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_detection_model_name=os.environ.get("PILOT_TEXT_DETECTION_MODEL_NAME", "PP-OCRv6_tiny_det"),
        text_recognition_model_name=os.environ.get("PILOT_TEXT_RECOGNITION_MODEL_NAME", "PP-OCRv6_tiny_rec"),
    )
    result = ocr.predict(str(image_path))
    output_dir = OCR_RAW_DIR / "smoke_page_044"
    output_dir.mkdir(parents=True, exist_ok=True)
    for res in result:
        res.save_to_json(save_path=str(output_dir))

    line_count = 0
    for json_path in find_json_files(output_dir):
        line_count += len(extract_ocr_lines(load_saved_result(json_path)))

    print(f"image={image_path}")
    print(f"result_pages={len(result)}")
    print(f"lines={line_count}")
    print(f"output_dir={output_dir}")


if __name__ == "__main__":
    main()
