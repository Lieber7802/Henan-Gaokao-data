# 第三章分专业录取统计复用说明

本文档沉淀本科一批全量处理后的经验，供后续处理“第三章本科二批分专业录取”时复用。目标是减少人工返工，避免再次出现学校列残片、专业列残片、公式错误和明显异常分数/位次。

## 结论先行

本科二批不要回到“逐文字 OCR + 自己切格”的旧路线。继续使用：

1. `PP-StructureV3` 按章节页提取。
2. `scripts/build_major_history_pilot_data.py` 做第三章专用解析、跨页继承、清洗和宽表转换。
3. `scripts/build_major_history_workbook.py` 输出最终 Excel。
4. `scripts/check_major_history_workbook.py` 扫描最终 Excel 的结构和数值异常。

当前解析器已覆盖本科一批踩坑后的规则，并且 `TARGET_SECTIONS` 支持：

- `chapter3_batch1_major_admission` -> `本科一批`
- `chapter3_batch2_major_admission` -> `本科二批`

## 本科二批推荐入口

```powershell
.\.venv-paddleocr\Scripts\python.exe scripts\run_chapter3_batch2_full_pipeline.py
```

默认输出：

- 原始 PP-Structure 结果：`output/ppstructure_full/chapter3_batch2/raw/`
- 宽表数据 JSON：`output/ppstructure_full/chapter3_batch2/review/major_history_chapter3_batch2_data.json`
- 最终 Excel：`output/ppstructure_full/chapter3_batch2/preview/本科二批分数线.xlsx`
- 进度状态：`output/ppstructure_full/chapter3_batch2/review/pipeline_status.json`

脚本默认页码是 `449-869`。本科一批到 PDF 446 页结束，PDF 447-448 为过渡页/无有效表格，PDF 449 页开始是本科二批。如果后续根据目录确认边界不同，只改 `scripts/run_chapter3_batch2_full_pipeline.py` 里的 `--page-from` 和 `--page-to`。

## 必须复用的经验

### 1. 不直接使用 PP-Structure 导出的 XLSX 做最终统计

PP-Structure 的 XLSX 是识别层证据，不是最终统计表。它容易保留页面结构、跨行碎片和不稳定列顺序。最终统计必须经过 `build_major_history_pilot_data.py`，因为该脚本做了这些业务处理：

- 按学校、专业、备注合并 2024/2023 年数据。
- 跨页继承学校上下文，处理页面从某个学校中间开始的情况。
- 把专业名称的前缀/后缀残片尽量拼回备注。
- 将无法可信修复的记录送入 `review_rows`，避免污染最终 Excel。

### 2. “隔离”不是删除源证据

最终 Excel 只保留能用于统计的记录。明显不可信的记录不进入最终表，但仍保留在 JSON 的 `review_rows` 中，便于后续回查。

常见隔离原因：

- `needs_review_missing_year`：年份缺失且无法安全回填。
- `needs_review_unusable_major_name`：专业名是残片。
- `needs_review_implausible_numeric`：分数/位次明显不合理，通常是列错位。

### 3. 学校名识别必须严格

不能因为 token 里含有 `学院` 就当作学校名。`学院，含生物信息`、`电子学院`、`投资学 双学士学位、公管学院和数学学` 这类内容在本科一批中都曾是错误来源。

正确处理方式：

- `大学` 通常可作为学校强信号。
- `学院` 只有在完整学校名结尾时才可作为学校信号。
- 带右括号、逗号、半截括号的 `学院` 片段优先视为专业备注片段。

### 4. 专业名残片不能进入最终表

最终表门禁：

- 专业名至少要有两个中文字符。
- 专业名不能以右括号开头。
- 专业名括号必须平衡。
- 专业名不能是表头字段。

备注列里出现 `学院` 是可以的，不应因为备注里有 `学院` 就删除。

### 5. 年份回填不能覆盖异常状态

PP-Structure 有时会把年份 token 放在若干专业行之后。解析器会用专业代码回绕和后续年份做回填，但年份回填不能把 `needs_review_implausible_numeric` 覆盖成普通候选。

### 6. 数值合理性要作为最终表门禁

本科一批中发现过最低分变成 `140`、`106`、`129`，最低位次变成 `14`、`2`、`1` 这类错误。这通常是列错位，把线差值、专业代码、人数当成最终字段。

当前门禁：

- 本科一批最低分小于 `450` 不进入最终表。
- 本科一批最低位次小于 `50` 且最低分低于 `690` 不进入最终表。
- 本科二批最低分小于 `300` 不进入最终表。

本科二批跑完后，如果发现新的异常分布，先看 raw token，再调整 `is_admission_numeric_plausible()`，不要只在 Excel 里手工改。

## 本科二批跑完后的验收清单

1. Excel 能打开，J 列公式是单等号，例如 `=IF(COUNT(F2,I2)=0,"",AVERAGE(F2,I2))`。
2. 学校列不能出现明显残片。
3. 专业列不能有括号不平衡。
4. 专业列不能出现单字残片或右括号开头残片。
5. 不能出现 `#DIV/0!`、`#REF!`、`#VALUE!`、`#NAME?`、`#N/A`。
6. 对最低分/最低位次做合理性扫描。
7. 对 `review_rows` 做数量和原因分布统计，确认主要问题不是系统性解析失败。
8. 抽查章节首、中、尾页，尤其是跨页学校延续位置。

可用测试命令：

```powershell
.\.venv-paddleocr\Scripts\python.exe -m pytest tests
```

可用 Excel 质量扫描命令：

```powershell
.\.venv-paddleocr\Scripts\python.exe scripts\check_major_history_workbook.py output\ppstructure_full\chapter3_batch2\preview\本科二批分数线.xlsx --batch 本科二批 --output-json output\ppstructure_full\chapter3_batch2\review\workbook_quality_check.json
```

## 发现新问题时的处理顺序

1. 先在 Excel 里标注问题单元格。
2. 读取标注单元格对应的整行：学校、专业、备注、2024/2023 分数和位次。
3. 回到 `raw/<section_id>/json/page_XXX-XXX_res.json` 查看原始 token。
4. 判断问题属于学校识别、专业拼接、年份回填、数值列错位，还是 PP-Structure 原始识别失败。
5. 先给 `tests/test_major_history_parser.py` 增加最小复现。
6. 再改 `scripts/build_major_history_pilot_data.py`。
7. 重跑数据和 Excel，另存新版本，不覆盖人工标注文件。
8. 用验收清单复查。

## 不建议做的事

- 不要直接编辑最终 Excel 来修正解析问题。
- 不要删除 PP-Structure raw JSON。
- 不要因为备注里出现 `学院` 就认为是学校列错误。
- 不要只凭括号平衡判断结果完全正确，还要检查专业残片和数值分布。
- 不要覆盖用户人工标注过的 Excel，应另存新版本用于对照。
