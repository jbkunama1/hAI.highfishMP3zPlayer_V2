/* Mobile now-playing view. Include after the existing player scripts. */
(() => {
'use strict';
function start() {
const byId = id => document.getElementById(id);
const audio = byId('audio');
if (!audio || byId('mobile-now-playing')) return;
const themes = {Ocean:['#123b59','#146b72'],Synthwave:['#47265d','#8b315b'],Forest:['#173e30','#51612d'],Sunset:['#693b38','#674165'],Graphite:['#434950','#252832']};
const root = document.createElement('section');
root.id = 'mobile-now-playing'; root.hidden = true;
root.setAttribute('aria-label','Aktuelle Wiedergabe');
const style = document.createElement('style');
style.textContent = `
#mobile-now-playing[hidden]{display:none!important}
#mobile-now-playing{position:fixed;inset:0;z-index:250;overflow-y:auto;display:flex;flex-direction:column;gap:18px;padding:calc(12px + env(safe-area-inset-top)) 22px calc(16px + env(safe-area-inset-bottom));background:linear-gradient(145deg,var(--mobile-a,#123b59),var(--mobile-b,#146b72) 45%,#101218 100%);color:#fff;font-family:system-ui,sans-serif;isolation:isolate}
#mobile-now-playing *{box-sizing:border-box}
#mobile-now-playing button,#mobile-now-playing select{font:inherit;color:inherit;min-height:44px;border:0;border-radius:12px;background:transparent;cursor:pointer}
#mobile-now-playing button:focus-visible,#mobile-now-playing select:focus-visible,#mobile-now-playing input:focus-visible{outline:3px solid white;outline-offset:3px}
#mobile-now-playing .mobile-top,#mobile-now-playing .mobile-controls,#mobile-now-playing .mobile-actions,#mobile-now-playing .mobile-bottom{display:flex;align-items:center;justify-content:space-between;gap:6px;flex-shrink:0}
#mobile-now-playing .mobile-top span{font-size:12px;letter-spacing:2px;text-transform:uppercase;opacity:.75}
#mobile-now-playing .mobile-art{width:100%;height:min(37dvh,380px);min-height:140px;display:grid;place-items:center;margin:8px 0 10px;background:#0002;border-radius:16px;overflow:hidden;box-shadow:0 18px 45px #0004}
#mobile-now-playing .mobile-art img{width:100%;height:100%;object-fit:contain}
#mobile-now-playing h1{font-size:clamp(24px,7vw,36px);line-height:1.15;margin:0 0 10px;overflow-wrap:anywhere}
#mobile-now-playing p{margin:6px 0;color:#ffffffb8;overflow-wrap:anywhere}
#mobile-now-playing .mobile-times{display:flex;justify-content:space-between;font-variant-numeric:tabular-nums;font-size:14px}
#mobile-now-playing input{width:100%;min-width:0;accent-color:white;min-height:44px}
#mobile-now-playing .mobile-controls button{flex:1;font-size:22px;min-width:0}
#mobile-now-playing .mobile-controls [data-action=play]{font-size:34px;min-height:76px}
#mobile-now-playing .mobile-actions button{flex:1;font-size:14px}
#mobile-now-playing button[aria-pressed=true]{background:#ffffff25}
#mobile-now-playing .mobile-bottom{margin-top:auto;border-top:1px solid #ffffff25;padding-top:12px;flex-wrap:wrap}
#mobile-now-playing .mobile-bottom button{padding:8px;font-size:13px}
#mobile-now-playing select{max-width:130px;background:#151921;padding:8px}
#mobile-now-playing option{background:#151921;color:white}
#mobile-open-view{min-height:44px;padding:8px 12px;color:var(--text,#fff);background:var(--card,#252832);border:1px solid var(--border,#555);border-radius:10px}
@media(min-width:821px){#mobile-now-playing{left:50%;right:auto;width:min(100%,560px);transform:translateX(-50%);box-shadow:0 0 80px #0008}}
`;
document.head.append(style);
root.innerHTML = `<div class="mobile-top"><button data-action="close" aria-label="Playeransicht schliessen">Zurück</button><span>Jetzt läuft</span><button data-action="theme" aria-label="Nächster Farbverlauf">Design</button></div><div class="mobile-art" aria-label="Albumcover"></div><div><h1>Kein Titel</h1><p class="mobile-artist">—</p><p class="mobile-album">—</p></div><div class="mobile-actions"><button data-action="shuffle" aria-pressed="false">Shuffle</button><button data-action="repeat" aria-pressed="false">Repeat</button><button data-action="queue">Queue</button></div><div><div class="mobile-times"><span class="mobile-elapsed">0:00</span><span class="mobile-duration">0:00</span></div><input type="range" min="0" max="1000" value="0" aria-label="Wiedergabeposition"></div><div class="mobile-controls"><button data-action="prev" aria-label="Vorheriger Titel">⏮</button><button data-action="back" aria-label="15 Sekunden zurück">−15</button><button data-action="play" aria-label="Wiedergabe starten">▶</button><button data-action="forward" aria-label="15 Sekunden vor">+15</button><button data-action="next" aria-label="Nächster Titel">⏭</button></div><nav class="mobile-bottom" aria-label="Playernavigation"><button data-action="library">Bibliothek</button><button data-action="search">Suche</button><label>Farben <select aria-label="Farbverlauf"></select></label></nav>`;
document.body.append(root);
const select = root.querySelector('select');
for (const name of Object.keys(themes)) select.add(new Option(name,name));
let previousFocus = null;
let chosen = 'Ocean';
try {chosen = localStorage.getItem('mp3z_mobile_gradient') || chosen;} catch {}
function apply(name) {if (!themes[name]) name='Ocean';chosen=name;select.value=name;root.style.setProperty('--mobile-a',themes[name][0]);root.style.setProperty('--mobile-b',themes[name][1]);try {localStorage.setItem('mp3z_mobile_gradient',name);} catch {}}
apply(chosen);select.addEventListener('change',()=>apply(select.value));
const time = n => {n=Number.isFinite(n)?Math.max(0,n):0;return Math.floor(n/60)+':'+String(Math.floor(n%60)).padStart(2,'0');};
const seek = root.querySelector('input');
const art = root.querySelector('.mobile-art');let artSource='';
function sync() {
root.querySelector('h1').textContent=byId('p-title')?.textContent || 'Kein Titel';
root.querySelector('.mobile-artist').textContent=byId('p-sub')?.textContent || '—';
let path='';try {if(typeof queue!=='undefined' && typeof queueIdx!=='undefined')path=queue[queueIdx]?.path || '';} catch {}
root.querySelector('.mobile-album').textContent=path.includes('/')?path.split('/').slice(-2,-1)[0]:'—';
const src=byId('p-art')?.querySelector('img')?.getAttribute('src') || '';
if(src!==artSource){artSource=src;art.replaceChildren();if(src){const image=document.createElement('img');image.src=src;image.alt='Albumcover';image.onerror=()=>{art.textContent='Kein Cover';};art.append(image);}else art.textContent='Kein Cover';}
if(!src && !art.childNodes.length)art.textContent='Kein Cover';
const play=root.querySelector('[data-action=play]');play.textContent=audio.paused?'▶':'❚❚';play.setAttribute('aria-label',audio.paused?'Wiedergabe starten':'Wiedergabe pausieren');
for(const action of ['shuffle','repeat'])root.querySelector('[data-action='+action+']').setAttribute('aria-pressed',String(!!byId('btn-'+action)?.classList.contains('active')));
root.querySelector('.mobile-elapsed').textContent=time(audio.currentTime);
root.querySelector('.mobile-duration').textContent=time(audio.duration);
seek.disabled=!Number.isFinite(audio.duration)||audio.duration<=0;
if(document.activeElement!==seek)seek.value=seek.disabled?0:Math.round(audio.currentTime/audio.duration*1000);
}
function open(){previousFocus=document.activeElement;root.hidden=false;sync();root.querySelector('[data-action=close]').focus();}
function close(){root.hidden=true;previousFocus?.focus();}
const opener=document.createElement('button');opener.id='mobile-open-view';opener.type='button';opener.textContent='Playeransicht';opener.addEventListener('click',open);(document.querySelector('header')||document.body).append(opener);
root.addEventListener('click',event=>{const action=event.target.closest('[data-action]')?.dataset.action;if(!action)return;
if(['close','library'].includes(action)){close();return;}
if(action==='search'){close();byId('search')?.focus();return;}
if(action==='queue'){close();byId('btn-queue')?.click();return;}
if(action==='theme'){const names=Object.keys(themes);apply(names[(names.indexOf(chosen)+1)%names.length]);return;}
if(action==='back'||action==='forward'){if(Number.isFinite(audio.duration))audio.currentTime=Math.max(0,Math.min(audio.duration,audio.currentTime+(action==='back'?-15:15)));return;}
byId('btn-'+action)?.click();sync();});
root.addEventListener('keydown',event=>{if(event.key==='Escape'){event.stopPropagation();close();}else if(event.key===' '&&event.target===seek)event.stopPropagation();});
seek.addEventListener('change',()=>{if(Number.isFinite(audio.duration))audio.currentTime=Number(seek.value)/1000*audio.duration;});
for(const event of ['play','pause','timeupdate','durationchange','loadedmetadata','ended'])audio.addEventListener(event,()=>{if(!root.hidden)sync();});
const observer=new MutationObserver(()=>{if(!root.hidden)sync();});
for(const id of ['p-title','p-sub','p-art','btn-shuffle','btn-repeat']){const element=byId(id);if(element)observer.observe(element,{subtree:true,childList:true,characterData:true,attributes:true});}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
