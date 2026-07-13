"""Shared config helpers for local CRM scripts."""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
CONFIG_DIR = os.path.dirname(CONFIG_PATH)
SUPPORTED_ENVS = ("test", "staging", "production")


def config_path(env=None):
    return os.path.join(CONFIG_DIR, f"config.{env}.json") if env else CONFIG_PATH


def load_config(env=None):
    path = config_path(env)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def apply_config_defaults(args, parser=None):
    env = getattr(args, "env", None) or os.environ.get("WWJ_ENV")
    if env and env not in SUPPORTED_ENVS:
        message = f"未知环境 {env}，可选: {', '.join(SUPPORTED_ENVS)}"
        if parser:
            parser.error(message)
        raise ValueError(message)

    cfg = load_config(env)
    if hasattr(args, "env"):
        args.env = env
    if hasattr(args, "api") and not args.api:
        args.api = cfg.get("api", "")
    if hasattr(args, "token") and not args.token:
        args.token = cfg.get("token", "")
    if hasattr(args, "attachment_dir") and not args.attachment_dir:
        args.attachment_dir = cfg.get("attachment_dir")
    if parser and (hasattr(args, "api") and not args.api or hasattr(args, "token") and not args.token):
        config_name = os.path.basename(config_path(env))
        parser.error(f"请在{config_name}中配置api和token，或通过--api/--token传入")
    return args
