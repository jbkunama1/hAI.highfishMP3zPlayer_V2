import os
import unittest
from unittest.mock import patch
from mcp_security import host_values, origin_values

class SecurityTests(unittest.TestCase):
    def test_default_hosts_include_reported_ip_pattern(self):
        with patch.dict(os.environ,{},clear=True):
            defaults=host_values()
            self.assertIn('192.168.178.26:*',defaults)
            self.assertIn('localhost:*',defaults)
            self.assertIn('mp3z:*',defaults)
    def test_explicit_ipv4_host(self):
        with patch.dict(os.environ,{'MCP_ALLOWED_HOSTS':'192.168.178.26:*'}):
            self.assertIn('192.168.178.26:*',host_values())
    def test_host_validation(self):
        for value in ('*','http://bad','good/path','bad host','host:99999','http://foo:80','foo:0','foo:65536','[gg::1]:*','2001:db8::1'):
            with patch.dict(os.environ,{'MCP_ALLOWED_HOSTS':value}):
                with self.assertRaises(ValueError):host_values()
    def test_origin_validation(self):
        with patch.dict(os.environ,{'MCP_ALLOWED_ORIGINS':'http://192.168.178.26:8066'}):
            self.assertEqual(origin_values(),['http://192.168.178.26:8066'])
        for value in ('*','http://user:pass@host','http://host/path','http://host/?x=1'):
            with patch.dict(os.environ,{'MCP_ALLOWED_ORIGINS':value}):
                with self.assertRaises(ValueError):origin_values()
    def test_public_url_origin_added(self):
        with patch.dict(os.environ,{'PUBLIC_URL':'https://music.example'}):
            self.assertIn('https://music.example',origin_values())

if __name__=='__main__':unittest.main()
