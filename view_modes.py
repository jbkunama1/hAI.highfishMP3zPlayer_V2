"""Optional browser views, mobile player and authenticated filename search."""
from pathlib import Path

EDITOR_SEARCH = r"""
(() => {
const path = document.getElementById('path'), load = document.getElementById('load');
if (!path || !load || document.getElementById('filename-search')) return;
const box = document.createElement('section');
box.innerHTML = '<label>MP3-Dateiname suchen<input id="filename-search" type="search" maxlength="200" placeholder="Mindestens 2 Zeichen" autocomplete="off"></label><p id="filename-status" role="status"></p><div id="filename-results"></div><button id="filename-more" type="button" hidden>Weitere Treffer</button>';
path.closest('label').before(box);
const query = box.querySelector('input'), status = box.querySelector('p'), results = box.querySelector('#filename-results'), more = box.querySelector('button');
let timer, controller, generation = 0, offset = 0;
async function search(append, version) {
controller?.abort(); controller = new AbortController();
more.hidden = true;
if (!append) {results.replaceChildren(); offset = 0;}
const q = query.value.trim();
if (q.length < 2) {status.textContent = 'Mindestens 2 Zeichen eingeben.'; return;}
status.textContent = 'Suche läuft…';
try {
const response = await fetch('/api/filename-search?' + new URLSearchParams({q,offset,limit:30}), {signal:controller.signal,cache:'no-store',headers:{'X-API-Key':localStorage.getItem('mp3z_apikey') || ''}});
const data = await response.json();
if (version !== generation) return;
if (!response.ok) throw Error(data.error || 'Suche fehlgeschlagen (' + response.status + ')');
for (const entry of data.results) {
const button = document.createElement('button'); button.type = 'button';
button.textContent = entry.name + ' — ' + entry.dir;
button.style.textAlign = 'left'; button.style.overflowWrap = 'anywhere';
button.onclick = () => {
if ([...document.querySelectorAll('#fields input')].some(i => i.value !== i.defaultValue) && !confirm('Ungespeicherte Eingaben verwerfen und diesen Titel laden?')) return;
path.value = entry.path; path.dispatchEvent(new Event('input',{bubbles:true})); load.click();
}; results.append(button);
}
offset += data.results.length; more.hidden = !data.has_more;
status.textContent = data.total ? Math.min(offset,data.total) + ' von ' + data.total + ' MP3-Treffern' : 'Keine passenden MP3-Dateien gefunden.';
} catch (error) {if (version === generation && error.name !== 'AbortError') {status.textContent = error.message;more.hidden = !append;}}
}
query.addEventListener('input',() => {clearTimeout(timer); controller?.abort();const version = ++generation;more.hidden=true;results.replaceChildren();status.textContent='';timer=setTimeout(()=>search(false,version),300);});
more.onclick = () => search(true,generation);
// Successful tag loads become the dirty-check baseline; failed loads do not.
const tagStatus = document.getElementById('status');
if (tagStatus) new MutationObserver(() => {
if (/^(Geladen|Gespeichert)/.test(tagStatus.textContent)) document.querySelectorAll('#fields input').forEach(i => {i.defaultValue=i.value;});
}).observe(tagStatus,{childList:true,subtree:true,characterData:true});
})();
"""

MOBILE_PRESETS = r"""
(() => {
const presets = {Aurora:['#153e45','#54315d'],Ember:['#6b2f20','#38243b'],Midnight:['#18234b','#342344'],Lagoon:['#124858','#205c51'],Plum:['#49213d','#293b58'],Copper:['#613e2b','#293e43'],Ice:['#304659','#25384d'],Crimson:['#641f37','#29263d']};
function start() {
const root=document.getElementById('mobile-now-playing'),select=root?.querySelector('select');
if(!select)return;
Object.keys(presets).forEach(name=>select.add(new Option(name,name)));
function apply(name){const colors=presets[name];if(!colors)return;root.style.setProperty('--mobile-a',colors[0]);root.style.setProperty('--mobile-b',colors[1]);select.value=name;try{localStorage.setItem('mp3z_mobile_gradient',name);}catch{}}
select.addEventListener('change',()=>apply(select.value));
try{apply(localStorage.getItem('mp3z_mobile_gradient'));}catch{}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
"""


def install_views(backend):
    from flask import request, Response, jsonify

    @backend.app.get('/view-modes.js')
    def view_modes_script():
        return Response(Path(__file__).with_name('view-modes.js').read_text(), mimetype='application/javascript', headers={'Cache-Control':'no-store'})

    @backend.app.get('/mobile-view.js')
    def mobile_view_script():
        return Response(Path(__file__).with_name('mobile-view.js').read_text(), mimetype='application/javascript', headers={'Cache-Control':'no-store'})

    @backend.app.get('/mobile-layout.js')
    def mobile_layout_script():
        return Response(Path(__file__).with_name('mobile-layout.js').read_text(encoding='utf-8'), mimetype='application/javascript', headers={'Cache-Control':'no-store'})

    @backend.app.get('/editor-search.js')
    def editor_search_script():
        return Response(EDITOR_SEARCH, mimetype='application/javascript', headers={'Cache-Control':'no-store'})

    @backend.app.get('/mobile-presets.js')
    def mobile_presets_script():
        return Response(MOBILE_PRESETS, mimetype='application/javascript', headers={'Cache-Control':'no-store'})

    @backend.app.get('/api/filename-search')
    def filename_search():
        if not backend.check_token(request.headers.get('X-API-Key','')):
            return jsonify(error='Unauthorized'),401
        try:
            offset = int(request.args.get('offset','0'))
            limit = int(request.args.get('limit','30'))
            if offset < 0 or not 1 <= limit <= 100:
                raise ValueError()
        except ValueError:
            return jsonify(error='Invalid pagination'),400
        q = request.args.get('q','').strip().casefold()
        if len(q)>200:
            return jsonify(error='Query exceeds 200 characters'),400
        hits = [] if len(q)<2 else [dict(name=e['name'],path=e['path'],dir=e['dir']) for e in backend.index.get() if e['name'].casefold().endswith('.mp3') and q in e['name'].casefold()]
        hits.sort(key=lambda e:(e['name'].casefold(),e['path']))
        return jsonify(results=hits[offset:offset+limit],total=len(hits),offset=offset,has_more=offset+limit<len(hits)),200,{'Cache-Control':'no-store'}

    @backend.app.after_request
    def add_view_modes(response):
        scripts = []
        if request.path == '/':
            scripts = ['view-modes.js','mobile-view.js','mobile-presets.js','mobile-layout.js']
        elif request.path == '/id3-editor':
            scripts = ['editor-search.js']
        if scripts and response.status_code == 200:
            response.direct_passthrough = False
            html = response.get_data(as_text=True)
            tags = ''.join('<script src="/'+name+'"></script>' for name in scripts if 'src="/'+name+'"' not in html)
            if '</body>' in html:
                html = html.replace('</body>',tags+'</body>')
            else:
                html = html.replace('</html>',tags+'</html>')
            response.set_data(html)
            response.headers.pop('ETag',None)
            response.headers.pop('Last-Modified',None)
            response.headers['Cache-Control']='no-store'
        if request.path == '/api/filename-search':
            response.headers['Cache-Control']='no-store'
        return response
