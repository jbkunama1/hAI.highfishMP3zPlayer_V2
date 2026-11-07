import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from mutagen.id3 import ID3, TIT2, APIC
from cover_service import CoverService, normalize_image, MAX_IMAGE

class Storage:
    mode = 'local'
    def __init__(self, root): self.root = root
    def _full(self, rel):
        p = (self.root / rel).resolve()
        if not p.is_relative_to(self.root): raise ValueError('outside')
        return p
    def open(self, rel): return open(self._full(rel), 'rb')
    def size(self, rel): return self._full(rel).stat().st_size

class Covers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.s = Storage(self.root); self.c = CoverService(self.s)
        tags=ID3();tags.add(TIT2(encoding=3,text=['Keep title']))
        tags.add(APIC(encoding=3,mime='image/jpeg',type=4,desc='Back',data=b'BACK'))
        tags.save(self.root/'track.mp3')
        with open(self.root/'track.mp3','ab') as f:f.write(b'AUDIO_SENTINEL')
        out=io.BytesIO();Image.new('RGBA',(20,20),(255,0,0,128)).save(out,'PNG');self.image=out.getvalue()
    def tearDown(self): self.temp.cleanup()
    def upload(self,path,target='embedded'):
        rev=self.c.inspect(path,target)['revision']
        with patch.dict(os.environ,{'EDIT_ENABLED':'true'}):return self.c.upload(path,self.image,target,rev)
    def test_embedded(self):
        original=(self.root/'track.mp3').read_bytes()
        result=self.upload('track.mp3');tags=ID3(self.root/'track.mp3')
        self.assertEqual(str(tags['TIT2']),'Keep title')
        self.assertTrue((self.root/'track.mp3').read_bytes().endswith(b'AUDIO_SENTINEL'))
        self.assertEqual((self.root/result['backup']).read_bytes(),original)
        pics=tags.getall('APIC');self.assertEqual(len(pics),2)
        self.assertEqual(next(p.data for p in pics if p.type==4),b'BACK')
        self.assertEqual(next(p.mime for p in pics if p.type==3),'image/jpeg')
    def test_folder_create_replace_backup(self):
        result=self.upload('','folder');self.assertIsNone(result['backup'])
        old=(self.root/'cover.jpg').read_bytes()
        result=self.upload('','folder');self.assertEqual((self.root/result['backup']).read_bytes(),old)
    def test_invalid(self):
        for data in (b'',b'not an image',b'x'*(MAX_IMAGE+1)):
            with self.assertRaises(ValueError):normalize_image(data)
    def test_oversized_pixels(self):
        with patch('cover_service.MAX_PIXELS',10):
            with self.assertRaises(ValueError):normalize_image(self.image)
    def test_disabled_and_stale(self):
        with patch.dict(os.environ,{'EDIT_ENABLED':'false'}):
            with self.assertRaises(PermissionError):self.c.upload('track.mp3',self.image,'embedded','')
        with patch.dict(os.environ,{'EDIT_ENABLED':'true'}):
            with self.assertRaises(ValueError):self.c.upload('track.mp3',self.image,'embedded','0'*64)
    def test_paths_and_symlink(self):
        for path in ('../outside','/absolute','.hidden','a/../b'):
            with self.assertRaises(ValueError):self.c.inspect(path,'folder')
        (self.root/'cover.jpg').symlink_to(self.root/'track.mp3')
        with self.assertRaises(ValueError):self.c.inspect('','folder')
    def test_mock_smb(self):
        root=self.root
        class SC:
            path=SimpleNamespace(isdir=lambda p,**kw:Path(p).is_dir(),exists=lambda p,**kw:Path(p).exists())
            def lstat(self,p,**kw):return Path(p).lstat()
            def stat(self,p,**kw):return Path(p).stat()
            def open_file(self,p,mode,**kw):return open(p,mode)
            def replace(self,a,b,**kw):os.replace(a,b)
            def remove(self,p,**kw):os.remove(p)
        self.c=CoverService(SimpleNamespace(mode='smb',port=445,sc=SC(),_login=lambda:None,_unc=lambda p:str(root/p)))
        result=self.upload('track.mp3')
        self.assertTrue((root/result['backup']).is_file())
        result=self.upload('','folder');self.assertTrue((root/'cover.jpg').is_file())

if __name__=='__main__':unittest.main()
