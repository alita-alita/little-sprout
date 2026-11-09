"""Local image drafts and Cloudflare Workers AI connector. Never serves credentials."""
import base64
import datetime as dt
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent
LOCK=threading.RLock()
MODEL='@cf/black-forest-labs/flux-1-schnell'

def require(value,message):
    if not value:raise ValueError(message)

def read(path,default):
    try:return json.loads(path.read_text())
    except FileNotFoundError:return default

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False));os.chmod(temp,0o600);temp.replace(path)

def credentials():
    stored=read(ROOT/'data/image-service.json',{})
    return os.environ.get('CLOUDFLARE_ACCOUNT_ID') or stored.get('account',''),os.environ.get('CLOUDFLARE_API_TOKEN') or stored.get('token','')

def status():
    account,token=credentials()
    assets=read(ROOT/'data/image-assets.json',{})
    return {'configured':bool(re.fullmatch(r'[a-fA-F0-9]{32}',account) and token),'provider':'Cloudflare Workers AI','model':MODEL,'library':list(assets.values())[-30:]}

def configure(body):
    account,token=body.get('account','').strip(),body.get('token','').strip()
    require(re.fullmatch(r'[a-fA-F0-9]{32}',account),'Account ID 应为32位字符，请从 Workers AI 页面复制')
    require(10<=len(token)<=500 and '\n' not in token and '\r' not in token,'请填写有效的 Workers AI API Token')
    with LOCK:write(ROOT/'data/image-service.json',{'account':account,'token':token})
    return status()

def prompt_for(word):
    return ('Create one educational picture-book flashcard for a four-year-old child. '
      'The only subject is: '+word+'. Show one clearly recognizable subject, centered, large, complete and uncropped. '
      'Warm hand-painted gouache and soft colored-pencil children picture book illustration, rounded gentle forms, '
      'accurate identifying features, cheerful natural colors, plain warm ivory background, ample empty space. '
      'No words, no letters, no numbers, no watermark, no border, no extra objects, no faces on food, no collage. '
      'Depict the vocabulary meaning literally. Square composition.')

def generate(word):
    account,token=credentials();require(account and token,'请先配置 Cloudflare 免费生图服务')
    body=json.dumps({'prompt':prompt_for(word),'steps':4}).encode()
    req=Request('https://api.cloudflare.com/client/v4/accounts/'+account+'/ai/run/'+MODEL,data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(req,timeout=180) as response:data=json.loads(response.read(12*1024*1024))
    except HTTPError as error:
        if error.code in [401,403]:raise ValueError('生图服务没有授权，请检查 Account ID 和 Token 的 Workers AI 权限')
        if error.code==429:raise ValueError('服务额度或速率已达上限，请稍后再试；本应用不会切换付费服务')
        raise ValueError('生图服务暂时不可用，请稍后重试')
    except (URLError,TimeoutError):raise ValueError('没有连上生图服务，请检查网络后重试')
    require(data.get('success') is not False,'生图服务未生成图片，请检查免费额度和模型权限')
    encoded=data.get('result',{}).get('image')
    require(isinstance(encoded,str) and len(encoded)<12*1024*1024,'生图服务没有返回有效图片')
    try:content=base64.b64decode(encoded,validate=True)
    except ValueError:raise ValueError('生图服务返回的图片格式不正确')
    require(100<len(content)<=8*1024*1024,'图片为空或超出大小限制')
    require(content.startswith(b'\x89PNG\r\n\x1a\n') or content.startswith(b'\xff\xd8\xff'),'只接受 PNG 或 JPEG 图片')
    return content

def save_asset(content,word,lang,source='cloudflare'):
    ident='pic_'+secrets.token_hex(12);extension='.png' if content.startswith(b'\x89PNG') else '.jpg'
    relative='assets/pictures/'+ident[4:]+extension;path=ROOT/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
    asset={'id':ident,'word':word,'lang':lang,'src':'/'+relative,'source':source,'approved':False,'createdAt':dt.datetime.now(dt.timezone.utc).isoformat()}
    with LOCK:
        assets=read(ROOT/'data/image-assets.json',{});assets[ident]=asset;write(ROOT/'data/image-assets.json',assets)
    return asset

def asset(ident,approved=False):
    require(isinstance(ident,str) and re.fullmatch(r'pic_[a-f0-9]{24}',ident),'图片标识无效')
    value=read(ROOT/'data/image-assets.json',{}).get(ident)
    require(value and (ROOT/value['src'].lstrip('/')).is_file(),'图片不存在，请重新生成')
    if approved:require(value.get('approved'),'图片需要家长确认后才能加入课次')
    return dict(value)

def approve(ident):
    with LOCK:
        value=dict(asset(ident));value['approved']=True
        assets=read(ROOT/'data/image-assets.json',{});assets[ident]=value;write(ROOT/'data/image-assets.json',assets)
    return dict(value)

def job(ident):
    require(isinstance(ident,str) and re.fullmatch(r'[a-f0-9]{24}',ident),'生成任务无效')
    value=read(ROOT/('data/image-jobs/'+ident+'.json'),None);require(value,'生成任务不存在')
    if value['state']=='running' and dt.datetime.now(dt.timezone.utc).timestamp()-value['started']>240:
        value.update(state='error',error='生成任务已超时，请手动重试；原图片仍保留')
    return dict(value)

def start(body):
    word=body.get('word','').strip();lang=body.get('lang')
    require(0<len(word)<=60 and not any(ord(c)<32 for c in word),'请填写1—60字的单词或物体名称')
    require(lang in ['en-US','zh-CN'],'请选择英语或语文')
    request=body.get('requestId');require(isinstance(request,str) and re.fullmatch(r'[a-zA-Z0-9-]{10,80}',request),'请求标识无效')
    with LOCK:
        requests=read(ROOT/'data/image-requests.json',{})
        if request in requests:
            prior=job(requests[request]);require(prior['word']==word and prior['lang']==lang,'同一请求不能用于不同单词');return prior
        require(status()['configured'],'请先在下方配置 Cloudflare 免费生图服务，再点击生成')
        running=[p for p in (ROOT/'data/image-jobs').glob('*.json') if job(p.stem)['state']=='running']
        require(len(running)<2,'已有图片正在生成，请稍候，避免重复消耗额度')
        ident=secrets.token_hex(12);value={'id':ident,'word':word,'lang':lang,'state':'running','started':dt.datetime.now(dt.timezone.utc).timestamp()}
        write(ROOT/('data/image-jobs/'+ident+'.json'),value);requests[request]=ident;write(ROOT/'data/image-requests.json',requests)
    def run():
        try:value.update(state='ready',asset=save_asset(generate(word),word,lang))
        except ValueError as error:value.update(state='error',error=str(error))
        except Exception:value.update(state='error',error='这次未能完成生成，请手动重试；不会自动重复调用服务')
        with LOCK:write(ROOT/('data/image-jobs/'+ident+'.json'),value)
    threading.Thread(target=run,daemon=True).start()
    return dict(value)
