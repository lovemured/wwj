import unittest

from common.feiyu_payload import MAP_NORMAL
from common.feiyu_payload import gen_data
from common.field_mapping import map_common_fields
from advertising.baidu_mapping import map_baidu_fields
from advertising import advertising as push_module


class BaiduMappingTests(unittest.TestCase):
    def setUp(self):
        self.map_fields = map_common_fields

    def test_maps_common_baidu_fields_to_crm_field_paths(self):
        values = {
            "name": "测试姓名",
            "company_name": "测试公司",
            "phone": "13800000000",
            "wechat": "13900000000",
            "email": "test@example.com",
            "qq": "123456789",
            "tel": "010-12345678",
            "detail_address": "测试地址",
            "province": "北京",
            "city": "北京市",
            "district": "朝阳区",
            "note": "测试备注",
        }

        self.assertEqual(
            self.map_fields(values),
            {
                "name": "测试姓名",
                "company_name": "测试公司",
                "address.phone": "13800000000",
                "address.wechat": "13900000000",
                "address.email": "test@example.com",
                "address.qq": "123456789",
                "address.tel": "010-12345678",
                "address.detail_address": "测试地址",
                "address.province": "北京",
                "address.city": "北京市",
                "address.district": "朝阳区",
                "note": "测试备注",
            },
        )

    def test_omits_none_values_and_unknown_fields(self):
        self.assertEqual(
            self.map_fields({"phone": None, "unknown_field": "ignored", "qq": "123456789"}),
            {"address.qq": "123456789"},
        )

    def test_baidu_and_toutiao_use_the_same_crm_paths(self):
        self.assertIs(push_module.map_common_fields, map_common_fields)
        self.assertEqual(
            map_baidu_fields({"phone": "13800000000", "wechat": "wx123"}),
            {"address.phone": "13800000000", "address.wechat": "wx123"},
        )
        self.assertEqual(MAP_NORMAL["telphone"], "address.phone")
        self.assertEqual(MAP_NORMAL["weixin"], "address.wechat")
        self.assertEqual(MAP_NORMAL["email"], "address.email")
        self.assertEqual(MAP_NORMAL["qq"], "address.qq")
        self.assertNotIn("phone", MAP_NORMAL)
        self.assertNotIn("wechat", MAP_NORMAL)

    def test_toutiao_payload_accepts_explicit_clue_values(self):
        data = gen_data(
            clue_info_overrides={
                "name": "线索转发测试",
                "telphone": "13888886666",
                "weixin": "wx1388866",
                "qq": "601480202",
                "email": "601480202@qq.com",
                "id": "6805367880608120846",
                "req_id": "202003181021430100140432190F234AE4",
            }
        )

        self.assertEqual(data["clueInfo"]["telphone"], "13888886666")
        self.assertEqual(data["clueInfo"]["weixin"], "wx1388866")
        self.assertEqual(data["clueInfo"]["email"], "601480202@qq.com")
        self.assertEqual(data["clueInfo"]["id"], "6805367880608120846")


if __name__ == "__main__":
    unittest.main()
