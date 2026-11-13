"""广告渠道共用的 CRM 字段路径映射。"""


CRM_FIELD_PATHS = {
    "name": "name",
    "company_name": "company_name",
    "phone": "address.phone",
    "wechat": "address.wechat",
    "email": "address.email",
    "qq": "address.qq",
    "tel": "address.tel",
    "detail_address": "address.detail_address",
    "country": "address.country",
    "province": "address.province",
    "city": "address.city",
    "district": "address.district",
    "note": "note",
    "department": "department",
    "job": "job",
}

SOURCE_FIELD_PATHS = {
    "adv_id": "adv_id",
    "site_name": "site_name",
    "store_id": "store_id",
    "site_id": "site_id",
    "telphone": CRM_FIELD_PATHS["phone"],
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
    "email": CRM_FIELD_PATHS["email"],
    "province_name": "province_name",
    "adv_name": "adv_name",
    "ad_id": "ad_id",
    "business": "business",
    "weixin": CRM_FIELD_PATHS["wechat"],
    "store_remark": "store_remark",
    "store_address": "store_address",
    "store_location": "store_location",
    "store_pack_remark": "store_pack_remark",
    "remark_dict": "remark_dict",
    "address": "address",
    "city_name": "city_name",
    "module_id": "module_id",
    "store_pack_id": "store_pack_id",
    "qq": CRM_FIELD_PATHS["qq"],
    "remark": "remark",
    "name": CRM_FIELD_PATHS["name"],
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


def map_common_fields(values):
    """将脚本通用字段转换为 CRM 字段路径，忽略空值和未知字段。"""
    return {
        CRM_FIELD_PATHS[field]: value
        for field, value in values.items()
        if field in CRM_FIELD_PATHS and value is not None
    }
