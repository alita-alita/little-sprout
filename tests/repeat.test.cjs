const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');const path=require('node:path');
function setup(extra={}){const ctx={document:{addEventListener(){}},...extra};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../repeat.js'),'utf8'),ctx);return ctx.SpeechRepeat;}
test('content scores handle case, punctuation, numerals and documented same-sound single characters',()=>{
  const r=setup();for(const [target,heard,expected] of [['Apple.','apple',100],['This is an apple.','This is an apple',100],['cat','car',67],['月','山',0],['一','1',100],['目','木',100],['树木长高了。','树木长高了',100],['banana','',0]])assert.equal(r.score(target,heard),expected);
});
test('recognition uses only final results; stopped and denied sessions cannot fabricate success',()=>{
  const instances=[],heard=[],errors=[];function Recognition(){instances.push(this);this.start=()=>this.onstart();this.abort=()=>{};}
  const r=setup({SpeechRecognition:Recognition});assert.equal(r.supported(),true);
  r.start({lang:'en-US',onstate(){},onresult:t=>heard.push(t),onerror:e=>errors.push(e)});assert.equal(instances[0].lang,'en-US');
  instances[0].onresult({results:[Object.assign([{transcript:'apple'}],{isFinal:false})]});assert.deepEqual(heard,[]);
  instances[0].onresult({results:[Object.assign([{transcript:'apple'}],{isFinal:true})]});assert.deepEqual(heard,['apple']);
  r.stop();instances[0].onresult({results:[Object.assign([{transcript:'banana'}],{isFinal:true})]});assert.deepEqual(heard,['apple']);
  r.start({lang:'zh-CN',onstate(){},onresult:t=>heard.push(t),onerror:e=>errors.push(e)});instances[1].onerror({error:'not-allowed'});assert.match(errors[0],/麦克风/);assert.equal(heard.length,1);
});
test('unsupported devices report the limitation without issuing a result',()=>{
  const r=setup();assert.equal(r.supported(),false);let message='';r.start({lang:'en-US',onresult:()=>assert.fail('no fabricated transcript'),onstate(){},onerror:e=>message=e});assert.match(message,/不支持/);
});
