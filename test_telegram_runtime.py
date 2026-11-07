import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch, Mock
from zoneinfo import ZoneInfo
from telegram_runtime import RuntimeBot, next_daily, status_chat, message, start_bot, send_status

class RuntimeTests(unittest.TestCase):
    def test_schedule_today_and_tomorrow(self):
        zone=ZoneInfo('Europe/Berlin')
        now=datetime(2026,1,15,20,0,tzinfo=zone)
        self.assertEqual(next_daily(now).hour,22)
        self.assertEqual(next_daily(now).day,15)
        self.assertEqual(next_daily(now.replace(hour=22)).day,16)
    def test_summer_winter(self):
        zone=ZoneInfo('Europe/Berlin')
        self.assertEqual(next_daily(datetime(2026,1,15,20,tzinfo=zone)).utcoffset(),timedelta(hours=1))
        self.assertEqual(next_daily(datetime(2026,7,15,20,tzinfo=zone)).utcoffset(),timedelta(hours=2))
    def test_recipient(self):
        self.assertIsNone(status_chat({'1'},''))
        self.assertEqual(status_chat({'1'},'1'),'1')
        for value in ('2','-100','1,2'):
            with self.assertRaises(ValueError):status_chat({'1'},value)
    def test_optional_url_and_filter(self):
        bot=RuntimeBot(None,'fake',['1'],'')
        self.assertIsNone(bot.url)
        with patch('telegram_runtime.Bot.call',return_value=[]) as call:
            bot.call('sendMessage',{'chat_id':'1','reply_markup':{'inline_keyboard':[[{'text':'bad','url':None}],[{'text':'ok','callback_data':'x'}]]}})
            self.assertEqual(call.call_args.args[1]['reply_markup']['inline_keyboard'],[[{'text':'ok','callback_data':'x'}]])
    def test_config_error_does_not_crash(self):
        with patch.dict('os.environ',{'TELEGRAM_ENABLED':'true','TELEGRAM_BOT_TOKEN':'','TELEGRAM_ALLOWED_USER_IDS':'1'}):
            with patch('telegram_runtime.threading.Thread') as thread:
                start_bot(None)
                thread.assert_not_called()
    def test_status_has_no_paths_or_keys(self):
        text=message({'total_files':12,'storage':'smb','building':True,'music_root':'SECRET_PATH'},'Dienst gestartet',3660,datetime.now(ZoneInfo('Europe/Berlin')))
        self.assertIn('12',text);self.assertIn('1 h 1 min',text);self.assertNotIn('SECRET_PATH',text)
    def test_send_retry_without_real_network(self):
        bot=SimpleNamespace(lib=SimpleNamespace(status=lambda:{'total_files':2}),call=Mock(side_effect=[RuntimeError('not logged'),[]]))
        stop=SimpleNamespace(wait=Mock(),is_set=lambda:False)
        self.assertTrue(send_status(bot,'1','Test',0,ZoneInfo('Europe/Berlin'),stop))
        self.assertEqual(bot.call.call_count,2)

if __name__=='__main__':unittest.main()
