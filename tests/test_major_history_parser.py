import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_major_history_pilot_data import (
    is_output_major_usable,
    parse_major_tokens,
    pivot_rows,
    row_from_profession,
)


def test_parser_does_not_treat_rank_as_school_when_major_name_wraps_before_code():
    tokens = [
        "1110",
        "\u4e2d\u56fd\u4eba\u6c11\u5927\u5b66",
        "01",
        "\u793e\u4f1a\u79d1\u5b66\u8bd5\u9a8c\u73ed(\u7ba1\u7406\u5b66\u79d1\u7c7b)",
        "1",
        "1",
        "667",
        "667",
        "667",
        "156",
        "1509",
        "\u793e\u4f1a\u79d1\u5b66\u8bd5\u9a8c\u73ed(\u5927\u6570\u636e\u6280\u672f\u4e0e\u519c\u6797\u7ecf\u7ba1",
        "02",
        "\u53cc\u4e3b\u5b66\u4f4d\u9879\u76ee\uff09",
        "1",
        "1",
        "655",
        "655",
        "655",
        "144",
        "2955",
        "\u7406\u79d1\u8bd5\u9a8c\u73ed\u7c7b(\u7269\u7406\u5b66\u62d4\u5c16\u73ed\uff0c\u542b\u4e25\u6d4e\u6148",
        "03",
        "\u7269\u7406\u5b66\u82f1\u624d\u73ed)",
        "671",
        "671",
        "671",
        "160",
        "1180",
        "2024",
    ]

    rows = parse_major_tokens(tokens, "\u672c\u79d1\u4e00\u6279", 127)

    assert [row["\u9662\u6821\u4ee3\u7801"] for row in rows] == ["1110", "1110", "1110"]
    assert {row["\u5b66\u6821"] for row in rows} == {"\u4e2d\u56fd\u4eba\u6c11\u5927\u5b66"}
    assert rows[0]["\u4e13\u4e1a"] == "\u793e\u4f1a\u79d1\u5b66\u8bd5\u9a8c\u73ed"
    assert rows[0]["\u6700\u4f4e\u5f55\u53d6\u4f4d\u6b21"] == 1509
    assert rows[1]["\u4e13\u4e1a"].startswith("\u793e\u4f1a\u79d1\u5b66\u8bd5\u9a8c\u73ed")
    assert rows[1]["\u6700\u4f4e\u5f55\u53d6\u4f4d\u6b21"] == 2955
    assert rows[2]["\u4e13\u4e1a"].startswith("\u7406\u79d1\u8bd5\u9a8c\u73ed\u7c7b")
    assert rows[2]["\u6700\u4f4e\u5f55\u53d6\u4f4d\u6b21"] == 1180


def test_parser_keeps_wrapped_school_marker_inside_major_name():
    tokens = [
        "1196",
        "\u6d59\u6c5f\u5927\u5b66\u533b\u5b66\u9662",
        "\u751f\u7269\u533b\u5b66(\u4e2d\u5916\u5408\u4f5c\u529e\u5b66,ZJU-UoE \u8054\u5408",
        "05",
        "5",
        "5",
        "639",
        "635.4",
        "632",
        "121",
        "8139",
        "\u5b66\u9662\uff0c\u542b\u751f\u7269\u4fe1\u606f\uff09",
        "2023",
        "01",
        "\u533b\u5b66\u8bd5\u9a8c\u73ed\u7c7b(\u5b66\u52365\u5e74)",
        "2",
        "2",
        "668",
        "666",
        "664",
        "150",
        "1571",
    ]

    rows = parse_major_tokens(tokens, "\u672c\u79d1\u4e00\u6279", 146)

    assert [row["\u9662\u6821\u4ee3\u7801"] for row in rows] == ["1196", "1196"]
    assert {row["\u5b66\u6821"] for row in rows} == {"\u6d59\u6c5f\u5927\u5b66\u533b\u5b66\u9662"}
    assert rows[0]["\u4e13\u4e1a"] == "\u751f\u7269\u533b\u5b66"
    assert "\u5b66\u9662\uff0c\u542b\u751f\u7269\u4fe1\u606f" in rows[0]["\u5907\u6ce8"]
    assert rows[1]["\u4e13\u4e1a"] == "\u533b\u5b66\u8bd5\u9a8c\u73ed\u7c7b"


def test_parser_does_not_prefix_closing_fragment_to_next_major():
    tokens = [
        "1250",
        "\u7535\u5b50\u79d1\u6280\u5927\u5b66",
        "\u7ecf\u6d4e\u7ba1\u7406\u8bd5\u9a8c\u73ed(\u7ba1\u7406\u4e0e\u7535\u5b50\u5de5\u7a0b\u53cc\u5b66\u4f4d",
        "01",
        "12",
        "12",
        "647",
        "645.9",
        "645",
        "134",
        "4744",
        "2024",
        "\u57f9\u517b\uff09",
        "02",
        "\u5de5\u79d1\u8bd5\u9a8c\u73ed(\u7535\u5b50\u5de5\u7a0b\u7c7b)",
        "17",
        "17",
        "668",
        "661.2",
        "659",
        "145",
        "2405",
    ]

    rows = parse_major_tokens(tokens, "\u672c\u79d1\u4e00\u6279", 154)

    assert [row["\u5b66\u6821"] for row in rows] == ["\u7535\u5b50\u79d1\u6280\u5927\u5b66", "\u7535\u5b50\u79d1\u6280\u5927\u5b66"]
    assert rows[0]["\u4e13\u4e1a"] == "\u7ecf\u6d4e\u7ba1\u7406\u8bd5\u9a8c\u73ed"
    assert "\u57f9\u517b" in rows[0]["\u5907\u6ce8"]
    assert rows[1]["\u4e13\u4e1a"] == "\u5de5\u79d1\u8bd5\u9a8c\u73ed"
    assert rows[1]["\u5907\u6ce8"] == "\u7535\u5b50\u5de5\u7a0b\u7c7b"


def test_parser_carries_school_across_pages_and_rejects_college_suffix_as_school():
    state = {
        "school_code": "1250",
        "school_name": "\u7535\u5b50\u79d1\u6280\u5927\u5b66",
        "current_year": "2023",
        "seen_year_for_school": True,
        "last_profession_order": None,
    }
    tokens = [
        "\u96c6\u6210\u7535\u8def\u8bbe\u8ba1\u4e0e\u96c6\u6210\u7cfb\u7edf(\u56fd\u5bb6\u793a\u8303\u6027\u5fae",
        "01",
        "29",
        "29",
        "649",
        "645.1",
        "643",
        "129",
        "4496",
        "\u7535\u5b50\u5b66\u9662\uff09",
        "02",
        "\u8f6f\u4ef6\u5de5\u7a0b(\u5de5\u4e1a\u8f6f\u4ef6)",
        "7",
        "7",
        "643",
        "642.3",
        "642",
        "128",
        "4712",
    ]

    rows = parse_major_tokens(tokens, "\u672c\u79d1\u4e00\u6279", 156, state=state)

    assert [row["\u5b66\u6821"] for row in rows] == ["\u7535\u5b50\u79d1\u6280\u5927\u5b66", "\u7535\u5b50\u79d1\u6280\u5927\u5b66"]
    assert rows[0]["\u4e13\u4e1a"] == "\u96c6\u6210\u7535\u8def\u8bbe\u8ba1\u4e0e\u96c6\u6210\u7cfb\u7edf"
    assert "\u7535\u5b50\u5b66\u9662" in rows[0]["\u5907\u6ce8"]
    assert rows[1]["\u4e13\u4e1a"] == "\u8f6f\u4ef6\u5de5\u7a0b"
    assert rows[1]["\u5907\u6ce8"] == "\u5de5\u4e1a\u8f6f\u4ef6"


def test_parser_handles_major_prefix_before_code_and_suffix_after_numbers():
    tokens = [
        "1445",
        "\u4e0a\u6d77\u8d22\u7ecf\u5927\u5b66",
        "06",
        "\u6295\u8d44\u5b66",
        "1",
        "1",
        "627",
        "627",
        "627",
        "113",
        "8771",
        "\u6295\u8d44\u5b66(\u53cc\u5b66\u58eb\u5b66\u4f4d\u3001\u516c\u7ba1\u5b66\u9662\u548c\u6570\u5b66\u5b66",
        "07",
        "2",
        "2",
        "627",
        "626.5",
        "626",
        "112",
        "9098",
        "\u9662\u57f9\u517b\uff09",
        "08",
        "\u6570\u5b66\u7c7b",
        "2",
        "2",
        "631",
        "630",
        "629",
        "115",
        "8494",
    ]

    rows = parse_major_tokens(tokens, "\u672c\u79d1\u4e00\u6279", 194)

    assert [row["\u5b66\u6821"] for row in rows] == [
        "\u4e0a\u6d77\u8d22\u7ecf\u5927\u5b66",
        "\u4e0a\u6d77\u8d22\u7ecf\u5927\u5b66",
        "\u4e0a\u6d77\u8d22\u7ecf\u5927\u5b66",
    ]
    assert rows[1]["\u4e13\u4e1a"] == "\u6295\u8d44\u5b66"
    assert "\u516c\u7ba1\u5b66\u9662\u548c\u6570\u5b66\u5b66\u9662\u57f9\u517b" in rows[1]["\u5907\u6ce8"]
    assert rows[2]["\u4e13\u4e1a"] == "\u6570\u5b66\u7c7b"


def test_single_character_major_fragment_is_not_output_usable():
    assert not is_output_major_usable("\u5fc3")
    assert is_output_major_usable("\u5fc3\u7406\u5b66")


def test_implausible_batch1_numeric_row_is_sent_to_review():
    row = row_from_profession(
        batch="\u672c\u79d1\u4e00\u6279",
        school_code="9999",
        school_name="\u6d4b\u8bd5\u5927\u5b66",
        year="2023",
        profession_code="01",
        profession_name="\u4e34\u5e8a\u533b\u5b66",
        number_tokens=["3", "1", "2", "2", "640", "640", "640", "140", "14"],
        source_page=999,
    )

    assert row is not None
    assert row["review_status"] == "needs_review_implausible_numeric"
    wide_rows, review_rows = pivot_rows([row])
    assert wide_rows == []
    assert review_rows == [row]


def test_year_backfill_preserves_implausible_numeric_status():
    tokens = [
        "9999",
        "\u6d4b\u8bd5\u5927\u5b66",
        "01",
        "\u4e34\u5e8a\u533b\u5b66",
        "3",
        "1",
        "2",
        "2",
        "640",
        "640",
        "640",
        "140",
        "14",
        "2023",
    ]

    rows = parse_major_tokens(tokens, "\u672c\u79d1\u4e00\u6279", 999)

    assert rows[0]["\u5e74\u4efd"] == 2023
    assert rows[0]["review_status"] == "needs_review_implausible_numeric"
