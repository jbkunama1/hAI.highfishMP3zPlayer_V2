"""Account-scoped appearance settings and player-only design controls."""
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

CHOICES={
 'theme':set('original neon80 tape90 rewind offair audio soundcheck goodmusic musicblocks'.split()),
 'design':set('Ocean Synthwave Forest Sunset Graphite Aurora Ember Midnight Lagoon Plum Copper Ice Crimson'.split()),
 'view':set('list compact cards row dropdown'.split())}
DEFAULTS={'theme':'original','design':'Ocean','view':'list'}


class Preferences:
    def __init__(self,filename):
        self.filename=str(filename)
        with closing(self.connect()) as db,db:db.execute('CREATE TABLE IF NOT EXISTS appearance (account TEXT PRIMARY KEY, revision INTEGER NOT NULL, data TEXT NOT NULL)')

    def connect(self):return sqlite3.connect(self.filename,timeout=10)

    def run(self,account,changes=None,revision=None):
        if changes is not None:
            if not isinstance(changes,dict) or not changes or set(changes)-set(CHOICES):raise ValueError('Invalid preference keys')
            if any(not isinstance(v,str) or v not in CHOICES[k] for k,v in changes.items()):raise ValueError('Invalid preference value')
            if type(revision) is not int or revision<0:raise ValueError('Revision required')
        with closing(self.connect()) as db,db:
            db.execute('BEGIN IMMEDIATE' if changes is not None else 'BEGIN')
            row=db.execute('SELECT revision,data FROM appearance WHERE account=?',(account,)).fetchone()
            rev,data=(row[0],json.loads(row[1])) if row else (0,dict(DEFAULTS))
            if changes is not None:
                if revision!=rev:return {'revision':rev,'preferences':data},409
                data.update(changes);rev+=1
                db.execute('INSERT OR REPLACE INTO appearance VALUES (?,?,?)',(account,rev,json.dumps(data)))
            return {'revision':rev,'preferences':data},200


def patch_script(path,text):
    if path=='/mobile-view.js':
        old='<label>Farben <select aria-label="Farbverlauf"></select></label>'
        if text.count(old)!=1:raise ValueError('Mobile markup changed')
        text=text.replace(old,'<select aria-label="Farbverlauf" hidden></select>').replace('>Design</button>','>Designs</button>')
    if path=='/music-themes.js':
        start=text.index("const mobile=document.getElementById('mobile-now-playing');if(mobile){")
        end=text.index("\ntry{localStorage.setItem('mp3z_music_theme'",start)
        text=text[:start]+"document.dispatchEvent(new Event('mp3z-theme-applied'));"+text[end:]
        old="[['settings-modal','.s-sheet'],['mobile-now-playing','.mobile-bottom']]"
        if text.count(old)!=1:raise ValueError('Theme targets changed')
        text=text.replace(old,"[['settings-modal','.s-sheet']]")
        old="if(mobile&&!mobile.querySelector('.music-theme-picker'))attach();"
        if text.count(old)!=1:raise ValueError('Theme observer changed')
        text=text.replace(old,'if(false)attach();')
        text += "\ndocument.addEventListener('mp3z-preferences-theme',e=>{const s=document.querySelector('#settings-modal .music-theme-picker select');if(s){s.value=e.detail;s.dispatchEvent(new Event('change',{bubbles:true}));}});\n"
    return text


def install_preferences(backend,playlist_filename):
    from flask import request,jsonify,Response
    store=Preferences(Path(playlist_filename).with_name('appearance.sqlite3'))
    # The existing login has one configured account. Never accept identity from the browser.
    account=hashlib.sha256(('app:'+os.environ['APP_USERNAME']).encode()).hexdigest()

    @backend.app.route('/api/appearance',methods=['GET','POST'])
    def appearance_api():
        if not backend.check_token(request.headers.get('X-API-Key','')):return jsonify(error='Unauthorized'),401
        try:
            if request.method=='GET':result,status=store.run(account)
            else:
                body=request.get_json(silent=True)
                if not isinstance(body,dict) or set(body)-{'changes','revision'} or not isinstance(body.get('changes'),dict):raise ValueError()
                result,status=store.run(account,body['changes'],body.get('revision'))
            return jsonify(result),status
        except ValueError:return jsonify(error='Invalid appearance request'),400
        except Exception:return jsonify(error='Appearance storage unavailable'),503

    @backend.app.get('/appearance.js')
    def appearance_script():return Response(Path(__file__).with_name('appearance.js').read_text(),mimetype='application/javascript',headers={'Cache-Control':'no-store'})

    @backend.app.after_request
    def appearance_response(response):
        if request.path in ('/mobile-view.js','/music-themes.js') and response.status_code==200:
            try:response.set_data(patch_script(request.path,response.get_data(as_text=True)))
            except ValueError:return Response('/* Appearance integration needs review. */',status=503,mimetype='application/javascript')
            response.headers.pop('ETag',None);response.headers['Cache-Control']='no-store'
        if request.path=='/' and response.status_code==200:
            response.direct_passthrough=False
            html=response.get_data(as_text=True)
            if 'src="/appearance.js"' not in html:response.set_data(html.replace('</body>','<script defer src="/appearance.js"></script></body>'))
            response.headers.pop('ETag',None);response.headers['Cache-Control']='no-store'
        if request.path=='/api/appearance':response.headers['Cache-Control']='no-store'
        return response
