"""Fixed-destination, TLS-verified provider admission for every demo model role."""
import asyncio
import hmac
import json
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path

import aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


class Ledger:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS calls
            (id INTEGER PRIMARY KEY, started REAL, role TEXT, generation INTEGER,
             tokens INTEGER, estimated INTEGER, status TEXT);
            CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY,value TEXT);''')
        self.db.execute("UPDATE calls SET status='interrupted' WHERE status='pending'")
        self.db.commit()

    def paused(self):
        row = self.db.execute("SELECT value FROM state WHERE key='paused'").fetchone()
        return row[0] if row else ''

    def pause(self, reason):
        self.db.execute("INSERT OR REPLACE INTO state VALUES ('paused',?)", (reason,))
        self.db.commit()

    def usage(self, seconds):
        row = self.db.execute('SELECT count(*),coalesce(sum(generation),0),coalesce(sum(tokens),0) FROM calls WHERE started>?', (time.time()-seconds,)).fetchone()
        return dict(zip(('requests','generations','tokens'), row))

    def reserve(self, role, generation, tokens):
        if self.paused():
            raise HTTPException(429, 'Provider admission paused; operator review required.')
        usage = self.usage(3600)
        if usage['requests'] >= 240 or usage['generations'] >= 120 or usage['tokens'] + tokens > 240000:
            self.pause('hourly_budget')
            raise HTTPException(429, 'Provider hourly budget reached.')
        cursor = self.db.execute('INSERT INTO calls(started,role,generation,tokens,estimated,status) VALUES(?,?,?,?,1,?)',
                                 (time.time(),role,int(generation),tokens,'pending'))
        self.db.commit()
        return cursor.lastrowid

    def finish(self, identifier, status, usage=None):
        if isinstance(usage, dict) and isinstance(usage.get('total_tokens'), int) and usage['total_tokens'] >= 0:
            self.db.execute('UPDATE calls SET status=?,tokens=?,estimated=0 WHERE id=?', (status,usage['total_tokens'],identifier))
        else:
            self.db.execute('UPDATE calls SET status=? WHERE id=?', (status,identifier))
        self.db.commit()


@asynccontextmanager
async def lifespan(app):
    app.state.ledger = Ledger(os.getenv('PROVIDER_DB','/data/provider.sqlite'))
    app.state.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60,connect=5))
    app.state.lock = asyncio.Lock()
    app.state.waiting = 0
    app.state.last_generation = 0.0
    app.state.errors = 0
    try:
        yield
    finally:
        await app.state.session.close()
        app.state.ledger.db.close()

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def authorize(request):
    key = os.getenv('MODEL_API_KEY','')
    supplied = request.headers.get('authorization','')
    if not key or not hmac.compare_digest(supplied, 'Bearer '+key):
        raise HTTPException(401,'Provider authentication required.')


@app.get('/health')
async def health():
    return {'status':'healthy'}


@app.get('/budget')
async def budget(request: Request):
    authorize(request)
    return {'paused':app.state.ledger.paused(), 'last_minute':app.state.ledger.usage(60),
            'last_hour':app.state.ledger.usage(3600),'concurrency':1,'generation_starts_per_minute':12,
            'hourly_request_limit':240,'hourly_generation_limit':120,'hourly_token_limit':240000,
            'waiting':app.state.waiting,'token_accounting':'Provider usage where present; conservative reservations otherwise'}


@app.post('/budget/resume')
async def resume(request: Request):
    authorize(request)
    app.state.ledger.pause('')
    app.state.errors=0
    return {'paused':''}


@app.post('/{path:path}')
async def forward(path: str, request: Request):
    authorize(request)
    if path not in ('v1/chat/completions','chat/completions','tokenize','v1/tokenize'):
        raise HTTPException(404,'Unsupported provider operation.')
    raw=await request.body()
    if len(raw)>24000:
        raise HTTPException(413,'Provider payload exceeds the demo budget.')
    try:
        body=json.loads(raw)
    except (ValueError,TypeError):
        raise HTTPException(400,'Invalid request.') from None
    if not isinstance(body,dict) or body.get('model') != os.getenv('PROVIDER_MODEL','qwen38-27b'):
        raise HTTPException(400,'Only the configured demo model is allowed.')
    generation='completions' in path
    if generation:
        cap=body.get('max_tokens',128)
        if type(cap) is not int or not 1<=cap<=192 or body.get('stream') is True or type(body.get('n',1)) is not int or body.get('n',1)!=1 or 'max_completion_tokens' in body:
            raise HTTPException(400,'Only bounded, non-streaming single completions are supported.')
        body['max_tokens']=cap
        body['stream']=False
        body['chat_template_kwargs']={'enable_thinking':False}
    else:
        cap=0
    if app.state.waiting>=8:
        raise HTTPException(429,'Provider queue is full.')
    role=request.headers.get('x-demo-role','target')
    role=role if role in ('attacker','judge','target') else 'target'
    app.state.waiting+=1
    identifier=None
    try:
        async with app.state.lock:
            if generation:
                last=app.state.ledger.db.execute('SELECT max(started) FROM calls WHERE generation=1').fetchone()[0] or 0
                await asyncio.sleep(max(0,5-(time.time()-last)))
            # UTF-8 byte count plus framing allowance is intentionally conservative.
            identifier=app.state.ledger.reserve(role,generation,len(raw)+512+cap)
            if generation:app.state.last_generation=time.monotonic()
            base=os.environ['PROVIDER_BASE_URL'].rstrip('/')
            if not base.startswith('https://'):
                raise RuntimeError('Provider requires HTTPS')
            async with app.state.session.post(base+'/'+path,json=body,headers={'Authorization':'Bearer '+os.environ['MODEL_API_KEY']},allow_redirects=False) as response:
                data=await response.read()
                if response.status==429:
                    app.state.ledger.pause('provider_throttled')
                if response.status>=300:
                    app.state.errors+=1
                    if app.state.errors>=3:app.state.ledger.pause('repeated_provider_errors')
                    app.state.ledger.finish(identifier,'provider_error')
                    return JSONResponse({'error':{'message':'Provider request failed; no automatic retry.','type':'provider_error'}},status_code=response.status if response.status>=400 else 502)
                app.state.errors=0
                try: result=json.loads(data)
                except ValueError: raise RuntimeError('Invalid provider response') from None
                app.state.ledger.finish(identifier,'completed',result.get('usage') if isinstance(result,dict) else None)
                return JSONResponse(result)
    except asyncio.CancelledError:
        if identifier is not None:app.state.ledger.finish(identifier,'cancelled_unknown_upstream')
        raise
    except HTTPException:
        raise
    except Exception:
        if identifier is not None:app.state.ledger.finish(identifier,'transport_error')
        app.state.errors+=1
        if app.state.errors>=3:app.state.ledger.pause('repeated_provider_errors')
        raise HTTPException(502,'Provider transport failed; no automatic retry.') from None
    finally:
        app.state.waiting-=1
