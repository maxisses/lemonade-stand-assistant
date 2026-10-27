"""Offline coverage for preventing state and plan reuse across AWS accounts."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from project_env import backend_configuration, verify_backend
from tf import verify_plan


class AccountGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.env = {
            "TF_VAR_expected_account_id": "111111111111",
            "TF_VAR_region": "eu-central-1",
            "TF_DATA_DIR": self.temporary.name,
        }

    def metadata(self, config):
        Path(self.temporary.name, "terraform.tfstate").write_text(json.dumps({
            "backend": {"type": "s3", "config": config},
        }))

    def test_rejects_backend_for_other_account(self):
        config = backend_configuration("rosa", self.env)
        config["bucket"] = "lemonade-demo-tfstate-222222222222"
        self.metadata(config)
        with self.assertRaisesRegex(RuntimeError, "backend does not match"):
            verify_backend("rosa", self.env)

    def test_rejects_backend_for_other_stage(self):
        self.metadata(backend_configuration("foundation", self.env))
        with self.assertRaisesRegex(RuntimeError, "backend does not match"):
            verify_backend("rosa", self.env)

    def test_accepts_matching_backend(self):
        self.metadata(backend_configuration("rosa", self.env))
        verify_backend("rosa", self.env)

    def test_rejects_saved_plan_for_other_account_or_region(self):
        for account, region in (("222222222222", "eu-central-1"), ("111111111111", "us-east-1")):
            with self.subTest(account=account, region=region), patch("tf.subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stdout = json.dumps({"variables": {
                    "expected_account_id": {"value": account}, "region": {"value": region},
                }})
                with self.assertRaisesRegex(RuntimeError, "another account or region"):
                    verify_plan(Path("example.tfplan"), self.env, self.temporary.name)


if __name__ == "__main__":
    unittest.main()
