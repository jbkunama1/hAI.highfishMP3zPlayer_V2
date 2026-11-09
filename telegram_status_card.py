"""Graphical Telegram status with explicitly labelled durable statistics."""
import io
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont


def duration(value):
    if value is None: return 'noch nicht erfasst'
    minutes = max(0, int(value)) // 60
    return f'{minutes // 1440} d {minutes % 1440 // 60} h {minutes % 60} min'


def rows(status, uptime, now):
    stats = status.get('stats') or {}
    last = stats.get('last_index') or {}
    count = last.get('files')
    size = last.get('bytes')
    stamp = last.get('at')
    date = datetime.fromtimestamp(stamp, now.tzinfo).strftime('%d.%m.%Y %H:%M %Z') if stamp is not None else 'noch nicht erfasst'
    runs = stats.get('index_runs')
    return [
        ('Dateien (letzter erfolgreicher Index)', f'{count:,}'.replace(',', '.') if count is not None else 'noch nicht erfasst'),
        ('Größe der Audiodateien', f'{size / 1_000_000_000:.2f} GB' if size is not None else 'noch nicht vollständig erfasst'),
        ('Gesamtlaufzeit', duration(stats.get('uptime_seconds'))),
        ('Aktuelle Sitzung', duration(stats.get('session_seconds', uptime))),
        ('Dienststarts', str(stats.get('starts', 'noch nicht erfasst'))),
        ('Indizierungen: gesamt / erfolgreich / Fehler', f"{runs} / {stats.get('index_successes', 0)} / {stats.get('index_failures', 0)}" if runs is not None else 'noch nicht erfasst'),
        ('Letzter erfolgreicher Index', date),
        ('Dauer dieses Indexlaufs', f"{last['duration']:.1f} s" if 'duration' in last else 'noch nicht erfasst'),
    ]


def caption(status, uptime, now, daily=False):
    from html import escape
    title = '🌙 MP3z · Tagesstatus 22:00' if daily else '🎧 MP3z ist gestartet'
    data = status.get('stats') or {}
    state = '🟡 Index wird aufgebaut' if status.get('building') else '⚪ Index ruhend'
    source = 'aktueller erfolgreicher Scan' if data.get('snapshot_source') == 'current' else 'zuletzt gespeicherter Stand'
    lines = [f'<b>{title}</b>', state, f'Stand: {source}']
    if not data.get('persistent'): lines.append('⚠ Statistik nicht dauerhaft gespeichert')
    for label, value in rows(status, uptime, now):
        lines.append(f'{escape(label)}: <b>{escape(value)}</b>')
    storage = {'smb': 'SMB', 'local': 'Lokal'}.get(status.get('storage'), 'unbekannt')
    lines.append(f'Speicher: {storage}')
    lines.append(now.strftime('%d.%m.%Y %H:%M %Z'))
    return '\n'.join(lines)


def render(status, uptime, now, daily=False):
    image = Image.new('RGB', (1100, 940), '#101522')
    draw = ImageDraw.Draw(image)
    def font(size):
        try: return ImageFont.truetype('DejaVuSans.ttf', size)
        except OSError:
            try: return ImageFont.load_default(size=size)
            except TypeError: return ImageFont.load_default()
    def text(x, y, value, size=24, color='#edf5ff', width=960):
        value = str(value); selected = font(size)
        while draw.textbbox((0, 0), value, font=selected)[2] > width and len(value) > 1:
            value = value[:-2] + '~'
        draw.text((x, y), value, fill=color, font=selected)
    for x in range(1100):
        t = x / 1099
        draw.line((x, 0, x, 9), fill=(int(70+160*t), int(200-65*t), int(220-110*t)))
    text(40, 30, 'MP3z', 48)
    text(40, 95, 'Tagesstatus 22:00' if daily else 'Dienst gestartet', 30)
    data = status.get('stats') or {}
    text(40, 145, 'Index wird aufgebaut' if status.get('building') else 'Index ruhend', 22, '#fbbf60' if status.get('building') else '#93c5fd')
    source = 'Aktueller erfolgreicher Scan' if data.get('snapshot_source') == 'current' else 'Zuletzt gespeicherter Stand'
    text(40, 185, source, 20, '#a7b6cc')
    for i, (label, value) in enumerate(rows(status, uptime, now)):
        x, y = 40+(i % 2)*520, 235+(i // 2)*145
        draw.rounded_rectangle((x,y,x+500,y+125),radius=18,fill='#1b2638',outline='#304059',width=2)
        text(x+18,y+15,label,16,'#a7b6cc',464)
        text(x+18,y+52,value,25,'#edf5ff',464)
    text(40, 838, 'Persistenz aktiv' if data.get('persistent') else 'WARNUNG: Statistik nur im Arbeitsspeicher', 21, '#6ee7b7' if data.get('persistent') else '#fbbf60')
    text(40, 890, now.strftime('%d.%m.%Y %H:%M %Z')+'  |  HIGHFISH AI', 20, '#a7b6cc')
    out = io.BytesIO(); image.save(out, 'JPEG', quality=90, optimize=True)
    return out.getvalue()


def send_startup(bot, chat, status, uptime, now, daily=False):
    payload = {'chat_id': chat, 'caption': caption(status, uptime, now, daily=daily), 'parse_mode': 'HTML'}
    url = getattr(bot, 'url', None)
    if url:
        payload['reply_markup'] = {'inline_keyboard': [[{'text': '🎧 Webplayer öffnen', 'url': url}]]}
    try:
        image = render(status, uptime, now, daily=daily)
        bot.call('sendPhoto', payload, image=image)
    except Exception:
        payload['text'] = payload.pop('caption')
        bot.call('sendMessage', payload)
