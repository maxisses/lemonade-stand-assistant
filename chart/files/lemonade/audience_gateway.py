"""Public event gateway for bounded audience sessions and checked-response SSE."""
import os
from contextlib import asynccontextmanager
import aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

@asynccontextmanager
async def lifespan(app):
    app.state.client=aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120,connect=5))
    yield
    await app.state.client.close()

app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
ALLOWED={('GET',''),('GET','join'),('GET','api/audience/state'),('POST','api/audience/session'),('POST','api/audience/chat')}

@app.get('/health')
async def health():return {'status':'healthy'}


class UpstreamStream(StreamingResponse):
    """Keep the upstream response open until delivery or client cancellation."""

    def __init__(self, content, context, **kwargs):
        super().__init__(content, **kwargs)
        self.context = context

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            await self.context.__aexit__(None, None, None)


@app.api_route('/{path:path}',methods=['GET','POST','PUT','DELETE','PATCH'])
async def forward(path:str, request:Request):
    if (request.method,path) not in ALLOWED:raise HTTPException(404,'Not found')
    body=await request.body()
    if len(body)>2048:raise HTTPException(413,'Request too large')
    target='/join' if path in ('','join') else '/'+path
    headers={'X-Audience-Gateway':os.environ['AUDIENCE_GATEWAY_KEY']}
    for name in ('content-type','cookie','x-csrf-token','origin'):
        if name in request.headers:headers[name]=request.headers[name]
    context=app.state.client.request(request.method,os.environ['APPLICATION_URL']+target,data=body,headers=headers,allow_redirects=False)
    entered=False
    handed_off=False
    try:
        response=await context.__aenter__()
        entered=True
        content_type=response.headers.get('content-type','text/plain')
        outgoing={'Content-Type':content_type,'Cache-Control':'no-store',
                  'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin'}
        if path=='api/audience/chat' and response.status==200 and content_type.startswith('text/event-stream'):
            async def stream():
                try:
                    async for chunk in response.content.iter_any():
                        yield chunk
                except (aiohttp.ClientError,TimeoutError):
                    # Keep transport failures distinct from model/policy decisions.
                    yield b'data: {"type":"error","outcome":"error","message":"The reply was interrupted. No automatic retry was sent."}\n\n'
            outgoing['Cache-Control']='no-store, no-transform'
            outgoing['X-Accel-Buffering']='no'
            result=UpstreamStream(stream(),context,headers=outgoing)
            handed_off=True
        else:
            result=Response(await response.read(),status_code=response.status,headers=outgoing)
        for cookie in response.headers.getall('Set-Cookie',[]):result.headers.append('set-cookie',cookie)
        return result
    except (aiohttp.ClientError,TimeoutError):
        raise HTTPException(503,'Demo is temporarily unavailable; no automatic retry.') from None
    finally:
        if entered and not handed_off:await context.__aexit__(None,None,None)
