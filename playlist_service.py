"""Shared durable playlists. No music, credentials or sessions are stored here."""
import json
import sqlite3
import uuid
from pathlib import PurePosixPath


class Conflict(ValueError):
    pass


class PlaylistStore:
    def __init__(self, filename, exists):
        self.filename, self.exists = str(filename), exists
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS playlists (id TEXT PRIMARY KEY, data TEXT NOT NULL)')

    def connect(self):
        # Callers explicitly close connections; the SQLite context commits/rolls back.
        return sqlite3.connect(self.filename, timeout=10)

    @staticmethod
    def name(value):
        if not isinstance(value,str) or not value.strip() or len(value)>200 or any(ord(c)<32 for c in value):
            raise ValueError('Name: 1-200 printable characters required')
        return value.strip()

    @staticmethod
    def path(value):
        if not isinstance(value,str) or not value or len(value)>4096 or value.startswith('/') or ':' in value or chr(92) in value or any(ord(c)<32 for c in value):
            raise ValueError('Visible relative audio path required')
        if any(not p or p.startswith('.') for p in value.split('/')) or PurePosixPath(value).suffix.lower() not in {'.mp3','.flac','.m4a','.ogg','.aac','.wav','.opus','.wma'}:
            raise ValueError('Invalid audio path')
        return value

    def items(self, paths):
        if not isinstance(paths,list) or len(paths)>1000:
            raise ValueError('At most 1000 tracks per playlist')
        result=[]
        for path in paths:
            path=self.path(path)
            if not self.exists(path):
                raise FileNotFoundError('Track not found')
            result.append({'id':uuid.uuid4().hex,'path':path})
        return result

    @staticmethod
    def read(db, ident):
        row=db.execute('SELECT data FROM playlists WHERE id=?',(ident,)).fetchone()
        if not row: raise FileNotFoundError('Playlist not found')
        return json.loads(row[0])

    def run(self, action, ident='', revision=None, name='', paths=None, order=None, item_id=''):
        if action not in {'list','get','create','rename','add','remove','reorder','duplicate','delete'}:
            raise ValueError('Unknown playlist action')
        db=self.connect()
        try:
            with db:
                db.execute('BEGIN IMMEDIATE' if action not in {'list','get'} else 'BEGIN')
                if action=='list':
                    return {'playlists':[{'id':p['id'],'name':p['name'],'revision':p['revision'],'count':len(p['items'])} for p in (json.loads(r[0]) for r in db.execute('SELECT data FROM playlists ORDER BY id'))]}
                if action=='create':
                    if db.execute('SELECT COUNT(*) FROM playlists').fetchone()[0]>=1000: raise ValueError('Playlist limit reached')
                    p={'id':uuid.uuid4().hex,'name':self.name(name),'revision':1,'items':self.items([] if paths is None else paths)}
                else:
                    p=self.read(db,ident)
                    if action=='get':
                        for item in p['items']: item['available']=bool(self.exists(item['path']))
                        return p
                    if type(revision) is not int or revision!=p['revision']: raise Conflict('Playlist changed: reload first')
                    if action=='delete':
                        db.execute('DELETE FROM playlists WHERE id=?',(ident,));return {'deleted':ident}
                    if action=='rename': p['name']=self.name(name)
                    if action=='add':
                        p['items']+=self.items(paths)
                        if len(p['items'])>1000: raise ValueError('Track limit reached')
                    if action=='remove':
                        if item_id not in [i['id'] for i in p['items']]: raise FileNotFoundError('Item not found')
                        p['items']=[i for i in p['items'] if i['id']!=item_id]
                    if action=='reorder':
                        items={i['id']:i for i in p['items']}
                        if not isinstance(order,list) or not all(isinstance(v,str) for v in order) or len(order)!=len(items) or set(order)!=set(items): raise ValueError('Supply each item ID exactly once')
                        p['items']=[items[k] for k in order]
                    if action=='duplicate':
                        if db.execute('SELECT COUNT(*) FROM playlists').fetchone()[0]>=1000: raise ValueError('Playlist limit reached')
                        p['id']=uuid.uuid4().hex;p['name']=self.name(name);p['revision']=0
                        for item in p['items']: item['id']=uuid.uuid4().hex
                    p['revision']+=1
                db.execute('INSERT OR REPLACE INTO playlists VALUES (?,?)',(p['id'],json.dumps(p,ensure_ascii=False)))
                return p
        finally:
            db.close()

    def snapshot(self):
        db=self.connect()
        try:
            with db:
                db.execute('BEGIN')
                return [json.loads(r[0]) for r in db.execute('SELECT data FROM playlists ORDER BY id')]
        finally: db.close()
