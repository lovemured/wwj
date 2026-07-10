# CRM Leads E2E 测试使用说明

## 安装依赖

```bash
npm install @playwright/test
npx playwright install
```

## 配置环境变量

创建 `.env` 文件：

```env
CRM_USERNAME=your_username
CRM_PASSWORD=your_password
CRM_TOKEN=your_api_token
```

## 运行测试

```bash
# 运行所有测试
npx playwright test crm-leads-e2e.spec.ts

# 运行单个测试
npx playwright test crm-leads-e2e.spec.ts -g "创建线索 - 正常流程"

# 带界面运行（推荐调试时使用）
npx playwright test crm-leads-e2e.spec.ts --ui

# 生成HTML报告
npx playwright test crm-leads-e2e.spec.ts --reporter=html
npx playwright show-report
```

## 录制测试（手动操作生成代码）

```bash
# 打开录制工具
npx playwright codegen https://lxcrm-test.weiwenjia.com

# 录制并保存
npx playwright codegen https://lxcrm-test.weiwenjia.com -o my-test.spec.ts
```

## 调试技巧

```bash
# 查看浏览器操作
npx playwright test --debug

# 只运行失败的测试
npx playwright test --last-failed
```

## 测试报告位置

- 截图：`test-results/` 目录
- 视频录像：失败时自动保存
- HTML报告：`playwright-report/` 目录