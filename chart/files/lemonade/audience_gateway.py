"""Public event gateway: only role selection and bounded audience chat are forwarded."""
import os
from contextlib import asynccontextmanager
import aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

@asynccontextmanager
async def lifespan(app):
    app.state.client=aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120,connect=5))
    yield
    await app.state.client.close()

app=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
ALLOWED={('GET',''),('GET','join'),('GET','api/audience/state'),('POST','api/audience/session'),('POST','api/audience/chat')}

@app.get('/health')
async def health():return {'status':'healthy'}

@app.api_route('/{path:path}',methods=['GET','POST','PUT','DELETE','PATCH'])
async def forward(path:str, request:Request):
    if (request.method,path) not in ALLOWED:raise HTTPException(404,'Not found')
    body=await request.body()
    if len(body)>2048:raise HTTPException(413,'Request too large')
    target='/join' if path in ('','join') else '/'+path
    headers={'X-Audience-Gateway':os.environ['AUDIENCE_GATEWAY_KEY']}
    for name in ('content-type','cookie','x-csrf-token','origin'):
        if name in request.headers:headers[name]=request.headers[name]
    try:
        async with app.state.client.request(request.method,os.environ['APPLICATION_URL']+target,data=body,headers=headers,allow_redirects=False) as response:
            content=await response.read()
            result=Response(content,status_code=response.status,media_type=response.headers.get('content-type','text/plain'))
            for cookie in response.headers.getall('Set-Cookie',[]):result.headers.append('set-cookie',cookie)
            result.headers['Cache-Control']='no-store'
            result.headers['X-Content-Type-Options']='nosniff'
            result.headers['Referrer-Policy']='same-origin'
            return result
    except (aiohttp.ClientError,TimeoutError):
        raise HTTPException(503,'Demo is temporarily unavailable; no automatic retry.') from None
