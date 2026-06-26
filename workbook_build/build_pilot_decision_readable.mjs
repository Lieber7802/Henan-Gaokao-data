import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "D:/gaokao_data";
const pilotDir = `${root}/output/pilot`;
const outputPath = `${pilotDir}/review/pilot_decision_readable.xlsx`;

function csvParse(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];
    if (ch === '"' && inQuotes && next === '"') {
      field += '"';
      i++;
    } else if (ch === '"') {
      inQuotes = !inQuotes;
    } else if (ch === "," && !inQuotes) {
      row.push(field);
      field = "";
    } else if ((ch === "\n" || ch === "\r") && !inQuotes) {
      if (ch === "\r" && next === "\n") i++;
      row.push(field);
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      field = "";
    } else {
      field += ch;
    }
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  if (!rows.length) return [];
  const headers = rows[0].map((h) => h.replace(/^\uFEFF/, ""));
  return rows.slice(1).map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? ""])));
}

async function readCsv(filePath) {
  return csvParse(await fs.readFile(filePath, "utf8"));
}

function addSheet(workbook, name, rows, widths = []) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const rowCount = Math.max(rows.length, 1);
  const colCount = Math.max(...rows.map((r) => r.length), 1);
  const matrix = rows.map((r) => [...r, ...Array(colCount - r.length).fill(null)]);
  sheet.getRangeByIndexes(0, 0, rowCount, colCount).values = matrix;
  if (rows.length > 1) {
    const header = sheet.getRangeByIndexes(0, 0, 1, colCount);
    header.format = {
      fill: "#1F4E78",
      font: { bold: true, color: "#FFFFFF" },
      wrapText: true,
    };
    sheet.freezePanes.freezeRows(1);
  }
  const used = sheet.getRangeByIndexes(0, 0, rowCount, colCount);
  used.format = {
    font: { name: "Microsoft YaHei", size: 10 },
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: "#BFBFBF" },
  };
  for (let i = 0; i < widths.length; i++) {
    sheet.getRangeByIndexes(0, i, rowCount, 1).format.columnWidth = widths[i];
  }
  return sheet;
}

function countStatuses(rows) {
  return {
    total: rows.length,
    autoPass: rows.filter((r) => r.review_status === "auto_pass").length,
    needsReview: rows.filter((r) => r.review_status === "needs_review").length,
  };
}

const timing = JSON.parse(await fs.readFile(`${pilotDir}/ocr_raw/timing.json`, "utf8"));
const validation = JSON.parse(await fs.readFile(`${pilotDir}/review/numeric_validation_summary.json`, "utf8"));
const pageProbe = await readCsv(`${pilotDir}/review/table_line_probe.csv`);
const config = JSON.parse(await fs.readFile(`${root}/configs/pilot_pages.json`, "utf8"));
const fieldFailures = await readCsv(`${pilotDir}/review/field_failures.csv`);

const tableNames = [
  "chapter1_score_lines",
  "chapter1_score_bands",
  "chapter2_batch1_application",
  "chapter2_batch2_application",
  "chapter2_vocational_application",
  "chapter3_batch1_major_admission",
  "chapter3_batch2_major_admission",
  "chapter3_vocational_admission",
];

const tableLabel = {
  chapter1_score_lines: "第一章：录取控制分数线",
  chapter1_score_bands: "第一章：分数段统计",
  chapter2_batch1_application: "第二章：本科一批投档统计",
  chapter2_batch2_application: "第二章：本科二批投档统计",
  chapter2_vocational_application: "第二章：高职高专投档统计",
  chapter3_batch1_major_admission: "第三章：本科一批分专业录取",
  chapter3_batch2_major_admission: "第三章：本科二批分专业录取",
  chapter3_vocational_admission: "第三章：高职高专院校录取",
};

const csvSummaries = [];
for (const name of tableNames) {
  const rows = await readCsv(`${pilotDir}/tables_csv/${name}.csv`);
  const statuses = countStatuses(rows);
  const numeric = validation[name] || { rows_checked: 0, auto_pass: 0, needs_review: 0 };
  csvSummaries.push([
    tableLabel[name],
    name,
    statuses.total,
    statuses.autoPass,
    statuses.needsReview,
    numeric.rows_checked ?? 0,
    numeric.auto_pass ?? 0,
    numeric.needs_review ?? 0,
    name.startsWith("chapter2")
      ? "不能直接全量跑：需要先把 OCR 文本按表格单元格/行重组，否则数字校验没有意义。"
      : name.includes("major")
        ? "不能直接全量跑：分专业表存在院校/年份跨行继承，必须做状态机解析。"
        : "可作为辅助参考，但仍需要最终字段化。"
  ]);
}

const avgSeconds = timing.reduce((sum, row) => sum + row.elapsed_seconds, 0) / timing.length;
const totalRows = timing.reduce((sum, row) => sum + row.normalized_rows, 0);
const needsReviewPages = pageProbe.filter((r) => r.boundary_status !== "ok").length;

const workbook = Workbook.create();

addSheet(workbook, "结论", [
  ["项目", "结论 / 说明"],
  ["是否应该现在直接全量跑", "不建议。当前试点证明 PaddleOCR 能在本机运行，但还没有生成可统计的最终结构化表。"],
  ["为什么你看不懂之前的表", "之前的 Excel/CSV 是 OCR 中间结果：一行代表一段识别文字，不代表 PDF 表格里的一条院校或专业记录。"],
  ["下一步应该做什么", "先做二阶段：表格线切格 + 单元格 OCR + 行/跨页状态机解析；再用 23 页样本生成真正最终格式预览。"],
  ["什么时候才全量跑", "当 23 页样本能输出最终字段表，并且抽查/数字校验通过后，再全量跑 912 页。"],
  ["本机能否跑 PaddleOCR", "可以。已本地 CPU 跑完 23 页试点。"],
  ["试点页数", timing.length],
  ["平均 OCR 时间/页", `${avgSeconds.toFixed(2)} 秒`],
  ["估算 912 页 OCR 时间", `${(avgSeconds * 912 / 3600).toFixed(2)} 小时`],
  ["OCR 行数", totalRows],
  ["需要特殊表格线处理的页数", needsReviewPages],
  ["异常复核队列条数", fieldFailures.length],
], [28, 90]);

addSheet(workbook, "你要的最终表结构", [
  ["最终文件/Sheet", "最终列名", "数据类型", "说明"],
  ["01_录取控制分数线", "年份", "整数", "2023 或 2024"],
  ["01_录取控制分数线", "科类", "文本", "理科综合/文科综合"],
  ["01_录取控制分数线", "本科一批线", "整数", "控制分数线"],
  ["01_录取控制分数线", "本科二批线", "整数", "控制分数线"],
  ["01_录取控制分数线", "高职高专批线", "整数", "控制分数线"],
  ["02_分数段统计", "分数", "整数", "高考分数"],
  ["02_分数段统计", "2023考生人数/位次", "整数", "按原表口径"],
  ["02_分数段统计", "2024考生人数/位次", "整数", "按原表口径"],
  ["03_院校投档统计", "批次", "文本", "本科一批/本科二批/高职高专"],
  ["03_院校投档统计", "院校代码", "文本", "保留前导 0"],
  ["03_院校投档统计", "院校名称", "文本", "含较高收费/软件类等括注"],
  ["03_院校投档统计", "年份", "整数", "2023 或 2024"],
  ["03_院校投档统计", "公布计划", "整数", "原表字段"],
  ["03_院校投档统计", "实际投档人数", "整数", "原表字段"],
  ["03_院校投档统计", "投档最低总分", "整数", "原表字段"],
  ["03_院校投档统计", "语文", "整数", "同分排序字段"],
  ["03_院校投档统计", "数学", "整数", "同分排序字段"],
  ["03_院校投档统计", "外语听力", "整数", "同分排序字段"],
  ["03_院校投档统计", "与分数线差值", "整数", "可用控制线校验"],
  ["03_院校投档统计", "最低分位次", "整数", "原表字段"],
  ["04_分专业录取统计", "批次/院校代码/院校名称/年份", "混合", "需要跨页继承"],
  ["04_分专业录取统计", "专业代码", "文本", "保留 01、02 等格式"],
  ["04_分专业录取统计", "专业名称", "文本", "可能换行，需要合并"],
  ["04_分专业录取统计", "公布计划/录取人数/最高分/平均分/最低分/差值/位次", "数字", "最终可统计字段"],
  ["所有最终表", "source_page / review_status", "审计字段", "保留来源页和复核状态，方便查原图"],
], [28, 28, 16, 60]);

addSheet(workbook, "试点结果汇总", [
  ["表类型", "技术表名", "OCR 行数", "自动通过行", "需复核行", "数字校验行", "数字自动通过", "数字需复核", "是否可直接全量跑"],
  ...csvSummaries,
], [30, 34, 14, 14, 14, 14, 14, 14, 80]);

const configByPage = Object.fromEntries(config.pages.map((p) => [String(p.pdf_page).padStart(3, "0"), p]));
addSheet(workbook, "问题页清单", [
  ["PDF 页", "表类型", "横线数", "竖线数", "表格线状态", "给你的判断"],
  ...pageProbe.map((r) => {
    const page = r.image.split("-")[0].replace("page_", "");
    const meta = configByPage[page] || {};
    return [
      Number(page),
      tableLabel[meta.table_type] || meta.table_type || "",
      Number(r.horizontal_line_count),
      Number(r.vertical_line_count),
      r.boundary_status,
      r.boundary_status === "ok" ? "结构识别基本可用" : "全量前必须加特殊处理或人工抽查",
    ];
  }),
], [12, 34, 12, 12, 16, 42]);

addSheet(workbook, "之前两个表是什么", [
  ["文件", "它是什么", "为什么你看不懂", "是否是最终数据"],
  ["paddleocr_pilot_extract.xlsx", "OCR 逐文字行清单，包含坐标、置信度、来源页。", "一行是一段 OCR 文本，不是一个院校/专业记录；字段名偏工程化。", "不是"],
  ["field_failures.csv", "异常复核队列，列出解析/数字校验没通过的 OCR 文本。", "里面混有说明文字误报和真实问题，需要二阶段解析后才有业务意义。", "不是"],
  ["table_line_probe.csv", "表格线探测诊断表，用来判断每页横线/竖线是否能自动定位。", "这是算法诊断，不是业务数据。", "不是"],
  ["pilot_decision_readable.xlsx", "你现在打开的这份说明表。", "它是给人看决策用的，不是最终录取统计数据。", "不是最终数据，但能告诉你下一步怎么做"],
], [34, 48, 70, 18]);

for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  if (used) {
    used.format.autofitRows();
  }
}

const summaryPreview = await workbook.render({
  sheetName: "结论",
  autoCrop: "all",
  scale: 1,
  format: "png",
});
await fs.writeFile(`${pilotDir}/review/pilot_decision_readable_preview.png`, new Uint8Array(await summaryPreview.arrayBuffer()));

const inspect = await workbook.inspect({
  kind: "sheet,region,match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  maxChars: 4000,
});
console.log(inspect.ndjson);

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
console.log(outputPath);
