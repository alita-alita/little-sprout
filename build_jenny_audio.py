"""Build reusable JennyNeural audio; only public curriculum text is sent online.
Run: uv run --with edge-tts python build_jenny_audio.py
"""
import asyncio
import hashlib
import json
from pathlib import Path
import edge_tts

ROOT=Path(__file__).resolve().parent
VOICE='en-US-JennyNeural'
RATE='-12%'
VERSION='jenny-v1'

def texts():
    result={'Apple.','The banana is yellow.','Bear sees an apple. Bear takes it home.'}
    def visit(value):
        if isinstance(value,dict):
            if value.get('lang')=='en-US' and value.get('speech'):
                result.add(value['speech'])
            for item in value.values():visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(json.loads((ROOT/'curriculum.json').read_text()))
    return sorted(result)

async def main():
    folder=ROOT/'assets/audio/en';folder.mkdir(parents=True,exist_ok=True)
    semaphore=asyncio.Semaphore(4)
    completed=0
    async def build(text):
        nonlocal completed
        name=hashlib.sha256((VERSION+RATE+text).encode()).hexdigest()[:24]+'.mp3'
        target=folder/name
        async with semaphore:
            if not target.exists() or target.stat().st_size<1000:
                temporary=target.with_suffix('.part')
                for attempt in range(3):
                    try:
                        await asyncio.wait_for(edge_tts.Communicate(text,voice=VOICE,rate=RATE).save(str(temporary)),timeout=60)
                        assert temporary.stat().st_size>1000,'Audio is empty'
                        temporary.replace(target)
                        break
                    except Exception:
                        if attempt==2:raise
                        await asyncio.sleep(2*(attempt+1))
            completed+=1
            if completed%20==0:print(f'Generated {completed} clips',flush=True)
        return text,target.relative_to(ROOT).as_posix()
    mapping=dict(await asyncio.gather(*(build(text) for text in texts())))
    metadata={'id':VERSION,'name':'Jenny','voice':VOICE,'rate':RATE,'source':'Microsoft Edge online TTS'}
    # Publish the manifest only after all requested audio files have succeeded.
    temporary=ROOT/'english-audio.js.tmp'
    temporary.write_text('globalThis.SproutEnglishVoice='+json.dumps(metadata)+';\n'+'globalThis.SproutEnglishAudio='+json.dumps(mapping,ensure_ascii=False)+';\n')
    temporary.replace(ROOT/'english-audio.js')
    print(f'Published {len(mapping)} Jenny clips',flush=True)

if __name__=='__main__':asyncio.run(main())
