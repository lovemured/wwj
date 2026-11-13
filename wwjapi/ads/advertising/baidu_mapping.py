"""百度字段映射的兼容导出。"""

from common.field_mapping import CRM_FIELD_PATHS, map_common_fields


BAIDU_FIELD_MAPPING = CRM_FIELD_PATHS


def map_baidu_fields(values):
    """兼容旧调用方，统一使用渠道共用的 CRM 字段路径。"""
    return map_common_fields(values)
