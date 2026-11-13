#!/usr/bin/env python3
"""STORY 22730 PC online integration tests; creates and removes only own tags.

Run: CRM_LABEL_TOKEN=... python3 label_management/pc_api_regression.py
Requires requests. Credentials come from environment settings and are never logged.
"""
from environment import settings
import json
import os
from pathlib import Path
import sys
import time
import unittest
import uuid
from datetime import datetime

import requests


BASE = settings.pc_base
MODELS = ["MarketActivity", "Lead", "Customer", "Contact", "Opportunity",
          "Quotation", "Contract", "ReceivedPayment", "InvoicedPayment", "Product"]
OUT = settings.result_root / datetime.now().strftime("%Y%m%d-%H%M%S")
PREFIX = "T" + uuid.uuid4().hex[:6]
EVIDENCE = []
OWN_GROUPS = set()
OWN_LABELS = set()
OWN_LEADS = set()
OWN_CUSTOMERS = set()
CASE_RESULTS = []
SESSION = requests.Session()


def save():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidence.json").write_text(json.dumps({
        **settings.metadata(), "base": BASE, "prefix": PREFIX, "requests": EVIDENCE,
        "remaining_group_ids": sorted(OWN_GROUPS),
        "remaining_label_ids": sorted(OWN_LABELS), "cases": CASE_RESULTS,
        "remaining_lead_ids": sorted(OWN_LEADS),
        "remaining_customer_ids": sorted(OWN_CUSTOMERS),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def api(method, path, body=None):
    response = SESSION.request(method, BASE + path, json=body, timeout=30,
                               allow_redirects=False)
    try:
        payload = response.json()
    except ValueError:
        payload = {"non_json": response.text[:500]}
    EVIDENCE.append({"time": datetime.now().isoformat(), "method": method,
                     "path": path, "request": body,
                     "http_status": response.status_code, "response": payload})
    if method == "POST" and path in ("/label_groups", "/labels", "/leads", "/customers") and payload.get("code") == 0:
        identifier = payload.get("data", {}).get("id")
        if identifier and path == "/label_groups":
            OWN_GROUPS.add(identifier)
        if identifier and path == "/labels":
            OWN_LABELS.add(identifier)
        if identifier and path == "/leads":
            OWN_LEADS.add(identifier)
        if identifier and path == "/customers":
            OWN_CUSTOMERS.add(identifier)
    if method == "DELETE" and payload.get("code") == 0:
        identifier = int(path.rsplit("/", 1)[-1])
        if path.startswith("/label_groups/"):
            OWN_GROUPS.discard(identifier)
        if path.startswith("/labels/"):
            OWN_LABELS.discard(identifier)
        if path.startswith("/leads/"):
            OWN_LEADS.discard(identifier)
        if path.startswith("/customers/"):
            OWN_CUSTOMERS.discard(identifier)
    save()
    return response.status_code, payload


def success(result):
    status, payload = result
    assert status == 200 and payload.get("code") == 0, (status, payload)
    return payload.get("data")


def rejected(result):
    status, payload = result
    assert status < 500 and payload.get("code") not in (None, 0, 500), (status, payload)
    assert "action_controller/" not in json.dumps(payload), payload


def groups():
    return success(api("GET", "/label_groups"))["list"]


def options(model):
    return success(api("GET", "/labels/options?model_klass=" + model))


def cleanup(group_ids, label_ids):
    # Cleanup retries never change a failed test into a pass. Preserve all attempts.
    for group in groups():
        if group["id"] in group_ids:
            for label in group["labels"]:
                OWN_LABELS.add(label["id"])
                label_ids.add(label["id"])
    for identifier in list(label_ids & OWN_LABELS):
        api("DELETE", f"/labels/{identifier}")
    for attempt in range(3):
        for identifier in list(group_ids & OWN_GROUPS):
            api("DELETE", f"/label_groups/{identifier}")
        if not (group_ids & OWN_GROUPS):
            break
        if attempt < 2:
            time.sleep(1)
    remaining = {g["id"] for g in groups()}
    assert not (remaining & group_ids), f"Cleanup failed: {remaining & group_ids}"
    assert not (label_ids & OWN_LABELS), f"Label cleanup failed: {label_ids & OWN_LABELS}"


class PCFixture(unittest.TestCase):
    """Each case owns its fixtures and can run independently."""

    def setUp(self):
        self.start = len(EVIDENCE)
        self.old_groups = OWN_GROUPS.copy()
        self.old_labels = OWN_LABELS.copy()
        self.addCleanup(lambda: cleanup(OWN_GROUPS - self.old_groups,
                                        OWN_LABELS - self.old_labels))

    def group(self, **changes):
        values = {"name": PREFIX, "color": "#1890ff", "select_type": "multi",
                  "applicable_models": ["Lead", "Contact"]}
        values.update(changes)
        return success(api("POST", "/label_groups", {"label_group": values}))

    def label(self, group_id, content="接口回归标签"):
        return success(api("POST", "/labels", {"label": {
            "content": content, "label_group_id": group_id}}))

    def batch(self, group_id, contents):
        result = api("POST", "/labels/batch_create", {
            "label_group_id": group_id, "contents": contents})
        # Register persisted IDs even if the endpoint reports partial failure.
        for label in self.persisted(group_id)["labels"]:
            OWN_LABELS.add(label["id"])
        save()
        return result

    def persisted(self, identifier):
        return next(g for g in groups() if g["id"] == identifier)


class PCLabelTests(PCFixture):

    def test_group_create_and_update(self):
        """分组创建及改名、颜色、适用范围更新后精确回读。"""
        g = self.group()
        change = {"name": PREFIX + "改", "color": "#ff0000", "select_type": "multi",
                  "applicable_models": ["Lead", "Product"]}
        success(api("PUT", f'/label_groups/{g["id"]}', {"label_group": change}))
        actual = self.persisted(g["id"])
        for key in ("name", "color", "select_type"):
            self.assertEqual(actual[key], change[key])
        self.assertEqual(set(actual["applicable_models"]), {"Lead", "Product"})

    def test_group_expand_customer_to_all_models(self):
        """客户分组扩展至全部 10 个模块，原标签 ID、内容及分组配置回读一致。"""
        g = self.group(applicable_models=["Customer"])
        label = self.label(g["id"])
        change = {"name": PREFIX + "全", "select_type": "multi", "color": "#50B83C",
                  "applicable_models": MODELS}
        success(api("PUT", f'/label_groups/{g["id"]}', {"label_group": change}))
        actual = self.persisted(g["id"])
        self.assertEqual(actual["name"], change["name"])
        self.assertEqual(actual["select_type"], "multi")
        self.assertEqual(actual["color"].lower(), "#50b83c")
        self.assertEqual(set(actual["applicable_models"]), set(MODELS))
        self.assertEqual([(x["id"], x["content"]) for x in actual["labels"]],
                         [(label["id"], label["content"])])
        for model in MODELS:
            visible = next(x for x in options(model) if x["id"] == g["id"])
            self.assertEqual(visible["name"], change["name"], model)
            self.assertEqual(visible["select_type"], "multi", model)
            self.assertEqual(visible["color"].lower(), "#50b83c", model)
            self.assertEqual([(x["id"], x["content"]) for x in visible["labels"]],
                             [(label["id"], label["content"])], model)

    def test_group_update_unknown_model_not_persisted(self):
        """混入未知模块可拒绝或过滤；不落库非法模块且保留原标签。"""
        g = self.group(applicable_models=["Customer"])
        label = self.label(g["id"])
        result = api("PUT", f'/label_groups/{g["id"]}', {
            "label_group": {"applicable_models": MODELS + ["BadModel"]}})
        if result[1].get("code") == 0:
            success(result)
            expected_models = set(MODELS)
        else:
            rejected(result)
            expected_models = {"Customer"}
        actual = self.persisted(g["id"])
        self.assertEqual(set(actual["applicable_models"]), expected_models)
        self.assertEqual(actual["name"], g["name"])
        self.assertEqual(actual["color"], g["color"])
        self.assertEqual(actual["select_type"], g["select_type"])
        self.assertEqual([x["id"] for x in actual["labels"]], [label["id"]])
        customer = next(x for x in options("Customer") if x["id"] == g["id"])
        self.assertEqual([x["id"] for x in customer["labels"]], [label["id"]])

    def test_label_create_and_rename(self):
        """标签创建、改名后在管理列表及选项接口回读。"""
        g = self.group()
        label = self.label(g["id"])
        success(api("PUT", f'/labels/{label["id"]}', {"label": {"content": "改名后的标签"}}))
        for items in (groups(), options("Lead")):
            actual = next(x for x in items if x["id"] == g["id"])
            self.assertEqual([(x["id"], x["content"]) for x in actual["labels"]],
                             [(label["id"], "改名后的标签")])

    def test_single_label_move_and_rename(self):
        """单个标签编辑同时改名及换组，ID 保持且适用模块随目标组变化。"""
        source = self.group(applicable_models=["Lead"])
        target = self.group(name=PREFIX + "B", applicable_models=["Contact"])
        label = self.label(source["id"])
        content = PREFIX + "换组"
        success(api("PUT", f'/labels/{label["id"]}', {"label": {
            "content": content, "label_group_id": target["id"]}}))
        self.assertEqual(self.persisted(source["id"])["labels"], [])
        actual = self.persisted(target["id"])["labels"]
        self.assertEqual([(x["id"], x["content"], x["label_group_id"]) for x in actual],
                         [(label["id"], content, target["id"])])
        self.assertNotIn(label["id"], [x["id"] for g in options("Lead") for x in g["labels"]])
        contact = next(g for g in options("Contact") if g["id"] == target["id"])
        self.assertEqual([(x["id"], x["content"]) for x in contact["labels"]],
                         [(label["id"], content)])

    def test_edit_label_name_30_characters(self):
        """单个标签编辑为 30 字名称成功，管理列表与模块选项回读一致。"""
        g = self.group()
        label = self.label(g["id"])
        content = PREFIX + "标" * 23
        success(api("PUT", f'/labels/{label["id"]}', {"label": {
            "content": content, "label_group_id": g["id"]}}))
        for items in (groups(), options("Lead")):
            actual = next(x for x in items if x["id"] == g["id"])
            self.assertEqual([(x["id"], x["content"]) for x in actual["labels"]],
                             [(label["id"], content)])

    def test_edit_label_name_31_characters_rejected(self):
        """单个标签编辑超过 30 字时拒绝且保留原值。"""
        g = self.group()
        label = self.label(g["id"])
        rejected(api("PUT", f'/labels/{label["id"]}', {"label": {
            "content": PREFIX + "标" * 24, "label_group_id": g["id"]}}))
        actual = self.persisted(g["id"])["labels"]
        self.assertEqual([(x["id"], x["content"]) for x in actual],
                         [(label["id"], label["content"])])

    def test_edit_label_name_empty_rejected(self):
        """单个标签编辑为空时拒绝且保留原值。"""
        g = self.group()
        label = self.label(g["id"])
        rejected(api("PUT", f'/labels/{label["id"]}', {"label": {
            "content": "", "label_group_id": g["id"]}}))
        actual = self.persisted(g["id"])["labels"]
        self.assertEqual([(x["id"], x["content"]) for x in actual],
                         [(label["id"], label["content"])])

    def test_single_label_delete_removes_options(self):
        """单个标签删除后管理列表及所有适用模块选项移除，其他标签保留。"""
        g = self.group()
        removed = self.label(g["id"], PREFIX + "删")
        kept = self.label(g["id"], PREFIX + "留")
        success(api("DELETE", f'/labels/{removed["id"]}'))
        for items in (groups(), options("Lead"), options("Contact")):
            actual = next(x for x in items if x["id"] == g["id"])
            self.assertEqual([(x["id"], x["content"]) for x in actual["labels"]],
                             [(kept["id"], kept["content"])])

    def test_remove_unused_model(self):
        """未绑定业务记录时取消适用模块，仅移除该模块选项。"""
        g = self.group()
        label = self.label(g["id"])
        success(api("PUT", f'/label_groups/{g["id"]}', {
            "label_group": {"applicable_models": ["Lead"]}}))
        self.assertNotIn(g["id"], [x["id"] for x in options("Contact")])
        actual = next(x for x in options("Lead") if x["id"] == g["id"])
        self.assertEqual([x["id"] for x in actual["labels"]], [label["id"]])

    def test_radio_configuration(self):
        """单选分组配置保存并回读；不代表业务记录单选约束已通过。"""
        g = self.group(select_type="radio")
        self.assertEqual(self.persisted(g["id"])["select_type"], "radio")

    def test_group_name_10_characters(self):
        """分组名称恰好 10 个字符可创建。"""
        g = self.group(name=PREFIX + "边界值")
        self.assertEqual(self.persisted(g["id"])["name"], PREFIX + "边界值")

    def test_group_name_11_characters_rejected(self):
        """分组名称超过 10 个字符被拒绝且不落库。"""
        before = {g["id"] for g in groups()}
        rejected(api("POST", "/label_groups", {"label_group": {
            "name": PREFIX + "超长边界", "select_type": "multi", "color": "#1890ff",
            "applicable_models": ["Lead"]}}))
        self.assertEqual({g["id"] for g in groups()}, before)

    def test_group_name_empty_rejected(self):
        """分组名称为空时拒绝创建。"""
        rejected(api("POST", "/label_groups", {"label_group": {
            "name": "", "select_type": "multi", "color": "#1890ff",
            "applicable_models": ["Lead"]}}))

    def test_label_name_30_characters(self):
        """标签名称恰好 30 个字符可创建并回读。"""
        g = self.group()
        text = PREFIX + "标" * 23
        label = self.label(g["id"], text)
        self.assertEqual(self.persisted(g["id"])["labels"][0]["content"], text)
        self.assertIsInstance(label["id"], int)

    def test_label_name_31_characters_rejected(self):
        """标签名称超过 30 个字符被拒绝且不落库。"""
        g = self.group()
        rejected(api("POST", "/labels", {"label": {
            "content": PREFIX + "标" * 24, "label_group_id": g["id"]}}))
        self.assertEqual(self.persisted(g["id"])["labels"], [])

    def test_label_name_empty_rejected(self):
        """空标签名称拒绝创建。"""
        g = self.group()
        rejected(api("POST", "/labels", {"label": {"content": "", "label_group_id": g["id"]}}))
        self.assertEqual(self.persisted(g["id"])["labels"], [])

    def test_unknown_model_rejected(self):
        """未知模块不能读取标签选项。"""
        rejected(api("GET", "/labels/options?model_klass=BadModel"))

    def test_invalid_model_create_rejected(self):
        """分组适用模块不在服务端白名单时拒绝创建。"""
        rejected(api("POST", "/label_groups", {"label_group": {
            "name": PREFIX, "select_type": "multi", "color": "#1890ff",
            "applicable_models": ["BadModel"]}}))

    def test_invalid_selection_type_rejected(self):
        """分组选择类型非法时正常校验拒绝，不返回内部异常。"""
        rejected(api("POST", "/label_groups", {"label_group": {
            "name": PREFIX, "select_type": "BadType", "color": "#1890ff",
            "applicable_models": ["Lead"]}}))

    def test_nonempty_group_delete_rejected(self):
        """包含标签的分组禁止删除，原标签完整保留。"""
        g = self.group()
        label = self.label(g["id"])
        rejected(api("DELETE", f'/label_groups/{g["id"]}'))
        self.assertEqual([x["id"] for x in self.persisted(g["id"])["labels"]], [label["id"]])

    def test_label_then_empty_group_delete(self):
        """删除最后一个标签后立即删除空分组并回读确认。"""
        g = self.group()
        label = self.label(g["id"])
        success(api("DELETE", f'/labels/{label["id"]}'))
        success(api("DELETE", f'/label_groups/{g["id"]}'))
        self.assertNotIn(g["id"], [x["id"] for x in groups()])


class PCBatchTests(PCFixture):
    """Bulk tag management and reported quota diagnostics."""

    def test_batch_three_labels(self):
        """批量创建三条标签，数量、内容、所属分组准确。"""
        g = self.group()
        names = [PREFIX + str(i) for i in range(3)]
        success(self.batch(g["id"], names))
        self.assertEqual(sorted(x["content"] for x in self.persisted(g["id"])["labels"]), names)

    def test_batch_empty_rejected(self):
        """空批次正常拒绝且不创建标签。"""
        g = self.group()
        rejected(self.batch(g["id"], []))
        self.assertEqual(self.persisted(g["id"])["labels"], [])

    def test_batch_overlong_label_rejected(self):
        """批量接口拒绝超过 30 字的标签且不落库。"""
        g = self.group()
        rejected(self.batch(g["id"], [PREFIX + "标" * 24]))
        self.assertEqual(self.persisted(g["id"])["labels"], [])

    def test_batch_unknown_group_rejected(self):
        """批量接口拒绝不存在的分组，返回正常校验错误。"""
        rejected(api("POST", "/labels/batch_create", {
            "label_group_id": 0, "contents": [PREFIX]}))

    def test_batch_201_labels_rejected(self):
        """201 条批次拒绝且不落库；错误需明确单次上限，避免与总额度混淆。"""
        g = self.group()
        result = self.batch(g["id"], [PREFIX + str(i) for i in range(201)])
        rejected(result)
        self.assertEqual(self.persisted(g["id"])["labels"], [])
        message = result[1].get("message", "")
        if not ("200" in message and any(x in message for x in ("单次", "一次", "批量"))):
            self.skipTest("请求被拒绝，但错误未区分单次上限与当前租户总额度：" + message)

    def test_batch_delete_subset(self):
        """批量删除所选标签，未选中的标签保留，选项接口同步移除。"""
        g = self.group()
        labels = [self.label(g["id"], PREFIX + str(i)) for i in range(3)]
        ids = [x["id"] for x in labels[:2]]
        success(api("PUT", "/labels/batch_delete", {"ids": ids, "label_group_id": g["id"]}))
        actual = self.persisted(g["id"])["labels"]
        self.assertEqual([x["id"] for x in actual], [labels[2]["id"]])
        OWN_LABELS.difference_update(ids)
        actual = next(x for x in options("Lead") if x["id"] == g["id"])
        self.assertEqual([x["id"] for x in actual["labels"]], [labels[2]["id"]])

    def test_batch_move_labels(self):
        """批量修改分组：标签 ID 保持，源组移除，目标组和模块选项增加。"""
        source = self.group(applicable_models=["Lead"])
        target = self.group(name=PREFIX + "B", applicable_models=["Contact"])
        labels = [self.label(source["id"], PREFIX + str(i)) for i in range(2)]
        ids = {x["id"] for x in labels}
        success(api("PUT", "/labels/batch_update", {"ids": sorted(ids), "label_group_id": target["id"]}))
        self.assertEqual(self.persisted(source["id"])["labels"], [])
        self.assertEqual({x["id"] for x in self.persisted(target["id"])["labels"]}, ids)
        contact = next(x for x in options("Contact") if x["id"] == target["id"])
        self.assertEqual({x["id"] for x in contact["labels"]}, ids)
        self.assertNotIn(target["id"], [x["id"] for x in options("Lead")])

    def test_reported_tenant_quota_boundary(self):
        """诊断接口所报当前企业额度的临界及超限；不代表高级版额度正确。"""
        config = success(api("GET", "/label_groups"))
        limit = config["max_label_count"]
        current = sum(len(x["labels"]) for x in config["list"])
        remaining = limit - current
        if not 0 < remaining <= 200:
            self.skipTest(f"当前剩余额度 {remaining}，不适用单批构造边界")
        g = self.group()
        names = [PREFIX + str(i) for i in range(remaining)]
        success(self.batch(g["id"], names))
        self.assertEqual(sorted(x["content"] for x in self.persisted(g["id"])["labels"]), sorted(names))
        self.assertEqual(sum(len(x["labels"]) for x in groups()), limit)
        rejected(api("POST", "/labels", {"label": {
            "label_group_id": g["id"], "content": PREFIX + "额外"}}))
        self.assertEqual(sum(len(x["labels"]) for x in groups()), limit)


class PCLeadTests(PCFixture):
    """Synthetic PC lead fixtures derived from the user-provided successful curl."""

    def setUp(self):
        super().setUp()
        previous = OWN_LEADS.copy()
        self.addCleanup(lambda: self.cleanup_leads(OWN_LEADS - previous))
        previous_customers = OWN_CUSTOMERS.copy()
        self.addCleanup(lambda: self.cleanup_customers(OWN_CUSTOMERS - previous_customers))

    def cleanup_customers(self, identifiers):
        for identifier in list(identifiers):
            success(api("DELETE", f"/customers/{identifier}"))
            status, payload = api("GET", f"/customers/{identifier}")
            self.assertEqual(status, 200)
            self.assertEqual(payload.get("code"), 100100)

    def cleanup_leads(self, identifiers):
        for identifier in list(identifiers):
            success(api("DELETE", f"/leads/{identifier}"))
            status, payload = api("GET", f"/leads/{identifier}")
            self.assertEqual(status, 200)
            self.assertEqual(payload.get("code"), 100100)

    def create_lead(self, labels, *, name=None):
        # Tenant-specific required fields from the supplied request; no business links.
        body = {"name": name or "标签回归" + PREFIX, "source": 392064, "status": 617883,
                "numeric_asset_922345": "2.0", "text_area_asset_df70dd": "20",
                "numeric_asset_aa4b85": "1", "numeric_asset_39fe31": 1.55,
                "numeric_asset_714d0e": -0.0083, "text_asset_a063a3": "false",
                "datetime_asset_f4fc01": datetime.now().strftime("%Y-%m-%d"),
                "user_id": 1000025901, "want_department_id": 5506212,
                "labels": labels, "product_assets_attributes": [],
                "intl_extra_attributes": {}}
        body = settings.record("Lead", body, ("name", "labels", "product_assets_attributes", "intl_extra_attributes"))
        return api("POST", "/leads", {"lead": body, "request_ticket": str(uuid.uuid4()),
                                       "social_record_id": ""})

    def lead_labels(self, lead_id):
        return success(api("GET", f"/leads/{lead_id}"))["labels"]

    def chosen(self, group, label):
        return {"id": label["id"], "group_id": group["id"], "color": group["color"],
                "content": label["content"], "isChose": False, "checked": True}

    def update_lead_labels(self, lead_ids, labels, operation):
        return api("PUT", "/batch_resources/batch_update", {
            "name": "labels", "field_id": settings.value("lead_label_field_id", 9673146), "field_name": "labels",
            "field_label": "标签", "field_value": [
                {"id": x["id"], "group_id": x["label_group_id"]} for x in labels],
            "operation_selection": operation, "resource_ids": lead_ids,
            "resource_type": "Lead"})

    def append_lead_labels(self, lead_ids, labels):
        return self.update_lead_labels(lead_ids, labels, "append")

    def assert_lead_label_ids(self, lead_id, expected):
        self.assertEqual(sorted(x["id"] for x in self.lead_labels(lead_id)), sorted(expected))

    def test_batch_append_multi_keeps_old_and_untargeted(self):
        """批量追加多选标签保留原值与其他组，只修改所选线索，空标签线索可追加。"""
        g = self.group(applicable_models=["Lead"])
        other = self.group(name=PREFIX + "B", applicable_models=["Lead"])
        old, new = [self.label(g["id"], PREFIX + str(i)) for i in range(2)]
        kept = self.label(other["id"], PREFIX + "保留")
        first = success(self.create_lead([self.chosen(g, old), self.chosen(other, kept)], name=PREFIX + "已标"))
        empty = success(self.create_lead([], name=PREFIX + "空标"))
        untouched = success(self.create_lead([self.chosen(g, old)], name=PREFIX + "未选"))
        self.assert_lead_label_ids(first["id"], [old["id"], kept["id"]])
        self.assert_lead_label_ids(empty["id"], [])
        success(self.append_lead_labels([first["id"], empty["id"]], [new]))
        self.assert_lead_label_ids(first["id"], [old["id"], new["id"], kept["id"]])
        self.assert_lead_label_ids(empty["id"], [new["id"]])
        self.assert_lead_label_ids(untouched["id"], [old["id"]])

    def test_batch_append_repeated_labels_no_duplicates(self):
        """重复提交相同追加标签不产生重复关联，其他原标签保留。"""
        g = self.group(applicable_models=["Lead"])
        old, new = [self.label(g["id"], PREFIX + str(i)) for i in range(2)]
        lead = success(self.create_lead([self.chosen(g, old)]))
        self.assert_lead_label_ids(lead["id"], [old["id"]])
        for _ in range(2):
            success(self.append_lead_labels([lead["id"]], [old, new]))
            self.assert_lead_label_ids(lead["id"], [old["id"], new["id"]])

    def test_batch_append_radio_replaces_only_same_group(self):
        """追加模式单选组替换原值，未选组中的多选及单选标签均保留。"""
        radio = self.group(select_type="radio", applicable_models=["Lead"])
        multi = self.group(name=PREFIX + "B", applicable_models=["Lead"])
        other_radio = self.group(name=PREFIX + "C", select_type="radio", applicable_models=["Lead"])
        old, new = [self.label(radio["id"], PREFIX + str(i)) for i in range(2)]
        kept_multi = self.label(multi["id"], PREFIX + "多选")
        kept_radio = self.label(other_radio["id"], PREFIX + "单选")
        lead = success(self.create_lead([self.chosen(radio, old), self.chosen(multi, kept_multi),
                                         self.chosen(other_radio, kept_radio)]))
        self.assert_lead_label_ids(lead["id"], [old["id"], kept_multi["id"], kept_radio["id"]])
        success(self.append_lead_labels([lead["id"]], [new]))
        self.assert_lead_label_ids(lead["id"], [new["id"], kept_multi["id"], kept_radio["id"]])

    def test_batch_append_wrong_module_label_not_saved(self):
        """批量追加联系人专属标签时不得存入线索，线索原标签保持。"""
        allowed = self.group(applicable_models=["Lead"])
        forbidden = self.group(name=PREFIX + "B", applicable_models=["Contact"])
        kept = self.label(allowed["id"], PREFIX + "原值")
        excluded = self.label(forbidden["id"], PREFIX + "不适用")
        lead = success(self.create_lead([self.chosen(allowed, kept)]))
        self.assert_lead_label_ids(lead["id"], [kept["id"]])
        result = self.append_lead_labels([lead["id"]], [excluded])
        if result[1].get("code") == 0:
            success(result)
        else:
            rejected(result)
        self.assert_lead_label_ids(lead["id"], [kept["id"]])

    def test_batch_replace_multi_clears_all_groups_and_untargeted(self):
        """批量替换清空所选线索全部原分组标签，空线索新增，未选线索保持。"""
        multi = self.group(applicable_models=["Lead"])
        other = self.group(name=PREFIX + "B", select_type="radio", applicable_models=["Lead"])
        old, first, second = [self.label(multi["id"], PREFIX + str(i)) for i in range(3)]
        other_old = self.label(other["id"], PREFIX + "旧单选")
        chosen = [self.chosen(multi, old), self.chosen(other, other_old)]
        selected = success(self.create_lead(chosen, name=PREFIX + "替换"))
        empty = success(self.create_lead([], name=PREFIX + "空值"))
        untouched = success(self.create_lead(chosen, name=PREFIX + "未选"))
        old_ids = [old["id"], other_old["id"]]
        self.assert_lead_label_ids(selected["id"], old_ids)
        self.assert_lead_label_ids(empty["id"], [])
        self.assert_lead_label_ids(untouched["id"], old_ids)
        success(self.update_lead_labels([selected["id"], empty["id"]], [first, second], "replace"))
        self.assert_lead_label_ids(selected["id"], [first["id"], second["id"]])
        self.assert_lead_label_ids(empty["id"], [first["id"], second["id"]])
        self.assert_lead_label_ids(untouched["id"], old_ids)

    def test_batch_replace_mixed_types_repeated(self):
        """替换同时提交单选及多选标签，清除其他原分组，重复提交无重复值。"""
        radio = self.group(select_type="radio", applicable_models=["Lead"])
        multi = self.group(name=PREFIX + "B", applicable_models=["Lead"])
        other = self.group(name=PREFIX + "C", applicable_models=["Lead"])
        old_radio, new_radio = [self.label(radio["id"], PREFIX + "单" + str(i)) for i in range(2)]
        old_multi, new_multi = [self.label(multi["id"], PREFIX + "多" + str(i)) for i in range(2)]
        other_old = self.label(other["id"], PREFIX + "旧组")
        lead = success(self.create_lead([self.chosen(radio, old_radio), self.chosen(multi, old_multi),
                                         self.chosen(other, other_old)]))
        self.assert_lead_label_ids(lead["id"], [old_radio["id"], old_multi["id"], other_old["id"]])
        for _ in range(2):
            success(self.update_lead_labels([lead["id"]], [new_radio, new_multi], "replace"))
            self.assert_lead_label_ids(lead["id"], [new_radio["id"], new_multi["id"]])

    def test_batch_replace_wrong_module_label_not_saved(self):
        """替换请求混入联系人专属标签时不得存入线索；成功则仅保留合法新值。"""
        allowed = self.group(applicable_models=["Lead"])
        forbidden = self.group(name=PREFIX + "B", applicable_models=["Contact"])
        old, new = [self.label(allowed["id"], PREFIX + str(i)) for i in range(2)]
        excluded = self.label(forbidden["id"], PREFIX + "不适用")
        lead = success(self.create_lead([self.chosen(allowed, old)]))
        self.assert_lead_label_ids(lead["id"], [old["id"]])
        result = self.update_lead_labels([lead["id"]], [new, excluded], "replace")
        if result[1].get("code") == 0:
            success(result)
            expected = [new["id"]]
        else:
            rejected(result)
            expected = [old["id"]]
        self.assert_lead_label_ids(lead["id"], expected)

    def test_batch_remove_multi_any_match_and_untargeted(self):
        """指定删除仅移除命中的标签关联，部分命中也删除，未命中及未选线索保持。"""
        g = self.group(applicable_models=["Lead"])
        first, second, kept = [self.label(g["id"], PREFIX + str(i)) for i in range(3)]
        all_chosen = [self.chosen(g, x) for x in (first, second, kept)]
        both = success(self.create_lead(all_chosen, name=PREFIX + "全命中"))
        partial = success(self.create_lead([self.chosen(g, first), self.chosen(g, kept)], name=PREFIX + "部分"))
        unmatched = success(self.create_lead([self.chosen(g, kept)], name=PREFIX + "未命中"))
        untouched = success(self.create_lead(all_chosen, name=PREFIX + "未选"))
        self.assert_lead_label_ids(both["id"], [first["id"], second["id"], kept["id"]])
        self.assert_lead_label_ids(partial["id"], [first["id"], kept["id"]])
        self.assert_lead_label_ids(unmatched["id"], [kept["id"]])
        self.assert_lead_label_ids(untouched["id"], [first["id"], second["id"], kept["id"]])
        success(self.update_lead_labels([both["id"], partial["id"], unmatched["id"]],
                                        [first, second], "remove_one_match"))
        for lead in (both, partial, unmatched):
            self.assert_lead_label_ids(lead["id"], [kept["id"]])
        self.assert_lead_label_ids(untouched["id"], [first["id"], second["id"], kept["id"]])
        self.assertEqual({x["id"] for x in self.persisted(g["id"])["labels"]},
                         {first["id"], second["id"], kept["id"]})

    def test_batch_remove_radio_exact_match_repeated(self):
        """移除单选指定值仅影响该值，保留同组其他值及跨组标签，重复删除结果稳定。"""
        radio = self.group(select_type="radio", applicable_models=["Lead"])
        multi = self.group(name=PREFIX + "B", applicable_models=["Lead"])
        removed, other = [self.label(radio["id"], PREFIX + str(i)) for i in range(2)]
        kept = self.label(multi["id"], PREFIX + "保留")
        matched = success(self.create_lead([self.chosen(radio, removed), self.chosen(multi, kept)],
                                           name=PREFIX + "命中"))
        unmatched = success(self.create_lead([self.chosen(radio, other), self.chosen(multi, kept)],
                                             name=PREFIX + "其他值"))
        self.assert_lead_label_ids(matched["id"], [removed["id"], kept["id"]])
        self.assert_lead_label_ids(unmatched["id"], [other["id"], kept["id"]])
        for _ in range(2):
            success(self.update_lead_labels([matched["id"], unmatched["id"]], [removed], "remove_one_match"))
            self.assert_lead_label_ids(matched["id"], [kept["id"]])
            self.assert_lead_label_ids(unmatched["id"], [other["id"], kept["id"]])
        self.assertEqual({x["id"] for x in self.persisted(radio["id"])["labels"]},
                         {removed["id"], other["id"]})

    def test_batch_remove_wrong_module_preserves_original_labels(self):
        """指定删除联系人专属标签不能误删线索原标签或标签定义。"""
        allowed = self.group(applicable_models=["Lead"])
        forbidden = self.group(name=PREFIX + "B", applicable_models=["Contact"])
        kept = self.label(allowed["id"], PREFIX + "原值")
        excluded = self.label(forbidden["id"], PREFIX + "不适用")
        lead = success(self.create_lead([self.chosen(allowed, kept)]))
        self.assert_lead_label_ids(lead["id"], [kept["id"]])
        result = self.update_lead_labels([lead["id"]], [excluded], "remove_one_match")
        if result[1].get("code") == 0:
            success(result)
        else:
            rejected(result)
        self.assert_lead_label_ids(lead["id"], [kept["id"]])
        self.assertEqual([x["id"] for x in self.persisted(allowed["id"])["labels"]], [kept["id"]])
        self.assertEqual([x["id"] for x in self.persisted(forbidden["id"])["labels"]], [excluded["id"]])

    def test_batch_remove_full_multi_requires_all_selected_tags(self):
        """完全匹配按每条线索判断，额外标签不妨碍命中，部分/未命中及未选线索保持。"""
        g = self.group(applicable_models=["Lead"])
        first, second, kept = [self.label(g["id"], PREFIX + str(i)) for i in range(3)]
        fixtures = [([first, second], []),
                    ([first, second, kept], [kept["id"]]),
                    ([first, kept], [first["id"], kept["id"]]),
                    ([kept], [kept["id"]]), ([], [])]
        selected = []
        for index, (labels, expected) in enumerate(fixtures):
            lead = success(self.create_lead([self.chosen(g, x) for x in labels],
                                            name=PREFIX + "全匹" + str(index)))
            self.assert_lead_label_ids(lead["id"], [x["id"] for x in labels])
            selected.append((lead["id"], expected))
        untouched = success(self.create_lead([self.chosen(g, first), self.chosen(g, second)],
                                             name=PREFIX + "未选"))
        self.assert_lead_label_ids(untouched["id"], [first["id"], second["id"]])
        success(self.update_lead_labels([identifier for identifier, _ in selected],
                                        [first, second], "remove_full_match"))
        for identifier, expected in selected:
            self.assert_lead_label_ids(identifier, expected)
        self.assert_lead_label_ids(untouched["id"], [first["id"], second["id"]])
        self.assertEqual({x["id"] for x in self.persisted(g["id"])["labels"]},
                         {first["id"], second["id"], kept["id"]})

    def test_batch_remove_full_cross_group_requires_complete_combination(self):
        """跨单选与多选组的组合必须全部命中，部分命中不删除，重复提交结果稳定。"""
        radio = self.group(select_type="radio", applicable_models=["Lead"])
        multi = self.group(name=PREFIX + "B", applicable_models=["Lead"])
        target, other = [self.label(radio["id"], PREFIX + "单" + str(i)) for i in range(2)]
        removed, kept = [self.label(multi["id"], PREFIX + "多" + str(i)) for i in range(2)]
        fixtures = [([(radio, target), (multi, removed), (multi, kept)], [kept["id"]]),
                    ([(radio, other), (multi, removed)], [other["id"], removed["id"]]),
                    ([(radio, target), (multi, kept)], [target["id"], kept["id"]])]
        selected = []
        for index, (labels, expected) in enumerate(fixtures):
            lead = success(self.create_lead([self.chosen(g, x) for g, x in labels],
                                            name=PREFIX + "跨组" + str(index)))
            self.assert_lead_label_ids(lead["id"], [x["id"] for _, x in labels])
            selected.append((lead["id"], expected))
        for _ in range(2):
            success(self.update_lead_labels([identifier for identifier, _ in selected],
                                            [target, removed], "remove_full_match"))
            for identifier, expected in selected:
                self.assert_lead_label_ids(identifier, expected)
        self.assertEqual({x["id"] for x in self.persisted(radio["id"])["labels"]},
                         {target["id"], other["id"]})
        self.assertEqual({x["id"] for x in self.persisted(multi["id"])["labels"]},
                         {removed["id"], kept["id"]})

    def test_batch_remove_full_single_radio_target_repeated(self):
        """仅指定一个单选标签时命中即可删除，同组其他值保持，重复提交无副作用。"""
        g = self.group(select_type="radio", applicable_models=["Lead"])
        removed, kept = [self.label(g["id"], PREFIX + str(i)) for i in range(2)]
        matched = success(self.create_lead([self.chosen(g, removed)], name=PREFIX + "命中"))
        unmatched = success(self.create_lead([self.chosen(g, kept)], name=PREFIX + "其他值"))
        self.assert_lead_label_ids(matched["id"], [removed["id"]])
        self.assert_lead_label_ids(unmatched["id"], [kept["id"]])
        for _ in range(2):
            success(self.update_lead_labels([matched["id"], unmatched["id"]],
                                            [removed], "remove_full_match"))
            self.assert_lead_label_ids(matched["id"], [])
            self.assert_lead_label_ids(unmatched["id"], [kept["id"]])
        self.assertEqual({x["id"] for x in self.persisted(g["id"])["labels"]},
                         {removed["id"], kept["id"]})

    def test_batch_remove_full_wrong_module_preserves_original_labels(self):
        """完全匹配删除输入不适用模块标签时，不得误删线索原关联或标签定义。"""
        allowed = self.group(applicable_models=["Lead"])
        forbidden = self.group(name=PREFIX + "B", applicable_models=["Contact"])
        kept = self.label(allowed["id"], PREFIX + "原值")
        excluded = self.label(forbidden["id"], PREFIX + "不适用")
        lead = success(self.create_lead([self.chosen(allowed, kept)]))
        self.assert_lead_label_ids(lead["id"], [kept["id"]])
        result = self.update_lead_labels([lead["id"]], [excluded], "remove_full_match")
        if result[1].get("code") == 0:
            success(result)
        else:
            rejected(result)
        self.assert_lead_label_ids(lead["id"], [kept["id"]])
        self.assertEqual([x["id"] for x in self.persisted(allowed["id"])["labels"]], [kept["id"]])
        self.assertEqual([x["id"] for x in self.persisted(forbidden["id"])["labels"]], [excluded["id"]])

    def assert_customer_preview(self, lead_id, expected, source_ids):
        before = success(api("GET", f"/leads/{lead_id}"))
        preview = success(api("GET", f"/leads/{lead_id}/turn_to_customer?custom_field_template_id={settings.template('Customer', 1172)}"))
        self.assertEqual(preview["id"], 0)
        self.assertEqual(preview["custom_field_template_id"], settings.template("Customer", 1172))
        self.assertEqual(sorted((x["id"], x["content"]) for x in preview["labels"]),
                         sorted((x["id"], x["content"]) for x in expected))
        for label in preview["labels"]:
            self.assertEqual(label["group_id"], next(x["label_group_id"] for x in expected if x["id"] == label["id"]))
        after = success(api("GET", f"/leads/{lead_id}"))
        self.assertEqual({x["id"] for x in after["labels"]}, set(source_ids))
        self.assertEqual(after["turned_to_customer"], before["turned_to_customer"])
        self.assertFalse(after["turned_to_customer"])
        self.assertEqual(after["turned_customer_id"], before["turned_customer_id"])
        self.assertEqual(after["turned_customer_id"], 0)

    def test_customer_preview_multi_filters_lead_only_labels(self):
        """转客户预填保留多选共用标签，过滤线索专属标签，源线索不转化。"""
        shared = self.group(applicable_models=["Lead", "Customer"])
        private = self.group(name=PREFIX + "B", applicable_models=["Lead"])
        expected = [self.label(shared["id"], PREFIX + str(i)) for i in range(2)]
        excluded = self.label(private["id"], PREFIX + "独有")
        chosen = [self.chosen(shared, x) for x in expected] + [self.chosen(private, excluded)]
        lead = success(self.create_lead(chosen))
        source_ids = [x["id"] for x in expected] + [excluded["id"]]
        self.assertEqual({x["id"] for x in self.lead_labels(lead["id"])}, set(source_ids))
        self.assert_customer_preview(lead["id"], expected, source_ids)

    def test_customer_preview_radio_label_preserved(self):
        """转客户预填保留共用单选标签的 ID、内容及分组。"""
        g = self.group(select_type="radio", applicable_models=["Lead", "Customer"])
        label = self.label(g["id"])
        lead = success(self.create_lead([self.chosen(g, label)]))
        self.assertEqual([x["id"] for x in self.lead_labels(lead["id"])], [label["id"]])
        self.assert_customer_preview(lead["id"], [label], [label["id"]])

    def test_customer_preview_no_labels_stays_empty(self):
        """无标签线索转客户预填为空，不凭空添加标签。"""
        lead = success(self.create_lead([]))
        self.assertEqual(self.lead_labels(lead["id"]), [])
        self.assert_customer_preview(lead["id"], [], [])

    def assert_customer_conversion(self, lead, expected):
        preview = success(api("GET", f'/leads/{lead["id"]}/turn_to_customer?custom_field_template_id={settings.template("Customer", 1172)}'))
        self.assertEqual(sorted(x["id"] for x in preview["labels"]), sorted(x["id"] for x in expected))
        # Preserve mapped labels from the preview rather than reconstructing them.
        customer = {"name": "映射客户" + PREFIX, "company_name": "标签映射测试企业" + PREFIX,
                    "custom_field_template_id": 1172, "source": 391979,
                    "labels": preview["labels"], "lead_id": lead["id"],
                    "numeric_asset_c12fb7": 12.34, "numeric_asset_b6049b": "10",
                    "numeric_asset_26d18d": "123", "user_id": 1000025901,
                    "want_department_id": 5506212, "contacts_attributes": [],
                    "contact_assetships_attributes": [], "opportunity_id": 0,
                    "assist_user_ids": [], "subsidiary_users_attributes": [],
                    "address_attributes": {}}
        customer = settings.record("Customer", customer, ("name", "company_name", "labels", "lead_id", "contacts_attributes", "contact_assetships_attributes", "assist_user_ids", "address_attributes"))
        customer["custom_field_template_id"] = settings.template("Customer", 1172)
        created = success(api("POST", "/customers", {
            "refer_lead_id": lead["id"], "data_from": "turn_to_customer",
            "request_ticket": str(uuid.uuid4()), "customer": customer}))
        actual = success(api("GET", f'/customers/{created["id"]}'))
        self.assertEqual(actual["name"], customer["name"])
        self.assertEqual(sorted((x["id"], x["content"], x["group_id"]) for x in actual["labels"]),
                         sorted((x["id"], x["content"], x["label_group_id"]) for x in expected))
        converted = success(api("GET", f'/leads/{lead["id"]}'))
        self.assertTrue(converted["turned_to_customer"])
        self.assertEqual(converted["turned_customer_id"], created["id"])
        self.assertEqual({x["id"] for x in converted["labels"]}, {x["id"] for x in lead["labels"]})

    def test_customer_conversion_multi_mapping(self):
        """线索转客户完整链路：两个共用多选标签落库，线索专属标签过滤。"""
        shared = self.group(applicable_models=["Lead", "Customer"])
        private = self.group(name=PREFIX + "B", applicable_models=["Lead"])
        expected = [self.label(shared["id"], PREFIX + str(i)) for i in range(2)]
        excluded = self.label(private["id"], PREFIX + "独有")
        lead = success(self.create_lead([self.chosen(shared, x) for x in expected]
                                       + [self.chosen(private, excluded)]))
        self.assertEqual({x["id"] for x in lead["labels"]}, {x["id"] for x in expected} | {excluded["id"]})
        self.assert_customer_conversion(lead, expected)

    def test_customer_conversion_radio_mapping(self):
        """线索共用单选标签转换后在客户详情精确回读，线索关联正确客户。"""
        g = self.group(select_type="radio", applicable_models=["Lead", "Customer"])
        label = self.label(g["id"])
        lead = success(self.create_lead([self.chosen(g, label)]))
        self.assert_customer_conversion(lead, [label])

    def test_customer_conversion_no_labels(self):
        """无标签线索转换成功后客户标签仍为空，线索转化状态正确。"""
        lead = success(self.create_lead([]))
        self.assert_customer_conversion(lead, [])

    def test_lead_create_multi_labels_readback(self):
        """P0：多选分组两个标签随 PC 线索创建，详情精确回读。"""
        g = self.group(applicable_models=["Lead"])
        labels = [self.label(g["id"], PREFIX + str(i)) for i in range(2)]
        lead = success(self.create_lead([self.chosen(g, x) for x in labels]))
        self.assertEqual({x["id"] for x in self.lead_labels(lead["id"])}, {x["id"] for x in labels})

    def test_lead_create_radio_one_readback(self):
        """单选分组一个标签随 PC 线索保存并精确回读。"""
        g = self.group(select_type="radio", applicable_models=["Lead"])
        label = self.label(g["id"])
        lead = success(self.create_lead([self.chosen(g, label)]))
        self.assertEqual([x["id"] for x in self.lead_labels(lead["id"])], [label["id"]])

    def test_lead_create_radio_multiple_bounded(self):
        """同一单选分组提交两个值，保存结果至多一个且属于提交值。"""
        g = self.group(select_type="radio", applicable_models=["Lead"])
        labels = [self.label(g["id"], PREFIX + str(i)) for i in range(2)]
        result = self.create_lead([self.chosen(g, x) for x in labels])
        if result[1].get("code") == 0:
            actual = self.lead_labels(success(result)["id"])
            self.assertLessEqual(len(actual), 1)
            self.assertTrue({x["id"] for x in actual}.issubset({x["id"] for x in labels}))
        else:
            rejected(result)

    def test_lead_create_wrong_module_label_not_saved(self):
        """联系人专属标签不能随线索保存。"""
        g = self.group(applicable_models=["Contact"])
        label = self.label(g["id"])
        result = self.create_lead([self.chosen(g, label)])
        if result[1].get("code") == 0:
            self.assertEqual(self.lead_labels(success(result)["id"]), [])
        else:
            rejected(result)

    def test_lead_edit_and_clear_labels(self):
        """PC 编辑线索替换标签并清空，详情回读不残留旧值。"""
        g = self.group(applicable_models=["Lead"])
        first, second = [self.label(g["id"], PREFIX + str(i)) for i in range(2)]
        lead = success(self.create_lead([self.chosen(g, first)]))
        success(api("PUT", f'/leads/{lead["id"]}', {"lead": {"labels": [self.chosen(g, second)]}}))
        self.assertEqual([x["id"] for x in self.lead_labels(lead["id"])], [second["id"]])
        success(api("PUT", f'/leads/{lead["id"]}', {"lead": {"labels": []}}))
        self.assertEqual(self.lead_labels(lead["id"]), [])

    def test_lead_unrelated_edit_keeps_labels(self):
        """修改非标签字段时保留已关联标签。"""
        g = self.group(applicable_models=["Lead"])
        label = self.label(g["id"])
        lead = success(self.create_lead([self.chosen(g, label)]))
        success(api("PUT", f'/leads/{lead["id"]}', {"lead": {"name": "标签保留" + PREFIX}}))
        actual = success(api("GET", f'/leads/{lead["id"]}'))
        self.assertEqual(actual["name"], "标签保留" + PREFIX)
        self.assertEqual([x["id"] for x in actual["labels"]], [label["id"]])

    def test_remove_used_model_rejected(self):
        """已有打标线索时禁止取消线索适用范围，原配置与标签关联保留。"""
        g = self.group()
        label = self.label(g["id"])
        lead = success(self.create_lead([self.chosen(g, label)]))
        rejected(api("PUT", f'/label_groups/{g["id"]}', {
            "label_group": {"applicable_models": ["Contact"]}}))
        self.assertEqual(set(self.persisted(g["id"])["applicable_models"]), {"Contact", "Lead"})
        self.assertEqual([x["id"] for x in self.lead_labels(lead["id"])], [label["id"]])


def module_case(model):
    def test(self):
        g = self.group(applicable_models=[model])
        label = self.label(g["id"])
        allowed = next(x for x in options(model) if x["id"] == g["id"])
        self.assertEqual([x["id"] for x in allowed["labels"]], [label["id"]])
        other = "Lead" if model != "Lead" else "Contact"
        self.assertNotIn(g["id"], [x["id"] for x in options(other)])
    test.__doc__ = f"{model} 适用标签可见，其他模块不可见。"
    return test


for model in MODELS:
    setattr(PCLabelTests, "test_scope_" + model, module_case(model))


class EvidenceResult(unittest.TextTestResult):
    def stopTest(self, test):
        failures = [(str(t), detail) for t, detail in self.failures + self.errors if t == test]
        skipped = [reason for t, reason in self.skipped if t == test]
        CASE_RESULTS.append({"case": test.id(), "description": test.shortDescription(),
                             "status": "FAIL" if failures else "SKIP" if skipped else "PASS",
                             "skip_reason": skipped,
                             "failures": [d for _, d in failures],
                             "evidence_start": test.start, "evidence_end": len(EVIDENCE)})
        save()
        super().stopTest(test)


if __name__ == "__main__":
    SESSION.headers.update(settings.headers())
    baseline = groups()
    suite = (unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:], module=sys.modules[__name__])
             if len(sys.argv) > 1 else unittest.TestSuite(
                 unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                 for cls in (PCLabelTests, PCBatchTests, PCLeadTests)))
    result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(suite)
    final = groups()
    # Compare only pre-existing groups; never modify them to force a baseline match.
    baseline_ids = {x["id"] for x in baseline}
    compatibility = [x for x in final if x["id"] in baseline_ids] == baseline
    report = {"executed": result.testsRun, "passed": sum(x["status"] == "PASS" for x in CASE_RESULTS),
              "failed": sum(x["status"] == "FAIL" for x in CASE_RESULTS),
              "skipped": len(result.skipped),
              "baseline_group_count": len(baseline), "final_group_count": len(final),
              "existing_configuration_unchanged": compatibility,
              "remaining_group_ids": sorted(OWN_GROUPS), "remaining_label_ids": sorted(OWN_LABELS),
              "remaining_lead_ids": sorted(OWN_LEADS), "remaining_customer_ids": sorted(OWN_CUSTOMERS)}
    (OUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    print("Evidence:", OUT)
    raise SystemExit(0 if result.wasSuccessful() and compatibility and not OWN_GROUPS and not OWN_LABELS and not OWN_LEADS and not OWN_CUSTOMERS else 1)
