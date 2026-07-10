# 测试用例 Excel 生成脚本

这个工具用于把 Markdown 格式的测试用例文档转换成 Excel，适合后续把需求分析结果统一落到 `/Users/mured/wwj/需求文档` 目录管理。

## 支持的 Markdown 表格

脚本会自动识别以下三类表格：

1. 测试用例表

```markdown
| ID | 优先级 | 类型 | 测试点 | 前置条件 | 测试步骤 | 预期结果 |
|---|---|---|---|---|---|---|
| TC-001 | P0 | 功能 | 正常导入 | 已登录 | 1. 上传文件<br>2. 点击导入 | 导入成功 |
```

2. 测试范围表

```markdown
| 范围 | 说明 |
|---|---|
| 页面入口 | 部分导入成功页、修正后导入按钮 |
```

3. 待确认事项表

```markdown
| 编号 | 待确认点 | 说明 |
|---|---|---|
| Q1 | 文件格式范围 | 是否仅支持 .xlsx |
```

## 生成当前 STORY 23598 Excel

在 `/Users/mured/wwj/wwjapi` 目录下执行：

```bash
/Users/mured/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
  tools/testcase-excel/markdown-to-testcase-excel.mjs \
  --input story-23598-error-report-direct-import-testcases.md \
  --output /Users/mured/wwj/需求文档/story-23598-error-report-direct-import-testcases.xlsx \
  --source https://zentao.weiwenjia.com/story-view-23598-2-project-2107.html
```

## 生成预览图

加上 `--preview` 会在 Excel 同目录生成每个 sheet 的 PNG 预览图：

```bash
/Users/mured/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
  tools/testcase-excel/markdown-to-testcase-excel.mjs \
  --input story-23598-error-report-direct-import-testcases.md \
  --output /Users/mured/wwj/需求文档/story-23598-error-report-direct-import-testcases.xlsx \
  --source https://zentao.weiwenjia.com/story-view-23598-2-project-2107.html \
  --preview
```

## 输出内容

Excel 会包含 3 个 sheet：

- `测试用例`：可筛选、冻结表头、按优先级着色
- `汇总`：用例总数、P0/P1/P2 统计、覆盖说明
- `待确认`：需求中需要产品或研发确认的问题

## 依赖说明

脚本默认使用本机 Codex runtime 中的 `@oai/artifact-tool`：

```text
/Users/mured/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules
```

如果以后 runtime 路径变化，可以通过环境变量指定：

```bash
ARTIFACT_TOOL_NODE_MODULES=/path/to/node_modules node tools/testcase-excel/markdown-to-testcase-excel.mjs --input xxx.md --output xxx.xlsx
```

