"""Shared config helpers for local CRM scripts."""
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def apply_config_defaults(args, parser=None):
    cfg = load_config()
    if hasattr(args, "api") and not args.api:
        args.api = cfg.get("api", "")
    if hasattr(args, "token") and not args.token:
        args.token = cfg.get("token", "")
    if hasattr(args, "attachment_dir") and not args.attachment_dir:
        args.attachment_dir = cfg.get("attachment_dir")
    if parser and (hasattr(args, "api") and not args.api or hasattr(args, "token") and not args.token):
        parser.error("请在config.json中配置api和token，或通过--api/--token传入")
    return args
