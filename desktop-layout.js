/* Desktop enhancement; existing navigation handlers and audio state are reused. */
(() => {
'use strict';
const time=n=>Number.isFinite(n)&&n>=0?Math.floor(n/60)+':'+String(Math.floor(n%60)).padStart(2,'0'):'0:00';
if(typeof module!=='undefined'&&module.exports)module.exports={time};
if(typeof document==='undefined')return;
function start(){
const id=n=>document.getElementById(n),app=id('app'),header=app?.querySelector('header'),audio=id('audio'),player=id('player'),drawer=id('queue-drawer'),crumb=id('breadcrumb');
if(!app||!header||!audio||!player||!drawer||!crumb||id('desktop-nav'))return;
const media=matchMedia('(min-width:760px)'),html=document.documentElement;
const nav=document.createElement('aside');nav.id='desktop-nav';nav.setAttribute('aria-label','Hauptnavigation');app.append(nav);
const toggle=document.createElement('button');toggle.type='button';toggle.id='desktop-nav-toggle';toggle.textContent='Navigation';toggle.setAttribute('aria-controls',nav.id);toggle.setAttribute('aria-expanded','true');header.prepend(toggle);
toggle.onclick=()=>{const collapsed=app.classList.toggle('desktop-nav-collapsed');toggle.setAttribute('aria-expanded',String(!collapsed));};
const path=document.createElement('div');path.id='desktop-path';app.append(path);const anchor=document.createComment('breadcrumb original position');crumb.before(anchor);
function buildNav(){nav.replaceChildren();const home=document.createElement('button');home.type='button';home.textContent='Bibliothek';home.onclick=()=>crumb.querySelector('.crumb')?.click();nav.append(home);
for(const target of header.querySelectorAll('button,a[href]')){if([toggle,id('mobile-menu-toggle'),id('btn-queue')].includes(target)||target.hidden)continue;const b=document.createElement('button');b.type='button';b.textContent=target.id==='admin-open'?'Ansicht & Verwaltung':target.id==='btn-settings'?'Einstellungen':target.textContent.trim()||target.title||'Öffnen';b.disabled=!!target.disabled;b.onclick=()=>target.click();nav.append(b);}}
new MutationObserver(()=>{if(media.matches)buildNav();}).observe(header,{childList:true});
const close=document.createElement('button');close.id='desktop-queue-close';close.type='button';close.textContent='Schließen';close.onclick=()=>id('btn-queue')?.click();(drawer.querySelector('.d-actions')||drawer).append(close);
const seekBox=document.createElement('div');seekBox.id='desktop-seek';seekBox.innerHTML='<span>0:00</span><input type="range" min="0" max="1000" value="0" aria-label="Wiedergabeposition"><span>0:00</span>';player.append(seekBox);
const seek=seekBox.querySelector('input'),times=seekBox.querySelectorAll('span');
const volumeBox=document.createElement('label');volumeBox.id='desktop-volume';volumeBox.textContent='Lautstärke';const volume=document.createElement('input');volume.type='range';volume.min='0';volume.max='1';volume.step='0.01';volume.setAttribute('aria-label','Lautstärke');volumeBox.append(volume);player.append(volumeBox);
let dragging=false;
function sync(){const duration=audio.duration;seek.disabled=!Number.isFinite(duration)||duration<=0;if(!dragging)seek.value=seek.disabled?'0':String(Math.round(audio.currentTime/duration*1000));times[0].textContent=time(audio.currentTime);times[1].textContent=time(duration);volume.value=String(audio.muted?0:audio.volume);}
seek.addEventListener('input',()=>{dragging=true;times[0].textContent=time(Number(seek.value)/1000*audio.duration);});
seek.addEventListener('change',()=>{if(Number.isFinite(audio.duration)&&audio.duration>0)audio.currentTime=Number(seek.value)/1000*audio.duration;dragging=false;sync();});
seek.addEventListener('blur',()=>{dragging=false;sync();});
volume.addEventListener('input',()=>{audio.muted=false;audio.volume=Number(volume.value);});
for(const input of [seek,volume])input.addEventListener('keydown',e=>e.stopPropagation());
for(const name of ['timeupdate','durationchange','loadedmetadata','emptied','volumechange'])audio.addEventListener(name,sync);
function queueState(){const open=drawer.classList.contains('open');app.classList.toggle('desktop-queue-open',open);if(media.matches){drawer.inert=!open;drawer.setAttribute('aria-hidden',String(!open));}}
new MutationObserver(queueState).observe(drawer,{attributes:true,attributeFilter:['class']});
function apply(){toggle.hidden=!media.matches;html.classList.toggle('mp3z-desktop',media.matches);if(media.matches){path.append(crumb);buildNav();queueState();sync();}else{anchor.after(crumb);drawer.inert=false;drawer.removeAttribute('aria-hidden');}}
const style=document.createElement('style');style.id='desktop-layout-style';style.textContent=`
#desktop-nav,#desktop-nav-toggle,#desktop-path,#desktop-seek,#desktop-volume,#desktop-queue-close{display:none}
html.mp3z-desktop{--ph:116px}
html.mp3z-desktop #app{position:relative;display:grid;max-width:1600px;width:100%;margin:auto;height:100vh;height:100dvh;grid-template-columns:200px minmax(0,1fr);grid-template-rows:auto auto auto auto minmax(0,1fr) auto 116px;overflow:hidden;padding:0}
html.mp3z-desktop #app > header{grid-column:1/-1;grid-row:1;min-width:0;flex-wrap:wrap;min-height:60px;padding:8px 16px}
html.mp3z-desktop #app > header > :not(.logo):not(#btn-queue):not(#desktop-nav-toggle){display:none!important}
html.mp3z-desktop header .logo{flex:1}
html.mp3z-desktop #desktop-nav-toggle{display:block}
html.mp3z-desktop :is(#desktop-nav-toggle,#desktop-nav button,#desktop-queue-close){font:inherit;min-height:44px;padding:8px 12px;background:var(--card);color:var(--text);border:1px solid var(--border);border-radius:var(--r)}
html.mp3z-desktop #desktop-nav{display:flex;flex-direction:column;gap:10px;grid-column:1;grid-row:2/7;min-height:0;overflow:auto;padding:16px 12px;background:var(--surf);border-right:1px solid var(--border)}
html.mp3z-desktop #desktop-nav button{text-align:left;overflow-wrap:anywhere;flex-shrink:0}
html.mp3z-desktop #search-wrap{grid-column:2;grid-row:2;padding:12px 20px;min-width:0}
html.mp3z-desktop #search{min-width:0;width:0}
html.mp3z-desktop #desktop-path{display:block;grid-column:2;grid-row:3;min-width:0;padding:6px 20px}
html.mp3z-desktop #breadcrumb{overflow-x:auto;min-width:0;min-height:26px}
html.mp3z-desktop #breadcrumb .crumb{flex-shrink:0;max-width:70vw}
html.mp3z-desktop #view-toolbar{grid-column:2;grid-row:4;padding:6px 20px;min-width:0}
html.mp3z-desktop #browser{grid-column:2;grid-row:5;min-width:0;min-height:0;padding:12px 20px;container-type:inline-size}
html.mp3z-desktop #browser .entry{border:1px solid transparent}
html.mp3z-desktop #browser .entry:hover{border-color:var(--border)}
html.mp3z-desktop #browser .entry.playing{border-color:var(--acc)}
html.mp3z-desktop #browser[data-view=cards] .file-list{grid-template-columns:repeat(auto-fit,minmax(min(100%,160px),1fr))}
html.mp3z-desktop #load-more-wrap{grid-column:2;grid-row:6;padding:8px 20px;max-height:20dvh;overflow:auto}
html.mp3z-desktop #player{position:relative;grid-column:1/-1;grid-row:7;left:auto;right:auto;bottom:auto;transform:none;width:100%;max-width:none;height:116px;display:grid;grid-template-columns:52px minmax(100px,1fr) repeat(5,44px) minmax(100px,1fr);grid-template-rows:52px 32px;padding:10px 16px;gap:6px}
html.mp3z-desktop #p-art{grid-column:1;grid-row:1;width:48px;height:48px}
html.mp3z-desktop #p-info{grid-column:2;grid-row:1;min-width:0}
html.mp3z-desktop #p-sub{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
html.mp3z-desktop #btn-prev{grid-column:3;grid-row:1}
html.mp3z-desktop #btn-shuffle{grid-column:4;grid-row:1}
html.mp3z-desktop #btn-play{grid-column:5;grid-row:1}
html.mp3z-desktop #btn-repeat{grid-column:6;grid-row:1}
html.mp3z-desktop #btn-next{grid-column:7;grid-row:1}
html.mp3z-desktop #prog-wrap{display:none}
html.mp3z-desktop #desktop-seek{display:flex;grid-column:2/8;grid-row:2;align-items:center;gap:10px;min-width:0;font-size:12px;font-variant-numeric:tabular-nums}
html.mp3z-desktop #desktop-seek input{flex:1;min-width:0;width:0;accent-color:var(--acc)}
html.mp3z-desktop #desktop-volume{display:flex;grid-column:8;grid-row:1/3;flex-direction:column;justify-content:center;gap:8px;min-width:0;font-size:12px;padding-left:12px}
html.mp3z-desktop #desktop-volume input{width:100%;min-width:0;accent-color:var(--acc)}
html.mp3z-desktop #queue-drawer{display:none;position:absolute;left:auto;right:0;top:60px;bottom:116px;width:min(360px,85%);max-width:none;max-height:none;margin:0;transform:none;border:1px solid var(--border);border-radius:var(--r);z-index:110}
html.mp3z-desktop #queue-drawer.open{display:flex}
html.mp3z-desktop #desktop-queue-close{display:block}
html.mp3z-desktop #queue-list{min-height:0}
html.mp3z-desktop #toast{bottom:126px;max-width:90vw;white-space:normal}
html.mp3z-desktop #app.desktop-nav-collapsed{grid-template-columns:0 minmax(0,1fr)}
html.mp3z-desktop #app.desktop-nav-collapsed #desktop-nav{display:none}
@media(min-width:1200px){html.mp3z-desktop #app.desktop-queue-open{grid-template-columns:200px minmax(0,1fr) 320px}html.mp3z-desktop #app.desktop-nav-collapsed.desktop-queue-open{grid-template-columns:0 minmax(0,1fr) 320px}html.mp3z-desktop #queue-drawer.open{position:relative;grid-column:3;grid-row:2/7;inset:auto;width:auto;min-height:0;border-radius:0;z-index:auto}}
@media(min-width:760px) and (max-width:1199px){html.mp3z-desktop #app{grid-template-columns:160px minmax(0,1fr)}html.mp3z-desktop #player{grid-template-columns:44px minmax(80px,1fr) repeat(5,44px) 100px;padding-inline:10px}}
`;
document.head.append(style);media.addEventListener('change',apply);apply();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
