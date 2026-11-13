import argparse
import hashlib
import json
import time
import uuid

import requests


DEFAULT_APP_ID = "test-app-id"
DEFAULT_APP_SECRET = "test-app-secret"


def build_sign(data, app_secret):
    pairs = []
    for key in sorted(data):
        if key == "sign" or data[key] is None:
            continue
        pairs.append(f"{key}={data[key]}")
    raw = "&".join(pairs) + app_secret
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def build_payload(args):
    serial_id = args.serial_id or f"XC{int(time.time())}{uuid.uuid4().hex[:8]}"
    now_ms = int(time.time() * 1000)

    payload = {
        "serialId": serial_id,
        "orderNo": args.order_no or f"ORDER{int(time.time())}",
        "type": args.type,
        "timestamp": now_ms,
        "appId": args.app_id,
        "phoneEncrypt": args.phone_encrypt,
        "payerEncrypt": args.payer_encrypt,
        "nicknameEncrypt": args.nickname_encrypt,
        "addressEncrypt": args.address_encrypt,
        "payAmount": "199.00",
        "payTime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "courseId": 10001,
        "courseTitle": "星橙知道测试课程",
        "buyFlag": 25,
        "payType": 1,
        "refundFlag": args.refund_flag,
        "refundTime": "",
        "refundMoney": "",
        "refundApplyTime": "",
        "itemNum": 1,
        "originAmount": "299.00",
        "shopId": "shop-test-001",
        "shopName": "星橙测试店铺",
        "authorId": "author-test-001",
        "authorName": "星橙测试达人",
        "cBizDesc": "测试业务",
        "productId": "product-test-001",
        "skuId": "sku-test-001",
        "skuCode": "SKU001",
        "skuName": "标准版",
        "skuTag": "测试标签",
        "productName": "星橙知道订单测试商品",
        "ddOrderAmount": "199.00",
        "ddOrderTime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "unionId": "union-test-001",
        "region": "浙江省 杭州市 滨江区",
        "wxworkFlag": args.wxwork_flag,
        "customerName": "测试客户",
        "customerPhone": "188****5678",
        "customerGroup": "测试分组",
        "tagName": "测试标签1,测试标签2",
        "buyerWords": "这是一条测试留言",
        "postAmount": "0",
        "promotionAmount": "0",
        "promotionTalentAmount": "0",
        "promotionPayAmount": "0",
        "promotionShopAmount": "0",
        "promotionPlatformAmount": "0",
        "smsLink": "",
        "verifyCode": "",
        "remark": args.remark,
    }

    if args.type == 1:
        payload.update(
            {
                "refundFlag": 1,
                "refundTime": time.strftime("%Y-%m-%d %H:%M:%S"),
                "refundMoney": payload["payAmount"],
                "refundApplyTime": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    payload["sign"] = build_sign(payload, args.app_secret)
    return payload


def parse_args():
    parser = argparse.ArgumentParser(description="星橙知道订单线索临时推送脚本")
    parser.add_argument("--url", help="广告助手接收 URL。不传则只打印请求体")
    parser.add_argument("--app-id", default=DEFAULT_APP_ID)
    parser.add_argument("--app-secret", default=DEFAULT_APP_SECRET)
    parser.add_argument("--serial-id", help="幂等唯一键。不传则自动生成")
    parser.add_argument("--order-no", help="订单号。不传则自动生成")
    parser.add_argument("--type", type=int, choices=[0, 1], default=0, help="0=下单，1=退款")
    parser.add_argument("--refund-flag", type=int, default=0, help="0=未退款，1=已退款，2=申请退款")
    parser.add_argument("--wxwork-flag", type=int, default=0, help="0=无，1=已添加，2=已删除")
    parser.add_argument("--phone-encrypt", default="", help="手机号 RSA 加密 Hex 字符串")
    parser.add_argument("--payer-encrypt", default="", help="付款人姓名 RSA 加密 Hex 字符串")
    parser.add_argument("--nickname-encrypt", default="", help="用户昵称 RSA 加密 Hex 字符串")
    parser.add_argument("--address-encrypt", default="", help="用户地址 RSA 加密 Hex 字符串")
    parser.add_argument("--remark", default="临时脚本测试推送")
    return parser.parse_args()


def main():
    args = parse_args()
    payload = build_payload(args)

    print("请求体：")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not args.url:
        print("\n未传 --url，仅生成请求体，不发送。")
        return

    response = requests.post(
        args.url,
        json=payload,
        headers={"Content-Type": "application/json;charset=UTF-8"},
        timeout=10,
        verify=False,
    )
    print("\n响应：")
    print(response.status_code)
    print(response.text)
    response.raise_for_status()


if __name__ == "__main__":
    main()
