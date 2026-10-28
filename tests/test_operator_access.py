"""Session bootstrap safety checks using fake cluster responses and secret bytes."""
import base64
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import operator_access_secrets as bootstrap


class OperatorAccessTests(unittest.TestCase):
    def setUp(self):
        self.context = {"cluster_api_url": "https://api.demo.example:443"}
        self.context_patch = patch.object(bootstrap, "load_context", return_value=self.context)
        self.context_patch.start()
        self.addCleanup(self.context_patch.stop)

    def test_wrong_cluster_never_reads_or_creates_secrets(self):
        with patch.object(bootstrap, "command", return_value="https://api.other.example") as command, \
                patch.object(bootstrap.subprocess, "run") as run, \
                self.assertRaises(bootstrap.AccessError):
            bootstrap.main()
        self.assertEqual(command.call_count, 1)
        run.assert_not_called()

    def test_existing_secrets_are_not_rotated(self):
        with patch.object(bootstrap, "command", side_effect=[self.context["cluster_api_url"], "secret/chat", "secret/dashboard"]), \
                patch.object(bootstrap.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            bootstrap.main()
        run.assert_not_called()

    def test_secret_values_only_reach_oc_stdin(self):
        fake = bytes([251]) * 32  # Distinguish URL-safe Base64 from standard Base64.
        output = io.StringIO()
        with patch.object(bootstrap, "command", side_effect=[self.context["cluster_api_url"], "", ""]), \
                patch.object(bootstrap.secrets, "token_bytes", return_value=fake), \
                patch.object(bootstrap.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run, \
                contextlib.redirect_stdout(output):
            bootstrap.main()
        encoded = base64.urlsafe_b64encode(fake).decode()
        self.assertNotIn(encoded, output.getvalue())
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertNotIn(encoded, str(call.args))
            manifest = json.loads(call.kwargs["input"])
            self.assertEqual(manifest["stringData"]["cookie-secret"], encoded)
            self.assertNotIn("+", encoded)
            self.assertNotIn("/", encoded)
            self.assertEqual(manifest["metadata"]["namespace"], "lemonade-demo")


if __name__ == "__main__":
    unittest.main()
