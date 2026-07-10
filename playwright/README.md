# CRM Playwright 自动化说明

这个目录目前保留了历史调试脚本，同时新增了一套更稳定的正式测试入口。

## 推荐入口

正式用例放在：

- `tests/pc/`：PC 端浏览器自动化
- `tests/webview/`：Android WebView CDP 自动化
- `helpers/`：环境变量、WebView 连接、测试数据等公共方法

历史调试脚本仍保留在目录根部，后续确认稳定后再逐步迁移或归档。

## 环境配置

复制 `.env.example` 为 `.env`，并填写本地账号、密码和 WebView 连接地址。

关键配置：

```env
CRM_BASE_URL=https://lxcrm-staging.weiwenjia.com
CRM_USERNAME=your_username
CRM_PASSWORD=your_password
WEBVIEW_CDP_ENDPOINT=http://localhost:9222
```

`.env` 里不要提交真实账号、密码、token 或模型 Key。

## 运行命令

在 `/Users/mured/wwj` 下执行：

```bash
npm run test:pc
npm run test:webview
npm run test:webview:connect
npm run test:ui
npm run test:report
```

## WebView 前置条件

运行 WebView 用例前，需要先连接设备并开启端口转发：

```bash
adb forward tcp:9222 localabstract:chrome_devtools_remote
```

如果 APP 使用的是指定 WebView remote 名称，需要按实际进程替换：

```bash
adb shell cat /proc/net/unix | grep webview
adb forward tcp:9222 localabstract:webview_devtools_remote_xxxxx
```

## 后续迁移建议

1. 把稳定的历史 `.spec.ts` 逐步迁移到 `tests/pc` 或 `tests/webview`
2. 把一次性排障脚本迁移到 `tools/debug`
3. 把截图、HTML、JSON、Excel 等产物迁移到 `outputs`
4. 把真实账号从脚本里移除，统一使用 `.env`
