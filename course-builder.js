(() => {
  'use strict';
  const B = {
    type: 'english', data: null, rows: null, stage: 'list', section: 'words',
    card: null, busy: false, dirty: false, reviewed: false, error: '', notice: ''
  };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c =>
    ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'})[c]);
  const button = (label, action, extra = '', style = 'secondary-btn') =>
    `<button type="button" class="${style}" data-build-action="${action}" ${extra}>${label}</button>`;
  const wordExamples = [['apple','苹果'], ['banana','香蕉'], ['orange','橙子'], ['red','红色'], ['yellow','黄色']];
  const sentenceExamples = [['This is an apple.','这是一个苹果。'], ['The banana is yellow.','香蕉是黄色的。'],
    ['This is an orange.','这是一个橙子。'], ['I see red.','我看到了红色。'], ['I see yellow.','我看到了黄色。']];
  const storyExamples = [['Bear sees an apple.','小熊看到了一个苹果。'], ['Bear picks a banana.','小熊挑了一根香蕉。'],
    ['Bear takes an orange home.','小熊带着一个橙子回家了。']];
  const goal = '认识3种水果和2种颜色，听懂简单句子，再跟着小熊逛水果店。';
  const stages = [['goal','学习目标'], ['content','编排内容'], ['materials','配图配音'], ['preview','试玩检查'], ['publish','发布安排']];
  const groups = [['words','单词卡'], ['sentences','简单句子'], ['story','场景故事']];
  const emptyDraft = () => ({
    theme:'水果店', phase:'入门认知', goal,
    words:wordExamples.map(() => ({en:'',cn:'',image:null})),
    sentences:sentenceExamples.map((_,ref) => ({en:'',cn:'',ref,review:false})),
    story:storyExamples.map((_,ref) => ({en:'',cn:'',ref,review:false}))
  });

  const subjectNames = {english:'英语', chinese:'汉字', math:'数学思维'};
  const subject = () => (B.data?.draft || B.newDraft)?.type || 'english';
  const mathNames = {count:'数一数',compare:'比大小',pattern:'找规律',order:'排序'};
  const today = () => SproutModel.date();
  const chineseExample = {
    words:['日','月','山','水','木'].map((cn,i)=>({cn,cue:['☀️','🌙','⛰️','💧','🌳'][i],other:''})),
    sentences:['太阳照在日历上。','月亮出来了。','我们看见一座山。','小鱼在水里游。','这里有一张木椅。'].map((cn,ref)=>({cn,ref,other:''})),
    story:['公园里有一座小山。','山下有一池水。','我们坐在木椅上休息。'].map((cn,i)=>({cn,ref:i+2,other:''}))
  };
  const mathExample = [
    {kind:'count',prompt:'数一数，有几个苹果？',symbol:'🍎',left:'4',choices:'3，4，5'},
    {kind:'compare',prompt:'哪边的梨更多？',symbol:'🍐',left:'3',right:'5',direction:'more'},
    {kind:'pattern',prompt:'问号处应该放什么？',sequence:'🍎，🍐，🍎，🍐',choices:'🍎，🍐',answer:'🍎'},
    {kind:'order',prompt:'从小到大点圆形。',direction:'asc'},
    {kind:'count',prompt:'数一数，有几根香蕉？',symbol:'🍌',left:'5',choices:'4，5，6'}
  ];
  function newDraft(type) {
    if (type==='english') return emptyDraft();
    const data = {type,theme:type==='chinese'?'逛公园':'水果篮',phase:'',goal:''};
    if(type==='math') return {...data,problems:mathExample.map(row=>({kind:row.kind,prompt:'',direction:row.direction||''}))};
    return {...data,...Object.fromEntries(groups.map(([key])=>[key,chineseExample[key].map(row=>({...row,cn:'',cue:''}))]))};
  }
  function selectField(label, name, value, options) {
    return `<label class="course-field">${label}<select data-build-field="${name}">${options.map(([id,title])=>
      `<option value="${esc(id)}" ${String(value)===String(id)?'selected':''}>${esc(title)}</option>`).join('')}</select></label>`;
  }

  function extraContent() {
    const draft = B.data.draft;
    const math = subject()==='math';
    const group = math?'problems':B.section;
    const labels = {words:'字卡',sentences:'短句',story:'场景'};
    const progress = key => draft[key].filter(row=>row.cn?.trim()).length;
    return `<div class="builder-panel"><h3>编排${subjectNames[subject()]}内容</h3>
      ${button(B.confirmExample?'确认覆盖当前内容':`填入《${math?'水果篮':'逛公园'}》范例`,'example')}
      ${B.confirmExample?button('保留当前内容','cancel-example'):''}
      ${math?'<p class="course-help">为每道题选择题型。数数和比较题会按数量显示物品。</p>':
        `<div class="course-view-tabs">${groups.map(([key])=>button(labels[key]+' '+progress(key)+'/'+draft[key].length,'group',`data-group="${key}"`,key===group?'active':'')).join('')}</div>`}
      ${draft[group].map((row,i)=>`<div class="builder-row" data-build-row="${i}">
        <strong>${math?'挑战':labels[group]} ${i+1}</strong>
        ${math?mathFields(row)+button('上移','move-up',`data-index="${i}" ${i===0?'disabled':''}`,'text-button')
          +button('下移','move-down',`data-index="${i}" ${i===4?'disabled':''}`,'text-button'):`${field(group==='words'?'目标汉字':group==='story'?'场景文字':'短句','cn',row.cn,group==='words'?1:200,group==='story')}
          ${group==='words'?'':selectField('目标字','ref',row.ref,draft.words.map((word,index)=>[index,word.cn||'字卡 '+(index+1)]))}
          ${field('干扰字（选填）','other',row.other,1)}
          ${group==='sentences'?'':field('图案（选填，可填表情符号）','cue',row.cue,12)}`}
      </div>`).join('')}
      ${button('孩子视角试玩','preview','','primary-btn')}
    </div>`;
  }

  function mathFields(row) {
    const kind = row.kind;
    let fields = '';
    if (kind==='count' || kind==='compare') {
      fields += field('物品图案','symbol',row.symbol,8);
      fields += field(kind==='count'?'物品数量（1至10）':'左边数量（1至10）','left',row.left,2);
    }
    if(kind==='compare') fields += field('右边数量（1至10）','right',row.right,2)
      +selectField('比较方向','direction',row.direction,[['','请选择'],['more','找更多'],['less','找更少']]);
    if(kind==='order') fields += selectField('排序方向','direction',row.direction,[['','请选择'],['asc','从小到大'],['desc','从大到小']]);
    if(kind==='pattern') fields += field('图案序列（逗号分隔）','sequence',row.sequence,80);
    if(kind==='count'||kind==='pattern') fields += field('选项（逗号分隔）','choices',row.choices,80);
    if(kind==='pattern') fields += field('正确选项','answer',row.answer,16);
    return selectField('题型','kind',kind,Object.entries(mathNames))+field('题目','prompt',row.prompt,120)+fields;
  }

  function assignmentList() {
    return (B.data.assignments||[]).map(item=>{
      const entry = item.entry;
      const completed = StudyModel.complete(entry);
      const status = completed?'已完成':item.startedAt?'学习中':'待学习';
      return `<div class="builder-row" data-assignment-row>
        <strong>${esc(item.date)} · ${status}</strong>
        <p class="course-help">${StudyModel.unitCount(entry)}/${subject()==='math'?5:11} 个单元${esc(StudyUI.repeatSummary(entry))}</p>
        ${item.startedAt?button('查看学习记录','record',`data-id="${esc(item.id)}"`):`
          <label class="course-field">安排日期<input type="date" min="${today()}" value="${esc(item.date)}" data-assignment-date></label>
          ${button('保存日期','reschedule',`data-id="${esc(item.id)}"`)}
          ${entry.lessonId!==B.data.publishedId?button('改用已发布新版','update-version',`data-id="${esc(item.id)}"`):''}
          ${button('取消安排','cancel',`data-id="${esc(item.id)}"`,'text-button')}`}
      </div>`;
    }).join('');
  }

  function extraPublish() {
    const data = B.data;
    return `<div class="builder-panel"><h3>发布与安排学习</h3>
      <p class="course-help">${esc(data.problem|| (B.reviewed?'试玩已确认，可以发布。':'请先完成孩子视角试玩。'))}</p>
      <label class="course-field">安排日期<input type="date" data-build-date min="${today()}" value="${esc(B.date||today())}"></label>
      ${button('发布并安排','publish',!B.dirty&&data.lesson&&B.reviewed?'':'disabled','primary-btn')}
      ${button('仅发布到课程库','publish-only',!B.dirty&&data.lesson&&B.reviewed?'':'disabled')}
      ${data.publishedId?button('安排已发布版本','assign'):''}
      <h3>学习安排与完成记录</h3>${assignmentList()||'<p class="course-help">还没有学习安排。</p>'}
    </div>`;
  }

  B.configure = api => { B.api = api; };
  const eligiblePlan = () => {
    const plan = B.api.plan();
    return plan?.study?.subjects.includes('english') ? plan : null;
  };
  const draftKey = () => 'sprout-authored-draft:'+B.data.id;
  const post = (action, extra = {}) => B.api.request('/api/course-builder', {
    method:'POST', body:JSON.stringify({action, id:B.data?.id, revision:B.data?.revision, ...extra})
  });

  function install(data) {
    B.data = data;
    B.dirty = false;
    if (data.audio) {
      Object.assign(SproutEnglishAudio, data.audio.files['en-US']);
      Object.assign(SproutChineseAudio, data.audio.files['zh-CN']);
    }
  }

  function remember() {
    B.dirty = true;
    B.reviewed = false;
    try {
      localStorage.setItem(draftKey(), JSON.stringify({revision:B.data.revision,draft:B.data.draft}));
    } catch {}
    const status = document.querySelector('[data-builder-status]');
    if (status) status.textContent = '有待保存修改';
  }

  async function save() {
    if (!B.dirty) return;
    install(await post('save', {draft:B.data.draft}));
    try { localStorage.removeItem(draftKey()); } catch {}
  }

  async function list() {
    B.rows = await B.api.request('/api/course-builder');
    B.stage = 'list';
    B.card = null;
  }

  async function open(id) {
    install(await B.api.request('/api/course-builder?id='+encodeURIComponent(id)));
    try {
      const stored = JSON.parse(localStorage.getItem(draftKey()) || 'null');
      if (stored?.revision === B.data.revision) {
        B.data.draft = stored.draft;
        B.dirty = true;
      }
    } catch {}
    B.stage = 'content';
    B.date = today();
    B.confirmExample = false;
    B.section = subject()==='math'?'problems':'words';
    B.card = null;
    B.reviewed = false;
  }

  function example() {
    const draft = B.data.draft;
    if (subject() !== 'english') {
      Object.assign(draft, structuredClone(subject()==='math'?{problems:mathExample}:chineseExample));
      remember();
      return;
    }
    draft.words = wordExamples.map(([en,cn],i) => ({en,cn,image:'fruit-'+i}));
    draft.sentences = sentenceExamples.map(([en,cn],ref) => ({en,cn,ref,review:false}));
    draft.story = storyExamples.map(([en,cn],ref) => ({en,cn,ref,review:false}));
    remember();
  }

  function field(label, name, value, limit, multiline = false) {
    return `<label class="course-field">${label}${multiline
      ? `<textarea data-build-field="${name}" maxlength="${limit}">${esc(value)}</textarea>`
      : `<input data-build-field="${name}" maxlength="${limit}" value="${esc(value)}">`}</label>`;
  }

  function listView() {
    const plan = eligiblePlan();
    const scheduled = new Set(plan?.courseQueue || []);
    const claimed = new Set(Object.values(plan?.records || {}).map(record => record.study?.english?.lessonId));
    return `<h2>课程管理</h2><p class="subtitle">把孩子感兴趣的内容，编成英语、汉字或数学小课。</p>
      ${button('＋ 自编课程','choose','','primary-btn')}
      <button class="secondary-btn" data-route="tabletop">数学思维活动</button>
      <div class="builder-list">${(B.rows || []).map(row =>
        `<button class="history-card" data-build-action="open" data-id="${esc(row.id)}">
          <span><strong>${esc(row.theme)}</strong><small>${subjectNames[row.type||'english']} · ${row.type==='math'?'5道思维挑战':row.type==='chinese'?'5字卡＋5短句＋1场景':'5单词＋5句子＋1故事'}</small></span>
          <span class="builder-chip">${claimed.has(row.publishedId)?'本期已领取':scheduled.has(row.publishedId)?'本期已安排':row.publishedId?'已发布':'草稿'}</span>
        </button>`).join('') || '<p class="course-help">还没有自编课程。可以从《水果店》的范例开始。</p>'}</div>
      <button class="secondary-btn" data-route="built-in-courses">查看与编辑内置课次</button>`;
  }

  function goalView() {
    const draft = B.data?.draft || B.newDraft;
    return `<h2>${B.data?'学习目标':'自编'+subjectNames[subject()]+'小课'}</h2>
      <div class="builder-panel">
        ${field('课程名称','theme',draft.theme,60)}
        ${field('学习阶段','phase',draft.phase,60)}
        ${field('学习目标','goal',draft.goal,200,true)}
        <div class="course-notice">${subjectNames[subject()]} · ${subject()==='math'?'5道思维挑战':subject()==='chinese'?'5张字卡、5句短句、1个三页场景':'5张单词卡、5个句子、1个三页故事'}</div>
        ${button(B.data?'保存目标并编排':'创建课程并编排',B.data?'content':'create','','primary-btn')}
      </div>`;
  }

  function contentView() {
    if(subject()!=='english') return extraContent();
    const draft = B.data.draft;
    const group = B.section;
    const count = rows => rows.filter(row => row.en.trim() && row.cn.trim()).length;
    const rows = draft[group];
    return `<div class="builder-panel"><h3>先编排内容，再准备素材</h3>
      <p class="course-help">句子和故事选择对应的单词卡，自动复用图片和单词发音。</p>
      ${button(B.confirmExample?'确认用范例覆盖草稿内容':'填入《水果店》范例（含配图）','example')}
      ${B.confirmExample?button('保留当前内容','cancel-example'):''}
      <div class="course-view-tabs">${groups.map(([key,label]) =>
        button(label+' '+count(draft[key])+'/'+draft[key].length,'group',
          `data-group="${key}" aria-pressed="${group===key}"`,group===key?'active':'')).join('')}</div>
      ${rows.map((row,i) => `<div class="builder-row" data-build-row="${i}">
        <strong>${group==='words'?'单词卡':group==='sentences'?'句子':'故事第'} ${i+1}${group==='story'?' 页':''}</strong>
        ${field(group==='words'?'英文单词':'英文朗读内容','en',row.en,group==='words'?60:400,group==='story')}
        ${field('中文含义','cn',row.cn,200)}
        ${group==='words'?'':`<label class="course-field">正确图片对应的单词卡<select data-build-field="ref">
          ${draft.words.map((word,index)=>`<option value="${index}" ${row.ref===index?'selected':''}>${esc(word.en || '单词卡 '+(index+1))}</option>`).join('')}
        </select></label>`}
        ${row.review?`<div class="course-notice">对应单词有修改，请检查英文和答案。 ${button('已核对','review',`data-index="${i}"`,'text-button')}</div>`:''}
      </div>`).join('')}
      ${group!=='story'?button(group==='words'?'接着编排句子':'接着编排故事','next-group'):''}
      ${button('下一步：配图配音','materials','','primary-btn')}
    </div>`;
  }

  function cardImage(word) {
    if (!word.image) return '<span class="course-help">待确认配图</span>';
    const asset = B.data.draftImages?.[word.image] || B.data.imageService.library.find(image => image.id === word.image);
    const builtin = /^fruit-[0-4]$/.test(word.image) ? {atlas:Number(word.image.at(-1)),word:word.en} : null;
    return OptionImages.render({images:{[word.image]:asset || builtin}}, word.image);
  }

  function materialsView() {
    const data = B.data;
    const words = data.draft.words;
    const audio = B.dirty ? null : data.audio;
    return `<div class="builder-panel"><h3>给单词配图、配音</h3>
      <p class="course-help">已绑定 ${words.filter(word=>word.image).length}/5 张。新配图同步到引用它的句子和故事。</p>
      <div class="builder-pictures">${words.map((word,i)=>`<article>
        <div class="builder-picture">${cardImage(word)}</div><strong>${esc(word.en||'单词卡 '+(i+1))}</strong>
        <small>${esc(word.cn)}</small>
        ${button(word.image?'查看／替换配图':'准备配图','image',`data-index="${i}" ${!word.en.trim()?'disabled':''}`)}
      </article>`).join('')}</div>
      ${B.card===null?'':`<div class="builder-image-panel">${button('关闭配图面板','close-image','','text-button')}
        ${ImageGenerator.render(B)}</div>`}
      <div class="builder-row"><h3>整课 Jenny 配音</h3>
        <p class="course-help">${audio?.ready?'示范配音已就绪。':audio?`还有 ${audio.missing.length} 段待生成。`:esc(data.problem||'保存后检查配音。')}</p>
        ${button('生成／补齐真实配音','audio')}
        <details><summary>试听单词、句子和故事</summary>
          ${groups.flatMap(([key])=>data.draft[key]).map(row=>row.en
            ? `<div class="builder-audio"><span>${esc(row.en)}</span>${button('试听','listen',`data-text="${esc(row.en)}" ${!audio?.files['en-US'][row.en]?'disabled':''}`,'text-button')}</div>`
            : '').join('')}
        </details>
      </div>
      ${button('下一步：孩子视角试玩','preview','','primary-btn')}
    </div>`;
  }

  function publishView() {
    if(subject()!=='english') return extraPublish();
    const data = B.data;
    const plan = eligiblePlan();
    const canPublish = !B.dirty && data.lesson && data.audio?.ready && B.reviewed;
    const currentRelease = data.publishedId && data.publishedRevision === data.revision && !B.dirty;
    const checks = [
      [!!data.lesson,data.lesson?'5＋5＋1内容、单词引用和配图已确认':data.problem, /配图|图片/.test(data.problem)?'materials':'content'],
      [!!data.audio?.ready,'整课示范配音已就绪','materials'],
      [B.reviewed,'已确认孩子视角试玩','preview']
    ];
    return `<div class="builder-panel"><h3>发布检查与学习安排</h3>
      ${checks.map(([pass,label,action])=>`<div class="builder-check"><span>${pass?'✓':'待处理'} · ${label}</span>${pass?'':button('去处理',action,'','text-button')}</div>`).join('')}
      <label class="course-field">发布去向<select data-build-destination>
        <option value="">仅发布到课程库</option>
        ${plan?`<option value="${esc(plan.id)}">安排给孩子 · ${esc(plan.name)}</option>`:''}
      </select></label>
      <p class="course-help">${plan?'选择安排后，按计划排队，在下一次领取英语课程时生效。正在学习的课继续完成。':'先在家长空间建立含自主英语的计划，再安排已发布课程。'}</p>
      ${button('确认发布','publish',canPublish?'':'disabled','primary-btn')}
      ${currentRelease&&plan?button('把已发布版本安排给孩子','assign'):''}
    </div>`;
  }

  function successView() {
    return `<div class="builder-panel"><h2>${B.assignedPlan?'课程已安排':'课程已发布'}</h2>
      <p class="course-notice">《${esc(B.data.draft.theme)}》${B.assignedPlan?`已加入「${esc(B.assignedPlan)}」的后续英语学习。`:'已加入课程库。'}</p>
      ${B.assignedPlan?'<button class="primary-btn" data-route="home">去孩子的今天查看</button>':eligiblePlan()?button('现在安排给孩子','assign','','primary-btn'):''}
      ${button('返回课程列表','list')}</div>`;
  }

  B.render = () => {
    if (B.stage === 'list' && B.rows === null && !B.busy) queueMicrotask(() => {
      if (B.rows === null && !B.busy) run('list');
    });
    let body;
    if (B.stage === 'list') body = listView();
    else if (B.stage === 'choose') body = `<h2>选择学科</h2>${Object.entries(subjectNames).map(([type,name])=>button(name,'new',`data-id="${type}"`)).join('')}${button('返回课程列表','list')}`;
    else if (B.stage === 'goal') body = goalView();
    else if (B.stage === 'content') body = contentView();
    else if (B.stage === 'materials') body = materialsView();
    else if (B.stage === 'publish') body = publishView();
    else body = successView();
    const editing = B.data && !['list','success'].includes(B.stage);
    return `<section class="screen course-editor course-builder">
      <header class="course-header"><button data-route="parent">← 家长空间</button><span>课程管理</span></header>
      ${editing?`<div class="course-status"><strong>${esc(B.data.draft.theme)}</strong>
        <small data-builder-status>${B.dirty?'有待保存修改':'草稿已保存 · 第 '+B.data.revision+' 版'}</small></div>
        <nav class="builder-steps" aria-label="编课步骤">${stages.filter(([key])=>subject()==='english'||key!=='materials').map(([key,label])=>button(label,key,`aria-pressed="${key===B.stage}"`,key===B.stage?'active':'')).join('')}</nav>`:''}
      ${B.error?`<p class="course-error" role="alert">${esc(B.error)}</p>`:''}
      ${B.notice?`<p class="course-notice" role="status">${esc(B.notice)}</p>`:''}
      ${B.busy?'<p class="course-notice" role="status">正在处理，请稍等。</p>':''}
      <fieldset ${B.busy?'disabled':''}>${body}
      ${editing?`<div class="course-actions">${button('保存草稿','save')}${button('返回课程列表','list','','text-button')}</div>`:''}
      </fieldset></section>`;
  };

  B.imageBinding = () => {
    const word = B.stage === 'materials' && B.card !== null && B.data?.draft.words?.[B.card];
    if (!word) return null;
    return {key:B.data.id+':'+B.card+':'+word.en.trim(), word:word.en.trim(),
      title:`正在为《${B.data.draft.theme}》的 ${word.en} 单词卡配图。确认后同步到相关句子与故事。`};
  };
  B.bindImage = async asset => {
    B.data.draft.words[B.card].image = asset.id;
    B.data.draftImages ||= {};
    B.data.draftImages[asset.id] = asset;
    remember();
    await run('save');
    if (B.dirty) throw Error('配图已暂存在浏览器，请重试保存草稿。');
  };

  async function run(action, value) {
    if (B.busy) return;
    B.busy = true;
    B.error = '';
    B.notice = '';
    // Read the choice before the working state replaces the form.
    const planId = document.querySelector('[data-build-destination]')?.value || null;
    const date = document.querySelector('[data-build-date]')?.value ?? B.date ?? today();
    B.api.render();
    try {
      if (action === 'list') {
        await save();
        await list();
      } else if (action === 'choose') {
        B.stage = 'choose';
      } else if (action === 'new') {
        B.data = null;
        B.dirty = false;
        B.reviewed = false;
        B.confirmExample = false;
        B.newDraft = newDraft(value || 'english');
        B.date = today();
        B.newId = 'custom-'+crypto.randomUUID().replaceAll('-','');
        B.stage = 'goal';
      } else if (action === 'create') {
        install(await post('create', {id:B.newId,draft:B.newDraft}));
        B.stage = 'content';
        B.section = subject()==='math'?'problems':'words';
      } else if (action === 'open') {
        await open(value);
      } else if (action === 'save') {
        await save();
        B.notice = '草稿已保存。';
      } else if (stages.some(([key])=>key===action) && !['preview','publish'].includes(action)) {
        await save();
        B.stage = action;
        B.card = null;
      } else if (action === 'check') {
        await save();
        if(subject()!=='english'){
          const latest=await B.api.request('/api/course-builder?id='+encodeURIComponent(B.data.id));
          if(latest.revision!==B.data.revision)B.reviewed=false;
          install(latest);
        }
        B.stage = 'publish';
      } else if (action === 'example') {
        example();
        B.confirmExample = false;
        await save();
      } else if (action === 'audio') {
        await save();
        install(await post('audio'));
        B.notice = '配音已就绪，可以试听或试玩。';
      } else if (action === 'preview') {
        await save();
        if (!B.data.lesson || subject()==='english'&&!B.data.audio?.ready) throw Error(B.data.problem || '请先补齐配音');
        B.api.preview(B.data.lesson, reviewed => {
          if (reviewed) B.reviewed = true;
          B.stage = reviewed ? 'publish' : subject()==='english'?'materials':'content';
          B.api.navigate('courses');
        });
      } else if (subject()!=='english' && ['publish','publish-only','assign','reschedule','cancel','update-version'].includes(action)) {
        await save();
        const operation = action==='publish-only'?'publish':action==='update-version'?'reschedule':action;
        const chosenDate=value?.date ?? date;
        if(!chosenDate&&!['publish-only','cancel'].includes(action))throw Error('请选择安排日期');
        install(await post(operation,{date:action==='publish-only'?null:chosenDate,reviewed:B.reviewed,
          assignmentId:value?.id,useLatest:action==='update-version'}));
        B.stage = 'publish';
        B.notice = action==='cancel'?'已取消安排。':'课程安排已保存。';
        await B.api.refresh();
      } else if (action === 'publish' || action === 'assign') {
        await save();
        const result = await post(action, {planId:action==='assign'?eligiblePlan()?.id:planId,reviewed:B.reviewed});
        install(result);
        B.assignedPlan = result.assignedPlan;
        B.stage = 'success';
        await B.api.refresh();
      }
    } catch (error) {
      B.error = error.message;
      if (action === 'list' && B.rows === null) B.rows = [];
    } finally {
      B.busy = false;
      B.api.render();
    }
  }

  document.addEventListener('input', event => {
    const input = event.target;
    const field = input.dataset.buildField;
    if(input.matches('[data-build-date]')) B.date = input.value;
    if (!field) return;
    const draft = B.data?.draft || B.newDraft;
    const container = input.closest('[data-build-row]');
    if (!container) {
      draft[field] = input.value;
    } else {
      const index = Number(container.dataset.buildRow);
      const row = draft[B.section][index];
      const value = field==='ref' ? Number(input.value) : input.value;
      if (row[field] === value) return;
      row[field] = value;
      if (subject()==='english' && B.section === 'words') {
        row.image = null;
        for (const item of [...draft.sentences, ...draft.story]) {
          if (item.ref === index && item.en) item.review = true;
        }
      }
    }
    if (B.data) remember();
    if(field==='kind') B.api.render();
  });

  document.addEventListener('click', event => {
    const control = event.target.closest('[data-build-action]');
    if (!control || B.busy || control.disabled) return;
    const {buildAction:action, index, id, group, text} = control.dataset;
    if (action === 'record') {
      B.api.record(id);
      return;
    }
    if (['reschedule','update-version','cancel'].includes(action)) {
      run(action,{id,date:control.closest('[data-assignment-row]').querySelector('[data-assignment-date]').value});
      return;
    }
    if (action === 'move-up' || action === 'move-down') {
      const from=Number(index), to=from+(action==='move-up'?-1:1), rows=B.data.draft.problems;
      if(to<0||to>=rows.length)return;
      [rows[from],rows[to]]=[rows[to],rows[from]];
      remember();
    } else if (action === 'group' || action === 'next-group') {
      B.section = group || (B.section==='words'?'sentences':'story');
    } else if (action === 'image' || action === 'close-image') {
      B.card = action==='image' ? Number(index) : null;
    } else if (action === 'review') {
      B.data.draft[B.section][Number(index)].review = false;
      remember();
    } else if (action === 'listen') {
      SproutSpeech.play([{text,lang:'en-US'}], {onerror:error=>{B.error=error;B.api.render();}});
      return;
    } else if (action === 'cancel-example') {
      B.confirmExample = false;
    } else if (action === 'example' && !B.confirmExample &&
      (subject()==='math'?B.data.draft.problems.some(row=>row.prompt):groups.some(([key])=>B.data.draft[key].some(row=>row.en || row.cn)))) {
      B.confirmExample = true;
    } else {
      const step = control.closest('.builder-steps');
      run(action==='publish'&&step?'check':action,id);
      return;
    }
    B.api.render();
    if (action==='image') document.querySelector('.builder-image-panel')?.scrollIntoView({block:'start'});
  });
  globalThis.CourseBuilder = B;
})();
