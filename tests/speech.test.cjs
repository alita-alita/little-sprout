const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function setup(list,extra={}){
  const played=[],tasks=new Map();let n=0,listener;
  const synth={getVoices:()=>list,speak:u=>played.push(u),cancel(){},addEventListener:(name,fn)=>listener=fn,removeEventListener(){}};
  const ctx={speechSynthesis:synth,SpeechSynthesisUtterance:function(text){this.text=text;},localStorage:{getItem:()=>null,setItem(){}},document:{addEventListener(){}},setTimeout:fn=>{tasks.set(++n,fn);return n;},clearTimeout:id=>tasks.delete(id),...extra};
  vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../speech.js'),'utf8'),ctx);
  return {api:ctx.SproutSpeech,played,setVoices:v=>{list=v;listener?.();},flush:()=>{const pending=[...tasks.values()];tasks.clear();pending.forEach(fn=>fn());}};
}
test('English uses an English enhanced voice, natural rate, and strips picture symbols',()=>{
  const voices=[{name:'Tingting',lang:'zh-CN',voiceURI:'zh'},{name:'English',lang:'en-US',voiceURI:'base'},{name:'Ava (Enhanced)',lang:'en-US',voiceURI:'ava'}],s=setup(voices);
  s.api.play([{text:'Apple 🍎.',lang:'en-US'}]);
  assert.equal(s.played[0].voice.voiceURI,'ava');assert.equal(s.played[0].rate,.96);assert.equal(s.played[0].text,'Apple .');
  s.api.save({english:'base'});s.api.play([{text:'Apple.',lang:'en-US'}],{slow:true});assert.equal(s.played[1].voice.voiceURI,'base');assert.equal(s.played[1].rate,.82);
});
test('stop prevents both the next queued phrase and delayed voice loading from resuming',()=>{
  const s=setup([{name:'Ava',lang:'en-US',voiceURI:'ava'}]);
  s.api.play([{text:'Apple.',lang:'en-US'},{text:'Banana.',lang:'en-US'}]);s.played[0].onend();s.api.stop();s.flush();assert.equal(s.played.length,1);
  const delayed=setup([]);delayed.api.play([{text:'Old.',lang:'en-US'}]);delayed.api.stop();delayed.setVoices([{name:'Ava',lang:'en-US',voiceURI:'ava'}]);delayed.flush();assert.equal(delayed.played.length,0);
});
test('rapid replay cancels stale queue while retaining current playback',()=>{
  const s=setup([{name:'Ava',lang:'en-US',voiceURI:'ava'}]);
  s.api.play([{text:'Old.',lang:'en-US'},{text:'Stale.',lang:'en-US'}]);const old=s.played[0];s.api.play([{text:'New.',lang:'en-US'}]);old.onend();s.flush();assert.deepEqual(s.played.map(u=>u.text),['Old.','New.']);
});

test('bundled English plays without browser voices and stops on exit',()=>{
  const clips=[];
  function Audio(path){this.src=path;this.play=()=>{clips.push(this);return Promise.resolve();};this.pause=()=>{this.paused=true;};}
  const s=setup([],{Audio,SproutEnglishAudio:{'Apple.':'assets/audio/en/apple.wav'}});
  s.api.play([{text:'Apple.',lang:'en-US'}]);assert.equal(clips.length,1);assert.equal(s.played.length,0);assert.equal(clips[0].playbackRate,1);
  s.api.stop();assert.equal(clips[0].paused,true);
  s.api.play([{text:'Apple.',lang:'en-US'}],{slow:true});assert.equal(clips[1].playbackRate,.85);
});
test('selected Jenny course voice replaces old device preferences once and keeps audition speed',()=>{
  let stored=JSON.stringify({english:'old-device',pace:'slow'});const clips=[];
  function Audio(path){this.src=path;this.play=()=>{clips.push(this);return Promise.resolve();};this.pause=()=>{};}
  const s=setup([],{Audio,SproutEnglishVoice:{id:'jenny-v1',name:'Jenny'},SproutEnglishAudio:{'Apple.':'assets/audio/en/jenny.mp3'},localStorage:{getItem:()=>stored,setItem:(k,v)=>stored=v}});
  assert.equal(s.api.preferences.english,'');assert.equal(s.api.preferences.pace,'natural');assert.equal(JSON.parse(stored).courseVoiceVersion,'jenny-v1');
  s.api.play([{text:'Apple.',lang:'en-US'}]);assert.equal(clips[0].src,'assets/audio/en/jenny.mp3');assert.equal(clips[0].playbackRate,1);assert.equal(s.played.length,0);
  const existing=JSON.stringify({...JSON.parse(stored),pace:'slow',english:'chosen-later'});
  const next=setup([],{SproutEnglishVoice:{id:'jenny-v1',name:'Jenny'},localStorage:{getItem:()=>existing,setItem:()=>assert.fail('Must not reset preferences again')}});
  assert.equal(next.api.preferences.english,'chosen-later');assert.equal(next.api.preferences.pace,'slow');
});
test('Yunxia reads Chinese course and choice audio without changing Jenny or inheriting English slow speed',()=>{
  const clips=[];let stored=JSON.stringify({english:'my-English',chinese:'old-Chinese',pace:'slow'});
  function Audio(path){this.src=path;this.play=()=>{clips.push(this);return Promise.resolve();};this.pause=()=>{};}
  const s=setup([],{Audio,SproutChineseVoice:{id:'yunxia-v1',name:'云夏'},SproutChineseAudio:{'月':'assets/audio/zh/moon.mp3','树木长高了。':'assets/audio/zh/grow.mp3'},localStorage:{getItem:()=>stored,setItem:(k,v)=>stored=v}});
  assert.equal(s.api.preferences.chinese,'');assert.equal(s.api.preferences.english,'my-English');assert.equal(s.api.preferences.pace,'slow');
  s.api.play([{text:'月',lang:'zh-CN'}]);assert.equal(clips[0].src,'assets/audio/zh/moon.mp3');assert.equal(clips[0].playbackRate,1);assert.equal(s.played.length,0);
  s.api.play([{text:'树木长高了。',lang:'zh-CN'}]);assert.equal(clips[1].src,'assets/audio/zh/grow.mp3');
});
test('playback completion waits for actual audio end; replay cancels the previous completion',async()=>{
  const clips=[];
  function Audio(path){this.src=path;this.play=()=>{clips.push(this);return Promise.resolve();};this.pause=()=>{};}
  const s=setup([],{Audio,SproutEnglishAudio:{'yellow':'yellow.mp3'}});
  let done=false;const result=s.api.play([{text:'yellow',lang:'en-US'}]).then(ok=>{done=true;return ok;});
  await Promise.resolve();assert.equal(done,false);clips[0].onended();s.flush();assert.equal(await result,true);
  const old=s.api.play([{text:'yellow',lang:'en-US'}]);s.api.play([{text:'yellow',lang:'en-US'}]);assert.equal(await old,false);
});
test('word and spoken feedback reuse the same gesture-authorized audio element in order',async()=>{
  const players=[],paths=[];
  function Audio(path){this.src=path;players.push(this);this.play=()=>{paths.push(this.src);return Promise.resolve();};this.pause=()=>{};}
  const s=setup([],{Audio,SproutEnglishAudio:{'yellow':'yellow.mp3'},SproutChineseAudio:{'真棒':'feedback.mp3'}});
  const finished=s.api.play([{text:'yellow',lang:'en-US'},{text:'真棒',lang:'zh-CN'}]);
  assert.deepEqual(paths,['yellow.mp3']);players[0].onended();s.flush();assert.deepEqual(paths,['yellow.mp3','feedback.mp3']);assert.equal(players.length,1);
  players[0].onended();s.flush();assert.equal(await finished,true);
});
