from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "output" / "ppstructure_pilot" / "raw"
REVIEW_DIR = ROOT / "output" / "ppstructure_pilot" / "review"
OUTPUT_JSON = REVIEW_DIR / "major_history_pilot_data.json"

TARGET_SECTIONS = {
    "chapter3_batch1_major_admission": "本科一批",
    "chapter3_batch2_major_admission": "本科二批",
}

YEAR_PATTERN = re.compile(r"20(?:23|24|25)")
SCHOOL_CODE_PATTERN = re.compile(r"\d{4}")
PROFESSION_CODE_PATTERN = re.compile(r"[A-Z]?\d{1,3}")
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
HEADER_TOKENS = {
    "专业",
    "年份",
    "专业名称",
    "公布计划",
    "录取人数",
    "公布计划录取人数",
    "最高分",
    "平均分",
    "最低分",
    "与分数",
    "最低分位次",
    "代码",
    "线差值",
}
CLOSING_BRACKETS = "）)]】"
OPENING_BRACKETS = "（([【"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_number(value: str) -> int | float | None:
    value = clean_text(value)
    if not NUMBER_PATTERN.fullmatch(value):
        return None
    number = float(value)
    return int(number) if number.is_integer() else number


def is_year(token: str) -> bool:
    return bool(YEAR_PATTERN.fullmatch(clean_text(token)))


def is_school_code(token: str) -> bool:
    token = clean_text(token)
    return bool(SCHOOL_CODE_PATTERN.fullmatch(token)) and not is_year(token)


def has_chinese(token: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", clean_text(token)))


def chinese_char_count(token: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", clean_text(token)))


def bracket_balance(token: str) -> int:
    token = clean_text(token)
    return sum(token.count(char) for char in OPENING_BRACKETS) - sum(token.count(char) for char in CLOSING_BRACKETS)


def is_header_token(token: str) -> bool:
    token = clean_text(token)
    if not token:
        return True
    if token in HEADER_TOKENS:
        return True
    header_markers = ("专业名称", "公布计划", "录取人数", "最高分", "平均分", "最低分位次", "线差值")
    return len(token) <= 12 and any(marker in token for marker in header_markers)


def looks_like_school_name(token: str) -> bool:
    token = clean_text(token)
    if not has_chinese(token) or is_header_token(token):
        return False
    if token[0] in CLOSING_BRACKETS:
        return False
    if token.startswith(("学院", "学校", "校区", "研究院")):
        return False
    if ("," in token or "，" in token) and "大学" not in token:
        return False
    if bracket_balance(token) != 0 and "大学" not in token:
        return False
    if "大学" in token:
        return True
    return token.endswith(("学院", "学校", "研究院"))


def is_profession_code(token: str) -> bool:
    token = clean_text(token)
    return bool(PROFESSION_CODE_PATTERN.fullmatch(token)) and not is_school_code(token) and not is_year(token)


def is_school_start(tokens: list[str], index: int) -> bool:
    return index + 1 < len(tokens) and is_school_code(tokens[index]) and looks_like_school_name(tokens[index + 1])


def is_profession_start(tokens: list[str], index: int) -> bool:
    if index + 1 >= len(tokens):
        return False
    if not is_profession_code(tokens[index]) or not has_chinese(tokens[index + 1]):
        return False
    return not is_school_start(tokens, index)


def is_prefixed_profession_start(tokens: list[str], index: int) -> bool:
    if index + 1 >= len(tokens):
        return False
    token = clean_text(tokens[index])
    if not has_chinese(token) or is_header_token(token) or looks_like_school_name(token):
        return False
    if token[0] in CLOSING_BRACKETS or bracket_balance(token) < 0:
        return False
    return is_profession_code(tokens[index + 1]) and not is_school_start(tokens, index + 1)


def is_major_suffix_fragment(token: str) -> bool:
    token = clean_text(token)
    if not token or not has_chinese(token):
        return False
    return token[0] in CLOSING_BRACKETS or bracket_balance(token) < 0


def is_profession_name_fragment(token: str) -> bool:
    token = clean_text(token)
    if not token or is_header_token(token) or is_year(token) or is_profession_code(token):
        return False
    if parse_number(token) is not None:
        return False
    return has_chinese(token) and not looks_like_school_name(token)


def join_profession_parts(parts: list[str]) -> str:
    return clean_text("".join(clean_text(part) for part in parts if clean_text(part)))


def profession_order(token: str) -> int | None:
    token = clean_text(token)
    match = re.search(r"\d+", token)
    return int(match.group(0)) if match else None


def split_major_and_remark(name: str) -> tuple[str, str]:
    name = clean_text(name)
    if not name:
        return "", ""

    bracket_match = re.search(r"(.+?)[（(](.+?)[）)]$", name)
    if bracket_match:
        return clean_text(bracket_match.group(1)), clean_text(bracket_match.group(2))

    square_match = re.search(r"(.+?)(\[.+\].*)$", name)
    if square_match:
        return clean_text(square_match.group(1)), clean_text(square_match.group(2))

    # Common unbracketed qualifiers in the source tables.
    qualifier_patterns = [
        r"(.*?)(中外合作办学.*)$",
        r"(.*?)(较高收费.*)$",
        r"(.*?)(学制\d+年.*)$",
        r"(.*?)(本博连读.*)$",
        r"(.*?)(5\+3一体化.*)$",
        r"(.*?)(卓越.*)$",
    ]
    for pattern in qualifier_patterns:
        match = re.fullmatch(pattern, name)
        if match and match.group(1):
            return clean_text(match.group(1)), clean_text(match.group(2))

    return name, ""


def table_tokens_from_json(json_path: Path) -> list[str]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    res = data.get("res", data)
    tokens: list[str] = []
    for table in res.get("table_res_list") or []:
        table_ocr = table.get("table_ocr_pred") or {}
        tokens.extend(clean_text(token) for token in table_ocr.get("rec_texts") or [])
    return [token for token in tokens if token]


def numeric_values(tokens: list[str]) -> list[int | float]:
    values: list[int | float] = []
    for token in tokens:
        number = parse_number(token)
        if number is not None:
            values.append(number)
    return values


def row_from_profession(
    *,
    batch: str,
    school_code: str,
    school_name: str,
    year: str,
    profession_code: str,
    profession_name: str,
    number_tokens: list[str],
    source_page: int,
) -> dict[str, Any] | None:
    name_fragments = [token for token in number_tokens if is_profession_name_fragment(token)]
    profession_name = join_profession_parts([profession_name, *name_fragments])
    numbers = numeric_values(number_tokens)
    if len(numbers) < 5:
        return None

    # The final three numeric fields are consistently minimum score, line difference, and rank.
    min_score = numbers[-3]
    min_rank = numbers[-1]
    if not (100 <= float(min_score) <= 750):
        return None
    if float(min_rank) < 1:
        return None

    major, remark = split_major_and_remark(profession_name)
    status = "candidate"
    if not year:
        status = "needs_review_missing_year"
    if not is_admission_numeric_plausible(batch, min_score, min_rank):
        status = "needs_review_implausible_numeric"
    return {
        "批次": batch,
        "院校代码": school_code,
        "学校": school_name,
        "专业代码": profession_code,
        "专业": major,
        "备注": remark,
        "年份": int(year) if year else None,
        "最低录取分数": min_score,
        "最低录取位次": int(min_rank) if float(min_rank).is_integer() else min_rank,
        "source_page": source_page,
        "review_status": status,
    }


def is_admission_numeric_plausible(batch: str, min_score: int | float, min_rank: int | float) -> bool:
    score = float(min_score)
    rank = float(min_rank)
    if "本科一批" in batch:
        if score < 450:
            return False
        if rank < 50 and score < 690:
            return False
    elif "本科二批" in batch:
        if score < 300:
            return False
    return True


def append_profession_fragment(row: dict[str, Any], fragment: str) -> None:
    current_name = clean_text(row.get("专业", ""))
    current_remark = clean_text(row.get("备注", ""))
    if current_remark:
        current_name = f"{current_name}({current_remark})"
    major, remark = split_major_and_remark(join_profession_parts([current_name, fragment]))
    row["专业"] = major
    row["备注"] = remark


def is_output_major_usable(major: str) -> bool:
    major = clean_text(major)
    if not major or chinese_char_count(major) < 2 or is_header_token(major):
        return False
    if major[0] in CLOSING_BRACKETS or bracket_balance(major) != 0:
        return False
    return True


def parse_major_tokens(
    tokens: list[str],
    batch: str,
    source_page: int,
    state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pending_without_year: list[dict[str, Any]] = []
    initial_state = state if state is not None else {}
    school_code = clean_text(initial_state.get("school_code", ""))
    school_name = clean_text(initial_state.get("school_name", ""))
    current_year = clean_text(initial_state.get("current_year", ""))
    seen_year_for_school = bool(initial_state.get("seen_year_for_school", False))
    last_profession_order = initial_state.get("last_profession_order")
    index = 0

    def backfill_pending(year: str) -> None:
        for item in pending_without_year:
            if item["年份"] is None:
                item["年份"] = int(year)
                if item["review_status"] == "needs_review_missing_year":
                    item["review_status"] = "candidate_year_backfilled"
        pending_without_year.clear()

    while index < len(tokens):
        token = tokens[index]
        if is_school_start(tokens, index):
            if current_year:
                backfill_pending(current_year)
            school_code = tokens[index]
            school_name = tokens[index + 1]
            current_year = ""
            seen_year_for_school = False
            pending_without_year = []
            last_profession_order = None
            index += 2
            continue

        if is_year(token):
            current_year = token
            if not seen_year_for_school:
                backfill_pending(token)
            else:
                backfill_pending(token)
            seen_year_for_school = True
            last_profession_order = None
            index += 1
            continue

        if rows and is_major_suffix_fragment(token):
            append_profession_fragment(rows[-1], token)
            index += 1
            continue

        profession_prefix = ""
        profession_index = index
        if school_code and is_prefixed_profession_start(tokens, index):
            profession_prefix = tokens[index]
            profession_index = index + 1
        if school_code and (profession_prefix or is_profession_start(tokens, index)):
            profession_code = tokens[profession_index]
            current_order = profession_order(profession_code)
            if (
                current_year
                and seen_year_for_school
                and last_profession_order is not None
                and current_order is not None
                and current_order <= last_profession_order
            ):
                # Some PP-StructureV3 token streams place the next year label after
                # the first few rows of that year. A profession-code reset is a
                # strong signal that a new year block has begun.
                current_year = ""
            profession_name = join_profession_parts(
                [profession_prefix] if profession_prefix else [tokens[profession_index + 1]]
            )
            number_start = profession_index + 1 if profession_prefix else profession_index + 2
            end = number_start
            while end < len(tokens):
                if (
                    is_year(tokens[end])
                    or is_school_start(tokens, end)
                    or is_profession_start(tokens, end)
                    or is_prefixed_profession_start(tokens, end)
                ):
                    break
                end += 1
            row = row_from_profession(
                batch=batch,
                school_code=school_code,
                school_name=school_name,
                year=current_year,
                profession_code=profession_code,
                profession_name=profession_name,
                number_tokens=tokens[number_start:end],
                source_page=source_page,
            )
            if row:
                rows.append(row)
                if row["年份"] is None:
                    pending_without_year.append(row)
            last_profession_order = current_order
            index = end
            continue

        index += 1

    if current_year:
        backfill_pending(current_year)
    if state is not None:
        state.update(
            {
                "school_code": school_code,
                "school_name": school_name,
                "current_year": current_year,
                "seen_year_for_school": seen_year_for_school,
                "last_profession_order": last_profession_order,
            }
        )
    return rows


def source_page_from_name(path: Path) -> int:
    match = re.search(r"page_(\d{3})-\d{3}_res\.json$", path.name)
    if not match:
        raise ValueError(f"Cannot parse source page from {path}")
    return int(match.group(1))


def load_long_rows(
    raw_dir: Path,
    target_sections: dict[str, str],
    *,
    page_from: int | None = None,
    page_to: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section_id, batch in target_sections.items():
        state: dict[str, Any] = {}
        for json_path in sorted((raw_dir / section_id / "json").glob("page_*_res.json")):
            page = source_page_from_name(json_path)
            if page_from is not None and page < page_from:
                continue
            if page_to is not None and page > page_to:
                continue
            tokens = table_tokens_from_json(json_path)
            rows.extend(parse_major_tokens(tokens, batch, page, state=state))
    return rows


def merge_duplicate(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) == 1:
        return records[0]
    ranked = sorted(
        records,
        key=lambda item: (
            item.get("review_status") != "candidate",
            item.get("review_status") != "candidate_year_backfilled",
            item.get("source_page") or 0,
        ),
    )
    chosen = dict(ranked[0])
    chosen["review_status"] = "needs_review_duplicate_key"
    return chosen


def pivot_rows(long_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: "OrderedDict[tuple[str, str, str], dict[str, list[dict[str, Any]]]]" = OrderedDict()
    review_rows: list[dict[str, Any]] = []

    for row in long_rows:
        if row["review_status"] == "needs_review_implausible_numeric":
            review_rows.append(row)
            continue
        if not is_output_major_usable(row["专业"]):
            review_row = dict(row)
            review_row["review_status"] = "needs_review_unusable_major_name"
            review_rows.append(review_row)
            continue
        key = (row["学校"], row["专业"], row["备注"])
        grouped.setdefault(key, {})
        year = row.get("年份")
        if year not in {2023, 2024}:
            review_rows.append(row)
            continue
        grouped[key].setdefault(str(year), []).append(row)

    output_rows: list[dict[str, Any]] = []
    for (school, major, remark), by_year in grouped.items():
        row_2024 = merge_duplicate(by_year["2024"]) if "2024" in by_year else None
        row_2023 = merge_duplicate(by_year["2023"]) if "2023" in by_year else None
        if not row_2024 and not row_2023:
            continue
        output_rows.append(
            {
                "学校": school,
                "专业": major,
                "备注": remark,
                "2024年份": 2024 if row_2024 else None,
                "2024最低录取分数": row_2024["最低录取分数"] if row_2024 else None,
                "2024最低录取位次": row_2024["最低录取位次"] if row_2024 else None,
                "2023年份": 2023 if row_2023 else None,
                "2023最低录取分数": row_2023["最低录取分数"] if row_2023 else None,
                "2023最低录取位次": row_2023["最低录取位次"] if row_2023 else None,
                "source_pages": ",".join(
                    str(item["source_page"])
                    for item in sorted(
                        [item for records in by_year.values() for item in records],
                        key=lambda value: (value["source_page"], value.get("专业代码", "")),
                    )
                ),
                "review_status": ";".join(
                    sorted(
                        {
                            item["review_status"]
                            for records in by_year.values()
                            for item in records
                            if item["review_status"] != "candidate"
                        }
                    )
                ),
            }
        )

    return output_rows, review_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build major-history wide-table data from PP-StructureV3 raw JSON.")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument(
        "--sections",
        nargs="+",
        default=list(TARGET_SECTIONS),
        help="Section ids to include. Defaults to the two pilot major-admission sections.",
    )
    parser.add_argument("--page-from", type=int, default=None, help="Optional inclusive PDF page lower bound.")
    parser.add_argument("--page-to", type=int, default=None, help="Optional inclusive PDF page upper bound.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_sections = {section_id: TARGET_SECTIONS.get(section_id, "本科一批") for section_id in args.sections}
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    long_rows = load_long_rows(args.raw_dir, target_sections, page_from=args.page_from, page_to=args.page_to)
    wide_rows, review_rows = pivot_rows(long_rows)
    payload = {
        "columns": [
            "学校",
            "专业",
            "",
            "年份",
            "最低录取分数",
            "最低录取位次",
            "年份",
            "最低录取分数",
            "最低录取位次",
            "平均最低录取位次",
        ],
        "wide_rows": wide_rows,
        "long_rows": long_rows,
        "review_rows": review_rows,
        "summary": {
            "long_row_count": len(long_rows),
            "wide_row_count": len(wide_rows),
            "review_row_count": len(review_rows),
            "source_sections": list(target_sections),
            "page_from": args.page_from,
            "page_to": args.page_to,
        },
    }
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output_json)
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
