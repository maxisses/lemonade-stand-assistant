"""Reject teardown plans outside the intended account and resource scope."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import shutdown


class ShutdownPlanTests(unittest.TestCase):
    def setUp(self):
        self.env = {'TF_VAR_expected_account_id':'123456789012', 'TF_VAR_region':'eu-central-1'}
        self.plan = {'variables': {'expected_account_id':{'value':'123456789012'}, 'region':{'value':'eu-central-1'}},
                     'resource_changes':[{'mode':'managed','address':'module.hcp.aws_iam_role.example','change':{'actions':['delete']}}]}

    def inspect(self, stage='rosa'):
        with patch.object(shutdown.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(self.plan))):
            return shutdown.inspect_plan(stage, Path('/private/plan.tfplan'), self.env)

    def test_expected_deletion(self):
        self.assertEqual(self.inspect(), ['module.hcp.aws_iam_role.example'])

    def test_wrong_account(self):
        self.plan['variables']['expected_account_id']['value']='999999999999'
        with self.assertRaisesRegex(RuntimeError, 'account or region'):
            self.inspect()

    def test_create_replace_and_update_refused(self):
        for actions in (['create'], ['update'], ['delete','create']):
            with self.subTest(actions=actions):
                self.plan['resource_changes'][0]['change']['actions']=actions
                with self.assertRaisesRegex(RuntimeError, 'non-delete'):
                    self.inspect()

    def test_wrong_module_and_stage_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'outside'):
            self.inspect('foundation')
        self.plan['resource_changes'][0]['address']='aws_s3_bucket.state'
        with self.assertRaisesRegex(RuntimeError, 'outside'):
            self.inspect()


if __name__ == '__main__':
    unittest.main()
