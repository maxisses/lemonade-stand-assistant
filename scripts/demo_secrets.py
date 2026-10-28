#!/usr/bin/env python3
"""Create missing demo session/gateway keys in the verified cluster without outputting values."""
import json
import secrets
import sys
from project_env import ROOT
from show_access import command, load_context, AccessError

def main():
    context=load_context()
    oc=['oc','--kubeconfig',str(ROOT/'local/kubeconfig'),'--request-timeout=15s']
    server=command(oc+['config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}'])
    if server.rstrip('/')!=context['cluster_api_url'].rstrip('/'):raise AccessError('Wrong cluster; no secret created.')
    exists=command(oc+['-n','lemonade-demo','get','secret','lemonade-control','--ignore-not-found','-o','name'])
    if exists:
        print('Retained existing demo session keys.');return
    manifest={'apiVersion':'v1','kind':'Secret','metadata':{'name':'lemonade-control','namespace':'lemonade-demo'},'type':'Opaque',
              'stringData':{key:secrets.token_urlsafe(32) for key in ('session-secret','gateway-key')}}
    command(oc+['create','-f','-'],input=json.dumps(manifest))
    print('Created private demo session keys.')

if __name__=='__main__':
    try:main()
    except Exception:sys.exit('Demo secret bootstrap failed; details withheld.')
