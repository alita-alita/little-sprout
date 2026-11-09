"""Generate only missing editor speech; merge audio indexes without replacing old clips."""
import asyncio,hashlib,json,sys
from pathlib import Path
import edge_tts
ROOT=Path(__file__).resolve().parent
async def main():
    items=json.loads(Path(sys.argv[1]).read_text());semaphore=asyncio.Semaphore(3)
    async def build(item):
        lang,text=item['lang'],item['text'];english=lang=='en-US';voice='en-US-JennyNeural' if english else 'zh-CN-YunxiaNeural'
        spoken=text if english else ('常' if text=='长' else text.replace('长高','掌高').replace('长大','掌大'))
        name=hashlib.sha256((voice+'-12%'+spoken).encode()).hexdigest()[:24]+'.mp3'
        relative=Path('assets/audio')/('en' if english else 'zh')/name;target=ROOT/relative
        async with semaphore:
            if not target.exists() or target.stat().st_size<1000:
                temporary=target.with_suffix('.part');await edge_tts.Communicate(spoken,voice=voice,rate='-12%').save(str(temporary));assert temporary.stat().st_size>1000;temporary.replace(target)
        return lang,text,relative.as_posix()
    results=await asyncio.gather(*(build(item) for item in items))
    for lang,file,variable in [('en-US','english-audio.js','SproutEnglishAudio'),('zh-CN','chinese-audio.js','SproutChineseAudio')]:
        lines=(ROOT/file).read_text().splitlines();mapping=json.loads(lines[-1].split('=',1)[1].rstrip(';'))
        mapping.update({text:path for language,text,path in results if language==lang})
        temporary=ROOT/(file+'.tmp');temporary.write_text(lines[0]+'\n'+'globalThis.'+variable+'='+json.dumps(mapping,ensure_ascii=False)+';\n');temporary.replace(ROOT/file)
asyncio.run(main())
