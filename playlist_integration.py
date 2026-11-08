"""REST, MCP and Telegram adapters over one playlist store."""
import json
import os
from pathlib import Path
from urllib.parse import quote
from playlist_service import PlaylistStore, Conflict


def flag(name):
    return os.getenv(name,'false').lower() in ('true','1','yes')


def install_playlists(server, lib):
    from flask import request, jsonify, Response
    from functools import wraps
    folder=Path(os.getenv('MP3Z_DATA_DIR',str(Path.home()/'.local/share/mp3z')))
    folder.mkdir(parents=True,exist_ok=True)
    store=PlaylistStore(folder/'playlists.sqlite3',lib.b.STORAGE.isfile)
    lib.playlists=store

    def export(ident='',fmt='json'):
        if fmt not in ('json','m3u8'): raise ValueError('Unsupported export format')
        if ident:
            p=store.run('get',ident=ident)
            if fmt=='m3u8': return '#EXTM3U\n'+''.join(quote(i['path'],safe='/')+'\n' for i in p['items'])
            data={'schema':'mp3z-playlist-v1','playlist':p}
        else:
            if fmt!='json': raise ValueError('Combined export requires JSON')
            from admin_ui import snapshot
            data={'schema':'mp3z-application-v1','library':snapshot(lib.b),'playlists':store.snapshot(),
                  'excludes':['music files','embedded ID3 backups','credentials','sessions','browser preferences'],
                  'consistency':'Each index/playlist snapshot is consistent independently; not one cross-store transaction.'}
        return json.dumps(data,ensure_ascii=False,indent=2)
    lib.playlist_export=export

    def auth(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            if not lib.b.check_token(request.headers.get('X-API-Key','')): return jsonify(error='Unauthorized'),401
            try: return fn(*args,**kwargs)
            except Conflict as exc: return jsonify(error=str(exc)),409
            except FileNotFoundError: return jsonify(error='Playlist or track not found'),404
            except (ValueError,TypeError): return jsonify(error='Invalid playlist request; check values and revision'),400
            except Exception:
                lib.b.app.logger.warning('Playlist operation failed; no private data logged')
                return jsonify(error='Playlist storage unavailable'),503
        return wrapped

    @lib.b.app.route('/api/playlists',methods=['GET','POST'])
    @auth
    def playlists_api():
        if request.method=='GET': return jsonify(store.run('list'))
        data=request.get_json(silent=True)
        if not isinstance(data,dict): raise ValueError()
        return jsonify(store.run(**data))

    @lib.b.app.get('/api/playlists/export')
    @auth
    def playlists_export_api():
        fmt=request.args.get('format','json')
        text=export(request.args.get('id',''),fmt)
        return Response(text,content_type=('application/json; charset=utf-8' if fmt=='json' else 'audio/x-mpegurl; charset=utf-8'),headers={'Content-Disposition':'attachment; filename="mp3z-export.'+fmt+'"'})

    @lib.b.app.get('/playlist-ui.js')
    def playlist_script():
        return Response(Path(__file__).with_name('playlist-ui.js').read_text(),mimetype='application/javascript',headers={'Cache-Control':'no-store'})

    @lib.b.app.after_request
    def playlist_headers(response):
        if request.path.startswith('/api/playlists'):
            response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
        if request.path=='/' and response.status_code==200:
            response.direct_passthrough=False
            html=response.get_data(as_text=True)
            if 'src="/playlist-ui.js"' not in html: html=html.replace('</body>','<script src="/playlist-ui.js"></script></body>')
            response.set_data(html);response.headers.pop('ETag',None);response.headers.pop('Last-Modified',None)
            response.headers['Cache-Control']='no-store'
        return response

    @server.tool()
    def list_playlists() -> dict:
        """List up to 1000 shared persisted playlists."""
        return store.run('list')

    @server.tool()
    def get_playlist(ident: str) -> dict:
        """Read ordered items, revision and current track availability."""
        return store.run('get',ident=ident)

    @server.tool()
    def change_playlist(action: str, ident: str = '', revision: int = 0, name: str = '', paths: list[str] | None = None, order: list[str] | None = None, item_id: str = '', confirmed: bool = False) -> dict:
        """After explicit approval: create/rename/add/remove/reorder/duplicate/delete. Reload revision before mutations. Duplicate paths have distinct item IDs."""
        if not flag('MCP_PLAYLIST_WRITE_ENABLED') or not confirmed: raise PermissionError('Playlist write flag and explicit approval required')
        if action not in {'create','rename','add','remove','reorder','duplicate','delete'}: raise ValueError('Mutation required')
        return store.run(action,ident,revision,name,paths,order,item_id)

    @server.tool()
    def export_music_data(ident: str = '', format: str = 'json') -> dict:
        """Export a playlist or combined index/playlists, excluding secrets and music. Inline content is limited to 1 MiB; use authenticated web download for larger exports."""
        text=export(ident,format)
        if len(text.encode())>1048576: raise ValueError('Export exceeds MCP limit; use authenticated web download')
        return {'filename':'mp3z-export.'+format,'content':text,'encoding':'utf-8'}
    return store


def enable_telegram_playlists():
    from telegram_runtime import RuntimeBot
    import telegram_runtime
    import time
    class PlaylistBot(RuntimeBot):
        def menu(self,uid,chat):
            super().menu(uid,chat)
            return self.show(uid,chat,'Playlists: /playlists\n/playlist {JSON} bereitet eine Änderung vor.\n/musicexport [Playlist-ID] [json|m3u8] exportiert Daten.\nBeispiel: /playlist {"action":"create","name":"Rock","paths":[]}')

        def document(self,chat,text,fmt):
            import secrets
            from urllib.request import Request,urlopen
            from telegram_bot import BotError
            raw=text.encode()
            if len(raw)>8*1024*1024: return self.show('',chat,'Export größer als 8 MiB. Bitte Webexport verwenden.')
            boundary='mp3z'+secrets.token_hex(16)
            body=(f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{chat}\r\n--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="mp3z-export.{fmt}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()+raw+f'\r\n--{boundary}--\r\n'.encode()
            try:
                req=Request(f'https://api.telegram.org/bot{self.token}/sendDocument',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary})
                with urlopen(req,timeout=40) as response:
                    if not json.load(response).get('ok'): raise BotError()
            except Exception: raise BotError() from None

        def handle(self,update):
            cb=update.get('callback_query');msg=(cb or {}).get('message') or update.get('message',{})
            uid=str((cb or msg).get('from',{}).get('id',''));chat=msg.get('chat',{})
            if uid not in self.allowed or chat.get('type')!='private': return
            cid=chat['id'];text=msg.get('text','').strip();command=text.split(maxsplit=1)[0].split('@')[0] if text else ''
            entry=self.callbacks.get(cb.get('data','')) if cb else None
            own=bool(entry and entry[2][0] in ('playlist:confirm','playlist:cancel'))
            if not own and (cb or command not in ('/playlists','/playlist','/musicexport')): return super().handle(update)
            now=time.time()
            if cb:
                self.call('answerCallbackQuery',{'callback_query_id':cb['id']})
                if not entry or entry[0]!=uid or entry[1]!=cid or entry[3]<=now: return self.show(uid,cid,'Bestätigung abgelaufen oder fremder Chat.')
                self.callbacks.pop(cb['data'],None)
            if now-self.last.get(uid,0)<0.5:return
            self.last[uid]=now
            try:
                if own:
                    if entry[2][0]=='playlist:cancel':
                        for key,value in list(self.callbacks.items()):
                            if value[0]==uid and value[1]==cid and value[2][0]=='playlist:confirm': self.callbacks.pop(key,None)
                        return self.show(uid,cid,'Abgebrochen; nichts geändert.')
                    if not flag('TELEGRAM_PLAYLIST_WRITE_ENABLED'): raise PermissionError()
                    result=self.lib.playlists.run(**entry[2][1])
                    return self.show(uid,cid,json.dumps(result,ensure_ascii=False))
                if command=='/playlists':
                    parts=text.split();offset=int(parts[1]) if len(parts)>1 else 0
                    if offset<0: raise ValueError()
                    rows=self.lib.playlists.run('list')['playlists'];page=rows[offset:offset+10]
                    return self.show(uid,cid,'Playlists (weitere: /playlists OFFSET)\n'+'\n'.join(p['name']+' | '+p['id']+' | Revision '+str(p['revision'])+' | '+str(p['count'])+' Titel' for p in page))
                if command=='/musicexport':
                    parts=text.split();ident=parts[1] if len(parts)>1 else '';fmt=parts[2] if len(parts)>2 else 'json'
                    return self.document(cid,self.lib.playlist_export(ident,fmt),fmt)
                data=json.loads(text.split(maxsplit=1)[1])
                if not isinstance(data,dict) or data.get('action') not in {'list','get','create','rename','add','remove','reorder','duplicate','delete'}: raise ValueError()
                if data['action'] in {'list','get'}: return self.show(uid,cid,json.dumps(self.lib.playlists.run(**data),ensure_ascii=False))
                if not flag('TELEGRAM_PLAYLIST_WRITE_ENABLED'): raise PermissionError()
                preview=json.dumps(data,ensure_ascii=False)
                if len(preview)>3000: raise ValueError()
                button=self.button('Bestätigen',uid,cid,('playlist:confirm',data,0));key=button['callback_data']
                actor,target,payload,_=self.callbacks[key];self.callbacks[key]=(actor,target,payload,now+60)
                return self.show(uid,cid,'Änderung bestätigen (60 Sekunden, einmalig):\n'+preview,[[button,self.button('Abbrechen',uid,cid,('playlist:cancel','',0))]])
            except Conflict: return self.show(uid,cid,'Playlist wurde geändert. Erst neu laden und aktuelle Revision verwenden.')
            except Exception: return self.show(uid,cid,'Aktion fehlgeschlagen. Syntax, Revision, Dateipfade und Schreibfreigabe prüfen. Kein Erfolg bestätigt.')
    telegram_runtime.RuntimeBot=PlaylistBot
