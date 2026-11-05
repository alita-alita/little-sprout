(() => {
  const U={subject:'english',day:1,screen:'map',qid:null,pending:null,error:'',feedback:'',review:false,practice:null,repeatState:'idle',repeatError:'',api:null};
  const S=StudyModel,M=SproutModel;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const symbolStyle=x=>{const n=Array.from(x.replace(/[\uFE0F\u200D]/g,'')).length;return n>1?'--symbol-size:'+(n>2?25:34)+'px':'';};
  const I=name=>icon(name),names={english:'英语小世界',chinese:'汉字小世界',math:'思维小探险'};
  const savedEntry=()=>S.entry(U.api.plan(),U.day,U.subject);
  const entry=()=>U.practice&&(U.api.practiceEvent?U.api.practice():U.practice)||savedEntry();
  const practiceKey=()=>`sprout-practice:${U.api.plan().id}:${U.day}:${U.subject}:${savedEntry()?.lessonId}`;
  const savePractice=()=>{if(U.api.practiceEvent)return;try{localStorage.setItem(practiceKey(),JSON.stringify(U.practice));}catch{}};
  U.syncPractice=()=>{
    if(!U.api.practiceEvent)return;
    const latest=U.api.practice();
    if(U.practice||latest&&!S.complete(latest)){
      if(latest?.roundId!==U.practice?.roundId){U.qid=null;U.screen='map';}
      U.practice=latest||null;
    }
  };
  U.beginPractice=async(action='start')=>{
    if(!S.complete(savedEntry()))return;
    if(U.api.practiceEvent){
      if(!U.pending)U.pending={eventId:crypto.randomUUID(),action,planId:U.api.plan().id,day:U.day,subject:U.subject,...(action==='import'?{entry:U.legacy}:{})};
      U.error='';const result=await U.api.practiceEvent(U.pending);
      if(!result){U.error='复习尚未确认保存，请重试；原学习记录不会改变。';U.api.render();return;}
      U.pending=null;U.practice=U.api.practice();U.legacy=null;
    }else U.practice={lessonId:savedEntry().lessonId,steps:{},repeatRequired:languageChoices()};
    U.review=false;U.error='';U.feedback='';U.screen='question';U.qid=next()?.id||all()[0]?.id;savePractice();U.api.render();U.listen();
  };
  const lesson=()=>S.lesson(entry());
  const all=()=>S.questions(lesson());
  U.choiceWord=value=>{
    if(U.subject==='math')return value;
    const l=lesson(),words=l?.units.filter(u=>u.section==='words')||[];
    for(let i=0;i<words.length;i++){
      if(words[i].questions.some(q=>q.answer===value))return words[i].label;
      const sentence=l.units.filter(u=>u.section==='sentences')[i];
      if(sentence?.questions.some(q=>q.answer===value))return words[i].label;
    }
    return value;
  };
  U.optionLabel=value=>U.subject==='chinese'?U.choiceWord(value):value;
  const languageChoices=()=>U.subject==='english'||U.subject==='chinese';
  // Simplified visual associations, not facsimiles of historical inscriptions.
  const pictographs={
    '日':['<circle cx="40" cy="40" r="26"/><circle cx="40" cy="40" r="3" fill="currentColor"/>','圆圆的太阳'],
    '月':['<path d="M49 11C15 16 12 65 47 69C33 53 33 29 49 11Z"/><path d="M31 32L43 29M30 49L42 52"/>','弯弯的月亮'],
    '山':['<path d="M12 61V34L27 23V61M27 61L40 12L53 61M53 61V31L68 24V61ZM12 61H68"/>','连起来的山峰'],
    '水':['<path d="M40 10C24 25 54 36 39 49S30 62 39 71M18 19L25 29M57 19L63 28M15 49L23 57M57 51L65 61"/>','流动的水和水滴'],
    '木':['<path d="M40 10V70M40 29L20 41M40 29L60 41M40 46L17 60M40 46L63 60M40 65L28 73M40 65L52 73"/>','树干、树枝和树根'],
    '人':['<path d="M47 11L37 40L17 67M37 40L61 67"/>','侧身站立的人'],
    '口':['<path d="M15 29Q40 17 65 29L62 57Q40 65 18 57Z"/>','张开的嘴'],
    '目':['<path d="M9 40Q40 10 71 40Q40 70 9 40Z"/><circle cx="40" cy="40" r="12"/>','眼睛的轮廓'],
    '手':['<path d="M39 70V21M39 39L23 25M39 43L58 25M39 54L18 42M39 56L64 42"/>','伸开的手指'],
    '足':['<path d="M47 10V48L31 61L16 64V70H58L62 61M27 19H53M39 32H55"/>','腿和脚的轮廓'],
    '羊':['<path d="M27 29C8 25 11 8 23 13L33 27M53 29C72 25 69 8 57 13L47 27M24 33L40 63L56 33ZM40 30V72M29 46H51"/>','弯角的羊头'],
    '牛':['<path d="M16 13Q17 30 40 30Q63 30 64 13M40 16V70M21 44H59M25 59H55"/>','牛角和牛头'],
    '鸟':['<path d="M47 20C51 8 34 8 30 22L28 38L17 53Q38 68 57 48L57 35L70 32L56 26M30 41L46 38M34 62L30 71M47 59L50 69M18 53L10 64"/><circle cx="44" cy="22" r="2" fill="currentColor"/>','鸟头、翅膀和尾巴'],
    '鱼':['<path d="M40 10L23 29L26 54L40 64L54 54L57 29ZM40 64L23 74M40 64L57 74M26 34H54M26 46H54M40 24V57"/>','鱼身、鱼鳞和鱼尾'],
    '门':['<path d="M12 69V15H68V69M39 16V68M17 28H33M47 28H63M17 42H33M47 42H63"/>','左右两扇门'],
    '米':['<path d="M40 13V67M13 40H67M20 20L27 27M53 53L60 60M20 60L27 53M53 27L60 20"/>','散开的米粒']
  };
  U.pictograph=(character,caption=true)=>{const data=pictographs[character];return data?`<span class="pictograph"><svg viewBox="0 0 80 80" role="img" aria-label="${esc(character)}的象形联想：${esc(data[1])}" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">${data[0]}</svg>${caption?'<small>象形示意</small>':''}</span>`:'';};
  U.wordVisual=q=>`<div class="character-visual" aria-label="象形字与代表图片">${U.pictograph(q.display,false)}<span class="character-picture" role="img" aria-label="${esc(q.display)}代表的图片">${esc(q.cue||q.answer)}</span></div>`;
  U.choiceSpeech=(answer,feedback)=>SproutSpeech.play([{text:U.choiceWord(answer),lang:U.subject==='english'?'en-US':'zh-CN',pause:550,status:U.subject==='english'?'Jenny · '+U.choiceWord(answer):'正在读：'+U.choiceWord(answer)},{text:feedback,lang:'zh-CN'}],{onerror:U.voiceError});
  const prompt=q=>U.subject!=='chinese'?q.prompt:q.kind==='story'?'听完这一页，点出场景里提到的汉字。':q.id.startsWith('w')?'听一听，找到对应的汉字。':'听句子，选出对应的汉字。';
  const hint=q=>U.subject==='chinese'?`听一听，找找“${U.optionLabel(q.answer)}”这个字。`:q.hint;

  const next=()=>all().find(q=>!entry()?.steps?.[q.id]?.correct);
  const bar=(a,b)=>`<div class="progress-track" role="progressbar" aria-label="学习进度" aria-valuemin="0" aria-valuemax="${b}" aria-valuenow="${a}"><i style="width:${b?100*a/b:0}%"></i></div>`;
  U.configure=api=>U.api=api;
  U.repeatSummary=e=>{const attempts=Object.values(e?.steps||{}).map(s=>s.repeat).filter(Boolean);return attempts.length?` · 跟读${attempts.length}步 · 平均匹配${Math.round(attempts.reduce((sum,r)=>sum+r.score,0)/attempts.length)}分`:'';};
  U.focusRepeat=()=>document.querySelector('.repeat-panel')?.scrollIntoView?.({behavior:'smooth',block:'center'});
  U.cards=(p,d)=>`<section class="self-study"><div class="section-heading"><h3>自己学一会儿</h3><span>可分几次完成</span></div><div class="study-cards">${p.study.subjects.map(type=>{const e=S.entry(p,d,type),done=S.complete(e),n=type==='math'?5:11,meta=M.subjects[type];return `<button class="study-card ${meta.color}" data-study-action="open" data-subject="${type}" data-day="${d}" ${M.stats(p).pending||M.stats(p).ended?'disabled':''}><span class="study-card-icon">${I(meta.icon)}</span><span class="study-card-copy"><strong>${names[type]}</strong><small>${type==='math'?'5个思维小挑战':'5'+(type==='english'?'单词':'汉字')+' · 5句子 · 1'+(type==='english'?'故事':'场景')}</small>${bar(S.unitCount(e),n)}<span class="study-card-status">${done?'今天这科已完成':e?`已完成${S.unitCount(e)}/${n}个单元 · 继续学习`:'点一下，开始探索'}</span></span><span class="task-arrow">${I(done?'check':'arrow')}</span></button>`;}).join('')}</div><p class="study-rule">${M.full(p,d)?'今天的学习目标已完成，已自动打卡。':'完成所选方向的学习后自动打卡，运动独立记录。'}</p></section>`;
  U.records=(p,d)=>{const details=S.detail(p,d);if(!details.length)return '<p class="muted-info">这天还没有自主学习记录。</p>';return `<div class="study-day-records">${details.map(x=>`<button data-study-action="history" data-subject="${x.type}" data-day="${d}" class="study-record-row"><span>${I(M.subjects[x.type].icon)}<strong>${M.subjects[x.type].label}</strong><small>${esc(x.lesson.phase)} · ${esc(x.lesson.theme)}${esc(U.repeatSummary(x.entry))}</small></span><b>${x.units}/${x.type==='math'?5:11}${x.done?' ✓':''}</b></button>`).join('')}</div>`;};
  U.growth=p=>{const totals={words:0,sentences:0,story:0,thinking:0},skills={},counts={direct:0,hinted:0,retried:0};Object.entries(p.records).forEach(([day,r])=>{Object.values(r.study||{}).forEach(e=>{const l=S.lesson(e);if(!l)return;l.units.forEach(u=>{const ok=u.questions.every(q=>e.steps?.[q.id]?.correct);if(ok&&u.questions.some(q=>{const time=e.steps?.[q.id]?.completedAt;return time&&Number.isFinite(Date.parse(time))&&new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(time))===M.add(p.start,Number(day)-1);}))totals[u.section]++;u.questions.forEach(q=>{const s=e.steps?.[q.id];if(!s?.correct||!s.completedAt||(!Number.isFinite(Date.parse(s.completedAt))||new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(s.completedAt))!==M.add(p.start,Number(day)-1)))return;if(s.hinted)counts.hinted++;else if(s.attempts)counts.retried++;else counts.direct++;if(q.ability)skills[q.ability]=(skills[q.ability]||0)+1;});});});});return `<section class="study-growth"><h3>自主学习的小脚印</h3><div class="study-growth-grid"><div><b>${totals.words}</b><small>词字单元练习</small></div><div><b>${totals.sentences}</b><small>句子单元练习</small></div><div><b>${totals.story}</b><small>故事与场景</small></div><div><b>${totals.thinking}</b><small>思维挑战</small></div></div><p>无额外提示${counts.direct}步 · 提示后${counts.hinted}步 · 重试后${counts.retried}步</p>${Object.keys(skills).length?`<div class="skill-tags">${Object.entries(skills).map(([k,v])=>`<span>${esc(k)} · ${v}次</span>`).join('')}</div>`:''}<small>以上为活动记录，包含复习次数，不代表已掌握字词或能力评分。</small></section>`;};
  U.select=(type,d)=>{globalThis.SpeechRepeat?.stop();U.repeatState='idle';U.repeatError='';U.subject=type;U.day=d;U.screen='map';U.qid=null;U.review=false;U.practice=null;U.legacy=null;U.feedback='';U.error='';U.pending=null;
    if(U.api.practiceEvent){const stored=U.api.practice();if(stored&&!S.complete(stored))U.practice=stored;}
    try{const stored=JSON.parse(localStorage.getItem(practiceKey())||'null');if(S.complete(savedEntry())&&stored?.lessonId===savedEntry().lessonId&&stored.steps&&typeof stored.steps==='object'&&!S.complete(stored)){if(U.api.practiceEvent){if(!U.api.practice())U.legacy=stored;}else U.practice=stored;}}catch{}
  };
  U.say=(prompt,foreign='',lang='zh-CN')=>SproutSpeech.play([{text:prompt,lang:'zh-CN'},{text:foreign,lang}],{onerror:U.voiceError});
  U.voiceError=text=>{const box=document.querySelector('.voice-error');if(box){box.textContent=text;box.hidden=false;}};
  U.listen=(slow=false,instruction=false)=>{if(U.screen==='map'){U.say('准备好后，点开始探索。');return;}const q=all().find(q=>q.id===U.qid)||next();if(q)SproutSpeech.play([{text:instruction?prompt(q):q.speech||prompt(q),lang:instruction?'zh-CN':q.lang||'zh-CN'}],{slow,onerror:U.voiceError});};
  function voiceSettings(){const p=SproutSpeech.preferences;return `<details class="voice-settings"><summary>家长 · 声音设置与试听</summary><p>英文默认使用课程离线音频（美式 ${esc(globalThis.SproutEnglishVoice?.name||'Samantha')} 合成声音）。中文默认使用${esc(globalThis.SproutChineseVoice?.name||'设备中文')}，也可选择这台设备的其他声音试听。</p>${[['english','en-US','英文声音'],['chinese','zh-CN','中文声音']].map(([key,lang,label])=>`<label>${label}<select data-voice-setting="${key}"><option value="">自动选择${key==='english'?' · 课程英语 '+esc(globalThis.SproutEnglishVoice?.name||'Samantha'):globalThis.SproutChineseVoice?' · 课程中文 '+esc(globalThis.SproutChineseVoice.name):SproutSpeech.choose(lang)?' · '+esc(SproutSpeech.choose(lang).name):' · 系统默认'}</option>${SproutSpeech.voices(lang).map(v=>`<option value="${esc(v.voiceURI)}" ${p[key]===v.voiceURI?'selected':''}>${esc(v.name)} · ${esc(v.lang)}</option>`).join('')}</select></label>`).join('')}<label>英文语速<select data-voice-setting="pace"><option value="natural" ${p.pace!=='slow'?'selected':''}>自然语速</option><option value="slow" ${p.pace==='slow'?'selected':''}>慢一点</option></select></label><div class="voice-tools"><button data-study-action="sample">试听英文</button><button data-study-action="sample-zh">试听中文</button><button data-study-action="stop">停止</button></div><small>设置保存在当前浏览器；学习进度照常保存。课程音频为合成配音，尚非真人教学录音。</small></details>`;}
  document.addEventListener('change',event=>{const key=event.target.dataset?.voiceSetting;if(key)SproutSpeech.save({[key]:event.target.value});});
  const readonly=()=>{if(U.practice)return false;const p=U.api.plan(),s=M.stats(p);return s.ended||s.today!==U.day||U.review;};
  function top(l){return `<header class="study-top"><button data-study-action="exit" aria-label="退出学习，保留进度">${I('back')}</button><div><strong>${names[U.subject]}</strong><small>第${l.index}课 · ${esc(l.phase)}</small></div><button data-study-action="listen" class="study-sound" aria-label="再听一遍">${I('speaker')}</button></header>`;}
  function map(){const l=lesson(),e=entry(),done=S.complete(e);if(!l)return `<section class="screen"><h2>正在找回学习进度</h2><button class="primary-btn" data-study-action="exit">回到今天</button></section>`;return `<section class="screen study-map">${top(l)}<div class="study-map-intro"><span class="study-bear">🐻</span><h2>${esc(l.theme)}</h2><p>${U.practice?'再练一遍，打卡记录会保留。':e.continued?'上次没做完的进度还在，我们接着来。':U.subject==='math'?'观察、试一试，找到自己的办法。':'从认识，到理解，再走进小故事。'}</p></div><div class="lesson-progress"><strong>${S.unitCount(e)} / ${l.units.length} 个单元</strong>${bar(S.unitCount(e),l.units.length)}</div>${(U.subject==='math'?['thinking']:['words','sentences','story']).map(section=>`<section class="unit-section"><h3>${({words:U.subject==='english'?'① 认识5个单词':'① 认识5个汉字',sentences:'② 理解5个句子',story:U.subject==='english'?'③ 走进1个故事':'③ 走进1个生活场景',thinking:'今天的5个思维挑战'})[section]}</h3><div class="unit-path ${section==='story'?'story-path':''}">${l.units.filter(u=>u.section===section).map((u,i)=>{const passed=u.questions.every(q=>e.steps?.[q.id]?.correct),first=u.questions.some(q=>q.id===next()?.id);return `<div class="unit-node ${passed?'passed':first?'current':''}"><span>${passed?I('check'):section==='story'?I('book'):i+1}</span><small>${section==='words'?esc(u.label):section==='thinking'?esc(u.label):section==='story'?U.subject==='chinese'?'3段话 · 听场景认汉字':'3幅画 · 听故事做互动':`句子${i+1}`}</small></div>`;}).join('')}</div></section>`).join('')}${voiceSettings()}${U.legacy?'<button class="secondary-btn" data-study-action="import-practice">把这台设备的旧复习进度同步到家庭记录</button>':''}${U.error?`<div class="study-save-error" role="alert">${esc(U.error)}<button class="secondary-btn" data-study-action="retry">重试保存</button></div>`:''}<p class="voice-playback-status" data-voice-status role="status"></p><p class="voice-error" role="status" hidden></p><div class="study-map-actions"><button class="primary-btn" data-study-action="start">${S.complete(savedEntry())&&(!U.practice||S.complete(U.practice))?'再来一次':U.practice?'继续复习':readonly()?'查看这一课':Object.keys(e.steps||{}).length?'接着学':'开始探索'}${I('arrow')}</button><button class="secondary-btn" data-study-action="exit">${readonly()?'返回记录':'先休息，进度会保留'}</button></div>${S.complete(savedEntry())?'<p class="study-rule">可以重复练习，原打卡保留，不重复计数。'+(U.api.practiceEvent?'复习进度随家庭记录保存，可换设备继续。':'复习进度保存在当前浏览器。')+'</p>':readonly()?'<p class="study-rule">历史记录仅供回顾，不补打卡。</p>':''}</section>`;}
  function options(q,s){if(q.kind==='grid')return `<div class="thinking-grid">${q.grid.map((cell,i)=>`<button data-study-action="answer" data-answer="${i}" class="grid-square ${String(i)===q.highlight&&s.hinted?'hint-glow':''} ${s.correct&&String(i)===q.answer?'right':''}" ${!q.options.includes(String(i))||s.correct||readonly()?'disabled':''} aria-label="第${Math.floor(i/3)+1}行第${i%3+1}列${cell?'，'+esc(cell):''}">${cell||'<span class="grid-dot"></span>'}</button>`).join('')}</div>`;if(q.kind==='order')return `<div class="order-progress" aria-label="已选顺序">${(s.order||[]).map((x,i)=>`<span>${i+1} · ${esc(x)}</span>`).join('')||'先找最小的圆形'}</div><div class="answer-options order-options">${q.options.map(x=>`<button data-study-action="answer" data-answer="${esc(x)}" ${(s.order||[]).includes(x)||s.correct||readonly()?'disabled':''} aria-label="${esc(x)}"><svg width="84" height="84" viewBox="0 0 90 90" aria-hidden="true"><circle cx="45" cy="45" r="${q.sizes[x]/2}" fill="#c7d9a9" stroke="#72915e" stroke-width="2"/></svg></button>`).join('')}</div>`;return `<div class="answer-options ${U.subject==='chinese'?'character-options':''} ${q.options.length===2?'two-options':''}">${q.options.map(x=>`<button class="answer-tile ${s.correct&&x===q.answer?'right':''} ${s.hinted&&x===q.answer?'hint-glow':''}" data-study-action="${languageChoices()&&(s.correct||s.choiceCorrect||readonly())?'pronounce':'answer'}" data-answer="${esc(x)}" ${!languageChoices()&&(s.correct||s.choiceCorrect||readonly())?'disabled':''} aria-label="${languageChoices()&&(s.correct||s.choiceCorrect||readonly())?'朗读':'选择'} ${esc(languageChoices()&&(s.correct||s.choiceCorrect||readonly())?U.choiceWord(x):U.optionLabel(x))}"><span style="${U.subject==='chinese'?'':symbolStyle(x)}">${esc(U.optionLabel(x))}</span>${s.correct&&x===q.answer?I('check'):''}</button>`).join('')}</div>`;}
  function question(){const l=lesson(),e=entry(),q=all().find(x=>x.id===U.qid)||next();if(!q)return finish();U.qid=q.id;const s=e.steps?.[q.id]||{},unit=l.units.find(u=>u.questions.some(x=>x.id===q.id)),pos=l.units.indexOf(unit)+1,story=unit.section==='story';return `<section class="screen study-question">${top(l)}${U.practice?'<p class="study-rule">复习练习 · 原打卡已保留</p>':''}<div class="study-mini-progress"><span>${story?`${U.subject==='chinese'?'场景':'故事'}第${unit.questions.indexOf(q)+1}/3页`:U.subject==='math'?`思维挑战${pos}/5`:`${unit.section==='words'?U.subject==='english'?'单词':'汉字':'句子'} ${unit.section==='words'?pos:pos-5}/5`}</span><span>${S.unitCount(e)}/${l.units.length}</span></div>${bar(S.unitCount(e),l.units.length)}<h2 class="question-prompt">${esc(prompt(q))}</h2>${q.scene?`<div class="story-scene ${U.subject==='chinese'?'character-scene':''}" aria-label="${U.subject==='chinese'?'场景中的汉字':'故事场景'}">${esc(U.subject==='chinese'?l.units.filter(u=>u.section==='words').map(u=>u.label).join(' · '):q.scene)}</div>`:''}${U.subject==='chinese'&&unit.section==='words'?U.wordVisual(q):`<div class="question-display ${unit.section==='words'?'word-display':''} ${U.subject==='chinese'?'chinese-display':''}"><span>${esc(q.display)}</span></div>`}<div class="voice-controls"><button class="listen-button" data-study-action="listen">${I('speaker')}${U.subject==='english'?'听英文':'再听一遍'}</button>${U.subject==='english'?'<button data-study-action="slow">慢一点</button>':''}<button data-study-action="instruction">听题目</button><button data-study-action="stop" aria-label="停止朗读">停止</button></div><p class="voice-playback-status" data-voice-status role="status"></p><p class="voice-error" role="status" hidden></p>${options(q,s)}<div class="answer-feedback ${s.correct?'success':''}" role="status">${s.correct?U.practice?'找到了！复习进度已保留。':'找到了！这一步已经保存。':s.choiceCorrect?'图片找对啦，接下来听一听、跟我读。':s.hinted?esc(hint(q)):U.feedback==='try'?'再观察一下，可以点提示。':U.feedback==='piece'?'这一小步已经保存，接着选下一个。':'听一听，再点选你的答案。'}</div>${repeatPanel(q,s)}${U.error?`<div class="study-save-error" role="alert"><p>${esc(U.error)}</p><button class="secondary-btn" data-study-action="retry">重试保存</button></div>`:''}<div class="question-actions">${s.correct||readonly()?`<button class="primary-btn" data-study-action="next">${all().at(-1).id===q.id?'看看今天的收获':'继续'}${I('arrow')}</button>`:s.choiceCorrect?'':`<button class="secondary-btn" data-study-action="hint">${I('bulb')}给我一点提示</button>`}<button class="rest-button" data-study-action="map">回到学习地图，先休息</button></div></section>`;}
  function repeatPanel(q,s){
    if(!languageChoices()||!s.choiceCorrect)return '';
    const result=s.repeat,busy=['starting','listening','saving'].includes(U.repeatState),supported=SpeechRepeat.supported(),locked=readonly();
    return `<section class="repeat-panel" aria-label="跟读练习"><h3>${s.correct?'跟读过关啦！':'轮到你读啦'}</h3><p class="repeat-target">${esc(q.speech)}</p><p class="repeat-description">听示范，再点麦克风跟读。内容匹配达到80分才能继续。</p>${result?`<div class="repeat-score ${result.passed?'passed':''}"><strong>${result.score}<small>分</small></strong><span>跟读匹配分 · ${result.passed?'已通过':'再试一次，你可以的'}</span><p>听到的是：${esc(result.transcript)}</p><small>已尝试${result.attempts}次 · 分数比较识别文字与目标内容，不评价音准。</small></div>`:''}${!s.correct&&!locked?`<button class="primary-btn repeat-mic" data-study-action="repeat-start" ${!supported||U.repeatState==='saving'?'disabled':''}>${U.repeatState==='listening'?'说完了，结束跟读':U.repeatState==='starting'?'正在打开麦克风…':U.repeatState==='saving'?'正在保存分数…':result?'再跟读一次':'点击开始跟读'}</button><p class="repeat-live" role="status">${U.repeatState==='listening'?'正在听，请读上面的内容…':U.repeatState==='saving'?'正在确认分数，请稍等…':''}</p>${!supported?'<p class="repeat-error">当前浏览器不支持语音识别，请家长在支持此功能的 Chrome 或 Safari 中打开本机应用。未识别成功不能跳过跟读。</p>':''}<small class="repeat-privacy">首次使用需家长允许麦克风。浏览器可能把声音发送到其语音服务识别，可能需要联网；本应用不录制、不保存音频，只保存识别文字、匹配分和次数。</small>`:''}${U.repeatError?`<p class="repeat-error" role="alert">${esc(U.repeatError)}</p>${U.pending?.action==='repeat'?'<button class="secondary-btn" data-study-action="retry">重试保存跟读结果</button>':''}`:''}</section>`;
  }
  U.saveRepeat=async transcript=>{
    const q=all().find(x=>x.id===U.qid);if(!q)return;
    U.repeatState='saving';U.repeatError='';
    if(U.practice&&!U.api.practiceEvent){
      const step=U.practice.steps[q.id];if(!step?.choiceCorrect||step.correct)return;
      const score=SpeechRepeat.score(q.speech,transcript);
      step.repeat={transcript,score,passed:score>=80,attempts:(step.repeat?.attempts||0)+1,updatedAt:new Date().toISOString(),method:'content-match-v1'};
      if(score>=80)step.correct=true;savePractice();
    }else{
      if(!U.pending)U.pending={action:'repeat',transcript,questionId:q.id,eventId:crypto.randomUUID(),planId:U.api.plan().id,day:U.day,subject:U.subject,...(U.practice?{roundId:U.practice.roundId}:{})};
      const result=await (U.practice&&U.api.practiceEvent?U.api.practiceEvent:U.api.event)(U.pending);
      if(U.practice&&result&&U.api.practiceEvent)U.practice=U.api.practice();
      if(!result){U.repeatState='error';U.repeatError='跟读结果暂时没能保存，点“重试保存跟读结果”，不用重读。';U.api.render();return;}
      U.pending=null;
    }
    U.repeatState='idle';U.api.render();U.focusRepeat();const passed=entry()?.steps?.[q.id]?.correct;
    U.say(passed?'真棒，找到了。':'再试一次，你可以的。');
  };
  U.startRepeat=()=>{
    const q=all().find(x=>x.id===U.qid),s=entry()?.steps?.[q?.id];
    if(!q||!s?.choiceCorrect||s.correct||readonly()||U.pending)return;
    if(U.repeatState==='listening'){SpeechRepeat.finish();return;}
    SproutSpeech.stop();U.repeatError='';const qid=q.id,subject=U.subject,day=U.day;
    const current=()=>U.screen==='question'&&U.qid===qid&&U.subject===subject&&U.day===day;
    SpeechRepeat.start({lang:U.subject==='english'?'en-US':'zh-CN',onstate:state=>{if(current()){U.repeatState=state;U.api.render();}},onresult:transcript=>{if(current())U.saveRepeat(transcript);},onerror:text=>{if(current()){U.repeatState='error';U.repeatError=text;U.api.render();}}});
  };
  function finish(){const p=U.api.plan(),l=lesson(),done=S.complete(entry()),daily=M.full(p,U.day);return `<section class="screen study-finish">${top(l)}<img src="assets/sprout.png" alt="小熊为你捧起一株小芽"><h2>${done?U.practice?'又完成一次，真棒！':'这一课，完成啦！':'小脚印，都记住了'}</h2><p>${names[U.subject]} · ${esc(l.theme)}</p><div class="finish-check">${I('check')}<strong>${U.practice?'复习完成，原打卡记录已保留':done?'学习结果已自动保存':'已有进度已保存'}</strong><span>${U.practice?'这次是复习练习，不重复计入打卡和成长统计。':readonly()?'这是已保存的学习回顾，不重复计数，也不补打卡。':daily?'今天所选方向已全部完成，已自动打卡。':'其他方向完成后，今天会自动打卡。运动可以另外记录。'}</span></div><p class="study-rule">用过提示也很棒。这里记录参与，不给能力打分。</p><button class="primary-btn" data-study-action="exit">回到今天${I('home')}</button>${done?'<button class="secondary-btn" data-study-action="replay">再来一次</button>':''}<button class="secondary-btn" data-study-action="map">看看这一课的脚印</button></section>`;}
  U.render=()=>U.screen==='question'?question():U.screen==='finish'?finish():map();
  U.submit=async(action,answer)=>{
    const q=all().find(x=>x.id===U.qid);if(!q)return;
    if(U.practice&&!U.api.practiceEvent){U.practiceAnswer(action,answer,q);return;}
    if(readonly())return;
    if(!U.pending)U.pending={action,answer,questionId:q.id,eventId:crypto.randomUUID(),planId:U.api.plan().id,day:U.day,subject:U.subject,...(U.practice?{roundId:U.practice.roundId}:{})};
    U.error='';
    // Start from the click gesture; network completion must not gate media playback.
    const selectedSubject=U.subject, selectedDay=U.day;
    const spoken=languageChoices()&&action==='answer'?U.choiceSpeech(answer,''):null;
    const result=await (U.practice&&U.api.practiceEvent?U.api.practiceEvent:U.api.event)(U.pending);
    if(U.practice&&result&&U.api.practiceEvent)U.practice=U.api.practice();
    if(!result){U.error='这一步暂时没能确认保存，先别退出，点下面重试。';U.api.render();return;}
    U.pending=null;U.feedback=result.feedback;U.api.render();if(entry()?.steps?.[q.id]?.choiceCorrect&&!entry()?.steps?.[q.id]?.correct)U.focusRepeat();
    const updated=entry()?.steps?.[q.id]||{};
    if(spoken){const played=await spoken;if(played&&U.screen==='question'&&U.qid===q.id&&U.subject===selectedSubject&&U.day===selectedDay)U.say((updated.correct||updated.choiceCorrect)?'真棒，找到了。':updated.hinted?hint(q):'再试一次，你可以的。');return;}
    if(result.feedback==='hint'||(result.feedback==='try'&&updated.hinted))U.say(U.subject==='chinese'?hint(q):q.kind==='order'||q.kind==='grid'?q.hint:'看一看发光的图片，再试一次。');
    else U.say((updated.correct||updated.choiceCorrect)?'真棒，找到了。':result.feedback==='piece'?'这一步已经记住啦，接着选下一个。':'再观察一下，也可以点提示。');
  };
  U.practiceAnswer=(action,answer,q)=>{
    if(q.id!==next()?.id)return;
    const step=U.practice.steps[q.id]||{correct:false,attempts:0,hinted:false,order:[]};
    if(action==='hint'){step.hinted=true;U.feedback='hint';}
    else if(action==='answer'){
      if(!q.options.includes(answer))return;
      const correct=q.kind==='order'?answer===q.answer[step.order.length]:answer===q.answer;
      if(correct){if(q.kind==='order')step.order.push(answer);step.correct=q.kind!=='order'||step.order.length===q.answer.length;U.feedback=step.correct?'correct':'piece';}
      else{step.attempts++;step.order=[];if(step.attempts>=2)step.hinted=true;U.feedback='try';}
    }else return;
    if(action==='answer'&&step.correct&&languageChoices()){step.choiceCorrect=true;step.repeatRequired=true;step.correct=false;}
    U.practice.steps[q.id]=step;savePractice();U.api.render();if(step.choiceCorrect&&!step.correct)U.focusRepeat();
    if(languageChoices()&&action==='answer'){U.choiceSpeech(answer,(step.correct||step.choiceCorrect)?'真棒，找到了。':step.hinted?hint(q):'再试一次，你可以的。');return;}
    U.say((step.correct||step.choiceCorrect)?'真棒，找到了。':U.feedback==='piece'?'接着选下一个。':step.hinted?U.subject==='chinese'?hint(q):q.kind==='order'||q.kind==='grid'?q.hint:'看一看发光的图片，再试一次。':'再试一次，你可以的。');
  };
  U.handle=async b=>{
    const action=b.dataset.studyAction;
    if(['listen','slow','instruction','pronounce','sample','sample-zh'].includes(action)&&['listening','starting'].includes(U.repeatState)){SpeechRepeat.stop();U.repeatState='idle';U.api.render();}
    if(action==='open'){U.select(b.dataset.subject,Number(b.dataset.day));const result=await U.api.event({eventId:crypto.randomUUID(),action:'open',planId:U.api.plan().id,day:U.day,subject:U.subject});if(result){U.api.navigate('study');U.say('我们来一起探索。准备好后，点开始探索。');}}
    else if(action==='history'){U.select(b.dataset.subject,Number(b.dataset.day));U.api.navigate('study');}
    else if(action==='replay')await U.beginPractice();
    else if(action==='import-practice')await U.beginPractice('import');
    else if(action==='retry'&&['start','import'].includes(U.pending?.action))await U.beginPractice(U.pending.action);
    else if(action==='start'){if(S.complete(savedEntry())&&(!U.practice||S.complete(U.practice))){U.beginPractice();return;}U.review=!U.practice&&(readonly()||S.complete(entry()));U.screen='question';U.qid=next()?.id||all()[0]?.id;U.feedback='';U.api.render();if(entry()?.steps?.[U.qid]?.choiceCorrect&&!entry()?.steps?.[U.qid]?.correct)U.focusRepeat();U.listen();}
    else if(action==='pronounce'&&languageChoices()){const q=all().find(q=>q.id===U.qid);if(q?.options.includes(b.dataset.answer))U.choiceSpeech(b.dataset.answer,'');}
    else if(action==='listen')U.listen();
    else if(action==='slow')U.listen(true);
    else if(action==='instruction')U.listen(false,true);
    else if(action==='stop')SproutSpeech.stop();
    else if(action==='sample')SproutSpeech.play([{text:'Apple.',lang:'en-US'},{text:'The banana is yellow.',lang:'en-US'},{text:'Bear sees an apple. Bear takes it home.',lang:'en-US'}],{onerror:U.voiceError});
    else if(action==='sample-zh')U.say('你好，我是小芽。我们一起听故事吧。');
    else if(action==='answer'&&!U.pending)await U.submit('answer',b.dataset.answer);
    else if(action==='hint'&&!U.pending)await U.submit('hint');
    else if(action==='repeat-start')U.startRepeat();
    else if(action==='retry'&&U.pending?.action==='repeat')await U.saveRepeat(U.pending.transcript);
    else if(action==='retry'&&U.pending)await U.submit(U.pending.action,U.pending.answer);
    else if(action==='next'){if(!readonly()&&!entry()?.steps?.[U.qid]?.correct)return;SpeechRepeat.stop();U.repeatState='idle';U.repeatError='';const q=all().find(x=>x.id===U.qid);if(readonly()){const i=all().indexOf(q);U.qid=all()[i+1]?.id;if(!U.qid)U.screen='finish';}else{U.qid=next()?.id;if(!U.qid)U.screen='finish';}U.feedback='';U.api.render();if(U.screen==='question')U.listen();else U.say(U.practice?'又完成一次啦，真棒。':'这一课完成啦。学习进度已经保存。');document.querySelector('#app').scrollTop=0;}
    else if(action==='map'){SpeechRepeat.stop();U.repeatState='idle';SproutSpeech.stop();U.screen='map';U.api.render();document.querySelector('#app').scrollTop=0;}
    else if(action==='exit'){SpeechRepeat.stop();U.repeatState='idle';SproutSpeech.stop();U.api.navigate('home');}
  };
  globalThis.StudyUI=U;
})();
