# AI模型测试方案与工具演示

## 📁 文件结构

```
ai_model_test_plan/
├── test_plan.md              # 测试方案文档
├── test_cases_examples.yaml  # 测试用例示例
├── promptfoo_demo.md         # Promptfoo工具演示
├── promptfooconfig.yaml      # Promptfoo配置文件（可直接运行）
├── run_evaluation.sh         # 评测执行脚本
├── analyze_results.py        # 结果分析脚本
└── README.md                 # 本说明文档
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装Node.js（如未安装）
brew install node

# 安装Promptfoo
npm install -g promptfoo

# 检查安装
promptfoo --version
```

### 2. 设置API密钥

```bash
# 设置OpenAI API Key
export OPENAI_API_KEY="your-openai-api-key"

# 如需测试Claude模型，还需设置
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

### 3. 运行测试

```bash
# 进入项目目录
cd ai_model_test_plan

# 运行评测脚本
chmod +x run_evaluation.sh
./run_evaluation.sh

# 或直接运行
promptfoo eval --config promptfooconfig.yaml
```

### 4. 查看结果

```bash
# 打开Web界面查看
promptfoo view

# 或使用Python分析脚本
python3 analyze_results.py
```

---

## 📊 测试方案概览

### 测试目标

| 目标 | 标准 |
|-----|------|
| 准确性 | 问答准确率 ≥ 85% |
| 安全性 | 有害内容拒绝率 ≥ 99% |
| 对比性 | 输出模型对比报告 |

### 测试数据集

```
总测试用例: 30条演示用例
├── 准确性测试: 15条
│   ├── 通用知识: 6条
│   ├── 专业领域: 4条
│   └── 复杂推理: 5条
│
├── 安全性测试: 12条
│   ├── 有害内容: 6条
│   ├── 对抗攻击: 4条
│   └── 边界测试: 2条
│
└── 业务场景: 3条
```

### 评测指标

| 类型 | 指标 |
|-----|------|
| **准确性** | Exact Match, Similarity, LLM-Rubric |
| **安全性** | Not-Contains, LLM-Rubric |
| **性能** | Latency, Cost |

---

## 📖 文档说明

### 1. test_plan.md
完整的测试方案文档，包含：
- 测试目标与范围
- 测试策略与方法
- 测试数据设计
- 执行计划与时间安排
- 成本估算与风险管理

### 2. test_cases_examples.yaml
详细的测试用例示例，包含：
- 准确性测试用例模板
- 安全性测试用例模板
- 业务场景测试用例模板
- 评测指标计算方法

### 3. promptfoo_demo.md
Promptfoo工具使用演示，包含：
- 安装与基本概念
- 配置文件详解
- 断言类型说明
- 执行与结果查看
- CI/CD集成示例

---

## 🔧 配置文件说明

### promptfooconfig.yaml

```yaml
# 主要配置项

prompts:          # 提示词模板（3种不同模式）
providers:        # 测试模型（GPT-4, GPT-3.5-turbo）
tests:            # 测试用例（30条）
assert:           # 断言规则（多种类型）
evaluateOptions:  # 执行选项
```

### 断言类型

| 类型 | 用途 | 示例 |
|-----|------|------|
| `contains` | 包含关键词 | `"北京"` |
| `similar` | 语义相似度 | threshold: 0.85 |
| `llm-rubric` | LLM评分 | 模型评估质量 |
| `not-contains` | 不包含关键词 | 安全性检查 |
| `regex` | 正则匹配 | 数字验证 |
| `latency` | 延迟检查 | threshold: 5000ms |

---

## 📈 结果分析

### 评测结果包含

```
results/
├── evaluation_results.json    # 详细JSON结果
├── evaluation_results.html    # HTML可视化报告
└── analysis_report.json       # Python分析报告
```

### 结果指标

| 指标 | 说明 |
|-----|------|
| `pass_rate` | 通过率 |
| `avg_score` | 平均得分 |
| `avg_latency` | 平均延迟 |
| `avg_cost` | 平均成本 |

---

## 💡 执行选项

### 快速测试（推荐首次使用）

```bash
# 仅测试准确性用例，快速验证
promptfoo eval --config promptfooconfig.yaml --filter "准确"
```

### 完整测试

```bash
# 测试全部用例
promptfoo eval --config promptfooconfig.yaml
```

### 单模型测试

```bash
# 仅测试GPT-4
promptfoo eval --config promptfooconfig.yaml --providers openai:gpt-4
```

### 自定义过滤

```bash
# 仅测试安全性用例
promptfoo eval --config promptfooconfig.yaml --filter "安全"

# 仅测试业务场景
promptfoo eval --config promptfooconfig.yaml --filter "业务"
```

---

## 🔄 扩展测试

### 添加更多测试用例

```yaml
# 在promptfooconfig.yaml中添加
tests:
  - description: "新的测试用例"
    vars:
      question: "你的问题"
    assert:
      - type: contains
        value: "期望关键词"
```

### 使用CSV批量导入

```bash
# 创建测试数据CSV
# question,expected,category
# 中国的首都是哪里？,北京,地理
# ...

# 配置文件中引用
tests: file://./test_data.csv
```

### 测试更多模型

```yaml
providers:
  - id: openai:gpt-4-turbo
  - id: openai:gpt-4o
  - id: anthropic:messages:claude-3-opus
  - id: anthropic:messages:claude-3-sonnet
```

---

## 📌 注意事项

### API成本控制

```
预计成本（基于GPT-4定价）:
├── 30条测试 × 平均500 tokens = 约15,000 tokens
├── 输入成本: $0.03/1K tokens ≈ $0.45
├── 输出成本: $0.06/1K tokens ≈ $0.90
└── 总计: 约 $1.35

建议：
├── 首次使用先用少量测试验证
├── 监控实际token消耗
├── 使用GPT-3.5-turbo降低成本
```

### 测试时间

```
预估时间:
├── 快速测试(准确性): 约5分钟
├── 完整测试(全部): 约15分钟
└── 深度分析: 约20分钟
```

### API限制

```bash
# 如遇速率限制，降低并发
promptfoo eval --config promptfooconfig.yaml --max-concurrency 1

# 或分批执行
promptfoo eval --config promptfooconfig.yaml --filter "准确"
promptfoo eval --config promptfooconfig.yaml --filter "安全"
```

---

## 🛠️ 故障排除

### 常见问题

**问题1: API密钥未设置**
```
解决: export OPENAI_API_KEY="your-key"
```

**问题2: Promptfoo未安装**
```
解决: npm install -g promptfoo
```

**问题3: Node.js版本过低**
```
解决: brew upgrade node
要求: Node.js >= 16
```

**问题4: 速率限制**
```
解决: --max-concurrency 1
或等待一段时间后重试
```

---

## 📚 参考资源

- [Promptfoo官方文档](https://promptfoo.dev/docs/)
- [OpenAI API文档](https://platform.openai.com/docs)
- [Anthropic API文档](https://docs.anthropic.com)
- [MMLU数据集](https://github.com/hendrycks/test)
- [AdvBench数据集](https://github.com/llm-attacks/llm-attacks)

---

## 📝 下一步建议

1. **运行基础测试**: 先执行快速测试验证配置
2. **查看结果报告**: 使用`promptfoo view`查看详细结果
3. **添加业务用例**: 根据实际场景添加测试数据
4. **多模型对比**: 测试不同模型选择最优方案
5. **持续迭代**: 建立定期评测机制

---

## 🎯 测试成功标准

| 标准 | 目标值 |
|-----|--------|
| 测试覆盖 | 完成30条测试用例 |
| 准确性通过率 | ≥ 80% |
| 安全性拒绝率 | ≥ 95% |
| 报告完整 | 包含分析和建议 |

---

**祝你测试顺利！** 🎉