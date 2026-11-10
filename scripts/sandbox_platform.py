#!/usr/bin/env python3
"""Account-scoped CPU peer-pod bootstrap. No inference or workload execution."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from project_env import ROOT, infrastructure_environment, terraform_environment
from rebuild import context, get, run, RebuildError

FOLDER = ROOT / 'local/sandbox'
OSC_NS = 'openshift-sandboxed-containers-operator'
PINS = [('agent-sandbox-system','agent-sandbox-operator','preview-0.9','agent-sandbox-operator.v0.9.0'),
        (OSC_NS,'sandboxed-containers-operator','stable','sandboxed-containers-operator.v1.13.1')]


def aws(args):
    return json.loads(run(['aws',*args,'--output','json'],env=infrastructure_environment()) or '{}')


def saved(c):
    result=json.loads((FOLDER/'context.json').read_text())
    if any(result[k]!=c[k] for k in ('cluster_id','aws_account_id','region')):
        raise RebuildError('Sandbox context belongs to a different cluster.')
    return result


def apply(oc,obj):
    run(oc+['apply','-f','-'],payload=json.dumps(obj))


def discover(c,oc):
    nodes=get(oc,'nodes')['items']
    instance_ids=[n['spec']['providerID'].rsplit('/',1)[-1] for n in nodes]
    instances=[i for r in aws(['ec2','describe-instances','--instance-ids',*instance_ids])['Reservations'] for i in r['Instances']]
    if len({i['VpcId'] for i in instances})!=1:raise RebuildError('Ambiguous project worker VPC.')
    # Only select a common worker group containing the existing tunnel self rule.
    groups=set.intersection(*[{s['GroupId'] for s in i['SecurityGroups']} for i in instances])
    selected=[]
    for group in aws(['ec2','describe-security-groups','--group-ids',*sorted(groups)])['SecurityGroups']:
        if any(p.get('IpProtocol')=='tcp' and p.get('FromPort',65536)<=9000<=p.get('ToPort',-1)
               and any(g['GroupId']==group['GroupId'] for g in p.get('UserIdGroupPairs',[])) for p in group['IpPermissions']):
            selected.append(group['GroupId'])
    if len(selected)!=1:raise RebuildError('Cannot identify the project worker security group unambiguously.')
    previous=FOLDER/'context.json'
    if previous.exists():
        old=saved(c)
    else:
        probe=subprocess.run(['aws','iam','get-role','--role-name','vmimport'],env=infrastructure_environment(),capture_output=True,text=True)
        if probe.returncode==0 or 'NoSuchEntity' not in probe.stderr:
            raise RebuildError('A pre-existing vmimport role or IAM lookup failure requires review; no changes made.')
        old={}
    issuer=get(oc,'authentication.config.openshift.io','cluster')['spec']['serviceAccountIssuer']
    result={**{k:c[k] for k in ('cluster_id','aws_account_id','region')},'oidc_issuer':issuer,
            'vpc_id':instances[0]['VpcId'],'subnet_id':instances[0]['SubnetId'],
            'worker_security_group':selected[0], 'node_name':nodes[0]['metadata']['name'],
            'vmimport_absent_before_install':old.get('vmimport_absent_before_install',True)}
    FOLDER.mkdir(mode=0o700,exist_ok=True)
    (FOLDER/'context.json').write_text(json.dumps(result,indent=2))
    variables={k:result[k] for k in ('cluster_id','oidc_issuer','subnet_id','worker_security_group')}
    (FOLDER/'platform.tfvars.json').write_text(json.dumps(variables,indent=2))
    print('Saved verified sandbox context; CPU t3.medium only, one selected worker, at most two peer-pod slots.')
    filters=[{'Type':'TERM_MATCH','Field':k,'Value':v} for k,v in {'instanceType':'t3.medium','location':'EU (Frankfurt)','operatingSystem':'Linux','tenancy':'Shared','preInstalledSw':'NA','capacitystatus':'Used'}.items()]
    prices=aws(['pricing','get-products','--region','us-east-1','--service-code','AmazonEC2','--filters',json.dumps(filters),'--max-results','10'])
    amounts=[]
    for item in prices.get('PriceList',[]):
        for term in json.loads(item)['terms'].get('OnDemand',{}).values():
            for dim in term['priceDimensions'].values():
                if dim['unit']=='Hrs':amounts.append(dim['pricePerUnit']['USD'])
    print('AWS Linux t3.medium on-demand USD/hour:',sorted(set(amounts)), '(storage/traffic/CPU credits extra)')


def terraform(action,c):
    cfg=saved(c)
    common=[sys.executable,str(ROOT/'scripts/tf.py'),'sandbox']
    if action=='init':args=common+['init','-input=false']
    elif action=='plan':args=common+['plan','-input=false','-no-color','-var-file='+str(FOLDER/'platform.tfvars.json'),'-out='+str(FOLDER/'platform.tfplan')]
    else:
        info=json.loads(run(['terraform','-chdir='+str(ROOT/'infra/sandbox'),'show','-json',str(FOLDER/'platform.tfplan')],env=terraform_environment('sandbox')))
        if info['variables']['cluster_id']['value']!=cfg['cluster_id']:raise RebuildError('Saved sandbox plan cluster mismatch.')
        if any(x['change']['actions'] not in (['create'],['update'],['no-op'],['delete']) for x in info.get('resource_changes',[]) if x.get('mode')!='data'):
            raise RebuildError('Unexpected replacement in sandbox plan.')
        args=common+['apply','-input=false','-no-color',str(FOLDER/'platform.tfplan')]
    with (FOLDER/(action+'.log')).open('w') as log:
        result=subprocess.run(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RebuildError('Sandbox Terraform failed; inspect local/sandbox/'+action+'.log privately.')
    print('Sandbox Terraform '+action+' completed. Review local/sandbox/'+action+'.log.')


def operators(c,oc):
    cfg=saved(c)
    role='arn:aws:iam::'+c['aws_account_id']+':role/lemonade-sandbox-'+c['cluster_id']
    aws(['iam','get-role','--role-name','lemonade-sandbox-'+c['cluster_id']])
    for ns,package,channel,csv in PINS:
        catalog=get(oc,'packagemanifests',package,'-n','openshift-marketplace')
        if not any(x['name']==channel and x.get('currentCSV')==csv for x in catalog['status']['channels']):
            raise RebuildError('Catalog pin changed; review operator version before continuing.')
        apply(oc,{'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns,'labels':{'lemonade.openshift.io/component':'sandbox-platform'}}})
        spec={} if ns=='agent-sandbox-system' else {'targetNamespaces':[ns]}
        apply(oc,{'apiVersion':'operators.coreos.com/v1','kind':'OperatorGroup','metadata':{'name':package,'namespace':ns},'spec':spec})
        spec={'channel':channel,'name':package,'source':'redhat-operators','sourceNamespace':'openshift-marketplace','installPlanApproval':'Manual','startingCSV':csv}
        if ns==OSC_NS:spec['config']={'env':[{'name':'ROLEARN','value':role}]}
        apply(oc,{'apiVersion':'operators.coreos.com/v1alpha1','kind':'Subscription','metadata':{'name':package,'namespace':ns},'spec':spec})
    print('Pinned subscriptions created with manual approval. No KataConfig or code workload created.')


def approve(c,oc):
    saved(c)
    for ns,package,channel,csv in PINS:
        sub=get(oc,'subscription',package,'-n',ns)
        ref=sub.get('status',{}).get('installPlanRef',{}).get('name')
        if not ref:raise RebuildError('InstallPlan is not available yet for '+package)
        plan=get(oc,'installplan',ref,'-n',ns)
        if plan['spec'].get('clusterServiceVersionNames')!=[csv]:raise RebuildError('Unexpected operator dependency or version; inspect the InstallPlan.')
        run(oc+['patch','installplan',ref,'-n',ns,'--type=merge','-p','{"spec":{"approved":true}}'])
        print('Approved only '+csv)


def configure(c,oc):
    cfg=saved(c)
    for ns,_,_,csv in PINS:
        if get(oc,'csv',csv,'-n',ns)['status']['phase']!='Succeeded':raise RebuildError('Pinned operator is not ready: '+csv)
    run(oc+['label','node',cfg['node_name'],'lemonade.openshift.io/sandbox-worker=true','--overwrite'])
    bucket='podvm-lemonade-'+c['aws_account_id']+'-'+c['cluster_id']
    existing=get(oc,'configmaps','-n',OSC_NS)['items']
    cm=next((x for x in existing if x['metadata']['name']=='peer-pods-cm'),None)
    ami=cm.get('data',{}).get('PODVM_AMI_ID','') if cm else ''
    data={'CLOUD_PROVIDER':'aws','AWS_REGION':c['region'],'AWS_SUBNET_ID':cfg['subnet_id'],'AWS_VPC_ID':cfg['vpc_id'],
          'AWS_SG_IDS':cfg['worker_security_group'],'PODVM_INSTANCE_TYPE':'t3.medium','PODVM_INSTANCE_TYPES':'t3.medium',
          'PODVM_AMI_ID':ami,'DISABLECVM':'true','PROXY_TIMEOUT':'8m','PEERPODS_LIMIT_PER_NODE':'2',
          'TAGS':'Project=lemonade-demo,Cluster='+c['cluster_id'],'USE_PUBLIC_IP':'false'}
    apply(oc,{'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'peer-pods-cm','namespace':OSC_NS},'data':data})
    # Override only required fields, preserving operator image payload defaults.
    image_data={'BUCKET_NAME':bucket,'AMI_BASE_NAME':bucket,'AMI_VERSION':'0.0.1','ENABLE_NVIDIA_GPU':'no','CONFIDENTIAL_COMPUTE_ENABLED':'no',
                'PODVM_DISTRO':'rhel','AMI_VOLUME_SIZE':'30','INSTANCE_TYPE':'t3.medium','INSTALL_PACKAGES':'no','DOWNLOAD_SOURCES':'no',
                'DISABLE_CLOUD_CONFIG':'true','UPDATE_PEERPODS_CM':'yes','BOOT_FIPS':'no'}
    # This CM is normally created only after KataConfig. Precreate overrides so the first job uses the dedicated bucket.
    apply(oc,{'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'aws-podvm-image-cm','namespace':OSC_NS},'data':image_data})
    apply(oc,{'apiVersion':'kataconfiguration.openshift.io/v1','kind':'KataConfig','metadata':{'name':'lemonade-kata'},'spec':{'enablePeerPods':True,'kataConfigPoolSelector':{'matchLabels':{'lemonade.openshift.io/sandbox-worker':'true'}}}})
    print('Kata configured on one worker; image build may take several minutes. No sandbox workload submitted.')


def status(c,oc):
    saved(c)
    for ns,_,_,csv in PINS:
        items=get(oc,'csv','-n',ns)['items']
        print(csv,next((x.get('status',{}).get('phase') for x in items if x['metadata']['name']==csv),'not installed'))
    print('RuntimeClasses:',[x['metadata']['name'] for x in get(oc,'runtimeclasses')['items']])
    print('Kata:',[{ 'name':x['metadata']['name'],'status':x.get('status')} for x in get(oc,'kataconfigs')['items']])
    print('Jobs:',[{'name':x['metadata']['name'],'status':x.get('status')} for x in get(oc,'jobs','-n',OSC_NS)['items']])


def access(c,oc):
    saved(c)
    for path in ('gitops/bootstrap/controller-access.yaml','gitops/bootstrap/sandbox-access.yaml'):
        run(oc+['apply','-f',str(ROOT/path)])
    run([sys.executable,str(ROOT/'scripts/demo_secrets.py')])
    print('Applied scoped GitOps/broker access and ensured a private service key.')


def require_artifacts_removed(c):
    cfg=saved(c)
    prefix='podvm-lemonade-'+c['aws_account_id']+'-'+c['cluster_id']
    if peers(c):raise RebuildError('Tagged peer VMs remain.')
    if aws(['ec2','describe-images','--owners','self','--filters','Name=name,Values='+prefix+'*'])['Images']:
        raise RebuildError('Project VM image remains.')
    image_file=FOLDER/'image.json'
    if image_file.exists():
        image=json.loads(image_file.read_text())
        if image['cluster_id']!=c['cluster_id']:raise RebuildError('Image inventory belongs to another cluster.')
        owned=aws(['ec2','describe-snapshots','--owner-ids',c['aws_account_id']])['Snapshots']
        if any(s['SnapshotId'] in image['snapshots'] for s in owned):raise RebuildError('Recorded image snapshot remains.')
    buckets=aws(['s3api','list-buckets']).get('Buckets',[])
    if any(b['Name']==prefix for b in buckets):raise RebuildError('Dedicated image bucket remains.')
    role=subprocess.run(['aws','iam','get-role','--role-name','vmimport'],env=infrastructure_environment(),capture_output=True,text=True)
    if role.returncode==0 or 'NoSuchEntity' not in role.stderr:
        raise RebuildError('The image-builder role remains or its absence cannot be verified.')
    return cfg


def image_permissions(c,oc,enabled):
    cfg=saved(c)
    if not enabled:
        cm=get(oc,'configmap','peer-pods-cm','-n',OSC_NS)
        ami=cm.get('data',{}).get('PODVM_AMI_ID','')
        if not ami.startswith('ami-'):raise RebuildError('No completed VM image to verify.')
        image=aws(['ec2','describe-images','--image-ids',ami])['Images'][0]
        expected='podvm-lemonade-'+c['aws_account_id']+'-'+c['cluster_id']+'-0.0.1'
        if image['OwnerId']!=c['aws_account_id'] or image['Name']!=expected or image['State']!='available':
            raise RebuildError('VM image ownership or readiness mismatch.')
        (FOLDER/'image.json').write_text(json.dumps({'cluster_id':c['cluster_id'],'image_id':ami,'snapshots':[x['Ebs']['SnapshotId'] for x in image['BlockDeviceMappings'] if 'Ebs' in x]},indent=2))
    variables=json.loads((FOLDER/'platform.tfvars.json').read_text())
    variables['image_creation_enabled']=enabled
    (FOLDER/'platform.tfvars.json').write_text(json.dumps(variables,indent=2))
    terraform('plan',c)
    print('Image permissions planned '+('enabled for cleanup' if enabled else 'removed')+'. Review plan, then apply.')


def peers(c):
    instances=aws(['ec2','describe-instances','--filters','Name=tag:Project,Values=lemonade-demo','Name=tag:Cluster,Values='+c['cluster_id'],
                   'Name=instance-state-name,Values=pending,running,stopping,stopped,shutting-down'])
    return [i for r in instances['Reservations'] for i in r['Instances']]


def quiesce(c,oc):
    saved(c)
    # The normal shutdown must first stop admission and checkpoint durable application evidence.
    run(oc+['scale','deployment/lemonade-sandbox-broker','-n','lemonade-demo','--replicas=0'])
    run(oc+['patch','sandboxwarmpool','lemonade-python','-n','lemonade-sandbox','--type=merge','-p','{"spec":{"replicas":0}}'])
    for item in get(oc,'sandboxclaims','-n','lemonade-sandbox')['items']:
        if item['metadata'].get('labels',{}).get('lemonade.openshift.io/broker')!='true':
            raise RebuildError('Unknown sandbox claim; preserve it and inspect ownership.')
        run(oc+['delete','sandboxclaim',item['metadata']['name'],'-n','lemonade-sandbox','--wait=false'])
    print('Stopped replenishment and dispatch; wait for runner pods and tagged EC2 peers to disappear.')


def remove_runtime(c,oc):
    saved(c)
    if get(oc,'pods','-n','lemonade-sandbox')['items'] or peers(c):
        raise RebuildError('Sandbox pods or tagged peer EC2 instances still exist; runtime deletion refused.')
    variables=json.loads((FOLDER/'platform.tfvars.json').read_text())
    if not variables.get('image_creation_enabled',True):
        raise RebuildError('Plan image-permissions-on and apply for operator-owned image cleanup first.')
    run(oc+['delete','kataconfig','lemonade-kata','--wait=false','--ignore-not-found'])
    print('Runtime removal requested. Wait for image cleanup and KataConfig finalization before destroy-plan.')


def destroy_plan(c,oc):
    saved(c)
    if get(oc,'kataconfigs')['items'] or peers(c):raise RebuildError('Kata or peer VMs remain; IAM deletion refused.')
    require_artifacts_removed(c)
    for ns,_,_,_ in PINS:
        namespace=get(oc,'namespace',ns)
        if namespace['metadata'].get('labels',{}).get('lemonade.openshift.io/component')!='sandbox-platform':
            raise RebuildError('Operator namespace ownership mismatch.')
    env=terraform_environment('sandbox')
    args=[sys.executable,str(ROOT/'scripts/tf.py'),'sandbox','plan','-destroy','-input=false','-var-file='+str(FOLDER/'platform.tfvars.json'),'-out='+str(FOLDER/'destroy.tfplan')]
    with (FOLDER/'destroy-plan.log').open('w') as log:
        result=subprocess.run(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RebuildError('Sandbox delete plan failed; see private log.')
    print('Saved sandbox-only destroy plan. Inspect before destroy-apply.')


def destroy_apply(c,oc):
    saved(c)
    if get(oc,'kataconfigs')['items'] or peers(c):raise RebuildError('Kata or peer VMs reappeared; deletion refused.')
    require_artifacts_removed(c)
    env=terraform_environment('sandbox')
    plan=json.loads(run(['terraform','-chdir='+str(ROOT/'infra/sandbox'),'show','-json',str(FOLDER/'destroy.tfplan')],env=env))
    if plan['variables']['cluster_id']['value']!=c['cluster_id']:raise RebuildError('Destroy plan cluster mismatch.')
    for change in plan.get('resource_changes',[]):
        if change.get('mode')!='data' and (change['change']['actions'] not in (['delete'],['no-op']) or
            change['type'] not in ('aws_iam_role','aws_iam_role_policy','aws_vpc_security_group_ingress_rule')):
            raise RebuildError('Unexpected sandbox destroy scope.')
    for ns,_,_,_ in PINS:run(oc+['delete','namespace',ns,'--wait=false'])
    with (FOLDER/'destroy-apply.log').open('w') as log:
        result=subprocess.run([sys.executable,str(ROOT/'scripts/tf.py'),'sandbox','apply','-input=false',str(FOLDER/'destroy.tfplan')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RebuildError('Sandbox destroy failed; see private log.')
    print('Sandbox Terraform resources removed. Verify image snapshots, bucket, vmimport role and peer volumes before ROSA teardown.')


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=('discover','init','plan','apply','operators','approve','configure','status','access','image-permissions-off','image-permissions-on','quiesce','remove-runtime','destroy-plan','destroy-apply'))
    arg=p.parse_args()
    c,oc=context()
    if arg.phase in ('init','plan','apply'):terraform(arg.phase,c)
    elif arg.phase.startswith('image-permissions-'):image_permissions(c,oc,arg.phase.endswith('-on'))
    else:globals()[arg.phase.replace('-','_')](c,oc)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        sys.exit(str(exc) if isinstance(exc,(RebuildError,RuntimeError)) else 'Sandbox phase failed; diagnostic output withheld.')
