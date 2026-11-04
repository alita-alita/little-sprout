/* Content matching only: this score does not assess pronunciation or accent. */
(() => {
  const digits={'0':'零','1':'一','2':'二','3':'三','4':'四','5':'五','6':'六','7':'七','8':'八','9':'九'};
  const normalize=text=>String(text||'').normalize('NFKC').toLowerCase().replace(/[0-9]/g,c=>digits[c]).replace(/[^\p{L}\p{N}]/gu,'');
  function score(target,heard){
    let a=normalize(target),b=normalize(heard);
    if(a==='目'&&b==='木'||a==='长'&&['常','肠','场','厂'].includes(b))b=a;
    if(!a||!b)return 0;
    let row=Array.from({length:b.length+1},(_,i)=>i);
    for(let i=1;i<=a.length;i++){const next=[i];for(let j=1;j<=b.length;j++)next[j]=Math.min(row[j]+1,next[j-1]+1,row[j-1]+(a[i-1]===b[j-1]?0:1));row=next;}
    return Math.round(100*(1-row[b.length]/Math.max(a.length,b.length)));
  }
  let active=null,serial=0,cancelNotice=null;
  const supported=()=>!!(globalThis.SpeechRecognition||globalThis.webkitSpeechRecognition);
  const stop=()=>{serial++;const old=active,notice=cancelNotice;active=null;cancelNotice=null;try{old?.abort();}catch{}notice?.();};
  function start({lang,onresult,onstate,onerror}){
    stop();const id=serial,Recognition=globalThis.SpeechRecognition||globalThis.webkitSpeechRecognition;
    if(!Recognition){onerror('当前浏览器不支持跟读识别，请家长在支持语音识别的 Chrome 或 Safari 中打开本机应用。');return;}
    const recognition=new Recognition();active=recognition;let received=false,failed=false;
    cancelNotice=()=>{if(!received&&!failed)onstate('idle');};
    recognition.lang=lang;recognition.continuous=false;recognition.interimResults=false;recognition.maxAlternatives=1;
    recognition.onstart=()=>{if(id===serial)onstate('listening');};
    recognition.onresult=event=>{if(id!==serial||received)return;const result=Array.from(event.results).find(r=>r.isFinal);if(result){received=true;onresult(result[0].transcript);}};
    recognition.onerror=event=>{if(id!==serial)return;failed=true;onerror(({ 'not-allowed':'麦克风还没获得允许，请家长开启浏览器的麦克风和语音识别权限后重试。','audio-capture':'没有找到可用的麦克风，请家长检查设备。','network':'语音识别暂时没有连上网络，请检查连接后再试。','no-speech':'还没听清，靠近麦克风，再读一遍吧。','language-not-supported':'当前设备不支持这门语言的语音识别，请家长检查浏览器语言服务。'})[event.error]||'这次没能听清，再试一次吧。');};
    recognition.onend=()=>{if(id===serial){active=null;cancelNotice=null;if(!received&&!failed)onerror('还没听清，点麦克风再读一遍吧。');}};
    try{onstate('starting');recognition.start();}catch{onerror('麦克风暂时没能启动，请重试。');}
  }
  globalThis.SpeechRepeat={normalize,score,supported,start,stop,finish:()=>{try{active?.stop();}catch{}}};
  globalThis.addEventListener?.('pagehide',stop);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
})();
