const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../sync-model.js'),'utf8'),ctx);
test('canonical day patches retain other days and plans without mutating the old snapshot',()=>{
  const state={version:1,child:{name:'测试'},selectedPlanId:'p1',plans:[{id:'p1',records:{1:{note:'keep'},2:{sport:{done:true}}}},{id:'p2',records:{}}]};
  const before=JSON.stringify(state),record={study:{math:{steps:{q0:{correct:true}}}},practice:{math:{roundId:'r1',steps:{}}}};
  const next=ctx.SproutSync.apply(state,{patch:{planId:'p1',day:2,record,selectedPlanId:'p1'}});
  assert.equal(JSON.stringify(state),before);assert.equal(next.plans[0].records[2],record);assert.equal(next.plans[0].records[1].note,'keep');assert.equal(next.plans[1],state.plans[1]);
});
test('idempotent retries use full canonical state and unknown targets require a fresh read',()=>{
  const current={plans:[{id:'p1'}]},canonical={plans:[{id:'p2'}]};
  assert.equal(ctx.SproutSync.apply(current,{state:canonical}),canonical);
  assert.throws(()=>ctx.SproutSync.apply(current,{patch:{planId:'missing'}}),/重新读取/);
});
