/* Responsive library shell; playback remains owned by the existing player. */
(() => {
'use strict';
function start() {
const byId=id=>document.getElementById(id), header=document.querySelector('#app > header');
const player=byId('player'), opener=byId('mobile-open-view');
if(!header||!player||!opener||byId('mobile-library-menu'))return;
const media=matchMedia('(max-width:759px)'), html=document.documentElement;
const menu=document.createElement('dialog');menu.id='mobile-library-menu';menu.setAttribute('aria-labelledby','mobile-menu-title');
menu.innerHTML='<h2 id="mobile-menu-title">Menü</h2><button type="button" class="mobile-menu-close">Schließen</button><div class="mobile-menu-items"></div>';
document.body.append(menu);
const toggle=document.createElement('button');toggle.id='mobile-menu-toggle';toggle.type='button';toggle.textContent='Menü';toggle.setAttribute('aria-haspopup','dialog');toggle.setAttribute('aria-controls',menu.id);toggle.setAttribute('aria-expanded','false');header.prepend(toggle);
const close=()=>{if(menu.open)menu.close();};
menu.querySelector('.mobile-menu-close').onclick=close;
menu.addEventListener('close',()=>{toggle.setAttribute('aria-expanded','false');if(media.matches)toggle.focus();});
menu.addEventListener('keydown',e=>e.stopPropagation());
toggle.onclick=()=>{
const items=menu.querySelector('.mobile-menu-items');items.replaceChildren();
for(const target of header.querySelectorAll('button,a[href]')){
if(target===toggle||target.id==='btn-queue'||target.hidden)continue;
const button=document.createElement('button');button.type='button';
button.textContent=target.id==='admin-open'?'Ansicht & Verwaltung':target.id==='btn-settings'?'Einstellungen':target.textContent.trim()||target.title||target.getAttribute('aria-label')||'Öffnen';
button.disabled=target.disabled;button.onclick=()=>{close();target.click();};items.append(button);
}
menu.showModal();toggle.setAttribute('aria-expanded','true');menu.querySelector('.mobile-menu-close').focus();
};
const search=byId('search'), oldPlaceholder=search?.getAttribute('placeholder');
const targets=['p-info','p-art'].map(byId).filter(Boolean);
const saved=new Map(targets.map(el=>[el,['role','tabindex','aria-label'].map(k=>[k,el.getAttribute(k)])]));
function openPlayer(){if(media.matches)opener.click();}
for(const el of targets){el.addEventListener('click',openPlayer);el.addEventListener('keydown',e=>{if(media.matches&&['Enter',' '].includes(e.key)){e.preventDefault();e.stopPropagation();openPlayer();}});}
function apply(){
html.classList.toggle('mp3z-mobile',media.matches);
if(search){if(media.matches)search.setAttribute('placeholder','Musik suchen …');else if(oldPlaceholder===null)search.removeAttribute('placeholder');else search.setAttribute('placeholder',oldPlaceholder);}
for(const el of targets){if(media.matches){el.setAttribute('role','button');el.tabIndex=0;el.setAttribute('aria-label','Große Playeransicht öffnen');}else for(const [key,value]of saved.get(el)){if(value===null)el.removeAttribute(key);else el.setAttribute(key,value);}}
if(!media.matches)close();
}
const style=document.createElement('style');style.id='mobile-layout-style';style.textContent=`
#mobile-menu-toggle{display:none}
#mobile-library-menu{margin:auto;width:min(92vw,420px);max-height:85vh;max-height:85dvh;overflow:auto;padding:20px;border:1px solid var(--border);border-radius:var(--r);background:var(--surf);color:var(--text);font:inherit}
#mobile-library-menu::backdrop{background:#000b}
#mobile-library-menu h2{font-size:20px;margin:0 0 12px}
#mobile-library-menu button{min-height:44px;padding:10px 12px;border:1px solid var(--border);border-radius:var(--r);background:var(--card);color:var(--text);font:inherit;text-align:left}
.mobile-menu-items{display:grid;gap:8px;margin-top:12px}
#mobile-library-menu button:focus-visible,html.mp3z-mobile #player [role=button]:focus-visible{outline:3px solid var(--acc);outline-offset:-3px}
html.mp3z-mobile{--mobile-player-height:calc(72px + env(safe-area-inset-bottom));--ph:var(--mobile-player-height)}
html.mp3z-mobile #app{height:100vh;height:100dvh;min-width:0;padding-bottom:var(--mobile-player-height)}
html.mp3z-mobile #app > header{display:flex;flex-wrap:wrap;gap:6px;padding:6px 10px;min-width:0}
html.mp3z-mobile #app > header > :not(.logo):not(#breadcrumb):not(#btn-queue):not(#mobile-menu-toggle){display:none!important}
html.mp3z-mobile #mobile-menu-toggle{display:block;order:-2;min-height:44px;padding:8px 12px;border:1px solid var(--border);border-radius:var(--r);background:var(--card);color:var(--text);font:inherit}
html.mp3z-mobile header .logo{order:-1;flex:1;text-align:center;font-size:24px}
html.mp3z-mobile #btn-queue{order:0;width:44px;min-height:44px}
html.mp3z-mobile #breadcrumb{order:1;flex:0 0 100%;width:100%;min-width:0;min-height:26px;overflow-x:auto;white-space:nowrap}
html.mp3z-mobile #breadcrumb .crumb{flex-shrink:0;max-width:70vw}
html.mp3z-mobile #search-wrap{min-width:0;padding:6px 10px;gap:6px}
html.mp3z-mobile #search{width:0;min-width:0;flex:1 1 0;min-height:44px;font-size:16px}
html.mp3z-mobile #search-mode{font-size:9px;letter-spacing:0}
html.mp3z-mobile #view-toolbar{flex-wrap:nowrap;gap:6px;padding:4px 10px;min-width:0}
html.mp3z-mobile .view-picker{min-width:0;font-size:12px;gap:6px}
html.mp3z-mobile .view-picker select{min-width:0;max-width:140px;min-height:44px;padding:6px;font-size:13px}
html.mp3z-mobile #view-count{white-space:nowrap;font-size:11px}
html.mp3z-mobile #browser{min-height:0;min-width:0;padding-bottom:12px}
html.mp3z-mobile #load-more-wrap{flex-shrink:0;padding:6px 10px 10px;max-height:25dvh;overflow-y:auto}
html.mp3z-mobile #player{--ph:var(--mobile-player-height);left:0;right:0;transform:none;width:100%;max-width:none;height:var(--mobile-player-height);display:grid!important;grid-template-columns:44px minmax(0,1fr) 44px 44px!important;grid-template-rows:48px!important;gap:6px;padding:10px 10px calc(10px + env(safe-area-inset-bottom))}
html.mp3z-mobile #p-art{grid-column:1!important;grid-row:1!important;width:44px;height:44px;cursor:pointer}
html.mp3z-mobile #p-info{grid-column:2!important;grid-row:1!important;min-width:0;cursor:pointer}
html.mp3z-mobile #p-title{font-size:14px}
html.mp3z-mobile #p-sub{font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
html.mp3z-mobile #btn-play{grid-column:3!important;grid-row:1!important;width:44px;height:44px;min-height:44px;justify-self:center}
html.mp3z-mobile #btn-next{grid-column:4!important;grid-row:1!important;width:44px;height:44px;min-height:44px;justify-self:center}
html.mp3z-mobile #player :is(#btn-prev,#btn-shuffle,#btn-repeat){display:none!important}
html.mp3z-mobile #queue-drawer{bottom:var(--mobile-player-height);max-height:55dvh}
html.mp3z-mobile #toast{bottom:calc(var(--mobile-player-height) + 10px);max-width:94vw;white-space:normal}
`;
document.head.append(style);media.addEventListener('change',apply);apply();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
