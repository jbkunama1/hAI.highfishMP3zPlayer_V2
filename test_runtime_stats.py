import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from PIL import Image
from runtime_stats import Stats
from telegram_status_card import caption, render, send_startup


class StatsTests(unittest.TestCase):
    def test_restart(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'stats.json'; clock=[0]
            a=Stats(p,clock=lambda:clock[0]); clock[0]=120
            a.save(); a.save(); a.record('index_runs'); a.close(); a.close()
            clock[0]=1000; b=Stats(p,clock=lambda:clock[0])
            self.assertEqual(b.snapshot()['uptime_seconds'],120)
            self.assertEqual(b.snapshot()['starts'],2)
            self.assertEqual(b.snapshot()['index_failures'],1)
            c=Stats(p); self.assertFalse(c.persistent); c.close(); b.close()
    def test_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'stats.json'; p.write_text('{bad'); a=Stats(p)
            self.assertIsNone(a.snapshot()['last_index'])
            self.assertTrue(Path(str(p)+'.corrupt').exists()); a.close()
    def test_cards(self):
        now=datetime.now(timezone.utc)
        s={'stats':{'last_index':dict(at=1,duration=2,files=3,bytes=4000000000),'persistent':True},'music_root':'SECRET'}
        for daily in (False,True):
            text=caption(s,120,now,daily=daily)
            self.assertIn('4.00 GB',text); self.assertNotIn('SECRET',text); self.assertLess(len(text),1024)
            self.assertEqual(Image.open(io.BytesIO(render(s,120,now,daily=daily))).size,(1100,940))
            bot=SimpleNamespace(call=Mock(side_effect=[RuntimeError(),None]))
            send_startup(bot,'1',s,120,now,daily=daily)
            self.assertEqual([c.args[0] for c in bot.call.call_args_list],['sendPhoto','sendMessage'])


if __name__=='__main__': unittest.main()
