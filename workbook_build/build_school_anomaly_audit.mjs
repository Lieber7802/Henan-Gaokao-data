import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "D:/gaokao_data";
const dataPath = process.argv[2] ?? `${root}/output/ppstructure_full/chapter3_batch1/review/major_history_chapter3_batch1_data.json`;
const outputPath = process.argv[3] ?? `${root}/output/ppstructure_full/chapter3_batch1/preview/本科一批分数线_异常行标注.xlsx`;
const previewPath = process.argv[4] ?? `${root}/output/ppstructure_full/chapter3_batch1/preview/school_anomaly_audit_preview.png`;

const payload = JSON.parse(await fs.readFile(dataPath, "utf8"));
const rows = payload.wide_rows ?? [];

const lacksSchoolKeyword = (school) => {
  const text = `${school ?? ""}`.trim();
  return text.length > 0 && !text.includes("大学") && !text.includes("学院");
};

const causeFor = (row) => {
  const school = `${row["学校"] ?? ""}`;
  const major = `${row["专业"] ?? ""}`;
  if (/试验班|类|医学|工程|计划|班|方向|学制|专业|技术/.test(school)) {
    return "专业名/备注片段进入学校列；旧解析规则把前一个4位最低位次误判为院校代码。";
  }
  if (!row["2024年份"] && !row["2023年份"]) {
    return "该行缺少年份和分数，疑似由残缺 OCR token 进入透视表。";
  }
  if (major) {
    return "学校列不像院校名，疑似专业跨行续写时继承状态被污染。";
  }
  return "学校列不含“大学/学院”，需人工复核。";
};

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Sheet1");
sheet.showGridLines = true;

const tableValues = [
  payload.columns,
  ...rows.map((row, index) => {
    const excelRow = index + 2;
    return [
      row["学校"] ?? "",
      row["专业"] ?? "",
      row["备注"] ?? "",
      row["2024年份"] ?? "",
      row["2024最低录取分数"] ?? "",
      row["2024最低录取位次"] ?? "",
      row["2023年份"] ?? "",
      row["2023最低录取分数"] ?? "",
      row["2023最低录取位次"] ?? "",
      `=IF(COUNT(F${excelRow},I${excelRow})=0,"",AVERAGE(F${excelRow},I${excelRow}))`,
    ];
  }),
];

sheet.getRangeByIndexes(0, 0, tableValues.length, 10).values = tableValues;

const used = sheet.getRangeByIndexes(0, 0, tableValues.length, 10);
used.format = {
  font: { name: "Microsoft YaHei", size: 10, color: "#1F1F1F" },
  borders: { preset: "all", style: "thin", color: "#D9E2EC" },
  wrapText: false,
};
sheet.getRangeByIndexes(0, 0, 1, 10).format = {
  font: { name: "Microsoft YaHei", size: 10, bold: true, color: "#000000" },
  fill: "#F2F2F2",
};

const widths = [22, 28, 24, 10, 14, 16, 10, 14, 16, 18];
for (let i = 0; i < widths.length; i++) {
  sheet.getRangeByIndexes(0, i, tableValues.length, 1).format.columnWidth = widths[i];
}
for (const column of [3, 4, 5, 6, 7, 8, 9]) {
  sheet.getRangeByIndexes(1, column, Math.max(tableValues.length - 1, 1), 1).numberFormat = "#,##0";
}

const anomalyRows = [];
for (let index = 0; index < rows.length; index++) {
  const row = rows[index];
  if (!lacksSchoolKeyword(row["学校"])) continue;
  const excelRow = index + 2;
  const cause = causeFor(row);
  anomalyRows.push([
    excelRow,
    row["学校"] ?? "",
    row["专业"] ?? "",
    row["备注"] ?? "",
    row["2024年份"] ?? "",
    row["2024最低录取分数"] ?? "",
    row["2024最低录取位次"] ?? "",
    row["2023年份"] ?? "",
    row["2023最低录取分数"] ?? "",
    row["2023最低录取位次"] ?? "",
    row["source_pages"] ?? "",
    cause,
  ]);
  sheet.getRangeByIndexes(excelRow - 1, 0, 1, 10).format = {
    fill: "#FCE4D6",
    font: { name: "Microsoft YaHei", size: 10, color: "#9C0006" },
  };
}

const audit = workbook.worksheets.add("异常行清单");
audit.showGridLines = true;
const auditValues = [
  ["原表行号", "学校栏内容", "专业", "备注", "2024年份", "2024最低分", "2024位次", "2023年份", "2023最低分", "2023位次", "source_pages", "异常原因"],
  ...anomalyRows,
];
audit.getRangeByIndexes(0, 0, auditValues.length, 12).values = auditValues;
audit.getRangeByIndexes(0, 0, auditValues.length, 12).format = {
  font: { name: "Microsoft YaHei", size: 10, color: "#1F1F1F" },
  borders: { preset: "all", style: "thin", color: "#D9E2EC" },
  wrapText: false,
};
audit.getRangeByIndexes(0, 0, 1, 12).format = {
  font: { name: "Microsoft YaHei", size: 10, bold: true, color: "#000000" },
  fill: "#F2F2F2",
};
const auditWidths = [10, 32, 28, 28, 10, 12, 12, 10, 12, 12, 18, 54];
for (let i = 0; i < auditWidths.length; i++) {
  audit.getRangeByIndexes(0, i, auditValues.length, 1).format.columnWidth = auditWidths[i];
}

const inspect = await workbook.inspect({
  kind: "sheet,region,match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  maxChars: 6000,
});
console.log(inspect.ndjson);

const preview = await workbook.render({
  sheetName: "异常行清单",
  range: "A1:L25",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
console.log(JSON.stringify({ outputPath, anomalyCount: anomalyRows.length }, null, 2));
