import csv
import io
import json
import threading
import unittest
from types import SimpleNamespace
from admin_ui import snapshot, render_export, csv_safe

class ExportTests(unittest.TestCase):
    def backend(self):
        return SimpleNamespace(STORAGE=SimpleNamespace(mode='local'),index=SimpleNamespace(
            _lock=threading.Lock(),_building=False,_built=123,
            _entries=[{'name':'Titel.mp3','path':'Album/Titel.mp3','dir':'Album','password':'NEVER_EXPORT'}]))
    def test_snapshot_excludes_secrets(self):
        data=snapshot(self.backend());raw=json.dumps(data)
        self.assertNotIn('NEVER_EXPORT',raw)
        self.assertEqual(data['total_files'],1)
        self.assertEqual(data['schema'],'mp3z-index-v1')
    def test_json(self):
        raw,mime,ext=render_export(snapshot(self.backend()),'json')
        self.assertEqual(json.loads(raw)['entries'][0]['name'],'Titel.mp3')
        self.assertEqual(ext,'json')
    def test_csv_injection(self):
        for value in ('=CMD()','+SUM(A1)','-1+2','@evil','  =evil','\ttext'):
            self.assertTrue(csv_safe(value).startswith("'"))
        self.assertEqual(csv_safe('normal.mp3'),'normal.mp3')
    def test_csv_roundtrip(self):
        data=snapshot(self.backend());data['entries'][0]['name']='Titel, mit Umlaut ä.mp3'
        raw,_,_=render_export(data,'csv')
        row=list(csv.DictReader(io.StringIO(raw)))[0]
        self.assertEqual(row['name'],'Titel, mit Umlaut ä.mp3')
        self.assertEqual(set(row),{'name','path','dir'})
    def test_unknown_format(self):
        with self.assertRaises(ValueError):render_export(snapshot(self.backend()),'sqlite')
    def test_snapshot_detached(self):
        backend=self.backend();data=snapshot(backend)
        backend.index._entries[0]['name']='Changed'
        self.assertEqual(data['entries'][0]['name'],'Titel.mp3')

if __name__=='__main__':unittest.main()
