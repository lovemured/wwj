import requests
import time

import urllib3

from common.feiyu_payload import HEADERS, URL, gen_data

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

COOKIE = {
    "feiyu_csrf_token": "k9ZvadgVMT1pqCl8YMFiyQz1",
    "passport_csrf_token": "e49fd1b54a8c162da9ee88aefb205036",
    "passport_csrf_token_default": "e49fd1b54a8c162da9ee88aefb205036",
    "d_ticket": "0f473289f20f2ca3e1b8aa7bf0ecbbfbad6ae",
    "n_mh": "9-mIeuD4wZnlYrrOvfzG3MuT6aQmCUtmr8FxV8Kl8xY",
    "is_staff_user": "false",
    "x-web-secsdk-uid": "ef3b4790-3ca5-4e02-8d2a-5508caf2db8a",
    "advertiserId": "1728061823011854",
    "superGroupId": "7078141129840934949",
    "sid_tt": "7a2612103f3ed1d6308b4a7c272d1669",
    "sessionid": "c07d254bf51f429dd7c8d14b6954c874",
    "sessionid_ss": "c07d254bf51f429dd7c8d14b6954c874",
    "ttwid": "1%7C3xM7sTu6GUTG599YRPtt2LHadJfpYJk_JgtObd6A09w%7C1774514860%7C6b16edda821775b7f3c1fb8d7b7bb6eee7c36c7b880f7c1de3d28c153af785bc",
}


# 单次推送 + 打印返回值（方便排查失败）
def send_once():
    data = gen_data(include_source=True)
    try:
        resp = requests.post(URL, headers=HEADERS, cookies=COOKIE, json=data, verify=False, timeout=10)
        resp.raise_for_status()
        # 打印关键信息 + 返回结果
        print(f"✅ 推送成功 | name={data['clueInfo']['name']} phone={data['clueInfo']['telphone']} weixin={data['clueInfo']['weixin']}")
        print(f"📄 接口返回：{resp.status_code} | {resp.text}")
        return resp
    except requests.RequestException as e:
        print(f"❌ 推送失败：{str(e)}")
        return None


# 批量推送
def batch_send(total=20):
    print(f"🚀 开始批量推送，共 {total} 条")
    for i in range(total):
        print(f"\n===== 第 {i+1}/{total} 条 =====")
        send_once()
        time.sleep(1)
    print("\n🏁 全部推送完成")


if __name__ == "__main__":
    batch_send(total=1)
