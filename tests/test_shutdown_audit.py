"""Offline scope checks for the read-only shutdown inventory."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_shutdown


class ShutdownAuditScopeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.backup = self.root / 'local' / 'backup'
        self.backup.mkdir(parents=True)
        self.context = {'aws_account_id': '123456789012', 'region': 'eu-central-1',
                        'cluster_id': 'abcdefghijklmnopqrstuvwxyz12'}
        self.vpc_id = 'vpc-0123456789abcdef0'
        self.baseline = {**self.context, 'vpc_id': self.vpc_id,
                         'volume_ids': ['vol-0123456789abcdef0'],
                         'instance_ids': ['i-0123456789abcdef0']}
        self.foundation = {'resources': [
            self.resource('aws_vpc', {'id': self.vpc_id, 'owner_id': self.context['aws_account_id'],
                'region': self.context['region'],
                'arn': f"arn:aws:ec2:eu-central-1:123456789012:vpc/{self.vpc_id}"}),
            self.resource('aws_subnet', {'id': 'subnet-0123', 'vpc_id': self.vpc_id})]}
        self.rosa = {'resources': [self.resource('rhcs_cluster_rosa_hcp', {
            'id': self.context['cluster_id'], 'aws_account_id': self.context['aws_account_id'],
            'cloud_region': self.context['region'], 'name': 'lemonade-demo',
            'aws_subnet_ids': ['subnet-0123'],
            'admin_credentials': [{'password': 'FAKE-PRIVATE-VALUE'}]})]}

    @staticmethod
    def resource(kind, attributes):
        return {'mode': 'managed', 'type': kind, 'instances': [{'attributes': attributes}]}

    def load(self):
        for filename, contents in [('foundation.tfstate', self.foundation),
                                   ('rosa.tfstate', self.rosa),
                                   ('baseline-inventory.json', self.baseline)]:
            (self.backup / filename).write_text(json.dumps(contents))
        (self.root / 'local/context.json').write_text(json.dumps(self.context))
        return audit_shutdown.load_scope(self.backup, self.backup / 'baseline-inventory.json', self.root)

    def test_current_scope_includes_detached_volume_ids_without_copying_credentials(self):
        scope = self.load()
        self.assertEqual(scope['cluster_id'], self.context['cluster_id'])
        self.assertIn(self.baseline['volume_ids'][0], scope['identifiers'])
        self.assertNotIn('FAKE-PRIVATE-VALUE', str(scope))
        self.assertTrue(audit_shutdown.project_match({'VolumeId': self.baseline['volume_ids'][0]}, scope['identifiers']))

    def test_rejects_foreign_account_and_region(self):
        vpc = self.foundation['resources'][0]['instances'][0]['attributes']
        for key, wrong in [('owner_id', '000000000000'), ('region', 'us-east-1')]:
            original = vpc[key]
            vpc[key] = wrong
            with self.assertRaisesRegex(RuntimeError, 'VPC account or region'):
                self.load()
            vpc[key] = original

    def test_rejects_previous_cluster_state(self):
        self.rosa['resources'][0]['instances'][0]['attributes']['id'] = 'oldclusterabcdefghijklmnopqr'
        with self.assertRaisesRegex(RuntimeError, 'cluster differs'):
            self.load()

    def test_rejects_foreign_network(self):
        self.rosa['resources'][0]['instances'][0]['attributes']['aws_subnet_ids'] = ['subnet-deadbeef']
        with self.assertRaisesRegex(RuntimeError, 'subnets'):
            self.load()

    def test_rejects_old_baseline(self):
        self.baseline['vpc_id'] = 'vpc-deadbeef'
        with self.assertRaisesRegex(RuntimeError, 'Pre-deletion inventory differs'):
            self.load()

    def test_rejects_missing_or_malformed_volume_list(self):
        self.baseline.pop('volume_ids')
        with self.assertRaisesRegex(RuntimeError, 'volume and instance'):
            self.load()
        self.baseline['volume_ids'] = ['arn:aws:ec2:foreign']
        with self.assertRaisesRegex(RuntimeError, 'volume and instance'):
            self.load()

    def test_rejects_empty_post_deletion_state(self):
        self.rosa['resources'] = []
        with self.assertRaisesRegex(RuntimeError, 'pre-deletion state'):
            self.load()

    def test_rejects_inputs_outside_private_directory(self):
        with self.assertRaisesRegex(RuntimeError, 'ignored local'):
            audit_shutdown.private_path(self.root / 'public' / 'report.json', self.root)

    def test_shared_account_roles_are_not_matched_by_name_alone(self):
        scope = self.load()
        self.assertFalse(audit_shutdown.project_match({'RoleName': 'lemonade-account-Worker-Role'}, scope['identifiers']))
        self.assertTrue(audit_shutdown.project_match({'Name': 'lemonade-demo-tfstate-123456789012'}, scope['identifiers']))


if __name__ == '__main__':
    unittest.main()
