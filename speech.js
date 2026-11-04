/* Device speech, shared by learning and activity previews. No learning data stored here. */
(() => {
  const key='sprout-voice-v1';
  let preferences={english:'',chinese:'',pace:'natural'}, generation=0, timer, active, audio;
  try { Object.assign(preferences,JSON.parse(localStorage.getItem(key)||'{}')); } catch {}
  const clean=text=>String(text||'').replace(/[\p{Extended_Pictographic}\uFE0F\u200D]/gu,'').replace(/\s+/g,' ').trim();
  const voices=lang=>(globalThis.speechSynthesis?.getVoices()||[]).filter(v=>lang==='en-US'?/^en[-_]/i.test(v.lang):/^zh[-_](CN|Hans)/i.test(v.lang));
  function choose(lang){
    const list=voices(lang),saved=preferences[lang==='en-US'?'english':'chinese'];
    return list.find(v=>v.voiceURI===saved)||list.map((v,i)=>({v,i,score:
      (/premium|enhanced|natural|neural/i.test(v.name)?100:0)+
      (/Samantha|Alex|Ava|Allison|Zoe|Susan|Aria|Jenny|Xiaoxiao|Tingting/i.test(v.name)?30:0)+
      (v.lang.replace('_','-').toLowerCase()===lang.toLowerCase()?20:0)-
      (/novelty|whisper|bells|boing|bubbles|bad news|good news|trinoids|zarvox|wobble|organ|cellos|jester|robot/i.test(v.name)?200:0)
    })).sort((a,b)=>b.score-a.score||a.i-b.i)[0]?.v;
  }
  function stop(){generation++;clearTimeout(timer);active=null;if(audio){audio.pause();audio=null;}globalThis.speechSynthesis?.cancel();}
  function play(parts,{slow=false,onerror=()=>{}}={}){
    stop();const id=generation,synth=globalThis.speechSynthesis;
    const queue=parts.map(p=>({...p,text:clean(p.text)})).filter(p=>p.text);
    const clip=p=>p.lang==='en-US'&&!preferences.english&&globalThis.SproutEnglishAudio?.[p.text];
    function read(index){
      if(id!==generation||index>=queue.length)return;
      const p=queue[index],path=clip(p);
      const advance=()=>{if(id===generation){active=null;timer=setTimeout(()=>read(index+1),p.pause??450);}};
      if(path){
        const player=new Audio(path);audio=player;
        player.playbackRate=slow||preferences.pace==='slow'?.85:1;player.preservesPitch=true;
        player.onended=advance;
        let failed=false;
        const fail=()=>{if(!failed&&id===generation){failed=true;onerror('英文音频暂时没有播放，请点“听英文”重试。');}};
        player.onerror=fail;player.play().catch(fail);return;
      }
      if(!synth){onerror('这台设备暂不支持当前语音。');return;}
      const u=new SpeechSynthesisUtterance(p.text),v=choose(p.lang||'zh-CN');
      u.lang=v?.lang||p.lang||'zh-CN';if(v)u.voice=v;
      u.rate=p.lang==='en-US'?(slow||preferences.pace==='slow'?.82:.96):.94;
      u.pitch=1;u.volume=1;active=u;
      u.onend=advance;
      u.onerror=e=>{if(id===generation&&!['interrupted','canceled'].includes(e.error)){active=null;onerror('声音暂时没能播放，请重新试听或换一个声音。');}};
      synth.speak(u);
    }
    // Some devices populate voices asynchronously. The generation guards prevent stale playback.
    if(synth&&!synth.getVoices().length&&!clip(queue[0]||{})){
      let waiting=true;
      const ready=()=>{if(!waiting)return;waiting=false;clearTimeout(fallback);synth.removeEventListener('voiceschanged',ready);if(id===generation)read(0);};
      const fallback=setTimeout(ready,800);synth.addEventListener('voiceschanged',ready);
    }else read(0);
  }
  function save(patch){Object.assign(preferences,patch);try{localStorage.setItem(key,JSON.stringify(preferences));}catch{}stop();}
  globalThis.SproutSpeech={play,stop,voices,choose,clean,save,get preferences(){return {...preferences};}};
  globalThis.addEventListener?.('pagehide',stop);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
})();
