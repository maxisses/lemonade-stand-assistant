#!/usr/bin/env python3
"""Read-only, account-guarded inventory after the recorded Lemonade shutdown."""
import argparse
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import subprocess
import sys

from project_env import ROOT, infrastructure_environment

def private_path(path, root=ROOT):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to((root / 'local').resolve()):
        raise RuntimeError('Audit inputs and output must stay under ignored local/')
    return resolved


def managed_attributes(state, resource_type):
    return [instance.get('attributes', {})
            for resource in state.get('resources', [])
            if resource.get('mode') == 'managed' and resource.get('type') == resource_type
            for instance in resource.get('instances', [])]


def load_scope(infrastructure_backup, baseline_inventory, root=ROOT):
    """Bind saved identifiers to the current project before reading cloud inventory."""
    directory = private_path(infrastructure_backup, root)
    baseline_path = private_path(baseline_inventory, root)
    context = json.loads((root / 'local/context.json').read_text())
    account, region, cluster_id = (context.get(key) for key in
                                  ('aws_account_id', 'region', 'cluster_id'))
    if not isinstance(account, str) or not re.fullmatch(r'[0-9]{12}', account):
        raise RuntimeError('Invalid project account in local context')
    if not isinstance(region, str) or not re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-[0-9]+', region):
        raise RuntimeError('Invalid project region in local context')
    if not isinstance(cluster_id, str) or not re.fullmatch(r'[a-z0-9]{20,64}', cluster_id):
        raise RuntimeError('Invalid project cluster in local context')
    foundation = json.loads((directory / 'foundation.tfstate').read_text())
    rosa = json.loads((directory / 'rosa.tfstate').read_text())
    vpcs = managed_attributes(foundation, 'aws_vpc')
    clusters = managed_attributes(rosa, 'rhcs_cluster_rosa_hcp')
    if len(vpcs) != 1 or len(clusters) != 1:
        raise RuntimeError('Use pre-deletion state with exactly one VPC and one ROSA cluster')
    vpc, cluster = vpcs[0], clusters[0]
    vpc_id = vpc.get('id')
    if not isinstance(vpc_id, str) or not re.fullmatch(r'vpc-[0-9a-f]+', vpc_id):
        raise RuntimeError('Invalid VPC identifier in infrastructure backup')
    if (vpc.get('owner_id') != account or vpc.get('region') != region or
            vpc.get('arn') != f'arn:aws:ec2:{region}:{account}:vpc/{vpc_id}'):
        raise RuntimeError('Infrastructure VPC account or region differs from project context')
    if (cluster.get('id') != cluster_id or cluster.get('aws_account_id') != account or
            cluster.get('cloud_region') != region or cluster.get('name') != 'lemonade-demo'):
        raise RuntimeError('Infrastructure cluster differs from the current Lemonade context')
    subnet_ids = {item.get('id') for item in managed_attributes(foundation, 'aws_subnet')
                  if item.get('vpc_id') == vpc_id}
    if not cluster.get('aws_subnet_ids') or not set(cluster['aws_subnet_ids']) <= subnet_ids:
        raise RuntimeError('Saved ROSA subnets do not belong to the saved project VPC')
    baseline = json.loads(baseline_path.read_text())
    expected = {'aws_account_id': account, 'region': region,
                'cluster_id': cluster_id, 'vpc_id': vpc_id}
    if any(baseline.get(key) != value for key, value in expected.items()):
        raise RuntimeError('Pre-deletion inventory differs from the current infrastructure scope')
    identifiers = {vpc_id, cluster_id}
    for key, pattern in (('volume_ids', r'vol-[0-9a-f]+'), ('instance_ids', r'i-[0-9a-f]+')):
        values = baseline.get(key)
        if (not isinstance(values, list) or any(not isinstance(value, str) or
                not re.fullmatch(pattern, value) for value in values)):
            raise RuntimeError('Pre-deletion inventory requires valid volume and instance ID lists')
        identifiers.update(values)
    for state in (foundation, rosa):
        for resource in state.get('resources', []):
            resource_type = resource.get('type', '')
            if resource.get('mode') != 'managed' or not (
                    resource_type.startswith('aws_') or resource_type == 'rhcs_cluster_rosa_hcp'):
                continue
            for instance in resource.get('instances', []):
                values = instance.get('attributes', {})
                for field in ('id', 'arn', 'name', 'external_id', 'url', 'allocation_id'):
                    value = values.get(field)
                    if isinstance(value, str) and value:
                        identifiers.add(value)
    return {**expected, 'identifiers': identifiers,
            'state_bucket': 'lemonade-demo-tfstate-' + account}


def project_match(item, identifiers):
    """Classification is review evidence, never authorization for deletion."""
    text = json.dumps(item, sort_keys=True)
    return any(value in text for value in identifiers) or any(value in text for value in
        ('lemonade-demo',))


def summarize(items, fields, identifiers):
    records = [{field: item[field] for field in fields if field in item} for item in items]
    matches = [record for item, record in zip(items, records) if project_match(item, identifiers)]
    return {'observed_count': len(items), 'project_matches': matches,
            'unmatched_count': len(items) - len(matches), 'observed': records}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--infrastructure-backup', required=True, type=Path,
                        help='Private directory containing current pre-deletion foundation.tfstate and rosa.tfstate')
    parser.add_argument('--baseline-inventory', required=True, type=Path,
                        help='Private pre-deletion scope with volume_ids and instance_ids')
    parser.add_argument('--output', type=Path, default=ROOT / 'local/shutdown-audit.json')
    args = parser.parse_args()
    path = private_path(args.output)
    scope = load_scope(args.infrastructure_backup, args.baseline_inventory)
    env = infrastructure_environment()
    if env['TF_VAR_expected_account_id'] != scope['aws_account_id'] or env['AWS_REGION'] != scope['region']:
        raise RuntimeError('Audit scope differs from the configured account and region')
    errors = []

    def aws(*args, required=False):
        result = subprocess.run(['aws', *args, '--output', 'json'], env=env,
                                capture_output=True, text=True, timeout=90)
        if result.returncode:
            label = ' '.join(args[:2])
            if required:
                raise RuntimeError('Required read-only query failed: ' + label)
            errors.append(label)
            return None
        return json.loads(result.stdout) if result.stdout.strip() else {}

    identity = aws('sts', 'get-caller-identity', required=True)
    if identity['Account'] != scope['aws_account_id']:
        raise RuntimeError('Live AWS account mismatch')
    identifiers = scope['identifiers']
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'account': scope['aws_account_id'],
              'region': scope['region'], 'cluster_id': scope['cluster_id'], 'vpc_id': scope['vpc_id'],
              'infrastructure_backup': str(args.infrastructure_backup.resolve()),
              'baseline_inventory': str(args.baseline_inventory.resolve()),
              'read_only': True, 'scope': 'Selected regional services plus global IAM, S3 and Route53; not an account-wide cost audit.',
              'retained_state_bucket': scope['state_bucket'], 'resources': {}}
    queries = [
        ('instances', ('ec2','describe-instances'), 'Reservations', ('InstanceId','State','InstanceType','VpcId','Tags')),
        ('vpcs', ('ec2','describe-vpcs'), 'Vpcs', ('VpcId','State','Tags')),
        ('nat_gateways', ('ec2','describe-nat-gateways'), 'NatGateways', ('NatGatewayId','State','VpcId','NatGatewayAddresses','Tags')),
        ('elastic_ips', ('ec2','describe-addresses'), 'Addresses', ('AllocationId','AssociationId','NetworkInterfaceId','PublicIp','Tags')),
        ('volumes', ('ec2','describe-volumes'), 'Volumes', ('VolumeId','State','Size','Attachments','Tags')),
        ('snapshots', ('ec2','describe-snapshots','--owner-ids','self'), 'Snapshots', ('SnapshotId','State','VolumeId','VolumeSize','Tags')),
        ('network_interfaces', ('ec2','describe-network-interfaces'), 'NetworkInterfaces', ('NetworkInterfaceId','Status','VpcId','Description','TagSet')),
        ('load_balancers_v2', ('elbv2','describe-load-balancers'), 'LoadBalancers', ('LoadBalancerArn','LoadBalancerName','VpcId','Type','State')),
        ('load_balancers_classic', ('elb','describe-load-balancers'), 'LoadBalancerDescriptions', ('LoadBalancerName','VPCId')),
        ('security_groups', ('ec2','describe-security-groups'), 'SecurityGroups', ('GroupId','GroupName','VpcId','Tags')),
        ('vpc_endpoints', ('ec2','describe-vpc-endpoints'), 'VpcEndpoints', ('VpcEndpointId','VpcId','State','Tags')),
        ('auto_scaling_groups', ('autoscaling','describe-auto-scaling-groups'), 'AutoScalingGroups', ('AutoScalingGroupName','DesiredCapacity','Instances','VPCZoneIdentifier','Tags')),
        ('log_groups', ('logs','describe-log-groups'), 'logGroups', ('logGroupName','storedBytes','retentionInDays','arn')),
        ('iam_roles', ('iam','list-roles'), 'Roles', ('RoleName','Arn')),
        ('iam_policies', ('iam','list-policies','--scope','Local'), 'Policies', ('PolicyName','Arn','AttachmentCount')),
        ('oidc_providers', ('iam','list-open-id-connect-providers'), 'OpenIDConnectProviderList', ('Arn',)),
        ('s3_buckets', ('s3api','list-buckets'), 'Buckets', ('Name',)),
        ('hosted_zones', ('route53','list-hosted-zones'), 'HostedZones', ('Id','Name','Config')),
    ]
    for name, args, key, fields in queries:
        data = aws(*args)
        if data is None:
            report['resources'][name] = {'query_failed': True}
            continue
        items = data.get(key, [])
        if name == 'instances':
            items = [item for reservation in items for item in reservation.get('Instances', [])]
        report['resources'][name] = summarize(items, fields, identifiers)
        summary = report['resources'][name]
        print(name + ': ' + str(summary['observed_count']) + ' observed, '
              + str(len(summary['project_matches'])) + ' project candidates', flush=True)
    # Check state durability and ensure the declined checkpoint prefix is empty.
    retained = {}
    for key, operation in (('versioning','get-bucket-versioning'),
                           ('encryption','get-bucket-encryption'),
                           ('public_access','get-public-access-block')):
        retained[key] = aws('s3api', operation, '--bucket', scope['state_bucket'])
    objects = aws('s3api','list-objects-v2','--bucket',scope['state_bucket'],'--prefix','checkpoints/','--max-keys','1')
    retained['checkpoint_objects_observed'] = objects.get('KeyCount', 0) if objects is not None else None
    report['retained_bucket_checks'] = retained
    report['incomplete_queries'] = errors
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with path.open('w') as output:
        json.dump(report, output, indent=2)
        output.write('\n')
    path.chmod(0o600)
    print('Private audit saved: ' + str(path))
    if errors:
        print('Some queries failed; missing results are not evidence of absence.')
        return 2
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        sys.exit(str(error) if isinstance(error, RuntimeError) else 'Read-only shutdown audit failed; diagnostic details withheld.')
