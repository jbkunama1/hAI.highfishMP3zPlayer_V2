(() => {
'use strict';
function install(){const d=document.getElementById('ai-playlist');if(!d||d.querySelector('.catalog-tools'))return false;
const box=document.createElement('section');box.className='catalog-tools';box.innerHTML='<h3>Metadaten & Filter</h3><p>Filter werden aus deinem Wunsch ermittelt. Für zuverlässige Genre-, Sprach- und Jahresfilter zuerst den MP3-Katalog scannen. Fehlende Tags zählen nicht als Treffer.</p><button type="button" class="scan">MP3-Metadaten scannen</button><button type="button" class="stop">Scan nach Batch stoppen</button><p class="progress" role="status"></p>';d.querySelector('textarea').parentElement.before(box);
let stop=false,running=false;const status=box.querySelector('.progress');const headers=()=>({'X-API-Key':localStorage.getItem('mp3z_apikey')||'','Content-Type':'application/json'});
box.querySelector('.stop').onclick=()=>{stop=true;status.textContent='Scan stoppt nach dem laufenden Batch.';};
box.querySelector('.scan').onclick=async()=>{if(running||!confirm('MP3-Metadaten aus deiner Sammlung lesen und lokal katalogisieren? Es werden keine Musikdateien geändert. Bei SMB kann das dauern.'))return;running=true;stop=false;box.querySelector('.scan').disabled=true;let offset=0,failed=0;
try{while(!stop){const r=await fetch('/api/ai-library',{method:'POST',headers:headers(),body:JSON.stringify({offset,confirmed:true})});const s=await r.json();if(!r.ok)throw Error(s.error||'Scan fehlgeschlagen');failed+=s.failed;offset=s.next_offset;status.textContent=offset+' / '+s.total_mp3+' MP3 geprüft, '+failed+' Fehler. '+s.cached_mp3+' im Katalog.';if(s.done)break;}}catch(e){status.textContent=e.message;}finally{running=false;box.querySelector('.scan').disabled=false;}};
fetch('/api/ai-library',{headers:headers(),cache:'no-store'}).then(r=>r.ok?r.json():null).then(s=>{if(s)status.textContent=s.cached_mp3+' MP3 im Katalog.';}).catch(()=>{});
return true;}
if(!install()){const observer=new MutationObserver(()=>{if(install())observer.disconnect();});observer.observe(document.documentElement,{childList:true,subtree:true});setTimeout(()=>observer.disconnect(),15000);}
})();
