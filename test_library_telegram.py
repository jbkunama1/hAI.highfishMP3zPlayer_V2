import io
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from library_tools import Library, public_url
from telegram_bot import Bot

class FakeLibrary:
    b=SimpleNamespace(AUDIO_EXTS={'.mp3'})
    def browse(self,path='',offset=0,limit=8):
        return {'entries':[{'type':'file','name':'Song.mp3','path':'Song.mp3'}], 'total':20,'has_more':offset<16}
    def search(self,q,offset=0,limit=8):return self.browse('',offset,limit)
    def status(self):return {'total_files':20,'building':False}
    def cover(self,path):raise ValueError('missing')

class BotTests(unittest.TestCase):
    def setUp(self):
        self.bot=Bot(FakeLibrary(),'FAKE_TOKEN',['1'],'https://music.example')
        self.calls=[]
        self.bot.call=lambda method,data,image=None:self.calls.append((method,data,image))
    def message(self,uid=1,kind='private',text='/start'):
        return {'message':{'from':{'id':uid},'chat':{'id':uid,'type':kind},'text':text}}
    def test_deny_unknown_or_group(self):
        self.bot.handle(self.message(2));self.bot.handle(self.message(kind='group'))
        self.assertEqual(self.calls,[])
    def test_menu(self):
        self.bot.handle(self.message())
        self.assertEqual(self.calls[0][0],'sendMessage')
        self.assertNotIn('FAKE_TOKEN',json.dumps(self.calls))
    def test_pagination(self):
        self.bot.page('1',1,'search','Song',0)
        self.assertTrue(any(v[2]==('search','Song',8) for v in self.bot.callbacks.values()))
    def test_callback_binding(self):
        button=self.bot.button('x','2',1,('status','',0))
        self.bot.handle({'callback_query':{'id':'cb','from':{'id':1},'message':{'chat':{'id':1,'type':'private'}},'data':button['callback_data']}})
        self.assertIn('abgelaufen',self.calls[-1][1]['text'])
    def test_expiry(self):
        with patch('telegram_bot.time.time',return_value=100):button=self.bot.button('x','1',1,('status','',0))
        with patch('telegram_bot.time.time',return_value=1000):
            self.bot.handle({'callback_query':{'id':'cb','from':{'id':1},'message':{'chat':{'id':1,'type':'private'}},'data':button['callback_data']}})
        self.assertIn('abgelaufen',self.calls[-1][1]['text'])
    def test_card_fallback(self):
        self.bot.card(1,'Song.mp3')
        self.assertEqual(self.calls[0][0],'sendPhoto')
        self.assertTrue(self.calls[0][2].startswith(bytes.fromhex('ffd8')))
    def test_required(self):
        with self.assertRaises(ValueError):Bot(FakeLibrary(),'token',[],'https://music.example')
        with self.assertRaises(ValueError):public_url('https://user:pass@music.example')
    def test_links_scoped_expiring_no_master_key(self):
        backend=SimpleNamespace(AUDIO_EXTS={'.mp3'},STORAGE=SimpleNamespace(isfile=lambda p:True))
        lib=Library(backend)
        from urllib.parse import urlsplit,parse_qs
        with patch.dict(os.environ,{'PUBLIC_URL':'https://music.example','API_KEY_OVERRIDE':'MASTER_SECRET'}):
            with patch('library_tools.time.time',return_value=100):result=lib.stream_link('Song.mp3')
        self.assertNotIn('MASTER_SECRET',result['url'])
        token=parse_qs(urlsplit(result['url']).query)['media_token'][0]
        with patch('library_tools.time.time',return_value=101):
            self.assertTrue(lib.valid_link('Song.mp3',token));self.assertFalse(lib.valid_link('Other.mp3',token))
        with patch('library_tools.time.time',return_value=701):self.assertFalse(lib.valid_link('Song.mp3',token))
    def test_reject_traversal(self):
        lib=Library(None)
        for value in ('../secret','/etc/passwd','a/../x','file:ads'):
            with self.assertRaises(ValueError):lib.path(value)

if __name__=='__main__':unittest.main()
