(function(root){
  const DAY=86400000;
  const date=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const add=(d,n)=>new Date(Date.parse(d+'T00:00:00Z')+n*DAY).toISOString().slice(0,10);
  const delta=(a,b)=>Math.round((Date.parse(a+'T00:00:00Z')-Date.parse(b+'T00:00:00Z'))/DAY);
  const subjects={english:{label:'英语启蒙',icon:'book',color:'peach'},math:{label:'数学思维',icon:'blocks',color:'yellow'},chinese:{label:'语文启蒙',icon:'book',color:'pink'},sport:{label:'运动启蒙',icon:'run',color:'mint'}};
  const rec=(p,d)=>p.records[d]||{};
  const full=(p,d)=>p.study&&d>=p.study.startDay?globalThis.StudyModel.dayComplete(p,d):!!(rec(p,d).learning?.done&&rec(p,d).sport?.done);
  function stats(p,now=date()){
    const today=delta(now,p.start)+1,pending=today<1,ended=p.status==='archived'||today>p.duration;
    const elapsed=Math.max(0,Math.min(p.duration,today,p.status==='archived'?delta(p.archivedDate,p.start)+1:Infinity));
    let completed=0,participated=0,activities=0,longest=0,run=0;
    const counts={english:0,math:0,chinese:0,sport:0},totals={english:0,math:0,chinese:0,sport:0};
    p.days.forEach((tasks,i)=>{const d=i+1,r=rec(p,d);if(p.study&&d>=p.study.startDay){p.study.subjects.forEach(type=>{totals[type]++;if(globalThis.StudyModel.complete(r.study?.[type])){counts[type]++;activities++;}});totals.sport++;if(r.sport?.done){counts.sport++;activities++;}}else tasks.forEach((t,j)=>{totals[t.type]++;if(r[j?'sport':'learning']?.done){counts[t.type]++;activities++;}});if(r.learning?.done||r.sport?.done||globalThis.StudyModel?.hasActivity(p,d))participated++;if(full(p,d)){completed++;longest=Math.max(longest,++run);}else run=0;});
    let cursor=ended?elapsed:full(p,today)?today:today-1,streak=0;while(cursor>0&&full(p,cursor)){streak++;cursor--;}
    return {today,pending,ended,elapsed,completed,participated,activities,longest,streak,counts,totals};
  }
  function makePlan({duration,start,subjects:chosen,name,autonomous=false},library){
    if(!Number.isInteger(duration)||duration<1||duration>90||!chosen.length)throw Error('请选择1—90天，并至少选择一个启蒙方向');
    const count={english:0,math:0,chinese:0,sport:0};
    const next=type=>{const list=library[type],index=count[type]++, task=JSON.parse(JSON.stringify(list[index%list.length]));if(index>=list.length)task.subtitle='再玩一次 · '+task.subtitle;return task;};
    const days=Array.from({length:duration},(_,i)=>[next(chosen[i%chosen.length]),next('sport')]);
    const plan={id:crypto.randomUUID(),name:name.trim()||'小小探索家',duration,start,status:'active',records:{},days,createdAt:new Date().toISOString()};
    if(autonomous)plan.study={version:1,startDay:1,subjects:[...chosen]};
    return plan;
  }
  function mark(plan,day,slot,mode,reaction,note,now=date()){
    const s=stats(plan,now);if(s.pending||s.ended||day!==s.today)throw Error('只能记录今天的活动，请返回今天查看');
    if(!['learning','sport'].includes(slot))throw Error('任务不存在');
    const r=plan.records[day]||(plan.records[day]={});
    if(!r[slot]?.done)r[slot]={done:true,mode,reaction,time:new Date().toISOString()};
    if(note?.trim())r.note=note.trim();return plan;
  }
  root.SproutModel={date,add,delta,subjects,rec,full,stats,makePlan,mark};
})(typeof window!=='undefined'?window:globalThis);
