import unittest
from app_login import AppLogin, patch_login

class LoginTests(unittest.TestCase):
    def test_credentials(self):
        auth=AppLogin('daniel','app-password')
        self.assertEqual(auth.authenticate('wrong','app-password','a')[1],401)
        self.assertEqual(auth.authenticate('daniel','smb-password','a')[1],401)
        token,status=auth.authenticate('daniel','app-password','a',now=100)
        self.assertEqual(status,200)
        self.assertTrue(auth.valid(token,now=101))
        self.assertFalse(auth.valid(token,now=43301))
    def test_logout(self):
        auth=AppLogin('user','password');token,_=auth.authenticate('user','password','a')
        auth.revoke(token);self.assertFalse(auth.valid(token))
    def test_required(self):
        for user,pw in (('','x'),('u',''),(' u','p')):
            with self.assertRaises(ValueError):AppLogin(user,pw)
    def test_limit(self):
        auth=AppLogin('u','p')
        for _ in range(10):auth.authenticate('bad','bad','a',now=100)
        self.assertEqual(auth.authenticate('u','p','a',now=101)[1],429)
        self.assertEqual(auth.authenticate('u','p','a',now=161)[1],200)
    def test_patch(self):
        source="<head></head>Gib dein Samba-Passwort ein um auf deine Musiksammlung zuzugreifen. JSON.stringify({ apikey: pass }) apiKey     = pass; function logout() {"
        result=patch_login(source)
        self.assertNotIn('Samba-Passwort',result)
        self.assertIn('username: user, password: pass',result)
        self.assertIn('apiKey = data.token',result)
        self.assertIn('mp3z_auth_version',result)
    def test_fail_closed_patch(self):
        with self.assertRaises(ValueError):patch_login('<head></head>')

if __name__=='__main__':unittest.main()
