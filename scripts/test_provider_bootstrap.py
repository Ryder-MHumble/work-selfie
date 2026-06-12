import subprocess
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import bootstrap_cli
import collect_self
import workselfie_providers as providers


ROOT = Path(__file__).resolve().parents[1]


class ProviderRegistryTest(unittest.TestCase):
    def test_registry_exposes_dws_and_lark(self):
        self.assertEqual(["dws", "lark"], providers.supported_provider_names())
        self.assertEqual("dws", providers.resolve_provider("auto", has_cli=lambda name: name == "dws").name)
        self.assertEqual("lark", providers.resolve_provider("auto", has_cli=lambda name: name == "lark-cli").name)

    def test_lark_provider_documents_agent_split_flow(self):
        lark = providers.get_provider("lark")

        self.assertIn("--no-wait --json", lark.auth_hint)
        self.assertIn("auth qrcode", lark.auth_hint)
        self.assertIn("chat", lark.data_sources)
        self.assertIn("doc", lark.data_sources)

    def test_lark_collection_entrypoint_is_explicitly_reserved(self):
        with self.assertRaisesRegex(NotImplementedError, "lark provider is reserved"):
            collect_self.collect_all(provider="lark", user_id="u1", user_name="Demo")

    def test_docs_explain_provider_bootstrap_paths(self):
        readme = (ROOT / "README.md").read_text()
        skill = (ROOT / "SKILL.md").read_text()

        self.assertIn("dws", readme)
        self.assertIn("lark-cli", readme)
        self.assertIn("scripts/bootstrap_cli.py --provider auto --dry-run", readme)
        self.assertIn("--provider {auto,dws,lark}", skill)
        self.assertIn("lark-shared", skill)


class BootstrapCliTest(unittest.TestCase):
    def test_missing_cli_returns_install_gap_without_running_auth(self):
        result = bootstrap_cli.bootstrap_provider(
            "lark",
            dry_run=False,
            has_cli=lambda _: False,
            run_cmd=Mock(),
        )

        self.assertFalse(result["ready"])
        self.assertEqual("missing_cli", result["status"])
        self.assertIn("lark-cli", result["message"])

    def test_lark_dry_run_shows_config_and_split_auth_plan(self):
        result = bootstrap_cli.bootstrap_provider(
            "lark",
            dry_run=True,
            has_cli=lambda _: True,
            run_cmd=Mock(),
        )

        self.assertTrue(result["ready"])
        self.assertEqual("dry_run", result["status"])
        self.assertTrue(any("lark-cli config init --new" in step for step in result["next_steps"]))
        self.assertTrue(any("--no-wait --json" in step for step in result["next_steps"]))

    def test_auto_respects_lark_binary_environment_override(self):
        with patch.dict("os.environ", {"WORKSELFIE_LARK_BIN": "/tmp/lark-cli"}, clear=False):
            result = bootstrap_cli.bootstrap_provider(
                "auto",
                dry_run=True,
                has_cli=lambda _: False,
                run_cmd=Mock(),
            )

        self.assertEqual("lark", result["provider"])

    def test_existing_dws_runs_auth_status_probe(self):
        completed = subprocess.CompletedProcess(
            args=["dws", "auth", "status", "--format", "json"],
            returncode=0,
            stdout='{"ok": true, "user_id": "secret-user"}',
            stderr="",
        )
        run_cmd = Mock(return_value=completed)

        result = bootstrap_cli.bootstrap_provider(
            "dws",
            dry_run=False,
            has_cli=lambda _: True,
            run_cmd=run_cmd,
        )

        self.assertTrue(result["ready"])
        self.assertEqual("ok", result["status"])
        self.assertNotIn("secret-user", result["message"])
        run_cmd.assert_called_once()


if __name__ == "__main__":
    unittest.main()
