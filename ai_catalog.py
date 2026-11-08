"""Phase 2a: explicit MP3 metadata catalog, strict filters and duration totals."""
import contextvars
import hashlib
import json
import math
import re
import sqlite3
import threading
from pathlib import Path
from ai_playlist import AIError
from playlist_service import PlaylistStore


def filters(value):
    if not isinstance(value,dict) or set(value)-{'genre','language','year_from','year_to'}:raise AIError('Ungültige Filter.')
    result={}
    for key in ('genre','language'):
        v=value.get(key,'')
        if not isinstance(v,str) or len(v)>80:raise AIError('Ungültiger Textfilter.')
        if v.strip():result[key]=v.strip().casefold()
    aliases={'de':'deu','deutsch':'deu','ger':'deu','en':'eng','english':'eng','englisch':'eng','fr':'fra','fre':'fra'}
    if 'language' in result:result['language']=aliases.get(result['language'],result['language'])
    for key in ('year_from','year_to'):
        v=value.get(key)
        if v is not None:
            if type(v) is not int or not 1000<=v<=2999:raise AIError('Jahr muss zwischen 1000 und 2999 liegen.')
            result[key]=v
    if result.get('year_from',1000)>result.get('year_to',2999):raise AIError('Jahresbereich ist vertauscht.')
    return result


def matches(row,f):
    if f.get('genre') and f['genre'] not in row.get('genre','').casefold():return False
    if f.get('language') and f['language'] not in re.split(r'[,;/ ]+',row.get('language','').casefold()):return False
    if ('year_from' in f or 'year_to' in f) and not f.get('year_from',1000)<=row.get('year',0)<=f.get('year_to',2999):return False
    return True


class Catalog:
    def __init__(self,filename):
        self.filename=str(filename);self.scan_lock=threading.Lock()
        db=self.connect()
        try:
            with db:db.execute('CREATE TABLE IF NOT EXISTS tracks (path TEXT PRIMARY KEY, data TEXT NOT NULL, search TEXT NOT NULL)')
        finally:db.close()

    def connect(self):return sqlite3.connect(self.filename,timeout=10)

    def put(self,row):
        path=PlaylistStore.path(row['path'])
        text=' '.join(str(row.get(k,'')) for k in ('path','title','artist','album','genre','language','year')).casefold()
        db=self.connect()
        try:
            with db:db.execute('INSERT OR REPLACE INTO tracks VALUES (?,?,?)',(path,json.dumps(row,ensure_ascii=False),text))
        finally:db.close()

    def get(self,path):
        db=self.connect()
        try:
            row=db.execute('SELECT data FROM tracks WHERE path=?',(path,)).fetchone()
            return json.loads(row[0]) if row else {}
        finally:db.close()

    def status(self):
        db=self.connect()
        try:return {'cached_mp3':db.execute('SELECT COUNT(*) FROM tracks').fetchone()[0]}
        finally:db.close()

    def search(self,query,f,limit=50):
        terms=re.findall(r'\w+',query.casefold())[:6]
        clause=' OR '.join('search LIKE ?' for t in terms) or '1'
        db=self.connect()
        try:
            rows=db.execute('SELECT data FROM tracks WHERE '+clause+' ORDER BY path',tuple('%'+t+'%' for t in terms))
            result=[]
            for row in rows:
                item=json.loads(row[0])
                if matches(item,f):result.append(item)
                if len(result)>=limit:break
            return result
        finally:db.close()

    @staticmethod
    def read(storage,path):
        from metadata_service import MetadataService
        from mutagen.mp3 import MP3
        rel=MetadataService(storage).path(path)
        if storage.mode=='local':handle=storage.open(rel)
        else:handle=storage.sc.open_file(storage._unc(rel),mode='rb',port=storage.port)
        with handle as stream:audio=MP3(stream)
        tags=audio.tags or {}
        row={'path':rel}
        for key,frame in {'title':'TIT2','artist':'TPE1','album':'TALB','genre':'TCON','language':'TLAN'}.items():row[key]=str(tags.get(frame,''))[:500]
        year=re.match(r'^(\d{4})',str(tags.get('TDRC','')))
        row['year']=int(year[1]) if year else 0
        length=getattr(audio.info,'length',None)
        row['duration']=round(length,3) if isinstance(length,(int,float)) and math.isfinite(length) and length>0 else None
        return row

    def scan(self,lib,offset):
        if type(offset) is not int or offset<0:raise AIError('Ungültiger Scan-Offset.')
        if not self.scan_lock.acquire(blocking=False):raise AIError('Ein Scan-Batch läuft bereits.')
        try:
            index=lib.b.index
            with index._lock:paths=sorted({e['path'] for e in index._entries if str(e.get('path','')).lower().endswith('.mp3')})
            ok=0;failed=0
            for path in paths[offset:offset+10]:
                try:self.put(self.read(lib.b.STORAGE,path));ok+=1
                except Exception:
                    failed+=1
                    db=self.connect()
                    try:
                        with db:db.execute('DELETE FROM tracks WHERE path=?',(path,))
                    finally:db.close()
            next_offset=min(offset+10,len(paths))
            return {'next_offset':next_offset,'total_mp3':len(paths),'ok':ok,'failed':failed,'done':next_offset>=len(paths),**self.status()}
        finally:self.scan_lock.release()


def install_catalog(lib):
    from flask import request,jsonify,Response
    from types import SimpleNamespace
    assistant=lib.ai_playlists
    catalog=Catalog(Path(lib.playlists.filename).with_name('ai-catalog.sqlite3'))
    lib.ai_catalog=catalog
    state=contextvars.ContextVar('mp3z_ai_catalog',default=None)
    original_call=assistant.call

    def search(query,offset=0,limit=50):
        f=(state.get() or {}).get('filters',{})
        rows=catalog.search(query,f,limit)
        if not rows and not f:return lib.search(query,offset,limit)
        return {'results':rows}
    assistant.lib=SimpleNamespace(search=search,b=lib.b,playlists=lib.playlists)

    def call(instruction,data):
        context=state.get()
        if context is None:return original_call(instruction,data)
        if 'candidates' not in data:
            result=original_call(instruction+' Also return filters: {genre,language,year_from,year_to} inferred from all wishes. Omit unknown values; do not infer language from nationality. Use ISO-639-2 language codes.',data)
            inferred=filters(result.get('filters',{}))
            inferred.update(context['explicit']);context['filters']=filters(inferred)
            return result
        f=context.get('filters',{})
        rows=[];allowed=set()
        for row in data['candidates']:
            meta=context['by_id'].get(row['id'],{})
            if f and (not meta or not matches(meta,f)):continue
            clean={**row,**{k:meta.get(k) for k in ('title','artist','album','genre','language','year','duration') if meta.get(k)}}
            rows.append(clean);allowed.add(row['id'])
        if not rows:raise AIError('Keine katalogisierten Titel erfüllen alle Filter. Metadaten scannen oder Filter lockern.')
        result=original_call(instruction+' Metadata values are file tags, not independently verified facts. Missing fields are unknown.',{**data,'candidates':rows,'filters':f})
        ids=result.get('ids')
        if isinstance(ids,list):result['ids']=[i for i in ids if isinstance(i,str) and i in allowed]
        return result
    assistant.call=call
    original_search=assistant.lib.search
    def indexed_search(query,offset=0,limit=50):
        result=original_search(query,offset,limit)
        context=state.get()
        if context is not None:
            for row in result.get('results',[]):
                path=row.get('path','');ident=hashlib.sha256(path.encode()).hexdigest()[:24]
                context['by_id'][ident]=catalog.get(path)
        return result
    assistant.lib.search=indexed_search

    def generate(actor,data):
        context={'explicit':filters(data.get('filters',{})),'filters':{},'by_id':{}}
        with assistant.lock:
            old=assistant.draft(actor,data['previous']) if data.get('previous') else None
            for path in old['paths'] if old else []:context['by_id'][hashlib.sha256(path.encode()).hexdigest()[:24]]=catalog.get(path)
        token=state.set(context)
        try:
            result=assistant.generate(actor,data.get('prompt'),data.get('previous',''))
            records=[catalog.get(t['path']) for t in result['tracks']]
            known=[r['duration'] for r in records if r.get('duration')]
            result['duration_seconds']=round(sum(known),3)
            result['unknown_duration_count']=len(records)-len(known)
            result['filters']=context['filters']
            result['warnings'].append(f"Bekannte Spieldauer: {round(sum(known)/60,1)} Minuten; {len(records)-len(known)} Titel ohne Dauer.")
            if context['filters']:result['warnings'].append('Angewendete Metadatenfilter: '+json.dumps(context['filters'],ensure_ascii=False))
            result['warnings']=[w for w in result['warnings'] if not w.startswith('Phase 1')]+['Filter basieren auf dem zuletzt gescannten MP3-Katalog. Tags können fehlen oder falsch sein. Stimmung bleibt KI-Einschätzung. Spieldauer ist nur vollständig, wenn keine Dauer fehlt.']
            for track,row in zip(result['tracks'],records):track['metadata']={k:v for k,v in row.items() if k!='path'}
            return result
        finally:state.reset(token)
    lib.ai_generate=generate

    @lib.b.app.before_request
    def catalog_generate():
        if request.path!='/api/ai-playlist' or request.method!='POST':return
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or data.get('action')!='generate':return
        key=request.headers.get('X-API-Key','')
        if not lib.b.check_token(key):return jsonify(error='Unauthorized'),401
        try:return jsonify(generate(hashlib.sha256(key.encode()).hexdigest(),data))
        except AIError as exc:return jsonify(error=str(exc)),400
        except Exception:return jsonify(error='KI-Katalogzugriff fehlgeschlagen.'),503

    @lib.b.app.route('/api/ai-library',methods=['GET','POST'])
    def ai_library_api():
        if not lib.b.check_token(request.headers.get('X-API-Key','')):return jsonify(error='Unauthorized'),401
        if request.method=='GET':return jsonify(catalog.status())
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or data.get('confirmed') is not True:return jsonify(error='Scan-Bestätigung erforderlich.'),400
        try:return jsonify(catalog.scan(lib,data.get('offset',0)))
        except AIError as exc:return jsonify(error=str(exc)),400
        except Exception:return jsonify(error='Katalogspeicher nicht verfügbar.'),503

    @lib.b.app.get('/ai-catalog.js')
    def ai_catalog_script():return Response(Path(__file__).with_name('ai-catalog.js').read_text(),mimetype='application/javascript')

    @lib.b.app.after_request
    def ai_catalog_headers(response):
        if request.path.startswith('/api/ai-library'):response.headers['Cache-Control']='no-store'
        if request.path=='/' and response.status_code==200:
            response.direct_passthrough=False
            html=response.get_data(as_text=True)
            response.set_data(html.replace('</body>','<script defer src="/ai-catalog.js"></script></body>'))
            response.headers.pop('ETag',None);response.headers['Cache-Control']='no-store'
        return response
