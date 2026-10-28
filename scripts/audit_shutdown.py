#!/usr/bin/env python3
"""Read-only, account-guarded inventory after the recorded Lemonade shutdown."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from project_env import ROOT, infrastructure_environment

EXPECTED_ACCOUNT = '058264461741'
EXPECTED_REGION = 'eu-central-1'
VPC_ID = 'vpc-0de0c1e164a72bee3'
CLUSTER_ID = '2tn4c1sto6l3cj13je431lqenalg0f38'
STATE_BUCKET = 'lemonade-demo-tfstate-' + EXPECTED_ACCOUNT
BASELINE_VOLUMES = {
    'vol-057cd1ff9f52f511b', 'vol-0c13f60032f9b31b4', 'vol-0f5ea86d12625cf0b',
    'vol-06cf0f3f2009999bf', 'vol-03e721221059c427f', 'vol-04f7e5cde123a5fd9',
}


def known_identifiers():
    """Read selected public identifiers, never print or copy full Terraform state."""
    identifiers = {VPC_ID, CLUSTER_ID, *BASELINE_VOLUMES}
    directory = ROOT / 'local/backups/2026-10-28-infrastructure'
    for filename in ('foundation.tfstate', 'rosa.tfstate'):
        data = json.loads((directory / filename).read_text())
        for resource in data.get('resources', []):
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
    return identifiers


def project_match(item, identifiers):
    """Classification is review evidence, never authorization for deletion."""
    text = json.dumps(item, sort_keys=True)
    return any(value in text for value in identifiers) or any(value in text for value in
        ('lemonade-demo', 'lemonade-account', 'lemonade-operator'))


def summarize(items, fields, identifiers):
    records = [{field: item[field] for field in fields if field in item} for item in items]
    matches = [record for item, record in zip(items, records) if project_match(item, identifiers)]
    return {'observed_count': len(items), 'project_matches': matches,
            'unmatched_count': len(items) - len(matches), 'observed': records}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'local/shutdown-audit.json')
    args = parser.parse_args()
    path = args.output.resolve()
    if not path.is_relative_to(ROOT / 'local'):
        raise RuntimeError('Audit output must stay under ignored local/')
    env = infrastructure_environment()
    if env['TF_VAR_expected_account_id'] != EXPECTED_ACCOUNT or env['AWS_REGION'] != EXPECTED_REGION:
        raise RuntimeError('This audit is scoped to the recorded account and region')
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
    if identity['Account'] != EXPECTED_ACCOUNT:
        raise RuntimeError('Live AWS account mismatch')
    identifiers = known_identifiers()
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'account': EXPECTED_ACCOUNT,
              'region': EXPECTED_REGION, 'cluster_id': CLUSTER_ID, 'vpc_id': VPC_ID,
              'read_only': True, 'scope': 'Selected regional services plus global IAM, S3 and Route53; not an account-wide cost audit.',
              'retained_state_bucket': STATE_BUCKET, 'resources': {}}
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
        retained[key] = aws('s3api', operation, '--bucket', STATE_BUCKET)
    objects = aws('s3api','list-objects-v2','--bucket',STATE_BUCKET,'--prefix','checkpoints/','--max-keys','1')
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
