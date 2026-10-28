"""Access helper checks with fake credentials; no cloud or clipboard operations."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import show_access as access

CONTEXT = {
    "aws_account_id": "123456789012", "region": "eu-central-1", "cluster_id": "test-cluster",
    "cluster_api_url": "https://api.demo.example:443", "console_url": "https://console.demo.example",
}
ENV = {"TF_VAR_expected_account_id": CONTEXT["aws_account_id"], "TF_VAR_region": CONTEXT["region"]}


class AccessTests(unittest.TestCase):
    def test_offline_report_does_not_read_cloud_or_credentials(self):
        with patch.object(access, "command") as command, patch.object(access, "terraform_environment") as terraform:
            report = access.build_report(CONTEXT, offline=True)
        command.assert_not_called()
        terraform.assert_not_called()
        self.assertIsNone(next(s["url"] for s in report["services"] if s["name"] == "OpenShift AI"))

    def test_other_cluster_is_not_queried(self):
        with patch.object(access, "command", return_value="https://api.other.example") as command:
            report = access.build_report(CONTEXT)
        self.assertEqual(command.call_count, 1)
        self.assertIn("another cluster", report["discovery"])

    def test_live_urls_use_allowlisted_services_and_exclude_guardrails(self):
        routes = "openshift-ingress\tdata-science-gateway\tai.demo.example\t\treencrypt\nlemonade-demo\tguardrails-orchestrator\tguardrails.demo.example\t\treencrypt"
        with patch.object(access, "command", side_effect=[CONTEXT["cluster_api_url"], routes]):
            report = access.build_report(CONTEXT)
        self.assertIn("https://ai.demo.example", json.dumps(report))
        self.assertNotIn("guardrails.demo.example", json.dumps(report))

    def test_credential_bearing_or_unsafe_urls_are_rejected(self):
        for url in ["https://user:fake-password@example.com", "https://example.com?token=fake-token", "https://example.com/#fake-token", "http://example.com", "https://example.com/\ninjected", None]:
            with self.subTest(url=url), self.assertRaises(access.AccessError):
                access.public_url(url)

    def test_command_failure_does_not_disclose_output(self):
        failed = subprocess.CompletedProcess(["terraform"], 1, "FAKE_SECRET", "FAKE_SECRET")
        with patch.object(access.subprocess, "run", return_value=failed):
            with self.assertRaises(access.AccessError) as error:
                access.command(["terraform"])
        self.assertNotIn("FAKE_SECRET", str(error.exception))

    def copy_context(self, responses):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(access.sys, "platform", "darwin"))
        stack.enter_context(patch.object(access.shutil, "which", return_value="/usr/bin/pbcopy"))
        stack.enter_context(patch.object(access, "terraform_environment", return_value=ENV))
        stack.enter_context(patch.object(access, "verify_backend"))
        command = stack.enter_context(patch.object(access, "command", side_effect=responses))
        return stack, command

    def test_wrong_aws_account_never_reads_password_or_changes_clipboard(self):
        stack, command = self.copy_context([json.dumps({"Account": "999999999999"})])
        with stack, self.assertRaises(access.AccessError):
            access.copy_admin_password(CONTEXT)
        self.assertEqual(command.call_count, 1)

    def test_wrong_state_cluster_never_reads_password(self):
        stack, command = self.copy_context([json.dumps({"Account": CONTEXT["aws_account_id"]}), "https://api.other.example"])
        with stack, self.assertRaises(access.AccessError):
            access.copy_admin_password(CONTEXT)
        self.assertEqual(command.call_count, 2)

    def test_password_only_reaches_clipboard_stdin(self):
        fake = "FAKE_PASSWORD_FOR_TEST_ONLY"
        stack, command = self.copy_context([json.dumps({"Account": CONTEXT["aws_account_id"]}), CONTEXT["cluster_api_url"], fake, ""])
        output = io.StringIO()
        with stack, contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            access.copy_admin_password(CONTEXT)
        self.assertNotIn(fake, output.getvalue())
        self.assertEqual(command.call_args.args, (["/usr/bin/pbcopy"],))
        self.assertEqual(command.call_args.kwargs, {"input": fake})
        self.assertTrue(all(fake not in str(call.args) for call in command.call_args_list))


if __name__ == "__main__":
    unittest.main()
