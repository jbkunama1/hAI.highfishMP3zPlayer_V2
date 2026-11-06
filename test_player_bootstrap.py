import unittest
from player_bootstrap import patch_player

class PlayerPatchTests(unittest.TestCase):
    def test_api_url(self):
        self.assertIn('fetch(baseUrl + endpoint', patch_player('fetch(url + endpoint'))
    def test_login_origin(self):
        self.assertEqual(patch_player("baseUrl || 'http://localhost'"), 'baseUrl || location.origin')
    def test_initial_origin(self):
        self.assertIn('location.origin', patch_player("localStorage.getItem('mp3z_url')    || ''"))
    def test_theme_script(self):
        self.assertIn('/player-themes.js', patch_player('<body></body>'))

if __name__ == '__main__': unittest.main()
