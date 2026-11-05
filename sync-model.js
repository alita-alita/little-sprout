(() => {
  'use strict';
  function apply(state, response) {
    if (response.state) return response.state;
    const p = response.patch;
    if (!p || !state.plans.some(plan => plan.id === p.planId)) throw Error('进度已变化，请重新读取');
    return {...state, selectedPlanId:p.selectedPlanId, plans:state.plans.map(plan => plan.id === p.planId
      ? {...plan, records:{...plan.records, [p.day]:p.record}} : plan)};
  }
  globalThis.SproutSync = {apply};
})();
