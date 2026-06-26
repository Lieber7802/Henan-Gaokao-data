import json
import subprocess
from pathlib import Path

try:
    from .pilot_paths import CONFIG_PATH, PDFTOPPM_EXE, RENDERED_DIR, SOURCE_PDF, ensure_output_dirs
except ImportError:
    from pilot_paths import CONFIG_PATH, PDFTOPPM_EXE, RENDERED_DIR, SOURCE_PDF, ensure_output_dirs


def load_pages() -> list[int]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return [item["pdf_page"] for item in config["pages"]]


def expected_output(page: int) -> Path:
    return RENDERED_DIR / f"page_{page:03d}-{page:03d}.png"


def render_page(page: int, dpi: int = 300, force: bool = False) -> Path:
    output_path = expected_output(page)
    if output_path.exists() and not force:
        print(f"skipped page {page}: {output_path}")
        return output_path

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
    print(f"rendered page {page}: {output_path}")
    return output_path


def main() -> None:
    ensure_output_dirs()
    for page in load_pages():
        render_page(page)


if __name__ == "__main__":
    main()
