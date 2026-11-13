# STORY 22730 PC 标签管理接口回归

这是测试环境的在线集成测试，不是单元测试。固定访问 `https://lxcrm-api-test.weiwenjia.com/api/pc`，不支持切换到生产环境。使用 Python 3 和 `requests`。

## 执行

先通过环境变量 `CRM_LABEL_TOKEN` 注入已授权测试企业的 Token。脚本和结果不记录 Authorization 请求头。

```bash
python3 label_management/pc_api_regression.py
```

默认执行 67 个独立场景。也可按类或单条用例执行：

```bash
python3 label_management/pc_api_regression.py PCLabelTests
python3 label_management/pc_api_regression.py PCBatchTests
python3 label_management/pc_api_regression.py PCLeadTests
python3 label_management/pc_api_regression.py PCLeadTests.test_lead_create_multi_labels_readback
```

线索测试沿用用户提供的测试企业必填字段及负责人/部门 ID，使用合成名称，不关联现有业务记录。换租户前需要更新这些字段；本脚本不读取仓库现有配置里的凭证。

## 数据与证据

- 每个场景创建自己的分组、标签、线索，转换场景还创建客户；仅删除本次创建的数据。不会执行用户 cURL 示例里的历史标签 ID。
- 每次请求写入 `results/<时间>/evidence.json`，记录请求体、HTTP 状态、业务码及响应。`remaining_*_ids` 是清理台账；中断后应先核对该台账。
- 每条场景有精确回读断言；错误码校验不将业务码 `500` 当正常拒绝。删除线索接口允许成功响应省略 `data`。
- `summary.json` 记录场景统计、清理剩余 ID、前后配置快照是否一致。共享测试环境中，其他人同时修改配置会影响该比较；不要强制恢复别人的修改。
- 清理最多尝试 3 次删除分组，间隔 1 秒。测试本身不通过反复重跑来掩盖失败。
- 当前额度边界场景会临时填满接口报告的标签总额度，然后清理测试标签。不要与其他人的标签新增测试同时执行。

## 覆盖与限制

覆盖标签管理、10 个模块的选项可见性、批量增删/换分组、当前配置额度边界、PC 线索标签创建/编辑/清空/回读及适用范围保护。

补充覆盖客户分组扩展到全部 10 个模块、同一标签 ID/内容及颜色回读，以及更新范围时未知模块不落库。当前混入未知模块的更新请求会过滤未知项并保存合法模块；需求尚未明确必须拒绝整次更新，因此按白名单约束判定。

单个标签编辑补充覆盖同时改名与换分组、30/31 字边界、空名称拒绝；单个删除回读管理列表及适用模块选项，核对其他标签保留。

线索转客户 GET 预填接口使用测试企业模板 1172，验证共用多选标签保留、线索专属标签过滤、共用单选标签保留、空标签不新增，以及源线索标签和未转化状态保持。此接口不提交客户创建，不能据此判定转换落库链路通过。

完整转换场景另外提交 `POST /customers`，使用预填接口返回的标签值，验证客户详情标签 ID、内容、分组以及源线索的转化状态、目标客户 ID、原标签保留。覆盖共用多选及线索专属混合、共用单选、空标签三类。客户必填字段取自用户提供的测试企业成功请求，不创建附带联系人或商机。清理顺序为测试客户、线索、标签及分组；`remaining_customer_ids` 也写入台账。

线索批量标签更新使用 `PUT /batch_resources/batch_update` 和本企业标签字段 ID 9673146。`operation_selection=append` 验证多选追加保留原标签、空标签线索可追加、未选线索不变、重复请求不重复关联、同组单选替换且其他组保留，以及不适用模块标签不得保存。

`operation_selection=replace` 对应“清空已有标签并新增”。验证所选线索所有原分组标签清空后仅保存新集合，空标签线索新增，未选线索保持；新集合可混合单选与多选组，重复提交不出现重复值；混入不适用模块标签时不得落库。空替换集合及同单选组提交多个新值尚未验证。

`operation_selection=remove_one_match` 对应“删除指定标签（有一个就可删除）”。验证多选全部命中、部分命中时仅删除命中的关联，未命中及未选线索保持；单选指定值移除后，同组其他记录的其他单选值及跨组标签保留；重复删除结果稳定。另验证联系人专属标签输入不能误删线索原标签，批量操作不会删除标签定义。

`operation_selection=remove_full_match` 对应“删除完全匹配的标签（选择的标签在线索中都有才删除）”。按每条线索判断所有指定标签是否存在：完整命中才移除指定关联，额外标签保留；部分命中、未命中、空标签及未选线索保持。另覆盖跨单选/多选组的完整组合、单标签条件、重复提交、不适用模块输入及标签定义保留。

单选多值与跨模块输入按业务约束判定：单选不保存多个值，不适用标签不保存。当前实现选择保留最后一个单选值、过滤不适用标签；是否必须向用户提示仍需确认。

本脚本不代表 PC 页面交互通过。其余业务模块记录保存、客户存量记录兼容、字段映射、导入/导出、AI、权限矩阵和 APP 尚需对应接口或页面操作继续验证。单次 200 条与高级版 500 条边界需要足够额度及正确灰测配置。

## 线索标签导入补测

使用相同的 `CRM_LABEL_TOKEN`，单独执行 `python3 label_management/pc_import_labels.py`。此脚本不包含在上述 67 个场景中，也不读取或重放用户示例附件。运行依赖本机 Codex bundled Node.js、`@oai/artifact-tool` 和 Python `requests`、`openpyxl`（只读检查）。

创建 3 个临时分组、5 个标签，下载当前线索模板；核对 `Sheet标签` 与适用于 Lead 的标签内容一致。先导入 1 行冒烟，再导入 10 行正常/异常混合文件，共 12 个检查点。混合文件覆盖中英文逗号、多选、单选、跨组、空标签、不存在标签、不适用模块、单选多值、合法/非法混合及错误分隔符。行级检查共享同一导入任务，不计为独立隔离场景。

通过 OSS 附件上传后，调用用户提供的 `entity_loaders/upload` 和 `entity_loaders/import`；等待匹配本次任务的校验事件，按附件 ID 查询导入历史，回读线索完整标签并核对错误报告。只清理唯一合成名称对应的线索及本轮分组、标签；上传附件与导入历史保留为证据。结果写入独立运行目录的 `import-summary.json`，不混入主脚本的 `latest_results.json`。

模板数据值由 Artifact Tool 写入，再将数据行合回原模板包以保留样式、下拉校验和系统模板元数据。模板列名、70 列布局及路径依赖当前测试企业，不适合直接跨租户运行。当前脚本仅检查最近最多 500 条线索；并发大量新增或异步超时后需核对本轮唯一名称与导入历史再清理，不能直接重放导入。

尚未接入 CI。可在提供隔离测试租户、环境变量凭证后运行以上命令；不要将 Token 写入 CI 配置。


## 本轮补充测试代码（2026-11-13）

- PC 模块保存及批量编辑：`pc_module_regression.py`；字段映射：`pc_module_mappings.py`、`pc_mapping_shared_groups.py`。
- PC 模块导入：`pc_module_imports.py`；导入工作簿数据写入：`import_workbook.mjs`。
- APP 线索新增、编辑及转客户：`mobile_lead_create.py`、`mobile_lead_edit_conversion.py`；其余模块：`mobile_module_regression.py`。
- PC/APP 标签筛选：`label_filter_regression.py`。
- 页面测试夹具：`pc_label_ui_fixture.py`、`mobile_label_ui_fixture.py`、`mobile_mapping_ui_fixture.py`。
- Android 报价单页面操作辅助：`appium_webview.py`、`mobile_quotation_ui.py`，用于新增、编辑、移除/清空标签、复制、生成合同映射的页面核对。

页面辅助通过 Appium UiAutomator2 + ChromeDriver 操作真实 APP WebView。复用已连接的会话：设置 `APPIUM_SESSION_FILE` 为 Appium 创建会话返回的 JSON 文件路径（包含 `sessionId`），可选 `APPIUM_SERVER_URL`，默认 `http://127.0.0.1:14723`；授权凭证仍通过 `CRM_LABEL_TOKEN` 提供。使用本轮切换后的企业凭证，不可重放旧企业的 Token。不要将会话或凭证文件提交到 Git。

`mobile_quotation_ui.py` 是本次交互测试使用的辅助函数集合，不是可直接无人值守运行的完整脚本。`text`/`fill`/`picker`/`toggle` 操作页面，`snap`/`network` 记录证据，`register`/`record` 核对保存结果。`picker` 使用当前测试标签前缀；调用前应准备当前企业的标签与 `fixture.json` 台账，并确认模板启用标签字段。复制保留原报价单有效标签；生成合同时仅映射报价单与合同共用分组的标签。

只同步测试代码；`data/` 中的企业字段快照、导入文件，以及 `results/` 中的响应、截图、会话、台账和报告保留本地。部分模块脚本依赖这些运行快照或上一轮台账，首次运行应先采集当前企业配置并核对脚本中的模板/字段 ID。不可将历史台账当作其他企业的可执行测试数据。
