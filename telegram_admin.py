"""Private-chat administration with actor-bound, expiring confirmations."""
import logging
import os
import threading
import time
from collections import Counter
from pathlib import Path
from telegram_bot import Bot

LOG = logging.getLogger('mp3z.telegram.admin')
STARTED = time.monotonic()
REINDEX_LOCK = threading.Lock()


class AdminBot(Bot):
    def show(self, uid, chat, text, rows=None):
        rows = list(rows or [])
        rows.append([self.button('🏠 Cockpit', uid, chat, ('menu', '', 0))])
        return self.call('sendMessage', {'chat_id': chat, 'text': text[:3900],
            'reply_markup': {'inline_keyboard': rows}})

    def menu(self, uid, chat):
        rows = [
            [self.button('📁 Sammlung', uid, chat, ('browse', '', 0)),
             self.button('🔎 Suchen', uid, chat, ('admin:search', '', 0))],
            [self.button('📊 Live-Status', uid, chat, ('admin:status', '', 0)),
             self.button('🎼 Statistik', uid, chat, ('admin:stats', '', 0))],
            [self.button('🛠 Admin & Wartung', uid, chat, ('admin:tools', '', 0)),
             self.button('🛡 Einstellungen', uid, chat, ('admin:config', '', 0))],
            [self.button('❓ Hilfe', uid, chat, ('admin:help', '', 0))]]
        if self.url:
            rows.append([{'text': '🎧 Ab zum Webplayer', 'url': self.url}])
        return self.show(uid, chat,
            '🎵 MP3z · Dein Musik-Cockpit\n\nMoin! Sammlung im Griff, Beats am Start.\nWas darf’s sein?', rows)

    def confirm(self, uid, chat, action, title):
        button = self.button('✅ Ja, ausführen', uid, chat, ('admin:execute', action, 0))
        key = button['callback_data']
        owner, target, payload, _ = self.callbacks[key]
        self.callbacks[key] = (owner, target, payload, time.time() + 60)
        return self.show(uid, chat, title + '\n\nBestätigung gilt 60 Sekunden und nur einmal.',
            [[button, self.button('❌ Abbrechen', uid, chat, ('admin:cancel', '', 0))]])

    def panel(self, uid, chat, action, value=''):
        refresh = [[self.button('🔄 Aktualisieren', uid, chat, ('admin:' + action, '', 0))]]
        if action == 'search':
            return self.show(uid, chat, '🔎 Welcher Track darf’s sein?\nTippe einen Suchbegriff oder /search Interpret Titel.')
        if action == 'help':
            return self.show(uid, chat, '🧭 Dein Spickzettel\n/start · Cockpit\n/admin · Wartung\n/status · Live-Status\n/stats · Bibliotheksstatistik\n/settings · sichere Konfigurationsübersicht\n/browse · Sammlung\n/search Begriff · Suche\n/cancel · zurück zum Cockpit\n\n🛡 Nur freigegebene private Chats. Wartung braucht dein Okay. Keine Fernsteuerung der Browser-Wiedergabe.')
        if action == 'tools':
            return self.show(uid, chat, '🛠 Maschinenraum\n\nIndex neu aufbauen: Musikdateien bleiben unverändert.\nStreamlinks sperren: Alle temporären Freigabelinks werden ungültig. Bereits laufende Downloads werden nicht aktiv beendet.\nMenüs schließen: Alte Buttons dieses Chats deaktivieren.', [
                [self.button('🔄 Index neu aufbauen', uid, chat, ('admin:ask', 'reindex', 0))],
                [self.button('🔐 Streamlinks sperren', uid, chat, ('admin:ask', 'revoke', 0))],
                [self.button('🧹 Alte Menüs schließen', uid, chat, ('admin:ask', 'menus', 0))]])
        if action == 'ask':
            titles = {'reindex': '🔄 Bibliotheksindex jetzt neu aufbauen?',
                      'revoke': '🔐 Wirklich ALLE temporären Streamlinks sperren? Auch Links anderer Nutzer sind betroffen.',
                      'menus': '🧹 Alle bisherigen Menübuttons in diesem Chat deaktivieren?'}
            if value not in titles:
                return self.show(uid, chat, '🤔 Diese Aktion kenne ich nicht. Zurück zum Cockpit.')
            return self.confirm(uid, chat, value, titles[value])
        if action == 'cancel':
            for key, entry in list(self.callbacks.items()):
                if entry[0] == str(uid) and entry[1] == chat and entry[2][0] == 'admin:execute':
                    self.callbacks.pop(key, None)
            return self.show(uid, chat, '👌 Abgebrochen. Nichts geändert.')
        if action == 'execute':
            if value == 'reindex':
                if not REINDEX_LOCK.acquire(blocking=False):
                    return self.show(uid, chat, '⏳ Ein Telegram-Indexauftrag läuft bereits.')
                if self.lib.b.index._building:
                    REINDEX_LOCK.release()
                    return self.show(uid, chat, '⏳ Der Index arbeitet bereits. Schau später im Status vorbei.')
                def rebuild():
                    try:
                        self.lib.b.index._build()
                    except Exception:
                        LOG.warning('Telegram index rebuild failed; no credentials logged')
                    finally:
                        REINDEX_LOCK.release()
                worker = threading.Thread(target=rebuild, name='mp3z-telegram-index', daemon=True)
                try:
                    worker.start()
                except Exception:
                    REINDEX_LOCK.release()
                    raise
                return self.show(uid, chat, '🔄 Index-Neuaufbau angestoßen. Das ist noch keine Erfolgsmeldung.\nDen aktuellen Stand findest du unter /status.')
            if value == 'revoke':
                with self.lib.lock:
                    count = len(self.lib.links)
                    self.lib.links.clear()
                LOG.info('Telegram admin action=revoke actor=%s count=%s', uid, count)
                return self.show(uid, chat, f'🔐 Erledigt: {count} gespeicherte Streamlinks entfernt. Neue Freigaben sind weiterhin möglich.')
            if value == 'menus':
                keys = [k for k, e in self.callbacks.items() if e[0] == str(uid) and e[1] == chat]
                for key in keys:
                    self.callbacks.pop(key, None)
                return self.show(uid, chat, f'🧹 Aufgeräumt: {len(keys)} alte Buttons deaktiviert.')
            return self.show(uid, chat, '🤔 Unbekannte Wartungsaktion. Nichts geändert.')
        if action == 'status':
            s = self.lib.status()
            with self.lib.lock:
                links = sum(1 for entry in self.lib.links.values() if entry[1] > time.time())
            uptime = int((time.monotonic() - STARTED) // 60)
            state = '🔄 wird aufgebaut' if s.get('building') else '💤 momentan kein Aufbau'
            text = (f'📊 MP3z · Lagebericht\n\n🎵 Titel: {s.get("total_files", 0)}\n'
                    f'📚 Index: {state}\n⏱ Bot-Modul aktiv: {uptime} Minuten\n'
                    f'🔗 Aktive temporäre Links: {links}\n\nDas ist der Bibliotheksstatus, kein externer Erreichbarkeitstest.')
            return self.show(uid, chat, text, refresh)
        if action == 'stats':
            index = self.lib.b.index
            with index._lock:
                entries = list(index._entries)
                building = index._building
            formats = Counter(Path(e.get('path', '')).suffix.lower() or '(ohne Endung)' for e in entries)
            folders = len({e.get('dir', '') for e in entries})
            lines = '\n'.join(f'{ext[:20]}: {count}' for ext, count in formats.most_common(12))
            return self.show(uid, chat, f'🎼 Sammlung in Zahlen\n\n{len(entries)} indexierte Titel\n{folders} Ordner mit indexierten Titeln\n\n{lines or "Noch keine Titel im Index."}\n\n' + ('🔄 Momentaufnahme während des Aufbaus.' if building else '📚 Aus dem aktuellen Index; kein neuer Dateiscan.'), refresh)
        if action == 'config':
            flag = lambda key: 'an' if os.getenv(key, 'false').lower() in ('true', '1', 'yes') else 'aus'
            return self.show(uid, chat, '🛡 Sichere Konfigurationsübersicht\n\n'
                f'ID3-Web-Schreibzugriff: {flag("EDIT_ENABLED")}\nMCP-Schreibzugriff: {flag("MCP_WRITE_ENABLED")}\n'
                f'Automatische Statusmeldungen: {"konfiguriert" if os.getenv("TELEGRAM_STATUS_CHAT_ID") else "nicht konfiguriert"}\n'
                f'HTTPS-Webplayer-Link: {"verfügbar" if self.url else "nicht konfiguriert"}\n'
                f'Freigegebene Nutzer: {len(self.allowed)}\n\nTokens, Passwörter und Speicherpfade bleiben geheim. Diese Ansicht ändert keine Berechtigungen.', refresh)
        return self.menu(uid, chat)

    def handle(self, update):
        cb = update.get('callback_query')
        msg = (cb or {}).get('message') or update.get('message', {})
        uid = str((cb or msg).get('from', {}).get('id', ''))
        chat = msg.get('chat', {})
        if uid not in self.allowed or chat.get('type') != 'private':
            return
        chat_id = chat['id']
        now = time.time()
        entry = self.callbacks.get(cb.get('data', '')) if cb else None
        text = msg.get('text', '').strip()
        command = text.split(maxsplit=1)[0].split('@')[0] if text else ''
        commands = {'/admin': 'tools', '/status': 'status', '/stats': 'stats', '/settings': 'config', '/help': 'help', '/cancel': 'cancel'}
        if not cb and command == '/start':
            action, value = 'menu', ''
        elif cb and entry and entry[2][0].startswith('admin:'):
            action, value = entry[2][0][6:], entry[2][1]
        elif not cb and command in commands:
            action, value = commands[command], ''
        else:
            return super().handle(update)
        if cb:
            self.call('answerCallbackQuery', {'callback_query_id': cb['id']})
            if entry[0] != uid or entry[1] != chat_id or entry[3] <= now:
                return self.show(uid, chat_id, '⌛ Dieser Button ist abgelaufen oder gehört zu einem anderen Chat. Bitte /start.')
        if now - self.last.get(uid, 0) < 0.5:
            return
        self.last[uid] = now
        if cb and action == 'execute':
            self.callbacks.pop(cb['data'], None)
        try:
            return self.panel(uid, chat_id, action, value)
        except Exception:
            LOG.warning('Telegram admin request failed; no credentials logged')
            return self.show(uid, chat_id, '🛠 Das hat gerade nicht geklappt. Bitte später erneut versuchen. Es wurde kein erfolgreicher Abschluss bestätigt.')
