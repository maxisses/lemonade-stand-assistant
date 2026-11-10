"""Offline safeguards for repeated sandbox provisioning. No cloud access."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sandbox_platform as platform

class PlacementTests(unittest.TestCase):
    def test_configure_refuses_a_second_selected_worker_before_mutating(self):
        def get(oc,resource,*args):
            if resource=='csv':return {'status':{'phase':'Succeeded'}}
            if resource=='nodes':return {'items':[{'metadata':{'name':'another-worker','labels':{'lemonade.openshift.io/sandbox-worker':'true'}}}]}
            raise AssertionError(resource)
        with patch.object(platform,'saved',return_value={'node_name':'original-worker'}),patch.object(platform,'get',side_effect=get),patch.object(platform,'run') as mutate:
            with self.assertRaises(platform.RebuildError):platform.configure({},[])
            mutate.assert_not_called()

    def test_discovery_keeps_worker_and_removed_builder_rights(self):
        c={'cluster_id':'cluster','aws_account_id':'123456789012','region':'eu-central-1'}
        nodes=[{'metadata':{'name':n},'spec':{'providerID':'aws:///zone/'+i}} for n,i in [('other','i-other'),('original','i-original')]]
        instances=[{'InstanceId':i,'VpcId':'vpc','SubnetId':s,'SecurityGroups':[{'GroupId':'sg'}]} for i,s in [('i-other','subnet-other'),('i-original','subnet-original')]]
        def aws(args):
            if args[:2]==['ec2','describe-instances']:return {'Reservations':[{'Instances':instances}]}
            if args[:2]==['ec2','describe-security-groups']:return {'SecurityGroups':[{'GroupId':'sg','IpPermissions':[{'IpProtocol':'tcp','FromPort':9000,'ToPort':9999,'UserIdGroupPairs':[{'GroupId':'sg'}]}]}]}
            if args[:2]==['pricing','get-products']:return {'PriceList':[]}
            raise AssertionError(args)
        def get(oc,resource,*args):
            return {'items':nodes} if resource=='nodes' else {'spec':{'serviceAccountIssuer':'https://issuer'}}
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'context.json').write_text(json.dumps({**c,'node_name':'original','vmimport_absent_before_install':True}))
            (folder/'platform.tfvars.json').write_text(json.dumps({'image_creation_enabled':False}))
            with patch.object(platform,'FOLDER',folder),patch.object(platform,'aws',side_effect=aws),patch.object(platform,'get',side_effect=get),patch('builtins.print'):
                platform.discover(c,[])
            self.assertFalse(json.loads((folder/'platform.tfvars.json').read_text())['image_creation_enabled'])
            saved=json.loads((folder/'context.json').read_text())
            self.assertEqual((saved['node_name'],saved['subnet_id']),('original','subnet-original'))

if __name__=='__main__':unittest.main()
