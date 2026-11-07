"""Run with installed requirements-metadata.txt; exercises the actual deployed entrypoint."""
import asyncio
import importlib.util
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

@unittest.skipUnless(importlib.util.find_spec('mcp') and importlib.util.find_spec('flask'), 'Install requirements-metadata.txt')
class Integration(unittest.TestCase):
    def test_real_sdk_and_http_auth(self):
        with tempfile.TemporaryDirectory() as directory:
            from mutagen.id3 import ID3,TIT2
            track=Path(directory)/'Song.mp3';tags=ID3();tags.add(TIT2(encoding=3,text=['Song']));tags.save(track)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            env={**os.environ,'HOST':'127.0.0.1','PORT':str(port),'MUSIC_ROOT':directory,'STORAGE_MODE':'local',
                'APP_USERNAME':'test','APP_PASSWORD':'test-password','API_KEY_OVERRIDE':'test-api','MCP_API_KEY':'test-mcp',
                'TELEGRAM_ENABLED':'false','EDIT_ENABLED':'false','MCP_WRITE_ENABLED':'false','PUBLIC_URL':'https://music.example'}
            process=subprocess.Popen([sys.executable,'cover_app.py'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            base=f'http://127.0.0.1:{port}'
            try:
                ready=False
                for _ in range(100):
                    if process.poll() is not None:self.fail('Application exited before ready')
                    try:
                        with urlopen(base+'/api/ping',timeout=1):ready=True;break
                    except Exception:time.sleep(0.1)
                self.assertTrue(ready,'Startup timeout')
                with self.assertRaises(HTTPError) as cm:urlopen(base+'/agent/mcp',timeout=3)
                self.assertEqual(cm.exception.code,401)
                async def exercise():
                    from mcp import ClientSession
                    from mcp.client.streamable_http import streamablehttp_client
                    async with streamablehttp_client(base+'/agent/mcp',headers={'Authorization':'Bearer test-mcp'}) as (read,write,_):
                        async with ClientSession(read,write) as session:
                            await session.initialize()
                            tools=await session.list_tools();names={t.name for t in tools.tools}
                            self.assertTrue({'browse_library','library_status','read_cover','get_stream_link','read_id3','update_id3','inspect_cover','upload_cover'}<=names)
                            result=await session.call_tool('browse_library',{'path':'','offset':0,'limit':8})
                            self.assertFalse(result.isError)
                            result=await session.call_tool('read_id3',{'path':'Song.mp3'})
                            self.assertFalse(result.isError)
                            result=await session.call_tool('update_id3',{'path':'Song.mp3','tags':{'title':'Blocked'},'revision':'0'*64})
                            self.assertTrue(result.isError)
                asyncio.run(exercise())
            finally:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':unittest.main()
