# CRM 导入完整流程测试脚本

用于验证 CRM Excel 导入链路，覆盖线索、客户、联系人、商机、报价单、合同、回款计划、回款记录、开票记录、产品等模块：

1. 下载指定模块导入模板。
2. 在模板可填写区域写入测试数据。
3. 上传 Excel 到 OSS。
4. 调用 `entity_loaders/new -> upload -> import`。
5. 监听 faye 导入消息。
6. 查询导入历史和最新业务列表摘要。

## 完整流程

```bash
python3 tools/error-report-import/error_report_import_tester.py full-flow \
  --env staging \
  --token "你的 user_token" \
  --module lead \
  --output-dir outputs/error-report-import/staging-full-flow \
  --rows 2 \
  --fill-mode all
```

脚本会输出：

- 下载模板文件路径。
- 生成后的测试 Excel 文件路径。
- OSS 附件 ID 和文件 URL。
- `new/upload/import` 接口响应。
- faye 中的 `validated_result` / `imported_result`，如果环境有推送。
- `import_histories` 查询结果。
- 最新业务列表摘要。
- `import_result_summary`，以导入历史或 faye 的 `success_count/fail_count` 判断业务是否成功。

## 批量验证多个模块

```bash
python3 tools/error-report-import/error_report_import_tester.py batch-full-flow \
  --env staging \
  --token "你的 user_token" \
  --modules customer,contact,opportunity,quotation,contract,payment-plan,received-payment,invoiced-payment,product \
  --output-dir outputs/error-report-import/staging-batch \
  --rows 1 \
  --fill-mode all \
  --validate-wait 20 \
  --import-wait 35 \
  --continue-on-error
```

客户、商机、报价单、合同会在下载模板和导入前自动选择一个启用的业务类型。如果要指定业务类型，可以这样写：

```bash
python3 tools/error-report-import/error_report_import_tester.py batch-full-flow \
  --env staging \
  --token "你的 user_token" \
  --modules customer,opportunity,quotation,contract \
  --business-type-map "customer=客户业务类型2,opportunity=792,quotation=报价单业务类型2,contract=796" \
  --output-dir outputs/error-report-import/staging-business-type \
  --rows 1 \
  --fill-mode all
```

模块参数支持：

| 参数 | 模块 |
|---|---|
| `lead` | 线索 |
| `customer` | 客户 |
| `contact` | 联系人 |
| `opportunity` | 商机 |
| `quotation` | 报价单 |
| `contract` | 合同 |
| `payment-plan` | 回款计划 |
| `received-payment` | 回款记录 |
| `invoiced-payment` | 开票记录 |
| `product` | 产品 |

## 分步执行

下载模板：

```bash
python3 tools/error-report-import/error_report_import_tester.py download-template \
  --env staging \
  --token "你的 user_token" \
  --module lead \
  --output outputs/error-report-import/lead-template.xlsx
```

基于模板生成测试文件：

```bash
python3 tools/error-report-import/error_report_import_tester.py generate-source-from-template \
  --template outputs/error-report-import/lead-template.xlsx \
  --output outputs/error-report-import/lead-source.xlsx \
  --rows 2 \
  --fill-mode all
```

导入已有文件：

```bash
python3 tools/error-report-import/error_report_import_tester.py import-flow \
  --env staging \
  --token "你的 user_token" \
  --module lead \
  --file outputs/error-report-import/lead-source.xlsx
```

只查导入历史：

```bash
python3 tools/error-report-import/error_report_import_tester.py history \
  --env staging \
  --token "你的 user_token" \
  --module lead
```

查询某个模块可用业务类型：

```bash
python3 tools/error-report-import/error_report_import_tester.py business-types \
  --env staging \
  --token "你的 user_token" \
  --module customer
```

## 环境配置

脚本内置两个环境：

| 环境 | 命令参数 | 默认域名 |
|---|---|---|
| 测试环境 | `--env test` | `https://lxcrm-test.weiwenjia.com` |
| 回归环境 | `--env staging` | `https://lxcrm-staging.weiwenjia.com` |

也可以通过参数覆盖：

```bash
--api https://xxx
--entity-loader-prefix /api/entity_loaders
--entity-loader-new-prefix /api/pc/entity_loaders
--entity-loader-history-prefix /api/pc/entity_loaders
--qiniu-token-path /api/qiniu/auth/oss_upload_token.json
--faye-url https://faye-dev.ikcrm.com/faye
```

支持环境变量：

```bash
export WWJ_IMPORT_ENV=staging
export WWJ_USER_TOKEN="你的 user_token"
export WWJ_BUSINESS_TYPE_MAP="customer=793,opportunity=791,quotation=797,contract=795"
```

之后可省略 `--env` 和 `--token`。

## 填充模式

`--fill-mode all` 是默认模式，会尽量填写模板里的每个字段，适合覆盖字段解析和导入映射：

- 文本、备注、多行文本自动生成测试值。
- 电话、手机、邮箱、网址生成合法格式。
- 整数、小数、金额、日期、时间生成对应类型值。
- 下拉、多选、级联、用户字段优先从模板中的 `Sheet字段名` 或示例提示的 `Sheet_字段名` 中取合法选项。
- `ID` 字段默认不填，避免误触发更新导入。

如果只想跑最小可用导入，可以改成：

```bash
--fill-mode minimal
```

## 当前注意点

- 脚本会自动调用 `/api/v2/user/info` 获取当前用户 ID 和组织 ID，避免 OSS 上传时附件归属不一致。
- 回归环境的前端接口是混合路径：`new/history` 使用 `/api/pc/entity_loaders`，模板、上传、导入使用 `/api/entity_loaders`。
- 造数时会自动填写模板里的必填字段；如果字段有对应 `Sheet字段名` 选项页，会取合法选项。
- 客户、商机、报价单、合同存在业务类型；脚本会把同一个 `custom_field_template_id` 同时带到模板下载、`new`、`upload`、`import`，保证字段模板和导入解析一致。
- 报价单、合同、回款和开票等模块会自动取已有客户、联系人、商机、合同、产品作为关联数据。
- 回款计划、回款记录、开票记录会优先使用合同所属客户，避免“合同 ID 不属于该客户”的业务校验失败。
- 客户模板存在特殊表头布局，脚本会自动复制可填写表头再写入数据。
- faye 默认地址是 `https://faye-dev.ikcrm.com/faye`，如回归环境配置不同，可通过 `--faye-url` 覆盖。
- 如果接口返回“导入中，请稍后”但 faye、导入历史、线索列表都没有结果，应优先排查环境异步任务或 faye 推送链路。

## 已验证结果

在回归环境 `https://lxcrm-staging.weiwenjia.com`，使用当前企业 token 验证过：

- 线索：成功导入全字段数据。
- 客户：成功导入。
- 联系人：成功导入。
- 商机：成功导入。
- 报价单：成功导入。
- 合同：成功导入。
- 回款计划：成功导入。
- 回款记录：成功导入。
- 开票记录：成功导入。
- 产品：成功导入。
