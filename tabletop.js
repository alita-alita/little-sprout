(() => {
  const key = 'sprout-tabletop-v1';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const step = (say, child, clue = '') => ({say, child, clue});
  const cards = ['红圆','蓝方','蓝圆','红方','红圆','蓝方'];
  const variants = ['A','B'];
  const sorting = variants.map((variant,i) => ({
    code:'07', variant, title:'分拣指挥灯', kind:'规则切换', page:11,
    materials:'M01／M02 图形卡（第17–18页）\nM06 颜色和形状提示卡（第22页）\nM07 四扇门（第23页）',
    setup:'四扇门都摆好。按红圆、蓝方、蓝圆、红方、红圆、蓝方从上到下叠放。规则顺序由家长保管。',
    steps:[step('每封信都有自己的规矩。我举牌，你看清，再送这一封。','看清两种提示卡，准备分拣。'),
      ...(i?['形状','形状','颜色','形状','颜色','颜色']:['颜色','颜色','形状','颜色','形状','形状']).map((rule,n)=>
        step('先举「'+rule+'」提示卡，再递出第 '+(n+1)+' 张「'+cards[n]+'」。即使规则和上一张相同，也重新举牌。','看提示，送到对应的门。放好并核对后再拿下一张。',rule))],
    hints:'保留当前提示和图形，问：这封信要看哪个特点？\n请孩子指一指当前提示，再决定要不要改放。\n如果仍卡住，示范一次，让孩子再试一张。',
    answer:i?'依次送到圆、方、蓝、方、红、蓝。':'依次送到红、蓝、圆、红、圆、方。',
    observation:'规则重复时，孩子是否仍先看提示？哪一次切换需要提醒？'
  }));
  const patterns = variants.map((variant,i) => ({
    code:'08', variant, title:'规律维修员', kind:'找规律', page:12,
    materials:'M03 红蓝色片（第19页）\nM14 的 8'+variant+'「补一格」「改一格」两行题条（第30页）',
    setup:'先只露出 8'+variant+' 的「补一格」，盖住「改一格」。准备红蓝色片。',
    steps:[
      step('今天每三格重复一次，顺序是'+(i?'蓝蓝红':'红红蓝')+'。先读第一组，再用一张车票盖住问号。','找问号在组内的第几格，选色补上，再读完整三组。'),
      step('收起第一行，露出「改一格」。找一找哪个车厢和约定不同。','先指出错格，再用正确色片盖住，其他车厢留在原位。'),
      step('两行分别读一遍，看看每组都一样了吗？','指出原来哪一格不合规则。')],
    hints:'先指着完整的一组读一遍。\n逐格比较第一组和待查组的第1、2、3格。\n需要时在每组三张下面放分组框。',
    answer:i?'补缺行第4格补蓝。纠错行第8格的红换成蓝。':'补缺行第5格补红。纠错行第6格的红换成蓝。',
    observation:'孩子是否用邻近完整的一组逐格比对？补缺和纠错分别需要什么帮助？'
  }));
  const houses = variants.map((variant,i) => ({
    code:'09', variant, title:'三间小屋', kind:'简单推理', page:13,
    materials:'M04 猫、狗、兔各1张（第20页）\nM09 红、蓝、黄三间房和 '+variant+' 组两张入住线索（第25页）',
    setup:'三间房分开放，动物先都放在房子外。认一遍颜色和动物。'+(i?'和上次相比，重新打乱三间房的摆位。':''),
    steps:[
      step('每间刚好住一只，三只都要入住。读出下面两条线索，你想先摆谁？','同时看两张线索，自己选从哪一条开始摆。',i?'小兔住黄房。\n小猫不住红房。':'小猫住红房。\n小狗不住蓝房。'),
      step('这里已经有人吗？这间是线索说不能住的吗？','让先摆好的动物留在原处。摆好第二只，再把最后一只放进空房。'),
      step('三间都住满了吗？我们逐条看看，两条线索都成立吗？','检查每间一只，核对两条线索，需要时自己搬家。')],
    hints:'哪条线索直接告诉你谁住哪间？\n看看哪间已经有人，再指一指哪间不能住。\n家长可以一起摆好线索直接指定的那只，让孩子自己安排另外两只。',
    answer:i?'小兔住黄房，小猫住蓝房，小狗住红房。':'小猫住红房，小狗住黄房，小兔住蓝房。',
    observation:'最后一只的位置是怎么确定的？孩子是否同时核对两条线索？'
  }));
  const templates = [...sorting,...patterns,...houses];
  const outcomes = ['独立完成','提示后完成','示范后完成','本次未完成'];
  let api, mode = 'list', draft, playing, error = '';
  const read = () => JSON.parse(localStorage.getItem(key) || '{"drafts":{},"scheduled":[],"records":[]}');
  const save = data => localStorage.setItem(key, JSON.stringify(data));
  const today = () => SproutModel.date();
  const btn = (label, action, id = '', style = 'secondary-btn') =>
    `<button type="button" class="${style}" data-tabletop="${action}" data-id="${esc(id)}">${esc(label)}</button>`;
  const field = (name, label, value, multi = false) => `<label class="course-field">${label}${multi
    ? `<textarea name="${name}" maxlength="2000">${esc(value)}</textarea>`
    : `<input name="${name}" maxlength="120" value="${esc(value)}">`}</label>`;
  const lines = value => esc(value).replace(/\n/g, '<br>');
  const render = () => {
    const data = read();
    let body;
    if (mode === 'edit') {
      body = `<h2>编排亲子桌面游戏</h2><p>范例 ${esc(draft.code+(draft.variant||""))} · ${esc(draft.kind)} · 打印包第 ${draft.page||"—"} 页</p><form id="tabletop-edit" class="builder-panel">
        ${field('title','活动名称',draft.title)}
        ${field('materials','材料清单（可填数量、材料编号与打印页）',draft.materials,true)}
        ${field('setup','初始摆放',draft.setup,true)}
        ${draft.steps.map((s,i) => `<fieldset class="builder-panel"><legend>步骤 ${i+1}</legend>
          ${field('say'+i,'家长怎么说',s.say,true)}
          ${field('child'+i,'孩子怎么做',s.child,true)}
          ${field('clue'+i,'线索或规则提示（每行一条，选填）',s.clue,true)}
          ${i>0?btn('上移','up',i):''}${draft.steps.length>1?btn('删除这步','remove',i):''}
        </fieldset>`).join('')}
        ${btn('＋ 添加步骤','add')}
        ${field('hints','逐级提示（每行一条）',draft.hints,true)}
        ${field('answer','核对答案',draft.answer,true)}
        ${btn('保存草稿','save')}${btn('预览陪玩流程','preview')}${btn('发布并安排到今天','publish','','primary-btn')}
      </form>`;
    } else if (mode === 'play') {
      const {activity:a, index:i, preview} = playing;
      const current = a.steps[i-1];
      const clues = a.kind === '简单推理' ? a.steps.slice(0,i).flatMap(s=>s.clue.split('\n')).filter(Boolean) : [current?.clue].filter(Boolean);
      body = `<h2>${esc(a.title)}</h2><p>${preview?'试玩预览':'亲子陪玩'} · ${esc(a.kind)}${a.variant?' · '+esc(a.variant)+' 题':''}</p><div class="builder-panel">${i===0
        ? `<h3>准备材料</h3><p>${lines(a.materials)}</p><h3>初始摆放</h3><p>${lines(a.setup)}</p>`
        : current
          ? `<h3>步骤 ${i} / ${a.steps.length}</h3><p><strong>家长怎么说</strong><br>${lines(current.say)}</p>
             <p><strong>孩子怎么做</strong><br>${lines(current.child)}</p>
             ${clues.length?`<h3>${a.kind==='简单推理'?'已给出的线索':'当前提示'}</h3><ul>${clues.map(c=>`<li>${esc(c)}</li>`).join('')}</ul>`:''}`
          : '<h3>检查与记录</h3>'}
        ${i>0 ? a.hints.split('\n').filter(x=>x.trim()).map((hint,n)=>`<details><summary>提示 ${n+1}</summary><p>${esc(hint)}</p></details>`).join('') : ''}
        ${!current&&i>0?`<details><summary>核对答案</summary><p>${lines(a.answer)}</p></details>`:''}
        ${i>0?btn('上一步','back-step'):''}
        ${i<=a.steps.length?btn(i?'继续':'材料准备好了','next','','primary-btn'):preview?btn('返回编辑','edit-return'):''}
        ${!preview&&i>a.steps.length?`<form id="tabletop-result"><label class="course-field">完成方式<select name="outcome">${outcomes.map(x=>`<option>${x}</option>`).join('')}</select></label>${a.observation?`<p>${esc(a.observation)}</p>`:''}${field('note','家长观察（选填）','',true)}${btn('保存陪玩记录','record','','primary-btn')}</form>`:''}
      </div>${preview?btn('返回编辑','edit-return'):btn('先休息，保留进度','home')}`;
    } else {
      body = `<h2>亲子桌面游戏</h2><p>家长看步骤，孩子在桌面摆纸卡。复制范例后可以改成自己的活动。</p>
        <div class="builder-list">${templates.filter(t=>t.variant==='A').map(t=>`<div class="builder-panel"><h3>${t.code} · ${esc(t.title)}</h3><p>${esc(t.kind)} · 打印包第 ${t.page} 页</p>${variants.map(v=>btn('复制《'+t.title+'》'+v+'题','copy',t.code+v)).join('')}</div>`).join('')}</div>
        <h3>我的活动</h3>${Object.values(data.drafts).map(d=>btn((d.title||'未命名活动')+(data.published?.[d.id]?' · 已发布':' · 草稿'),'edit',d.id)).join('')||'<p>还没有草稿。</p>'}
        <h3>陪玩记录</h3>${data.records.slice().reverse().map(r=>`<div class="builder-panel"><strong>${esc(r.title)}</strong><p>${esc(r.date)}${r.variant?' · '+esc(r.variant)+' 题':''} · ${esc(r.outcome)}</p>${r.note?`<p>${lines(r.note)}</p>`:''}</div>`).join('')||'<p>陪玩结束后，记录会显示在这里。</p>'}`;
    }
    return `<section class="screen course-editor course-builder">${btn('← 返回课程管理','courses')}${error?`<p role="alert">${esc(error)}</p>`:''}${body}</section>`;
  };
  function capture() {
    const form = document.querySelector('#tabletop-edit');
    if (!form) return;
    const values = new FormData(form);
    for (const name of ['title','materials','setup','hints','answer']) draft[name] = values.get(name).trim();
    draft.steps = draft.steps.map((_,i)=>step(...['say','child','clue'].map(name=>values.get(name+i).trim())));
  }
  const valid = () => draft.title && draft.materials && draft.setup && draft.answer &&
    draft.steps.length && draft.steps.every(s=>s.say && s.child);
  function handle(action,id) {
    const data = read();
    error = '';
    if (mode==='edit') capture();
    if (action==='copy') {
      draft = {...structuredClone(templates.find(t=>t.code+t.variant===id)),id:crypto.randomUUID()};
      mode='edit';
    } else if (action==='edit') {
      draft=data.drafts[id]; mode='edit';
    } else if (action==='add') {
      draft.steps.push(step('',''));
    } else if (action==='remove') {
      draft.steps.splice(Number(id),1);
    } else if (action==='up') {
      const i=Number(id);
      [draft.steps[i-1],draft.steps[i]]=[draft.steps[i],draft.steps[i-1]];
    } else if (action==='save') {
      data.drafts[draft.id]=draft; save(data); mode='list';
    } else if (action==='preview'||action==='publish') {
      if (!valid()) throw Error('请填写活动名称、材料、初始摆放、每步话术与操作，以及核对答案。');
      if (action==='preview') {
        playing={activity:structuredClone(draft),index:0,preview:true}; mode='play';
      } else {
        data.drafts[draft.id]=draft;
        data.published ??= {};
        data.published[draft.id]=structuredClone(draft);
        const existing=data.scheduled.find(r=>r.date===today()&&r.activity.id===draft.id&&!r.done);
        if (existing) throw Error('这节活动今天已经安排，可以到首页接着玩。');
        data.scheduled.push({id:crypto.randomUUID(),date:today(),activity:structuredClone(draft),index:0});
        save(data); mode='list'; api.navigate('home'); return;
      }
    } else if (action==='play') {
      playing=data.scheduled.find(r=>r.id===id&&!r.done);
      if (!playing) return;
      mode='play'; api.navigate('tabletop'); return;
    } else if (action==='next'||action==='back-step') {
      const run=playing.preview?playing:data.scheduled.find(r=>r.id===playing.id&&!r.done);
      if (!run) throw Error('本次陪玩已经记录。');
      run.index=Math.max(0,Math.min(run.activity.steps.length+1,run.index+(action==='next'?1:-1)));
      if (!run.preview) save(data);
      playing=run;
    } else if (action==='record') {
      const run=data.scheduled.find(r=>r.id===playing.id&&!r.done);
      if (!run || run.index<=run.activity.steps.length) throw Error('请完成陪玩步骤后记录。');
      const values=new FormData(document.querySelector('#tabletop-result'));
      const outcome=values.get('outcome');
      if (!outcomes.includes(outcome)) throw Error('请选择完成方式。');
      data.records.push({title:run.activity.title,variant:run.activity.variant,kind:run.activity.kind,date:today(),outcome,note:values.get('note').trim()});
      run.done=true; save(data); mode='list';
    } else if (action==='edit-return') {
      mode='edit';
    } else if (action==='home'||action==='courses') {
      mode='list'; api.navigate(action); return;
    }
    api.render();
    if (['copy','edit','preview','next','back-step','record','edit-return'].includes(action)) document.querySelector('#app').scrollTop=0;
  }
  document.addEventListener('click', event=>{
    const target=event.target.closest('[data-tabletop]');
    if (!target) return;
    try { handle(target.dataset.tabletop,target.dataset.id); }
    catch (cause) {
      error=cause.message;
      let alert=document.querySelector('#app [role="alert"]');
      if (!alert) {
        alert=document.createElement('p'); alert.setAttribute('role','alert');
        target.closest('form,section')?.prepend(alert);
      }
      alert.textContent=error;
      alert.scrollIntoView({block:'nearest'});
    }
  });
  globalThis.Tabletop = {
    configure: config=>{api=config;},
    render,
    home:()=> {
      const pending=read().scheduled.filter(r=>!r.done&&r.date<=today());
      return pending.length?`<div class="builder-panel"><h3>今天一起玩</h3>${pending.map(r=>btn((r.index?'继续 · ':'开始 · ')+r.activity.title,'play',r.id)).join('')}</div>`:'';
    }
  };
})();
