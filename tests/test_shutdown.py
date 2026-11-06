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
        self.context = {'aws_account_id':'123456789012', 'region':'eu-central-1', 'cluster_id':'current-cluster'}
        self.plan = {'variables': {'expected_account_id':{'value':'123456789012'}, 'region':{'value':'eu-central-1'}},
                     'resource_changes':[{'mode':'managed','address':'module.hcp.aws_iam_role.example','change':{'actions':['delete']}}]}

    def inspect(self, stage='rosa'):
        with patch.object(shutdown.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(self.plan))):
            return shutdown.inspect_plan(stage, Path('/private/plan.tfplan'), self.env, recorded=self.context)

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

    def add_cluster(self, actions=None):
        cluster = {'mode': 'managed', 'type': 'rhcs_cluster_rosa_hcp',
                   'address': 'module.hcp.rhcs_cluster_rosa_hcp.rosa_cluster',
                   'change': {'actions': actions or ['delete'], 'before': {
                       'id': 'current-cluster', 'aws_account_id': '123456789012',
                       'cloud_region': 'eu-central-1', 'name': 'lemonade-demo'}}}
        self.plan['resource_changes'].append(cluster)
        return cluster

    def test_matching_cluster_delete(self):
        self.add_cluster()
        self.assertIn('module.hcp.rhcs_cluster_rosa_hcp.rosa_cluster', self.inspect())

    def test_rejects_cluster_identity_drift_even_with_matching_plan_variables(self):
        cluster = self.add_cluster()
        before = cluster['change']['before']
        for field, wrong in [('id', 'previous-cluster'), ('aws_account_id', '999999999999'),
                             ('cloud_region', 'us-east-1'), ('name', 'another-demo')]:
            original = before[field]
            with self.subTest(field=field):
                before[field] = wrong
                with self.assertRaisesRegex(RuntimeError, 'ROSA identity'):
                    self.inspect()
                before[field] = original

    def test_rejects_cluster_without_before_identity(self):
        cluster = self.add_cluster()
        del cluster['change']['before']
        with self.assertRaisesRegex(RuntimeError, 'ROSA identity'):
            self.inspect()

    def test_rejects_multiple_cluster_resources(self):
        self.add_cluster()
        self.add_cluster()
        with self.assertRaisesRegex(RuntimeError, 'multiple ROSA clusters'):
            self.inspect()

    def test_no_op_cluster_is_checked_but_not_returned_for_deletion(self):
        cluster = self.add_cluster(['no-op'])
        self.assertEqual(self.inspect(), ['module.hcp.aws_iam_role.example'])
        cluster['change']['before']['id'] = 'previous-cluster'
        with self.assertRaisesRegex(RuntimeError, 'ROSA identity'):
            self.inspect()

    def test_empty_rosa_recovery_and_foundation_remain_supported(self):
        self.plan['resource_changes'] = []
        self.assertEqual(self.inspect(), [])
        self.plan['resource_changes'] = [{'mode':'managed', 'address':'module.vpc.aws_vpc.this[0]',
                                         'change':{'actions':['delete']}}]
        self.assertEqual(self.inspect('foundation'), ['module.vpc.aws_vpc.this[0]'])

    def test_current_context_must_match_environment(self):
        self.add_cluster()
        self.context['aws_account_id'] = '999999999999'
        with self.assertRaisesRegex(RuntimeError, 'context differs'):
            self.inspect()

    def test_checkpoint_must_belong_to_current_cluster(self):
        shutdown.verify_checkpoint_context({'context':dict(self.context)}, self.context)
        for field in ('aws_account_id', 'region', 'cluster_id'):
            stale = dict(self.context)
            stale[field] = 'previous-value'
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, 'Checkpoint'):
                shutdown.verify_checkpoint_context({'context':stale}, self.context)
        with self.assertRaisesRegex(RuntimeError, 'Checkpoint'):
            shutdown.verify_checkpoint_context({'context':{'aws_account_id':'123456789012', 'region':'eu-central-1'}},
                                               {'aws_account_id':'123456789012', 'region':'eu-central-1'})


if __name__ == '__main__':
    unittest.main()
