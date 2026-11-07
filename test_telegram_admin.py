import threading
import time
import unittest
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import Mock
from telegram_admin import AdminBot


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.bot = AdminBot.__new__(AdminBot)
        self.bot.allowed = {'1', '2'}
        self.bot.url = None
        self.bot.callbacks = OrderedDict()
        self.bot.last = {}
        self.bot.lib = SimpleNamespace(lock=threading.RLock(), links={'x': ('track', time.time()+600)})
        self.bot.call = Mock(return_value={})
        self.bot.show = Mock()
        self.bot.button = Mock(return_value={"text": "Test", "callback_data": "test"})

    def callback(self, uid=1, chat=1):
        return {'callback_query': {'id': 'cb', 'from': {'id': uid}, 'data': 'once',
            'message': {'chat': {'id': chat, 'type': 'private'}}}}

    def pending(self, expiry=None):
        self.bot.callbacks['once'] = ('1', 1, ('admin:execute', 'revoke', 0), expiry or time.time()+60)

    def test_unknown_user_cannot_act(self):
        self.pending()
        self.bot.handle(self.callback(uid=9))
        self.assertIn('x', self.bot.lib.links)
        self.bot.call.assert_not_called()

    def test_confirmation_is_actor_and_chat_bound(self):
        self.pending()
        self.bot.handle(self.callback(uid=2))
        self.assertIn('x', self.bot.lib.links)
        self.bot.handle(self.callback(chat=2))
        self.assertIn('x', self.bot.lib.links)

    def test_expired_confirmation_does_not_mutate(self):
        self.pending(time.time()-1)
        self.bot.handle(self.callback())
        self.assertIn('x', self.bot.lib.links)

    def test_confirmation_consumed_before_mutation(self):
        self.pending()
        self.bot.handle(self.callback())
        self.assertEqual(self.bot.lib.links, {})
        self.assertNotIn('once', self.bot.callbacks)

    def test_cancel_invalidates_pending_confirmation(self):
        self.pending()
        self.bot.panel('1', 1, 'cancel')
        self.assertNotIn('once', self.bot.callbacks)
        self.assertIn('x', self.bot.lib.links)

    def test_group_is_rejected(self):
        self.pending()
        update = self.callback()
        update['callback_query']['message']['chat']['type'] = 'group'
        self.bot.handle(update)
        self.assertIn('x', self.bot.lib.links)
        self.bot.call.assert_not_called()

    def test_menu_has_no_empty_url(self):
        del self.bot.show
        self.bot.button = lambda text, uid, chat, action: {'text': text, 'callback_data': 'test'}
        self.bot.menu('1', 1)
        payload = self.bot.call.call_args.args[1]
        self.assertFalse(any('url' in button for row in payload['reply_markup']['inline_keyboard'] for button in row))


if __name__ == '__main__':
    unittest.main()
