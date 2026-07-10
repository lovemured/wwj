import random
import string
import time

from faker import Faker


fake = Faker("zh_CN")

URL = "https://feiyu.oceanengine.com/bff/pc/settings/clue-translate-rule-debug?clue_account_id=1728061825523716"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://feiyu.oceanengine.com",
    "referer": "https://feiyu.oceanengine.com/pc/crm/feiyu/management/clue-push-rule/add-edit-config?status=edit&id=127223&clue_account_id=1728061825523716",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "x-csrftoken": "k9ZvadgVMT1pqCl8YMFiyQz1",
    "x-path": "/pc/crm/feiyu/management/clue-push-rule/add-edit-config",
}

MAP_NORMAL = {
    "telphone": "address.phone",
    "weixin": "address.wechat",
    "adv_id": "adv_id",
    "site_name": "site_name",
    "store_id": "store_id",
    "site_id": "site_id",
    "date": "date",
    "create_time": "create_time",
    "clue_convert_status": "clue_convert_status",
    "promotion_id": "promotion_id",
    "id": "id",
    "app_name": "app_name",
    "clue_source": "clue_source",
    "ad_name": "ad_name",
    "form_remark": "form_remark",
    "promotion_name": "promotion_name",
    "store_name": "store_name",
    "location": "location",
    "county_name": "county_name",
    "email": "email",
    "province_name": "province_name",
    "adv_name": "adv_name",
    "ad_id": "ad_id",
    "business": "business",
    "store_remark": "store_remark",
    "store_address": "store_address",
    "store_location": "store_location",
    "store_pack_remark": "store_pack_remark",
    "remark_dict": "remark_dict",
    "address": "address",
    "city_name": "city_name",
    "module_id": "module_id",
    "store_pack_id": "store_pack_id",
    "qq": "qq",
    "remark": "remark",
    "name": "name",
    "cid": "cid",
    "gender": "gender",
    "store_pack_name": "store_pack_name",
    "clue_data_source_detail": "clue_data_source_detail",
    "req_id": "req_id",
    "clue_type": "clue_type",
    "module_name": "module_name",
    "age": "age",
    "external_url": "external_url",
}

MAP_NORMAL_TYPE_KEYS = [
    "adv_id",
    "site_name",
    "store_id",
    "site_id",
    "telphone",
    "date",
    "create_time",
    "clue_convert_status",
    "promotion_id",
    "id",
    "app_name",
    "clue_source",
    "ad_name",
    "form_remark",
    "promotion_name",
    "store_name",
    "location",
    "county_name",
    "email",
    "province_name",
    "adv_name",
    "ad_id",
    "business",
    "weixin",
    "store_remark",
    "store_address",
    "store_location",
    "store_pack_remark",
    "remark_dict",
    "address",
    "city_name",
    "module_id",
    "store_pack_id",
    "qq",
    "remark",
    "name",
    "cid",
    "gender",
    "store_pack_name",
    "clue_data_source_detail",
    "req_id",
    "clue_type",
    "module_name",
    "age",
    "external_url",
]

POST_CONFIG = {
    "url": "https://ads-test.weiwenjia.com/api/v1/clues/sync?s=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJydWxlX2lkIjoxNDAyLCJvcmdhbml6YXRpb25faWQiOjU1MDA5MDZ9.Z6yCrop7Qk8cBKO5nWwKwLaXBdYB53DboJ2oe-nFGZs",
    "secretkey": "UgiWlBNBDm7xNBss71kLSxbraxOCqfLf397xjGWC",
    "token": "xJgwLHfahw4raXV4nExSqbdWGcpn30QnBuyj74mL",
    "enable": 1,
}

RESP_SETTING = {
    "codeKey": "code",
    "msgKey": "message",
    "respStatusList": [
        {
            "msgValue": "success",
            "statusValue": "成功",
            "codeValueLong": 200,
            "statusExplain": "成功状态",
            "codeValue": "200",
        }
    ],
}


def r_digit(k):
    return ''.join(random.choices(string.digits, k=k))


def gen_data(include_source=False):
    ts = str(int(time.time()))
    r6 = r_digit(6)
    r8 = r_digit(8)
    phone = fake.phone_number()
    weixin = "wx" + r_digit(9)

    clue_info = {
        "adv_id": r_digit(8),
        "app_name": random.choice(["火山", "抖音", "头条", "番茄"]),
        "convert_status": random.choice(["1", "2", "3"]),
        "module_id": r_digit(12),
        "city": fake.city(),
        "store_name": "",
        "location": f"{fake.province()}+{fake.city()}",
        "business_dict": "{}",
        "clue_source": random.choice(["1", "2", "3", "4"]),
        "weixin": weixin,
        "adv_name": fake.company(),
        "advertiser_id": r_digit(10),
        "ad_name": f"测试计划_{r6}",
        "qq": "",
        "name": fake.name(),
        "cid": "0",
        "gender": random.choice(["男", "女"]),
        "module_name": f"组件_{r8}",
        "external_url": "https://ad.toutiao.com/tetris/page/66959075793122099/",
        "site_name": "",
        "store_id": "0",
        "telphone": phone,
        "create_time": ts,
        "clue_convert_status": random.choice(["广告预览", "营销预览", "已转化"]),
        "id": r_digit(16),
        "form_remark": "",
        "email": fake.email(),
        "province_name": fake.province(),
        "ad_id": r_digit(12),
        "address": fake.address(),
        "city_name": fake.city(),
        "age": str(random.randint(18, 55)),
        "modify_time": ts,
        "req_id": f"20200318{r6}{r_digit(8)}",
        "clue_data_source_detail": f"测试渠道_{r6}",
        "flow_type": "2",
        "mid_info": '{"titleId":1356780190,"videoId":1648622907,"imageId":3683964167}',
    }
    if include_source:
        clue_info["source"] = "搜客宝🏠"

    return {
        "rule": {
            "id": "127223",
            "enable": 1,
            "ruleName": f"测试规则_{r6}",
            "filter": {},
            "translateMap": {
                "mapNormal": MAP_NORMAL.copy(),
                "mapNormalType": {
                    "address.phone": 0,
                    "address.wechat": 0,
                    **{k: 0 for k in MAP_NORMAL_TYPE_KEYS},
                },
                "mapForm": {},
                "mapFormType": {},
                "mapBusiness": {},
                "mapBusinessType": {},
                "mapCustom": {},
            },
            "postConfig": POST_CONFIG.copy(),
            "respSetting": RESP_SETTING.copy(),
            "notifySetting": {"enable": 0, "crmUserIds": [], "notifyChannel": [], "timeSpan": 30},
            "mappingFormatSetting": "{}",
        },
        "clueInfo": clue_info,
    }
