"""Versioned course drafts. Original/published lesson IDs are immutable."""
import copy
import datetime as dt
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import learning
import course_images

ROOT=Path(__file__).resolve().parent
LOCK=threading.RLock()

def require(value,message):
    if not value:raise ValueError(message)

def initialize(connection):
    connection.execute('CREATE TABLE IF NOT EXISTS course_drafts (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL, updated TEXT NOT NULL)')

def base_id(value):
    require(isinstance(value,str) and re.fullmatch(r'(english|chinese|math)-([1-9]|[1-8][0-9]|90)',value),'课次不存在')
    return value

def validate(base,lesson):
    original=learning.LESSONS[base_id(base)]
    require(isinstance(lesson,dict),'课程格式无效')
    result=copy.deepcopy(original)
    bindings=original_bindings(original)
    used_images={x for u in lesson.get('units',[]) for q in u.get('questions',[]) for x in q.get('options',[]) if isinstance(x,str) and x.startswith('pic_')}
    result['images']={ident:course_images.asset(ident,approved=True) for ident in used_images}
    for ident,image in result['images'].items():
        require(image['lang']==('en-US' if original['type']=='english' else 'zh-CN'),'图片绑定语言与课次不一致')
        bindings[ident]=image['word']
    if original['type'] in ['english','chinese']:
        supplied=lesson.get('optionWords',{})
        require(isinstance(supplied,dict),'选项词语绑定格式无效')
        for u in lesson.get('units',[]):
            for q in u.get('questions',[]):
                for value in q.get('options',[]):
                    if isinstance(value,str) and value not in bindings:
                        word=supplied.get(value)
                        require(isinstance(word,str) and 0<len(word.strip())<=60 and not any(ord(c)<32 for c in word),'请为每个新增选项填写对应的单词／汉字，用于点击发音')
                        bindings[value]=word.strip()
    for field in ['theme','phase']:
        value=lesson.get(field)
        require(isinstance(value,str) and 0<len(value.strip())<=60,'主题和阶段需为1—60字')
        result[field]=value.strip()
    require(isinstance(lesson.get('units'),list) and len(lesson['units'])==len(original['units']),'本版保持原课的单元数量')
    for source,target in zip(lesson['units'],result['units']):
        require(source.get('id')==target['id'] and len(source.get('questions',[]))==len(target['questions']),'请保留题目顺序与数量')
        for q,t in zip(source['questions'],target['questions']):
            require(q.get('id')==t['id'] and q.get('kind')==t['kind'],'题型不可直接更换')
            for field in ['prompt','display','speech','hint']:
                value=q.get(field)
                require(isinstance(value,str) and 0<len(value.strip())<=400,'题目、展示、朗读和提示需为1—400字')
                t[field]=value.strip()
            if t['kind'] in ['choice','story']:
                choices=q.get('options')
                require(isinstance(choices,list) and 2<=len(choices)<=4 and all(isinstance(x,str) and 0<len(x.strip())<=64 for x in choices),'选项需为2—4个，每项最多64字')
                require(len(set(choices))==len(choices) and q.get('answer') in choices,'选项不能重复，正确答案必须在选项中')
                t['options']=choices;t['answer']=q['answer']
            elif t['kind']=='grid':
                require(q.get('answer') in t['options'],'请从可用格子选择正确答案')
                t['answer']=q['answer'];t['highlight']=q['answer']
            else:
                require(q.get('answer')==t['answer'],'本版保留排序与棋盘结构，可编辑题目和提示')
            if target['section']=='words':
                require(t['speech']==t['display'],'认字／单词的展示文字和朗读内容需一致')
                target['label']=t['display']
                bindings.setdefault(t['answer'],t['display'])
                require(bindings[t['answer']].casefold()==t['display'].casefold(),'正确图片绑定的单词与当前目标词不一致，请更换对应图片')
                t['cue']=t['answer'] if t.get('cue') else ''
        if target['section']=='story':target['label']=result['theme']+'的小故事'
    if result['type'] in ['english','chinese']:
        known=set(bindings)
        require(all(option in known for u in result['units'] for q in u['questions'] for option in q['options']),'语言题的每个选项需对应本课5个单词／汉字的图片，请同步编辑相关选项')
    result['optionWords']=bindings
    return result

def original_bindings(lesson):
    bindings=dict(lesson.get('optionWords',{}));words=[u for u in lesson['units'] if u['section']=='words'];sentences=[u for u in lesson['units'] if u['section']=='sentences']
    for i,unit in enumerate(words):
        for q in unit['questions']:bindings.setdefault(q['answer'],unit['label'])
        if i<len(sentences):
            for q in sentences[i]['questions']:bindings.setdefault(q['answer'],unit['label'])
    return bindings

def manifest(name):
    path=ROOT/name
    lines=path.read_text().splitlines()
    return json.loads(lines[-1].split('=',1)[1].rstrip(';'))

def audio_texts(lesson):
    lang='en-US' if lesson['type']=='english' else 'zh-CN'
    result={(lang,q['speech']) for u in lesson['units'] for q in u['questions']}
    for u in lesson['units']:
        for q in u['questions']:
            result.add(('zh-CN',q['prompt']))
            if lesson['type']=='math':result.add(('zh-CN',q['hint']))
        if u['section']=='words':
            result.add((lang,u['label']))
            if lesson['type']=='chinese':result.add(('zh-CN',f'听一听，找找“{u["label"]}”这个字。'))
    if lesson['type'] in ['english','chinese']:
        for word in lesson.get('optionWords',{}).values():result.add((lang,word))
    for image in lesson.get('images',{}).values():result.add((image['lang'],image['word']))
    return sorted(result)

def readiness(lesson):
    en,zh=manifest('english-audio.js'),manifest('chinese-audio.js')
    missing=[{'lang':lang,'text':text} for lang,text in audio_texts(lesson) if not (en if lang=='en-US' else zh).get(text) or not (ROOT/(en if lang=='en-US' else zh)[text]).is_file()]
    files={'en-US':{},'zh-CN':{}}
    for lang,text in audio_texts(lesson):
        path=(en if lang=='en-US' else zh).get(text)
        if path and (ROOT/path).is_file():files[lang][text]=path
    return {'ready':not missing,'missing':missing,'count':len(audio_texts(lesson)),'files':files}

def get(connection,base):
    initialize(connection);base_id(base)
    row=connection.execute('SELECT revision,payload,updated FROM course_drafts WHERE id=?',(base,)).fetchone()
    current=learning.CATALOG.get('published',{}).get(base,base)
    lesson=json.loads(row[1]) if row else copy.deepcopy(learning.LESSONS[current])
    lesson.setdefault('optionWords',original_bindings(learning.LESSONS[base]))
    return {'lesson':lesson,'revision':row[0] if row else 0,'updated':row[2] if row else None,'publishedId':current,'audio':readiness(lesson),'imageService':course_images.status(),'fixedBindings':original_bindings(learning.LESSONS[base])}

def generate_audio(missing):
    if not missing:
        return
    uv=shutil.which('uv') or str(Path.home()/'.local/bin/uv')
    with tempfile.TemporaryDirectory(prefix='sprout-course-') as directory:
        source=Path(directory)/'texts.json';source.write_text(json.dumps(missing,ensure_ascii=False))
        try:subprocess.run([uv,'run','--offline','--with','edge-tts','python',str(ROOT/'editor_audio.py'),str(source)],cwd=ROOT,check=True,capture_output=True,timeout=240)
        except (subprocess.SubprocessError,OSError):raise ValueError('配音暂未完成，请检查网络和本机语音生成组件后重试；已保存草稿保留')

def act(connection,body):
    with LOCK:
        base=base_id(body.get('id'));current=get(connection,base)
        require(type(body.get('revision')) is int and body['revision']==current['revision'],'另一页面修改了草稿，请重新打开课次后再保存')
        action=body.get('action')
        if action=='save':
            lesson=validate(base,body.get('lesson'))
            connection.execute('INSERT INTO course_drafts VALUES (?,?,?,?) ON CONFLICT (id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload,updated=excluded.updated',(base,current['revision']+1,json.dumps(lesson,ensure_ascii=False),dt.datetime.now(dt.timezone.utc).isoformat()))
        elif action=='audio':
            require(current['revision']>0,'请先保存草稿，再生成配音')
            if not current['audio']['ready']:
                generate_audio(current['audio']['missing'])
        elif action=='publish':
            require(current['revision']>0,'请先保存草稿')
            require(current['audio']['ready'],'还有朗读内容没有配音，请先生成配音')
            lesson=validate(base,current['lesson']);version=base+'-v'+secrets.token_hex(6);lesson['id']=version
            catalog=copy.deepcopy(learning.CATALOG);catalog['lessons']={key:value for key,value in catalog['lessons'].items() if not value.get('courseId')};catalog['lessons'][version]=lesson;catalog.setdefault('published',{})[base]=version
            temporary=ROOT/'curriculum.json.tmp';temporary.write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':')));temporary.replace(ROOT/'curriculum.json')
            learning.LESSONS[version]=lesson;learning.CATALOG['published']=catalog['published']
        else:raise ValueError('课程操作无效')
        return get(connection,base)
