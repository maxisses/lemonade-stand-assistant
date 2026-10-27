#!/usr/bin/env python3
"""Log into the provisioned demo cluster without printing or passing passwords in argv."""
import json, os, pty, select, subprocess, sys, termios, time
from project_env import ROOT, terraform_environment, verify_backend

def main():
    env = terraform_environment('rosa')
    verify_backend('rosa', env)
    identity = json.loads(subprocess.check_output(['aws','sts','get-caller-identity','--output','json'], env=env))
    if identity['Account'] != env['TF_VAR_expected_account_id']:
        sys.exit('AWS account mismatch')
    result = subprocess.run(['terraform','-chdir='+str(ROOT/'infra/rosa'),'output','-json'], env=env, capture_output=True, text=True)
    if result.returncode:
        sys.exit('Cluster outputs unavailable; no login attempted')
    outputs = json.loads(result.stdout)
    required = ['api_url', 'cluster_id', 'console_url', 'admin_password']
    if not all(k in outputs for k in required):
        sys.exit('Cluster creation is not complete')
    server = outputs['api_url']['value']
    if not server.startswith('https://'):
        sys.exit('Expected a TLS-protected cluster API')
    kubeconfig = ROOT/'local/kubeconfig'
    env['KUBECONFIG'] = str(kubeconfig)
    master, slave = pty.openpty()
    attrs = termios.tcgetattr(slave)
    attrs[3] &= ~termios.ECHO
    termios.tcsetattr(slave, termios.TCSANOW, attrs)
    proc = subprocess.Popen(['oc','login',server,'--username','cluster-admin','--kubeconfig',str(kubeconfig)], env=env, stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)
    buffer, sent = b'', False
    deadline = time.monotonic()+75
    try:
        while proc.poll() is None and time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 1)
            if not ready: continue
            try: buffer += os.read(master, 4096)
            except OSError: break
            if b'password:' in buffer.lower() and not sent:
                os.write(master, outputs['admin_password']['value'].encode()+b'\n')
                sent = True
            if b'insecure' in buffer.lower() and b'(y/n)' in buffer.lower():
                proc.terminate()
                sys.exit('Cluster certificate was not trusted; insecure login was refused')
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        if proc.returncode:
            sys.exit('Cluster login did not complete; identity provider may still be initializing')
    finally:
        os.close(master)
    os.chmod(kubeconfig, 0o600)
    check = subprocess.run(['oc','whoami'], env=env, capture_output=True, text=True)
    if check.returncode:
        sys.exit('Post-login identity verification failed')
    path = ROOT/'local/context.json'
    context = json.loads(path.read_text())
    context.update(cluster_api_url=server, cluster_id=outputs['cluster_id']['value'], console_url=outputs['console_url']['value'])
    path.write_text(json.dumps(context, indent=2)+'\n')
    os.chmod(path, 0o600)
    print('Authenticated to the project cluster; kubeconfig saved privately under local/.')

if __name__ == '__main__': main()
