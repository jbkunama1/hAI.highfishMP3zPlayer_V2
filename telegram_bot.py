"""Optional read-only private-chat Telegram bot. No live calls during tests."""
import io
import json
import logging
import os
import secrets
import threading
import time
from collections import OrderedDict
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from PIL import Image, ImageDraw
from library_tools import public_url

LOG = logging.getLogger('mp3z.telegram')


class BotError(Exception):
    def __init__(self, retry=5):
        self.retry = min(300,max(1,int(retry)))


class Bot:
    def __init__(self, lib, token, allowed, url):
        if not token or not allowed or not all(str(x).isdigit() for x in allowed):
            raise ValueError('Telegram token and numeric user allowlist required')
        self.lib,self.token,self.allowed,self.url = lib,token,{str(x) for x in allowed},public_url(url)
        self.callbacks,self.last = OrderedDict(),{}

    def call(self, method, data, image=None):
        if image is None:
            body=json.dumps(data).encode();content='application/json'
        else:
            boundary='mp3z'+secrets.token_hex(12)
            chunks=[]
            for name,value in data.items():
                value=json.dumps(value) if isinstance(value,dict) else str(value)
                chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="cover.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()+image+f'\r\n--{boundary}--\r\n'.encode())
            body=b''.join(chunks);content='multipart/form-data; boundary='+boundary
        req=Request(f'https://api.telegram.org/bot{self.token}/{method}',data=body,headers={'Content-Type':content})
        try:
            with urlopen(req,timeout=40) as response:result=json.load(response)
        except HTTPError as exc:
            try: retry=json.loads(exc.read(65536)).get('parameters',{}).get('retry_after',5)
            except Exception: retry=5
            raise BotError(retry) from None
        except Exception:
            raise BotError() from None
        if not result.get('ok'): raise BotError(result.get('parameters',{}).get('retry_after',5))
        return result.get('result',[])

    def button(self, text, uid, chat, action):
        now=time.time()
        self.callbacks=OrderedDict((k,v) for k,v in self.callbacks.items() if v[3]>now)
        ident=secrets.token_hex(10)
        self.callbacks[ident]=(str(uid),chat,action,now+600)
        while len(self.callbacks)>1024:self.callbacks.popitem(last=False)
        return {'text':text[:60],'callback_data':ident}

    def menu(self, uid, chat):
        self.call('sendMessage',{'chat_id':chat,'text':'🎵 MP3z · Deine Musiksammlung\nSuche mit /search Begriff oder tippe einen Suchbegriff.',
            'reply_markup':{'inline_keyboard':[[self.button('📁 Sammlung',uid,chat,('browse','',0)),self.button('📊 Status',uid,chat,('status','',0))],[{'text':'🎧 Webplayer','url':self.url}]]}})

    def page(self, uid, chat, mode, value, offset):
        data=self.lib.browse(value,offset,8) if mode=='browse' else self.lib.search(value,offset,8)
        entries=data.get('entries',data.get('results',[]));rows=[]
        for e in entries:
            kind='browse' if e.get('type')=='dir' else 'track'
            if kind=='track' and Path(e['path']).suffix.lower() not in self.lib.b.AUDIO_EXTS:continue
            rows.append([self.button(('📁 ' if kind=='browse' else '🎵 ')+e['name'],uid,chat,(kind,e['path'],0))])
        nav=[]
        if offset:nav.append(self.button('◀ Zurueck',uid,chat,(mode,value,max(0,offset-8))))
        if data.get('has_more'):nav.append(self.button('Weiter ▶',uid,chat,(mode,value,offset+8)))
        if nav:rows.append(nav)
        if mode=='browse' and value:rows.append([self.button('⬆ Uebergeordneter Ordner',uid,chat,('browse',value.rpartition('/')[0],0))])
        rows.append([self.button('🏠 Menue',uid,chat,('menu','',0))])
        text=f'📁 {value or "Sammlung"}' if mode=='browse' else f'🔎 {value}'
        self.call('sendMessage',{'chat_id':chat,'text':text[:500]+f'\n{data.get("total",0)} Eintraege · ab {offset+1}', 'reply_markup':{'inline_keyboard':rows}})

    def card(self, chat, path):
        try:
            from cover_service import normalize_image
            image=normalize_image(self.lib.cover(path))
        except Exception:
            img=Image.new('RGB',(640,360),'#141429');draw=ImageDraw.Draw(img)
            for x in range(640):draw.line((x,0,x,360),fill=(80+x//5,40,150))
            draw.text((35,145),'MP3z / Highfish AI',fill='white')
            out=io.BytesIO();img.save(out,'JPEG');image=out.getvalue()
        rows=[[{'text':'🎧 Webplayer oeffnen','url':self.url}]]
        self.call('sendPhoto',{'chat_id':chat,'caption':('🎵 '+path)[:1000],'reply_markup':{'inline_keyboard':rows}},image=image)

    def handle(self, update):
        cb=update.get('callback_query');msg=(cb or {}).get('message') or update.get('message',{})
        uid=str((cb or msg).get('from',{}).get('id',''));chat=msg.get('chat',{})
        if uid not in self.allowed or chat.get('type')!='private':return
        chat_id=chat['id'];now=time.time()
        if now-self.last.get(uid,0)<0.5:return
        self.last[uid]=now
        if cb:
            self.call('answerCallbackQuery',{'callback_query_id':cb['id']})
            entry=self.callbacks.get(cb.get('data',''))
            if not entry or entry[0]!=uid or entry[1]!=chat_id or entry[3]<=now:
                self.call('sendMessage',{'chat_id':chat_id,'text':'Menue abgelaufen. Bitte /start eingeben.'});return
            mode,value,offset=entry[2]
        else:
            text=msg.get('text','').strip()
            if not text or len(text)>500:return
            if text.startswith('/start') or text=='/help':return self.menu(uid,chat_id)
            if text=='/browse':mode,value,offset='browse','',0
            elif text=='/status':mode,value,offset='status','',0
            else:
                value=text[8:].strip() if text.startswith('/search ') else text
                if len(value)<2 or value.startswith('/'):
                    return self.menu(uid,chat_id)
                mode,offset='search',0
        if mode=='menu':return self.menu(uid,chat_id)
        if mode=='status':
            s=self.lib.status()
            return self.call('sendMessage',{'chat_id':chat_id,'text':f'📊 {s.get("total_files",0)} Titel · Index aktiv: {s.get("building",False)}'})
        if mode=='track':return self.card(chat_id,value)
        return self.page(uid,chat_id,mode,value,offset)

    def run(self):
        offset=0
        while True:
            try:
                updates=self.call('getUpdates',{'offset':offset,'timeout':25,'allowed_updates':['message','callback_query']})
                for update in updates:
                    offset=update['update_id']+1
                    try:self.handle(update)
                    except BotError:raise
                    except Exception:LOG.warning('Telegram library request failed; no credentials logged')
            except BotError as exc:
                LOG.warning('Telegram request failed; retrying without logging token')
                time.sleep(exc.retry)
            except Exception:
                LOG.warning('Telegram polling failed');time.sleep(5)


def start_bot(lib):
    if os.getenv('TELEGRAM_ENABLED','false').lower() not in ('true','1','yes'):return
    allowed=[v.strip() for v in os.getenv('TELEGRAM_ALLOWED_USER_IDS','').split(',') if v.strip()]
    bot=Bot(lib,os.getenv('TELEGRAM_BOT_TOKEN',''),allowed,os.getenv('PUBLIC_URL',''))
    threading.Thread(target=bot.run,name='mp3z-telegram',daemon=True).start()
