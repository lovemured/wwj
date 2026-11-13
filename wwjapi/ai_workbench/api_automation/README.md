# AI 工作台接口自动化脚本

这是一套 AI 工作台二期 pytest 接口自动化脚本，当前覆盖：

- PC 端 9 个前台看板接口契约检查；
- APP `/api/v2/ai_workbenches` 接口结构检查；
- PC/APP 列表数据结构一致性；
- 工作台新增、列表、详情、规则选项、筛选字段接口；
- 新建模板 9 个看板默认开启；
- 自定义规则/筛选条件上限和灰测字段契约；
- AI分析权限、`processing/partial/completed` 状态和轮询接口；
- 算力消费查询和分页字段；
- 无效 token 鉴权校验；
- “逾期不包含今天”“同一数据取最高优先级”等离线业务规则。

默认不会执行在线接口，也不会触发手动 AI 分析、写配置或删除数据。需要在线验证时必须显式打开环境变量。

## 安装依赖

```bash
python -m pip install pytest requests
```

## 运行离线规则测试

```bash
PYTHONPYCACHEPREFIX=/tmp/aiwb-pycache \
python3 -m pytest ai_workbench/api_automation/test_rules.py -q
```

## 运行在线只读接口用例

不要把 token 写入代码或提交到仓库，使用环境变量：

```bash
export AIWB_PC_TOKEN='测试环境PC token'
export AIWB_MOBILE_TOKEN='测试环境APP token'
export AIWB_PC_BASE_URL='https://lxcrm-api-test.weiwenjia.com'
export AIWB_MOBILE_BASE_URL='https://lxcrm-api-test.weiwenjia.com'
export AIWB_WORKBENCH_ID='1'
export AIWB_PERIOD_START='2026-09-01'
export AIWB_PERIOD_END='2026-09-18'
export AIWB_RUN_ONLINE='true'

PYTHONPYCACHEPREFIX=/tmp/aiwb-pycache \
python3 -m pytest ai_workbench/api_automation/test_api_contract.py \
  ai_workbench/api_automation/test_settings_api.py \
  ai_workbench/api_automation/test_power_logs.py -q
```

如果只设置 PC token，APP 用例会自动跳过；如果没有设置 token，在线用例会跳过。

## 运行 AI异步/手动分析用例

这组用例可能触发 AI 分析并消耗算力，只有确认要执行时才打开：

```bash
export AIWB_RUN_ONLINE='true'
export AIWB_RUN_MANUAL_ANALYSIS='true'

PYTHONPYCACHEPREFIX=/tmp/aiwb-pycache \
python3 -m pytest ai_workbench/api_automation/test_ai_flow.py -q
```

## 验证线上预设模板默认状态

需要提供线上预设模板 ID：

```bash
export AIWB_PRESET_WORKBENCH_ID='线上预设模板ID'
PYTHONPYCACHEPREFIX=/tmp/aiwb-pycache \
python3 -m pytest ai_workbench/api_automation/test_settings_api.py \
  -k preset_panel_states -q
```

预期：

- `contract_receipt_management.status == true`
- `team_performance_distribution.status == false`
- `team_process_distribution.status == false`

## 文件说明

| 文件 | 作用 |
|---|---|
| `test_api_contract.py` | 前台 PC/移动端看板接口、统一响应壳、鉴权 |
| `test_settings_api.py` | 工作台设置页、默认看板、AI能力、规则和筛选配置 |
| `test_ai_flow.py` | 手动分析权限、AI结果状态、轮询 |
| `test_power_logs.py` | 算力消费记录和筛选字段 |
| `test_frontend_schema.py` | 前台看板返回字段契约 |
| `test_settings_mutation.py` | 可选的工作台新增/编辑/删除生命周期 |
| `test_rules.py` | 不访问环境的业务规则单元测试 |
| `client.py` | 请求客户端、响应结构断言 |
| `config.py` | 环境变量配置 |

## 后续补充接口的方式

1. 在 `test_api_contract.py` 增加真实 endpoint。
2. 在测试数据文件中维护命中、未命中和边界数据 ID。
3. 增加字段、排序、分页、权限和状态断言。
4. 对写接口使用专用测试数据，并在 fixture 中做清理，保证可重复执行。
5. 将测试环境、回归环境分别通过环境变量或 CI secret 注入。
