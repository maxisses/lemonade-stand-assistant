"""One-use code runner inside a Kata VM. Never run model code in the broker."""
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_CODE = 8000
MAX_OUTPUT = 8192
WALL_SECONDS = 5
SALES = 'day,cups\nMonday,40\nTuesday,55\nWednesday,65\n'
lock = threading.Lock()
consumed = False


def child_limits():
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def execute(code):
    if not isinstance(code, str) or not code.strip() or len(code.encode()) > MAX_CODE:
        raise ValueError('Code must contain 1–8000 UTF-8 bytes.')
    with tempfile.TemporaryDirectory(prefix='lemonade-',dir='/tmp') as folder:
        Path(folder,'analysis.py').write_text(code)
        Path(folder,'sales.csv').write_text(SALES)
        start=time.monotonic()
        # No model credential, Kubernetes token or parent environment reaches the child.
        process=subprocess.Popen([sys.executable,'-I','-B','analysis.py'],cwd=folder,
            env={'PATH':'/usr/bin:/bin','HOME':folder,'LANG':'C.UTF-8'},
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            start_new_session=True,preexec_fn=child_limits)
        output=bytearray(); outcome='completed'; selector=selectors.DefaultSelector()
        selector.register(process.stdout,selectors.EVENT_READ)
        try:
            while True:
                if time.monotonic()-start>WALL_SECONDS:
                    outcome='timeout';break
                ready=selector.select(timeout=.05)
                if ready:
                    part=os.read(process.stdout.fileno(),1024)
                    if not part:break
                    output.extend(part)
                    if len(output)>MAX_OUTPUT:
                        outcome='output_limit';break
                elif process.poll() is not None:break
        finally:
            if outcome=='completed':
                try:process.wait(timeout=.2)
                except subprocess.TimeoutExpired:outcome='execution_error'
            # Kill the whole original group even if the initial process has exited.
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=2)
            selector.close();process.stdout.close()
        if outcome=='completed' and process.returncode!=0:outcome='execution_error'
        return {'outcome':outcome,'stdout':bytes(output[:MAX_OUTPUT]).decode('utf-8','replace'),
                'exit_code':process.returncode,'seconds':round(time.monotonic()-start,3),
                'output_truncated':len(output)>MAX_OUTPUT,'dataset':'Synthetic Lemonade sales — 3 days'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,data):
        body=json.dumps(data).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        self.reply(503 if consumed else 200,{'ready':not consumed}) if self.path=='/health' else self.reply(404,{'error':'Not found'})
    def do_POST(self):
        global consumed
        if self.path!='/run':return self.reply(404,{'error':'Not found'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=12000:raise ValueError()
            data=json.loads(self.rfile.read(size))
            if set(data)!={'code'} or not isinstance(data['code'],str) or len(data['code'].encode())>MAX_CODE:raise ValueError()
        except (ValueError,TypeError):return self.reply(400,{'error':'Invalid bounded code request'})
        if not lock.acquire(blocking=False):return self.reply(409,{'error':'Runner busy'})
        try:
            if consumed:return self.reply(409,{'error':'This sandbox has already been used'})
            consumed=True
            self.reply(200,execute(data['code']))
        except Exception:self.reply(500,{'error':'Runner failed'})
        finally:lock.release()

if __name__=='__main__':
    ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
