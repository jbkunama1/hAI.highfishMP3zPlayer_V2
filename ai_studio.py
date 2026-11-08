"""Phase 2b: actor-scoped saved wishes, web studio, MCP and private Telegram."""
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path


class MixError(ValueError):
    pass


def flag(name):
    return os.getenv(name,'false').lower() in ('true','1','yes')


def options(data):
    if not isinstance(data,dict):raise MixError('JSON-Objekt erforderlich.')
    prompt=data.get('prompt','')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>2000:raise MixError('Wunsch: 1–2000 Zeichen.')
    f=data.get('filters',{})
    if not isinstance(f,dict) or set(f)-{'genre','language','year_from','year_to'}:raise MixError('Ungültige Filter.')
    f=dict(f)
    for k in ('genre','language'):
        if k in f and (not isinstance(f[k],str) or len(f[k])>80):raise MixError('Ungültiger Textfilter.')
    for k in ('year_from','year_to'):
        if k in f and (type(f[k]) is not int or not 1000<=f[k]<=2999):raise MixError('Ungültiges Jahr.')
    if f.get('year_from',1000)>f.get('year_to',2999):raise MixError('Jahresbereich vertauscht.')
    return {'prompt':prompt.strip(),'filters':f}


class Wishes:
    def __init__(self,filename):
        self.filename=str(filename)
        with closing(self.connect()) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS wishes (id TEXT PRIMARY KEY, actor TEXT NOT NULL, payload TEXT NOT NULL)')

    def connect(self):return sqlite3.connect(self.filename,timeout=10)

    def run(self,actor,action,data,confirmed=False):
        if action not in ('list','get','create','delete'):raise MixError('Unbekannte Wunschaktion.')
        if action in ('create','delete') and confirmed is not True:raise MixError('Bestätigung erforderlich.')
        with closing(self.connect()) as db,db:
            db.execute('BEGIN IMMEDIATE' if action in ('create','delete') else 'BEGIN')
            if action=='list':
                return {'wishes':[{'id':r[0],**json.loads(r[1])} for r in db.execute('SELECT id,payload FROM wishes WHERE actor=? ORDER BY id',(actor,))]}
            ident=data.get('id','')
            if not isinstance(ident,str):raise MixError('Ungültige Wunsch-ID.')
            if action=='create':
                name=data.get('name','')
                if not isinstance(name,str) or not name.strip() or len(name)>120 or any(ord(c)<32 for c in name):raise MixError('Name: 1–120 druckbare Zeichen.')
                value={'name':name.strip(),**options(data)}
                if db.execute('SELECT COUNT(*) FROM wishes WHERE actor=?',(actor,)).fetchone()[0]>=100 or db.execute('SELECT COUNT(*) FROM wishes').fetchone()[0]>=1000:raise MixError('Wunschlimit erreicht.')
                ident=secrets.token_hex(16)
                db.execute('INSERT INTO wishes VALUES (?,?,?)',(ident,actor,json.dumps(value,ensure_ascii=False)))
                return {'id':ident,**value}
            row=db.execute('SELECT payload FROM wishes WHERE id=? AND actor=?',(ident,actor)).fetchone()
            if not row:raise MixError('Wunsch nicht gefunden.')
            if action=='delete':
                db.execute('DELETE FROM wishes WHERE id=? AND actor=?',(ident,actor));return {'deleted':ident}
            return {'id':ident,**json.loads(row[0])}


class Mixer:
    def __init__(self,lib):
        self.lib=lib
        self.wishes=Wishes(Path(lib.playlists.filename).with_name('ai-wishes.sqlite3'))

    def request(self,actor,action,data,confirmed=False):
        if not isinstance(data,dict):raise MixError('JSON-Objekt erforderlich.')
        if action=='generate':
            value=options(data);previous=data.get('previous','')
            if not isinstance(previous,str) or len(previous)>128:raise MixError('Ungültige Vorschau-ID.')
            return self.lib.ai_generate(actor,{**value,'previous':previous})
        if action in ('get','save'):
            token=data.get('draft_id','')
            if not isinstance(token,str) or len(token)>128:raise MixError('Ungültige Vorschau-ID.')
            if action=='save':
                name=data.get('name','')
                if not isinstance(name,str):raise MixError('Ungültiger Name.')
                return self.lib.ai_playlists.save(actor,token,name,confirmed)
            with self.lib.ai_playlists.lock:
                return self.lib.ai_playlists.public(token,self.lib.ai_playlists.draft(actor,token))
        if action.startswith('wish_'):return self.wishes.run(actor,action[5:],data,confirmed)
        raise MixError('Unbekannte Aktion.')


def install_studio(server,lib):
    from flask import request,jsonify
    mixer=Mixer(lib);lib.ai_studio=mixer

    @lib.b.app.route('/api/ai-studio',methods=['GET','POST'])
    def ai_studio_api():
        key=request.headers.get('X-API-Key','')
        if not lib.b.check_token(key):return jsonify(error='Unauthorized'),401
        actor=hashlib.sha256(key.encode()).hexdigest()
        if request.method=='GET':return jsonify(enabled=flag('AI_PLAYLIST_ENABLED'),configured=bool(os.getenv('LLM_API_KEY')))
        data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='JSON-Objekt erforderlich.'),400
        try:return jsonify(mixer.request(actor,data.get('action',''),data,data.get('confirmed',False)))
        except ValueError as exc:return jsonify(error=str(exc)),400
        except Exception:return jsonify(error='Assistenten-Anfrage fehlgeschlagen.'),503

    @lib.b.app.after_request
    def studio_cache(response):
        if request.path=='/api/ai-studio':response.headers['Cache-Control']='no-store'
        return response

    @server.tool()
    def ai_playlist_assistant(action: str, options_json: str = '{}', approved: bool = False, confirmed: bool = False) -> dict:
        """AI mix generate/get/save and wish_list/wish_get/wish_create/wish_delete. options_json holds prompt, filters, previous, draft_id, name or id. Generate sends wishes and music metadata to the configured LLM and needs approved=true. Writes need confirmed=true and MCP_PLAYLIST_WRITE_ENABLED. No browser playback control. MCP clients share one trusted account scope."""
        if not flag('MCP_AI_ENABLED'):raise PermissionError('MCP_AI_ENABLED ist deaktiviert.')
        if not isinstance(options_json,str) or len(options_json)>10000:raise MixError('Optionen zu groß.')
        if action=='generate' and approved is not True:raise MixError('LLM-Datenübertragung und Anfrage müssen freigegeben sein.')
        if action in ('save','wish_create','wish_delete') and (not flag('MCP_PLAYLIST_WRITE_ENABLED') or confirmed is not True):raise PermissionError('Schreibfreigabe und Bestätigung erforderlich.')
        return mixer.request('mcp',action,json.loads(options_json),confirmed)


def enable_telegram_studio():
    import telegram_runtime
    Base=telegram_runtime.RuntimeBot
    class StudioBot(Base):
        def menu(self,uid,chat):
            super().menu(uid,chat)
            return self.show(uid,chat,'KI-Mix: /mix Wunsch\nNachbessern: /mixmore Wunsch\nNeue Unterhaltung: /mixnew\nVorlagen: /mixwishes · /mixuse ID\nAktuellen Wunsch merken: /mixwish Name\nKI-Anfragen senden Wünsche und Musikmetadaten an den konfigurierten LLM-Dienst.')

        def mix_preview(self,uid,chat,draft,offset=0):
            tracks=draft['tracks'];lines=[draft['name'],f"{len(tracks)} Titel · ab {offset+1}"]
            lines += [f"{i+1}. {t['name'][:100]}" for i,t in enumerate(tracks[offset:offset+10],offset)]
            lines += [str(w)[:350] for w in draft.get('warnings',[])][:5]
            rows=[[self.button('Playlist speichern',uid,chat,('mix:save',(draft['draft_id'],draft['name']),0))]]
            if offset+10<len(tracks):rows.append([self.button('Weitere Titel',uid,chat,('mix:page',draft['draft_id'],offset+10))])
            return self.show(uid,chat,'\n'.join(lines),rows)

        def handle(self,update):
            cb=update.get('callback_query');msg=(cb or {}).get('message') or update.get('message',{})
            uid=str((cb or msg).get('from',{}).get('id',''));chat=msg.get('chat',{})
            if uid not in self.allowed or chat.get('type')!='private':return
            cid=chat['id'];actor=f'telegram:{uid}:{cid}'
            text=msg.get('text','').strip();parts=text.split(maxsplit=1);command=parts[0].split('@')[0] if parts else ''
            entry=self.callbacks.get(cb.get('data','')) if cb else None
            own=bool(entry and entry[2][0].startswith('mix:'))
            commands={'/mix','/mixmore','/mixnew','/mixwishes','/mixuse','/mixwish'}
            if not own and (cb or command not in commands):return super().handle(update)
            if not flag('TELEGRAM_AI_ENABLED'):return self.show(uid,cid,'KI für Telegram ist deaktiviert: TELEGRAM_AI_ENABLED=true erforderlich.')
            now=time.time()
            if cb:
                self.call('answerCallbackQuery',{'callback_query_id':cb['id']})
                if entry[0]!=uid or entry[1]!=cid or entry[3]<=now:return self.show(uid,cid,'Button abgelaufen oder fremder Chat.')
            if now-self.last.get(uid,0)<0.5:return
            self.last[uid]=now
            if not hasattr(self,'mix_sessions'):self.mix_sessions={}
            session=self.mix_sessions.get(actor,{})
            mixer=self.lib.ai_studio
            try:
                if own:
                    mode,value,offset=entry[2]
                    if mode=='mix:page':return self.mix_preview(uid,cid,mixer.request(actor,'get',{'draft_id':value}),offset)
                    self.callbacks.pop(cb['data'],None)
                    if mode=='mix:save':
                        token,name=value
                        with self.lib.ai_playlists.lock:d=self.lib.ai_playlists.draft(actor,token)
                        button=self.button('Ja, diese Playlist speichern',uid,cid,('mix:commit',(token,name),0))
                        k=button['callback_data'];a,b,p,_=self.callbacks[k];self.callbacks[k]=(a,b,p,now+60)
                        return self.show(uid,cid,f"Playlist {name[:200]} mit {len(d['paths'])} Titeln speichern? Bestätigung gilt 60 Sekunden.",[[button]])
                    if mode in ('mix:commit','mix:wish'):
                        if not flag('TELEGRAM_PLAYLIST_WRITE_ENABLED'):raise MixError('Telegram-Schreibfreigabe fehlt.')
                        if mode=='mix:commit':result=mixer.request(actor,'save',{'draft_id':value[0],'name':value[1]},True)
                        else:result=mixer.request(actor,'wish_create',value,True)
                        return self.show(uid,cid,'Gespeichert: '+result['id'])
                argument=parts[1] if len(parts)>1 else ''
                if command=='/mixnew':self.mix_sessions.pop(actor,None);return self.show(uid,cid,'Unterhaltung zurückgesetzt. /mix Wunsch startet neu.')
                if command=='/mixwishes':
                    rows=mixer.request(actor,'wish_list',{})['wishes']
                    return self.show(uid,cid,'Gespeicherte Wünsche (nur dieser Telegram-Akteur):\n'+'\n'.join(r['name'][:80]+' | '+r['id'] for r in rows[:25])+'\nZum Verwenden: /mixuse ID. Angezeigt: erste 25.')
                if command=='/mixwish':
                    value={**session.get('options',{}),'name':argument};options(value)
                    if not argument:raise MixError('/mixwish Name erforderlich.')
                    button=self.button('Wunsch speichern',uid,cid,('mix:wish',value,0))
                    k=button['callback_data'];a,b,p,_=self.callbacks[k];self.callbacks[k]=(a,b,p,now+60)
                    return self.show(uid,cid,'Diesen Wunsch speichern?\n'+json.dumps(value,ensure_ascii=False)[:2800],[[button]])
                if command=='/mixuse':
                    value=mixer.request(actor,'wish_get',{'id':argument})
                    data=options(value)
                else:data={'prompt':argument,'filters':session.get('options',{}).get('filters',{}) if command=='/mixmore' else {}}
                if command=='/mixmore':
                    if not session.get('draft_id'):raise MixError('Zuerst /mix Wunsch verwenden.')
                    data['previous']=session['draft_id']
                draft=mixer.request(actor,'generate',data)
                combined=options(data)
                if command=='/mixmore':combined['prompt']=session.get('options',{}).get('prompt','')+'\n'+combined['prompt']
                self.mix_sessions[actor]={'draft_id':draft['draft_id'],'options':combined}
                return self.mix_preview(uid,cid,draft)
            except ValueError as exc:return self.show(uid,cid,str(exc)[:1000])
            except Exception:return self.show(uid,cid,'KI-Anfrage fehlgeschlagen. Kein erfolgreicher Abschluss bestätigt.')
    telegram_runtime.RuntimeBot=StudioBot
