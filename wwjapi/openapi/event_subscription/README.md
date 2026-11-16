# 事件订阅回归工具

本目录整理自 staging 企业版、基础版事件订阅回归。支持保存订阅并回读、版本权限校验、真实回调匹配，以及移动端网关陌拜新增和签到删除。业务新增、批量操作、转换及导入继续复用仓库已有脚本，不重复提交。

仅支持 staging。运行依赖 Python 3.9+ 和 `requests`。所有 Token 通过环境变量传入；企业数据 ID、接收器地址和原始测试证据不随代码提交。

## 配置与事件数量

从 `wwjapi` 目录运行。设置当前测试账号 Token 和自己的接收器地址：

```bash
export CRM_WEBHOOK_TOKEN='<当前测试账号 Token>'
export CRM_WEBHOOK_CALLBACK='https://webhook.site/<接收器 UUID>'
python3 openapi/event_subscription/regression.py --output /tmp/webhook-catalog catalog
```

回调地址必须是实际接收地址，不能使用 `https://webhook.site/#!/view/...` 页面地址。结果存入 `--output`，日志中的订阅密钥会脱敏。原始回调可能包含业务数据，输出目录应保留在本地。

基础版最多 20 个事件；企业版最多 40 个。示例事件来自本次已执行的回归清单，使用前核对当前需求及 `event_types`：

```bash
python3 openapi/event_subscription/regression.py --output /tmp/webhook-basic configure \
  --events openapi/event_subscription/basic-20.json

# 对企业版账号使用企业版清单；不要对基础版执行此配置。
python3 openapi/event_subscription/regression.py --output /tmp/webhook-enterprise configure \
  --events openapi/event_subscription/enterprise-40.json
```

配置操作会替换该账号所在企业的订阅，先备份原配置，再保存并检查回读。它不会自动恢复；恢复时将原配置中的事件数组提交，并指定原接收器地址。不同企业的账号分别运行，不共享企业数据 ID。

## 基础版拦截企业版事件

先为基础版保存至少一个有效基础事件，再执行：

```bash
python3 openapi/event_subscription/regression.py --output /tmp/webhook-edition check-denied \
  --events openapi/event_subscription/enterprise-only-requirements.json
```

逐个提交“一个原基础事件 + 一个待拦截事件”，每次回读确认原配置未变。意外保存成功时会恢复原配置并回读，该案例仍记失败。请求总数不超过订阅上限，避免把“数量超限”误当作版本拦截。

`enterprise-only-requirements.json` 按需求口径包含产品标准单价变更。本次回归发现：基础版目录包含 `product.standard_unit_price_change`，且可以保存并收到真实回调；其余标注企业版的 49 个事件保存被拒绝。如果后续需求调整，需同步修改预期清单。

`test_webhook` 发送的是通用 `test.ping`。即使传入企业版事件名并返回成功，也不能证明该企业版业务事件被推送。

## 验证业务事件

先保存包含目标事件的订阅，再记录基线。通过页面或仓库业务脚本触发操作后，用本次产生的数据 ID 核对：

```bash
python3 openapi/event_subscription/regression.py --output /tmp/webhook-before snapshot

# 在这里执行真实业务操作，并记录其企业 ID 和本次数据 ID。
python3 openapi/event_subscription/regression.py --output /tmp/webhook-after verify \
  --event customer.batch_update --organization-id 123 --ids 456 457 \
  --baseline /tmp/webhook-before/receipts.json --wait 60
```

匹配要求同时满足事件名、企业 ID、实体 ID。批量与导入支持 `data.ids`、`created_ids`、`updated_ids`，会排除基线中的旧回调。批量场景还应人工对照完整 ID 集合、数量及分片信息；找到其中一个目标 ID 不能证明整批都已推送。无匹配退出码为 1，不会把业务接口成功当作回调成功。

Webhook.site 可能在 50 条后耗尽免费额度。清空收件列表不一定重置额度；出现 HTTP 429 需更换接收地址并重新保存订阅。先归档现有回调，重新用业务操作验证，不能把接收器限流造成的漏收直接报为产品缺陷。

## 移动端网关陌拜与签到删除

确保已订阅 `checkin.cold_visit_create` 和 `checkin.delete`，执行：

```bash
python3 openapi/event_subscription/regression.py --output /tmp/webhook-checkin mobile-checkin --wait 30
```

走 `https://lxcrm-api-staging.weiwenjia.com/api/v3/checkin`，请求头为 `device=lxcrm_duli, version_code=4.0.1`，新增陌拜传 `checkPattern.status=陌拜`。只删除本次新建签到，并查询确认删除后再核对回调。企业若设置了额外必填字段，需按当前企业字段补齐请求。异常中断后通过 `created-checkin.json` 和请求日志核对是否有未清理数据。

这是脚本调用移动端接口，不是自动点击手机 App。此前直连 `staging-pc-checkin.ikcrm.com` 的简化请求未收到事件，改为用户抓取的网关参数后新增、删除均通过；不能将两条路径的结果混用。

## 已有业务和导入脚本

- `../../flow/crm_flow.py`、`../../flow/mobile_crm_flow.py`：客户、线索、合同、回款等业务操作。
- `../../import/error-report-import/error_report_import_tester.py`：模板下载、校验、导入、异步任务与导入历史。

使用这些脚本时核对它们各自的环境参数和默认值，显式指定 staging。关联字段使用本次自建数据，操作完清理。普通用户转移数据后可能失去删除权限，转移测试需要事先安排同企业的清理权限。

本次另有待处理差异：回款计划自动收满有 `received_payment_plan.finish`，手动 `batch_done` 后状态为 done 但未见回调；跟进提醒有同一时间多条不同 `event_id`，需核对重复通知规则。这些是回归观察，不是脚本对后续版本的固定断言。

## 本地验证

```bash
python3 -m unittest discover -s openapi/event_subscription -p 'test_*.py'
```

离线测试不发业务请求。同步代码时不需要重跑在线回归。
