const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');const path=require('node:path');
function setup(type='english'){
  const storage=new Map(),spoken=[],ctx={crypto:require('node:crypto').webcrypto,console,icon:()=>'',document:{addEventListener(){},querySelector:()=>({scrollTop:0})},SproutSpeech:{play:parts=>{spoken.push(parts);return Promise.resolve(true);},stop(){},preferences:{},voices:()=>[],choose:()=>null},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)}};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../repeat.js'),'utf8'),ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../study-model.js'),'utf8'),ctx);ctx.StudyModel.catalog=require('../curriculum.json');
  const lesson=ctx.StudyModel.lesson({lessonId:type+'-1'}),entry={lessonId:lesson.id,steps:{}};ctx.StudyModel.questions(lesson).forEach(q=>entry.steps[q.id]={correct:true});
  const plan={id:'test',records:{1:{study:{[type]:entry}}}},original=JSON.stringify(plan);let requests=0;
  ctx.SproutModel={stats:()=>({today:1,ended:false}),full:()=>true};vm.runInContext(fs.readFileSync(path.join(__dirname,'../study-ui.js'),'utf8'),ctx);
  const U=ctx.StudyUI;U.configure({plan:()=>plan,render(){},event:()=>{requests++;throw Error('Practice must not send study events');}});U.select(type,1);
  return {U,ctx,plan,original,lesson,spoken,requests:()=>requests};
}
test('replay resets answer controls, retries and hints without altering saved check-in',async()=>{
  const t=setup(),{U}=t;U.beginPractice();assert.match(U.render(),/复习练习/);assert.equal(Object.keys(U.practice.steps).length,0);
  const q=t.lesson.units[0].questions[0];await U.submit('answer',q.options.find(x=>x!==q.answer));assert.equal(U.practice.steps[q.id].correct,false);assert.doesNotMatch(U.render(),/data-study-action="next"/);
  await U.submit('hint');assert.equal(U.practice.steps[q.id].hinted,true);await U.submit('answer',q.answer);assert.equal(U.practice.steps[q.id].choiceCorrect,true);assert.equal(U.practice.steps[q.id].correct,false);await U.saveRepeat(q.speech);assert.equal(U.practice.steps[q.id].correct,true);assert.match(U.render(),/data-study-action="next"/);
  assert.equal(JSON.stringify(t.plan),t.original);assert.equal(t.requests(),0);
  U.select('english',1);assert.equal(U.practice.steps[q.id].correct,true);
});
test('Chinese choices pronounce the selected character before feedback, including wrong choices and replay',async()=>{
  const t=setup('chinese'),{U}=t;U.beginPractice();const q=t.lesson.units[0].questions[0];
  assert.match(U.render(),/日的象形联想/);assert.match(U.render(),/象形字与代表图片/);const visual=U.wordVisual(q);assert.match(visual,/☀️/);assert.doesNotMatch(visual,/>日<|<small>/);
  const wrong=q.options.find(x=>x!==q.answer);await U.submit('answer',wrong);
  assert.equal(t.spoken.at(-1)[0].text,U.optionLabel(wrong));assert.equal(t.spoken.at(-1)[0].lang,'zh-CN');assert.match(t.spoken.at(-1)[1].text,/再试/);
  await U.submit('answer',q.answer);assert.equal(t.spoken.at(-1)[0].text,'日');assert.match(U.render(),/aria-label="朗读 日"/);
  const before=JSON.stringify(U.practice);await U.handle({dataset:{studyAction:'pronounce',answer:q.answer}});assert.equal(t.spoken.at(-1)[0].text,'日');assert.equal(JSON.stringify(U.practice),before);assert.equal(JSON.stringify(t.plan),t.original);
  U.practice=null;U.review=false;U.qid='w0';let requests=0;
  U.configure({plan:()=>t.plan,render(){},event:async()=>{requests++;return {feedback:'already'};}});
  await U.submit('answer',q.answer);assert.equal(requests,1);assert.equal(t.spoken.at(-2)[0].text,'日');assert.equal(t.spoken.at(-1)[0].text,'真棒，找到了。');
});
test('all replay questions can be completed and another fresh replay can begin',async()=>{
  const t=setup(),{U}=t;U.beginPractice();for(const q of t.ctx.StudyModel.questions(t.lesson)){U.qid=q.id;await U.submit('answer',q.answer);await U.saveRepeat(q.speech);await U.handle({dataset:{studyAction:'next'}});}
  assert.equal(U.screen,'finish');assert.match(U.render(),/又完成一次/);assert.match(U.render(),/再来一次/);assert.equal(JSON.stringify(t.plan),t.original);
  await U.handle({dataset:{studyAction:'replay'}});assert.equal(U.qid,'w0');assert.equal(Object.keys(U.practice.steps).length,0);
});
test('English image choices read their word first and remain replayable after a correct answer',async()=>{
  const t=setup(),{U}=t;U.beginPractice();const q=t.lesson.units[0].questions[0];
  const wrong=q.options.find(x=>x!==q.answer);await U.submit('answer',wrong);
  assert.equal(t.spoken.at(-1)[0].text,U.choiceWord(wrong));assert.equal(t.spoken.at(-1)[0].lang,'en-US');assert.match(t.spoken.at(-1)[1].text,/再试/);
  await U.submit('answer',q.answer);assert.equal(t.spoken.at(-1)[0].text,'apple');assert.match(U.render(),/aria-label="朗读 apple"/);
  const before=JSON.stringify(U.practice);await U.handle({dataset:{studyAction:'pronounce',answer:q.answer}});
  assert.equal(t.spoken.at(-1)[0].text,'apple');assert.equal(JSON.stringify(U.practice),before);assert.equal(JSON.stringify(t.plan),t.original);assert.equal(t.requests(),0);
  // Saved lessons and ordinary grading use the same pronunciation path.
  U.practice=null;U.review=false;U.qid='w0';let requests=0;
  U.configure({plan:()=>t.plan,render(){},event:async()=>{requests++;return {feedback:'already'};}});
  await U.submit('answer',q.answer);assert.equal(requests,1);assert.equal(t.spoken.at(-2)[0].text,'apple');assert.equal(t.spoken.at(-1)[0].text,'真棒，找到了。');
});
test('every English picture in words, sentences and stories maps to a bundled Jenny word',()=>{
  const t=setup();vm.runInContext(fs.readFileSync(path.join(__dirname,'../english-audio.js'),'utf8'),t.ctx);
  for(let i=1;i<=90;i++){
    t.plan.records[1].study.english.lessonId='english-'+i;
    const lesson=t.ctx.StudyModel.lesson(t.plan.records[1].study.english);
    for(const q of t.ctx.StudyModel.questions(lesson))for(const value of q.options){
      const word=t.U.choiceWord(value);assert.match(word,/^[a-z]+$/);assert.ok(t.ctx.SproutEnglishAudio[word],`${lesson.id} ${q.id} ${word}`);assert.equal(t.U.optionLabel(value),value);
    }
  }
});
test('ordinary learning starts word playback before saving and gives feedback only after playback finishes',async()=>{
  const t=setup(),{U}=t;U.screen='question';U.qid='w0';let finishWord,finishSave;const order=[];
  t.ctx.SproutSpeech.play=parts=>{order.push(parts[0].text);if(parts[0].lang==='en-US')return new Promise(resolve=>finishWord=resolve);return Promise.resolve(true);};
  U.configure({plan:()=>t.plan,render(){},event:()=>{order.push('save');return new Promise(resolve=>finishSave=resolve);}});
  const submission=U.submit('answer',t.lesson.units[0].questions[0].answer);
  assert.deepEqual(order,['apple','save']);finishSave({feedback:'correct'});await Promise.resolve();await Promise.resolve();assert.deepEqual(order,['apple','save']);
  finishWord(true);await submission;assert.deepEqual(order,['apple','save','真棒，找到了。']);
});
test('follow-along blocks next until an 80-point match and retains scores on reopening',async()=>{
  const t=setup(),{U}=t;U.beginPractice();const q=t.lesson.units[0].questions[0];await U.submit('answer',q.answer);
  assert.equal(U.practice.steps.w0.correct,false);assert.match(U.render(),/跟读练习/);assert.doesNotMatch(U.render(),/data-study-action="next"/);
  await U.handle({dataset:{studyAction:'next'}});assert.equal(U.qid,'w0');
  await U.saveRepeat('banana');assert.equal(U.practice.steps.w0.repeat.passed,false);assert.doesNotMatch(U.render(),/data-study-action="next"/);
  await U.saveRepeat('apple');assert.equal(U.practice.steps.w0.repeat.score,100);assert.equal(U.practice.steps.w0.repeat.attempts,2);assert.equal(U.practice.steps.w0.correct,true);
  U.select('english',1);assert.equal(U.practice.steps.w0.repeat.score,100);assert.equal(JSON.stringify(t.plan),t.original);
});
test('math ordering stores each practice selection and enforces order',()=>{
  const t=setup('math'),{U}=t;U.beginPractice();const lesson=t.ctx.StudyModel.catalog.lessons['math-6'];
  t.plan.records[1].study.math.lessonId=lesson.id;U.practice={lessonId:lesson.id,steps:{}};const q=t.ctx.StudyModel.questions(lesson)[0];assert.equal(q.kind,'order');U.qid=q.id;
  U.practiceAnswer('answer',q.answer[0],q);assert.equal(U.practice.steps[q.id].correct,false);assert.equal(U.practice.steps[q.id].order.length,1);
  U.practiceAnswer('answer',q.answer[1],q);assert.equal(U.practice.steps[q.id].correct,true);assert.equal(t.requests(),0);
});
test('all Chinese lessons show character choices while preserving stored answer identifiers',()=>{
  const t=setup('chinese'),{U}=t;
  for(let i=1;i<=90;i++){
    t.plan.records[1].study.chinese.lessonId='chinese-'+i;
    const lesson=t.ctx.StudyModel.lesson(t.plan.records[1].study.chinese),original=JSON.stringify(lesson);
    for(const q of t.ctx.StudyModel.questions(lesson))for(const value of q.options){
      assert.match(U.optionLabel(value),/^[\p{Script=Han}]+$/u,`lesson ${i} ${q.id} ${value}`);
    }
    U.screen='question';U.qid='p1';const rendered=U.render();assert.match(rendered,/场景里提到的汉字/);assert.match(rendered,/class="answer-options character-options/);assert.doesNotMatch(rendered,/aria-label="选择 [\p{Extended_Pictographic}]/u);
    assert.equal(JSON.stringify(lesson),original);
  }
});

test('cloud replay waits for server confirmation, retains retry IDs, and resumes on a fresh device',async()=>{
  const t=setup(),{U}=t;let confirmed=null,fail=true;const calls=[];
  U.configure({plan:()=>t.plan,render(){},event(){throw Error('Formal learning must not be modified');},practice:()=>confirmed,practiceEvent:async payload=>{
    calls.push(JSON.parse(JSON.stringify(payload)));
    if(fail)return null;
    if(payload.action==='start')confirmed={lessonId:t.lesson.id,steps:{},roundId:payload.eventId,roundNumber:1,repeatRequired:true};
    else if(payload.action==='answer')confirmed.steps.w0={correct:false,choiceCorrect:true,repeatRequired:true,attempts:0,hinted:false,order:[]};
    else if(payload.action==='repeat')confirmed.steps.w0={...confirmed.steps.w0,correct:true,repeat:{score:100,passed:true,transcript:payload.transcript,attempts:1}};
    return {feedback:payload.action==='repeat'?'repeat-pass':'repeat'};
  }});
  await U.beginPractice();assert.equal(U.practice,null);assert.ok(U.pending);assert.match(U.error,/未确认/);
  fail=false;await U.beginPractice();assert.equal(calls[0].eventId,calls[1].eventId);assert.equal(U.practice,confirmed);
  const q=t.lesson.units[0].questions[0];await U.submit('answer',q.answer);assert.equal(U.practice.steps.w0.correct,false);assert.equal(calls.at(-1).roundId,confirmed.roundId);
  await U.saveRepeat(q.speech);assert.equal(U.practice.steps.w0.correct,true);assert.equal(JSON.stringify(t.plan),t.original);
  U.select('english',1);assert.equal(U.practice.steps.w0.correct,true);assert.match(U.render(),/继续复习/);
});

test('another device can create or advance a replay round without being overwritten by browser storage',async()=>{
  const t=setup(),{U}=t;let current=null;
  U.configure({plan:()=>t.plan,render(){},practiceEvent:async()=>null,practice:()=>current});
  U.select('english',1);assert.equal(U.practice,null);
  current={lessonId:t.lesson.id,steps:{},roundId:'other-device'};U.syncPractice();assert.equal(U.practice.roundId,'other-device');
  U.qid='w0';current={lessonId:t.lesson.id,steps:{},roundId:'new-round'};U.syncPractice();assert.equal(U.qid,null);assert.equal(U.screen,'map');assert.equal(U.practice.roundId,'new-round');
});
test('generated picture uses its bound word before feedback and remains replayable',async()=>{
  const t=setup(),{U,ctx}=t;vm.runInContext(fs.readFileSync(path.join(__dirname,'../image-options.js'),'utf8'),ctx);
  // Clone the catalogue to keep this fixture out of the shared content used by other tests.
  ctx.StudyModel.catalog=JSON.parse(JSON.stringify(ctx.StudyModel.catalog));const l=ctx.StudyModel.lesson({lessonId:'english-1'}),q=l.units[0].questions[0];
  const id='pic_'+'a'.repeat(24);l.images={[id]:{word:'pineapple',lang:'en-US',src:'/assets/pictures/'+'a'.repeat(24)+'.png'}};q.options[0]=id;q.answer=id;q.display=q.speech='pineapple';l.units[0].label='pineapple';
  U.beginPractice();assert.match(U.render(),/class="option-picture"/);assert.equal(U.choiceWord(id),'pineapple');await U.submit('answer',id);assert.equal(t.spoken.at(-1)[0].text,'pineapple');assert.equal(t.spoken.at(-1)[0].lang,'en-US');assert.equal(U.practice.steps[q.id].choiceCorrect,true);assert.equal(U.practice.steps[q.id].correct,false);
  const before=JSON.stringify(U.practice);await U.handle({dataset:{studyAction:'pronounce',answer:id}});assert.equal(t.spoken.at(-1)[0].text,'pineapple');assert.equal(JSON.stringify(U.practice),before);
});

test('manual completion and parent scores work without microphone and remain separate from automatic scores',async()=>{
  for(const type of ['english','chinese']){
    const {U,lesson}=setup(type);U.beginPractice();const q=lesson.units[0].questions[0];await U.submit('answer',q.answer);
    assert.match(U.render(),/已读过，手动完成/);assert.match(U.render(),/保存评分并完成/);
    await U.manualRepeat(null);assert.equal(U.practice.steps[q.id].repeat.score,null);assert.equal(U.practice.steps[q.id].repeat.method,'parent-confirm-v1');assert.match(U.render(),/data-study-action="next"/);assert.doesNotMatch(U.repeatSummary(U.practice),/平均匹配/);
    await U.handle({dataset:{studyAction:'next'}});const q2=lesson.units[1].questions[0];await U.submit('answer',q2.answer);await U.manualRepeat(45);assert.equal(U.practice.steps[q2.id].correct,true);assert.equal(U.practice.steps[q2.id].repeat.score,45);assert.match(U.render(),/家长评分/);
  }
});

test('manual cloud save retains event ID and score on retry and never advances before acknowledgement',async()=>{
  const t=setup(),{U}=t;await U.beginPractice();const q=t.lesson.units[0].questions[0];await U.submit('answer',q.answer);let saved=U.practice,calls=[],fail=true;
  U.configure({plan:()=>t.plan,render(){},practice:()=>saved,practiceEvent:async body=>{calls.push({...body});if(fail)return null;saved.steps[q.id].repeat={method:body.method,score:body.score,passed:true,transcript:''};saved.steps[q.id].correct=true;return {feedback:'repeat-pass'};}});
  await U.manualRepeat(72);assert.equal(U.pending.method,'parent-score-v1');assert.equal(U.practice.steps[q.id].correct,false);assert.doesNotMatch(U.render(),/data-study-action="next"/);
  fail=false;await U.handle({dataset:{studyAction:'retry'}});assert.equal(calls[0].eventId,calls[1].eventId);assert.equal(calls[1].score,72);assert.equal(U.pending,null);assert.match(U.render(),/data-study-action="next"/);
});

test('authored Chinese and math previews use their own grading without saving learning records',async()=>{
  for(const type of ['chinese','math']){
    const t=setup(type),{U}=t;
    const lesson=JSON.parse(JSON.stringify(t.lesson));
    const q=lesson.units[0].questions[0];
    if(type==='math')Object.assign(q,{kind:'order',options:['小圆','中圆','大圆'],answer:['大圆','中圆','小圆'],
      sizes:{小圆:24,中圆:48,大圆:75},editableOrder:true});
    let reviewed=false;
    U.startPreview(lesson,result=>{reviewed=result;});
    assert.equal(U.subject,type);
    assert.match(U.render(),/家长试玩/);
    if(type==='chinese'){
      await U.submit('answer',q.answer);
      await U.manualRepeat(75);
    }else{
      await U.submit('answer','大圆');
      assert.match(U.render(),/撤销上一步/);
      await U.submit('undo-order');
      assert.equal(U.preview.entry.steps[q.id].order.length,0);
      for(const answer of q.answer)await U.submit('answer',answer);
    }
    assert.match(U.render(),/data-study-action="next"/);
    await U.handle({dataset:{studyAction:'preview-done'}});
    assert.equal(reviewed,true);
    assert.equal(t.requests(),0);
    assert.equal(JSON.stringify(t.plan),t.original);
  }
});
