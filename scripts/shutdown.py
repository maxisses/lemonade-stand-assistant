#!/usr/bin/env python3
"""Plan or apply a project-only teardown after a verified private checkpoint."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import checkpoint
from project_env import ROOT, terraform_environment, verify_backend


def run_private(args, env, log):
    with log.open('wb') as output:
        result = subprocess.run(args, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('Command failed; private diagnostics: ' + str(log))


def verify_checkpoint_context(saved, recorded):
    """An older cluster in the same AWS account is not a current data backup."""
    for name in ('aws_account_id', 'region', 'cluster_id'):
        expected = recorded.get(name)
        if not isinstance(expected, str) or not expected or saved.get('context', {}).get(name) != expected:
            raise RuntimeError('Checkpoint account, region or cluster mismatch')


def inspect_plan(stage, path, env, *, recorded=None):
    result = subprocess.run(['terraform', '-chdir=' + str(ROOT / 'infra' / stage), 'show', '-json', str(path)],
                            env=env, capture_output=True)
    if result.returncode:
        raise RuntimeError('Saved teardown plan could not be inspected')
    plan = json.loads(result.stdout)
    for name in ('expected_account_id', 'region'):
        if plan.get('variables', {}).get(name, {}).get('value') != env['TF_VAR_' + name]:
            raise RuntimeError('Teardown plan account or region mismatch')
    resources = []
    cluster_resources = 0
    for change in plan.get('resource_changes', []):
        if change.get('mode') == 'data':
            continue
        actions = change['change']['actions']
        if actions not in (['delete'], ['no-op']):
            raise RuntimeError('Teardown plan contains a non-delete mutation')
        address = change['address']
        valid = ((address.startswith('module.hcp.') or address == 'random_password.admin')
                 if stage == 'rosa' else address.startswith('module.vpc.'))
        if not valid:
            raise RuntimeError('Unexpected resource outside the project teardown scope')
        if change.get('type') == 'rhcs_cluster_rosa_hcp' or '.rhcs_cluster_rosa_hcp.' in address:
            cluster_resources += 1
            if cluster_resources > 1:
                raise RuntimeError('Teardown plan contains multiple ROSA clusters')
            if recorded is None:
                recorded = json.loads((ROOT / 'local/context.json').read_text())
            if (recorded.get('aws_account_id') != env['TF_VAR_expected_account_id'] or
                    recorded.get('region') != env['TF_VAR_region'] or
                    not isinstance(recorded.get('cluster_id'), str) or not recorded['cluster_id']):
                raise RuntimeError('Current cluster context differs from teardown environment')
            expected = {'id': recorded['cluster_id'],
                        'aws_account_id': recorded['aws_account_id'],
                        'cloud_region': recorded['region'],
                        'name': recorded.get('cluster_name', 'lemonade-demo')}
            before = change['change'].get('before')
            if not isinstance(before, dict) or any(before.get(key) != value for key, value in expected.items()):
                raise RuntimeError('Teardown plan ROSA identity differs from the current project cluster')
        if actions == ['delete']:
            resources.append(address)
    return resources


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('rosa', 'foundation'))
    parser.add_argument('action', choices=('plan', 'apply'))
    parser.add_argument('--checkpoint', required=True, type=Path)
    args = parser.parse_args()
    folder = args.checkpoint.resolve()
    if not folder.is_relative_to(ROOT / 'local'):
        raise RuntimeError('Use a private checkpoint under local/')
    saved = checkpoint.verify(folder)
    recorded = checkpoint.context()
    verify_checkpoint_context(saved, recorded)
    # Peer pods and image-build permissions must be removed while the cluster still exists.
    sandbox_env=terraform_environment('sandbox')
    if (Path(sandbox_env['TF_DATA_DIR'])/'terraform.tfstate').exists():
        verify_backend('sandbox',sandbox_env)
        state=subprocess.run(['terraform','-chdir='+str(ROOT/'infra/sandbox'),'state','pull'],env=sandbox_env,capture_output=True,text=True)
        if state.returncode or any(r.get('mode')=='managed' and r.get('instances') for r in json.loads(state.stdout).get('resources',[])):
            raise RuntimeError('Sandbox infrastructure remains. Complete sandbox_platform.py quiesce/runtime/image/IAM cleanup before ROSA teardown.')
    env = terraform_environment(args.stage)
    verify_backend(args.stage, env)
    # Foundation may only be removed after the ROSA stage is genuinely empty.
    if args.stage == 'foundation':
        rosa_env = terraform_environment('rosa'); verify_backend('rosa', rosa_env)
        result = subprocess.run(['terraform', '-chdir=' + str(ROOT / 'infra/rosa'), 'state', 'pull'],
                                env=rosa_env, capture_output=True, text=True)
        if result.returncode or any(resource.get('mode') == 'managed' and resource.get('instances')
                                    for resource in json.loads(result.stdout).get('resources', [])):
            raise RuntimeError('ROSA state is not empty; finish cluster deletion first')
    path = folder / (args.stage + '-destroy.tfplan')
    log = folder / (args.stage + '-' + args.action + '.log')
    if args.action == 'plan':
        run_private([sys.executable, str(ROOT / 'scripts/tf.py'), args.stage, 'plan', '-destroy',
                     '-out=' + str(path), '-no-color', '-input=false'], env, log)
    resources = inspect_plan(args.stage, path, env, recorded=recorded)
    print('Verified delete-only plan:', args.stage, len(resources), 'managed resources', flush=True)
    if args.action == 'apply':
        print('Applying saved teardown plan; progress is recorded privately in ' + str(log), flush=True)
        run_private([sys.executable, str(ROOT / 'scripts/tf.py'), args.stage, 'apply', '-no-color', '-input=false', str(path)], env, log)
        print('Teardown stage completed: ' + args.stage)
    else:
        for address in resources:
            print('  delete ' + address)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        sys.exit(str(error) if isinstance(error, RuntimeError) else 'Shutdown command failed; diagnostic details withheld.')
