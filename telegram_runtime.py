"""Optional bot runtime with startup and 22:00 local-time status notifications."""
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from urllib.request import urlopen
from zoneinfo import ZoneInfo
from telegram_admin import AdminBot as Bot
from telegram_bot import BotError
from library_tools import public_url

LOG=logging.getLogger('mp3z.telegram.runtime')


def next_daily(now):
    target=now.replace(hour=22,minute=0,second=0,microsecond=0)
    return target if target>now else target+timedelta(days=1)


def status_chat(allowed, value):
    if not value:
        return None
    if not value.isdigit() or value not in allowed:
        raise ValueError('Status chat must be one private user ID from TELEGRAM_ALLOWED_USER_IDS')
    return value


def message(status, reason, uptime, now):
    state='wird aufgebaut' if status.get('building') else 'ruhend'
    return (f'MP3z | {reason}\n'
            f'Zeit: {now:%d.%m.%Y %H:%M %Z}\n'
            f'Dienst: HTTP bereit\n'
            f'Laufzeit: {int(max(0,uptime)//3600)} h {int(max(0,uptime)%3600//60)} min\n'
            f'Titel im Index: {status.get("total_files",0)}\n'
            f'Speicher: {status.get("storage","unbekannt")}\n'
            f'Index: {state}')


class RuntimeBot(Bot):
    def __init__(self,lib,token,allowed,url):
        if not token or not allowed or not all(str(x).isdigit() for x in allowed):
            raise ValueError('Telegram token and numeric user allowlist required')
        self.lib,self.token,self.allowed=lib,token,{str(x) for x in allowed}
        self.url=public_url(url.strip()) if url.strip() else None
        self.callbacks,self.last=OrderedDict(),{}

    def call(self,method,data,image=None):
        data=dict(data)
        markup=data.get('reply_markup')
        if isinstance(markup,dict) and 'inline_keyboard' in markup:
            rows=[[b for b in row if 'url' not in b or b.get('url')] for row in markup['inline_keyboard']]
            data['reply_markup']={**markup,'inline_keyboard':[row for row in rows if row]}
        return super().call(method,data,image=image)


def wait_ready(port,stop):
    for _ in range(120):
        if stop.is_set():return False
        try:
            with urlopen(f'http://127.0.0.1:{int(port)}/api/ping',timeout=2) as response:
                if json.load(response).get('status')=='ok':return True
        except Exception:
            pass
        stop.wait(1)
    LOG.warning('Telegram startup status skipped: HTTP readiness timeout')
    return False


def send_status(bot,chat,reason,started,zone,stop):
    for attempt in range(3):
        try:
            try:status=bot.lib.status()
            except Exception:
                bot.call('sendMessage',{'chat_id':chat,'text':f'MP3z | {reason}\nDienst: HTTP bereit\nBibliotheksstatus derzeit nicht abrufbar.'})
                return True
            uptime=time.monotonic()-started
            now=datetime.now(zone)
            if reason=='Dienst gestartet':
                from telegram_status_card import send_startup
                send_startup(bot,chat,status,uptime,now)
            else:
                bot.call('sendMessage',{'chat_id':chat,'text':message(status,reason,uptime,now)})
            return True
        except Exception as exc:
            LOG.warning('Telegram status delivery failed; no credentials logged')
            if attempt<2:
                stop.wait(min(300,max(1,getattr(exc,'retry',10))))
            if stop.is_set():return False
    return False


def notification_loop(bot,chat,zone,port,stop):
    started=time.monotonic()
    if not wait_ready(port,stop):return
    send_status(bot,chat,'Dienst gestartet',started,zone,stop)
    target=next_daily(datetime.now(zone))
    while not stop.is_set():
        now=datetime.now(zone)
        if now>=target:
            send_status(bot,chat,'Tagesstatus 22:00',started,zone,stop)
            target=next_daily(datetime.now(zone))
        delay=max(0.1,min(30,target.timestamp()-datetime.now(zone).timestamp()))
        stop.wait(delay)


def start_bot(lib):
    if os.getenv('TELEGRAM_ENABLED','false').lower() not in ('true','1','yes'):
        return
    allowed=[v.strip() for v in os.getenv('TELEGRAM_ALLOWED_USER_IDS','').split(',') if v.strip()]
    try:
        bot=RuntimeBot(lib,os.getenv('TELEGRAM_BOT_TOKEN',''),allowed,os.getenv('PUBLIC_URL',''))
    except (ValueError,TypeError):
        LOG.error('Telegram disabled: check token, allowlist and optional HTTPS PUBLIC_URL; player/MCP continue')
        return
    threading.Thread(target=bot.run,name='mp3z-telegram',daemon=True).start()
    try:
        chat=status_chat(bot.allowed,os.getenv('TELEGRAM_STATUS_CHAT_ID','').strip())
        if chat is None:
            LOG.info('Automatic Telegram status disabled: set TELEGRAM_STATUS_CHAT_ID')
            return
        zone=ZoneInfo(os.getenv('TELEGRAM_STATUS_TIMEZONE','Europe/Berlin'))
        port=int(os.getenv('PORT','80'))
    except (ValueError,KeyError,TypeError):
        LOG.error('Automatic Telegram status disabled: check status recipient, timezone and port')
        return
    stop=threading.Event()
    threading.Thread(target=notification_loop,args=(bot,chat,zone,port,stop),name='mp3z-status',daemon=True).start()
