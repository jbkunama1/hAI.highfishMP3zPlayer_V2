import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch, Mock
from zoneinfo import ZoneInfo
from telegram_runtime import RuntimeBot, next_daily, status_chat, message, start_bot, send_status, HOME_CALLBACK

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
            self.assertEqual(call.call_args.args[1]['reply_markup']['inline_keyboard'],[[{'text':'ok','callback_data':'x'}],[{'text':'🏠 Hauptmenü','callback_data':HOME_CALLBACK}]])
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
    def test_home_on_photos_text_and_edits(self):
        bot=RuntimeBot(None,'fake',['1'],'')
        with patch('telegram_runtime.Bot.call',return_value=[]) as call:
            for method in ('sendMessage','sendPhoto','editMessageCaption'):
                bot.call(method,{'chat_id':1})
                data=call.call_args.args[1]
                self.assertEqual(data['reply_markup']['inline_keyboard'][-1][0]['callback_data'],HOME_CALLBACK)
                bot.call(method,data)
                self.assertEqual(call.call_args.args[1],data)
    def test_home_survives_missing_callback_cache_and_rejects_groups(self):
        bot=RuntimeBot(None,'fake',['1'],'')
        update={'callback_query':{'id':'x','data':HOME_CALLBACK,'from':{'id':1},'message':{'chat':{'id':1,'type':'private'}}}}
        with patch.object(bot,'menu') as menu, patch('telegram_runtime.Bot.call'):
            bot.handle(update);menu.assert_called_once_with('1',1)
            menu.reset_mock();update['callback_query']['from']['id']=2
            bot.handle(update);menu.assert_not_called()
            update['callback_query']['from']['id']=1
            update['callback_query']['message']['chat']['type']='group'
            bot.handle(update);menu.assert_not_called()
    def test_old_menu_replaced_without_mutating_keyboard(self):
        bot=RuntimeBot(None,'fake',['1'],'')
        bot.callbacks['old']=('1',1,('menu','',0),0)
        data={'chat_id':1,'reply_markup':{'inline_keyboard':[[{'text':'Old','callback_data':'old'},{'text':'Action','callback_data':'action'}]]}}
        with patch('telegram_runtime.Bot.call') as call:
            bot.call('sendMessage',data)
            rows=call.call_args.args[1]['reply_markup']['inline_keyboard']
            self.assertEqual(rows[0],[{'text':'Action','callback_data':'action'}])
            self.assertEqual(rows[-1][0]['callback_data'],HOME_CALLBACK)
            self.assertEqual(len(data['reply_markup']['inline_keyboard'][0]),2)

if __name__=='__main__':unittest.main()
