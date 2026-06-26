import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = "D:/gaokao_data";
const dataPath = process.argv[2] ?? `${root}/output/ppstructure_pilot/review/major_history_pilot_data.json`;
const outputPath = process.argv[3] ?? `${root}/output/ppstructure_pilot/preview/major_history_pilot.xlsx`;
const previewPath = process.argv[4] ?? `${root}/output/ppstructure_pilot/preview/major_history_pilot_preview.png`;

const payload = JSON.parse(await fs.readFile(dataPath, "utf8"));
const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Sheet1");
sheet.showGridLines = true;

const rows = payload.wide_rows;
const values = [
  payload.columns,
  ...rows.map((row, index) => {
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
      "",
    ];
  }),
];

sheet.getRangeByIndexes(0, 0, values.length, 10).values = values;
if (rows.length > 0) {
  sheet.getRangeByIndexes(1, 9, rows.length, 1).formulas = rows.map((_, index) => {
    const excelRow = index + 2;
    return [`=IF(COUNT(F${excelRow},I${excelRow})=0,"",AVERAGE(F${excelRow},I${excelRow}))`];
  });
}

const used = sheet.getRangeByIndexes(0, 0, values.length, 10);
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
  sheet.getRangeByIndexes(0, i, values.length, 1).format.columnWidth = widths[i];
}

for (const column of [3, 4, 5, 6, 7, 8, 9]) {
  sheet.getRangeByIndexes(1, column, Math.max(values.length - 1, 1), 1).numberFormat = "#,##0";
}

const inspect = await workbook.inspect({
  kind: "sheet,region,match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  maxChars: 6000,
});
console.log(inspect.ndjson);

const preview = await workbook.render({
  sheetName: "Sheet1",
  range: "A1:J25",
  scale: 1,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
console.log(outputPath);
