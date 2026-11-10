#!/usr/bin/env python3
"""One serial operator sandbox check; never starts campaigns or audience traffic."""
import argparse
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from rebuild import ROOT, context, run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','generate','run','egress','credentials','timeout'])
    parser.add_argument('--id');parser.add_argument('--sha256')
    args=parser.parse_args()
    if args.action=='run' and (not args.id or not args.sha256):parser.error('Run requires the reviewed --id and --sha256.')
    c,oc=context()
    token=run(oc+['whoami','-t'])
    config=json.loads((ROOT/'presentation/config.js').read_text().split('window.LEMONADE_DECK =',1)[1].strip().removesuffix(';'))
    origin=config['links']['chat']
    with socket.socket() as port_socket:
        port_socket.bind(('127.0.0.1',0));port=port_socket.getsockname()[1]
    process=subprocess.Popen(oc+['port-forward','-n','lemonade-demo','service/lemonade-stand',str(port)+':8080','--address','127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    base='http://127.0.0.1:'+str(port)+'/api/control/sandbox'
    def request(path='',body=None,csrf=''):
        headers={'X-Forwarded-Access-Token':token,'Origin':origin,'Content-Type':'application/json'}
        if body is not None:headers['X-CSRF-Token']=csrf
        req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
    try:
        deadline=time.monotonic()+20
        while True:
            try:state=request();break
            except urllib.error.URLError:
                if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Local project forwarding did not become ready') from None
                time.sleep(.5)
        if args.action=='status':
            print(json.dumps({k:state[k] for k in ['active','platform','can_execute','locked','model']},indent=2));return
        if args.action=='generate':path,body='/generate',{'task':'total'}
        elif args.action=='run':path,body='/'+args.id+'/run',{'code_sha256':args.sha256}
        else:path,body='/probe',{'probe':args.action}
        record=request(path,body,state['csrf_token']);identifier=record['id']
        deadline=time.monotonic()+260
        while time.monotonic()<deadline:
            state=request();record=next(r for r in state['runs'] if r['id']==identifier)
            if record['status'] not in ['generating','allocating','running','stopping']:break
            time.sleep(2)
        else:raise RuntimeError('Check still active; inspect operator UI, do not replay')
        folder=ROOT/'local/sandbox';folder.mkdir(mode=0o700,exist_ok=True)
        output=folder/('probe-'+identifier+'.json');output.write_text(json.dumps(record,indent=2));output.chmod(0o600)
        # Only fixture code/results, never authentication state or tokens.
        print(json.dumps({k:record[k] for k in ['id','status','code','code_sha256','result','check','error'] if k in record},indent=2))
        expected=(record['status']=='review' if args.action=='generate' else
                  record.get('result',{}).get('outcome')=='completed' if args.action=='run' else record.get('check')=='observed')
        if not expected:raise SystemExit(2)
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':
    try:main()
    except Exception as error:
        if isinstance(error,urllib.error.HTTPError):raise SystemExit('Operator request rejected: HTTP '+str(error.code)) from None
        raise SystemExit('Sandbox probe did not complete; inspect private platform state. No retry dispatched.') from None
