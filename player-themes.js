(() => {
'use strict';
const themes = {
  'Highfish Original': ['#0a0a0f','#13131c','#1a1a27','#2a2a3f','#ff5e3a','#ff9a3c','#e8e8f0','#a3a3b8'],
  Ocean: ['#061b29','#0b2839','#12384a','#28546b','#46c5ff','#63e3d0','#eefaff','#a7c8da'],
  Synthwave: ['#160c25','#261439','#351d4a','#674280','#ff73d6','#ba8cff','#fff0fc','#d1accd'],
  Forest: ['#0b1c14','#132b20','#1e3b2b','#44664f','#73df9c','#c8df76','#f0fff2','#b3cbb7'],
  Paper: ['#f4f1e9','#fffcf5','#e9e3d5','#b8ad98','#9e341b','#946219','#24231f','#605c52']
};
const style = document.createElement('style');
style.textContent = ':focus-visible{outline:3px solid var(--acc)}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}';
document.head.append(style);
function apply(name) {
 const vals = themes[name] || themes['Highfish Original'];
 ['bg','surf','card','border','acc','acc2','text','muted'].forEach((k,i)=>document.documentElement.style.setProperty('--'+k,vals[i]));
 localStorage.setItem('mp3z_theme',name);
}
apply(localStorage.getItem('mp3z_theme') || 'Highfish Original');
const select=document.createElement('select');
select.setAttribute('aria-label','Player-Theme');
Object.keys(themes).forEach(name=>select.add(new Option(name,name)));
select.value=localStorage.getItem('mp3z_theme') || 'Highfish Original';
select.style.cssText='max-width:130px;min-height:40px;background:var(--card);color:var(--text);border:1px solid var(--border);border-radius:8px';
select.onchange=()=>apply(select.value);
const header=document.querySelector('header');
if(header)header.append(select);
})();

