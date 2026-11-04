const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');const path=require('node:path');
function setup(type='english'){
  const storage=new Map(),spoken=[],ctx={crypto:require('node:crypto').webcrypto,console,icon:()=>'',document:{addEventListener(){},querySelector:()=>({scrollTop:0})},SproutSpeech:{play:parts=>{spoken.push(parts);return Promise.resolve(true);},stop(){},preferences:{},voices:()=>[],choose:()=>null},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)}};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../study-model.js'),'utf8'),ctx);ctx.StudyModel.catalog=require('../curriculum.json');
  const lesson=ctx.StudyModel.lesson({lessonId:type+'-1'}),entry={lessonId:lesson.id,steps:{}};ctx.StudyModel.questions(lesson).forEach(q=>entry.steps[q.id]={correct:true});
  const plan={id:'test',records:{1:{study:{[type]:entry}}}},original=JSON.stringify(plan);let requests=0;
  ctx.SproutModel={stats:()=>({today:1,ended:false}),full:()=>true};vm.runInContext(fs.readFileSync(path.join(__dirname,'../study-ui.js'),'utf8'),ctx);
  const U=ctx.StudyUI;U.configure({plan:()=>plan,render(){},event:()=>{requests++;throw Error('Practice must not send study events');}});U.select(type,1);
  return {U,ctx,plan,original,lesson,spoken,requests:()=>requests};
}
test('replay resets answer controls, retries and hints without altering saved check-in',async()=>{
  const t=setup(),{U}=t;U.beginPractice();assert.match(U.render(),/复习练习/);assert.equal(Object.keys(U.practice.steps).length,0);
  const q=t.lesson.units[0].questions[0];await U.submit('answer',q.options.find(x=>x!==q.answer));assert.equal(U.practice.steps[q.id].correct,false);assert.doesNotMatch(U.render(),/data-study-action="next"/);
  await U.submit('hint');assert.equal(U.practice.steps[q.id].hinted,true);await U.submit('answer',q.answer);assert.equal(U.practice.steps[q.id].correct,true);assert.match(U.render(),/data-study-action="next"/);
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
  const t=setup(),{U}=t;U.beginPractice();for(const q of t.ctx.StudyModel.questions(t.lesson)){U.qid=q.id;await U.submit('answer',q.answer);await U.handle({dataset:{studyAction:'next'}});}
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
