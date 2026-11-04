"""Generate selected Yunxia Chinese audio. Only public curriculum/UI text is sent.
Run: uv run --offline --with edge-tts python build_yunxia_audio.py
"""
import asyncio
import hashlib
import json
from pathlib import Path
import edge_tts

ROOT=Path(__file__).resolve().parent
VERSION='yunxia-v1'
VOICE='zh-CN-YunxiaNeural'
RATE='-12%'
UI_TEXTS=[
 '你好，我是小芽。我们一起听故事吧。','准备好后，点开始探索。',
 '我们来一起探索。准备好后，点开始探索。','真棒，找到了。',
 '再试一次，你可以的。','再观察一下，也可以点提示。',
 '看一看发光的图片，再试一次。','接着选下一个。',
 '这一步已经记住啦，接着选下一个。','又完成一次啦，真棒。',
 '这一课完成啦。学习进度已经保存。',
 '听一听，找到对应的汉字。','听句子，选出对应的汉字。',
 '听完这一页，点出场景里提到的汉字。',
 '日光照着大地。','月亮出来了。','树木长高了。',
]

def spoken_text(text):
    # Narrow same-sound aliases fix heteronyms without modifying displayed text.
    if text=='长':return '常'  # The course teaches 长短, cháng.
    return text.replace('长高','掌高').replace('长大','掌大')

def texts():
    result=set(UI_TEXTS)
    catalog=json.loads((ROOT/'curriculum.json').read_text())
    for lesson in catalog['lessons'].values():
        if lesson['type'] not in ['chinese','math']:continue
        for unit in lesson['units']:
            if lesson['type']=='chinese' and unit['section']=='words':
                result.add(unit['label'])
                result.add(f'听一听，找找“{unit["label"]}”这个字。')
            for q in unit['questions']:
                for field in ['speech','prompt']:
                    if q.get(field):result.add(q[field])
                if lesson['type']=='math' and q.get('hint'):result.add(q['hint'])
    return sorted(result)

async def main():
    folder=ROOT/'assets/audio/zh';folder.mkdir(parents=True,exist_ok=True)
    semaphore=asyncio.Semaphore(4)
    completed=0
    async def build(text):
        nonlocal completed
        spoken=spoken_text(text)
        name=hashlib.sha256((VERSION+RATE+spoken).encode()).hexdigest()[:24]+'.mp3'
        target=folder/name
        async with semaphore:
            if not target.exists() or target.stat().st_size<1000:
                temporary=target.with_suffix('.part')
                for attempt in range(3):
                    try:
                        await asyncio.wait_for(edge_tts.Communicate(spoken,voice=VOICE,rate=RATE).save(str(temporary)),60)
                        assert temporary.stat().st_size>1000,'Empty audio'
                        temporary.replace(target)
                        break
                    except Exception:
                        if attempt==2:raise
                        await asyncio.sleep(2*(attempt+1))
            completed+=1
            if completed%30==0:print(f'Generated {completed} Chinese clips',flush=True)
        return text,target.relative_to(ROOT).as_posix()
    mapping=dict(await asyncio.gather(*(build(text) for text in texts())))
    metadata={'id':VERSION,'name':'云夏','voice':VOICE,'rate':RATE,'pronunciationOverrides':{'长高':'zhang3','长大':'zhang3','长':'chang2'}}
    temporary=ROOT/'chinese-audio.js.tmp'
    temporary.write_text('globalThis.SproutChineseVoice='+json.dumps(metadata,ensure_ascii=False)+';\n'+'globalThis.SproutChineseAudio='+json.dumps(mapping,ensure_ascii=False)+';\n')
    temporary.replace(ROOT/'chinese-audio.js')
    print(f'Published {len(mapping)} Yunxia clips',flush=True)

if __name__=='__main__':asyncio.run(main())
