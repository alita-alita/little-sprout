(() => {
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const G={word:'',candidate:null,job:null,busy:false,error:'',message:'',timer:null,context:''};
  const post=(E,body)=>E.api.request('/api/course-images',{method:'POST',body:JSON.stringify(body)});
  const pendingKey='sprout-image-pending';
  function rememberJob(){try{localStorage.setItem(pendingKey,JSON.stringify({id:G.job.id,word:G.job.word,lang:G.job.lang}));}catch{}}
  function accept(E,job){G.job=job;G.busy=job.state==='running';if(job.state==='ready'){G.candidate=job.asset;const lib=E.data?.imageService?.library;if(lib&&!lib.some(x=>x.id===job.asset.id))lib.push(job.asset);G.error='';G.message='图片已生成，请确认图片与词义一致。';localStorage.removeItem(pendingKey);}if(job.state==='error'){G.error=job.error;localStorage.removeItem(pendingKey);}E.api.render();if(G.busy){clearTimeout(G.timer);G.timer=setTimeout(()=>poll(E),1800);}}
  async function poll(E){try{accept(E,await E.api.request('/api/course-images?id='+G.job.id));}catch(e){G.busy=false;G.error='查询中断，点击“查询生成结果”继续，不会重复生成。';E.api.render();}}
  G.render=E=>{
    const binding=E.imageBinding?.();
    if(!E.data||(!binding&&(!['english','chinese'].includes(E.type)||!['choice','story'].includes(E.current().q.kind))))return '';
    const lang=E.type==='english'?'en-US':'zh-CN',context=binding?.key||E.type+'-'+E.index+'-'+E.question;
    if(G.context!==context){G.context=context;G.word=binding?binding.word:(E.current().unit.section==='words'?E.current().q.display:'');G.message='';}
    if(!G.job){try{const old=JSON.parse(localStorage.getItem(pendingKey)||'null');if(old?.id){G.job=old;}}catch{}}
    const service=E.data.imageService||{},c=G.candidate,usable=c?.lang===lang&&(!binding||c.word.toLowerCase()===binding.word.toLowerCase());
    return `<section class="image-generator"><h3>一键生成绘本图片</h3><p class="course-help">${binding?esc(binding.title):'输入一个单词或物体名称。图片与词义确认后加入选项，再保存、补齐配音并发布。'}</p><label class="course-field">${lang==='en-US'?'英语单词，例如 pineapple':'汉字或物体名称，例如 树'}<input data-image-word value="${esc(G.word)}" maxlength="60" ${G.busy?'disabled':''} ${binding?'readonly':''}></label><button class="secondary-btn" data-image-action="generate" ${G.busy||!service.configured?'disabled':''}>${G.busy?'正在画，请稍候…':c?'重新生成一张':'生成单张图片'}</button>${G.job&&G.job.state!=='ready'&&!G.busy?'<button class="text-button" data-image-action="poll">查询生成结果</button>':''}${G.error?`<p class="course-error" role="alert">${esc(G.error)}</p>`:''}${G.message?`<p class="course-notice" role="status">${esc(G.message)}</p>`:''}${G.busy?'<p class="course-help" role="status">正在生成，通常需要等待一会儿。离开页面后可回来查询结果，请勿重复提交。</p>':''}${c?`<div class="image-candidate"><img src="${esc(c.src)}" alt="${esc(c.word)} 的待确认图片"><strong>${esc(c.word)}</strong><small>绑定发音：${c.lang==='en-US'?'Jenny · 英语':'云夏 · 中文'}，补齐配音后可试听</small>${usable?`<label class="image-approval"><input type="checkbox" data-image-approve>我已确认图片清楚、词义正确</label>${binding?'':`<label class="course-field">加入位置<select data-image-position>${E.current().q.options.length<4?'<option value="add">新增一个选项</option>':''}${E.current().q.options.map((x,i)=>`<option value="${i}">替换：${esc(OptionImages.word(E.data.lesson,x)||x)}</option>`).join('')}</select></label><label class="image-approval"><input type="checkbox" data-image-answer ${E.current().unit.section==='words'?'checked':''}>设为正确答案${E.current().unit.section==='words'?'，并同步目标单词与朗读':''}</label>`}<button class="primary-btn" data-image-action="add">${binding?'确认选用并绑定':'确认并加入选项'}</button>`:'<p class="course-help">请选择与当前单词或语言对应的图片。</p>'}</div>`:''}${(service.library||[]).some(x=>x.lang===lang&&(!binding||x.word.toLowerCase()===binding.word.toLowerCase()))?`<details class="image-library"><summary>已生成的图片，可再次使用</summary><div class="image-library-grid">${service.library.filter(x=>x.lang===lang&&(!binding||x.word.toLowerCase()===binding.word.toLowerCase())).slice().reverse().map(x=>`<button type="button" data-image-action="reuse" data-id="${esc(x.id)}"><img src="${esc(x.src)}" alt="${esc(x.word)}"><span>${esc(x.word)}</span></button>`).join('')}</div></details>`:''}<details class="image-setup" ${!service.configured?'open':''}><summary>${service.configured?'免费生图已配置 · 查看或更换设置':'先配置免费生图服务'}</summary><ol><li>打开 <a href="https://dash.cloudflare.com/sign-up" target="_blank" rel="noopener noreferrer">Cloudflare 注册页</a>，注册并验证邮箱，保持 Free 免费计划。</li><li>进入 Workers AI，选择 Use REST API，再点 Create a Workers AI API Token。</li><li>复制页面上的 Account ID 和新生成的 API Token，填到下方，仅保存在本机。</li></ol><p class="course-help">免费额度为每天 10,000 neurons，图片数量取决于模型用量。达到免费限额后暂停；本应用不会自动升级套餐或切换付费服务。<a href="https://developers.cloudflare.com/workers-ai/get-started/rest-api/" target="_blank" rel="noopener noreferrer">查看官方配置步骤</a></p><label class="course-field">Account ID<input data-image-account placeholder="32位账号 ID" autocomplete="off" maxlength="32"></label><label class="course-field">API Token<input data-image-token type="password" autocomplete="off" placeholder="仅在本机填写，不要发到聊天里" maxlength="500"></label><button class="secondary-btn" data-image-action="configure">保存本机配置</button><p class="course-help">只向 Cloudflare 发送待生成的单词与画风要求，不发送孩子档案。配置保存后，首次生成时验证权限。图片生成与配音均需联网。</p></details></section>`;
  };
  document.addEventListener('input',e=>{if(e.target.hasAttribute('data-image-word'))G.word=e.target.value;});
  document.addEventListener('click',async e=>{
    const b=e.target.closest('[data-image-action]'),E=b?.closest('.course-builder')?globalThis.CourseBuilder:globalThis.CourseEditor;if(!b||!E?.data||E.busy)return;
    const action=b.dataset.imageAction;G.error='';G.message='';
    try{
      if(action==='reuse'){G.candidate=E.data.imageService.library.find(x=>x.id===b.dataset.id);G.message='已选用图片，请确认后加入当前题目。';}
      if(action==='configure'){const tokenInput=document.querySelector('[data-image-token]');const body={action,account:document.querySelector('[data-image-account]').value,token:tokenInput.value};tokenInput.value='';E.data.imageService=await post(E,body);G.message='已保存本机配置，可以生成第一张图片。';}
      if(action==='poll'){if(G.busy)return;G.busy=true;E.api.render();await poll(E);return;}
      if(action==='generate'){if(G.busy)return;const word=G.word.trim();if(!word)throw Error('请先输入单词或物体名称');G.busy=true;E.api.render();const requestId=crypto.randomUUID();const job=await post(E,{action,word,lang:E.type==='english'?'en-US':'zh-CN',requestId});G.job=job;rememberJob();accept(E,job);return;}
      if(action==='add'){
        if(!document.querySelector('[data-image-approve]')?.checked)throw Error('请先确认图片清楚、词义正确');
        if(E.imageBinding){
          const binding=E.imageBinding(),candidate=G.candidate;
          if(!binding||candidate?.lang!=='en-US'||candidate.word.toLowerCase()!==binding.word.toLowerCase())throw Error('请选择对应单词的图片');
          const asset=await post(E,{action:'approve',id:candidate.id});
          if(E.imageBinding()?.key!==binding.key)throw Error('单词卡已切换，请重新确认');
          await E.bindImage(asset);
          G.message='配图已绑定，引用它的句子与故事会使用同一张图。';
          E.api.render();return;
        }
        const position=document.querySelector('[data-image-position]').value,setAnswer=document.querySelector('[data-image-answer]').checked;
        const item=E.current(),lesson=E.data.lesson,c=G.candidate;
        if(!c||c.lang!==(E.type==='english'?'en-US':'zh-CN'))throw Error('请使用当前语言的图片');
        if(item.q.options.includes(c.id))throw Error('这张图片已在当前选项中');
        if(position==='add'&&item.q.options.length>=4)throw Error('最多4个选项，请选择一个替换');
        const asset=await post(E,{action:'approve',id:c.id});
        if(lesson!==E.data.lesson||item.q!==E.current().q)throw Error('题目已切换，图片已保留，请在当前题目重新加入');
        lesson.images||={};lesson.optionWords||={};lesson.images[asset.id]=asset;lesson.optionWords[asset.id]=asset.word;
        const old=position==='add'?null:item.q.options[Number(position)];
        if(position==='add')item.q.options.push(asset.id);else item.q.options[Number(position)]=asset.id;
        if(setAnswer||item.q.answer===old){item.q.answer=asset.id;if(item.unit.section==='words'){item.q.display=asset.word;item.q.speech=asset.word;item.q.cue=asset.id;item.unit.label=asset.word;}}
        E.remember();G.message='图片已加入草稿，并绑定对应词语。请保存后补齐配音，再预览和发布。';
      }
      if(action==='remove'){
        const q=E.current().q,index=Number(b.dataset.index);
        if(q.options.length<=2)throw Error('每道题至少保留两个选项，请先添加或替换');
        if(q.options[index]===q.answer)throw Error('请先选择其他正确答案，再移除这个选项');
        q.options.splice(index,1);E.remember();
      }
    }catch(error){G.busy=false;G.error=error.message;}E.api.render();
  });
  globalThis.ImageGenerator=G;
})();
