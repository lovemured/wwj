"""Environment and tenant settings shared by label regression entry points."""
import argparse
import copy
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from lib.config import load_config, SUPPORTED_ENVS


class Environment:
    def __init__(self, env="test", profile=None, config=None, api=None, token=None):
        if env not in SUPPORTED_ENVS:
            raise ValueError(f"未知环境 {env}，可选：{', '.join(SUPPORTED_ENVS)}")
        if profile and (Path(profile).name != profile or profile in (".", "..")):
            raise ValueError("profile 必须为单个配置名称")
        self.env, self.profile = env, profile
        self.config = load_config(env, profile) if config is None else config
        self.label = self.config.get("label_management", {})
        suffix = "" if env == "production" else "-" + env
        default_pc = f"https://lxcrm{suffix}.weiwenjia.com"
        parsed = urlsplit(api or self.config.get("api") or default_pc)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("api 必须为不含凭证的 HTTP(S) 地址")
        if parsed.path.rstrip("/") not in ("", "/api", "/api/pc", "/api/v2", "/api/v3") or parsed.query or parsed.fragment:
            raise ValueError("api 请填写站点地址或 /api、/api/pc、/api/v2、/api/v3 地址")
        hostname = parsed.netloc
        if hostname.startswith("lxcrm.") or (hostname.startswith("lxcrm-") and not hostname.startswith("lxcrm-api-")):
            hostname = hostname.replace("lxcrm", "lxcrm-api", 1)
        self.origin = urlunsplit((parsed.scheme, hostname, "", "", ""))
        self.api_root = self.origin + "/api"
        self.pc_base = self.api_root + "/pc"
        self.pc_origin = self.label.get("pc_origin", default_pc)
        self.mobile_origin = self.label.get("mobile_origin", f"https://crmh5{suffix}.weiwenjia.com")
        self._token = token or self.config.get("token")
        self.result_root = ROOT / "results" / env / (profile or "default")
        self.data_root = Path(self.label.get("data_dir", ROOT / "data" / env / (profile or "default")))
        if not self.data_root.is_absolute():
            self.data_root = ROOT.parent / self.data_root

    @property
    def token(self):
        if not self._token:
            raise ValueError(f"请配置 config.{self.env}.json 的 token 或 CRM_LABEL_TOKEN")
        return self._token

    def headers(self, mobile=False):
        device = 'device="lxcrm_duli",version_code="4.0.1"' if mobile else 'device="web"'
        return {"Authorization": f'Token token="{self.token}",{device}',
                "Accept": "application/json", "Origin": self.mobile_origin if mobile else self.pc_origin}

    def value(self, name, test_default=None):
        if name in self.label:
            return copy.deepcopy(self.label[name])
        if self.env == "test" and not self.profile:
            return copy.deepcopy(test_default)
        raise ValueError(f"当前企业缺少 label_management.{name} 配置")

    def templates(self, test_defaults):
        return self.value("templates", test_defaults)

    def template(self, model, test_default):
        templates = self.templates({model: test_default})
        if model not in templates:
            raise ValueError(f"当前企业缺少 label_management.templates.{model} 配置")
        return templates[model]

    def payload(self, model, test_defaults, mobile=False):
        name = "mobile_payloads" if mobile else "pc_payloads"
        configured = self.label.get(name, {})
        if model in configured:
            return copy.deepcopy(configured[model])
        if self.env == "test" and not self.profile:
            return copy.deepcopy(test_defaults)
        raise ValueError(f"当前企业缺少 label_management.{name}.{model} 必填字段配置")

    def record(self, model, body, dynamic, mobile=False):
        values = self.payload(model, body, mobile)
        values.update({key: copy.deepcopy(body[key]) for key in dynamic if key in body})
        return values

    @property
    def loader_prefix(self):
        return self.label.get("entity_loader_prefix", "/api/pc/entity_loaders" if self.env == "test" else "/api/entity_loaders")

    @property
    def upload_token_path(self):
        return self.label.get("upload_token_path", "/api/pc/qiniu/auth/oss_upload_token.json" if self.env == "test" else "/api/qiniu/auth/oss_upload_token.json")

    @property
    def faye_url(self):
        return self.value("faye_url", "https://faye-dev.ikcrm.com/faye")

    def metadata(self):
        return {"environment": self.env, "profile": self.profile, "api_origin": self.origin}


def from_command_line():
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--env", choices=SUPPORTED_ENVS, default=os.environ.get("WWJ_ENV", "test"))
    parser.add_argument("--profile", default=os.environ.get("WWJ_PROFILE"))
    parser.add_argument("--api", default=os.environ.get("CRM_LABEL_API"))
    parser.add_argument("--token", default=os.environ.get("CRM_LABEL_TOKEN"))
    options, remaining = parser.parse_known_args()
    sys.argv[1:] = remaining
    return Environment(**vars(options))


settings = from_command_line()

if __name__ == "__main__":
    import json
    print(json.dumps({**settings.metadata(), "pc_base": settings.pc_base,
                      "mobile_base": settings.api_root, "pc_origin": settings.pc_origin,
                      "mobile_origin": settings.mobile_origin,
                      "loader_prefix": settings.loader_prefix,
                      "result_root": str(settings.result_root), "data_root": str(settings.data_root)},
                     ensure_ascii=False, indent=2))
