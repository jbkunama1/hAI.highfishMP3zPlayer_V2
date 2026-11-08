(() => {
'use strict';
function init(){
if(document.getElementById('ai-playlist'))return;
const dialog=document.createElement('dialog');dialog.id='ai-playlist';dialog.setAttribute('aria-label','KI-Playlist-Assistent');
dialog.innerHTML='<h2>Dein KI-Mixtape</h2><p>Beschreibe Thema, Stimmung oder Musikwünsche. Nur Titel aus deiner Sammlung werden übernommen.</p><button data-a="close">Schließen</button><button data-a="reset">Neue Unterhaltung</button><div class="chat" aria-live="polite"></div><label>Dein Wunsch<textarea maxlength="2000" placeholder="20 Songs für eine entspannte Nachtfahrt"></textarea></label><button data-a="generate">Zusammenstellen / nachbessern</button><p class="state" role="status"></p><section class="preview"></section><button data-a="save" disabled>Als Playlist speichern</button><button data-a="queue" disabled>In Queue laden & abspielen</button>';
const css=document.createElement('style');css.textContent='#ai-playlist{position:fixed;inset:4dvh auto auto 50%;transform:translateX(-50%);width:min(94vw,800px);max-height:92dvh;overflow:auto;border:1px solid var(--border,#555);border-radius:20px;padding:24px;background:var(--surf,#171725);color:var(--text,#eee)}#ai-playlist::backdrop{background:#000b}#ai-playlist button,#ai-playlist textarea{font:inherit;background:var(--card,#252535);color:inherit;border:1px solid var(--border,#666);border-radius:10px;padding:12px;margin:5px;min-height:44px}#ai-playlist textarea{display:block;width:95%;min-height:100px}#ai-playlist button:disabled{opacity:.45}#ai-playlist li,#ai-playlist p{overflow-wrap:anywhere;white-space:pre-wrap;margin:10px 0}#ai-playlist .chat{border-left:3px solid var(--acc,#f85);padding-left:12px}';document.head.append(css);document.body.append(dialog);
const open=document.createElement('button');open.textContent='KI-Playlist';open.type='button';open.className='d-btn';(document.querySelector('header')||document.body).append(open);
let draft=null,busy=false;const chat=dialog.querySelector('.chat'),status=dialog.querySelector('.state'),preview=dialog.querySelector('.preview'),input=dialog.querySelector('textarea');
const actions=()=>dialog.querySelectorAll('[data-a="save"],[data-a="queue"]');
function line(text,target=chat){const p=document.createElement('p');p.textContent=text;target.append(p);}
async function api(data){const r=await fetch('/api/ai-playlist',{method:data?'POST':'GET',headers:{'X-API-Key':localStorage.getItem('mp3z_apikey')||'','Content-Type':'application/json'},cache:'no-store',...(data?{body:JSON.stringify(data)}:{})});const value=await r.json();if(!r.ok)throw Error(value.error||'Anfrage fehlgeschlagen');return value;}
open.onclick=async()=>{dialog.showModal();try{const s=await api();status.textContent=!s.enabled?'KI ist deaktiviert. AI_PLAYLIST_ENABLED=true setzen.':!s.configured?'Serverseitigen LLM_API_KEY hinterlegen.':'Bereit. Wünsche und Kandidatenmetadaten werden an den konfigurierten LLM-Dienst gesendet.';}catch(e){status.textContent=e.message;}};
dialog.addEventListener('keydown',e=>e.stopPropagation());
dialog.addEventListener('click',async e=>{const action=e.target.closest('[data-a]')?.dataset.a;if(!action)return;if(action==='close'){dialog.close();return;}if(busy)return;
if(action==='reset'){draft=null;chat.replaceChildren();preview.replaceChildren();input.value='';actions().forEach(b=>b.disabled=true);return;}
busy=true;dialog.querySelector('[data-a="generate"]').disabled=true;actions().forEach(b=>b.disabled=true);
try{
if(action==='generate'){
const prompt=input.value.trim();if(!prompt)throw Error('Bitte Musikwunsch eingeben.');status.textContent='Suche und stelle dein Mixtape zusammen…';
const next=await api({action:'generate',prompt,previous:draft?.draft_id||''});draft=next;line('Du: '+prompt);line('KI: '+draft.explanation);input.value='';preview.replaceChildren();line(draft.name,preview);draft.warnings.forEach(w=>line(w,preview));const list=document.createElement('ol');draft.tracks.forEach(t=>{const li=document.createElement('li');li.textContent=t.name;list.append(li);});preview.append(list);status.textContent=draft.tracks.length+' Titel in der Vorschau. Noch nicht gespeichert.';
}
if(action==='save'&&draft){const name=prompt('Playlistname',draft.name);if(name){const result=await api({action:'save',draft_id:draft.draft_id,name,confirmed:true});status.textContent='Gespeichert: '+result.id;draft.saved_id=result.id;}}
if(action==='queue'&&draft){if(typeof queue==='undefined'||typeof loadTrack!=='function')throw Error('Player-Schnittstelle fehlt.');if(queue.length&&!confirm('Aktuelle Queue ersetzen?'))return;queue=draft.tracks.map(t=>({...t}));queueIdx=-1;loadTrack(0);if(typeof renderQueue==='function')renderQueue();dialog.close();}
}catch(err){status.textContent=err.message;}finally{busy=false;dialog.querySelector('[data-a="generate"]').disabled=false;actions().forEach(b=>b.disabled=!draft);if(draft?.saved_id)dialog.querySelector('[data-a="save"]').disabled=true;}
});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
