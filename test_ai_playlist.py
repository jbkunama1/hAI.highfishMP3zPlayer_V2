"""Offline service tests. No calls to the configured LLM provider."""
import os
import types
import unittest
from unittest.mock import patch
from ai_playlist import Assistant, AIError


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'AI_PLAYLIST_ENABLED':'true'});self.env.start()
        self.addCleanup(self.env.stop)
        self.saved=[]
        def store(action,**kw):
            self.saved.append(kw);return {'id':'saved'}
        self.lib=types.SimpleNamespace(search=lambda *a:{'results':[{'path':'Rock/song.mp3'}]},
            b=types.SimpleNamespace(STORAGE=types.SimpleNamespace(isfile=lambda p:True)),
            playlists=types.SimpleNamespace(run=store))
        self.calls=[]
        def call(instruction,data):
            self.calls.append(data)
            if 'candidates' not in data:return {'queries':['Rock'],'count':3}
            return {'ids':[data['candidates'][0]['id'],'invented',data['candidates'][0]['id']], 'name':'Rock mix','explanation':'Vorschlag'}
        self.ai=Assistant(self.lib,call)

    def test_known_ids_only_and_no_paths_to_model(self):
        d=self.ai.generate('actor','Rock bitte')
        self.assertEqual([t['path'] for t in d['tracks']],['Rock/song.mp3'])
        self.assertNotIn('path',self.calls[1]['candidates'][0])
        self.assertTrue(any('2 ungültige' in w for w in d['warnings']))
        self.assertEqual(self.saved,[])

    def test_save_confirmation_and_idempotency(self):
        d=self.ai.generate('actor','Rock bitte')
        with self.assertRaises(AIError):self.ai.save('actor',d['draft_id'],'Rock')
        self.ai.save('actor',d['draft_id'],'Rock',True)
        self.ai.save('actor',d['draft_id'],'Rock',True)
        self.assertEqual(len(self.saved),1)

    def test_actor_binding_expiration_and_feedback(self):
        d=self.ai.generate('actor','Rock bitte')
        with self.assertRaises(AIError):self.ai.generate('other','Noch mehr',d['draft_id'])
        self.ai.generate('actor','Etwas ruhiger',d['draft_id'])
        self.assertEqual(self.calls[-1]['wishes'],['Rock bitte','Etwas ruhiger'])
        self.ai.drafts[d['draft_id']]['expires']=0
        with self.assertRaises(AIError):self.ai.save('actor',d['draft_id'],'Rock',True)

    def test_disabled_and_invalid_input(self):
        for prompt in ['',None,'x'*2001]:
            with self.assertRaises(AIError):self.ai.generate('actor',prompt)
        os.environ['AI_PLAYLIST_ENABLED']='false'
        with self.assertRaises(AIError):self.ai.generate('actor','Rock')
        self.assertEqual(self.calls,[])

    def test_bad_plan_and_empty_library(self):
        self.ai.call=lambda *a:{'queries':['rock'],'count':True}
        with self.assertRaises(AIError):self.ai.generate('actor','Rock')
        self.ai.call=lambda *a:{'queries':['rock'],'count':10}
        self.lib.search=lambda *a:{'results':[]}
        with self.assertRaises(AIError):self.ai.generate('actor','Rock')

    def test_overload_releases_slots_on_failure(self):
        self.ai.slots.acquire();self.ai.slots.acquire()
        with self.assertRaises(AIError):self.ai.generate('actor','Rock')
        self.ai.slots.release();self.ai.slots.release()
        self.ai.call=lambda *a: (_ for _ in ()).throw(AIError('failure'))
        with self.assertRaises(AIError):self.ai.generate('actor','Rock')
        self.assertTrue(self.ai.slots.acquire(blocking=False));self.ai.slots.release()


if __name__=='__main__':unittest.main()
