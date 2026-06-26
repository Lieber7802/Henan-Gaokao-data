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
