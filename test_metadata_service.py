import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from mutagen.id3 import ID3, TIT2, APIC
from metadata_service import MetadataService, BearerAuth

class Storage:
    mode = 'local'
    def __init__(self, root): self.root = root
    def _full(self, rel):
        p = (self.root / rel).resolve()
        if not p.is_relative_to(self.root): raise ValueError('outside')
        return p
    def open(self, rel): return open(self._full(rel), 'rb')
    def size(self, rel): return self._full(rel).stat().st_size

class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.service = MetadataService(Storage(self.root))
        tags = ID3(); tags.add(TIT2(encoding=3,text=['Before']))
        tags.add(APIC(encoding=3,mime='image/jpeg',type=3,data=b'COVER'))
        tags.save(self.root / 'track.mp3')
        with open(self.root / 'track.mp3','ab') as f: f.write(b'AUDIO_SENTINEL')
    def tearDown(self): self.temp.cleanup()
    def test_roundtrip(self):
        original = (self.root / 'track.mp3').read_bytes()
        revision = self.service.read('track.mp3')['revision']
        with patch.dict(os.environ, {'EDIT_ENABLED':'true'}):
            result = self.service.update('track.mp3', {'title':'After'}, revision)
        self.assertEqual(result['tags']['title'],'After')
        self.assertEqual((self.root / result['backup']).read_bytes(),original)
        self.assertTrue((self.root / 'track.mp3').read_bytes().endswith(b'AUDIO_SENTINEL'))
        self.assertEqual(ID3(self.root / 'track.mp3').getall('APIC')[0].data,b'COVER')
    def test_disabled(self):
        with patch.dict(os.environ, {'EDIT_ENABLED':'false'}):
            with self.assertRaises(PermissionError): self.service.update('track.mp3',{},'')
    def test_paths(self):
        for p in ('../x.mp3','/x.mp3','a/../x.mp3','.hidden.mp3','x.mp3:ads','x.flac'):
            with self.assertRaises(ValueError): self.service.path(p)
    def test_symlink(self):
        (self.root / 'link.mp3').symlink_to(self.root / 'track.mp3')
        with self.assertRaises(ValueError): self.service.read('link.mp3')
    def test_stale(self):
        with patch.dict(os.environ, {'EDIT_ENABLED':'true'}):
            with self.assertRaises(ValueError): self.service.update('track.mp3',{'title':'x'},'0'*64)
    def test_unknown(self):
        with patch.dict(os.environ, {'EDIT_ENABLED':'true'}):
            with self.assertRaises(ValueError): self.service.update('track.mp3',{'unknown':'x'},'0'*64)
    def test_auth(self):
        async def check(header):
            events=[]
            async def target(scope,receive,send): events.append({'status':200})
            async def send(event): events.append(event)
            await BearerAuth(target,'secret')({'type':'http','headers':[(b'authorization',header)]},None,send)
            return events[0]['status']
        for header in (b'',b'Bearer wrong',b'secret'):
            self.assertEqual(asyncio.run(check(header)),401)
        self.assertEqual(asyncio.run(check(b'Bearer secret')),200)
        with self.assertRaises(ValueError): BearerAuth(None,'')

if __name__ == '__main__': unittest.main()
