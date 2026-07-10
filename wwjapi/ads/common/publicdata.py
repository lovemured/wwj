import random


class GetRequestdata:
    ENV_HOSTS = {
        "test": "https://ads-test.weiwenjia.com",
        "staging": "https://ads-staging.weiwenjia.com",
        "pro": "https://ads.weiwenjia.com",
    }
    env = list(ENV_HOSTS)
    # 接收url
    accept_url = ''
    # 资源流入
    accept_resource_style = ["线索", "线索池", "客户", "客户公海"]
    # 资源名称
    adv_name = ''
    adv_id = ''

    def get_url(self, env_now, half_accpet_url):
        # 获取各环境完整的url
        if env_now not in GetRequestdata.ENV_HOSTS:
            raise ValueError(f"未知环境：{env_now}")
        GetRequestdata.accept_url = GetRequestdata.ENV_HOSTS[env_now] + half_accpet_url
        return GetRequestdata.accept_url

    def get_requestdata(self, resource_style):
        # 获取流入不同类型的资源名称、不同的广告id
        if resource_style not in GetRequestdata.accept_resource_style:
            raise ValueError(f"未知资源类型：{resource_style}")

        num = '1368163863861283681681'
        num1 = random.sample(num, 6)
        GetRequestdata.adv_id = ''.join(num1)
        a = 'jhadjhajdhjwhdjwhfjwhfjhj2781738917'
        b = random.sample(a, 5)
        GetRequestdata.adv_name = "百度" + resource_style + "广告助手" + ''.join(b)
        return GetRequestdata.adv_name, GetRequestdata.adv_id

