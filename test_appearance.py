"""Appearance store and source-patch contract tests; no live service calls."""
import tempfile
import unittest
from pathlib import Path
from appearance import Preferences, DEFAULTS, patch_script


class AppearanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'appearance.db';self.store=Preferences(self.db)

    def test_persistence_account_and_partial_merge(self):
        self.assertEqual(self.store.run('alice')[0]['preferences'],DEFAULTS)
        self.store.run('alice',{'theme':'neon80'},0)
        self.store.run('alice',{'view':'cards'},1)
        data,status=Preferences(self.db).run('alice')
        self.assertEqual(status,200);self.assertEqual(data['preferences']['theme'],'neon80')
        self.assertEqual(data['preferences']['view'],'cards')
        self.assertEqual(self.store.run('bob')[0]['preferences'],DEFAULTS)

    def test_stale_revision_and_validation(self):
        self.store.run('alice',{'design':'Synthwave'},0)
        self.assertEqual(self.store.run('alice',{'design':'Ocean'},0)[1],409)
        for patch,rev in [({'theme':'unknown'},1),({'user':'bob'},1),({},1),({'view':'cards'},True)]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):self.store.run('alice',patch,rev)

    def test_mobile_markup(self):
        text='<button>Design</button><label>Farben <select aria-label="Farbverlauf"></select></label>'
        result=patch_script('/mobile-view.js',text)
        self.assertIn('>Designs</button>',result);self.assertIn('hidden',result)
        self.assertNotIn('<label>Farben',result)
        with self.assertRaises(ValueError):patch_script('/mobile-view.js','changed source')

    def test_theme_patch_contract(self):
        text="const mobile=document.getElementById('mobile-now-playing');if(mobile){disable();}\ntry{localStorage.setItem('mp3z_music_theme',current);}catch{}\nconst targets=[['settings-modal','.s-sheet'],['mobile-now-playing','.mobile-bottom']];if(mobile&&!mobile.querySelector('.music-theme-picker'))attach();"
        result=patch_script('/music-themes.js',text)
        self.assertNotIn('disable();',result)
        self.assertNotIn("['mobile-now-playing','.mobile-bottom']",result)
        self.assertIn('mp3z-preferences-theme',result)
        self.assertIn('mp3z-theme-applied',result)


if __name__=='__main__':unittest.main()
