(() => {
  const S={catalog:null};
  S.lesson=e=>S.catalog?.lessons[e?.lessonId];
  S.questions=lesson=>lesson?.units.flatMap(u=>u.questions)||[];
  S.complete=e=>!!S.lesson(e)&&S.questions(S.lesson(e)).every(q=>e.steps?.[q.id]?.correct===true);
  S.unitCount=e=>S.lesson(e)?.units.filter(u=>u.questions.every(q=>e.steps?.[q.id]?.correct)).length||0;
  S.entry=(p,d,type)=>p.records[d]?.study?.[type];
  S.enabled=(p,d)=>!!p.study&&d>=p.study.startDay;
  S.hasActivity=(p,d)=>Object.values(p.records[d]?.study||{}).some(e=>Object.values(e.steps||{}).some(step=>!e.continued||(step.updatedAt&&Number.isFinite(Date.parse(step.updatedAt))&&new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(step.updatedAt))===globalThis.SproutModel.add(p.start,d-1))));
  S.dayComplete=(p,d)=>p.study.subjects.every(t=>S.complete(S.entry(p,d,t)));
  S.detail=(p,d)=>{const entries=p.records[d]?.study||{};return Object.entries(entries).map(([type,e])=>({type,entry:e,lesson:S.lesson(e),units:S.unitCount(e),done:S.complete(e),hints:Object.values(e.steps||{}).filter(s=>s.correct&&s.hinted).length,independent:Object.values(e.steps||{}).filter(s=>s.correct&&!s.hinted&&s.attempts===0).length}));};
  globalThis.StudyModel=S;
})();
