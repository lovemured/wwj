import fs from 'node:fs/promises';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

// Only data cells change; the Python runner preserves the original XLSX package.
const plan = JSON.parse(await fs.readFile(process.argv[2], 'utf8'));
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(plan.template));
const sheet = workbook.worksheets.getItem(plan.sheet);
const preview = async (name) => {
  const image = await workbook.render({sheetName: plan.sheet, range: plan.previewRange ?? 'A12:I17', scale: 1});
  await fs.writeFile(name, new Uint8Array(await image.arrayBuffer()));
};
if (process.argv[3] === 'preview') {
  await preview(plan.beforePreview);
} else {
  sheet.getRangeByIndexes((plan.dataStart ?? 14) - 1, 0, plan.rows.length, plan.width ?? 70).values = plan.rows;
  workbook.recalculate();
  console.log((await workbook.inspect({kind: 'table', range: `${plan.sheet}!C14:I17`,
    include: 'values', tableMaxRows: 4, tableMaxCols: 7, maxChars: 1600})).ndjson);
  await preview(plan.afterPreview);
  await (await SpreadsheetFile.exportXlsx(workbook)).save(plan.artifact);
}
