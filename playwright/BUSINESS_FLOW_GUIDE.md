# Midscene Android 业务流程测试指南

## 📋 目录
- [基础概念](#基础概念)
- [常用 AI 操作方法](#常用-ai-操作方法)
- [业务流程编写技巧](#业务流程编写技巧)
- [最佳实践](#最佳实践)
- [常见问题](#常见问题)

---

## 基础概念

### Midscene AI 的优势
- **无需写 xpath/resource-id**：使用自然语言描述即可
- **视觉识别**：AI 能看懂屏幕内容
- **智能定位**：自动识别按钮、输入框等元素

---

## 常用 AI 操作方法

### 1. aiAction - 执行操作
执行一系列 UI 操作（点击、输入、滑动等）

```typescript
// 点击操作
await testAgent.aiAction('点击【客户管理】按钮');

// 输入操作
await testAgent.aiAction('在姓名输入框输入"测试用户"');

// 组合操作（推荐）
await testAgent.aiAction('点击【新建】按钮，在名称框输入"产品001"，点击【保存】');
```

### 2. aiBoolean - 验证条件
判断页面上是否出现某些元素或文字

```typescript
// 验证文字
const hasSuccess = await testAgent.aiBoolean('页面出现"操作成功"提示');

// 验证按钮
const hasButton = await testAgent.aiBoolean('页面有【确认】按钮');

// 验证状态
const isLoggedIn = await testAgent.aiBoolean('页面显示用户头像或工作台');
```

### 3. aiQuery - 查询数据
从页面提取数据信息

```typescript
// 提取文字
const userName = await testAgent.aiQuery<string>('提取当前用户名称');

// 提取列表数量
const customerCount = await testAgent.aiQuery<number>('统计客户列表的数量');

// 提取多条数据
const customers = await testAgent.aiQuery<string[]>('提取所有客户的名称');
```

### 4. aiWaitFor - 等待条件
等待某个条件出现（最多等待指定时间）

```typescript
// 等待页面加载
await testAgent.aiWaitFor('页面出现【工作台】或【首页】', { timeout: 10000 });

// 等待提示消失
await testAgent.aiWaitFor('页面不再显示加载动画');
```

### 5. 其他常用方法

```typescript
// 点击特定位置
await testAgent.aiTap('登录按钮');
await testAgent.aiTap('屏幕右上角的设置图标');

// 输入文本
await testAgent.aiInput('测试文本', '备注输入框');

// 滑动屏幕
await testAgent.aiScroll('向下滑动一屏');

// 截图
await testAgent.aiScreenshot('保存当前页面截图');
```

---

## 业务流程编写技巧

### 1. 分步骤编写
将复杂业务拆分成多个小步骤：

```typescript
test('客户跟进流程', async () => {
  test.setTimeout(180000);

  const testAgent = ensureAgent();

  // 步骤 1：打开客户列表
  await testAgent.aiAction('点击【客户】菜单');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // 步骤 2：选择客户
  await testAgent.aiAction('点击客户列表中的第一个客户');

  // 步骤 3：添加跟进记录
  await testAgent.aiAction('点击【添加跟进】按钮');
  await testAgent.aiAction('在跟进内容输入框输入"电话联系，客户有意向"');

  // 步骤 4：保存
  await testAgent.aiAction('点击【保存】按钮');

  // 步骤 5：验证
  const success = await testAgent.aiBoolean('页面出现"保存成功"提示');
  expect(success).toBe(true);
});
```

### 2. 合并相关操作
减少 AI 调用次数，提高效率：

```typescript
// ✅ 推荐：合并操作
await testAgent.aiAction('点击【新建订单】，选择产品"手机"，输入数量10，点击【确定】');

// ❌ 不推荐：分步调用（会增加等待时间）
await testAgent.aiAction('点击【新建订单】');
await testAgent.aiAction('选择产品"手机"');
await testAgent.aiAction('输入数量10');
await testAgent.aiAction('点击【确定】');
```

### 3. 添加适当的等待时间
在关键步骤后添加等待：

```typescript
// 页面跳转后等待
await testAgent.aiAction('点击【提交】按钮');
await new Promise(resolve => setTimeout(resolve, 3000)); // 等待3秒

// 下一步操作
await testAgent.aiAction('点击【确认】按钮');
```

---

## 最佳实践

### 1. 使用描述性的提示词
让 AI 更容易理解你的意图：

```typescript
// ✅ 清晰的描述
await testAgent.aiAction('在用户名输入框（页面顶部左侧）输入"admin"');

// ❌ 模糊的描述
await testAgent.aiAction('输入admin');
```

### 2. 验证关键节点
在每个重要步骤后验证结果：

```typescript
// 提交表单后验证
await testAgent.aiAction('填写表单并提交');

// 等待响应
await new Promise(resolve => setTimeout(resolve, 2000));

// 验证成功
const isSuccess = await testAgent.aiBoolean('页面出现成功提示或跳转到列表页');
expect(isSuccess).toBe(true);
```

### 3. 处理异常情况
考虑可能的失败场景：

```typescript
test('搜索客户', async () => {
  const testAgent = ensureAgent();

  await testAgent.aiAction('在搜索框输入"不存在的客户名称"');
  await testAgent.aiAction('点击搜索按钮');

  // 验证两种可能的结果
  const hasResult = await testAgent.aiBoolean('页面显示客户列表');
  const hasEmpty = await testAgent.aiBoolean('页面显示"无搜索结果"');

  expect(hasResult || hasEmpty).toBe(true); // 任何一种结果都算通过
});
```

### 4. 合理设置超时时间
根据业务复杂度设置超时：

```typescript
// 简单操作：30-60秒
test('简单点击测试', async () => {
  test.setTimeout(60000);
});

// 中等复杂度：60-120秒
test('表单填写测试', async () => {
  test.setTimeout(120000);
});

// 复杂流程：120-180秒
test('完整业务流程', async () => {
  test.setTimeout(180000);
});
```

---

## 常见问题

### Q1: AI 操作速度慢怎么办？
**原因**：AI 需要截图分析，公司 API 处理图片需要时间

**解决方案**：
1. 合并多个操作到一个 aiAction
2. 使用更快的模型（联系公司管理员）
3. 减少不必要的验证步骤

### Q2: AI 找不到元素怎么办？
**解决方案**：
1. 使用更精确的描述："在页面右上角的【设置】图标"
2. 添加位置信息："在用户名输入框下方"
3. 使用多个关键词："点击【提交】或【确定】或【保存】按钮"

### Q3: 测试经常超时怎么办？
**解决方案**：
1. 增加 test.setTimeout 时间
2. 简化测试流程
3. 减少等待时间间隔
4. 检查公司 API 是否响应慢

### Q4: 如何调试测试？
**解决方案**：
1. 查看 Midscene 报告：`midscene_run/report/*.html`
2. 查看截图：报告中有每一步的截图
3. 查看日志：`test-results/*/error-context.md`

---

## 📝 完整业务流程示例

```typescript
import { test, expect } from '@playwright/test';
import { agentFromAdbDevice, getConnectedDevices } from '@midscene/android';

// 初始化代码...

test('完整的客户管理流程', async () => {
  test.setTimeout(180000); // 3分钟

  const testAgent = ensureAgent();

  // 1. 登录（已在 beforeAll 完成）

  // 2. 进入客户管理
  await testAgent.aiAction('点击底部导航栏的【客户】图标');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // 3. 新建客户
  await testAgent.aiAction('点击页面右上角的【+】按钮');
  await testAgent.aiAction('在客户姓名输入框输入"测试客户"，在电话输入框输入"13800138000"，在地址输入框输入"上海市浦东新区"');
  await testAgent.aiAction('点击【保存】按钮');
  await new Promise(resolve => setTimeout(resolve, 3000));

  // 4. 验证客户创建成功
  const customerCreated = await testAgent.aiBoolean('页面显示"测试客户"或客户列表包含新客户');
  expect(customerCreated).toBe(true);

  // 5. 搜索客户
  await testAgent.aiAction('在搜索框输入"测试客户"');
  await testAgent.aiAction('点击搜索按钮或按回车');
  await new Promise(resolve => setTimeout(resolve, 2000));

  // 6. 验证搜索结果
  const searchResult = await testAgent.aiBoolean('客户列表中显示"测试客户"');
  expect(searchResult).toBe(true);

  // 7. 编辑客户
  await testAgent.aiAction('点击"测试客户"所在行');
  await testAgent.aiAction('点击【编辑】按钮');
  await testAgent.aiAction('在备注输入框输入"这是测试备注"');
  await testAgent.aiAction('点击【保存】按钮');

  // 8. 验证编辑成功
  const editSuccess = await testAgent.aiBoolean('页面出现成功提示');
  expect(editSuccess).toBe(true);
});
```

---

## 🎯 下一步建议

1. **熟悉业务流程**：先手动操作几次，记录关键步骤
2. **编写测试脚本**：从简单流程开始，逐步增加复杂度
3. **优化提示词**：根据 AI 执行结果调整描述方式
4. **建立测试库**：积累常用操作，提高编写效率

---

**祝你测试顺利！如有问题，随时查看 Midscene 报告或联系团队。** 🚀