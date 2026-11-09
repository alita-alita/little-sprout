(() => {
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const image=(lesson,value)=>{const item=lesson?.images?.[value];return item&&((Number.isInteger(item.atlas)&&item.atlas>=0&&item.atlas<5)||/^\/assets\/pictures\/[a-f0-9]{24}\.(png|jpg)$/.test(item.src))?item:null;};
  const word=(lesson,value)=>image(lesson,value)?.word||lesson?.optionWords?.[value];
  const render=(lesson,value)=>{const item=image(lesson,value);return Number.isInteger(item?.atlas)?`<span class="course-fruit fruit-${item.atlas}" role="img" aria-label="${esc(item.word)}"></span>`:item?`<img class="option-picture" src="${esc(item.src)}" alt="${esc(item.word)}" loading="lazy">`:esc(value);};
  globalThis.OptionImages={image,word,render};
})();
