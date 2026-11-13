"""Offline checks; no CRM environment is contacted."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from environment import Environment, from_command_line


class EnvironmentTests(unittest.TestCase):
    def test_default_routes_for_all_environments(self):
        for env, suffix in (("test", "-test"), ("staging", "-staging"), ("production", "")):
            with self.subTest(env=env):
                cfg = Environment(env, config={}, token="offline")
                self.assertEqual(cfg.pc_base, f"https://lxcrm-api{suffix}.weiwenjia.com/api/pc")
                self.assertEqual(cfg.mobile_origin, f"https://crmh5{suffix}.weiwenjia.com")
                self.assertEqual(cfg.loader_prefix, "/api/pc/entity_loaders" if env == "test" else "/api/entity_loaders")
                self.assertIn('device="lxcrm_duli"', cfg.headers(mobile=True)["Authorization"])

    def test_frontend_api_urls_and_trailing_slashes(self):
        for api in ("https://lxcrm-staging.weiwenjia.com/", "https://lxcrm-api-staging.weiwenjia.com/api/pc/",
                    "https://lxcrm-api-staging.weiwenjia.com/api/v2"):
            self.assertEqual(Environment("staging", config={}, api=api).api_root,
                             "https://lxcrm-api-staging.weiwenjia.com/api")
        custom = Environment(config={}, api="http://127.0.0.1:1234/api")
        self.assertEqual(custom.pc_base, "http://127.0.0.1:1234/api/pc")

    def test_reject_invalid_urls_and_profiles(self):
        for api in ("ftp://example.com", "https://user:secret@example.com", "https://example.com/api/pc/leads", "https://example.com/?token=secret"):
            with self.subTest(api=api), self.assertRaises(ValueError):
                Environment(config={}, api=api)
        with self.assertRaises(ValueError):
            Environment(profile="../other", config={})

    def test_cli_precedence_and_remaining_scenario_arguments(self):
        args = ["runner.py", "--env", "staging", "--profile", "gray", "--api", "https://override.example.com",
                "--token", "cli-token", "PCLabelTests", "--mappings"]
        with patch("environment.load_config", return_value={"api": "https://config.example.com", "token": "config-token"}) as load, \
                patch.dict("os.environ", {"WWJ_ENV": "production", "CRM_LABEL_TOKEN": "env-token"}), \
                patch.object(sys, "argv", args):
            cfg = from_command_line()
            load.assert_called_once_with("staging", "gray")
            self.assertEqual((cfg.origin, cfg.token), ("https://override.example.com", "cli-token"))
            self.assertEqual(sys.argv, ["runner.py", "PCLabelTests", "--mappings"])

    def test_config_and_missing_credentials(self):
        self.assertEqual(Environment(config={"token": "config-token"}).token, "config-token")
        with self.assertRaises(ValueError):
            Environment(config={}).token
        with self.assertRaisesRegex(ValueError, "templates.Customer"):
            Environment("staging", config={"label_management": {"templates": {}}}).template("Customer", 1172)

    def test_tenant_values_never_fall_back_in_staging_production_or_profiles(self):
        for env, profile in (("staging", None), ("production", None), ("test", "another-company")):
            cfg = Environment(env, profile, config={})
            with self.subTest(env=env, profile=profile):
                with self.assertRaises(ValueError):
                    cfg.payload("Lead", {"user_id": 1000025901})
                with self.assertRaises(ValueError):
                    cfg.template("Customer", 1172)
                with self.assertRaises(ValueError):
                    cfg.faye_url
        self.assertEqual(Environment(config={}).payload("Lead", {"source": 1}), {"source": 1})

    def test_environment_directories_and_record_payload_isolation(self):
        cfg = Environment("production", "company", config={"label_management": {
            "pc_payloads": {"Lead": {"source": 99, "user_id": 88, "nested": []}}, "templates": {"Customer": 77}}})
        values = cfg.record("Lead", {"source": 1, "name": "owned", "labels": [2]}, ("name", "labels"))
        self.assertEqual(values, {"source": 99, "user_id": 88, "nested": [], "name": "owned", "labels": [2]})
        values["nested"].append("changed")
        self.assertEqual(cfg.label["pc_payloads"]["Lead"]["nested"], [])
        self.assertEqual(cfg.template("Customer", 1172), 77)
        self.assertEqual(cfg.result_root.parts[-2:], ("production", "company"))
        self.assertEqual(cfg.data_root.parts[-2:], ("production", "company"))

    def test_pc_create_uses_selected_tenant_and_api(self):
        import pc_api_regression as core
        cfg = Environment("staging", config={"label_management": {
            "pc_payloads": {"Lead": {"user_id": 12, "source": 13}}, "lead_label_field_id": 14}}, token="offline")
        response = Mock(status_code=200)
        response.json.return_value = {"code": 0, "data": {"id": 987}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, "settings", cfg), \
                patch.object(core, "BASE", cfg.pc_base), patch.object(core, "OUT", Path(tmp)), \
                patch.object(core, "EVIDENCE", []), patch.object(core, "OWN_LEADS", set()), \
                patch.object(core.SESSION, "request", return_value=response) as request:
            core.PCLeadTests().create_lead([{"id": 5}], name="owned")
            self.assertEqual(request.call_args.args[1], cfg.pc_base + "/leads")
            body = request.call_args.kwargs["json"]["lead"]
            self.assertEqual(body["user_id"], 12)
            self.assertEqual(body["source"], 13)
            self.assertNotIn("numeric_asset_922345", body)
            core.PCLeadTests().update_lead_labels([987], [], "replace")
            self.assertEqual(request.call_args.kwargs["json"]["field_id"], 14)

    def test_import_route_switch_and_restoration_on_failure(self):
        import pc_import_labels as imp
        for env in ("test", "staging", "production"):
            cfg = Environment(env, config={})
            observed = []
            def fail(method, path, body):
                observed.append((imp.core.BASE, path))
                raise RuntimeError("offline failure")
            before = imp.core.BASE
            with patch.object(imp, "settings", cfg), patch.object(imp.core, "api", side_effect=fail):
                with self.assertRaises(RuntimeError):
                    imp.loader_api("POST", "/upload", {})
            self.assertEqual(observed, [(cfg.origin, cfg.loader_prefix + "/upload")])
            self.assertEqual(imp.core.BASE, before)

    def test_mobile_requests_use_selected_environment_and_restore_pc_base(self):
        import environment
        import pc_api_regression as core
        cfg = Environment("production", config={"label_management": {"templates": {}}})
        old = sys.modules.pop("mobile_module_regression", None)
        try:
            with patch.object(environment, "settings", cfg), patch.object(core, "BASE", cfg.pc_base):
                module = importlib.import_module("mobile_module_regression")
                seen = []
                def capture(method, path, body):
                    seen.append((core.BASE, path))
                    return 200, {"code": 0}
                with patch.object(core, "api", side_effect=capture):
                    module.mobile("GET", "/quotations", version="v2")
                    module.mobile("GET", "/leads", version="v3")
                self.assertEqual(seen, [(cfg.api_root + "/v2", "/quotations"),
                                        (cfg.api_root + "/v3", "/leads")])
                self.assertEqual(core.BASE, cfg.pc_base)
        finally:
            sys.modules.pop("mobile_module_regression", None)
            if old is not None:
                sys.modules["mobile_module_regression"] = old

    def test_custom_import_settings_and_current_template_layout(self):
        import pc_import_labels as imp
        cfg = Environment("staging", config={"label_management": {
            "faye_url": "https://events.example.com/faye", "entity_loader_prefix": "/api/tenant_loaders",
            "upload_token_path": "/api/tenant_upload_token", "lead_import_layout": {
                "columns": 7, "label_col": 2, "name_col": 6, "defaults": {"1": "required"}}}})
        self.assertEqual(cfg.faye_url, "https://events.example.com/faye")
        self.assertEqual(cfg.upload_token_path, "/api/tenant_upload_token")
        self.assertEqual(cfg.loader_prefix, "/api/tenant_loaders")
        with patch.object(imp, "settings", cfg):
            self.assertEqual(imp.row("owned-name", "tag"), ["required", "tag", None, None, None, "owned-name", None])

    def test_environment_preview_never_prints_token(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("environment.py")),
                                 "--env", "production", "--token", "private-test-token"],
                                capture_output=True, text=True, check=True)
        self.assertNotIn("private-test-token", result.stdout)
        self.assertEqual(json.loads(result.stdout)["environment"], "production")


if __name__ == "__main__":
    unittest.main()
