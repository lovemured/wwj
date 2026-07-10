#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DEFAULT_NODE_MODULES =
  "/Users/mured/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";

function parseArgs(argv) {
  const args = {
    input: "story-23598-error-report-direct-import-testcases.md",
    output: "/Users/mured/wwj/需求文档/story-23598-error-report-direct-import-testcases.xlsx",
    title: "",
    source: "",
    preview: false,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === "--input") {
      args.input = value;
      i += 1;
    } else if (key === "--output") {
      args.output = value;
      i += 1;
    } else if (key === "--title") {
      args.title = value;
      i += 1;
    } else if (key === "--source") {
      args.source = value;
      i += 1;
    } else if (key === "--preview") {
      args.preview = true;
    } else if (key === "--help" || key === "-h") {
      printHelp();
      process.exit(0);
    }
  }

  return args;
}

function printHelp() {
  console.log(`Usage:
  node tools/testcase-excel/markdown-to-testcase-excel.mjs \\
    --input story-23598-error-report-direct-import-testcases.md \\
    --output /Users/mured/wwj/需求文档/story-23598-error-report-direct-import-testcases.xlsx

Options:
  --input    Markdown test case document.
  --output   Target .xlsx path.
  --title    Optional workbook title. Defaults to the Markdown H1.
  --source   Optional source URL shown in the workbook.
  --preview  Also render PNG previews next to the Excel file.
`);
}

async function ensureArtifactTool() {
  const localNodeModules = path.join(__dirname, "node_modules");
  const configuredNodeModules = process.env.ARTIFACT_TOOL_NODE_MODULES || DEFAULT_NODE_MODULES;

  try {
    await fs.access(path.join(localNodeModules, "@oai", "artifact-tool", "package.json"));
  } catch {
    await fs.rm(localNodeModules, { recursive: true, force: true });
    await fs.symlink(configuredNodeModules, localNodeModules, "dir");
  }

  return import("@oai/artifact-tool");
}

function splitMarkdownRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cleanMarkdown(cell.trim()));
}

function cleanMarkdown(value) {
  return value
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/&gt;/g, ">")
    .replace(/&lt;/g, "<")
    .replace(/&amp;/g, "&")
    .trim();
}

function isSeparatorRow(line) {
  return /^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line.trim());
}

function isTableRow(line) {
  return line.trim().startsWith("|") && line.trim().endsWith("|");
}

function stripSectionPrefix(heading) {
  return heading.replace(/^#+\s*/, "").replace(/^[A-Z]\.\s*/, "").trim();
}

function parseMarkdown(markdown, fallbackTitle) {
  const lines = markdown.split(/\r?\n/);
  const titleLine = lines.find((line) => line.startsWith("# "));
  const title = fallbackTitle || cleanMarkdown(titleLine ? titleLine.replace(/^#\s+/, "") : "测试用例");
  let currentSection = "";
  const cases = [];
  const confirmations = [];
  const coverage = [];

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (line.startsWith("### ")) {
      currentSection = stripSectionPrefix(line);
      continue;
    }

    if (!isTableRow(line)) continue;
    const header = splitMarkdownRow(line);
    const nextLine = lines[i + 1] || "";
    if (!isSeparatorRow(nextLine)) continue;

    const headerText = header.join("|");
    const bodyRows = [];
    let cursor = i + 2;
    while (cursor < lines.length && isTableRow(lines[cursor])) {
      bodyRows.push(splitMarkdownRow(lines[cursor]));
      cursor += 1;
    }

    if (headerText === "ID|优先级|类型|测试点|前置条件|测试步骤|预期结果") {
      for (const row of bodyRows) {
        if (row.length < 7 || !row[0]) continue;
        cases.push({
          id: row[0],
          module: currentSection || "未分组",
          scenario: currentSection || "未分组",
          title: row[3],
          precondition: row[4],
          steps: row[5],
          expected: row[6],
          priority: row[1],
          type: row[2],
          data: inferTestData(row[4], row[5], row[6]),
          note: "",
        });
      }
    } else if (headerText.startsWith("编号|待确认点|说明")) {
      for (const row of bodyRows) {
        if (row.length < 3 || !row[0]) continue;
        confirmations.push({
          id: row[0],
          point: row[1],
          description: row[2],
          impact: inferImpact(row[1]),
        });
      }
    } else if (headerText === "范围|说明") {
      for (const row of bodyRows) {
        if (row.length < 2 || !row[0]) continue;
        coverage.push({ area: row[0], description: row[1] });
      }
    }

    i = cursor - 1;
  }

  return { title, cases, confirmations, coverage };
}

function inferTestData(precondition, steps, expected) {
  const text = `${precondition} ${steps} ${expected}`;
  if (text.includes("4001")) return "4001条错误数据";
  if (text.includes("4000")) return "4000条错误数据";
  if (text.includes("单条") || text.includes("1 条") || text.includes("1个")) return "1条错误数据";
  if (text.includes("多个") || text.includes("多条") || text.includes("批次")) return "多条/多批次数据";
  if (text.includes("模板")) return "系统模板文件";
  if (text.includes("原始数据")) return "原始数据文件";
  if (text.includes("错误报告")) return "错误报告文件";
  return "-";
}

function inferImpact(point) {
  if (point.includes("格式")) return "影响导入与文件识别";
  if (point.includes("表头")) return "影响错误文件是否可回传";
  if (point.includes("4000") || point.includes("拆分")) return "影响批量下载与回归数据构造";
  if (point.includes("下载")) return "影响异常场景断言";
  if (point.includes("源文件位置")) return "影响修正定位准确性";
  return "影响测试预期与断言";
}

function applyTitle(range, fill) {
  range.format = {
    fill,
    font: { color: "#FFFFFF", bold: true, size: 14 },
  };
}

function applyHeader(range, fill = "#2563EB") {
  range.format = {
    fill,
    font: { color: "#FFFFFF", bold: true, size: 11 },
  };
}

function applyBorders(range) {
  range.format.borders = {
    insideHorizontal: { style: "thin", color: "#E5E7EB" },
    insideVertical: { style: "thin", color: "#E5E7EB" },
    top: { style: "thin", color: "#CBD5E1" },
    bottom: { style: "thin", color: "#CBD5E1" },
    left: { style: "thin", color: "#CBD5E1" },
    right: { style: "thin", color: "#CBD5E1" },
  };
}

async function buildWorkbook({ Workbook }, parsed, options) {
  const workbook = Workbook.create();
  const mainSheet = workbook.worksheets.add("测试用例");
  const summarySheet = workbook.worksheets.add("汇总");
  const confirmSheet = workbook.worksheets.add("待确认");
  const cases = parsed.cases;
  const rowCount = cases.length;
  const lastRow = rowCount + 4;

  mainSheet.showGridLines = false;
  mainSheet.getRange("A1:K1").merge();
  mainSheet.getRange("A2:K2").merge();
  mainSheet.getRange("A3:K3").merge();
  mainSheet.getRange("A1").values = [[parsed.title]];
  mainSheet.getRange("A2").values = [[options.source ? `来源：${options.source}` : "来源：Markdown测试用例文档"]];
  mainSheet.getRange("A3").values = [["说明：由 Markdown 自动转换，按模块、场景、优先级和类型筛选执行。"]];
  applyTitle(mainSheet.getRange("A1:K1"), "#1E3A8A");
  mainSheet.getRange("A2:K2").format = { fill: "#DBEAFE", font: { color: "#1F2937", size: 10 } };
  mainSheet.getRange("A3:K3").format = { fill: "#FEF3C7", font: { color: "#1F2937", size: 10 } };

  const headers = ["用例ID", "功能模块", "测试场景", "测试标题", "前置条件", "测试步骤", "预期结果", "优先级", "用例类型", "测试数据", "备注/风险"];
  mainSheet.getRange("A4:K4").values = [headers];
  applyHeader(mainSheet.getRange("A4:K4"));

  const values = cases.map((item) => [
    item.id,
    item.module,
    item.scenario,
    item.title,
    item.precondition,
    item.steps,
    item.expected,
    item.priority,
    item.type,
    item.data,
    item.note,
  ]);
  if (values.length > 0) {
    mainSheet.getRange(`A5:K${lastRow}`).values = values;
    mainSheet.tables.add(`A4:K${lastRow}`, true, "TestCasesTable");
    applyBorders(mainSheet.getRange(`A4:K${lastRow}`));
    mainSheet.getRange(`A5:K${lastRow}`).format = { font: { color: "#111827", size: 10 } };
    mainSheet.getRange(`A5:K${lastRow}`).format.wrapText = true;
    mainSheet.dataValidations.add({ range: `H5:H${lastRow}`, rule: { type: "list", values: ["P0", "P1", "P2", "P3"] } });
    mainSheet.dataValidations.add({ range: `I5:I${lastRow}`, rule: { type: "list", values: ["功能", "异常", "边界", "性能", "兼容"] } });

    const priorityColors = { P0: "#FEE2E2", P1: "#FFEDD5", P2: "#DBEAFE", P3: "#E5E7EB" };
    for (let i = 0; i < values.length; i += 1) {
      const cell = mainSheet.getRange(`H${i + 5}`);
      cell.format = { fill: priorityColors[values[i][7]] || "#FFFFFF", font: { color: "#111827", bold: true } };
    }
  }

  mainSheet.freezePanes.freezeRows(4);
  const widths = [90, 120, 120, 190, 190, 260, 240, 70, 90, 160, 150];
  for (let col = 0; col < widths.length; col += 1) {
    mainSheet.getRangeByIndexes(0, col, Math.max(lastRow, 5), 1).format.columnWidthPx = widths[col];
  }
  mainSheet.getRange("A1:K1").format.rowHeightPx = 32;
  mainSheet.getRange("A2:K4").format.rowHeightPx = 26;
  for (let row = 5; row <= lastRow; row += 1) {
    mainSheet.getRange(`A${row}:K${row}`).format.rowHeightPx = 46;
  }

  buildSummarySheet(summarySheet, parsed, lastRow);
  buildConfirmSheet(confirmSheet, parsed.confirmations);

  return workbook;
}

function buildSummarySheet(sheet, parsed, lastCaseRow) {
  sheet.showGridLines = false;
  sheet.getRange("A1:E1").merge();
  sheet.getRange("A1").values = [["测试汇总"]];
  applyTitle(sheet.getRange("A1:E1"), "#0F766E");
  sheet.getRange("A3:B7").values = [
    ["统计项", "数值"],
    ["用例总数", `=COUNTA('测试用例'!A5:A${lastCaseRow})`],
    ["P0 用例", `=COUNTIF('测试用例'!H5:H${lastCaseRow},"P0")`],
    ["P1 用例", `=COUNTIF('测试用例'!H5:H${lastCaseRow},"P1")`],
    ["P2/P3 用例", `=COUNTIF('测试用例'!H5:H${lastCaseRow},"P2")+COUNTIF('测试用例'!H5:H${lastCaseRow},"P3")`],
  ];
  applyHeader(sheet.getRange("A3:B3"), "#1D4ED8");
  applyBorders(sheet.getRange("A3:B7"));

  sheet.getRange("A9:B9").merge();
  sheet.getRange("A9").values = [["覆盖说明"]];
  sheet.getRange("A9:B9").format = { fill: "#DBEAFE", font: { color: "#1F2937", bold: true, size: 12 } };

  const coverageRows = parsed.coverage.length > 0 ? parsed.coverage : [{ area: "测试用例", description: "详见测试用例页" }];
  sheet.getRangeByIndexes(9, 0, coverageRows.length, 2).values = coverageRows.map((item) => [item.area, item.description]);
  const coverageRange = sheet.getRangeByIndexes(9, 0, coverageRows.length, 2);
  coverageRange.format.wrapText = true;
  applyBorders(coverageRange);
  sheet.getRangeByIndexes(9, 0, coverageRows.length, 1).format = { font: { color: "#111827", bold: true } };

  sheet.getRange("A1:E1").format.rowHeightPx = 30;
  sheet.getRange("A3:B7").format.rowHeightPx = 24;
  sheet.getRange("A:A").format.columnWidthPx = 120;
  sheet.getRange("B:B").format.columnWidthPx = 520;
  for (let row = 10; row < 10 + coverageRows.length; row += 1) {
    sheet.getRange(`A${row}:B${row}`).format.rowHeightPx = 34;
  }
}

function buildConfirmSheet(sheet, confirmations) {
  sheet.showGridLines = false;
  sheet.getRange("A1:D1").merge();
  sheet.getRange("A1").values = [["待确认事项"]];
  applyTitle(sheet.getRange("A1:D1"), "#7C3AED");
  sheet.getRange("A3:D3").values = [["编号", "待确认点", "说明", "影响"]];
  applyHeader(sheet.getRange("A3:D3"), "#9333EA");

  const rows = confirmations.length > 0 ? confirmations : [{ id: "-", point: "暂无", description: "Markdown中未识别到待确认表", impact: "-" }];
  sheet.getRangeByIndexes(3, 0, rows.length, 4).values = rows.map((item) => [item.id, item.point, item.description, item.impact]);
  const range = sheet.getRangeByIndexes(2, 0, rows.length + 1, 4);
  range.format.wrapText = true;
  applyBorders(range);
  sheet.getRange("A:A").format.columnWidthPx = 70;
  sheet.getRange("B:B").format.columnWidthPx = 190;
  sheet.getRange("C:C").format.columnWidthPx = 300;
  sheet.getRange("D:D").format.columnWidthPx = 190;
  for (let row = 4; row < 4 + rows.length; row += 1) {
    sheet.getRange(`A${row}:D${row}`).format.rowHeightPx = 42;
  }
}

async function main() {
  const args = parseArgs(process.argv);
  const inputPath = path.resolve(args.input);
  const outputPath = path.resolve(args.output);
  const markdown = await fs.readFile(inputPath, "utf8");
  const parsed = parseMarkdown(markdown, args.title);

  if (parsed.cases.length === 0) {
    throw new Error("No test case table found. Expected header: | ID | 优先级 | 类型 | 测试点 | 前置条件 | 测试步骤 | 预期结果 |");
  }

  const artifactTool = await ensureArtifactTool();
  const workbook = await buildWorkbook(artifactTool, parsed, args);

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  if (args.preview) {
    const base = outputPath.replace(/\.xlsx$/i, "");
    for (const sheetName of ["测试用例", "汇总", "待确认"]) {
      const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
      await fs.writeFile(`${base}-${sheetName}.png`, new Uint8Array(await preview.arrayBuffer()));
    }
  }

  const output = await artifactTool.SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  console.log(`Generated: ${outputPath}`);
  console.log(`Cases: ${parsed.cases.length}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});

