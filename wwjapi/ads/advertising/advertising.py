import time
import random
import string
from faker import Faker

# 初始化中文数据生成器
fake = Faker("zh_CN")

from common.publicdata import GetRequestdata
from common.request_util import RequestUtil


class CreateAdvertising:

    def baidu_advertising(self, url=None):
        # ===================== 核心：所有字段自动生成（每次都不同）=====================
        timestamp = str(int(time.time()))  # 时间戳，保证唯一
        random_6 = str(random.randint(100000, 999999))  # 6位随机数
        random_8 = ''.join(random.choices(string.digits, k=8))  # 8位随机字符串

        # 自动生成：姓名 + 手机号 +wx号
        auto_name = fake.name()
        auto_phone = fake.phone_number()
        auto_wx = fake.phone_number()

        # 自动生成：广告主ID / 广告计划ID / 组件ID（全部唯一）
        auto_adv_id = f"352690{random_6}"
        auto_module_id = f"16347608873{random_8}"
        auto_adv_name = fake.company()

        # 自动生成：唯一ID
        auto_id = f"6805367880608{random_6}"
        auto_ad_id = f"1634867302{random_6}"

        # ===================== 接口请求体=====================
        body = {
            "adv_id": auto_adv_id,
            "app_name": "火山",
            "convert_status": 3,
            "module_id": auto_module_id,
            "city": "北京,北京",
            "store_name": "",
            "location": "北京+北京",
            "business_dict": {},
            "clue_source": 1,
            "adv_name": auto_adv_name,
            "ad_name": f"测试计划名称_{timestamp}",
            "name": auto_name,
            "cid": 0,
            "gender": "男",
            "source": "搜客宝22🏠",
            "module_name": f"测试组件名称_{timestamp}",
            "external_url": "https://ad.toutiao.com/tetris/page/66959075793122090F234AE4/",
            "site_name": "",
            "store_id": 0,
            "address.phone": auto_phone,
            "address.wechat": auto_wx,
            "create_time": "1584498183",
            "clue_convert_status": "广告预览",
            "id": auto_id,
            "ad_id": auto_ad_id,
            "req_id": f"202003181021430100140432190F{random_6}"
        }

        # 发送请求
        response = RequestUtil().all_send_request(
            method="post",
            url=url or GetRequestdata.accept_url,
            json=body,
            verify=False
        )
        print("✅ 推送成功 →", response.text)
