# AI模型测试 - 多API提供商配置指南

## 一、可用的API提供商选项

### 1. 国内API服务（推荐，稳定可访问）

| 服务商 | 模型 | 特点 | 注册地址 |
|-------|------|------|---------|
| **阿里云通义千问** | qwen-turbo, qwen-plus | 价格实惠，速度快 | https://dashscope.console.aliyun.com/ |
| **百度文心一言** | ernie-bot, ernie-bot-turbo | 企业级稳定 | https://console.bce.baidu.com/qianfan/ |
| **智谱ChatGLM** | glm-4, glm-3-turbo | 性价比高 | https://open.bigmodel.cn/ |
| **DeepSeek** | deepseek-chat | 最新开源模型 | https://platform.deepseek.com/ |
| **Moonshot Kimi** | moonshot-v1 | 长文本能力强 | https://platform.moonshot.cn/ |

### 2. 国际API服务（需代理）

| 服务商 | 模型 | 特点 | 注册地址 |
|-------|------|------|---------|
| **Anthropic Claude** | claude-3-opus, claude-3-sonnet | 安全性强 | https://console.anthropic.com/ |
| **Google Gemini** | gemini-pro | 多模态能力 | https://makersuite.google.com/ |
| **Azure OpenAI** | gpt-4, gpt-35-turbo | 企业合规 | https://portal.azure.com/ |

---

## 二、各API配置示例

### 阿里云通义千问

```yaml
# config_qwen.yaml
providers:
  - id: 'custom:qwen'
    config:
      apiBase: 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation'
      headers:
        Authorization: 'Bearer ${DASHSCOPE_API_KEY}'
      bodyTemplate:
        model: 'qwen-plus'
        input:
          prompt: '{{prompt}}'
        parameters:
          temperature: 0.3
          max_tokens: 300
```

环境变量设置：
```bash
export DASHSCOPE_API_KEY="your-dashscope-key"
```

### 百度文心一言

```yaml
# config_ernie.yaml
providers:
  - id: 'custom:ernie'
    config:
      apiBase: 'https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions'
      headers:
        Content-Type: 'application/json'
      bodyTemplate:
        model: 'ernie-bot-4'
        messages:
          - role: 'user'
            content: '{{prompt}}'
        temperature: 0.3
```

### 智谱ChatGLM

```yaml
# config_glm.yaml
providers:
  - id: 'custom:glm'
    config:
      apiBase: 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
      headers:
        Authorization: 'Bearer ${ZHIPUAI_API_KEY}'
      bodyTemplate:
        model: 'glm-4'
        messages:
          - role: 'user'
            content: '{{prompt}}'
        temperature: 0.3
        max_tokens: 300
```

环境变量设置：
```bash
export ZHIPUAI_API_KEY="your-zhipuai-key"
```

### DeepSeek

```yaml
# config_deepseek.yaml
providers:
  - id: 'openai:deepseek-chat'
    config:
      apiBase: 'https://api.deepseek.com/v1'
      apiKey: '${DEEPSEEK_API_KEY}'
      temperature: 0.3
      max_tokens: 300
```

环境变量设置：
```bash
export DEEPSEEK_API_KEY="your-deepseek-key"
```

---

## 三、使用Promptfoo调用自定义API

Promptfoo支持通过`http` provider调用任何兼容OpenAI格式的API：

```yaml
providers:
  # HTTP provider方式（通用）
  - id: 'http'
    config:
      url: 'https://api.deepseek.com/v1/chat/completions'
      method: 'POST'
      headers:
        Content-Type: 'application/json'
        Authorization: 'Bearer ${DEEPSEEK_API_KEY}'
      body:
        model: 'deepseek-chat'
        messages:
          - role: 'user'
            content: '{{prompt}}'
        temperature: 0.3
      # 解析响应
      responseParser: 'json.choices[0].message.content'
```

---

## 四、API Key获取步骤

### 阿里云通义千问

1. 访问 https://dashscope.console.aliyun.com/
2. 登录阿里云账号
3. 开通灵积模型服务
4. 创建API-KEY管理中的密钥
5. 复制密钥

**价格参考**：
- qwen-turbo: ¥0.008/千tokens
- qwen-plus: ¥0.04/千tokens
- qwen-max: ¥0.12/千tokens

### 智谱ChatGLM

1. 访问 https://open.bigmodel.cn/
2. 注册账号（支持手机号）
3. 进入API管理页面
4. 创建API Key
5. 新用户有免费额度

**价格参考**：
- glm-3-turbo: ¥0.001/千tokens（非常便宜）
- glm-4: ¥0.1/千tokens

### DeepSeek

1. 访问 https://platform.deepseek.com/
2. 注册账号
3. 获取API Key
4. 新用户赠送500万tokens

**价格参考**：
- deepseek-chat: ¥0.001/千tokens

---

## 五、推荐配置方案

根据你的情况，推荐使用**智谱ChatGLM**或**DeepSeek**：

```yaml
# 推荐配置：使用国内API
description: "使用国内API的AI评测测试"

prompts:
  - "请回答：{{question}}"

providers:
  # 智谱ChatGLM（推荐）
  - id: 'http'
    label: 'GLM-4'
    config:
      url: 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
      method: 'POST'
      headers:
        Content-Type: 'application/json'
        Authorization: 'Bearer ${ZHIPUAI_API_KEY}'
      body:
        model: 'glm-4'
        messages:
          - role: 'user'
            content: '{{prompt}}'
        temperature: 0.3
        max_tokens: 200
      responseParser: 'json.choices[0].message.content'

  # DeepSeek（推荐）
  - id: 'http'
    label: 'DeepSeek'
    config:
      url: 'https://api.deepseek.com/v1/chat/completions'
      method: 'POST'
      headers:
        Content-Type: 'application/json'
        Authorization: 'Bearer ${DEEPSEEK_API_KEY}'
      body:
        model: 'deepseek-chat'
        messages:
          - role: 'user'
            content: '{{prompt}}'
        temperature: 0.3
        max_tokens: 200
      responseParser: 'json.choices[0].message.content'

tests:
  - description: "地理知识"
    vars:
      question: "中国的首都是哪里？"
    assert:
      - type: contains
        value: "北京"

  - description: "科学知识"
    vars:
      question: "水的化学式是什么？"
    assert:
      - type: similar
        value: "H2O"
        threshold: 0.8

  - description: "数学计算"
    vars:
      question: "5乘以3等于多少？"
    assert:
      - type: contains
        value: "15"

outputPath: ./results/test_results.json
```

---

## 六、执行命令

```bash
# 设置API密钥
export ZHIPUAI_API_KEY="your-key"  # 智谱
# 或
export DEEPSEEK_API_KEY="your-key"  # DeepSeek

# 运行测试
cd /Users/mured/ai_model_test_plan
npx promptfoo eval --config domestic_api_test.yaml

# 查看结果
npx promptfoo view
```

---

## 七、成本对比

| 服务商 | 测试成本估算（1000次） | 备注 |
|-------|----------------------|------|
| 智谱GLM-3-turbo | ¥1 | 最便宜 |
| DeepSeek | ¥1 | 新用户免费额度 |
| 阿里qwen-turbo | ¥8 | 稳定可靠 |
| OpenAI GPT-3.5 | $0.2 (~¥1.4) | 需代理 |
| OpenAI GPT-4 | $3 (~¥21) | 需代理 |

---

**推荐顺序**：智谱ChatGLM > DeepSeek > 阿里通义千问

需要我为你准备具体的配置文件吗？