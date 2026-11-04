/* Device speech, shared by learning and activity previews. No learning data stored here. */
(() => {
  const key='sprout-voice-v1';
  let preferences={english:'',chinese:'',pace:'natural'}, generation=0, timer, active, audio, settle, playerElement;
  try { Object.assign(preferences,JSON.parse(localStorage.getItem(key)||'{}')); } catch {}
  // Apply the selected course voice once, including browsers with old device-voice overrides.
  const courseVoice=globalThis.SproutEnglishVoice;
  if(courseVoice?.id&&preferences.courseVoiceVersion!==courseVoice.id){
    Object.assign(preferences,{english:'',pace:'natural',courseVoiceVersion:courseVoice.id});
    try{localStorage.setItem(key,JSON.stringify(preferences));}catch{}
  }
  const chineseVoice=globalThis.SproutChineseVoice;
  if(chineseVoice?.id&&preferences.chineseVoiceVersion!==chineseVoice.id){
    Object.assign(preferences,{chinese:'',chineseVoiceVersion:chineseVoice.id});
    try{localStorage.setItem(key,JSON.stringify(preferences));}catch{}
  }
  const clean=text=>String(text||'').replace(/[\p{Extended_Pictographic}\uFE0F\u200D]/gu,'').replace(/\s+/g,' ').trim();
  const status=text=>document.querySelectorAll?.('[data-voice-status]').forEach(el=>el.textContent=text);
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
  function stop(){generation++;clearTimeout(timer);if(settle){settle(false);settle=null;}active=null;if(audio){audio.pause();audio=null;}globalThis.speechSynthesis?.cancel();status('朗读已停止');}
  function play(parts,{slow=false,onerror=()=>{}}={}){
    stop();const id=generation,synth=globalThis.speechSynthesis;
    let sharedPlayer;
    const finished=new Promise(resolve=>settle=resolve);
    const finish=ok=>{if(id===generation&&settle){settle(ok);settle=null;if(audio===sharedPlayer)audio=null;}};
    const queue=parts.map(p=>({...p,text:clean(p.text)})).filter(p=>p.text);
    const clip=p=>p.lang==='en-US'&&!preferences.english?globalThis.SproutEnglishAudio?.[p.text]:p.lang==='zh-CN'&&!preferences.chinese?globalThis.SproutChineseAudio?.[p.text]:undefined;
    function read(index){
      if(id!==generation)return;
      if(index>=queue.length){status('播放结束，可以再听一次');finish(true);return;}
      const p=queue[index],path=clip(p);
      const advance=()=>{if(id===generation){active=null;timer=setTimeout(()=>read(index+1),p.pause??450);}};
      if(path){
        // Retain the gesture-authorized element across word and feedback clips.
        const player=sharedPlayer||(sharedPlayer=playerElement||(playerElement=new Audio(path)));
        if(player.src!==path)player.src=path;
        audio=player;
        player.hidden=true;player.setAttribute?.('data-sprout-player',p.lang);
        document.body?.appendChild?.(player);
        player.playbackRate=slow||(p.lang==='en-US'&&preferences.pace==='slow')?.85:1;player.preservesPitch=true;
        player.onplaying=()=>{if(id===generation)status(p.status||(p.lang==='zh-CN'?`正在播放 ${chineseVoice?.name||'课程'} 中文`:courseVoice?.name?`正在播放 ${courseVoice.name} 英语`:'正在播放课程英语'));};
        player.onended=advance;
        let failed=false;
        const fail=()=>{if(!failed&&id===generation){failed=true;status('声音未能播放，请点图片重听');finish(false);onerror(p.lang==='en-US'?'英文音频暂时没有播放，请点图片或“听英文”重试。':'中文音频暂时没有播放，请点选项或“再听一遍”重试。');}};
        player.onerror=fail;player.play().catch(fail);return;
      }
      if(!synth){finish(false);onerror('这台设备暂不支持当前语音。');return;}
      const u=new SpeechSynthesisUtterance(p.text),v=choose(p.lang||'zh-CN');
      u.lang=v?.lang||p.lang||'zh-CN';if(v)u.voice=v;
      u.rate=p.lang==='en-US'?(slow||preferences.pace==='slow'?.82:.96):.94;
      u.pitch=1;u.volume=1;active=u;
      u.onstart=()=>{if(id===generation)status(p.status||(p.lang==='en-US'?'正在朗读英语':'正在朗读中文'));};
      u.onend=advance;
      u.onerror=e=>{if(id===generation){finish(false);if(!['interrupted','canceled'].includes(e.error)){active=null;onerror('声音暂时没能播放，请重新试听或换一个声音。');}}};
      synth.speak(u);
    }
    // Some devices populate voices asynchronously. The generation guards prevent stale playback.
    if(synth&&!synth.getVoices().length&&!clip(queue[0]||{})){
      let waiting=true;
      const ready=()=>{if(!waiting)return;waiting=false;clearTimeout(fallback);synth.removeEventListener('voiceschanged',ready);if(id===generation)read(0);};
      const fallback=setTimeout(ready,800);synth.addEventListener('voiceschanged',ready);
    }else read(0);
    return finished;
  }
  function save(patch){Object.assign(preferences,patch);try{localStorage.setItem(key,JSON.stringify(preferences));}catch{}stop();}
  globalThis.SproutSpeech={play,stop,voices,choose,clean,save,get preferences(){return {...preferences};}};
  globalThis.addEventListener?.('pagehide',stop);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
})();
