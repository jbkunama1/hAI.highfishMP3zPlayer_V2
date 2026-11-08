"""Phase 2b offline tests: real SQLite, mocked LLM and transports."""
import os
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from ai_studio import Wishes, Mixer, MixError, options, install_studio, enable_telegram_studio


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'w.db';self.w=Wishes(self.db)
        self.value={'name':'Rock','prompt':'Rock bitte','filters':{'genre':'rock','year_from':2000}}

    def test_confirm_persistence_and_actor_isolation(self):
        with self.assertRaises(MixError):self.w.run('alice','create',self.value)
        row=self.w.run('alice','create',self.value,True)
        self.assertEqual(Wishes(self.db).run('alice','get',row)['prompt'],'Rock bitte')
        self.assertEqual(self.w.run('bob','list',{})['wishes'],[])
        with self.assertRaises(MixError):self.w.run('bob','delete',row,True)
        self.w.run('alice','delete',row,True)
        self.assertEqual(self.w.run('alice','list',{})['wishes'],[])

    def test_invalid_options_and_limit(self):
        for value in [{},{'prompt':'x','filters':{'year_from':True}},{'prompt':'x','filters':{'year_from':2010,'year_to':2000}},{'prompt':'x','filters':{'language':None}},{'prompt':'x'*2001}]:
            with self.subTest(value=value),self.assertRaises(MixError):options(value)
        for _ in range(100):self.w.run('alice','create',self.value,True)
        with self.assertRaises(MixError):self.w.run('alice','create',self.value,True)

    def test_mixer_dispatch(self):
        calls=[]
        lib=types.SimpleNamespace(playlists=types.SimpleNamespace(filename=self.db),ai_generate=lambda actor,data:calls.append((actor,data)) or {'draft_id':'d'},ai_playlists=types.SimpleNamespace(save=lambda *args:calls.append(args) or {'id':'saved'}))
        mixer=Mixer(lib)
        mixer.request('actor','generate',{'prompt':'Rock','filters':{'language':'deu'}})
        self.assertEqual(calls[0][1]['filters'],{'language':'deu'})
        mixer.request('actor','save',{'draft_id':'d','name':'Rock'},True)
        self.assertTrue(calls[-1][-1])
        with self.assertRaises(MixError):mixer.request('actor','unknown',{})

    def test_mcp_permissions(self):
        flask=types.ModuleType('flask');flask.request=object();flask.jsonify=lambda **x:x
        class App:
            def route(self,*a,**kw):return lambda f:f
            def after_request(self,f):return f
        tools={};calls=[]
        lib=types.SimpleNamespace(b=types.SimpleNamespace(app=App()),playlists=types.SimpleNamespace(filename=self.db),ai_generate=lambda actor,data:calls.append(actor) or {'draft_id':'d'})
        server=types.SimpleNamespace(tool=lambda:lambda f:tools.setdefault(f.__name__,f))
        with patch.dict('sys.modules',{'flask':flask}),patch.dict(os.environ,{'MCP_AI_ENABLED':'false','MCP_PLAYLIST_WRITE_ENABLED':'false'}):
            install_studio(server,lib);tool=tools['ai_playlist_assistant']
            with self.assertRaises(PermissionError):tool('wish_list')
            os.environ['MCP_AI_ENABLED']='true'
            with self.assertRaises(MixError):tool('generate','{"prompt":"Rock"}')
            self.assertEqual(calls,[])
            tool('generate','{"prompt":"Rock"}',approved=True)
            self.assertEqual(calls,['mcp'])
            with self.assertRaises(PermissionError):tool('wish_create','{"prompt":"Rock","name":"R"}',confirmed=True)
            os.environ['MCP_PLAYLIST_WRITE_ENABLED']='true'
            self.assertIn('id',tool('wish_create','{"prompt":"Rock","name":"R"}',confirmed=True))

    def test_telegram_allowlist_group_and_disabled(self):
        class Base:
            def handle(self,u):self.forwarded=True
            def show(self,*args):self.shown=args
        runtime=types.ModuleType('telegram_runtime');runtime.RuntimeBot=Base
        with patch.dict('sys.modules',{'telegram_runtime':runtime}),patch.dict(os.environ,{'TELEGRAM_AI_ENABLED':'false'}):
            enable_telegram_studio();bot=runtime.RuntimeBot();bot.allowed={'1'};bot.callbacks={};bot.last={}
            def message(uid,kind,text):return {'message':{'from':{'id':uid},'chat':{'id':uid,'type':kind},'text':text}}
            bot.handle(message(2,'private','/mix Rock'));self.assertFalse(hasattr(bot,'shown'))
            bot.handle(message(1,'group','/mix Rock'));self.assertFalse(hasattr(bot,'shown'))
            bot.handle(message(1,'private','/mix Rock'));self.assertIn('deaktiviert',bot.shown[2])
            bot.handle(message(1,'private','/browse'));self.assertTrue(bot.forwarded)


if __name__=='__main__':unittest.main()
