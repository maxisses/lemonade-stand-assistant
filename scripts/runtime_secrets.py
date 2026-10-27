#!/usr/bin/env python3
"""Idempotent secret bootstrap for the verified project cluster; no secret output."""
import json, os, secrets, subprocess, sys
from project_env import ROOT, configuration

def main():
    values = configuration()
    context = json.loads((ROOT/'local/context.json').read_text())
    server = context.get('cluster_api_url')
    if not server: sys.exit('Project cluster context is not initialized')
    env = os.environ.copy()
    env['KUBECONFIG'] = str(ROOT/'local/kubeconfig')
    result = subprocess.run(['oc','config','view','--minify','-o','jsonpath={.clusters[0].cluster.server}'], env=env, capture_output=True, text=True)
    if result.returncode or result.stdout.rstrip('/') != server.rstrip('/'):
        sys.exit('Kubeconfig does not match the provisioned project cluster')
    path = ROOT/'local/model-storage-credentials.json'
    if path.exists(): storage = json.loads(path.read_text())
    else:
        storage = {'access_key':'lemonade-'+secrets.token_hex(8), 'secret_key':secrets.token_urlsafe(32)}
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd,'w') as file: json.dump(storage, file)
    definitions = {
        'lemonade-model': {'vllm-api-key':values['modelkey']},
        'minio-data-connection-detector-models': {
            'AWS_ACCESS_KEY_ID':storage['access_key'], 'AWS_SECRET_ACCESS_KEY':storage['secret_key'],
            'AWS_DEFAULT_REGION':'us-east-1', 'AWS_S3_BUCKET':'huggingface',
            'AWS_S3_ENDPOINT':'http://minio-storage-guardrail-detectors:9000'
        }
    }
    for name, data in definitions.items():
        manifest={'apiVersion':'v1','kind':'Secret','metadata':{'name':name,'namespace':'lemonade-demo'},'type':'Opaque','stringData':data}
        result=subprocess.run(['oc','apply','--server-side','--field-manager=lemonade-runtime-secrets','-f','-'],input=json.dumps(manifest),env=env,capture_output=True,text=True)
        if result.returncode:sys.exit('Secret bootstrap failed for '+name+'; response withheld')
        print('Configured runtime secret: '+name)

if __name__ == '__main__': main()
