import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "D:/gaokao_data";
const dataPath = `${root}/output/ppstructure_pilot/review/ppstructure_preview_data.json`;
const outputPath = `${root}/output/ppstructure_pilot/preview/ppstructure_final_preview.xlsx`;
const previewPath = `${root}/output/ppstructure_pilot/preview/ppstructure_final_preview_summary.png`;

const data = JSON.parse(await fs.readFile(dataPath, "utf8"));

function matrixForSheet(sheetName) {
  const columns = data.columns_by_sheet[sheetName] ?? [];
  const rows = data.rows_by_sheet[sheetName] ?? [];
  return [
    columns,
    ...rows.map((row) => columns.map((column) => row[column] ?? "")),
  ];
}

function widthForColumn(name) {
  if (name === "项目" || name === "结论" || name === "说明" || name === "建议动作") return 42;
  if (name.includes("院校名称") || name.includes("专业名称") || name === "章节") return 28;
  if (name === "review_status") return 30;
  if (name === "source_page" || name === "PDF页" || name === "年份") return 12;
  return 14;
}

function addSheet(workbook, sheetName) {
  const matrix = matrixForSheet(sheetName);
  const rowCount = Math.max(matrix.length, 1);
  const colCount = Math.max(...matrix.map((row) => row.length), 1);
  const normalized = matrix.map((row) => [...row, ...Array(colCount - row.length).fill("")]);

  const sheet = workbook.worksheets.add(sheetName);
  sheet.showGridLines = false;
  sheet.getRangeByIndexes(0, 0, rowCount, colCount).values = normalized;

  const used = sheet.getRangeByIndexes(0, 0, rowCount, colCount);
  used.format = {
    font: { name: "Microsoft YaHei", size: 10, color: "#1F1F1F" },
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D9E2EC" },
  };

  const header = sheet.getRangeByIndexes(0, 0, 1, colCount);
  header.format = {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF", name: "Microsoft YaHei", size: 10 },
    wrapText: true,
  };
  sheet.freezePanes.freezeRows(1);

  const columns = data.columns_by_sheet[sheetName] ?? [];
  for (let i = 0; i < colCount; i++) {
    sheet.getRangeByIndexes(0, i, rowCount, 1).format.columnWidth = widthForColumn(columns[i] ?? "");
  }

  const statusIndex = columns.indexOf("review_status");
  if (statusIndex >= 0 && rowCount > 1) {
    const range = sheet.getRangeByIndexes(1, statusIndex, rowCount - 1, 1);
    range.format = { fill: "#FFF7ED", font: { color: "#9A3412", name: "Microsoft YaHei", size: 10 } };
  }
  return sheet;
}

const workbook = Workbook.create();
for (const sheetName of data.sheet_order) {
  addSheet(workbook, sheetName);
}

for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  if (used) used.format.autofitRows();
}

const inspect = await workbook.inspect({
  kind: "sheet,region,match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|bbox_json|poly_json|ocr_index",
  options: { useRegex: true, maxResults: 100 },
  maxChars: 8000,
});
console.log(inspect.ndjson);

const summaryPreview = await workbook.render({
  sheetName: "00_试点结论",
  autoCrop: "all",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await summaryPreview.arrayBuffer()));

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
console.log(outputPath);
