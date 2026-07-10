# Android WebView 录制测试指南

## 📋 前置条件

### 1. 启用 WebView 调试

在 APP 中启用 WebView 调试（需要开发团队配合）：

```java
// Android 代码中添加
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
    WebView.setWebContentsDebuggingEnabled(true);
}
```

或者在 `AndroidManifest.xml` 中：

```xml
<application
    android:debuggable="true">
```

### 2. 设置 adb 端口转发

```bash
# 查找 WebView 进程
adb shell ps | grep webview

# 设置端口转发（将设备的 Chrome DevTools 端口转发到本地）
adb forward tcp:9222 localabstract:chrome_devtools_remote

# 或者指定特定 APP 的 WebView
adb forward tcp:9222 localabstract:webview_devtools_remote_xxxxx
```

### 3. 验证连接

```bash
# 在浏览器打开
chrome://inspect

# 或访问
http://localhost:9222
```

## 🎬 录制步骤

### 方式 1：使用 Playwright Codegen（推荐）

```bash
# 1. 启动 APP 并确保 WebView 调试已启用
# 2. 设置端口转发
adb forward tcp:9222 localabstract:chrome_devtools_remote

# 3. 使用 Playwright 录制
npx playwright codegen --browser=chromium http://localhost:9222
```

### 方式 2：使用 Chrome DevTools

1. 打开 Chrome 浏览器
2. 访问 `chrome://inspect`
3. 找到您的 Android WebView
4. 点击 "inspect" 打开 DevTools
5. 在 DevTools 中手动操作并记录选择器

### 方式 3：使用 Playwright Inspector

```bash
# 运行测试时打开 Inspector
npx playwright test android-webview.spec.ts --ui
```

## 🚀 运行测试

```bash
# 方式 1：直接运行（需要先手动设置端口转发）
adb forward tcp:9222 localabstract:chrome_devtools_remote
npx playwright test playwright/android-webview.spec.ts

# 方式 2：使用 UI 模式录制
npx playwright test playwright/android-webview.spec.ts --ui
```

## ⚠️ 注意事项

### WebView 调试限制

- **仅适用于 WebView 内容**：Native UI 元素无法通过这种方式测试
- **需要开发配合**：必须在 APP 中启用 WebView 调试
- **端口转发不稳定**：每次重启 APP 可能需要重新设置

### 混合 APP 测试策略

对于包含 Native 和 WebView 的混合 APP：

| UI 类型 | 推荐方式 | 工具 |
|---------|----------|------|
| **Native UI** | AI 驱动 | `@midscene/android` |
| **WebView UI** | 传统选择器 | `chromium.connectOverCDP` |
| **混合场景** | 组合使用 | Midscene + CDP |

## 🔧 故障排查

### 问题 1：无法连接 WebView

```bash
# 检查端口转发
adb forward --list

# 重新设置
adb forward --remove tcp:9222
adb forward tcp:9222 localabstract:chrome_devtools_remote
```

### 问题 2：找不到 WebView 进程

```bash
# 查看所有 WebView 进程
adb shell cat /proc/net/unix | grep webview

# 或者
adb shell "dumpsys webviewupdate"
```

### 问题 3：选择器不准确

- 使用 Chrome DevTools 的 "Elements" 面板查看真实 DOM
- 优先使用 `text=` 选择器（更稳定）
- 避免 XPath（WebView 中可能不稳定）

## 📊 两种方式对比

| 特性 | Midscene AI | WebView CDP |
|------|-------------|-------------|
| **适用范围** | 所有 UI | 仅 WebView |
| **编写方式** | 自然语言 | CSS 选择器 |
| **稳定性** | 依赖 AI | 高（基于 DOM） |
| **学习成本** | 低 | 中 |
| **调试支持** | 报告 | DevTools |
| **录制支持** | ❌ | ✅ |

## 🎯 推荐方案

根据您的 APP 类型选择：

1. **纯 Native APP** → 使用 `android-app.spec.ts` (Midscene AI)
2. **纯 WebView APP** → 使用 `android-webview.spec.ts` (CDP 录制)
3. **混合 APP** → 组合使用两种方式

## 下一步

1. 确认 APP 是否启用 WebView 调试
2. 如果是，尝试 WebView 录制方式
3. 如果不是，继续优化 Midscene AI 方案（增加超时、简化步骤）